"""Evaluate LLM structured-output stability for test-case generation.

This eval measures only:
LLM response -> JSON parsing -> schema validation -> structured-output repair.

It intentionally does not call the rule-based fallback used by the production
case-generation pipeline.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.tools.case_generator import build_prompt  # noqa: E402


class TestCaseModel(BaseModel):
    case_id: str
    title: str
    precondition: str
    steps: list[str]
    expected_result: str


DEFAULT_REQUIREMENT = """
用户主动取消未接单订单后，订单状态变为 cancelled。
如果订单创建后 3 分钟内没有司机接单，系统自动取消订单。
如果司机已接单，用户取消订单时必须记录取消原因。
订单取消后司机资源应释放。
"""


TARGET_JSON_SCHEMA: dict[str, Any] = {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["case_id", "title", "precondition", "steps", "expected_result"],
        "properties": {
            "case_id": {"type": "string"},
            "title": {"type": "string"},
            "precondition": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
            "expected_result": {"type": "string"},
        },
        "additionalProperties": True,
    },
}


API_ERROR_TYPES = {
    "insufficient_balance",
    "rate_limit",
    "timeout",
    "network_error",
    "5xx",
    "other_api_error",
}


FORMAT_ERROR_TYPES = {
    "json_decode_error",
    "markdown_parse_error",
    "wrong_root_type",
    "missing_field",
    "field_type_error",
    "validation_error",
    "other_format_error",
}


def call_llm(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {
                "role": "system",
                "content": "You are a strict test engineer. Return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content or ""


def build_repair_prompt(requirement: str, raw_output: str, error_message: str) -> str:
    schema = json.dumps(TARGET_JSON_SCHEMA, ensure_ascii=False, indent=2)
    return f"""
The previous model output failed structured-output validation.

Original requirement:
{requirement}

Previous raw model output:
{raw_output}

Parsing or validation error:
{error_message}

Target JSON Schema:
{schema}

Return only the repaired JSON array. Do not add Markdown code fences,
comments, explanations, or any text outside the JSON.
"""


def strip_markdown_fence(text: str) -> tuple[str, str | None]:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped, None

    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return stripped, "markdown_parse_error"
    return match.group(1).strip(), None


def parse_json_array(raw_output: str) -> list[dict[str, Any]]:
    candidate, markdown_error = strip_markdown_fence(raw_output)
    if markdown_error:
        raise ValueError(markdown_error)

    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as first_error:
        start = candidate.find("[")
        end = candidate.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise first_error
        data = json.loads(candidate[start : end + 1])

    if not isinstance(data, list):
        raise TypeError("wrong_root_type")
    return data


def validate_cases(data: Any) -> list[TestCaseModel]:
    if not isinstance(data, list):
        raise TypeError("wrong_root_type")
    return [TestCaseModel.model_validate(item) for item in data]


def classify_validation_error(exc: ValidationError) -> tuple[str, list[dict[str, Any]]]:
    errors = exc.errors()
    error_types = {error.get("type", "") for error in errors}
    if any(error_type == "missing" for error_type in error_types):
        return "missing_field", errors
    if any("list_type" in error_type or "string_type" in error_type for error_type in error_types):
        return "field_type_error", errors
    return "validation_error", errors


def classify_format_exception(exc: Exception) -> tuple[str, str, list[dict[str, Any]]]:
    if isinstance(exc, ValidationError):
        error_type, validation_errors = classify_validation_error(exc)
        return error_type, str(exc), validation_errors
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error", str(exc), []
    if isinstance(exc, TypeError) and str(exc) == "wrong_root_type":
        return "wrong_root_type", "LLM output root must be a JSON array", []
    if isinstance(exc, ValueError) and str(exc) == "markdown_parse_error":
        return "markdown_parse_error", "Malformed Markdown code block around JSON", []
    return "other_format_error", str(exc), []


def get_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def classify_api_exception(exc: Exception) -> tuple[str, str, int | None, bool]:
    status_code = get_status_code(exc)
    message = str(exc)
    lower_message = message.lower()
    class_name = type(exc).__name__.lower()

    if status_code == 402 or "insufficient balance" in lower_message:
        return "insufficient_balance", message, status_code, False
    if status_code == 429 or "rate limit" in lower_message:
        return "rate_limit", message, status_code, True
    if "timeout" in class_name or "timeout" in lower_message or "timed out" in lower_message:
        return "timeout", message, status_code, True
    if "connection" in class_name or "network" in lower_message or "connection" in lower_message:
        return "network_error", message, status_code, True
    if status_code is not None and 500 <= status_code <= 599:
        return "5xx", message, status_code, True
    return "other_api_error", message, status_code, False


def is_api_exception(exc: Exception) -> bool:
    status_code = get_status_code(exc)
    class_name = type(exc).__name__.lower()
    if status_code is not None:
        return True
    return any(name in class_name for name in ["api", "openai", "timeout", "connection"])


def make_attempt(
    attempt_no: int,
    retry_type: str | None,
    started: float,
    raw_output: str | None = None,
) -> dict[str, Any]:
    return {
        "attempt_no": attempt_no,
        "api_success": False,
        "status_code": None,
        "raw_output": raw_output,
        "json_valid": None,
        "schema_valid": None,
        "validation_errors": [],
        "retry_type": retry_type,
        "retryable": False,
        "error_type": None,
        "error_message": None,
        "duration_seconds": round(time.perf_counter() - started, 4),
    }


def evaluate_output(raw_output: str) -> tuple[bool, bool, str | None, str | None, list[dict[str, Any]]]:
    try:
        raw_cases = parse_json_array(raw_output)
        json_valid = True
        validate_cases(raw_cases)
        return json_valid, True, None, None, []
    except Exception as exc:
        error_type, error_message, validation_errors = classify_format_exception(exc)
        json_valid = error_type not in {"json_decode_error", "markdown_parse_error", "wrong_root_type"}
        return json_valid, False, error_type, error_message, validation_errors


def evaluate_once(
    run_id: int,
    requirement: str,
    max_api_retries: int = 1,
    max_format_retries: int = 1,
    call_fn: Callable[[str], str] = call_llm,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    prompt = build_prompt(requirement)
    retry_type: str | None = None
    api_retry_count = 0
    format_retry_count = 0

    while True:
        attempt_no = len(attempts) + 1
        started = time.perf_counter()
        attempt = make_attempt(attempt_no, retry_type, started)

        try:
            raw_output = call_fn(prompt)
            attempt["api_success"] = True
            attempt["raw_output"] = raw_output

            json_valid, schema_valid, error_type, error_message, validation_errors = evaluate_output(raw_output)
            attempt["json_valid"] = json_valid
            attempt["schema_valid"] = schema_valid
            attempt["structured_output_success"] = json_valid and schema_valid
            attempt["validation_errors"] = validation_errors
            attempt["error_type"] = error_type
            attempt["error_message"] = error_message

            if attempt["structured_output_success"]:
                attempt["retryable"] = False
                attempt["duration_seconds"] = round(time.perf_counter() - started, 4)
                attempts.append(attempt)
                break

            if format_retry_count < max_format_retries:
                attempt["retryable"] = True
                format_retry_count += 1
                retry_type = "format_repair"
                prompt = build_repair_prompt(requirement, raw_output, error_message or "unknown format error")
                attempt["duration_seconds"] = round(time.perf_counter() - started, 4)
                attempts.append(attempt)
                continue

            attempt["retryable"] = False
            attempt["duration_seconds"] = round(time.perf_counter() - started, 4)
            attempts.append(attempt)
            break

        except Exception as exc:
            if is_api_exception(exc):
                error_type, error_message, status_code, retryable = classify_api_exception(exc)
                attempt["status_code"] = status_code
                attempt["error_type"] = error_type
                attempt["error_message"] = error_message
                attempt["retryable"] = retryable and api_retry_count < max_api_retries
                attempt["duration_seconds"] = round(time.perf_counter() - started, 4)
                attempts.append(attempt)

                if attempt["retryable"]:
                    api_retry_count += 1
                    retry_type = "api_retry"
                    sleep_fn(min(2 ** api_retry_count, 8))
                    continue
                break

            error_type, error_message, validation_errors = classify_format_exception(exc)
            attempt["api_success"] = True
            attempt["json_valid"] = error_type not in {"json_decode_error", "markdown_parse_error", "wrong_root_type"}
            attempt["schema_valid"] = False
            attempt["structured_output_success"] = False
            attempt["validation_errors"] = validation_errors
            attempt["error_type"] = error_type
            attempt["error_message"] = error_message
            attempt["retryable"] = format_retry_count < max_format_retries
            attempt["duration_seconds"] = round(time.perf_counter() - started, 4)
            attempts.append(attempt)
            if attempt["retryable"]:
                format_retry_count += 1
                retry_type = "format_repair"
                prompt = build_repair_prompt(requirement, attempt.get("raw_output") or "", error_message)
                continue
            break

    api_success = any(attempt["api_success"] for attempt in attempts)
    final_attempt = attempts[-1]
    final_structured_success = bool(final_attempt.get("structured_output_success"))

    return {
        "run_id": run_id,
        "input": requirement.strip(),
        "attempts": attempts,
        "api_success": api_success,
        "api_error": not api_success,
        "json_valid": final_attempt["json_valid"],
        "schema_valid": final_attempt["schema_valid"],
        "structured_output_success": final_structured_success,
        "retryable": final_attempt["retryable"],
        "error_type": final_attempt["error_type"],
        "error_message": final_attempt["error_message"],
        "retry_count": max(0, len(attempts) - 1),
        "format_retry_triggered": any(attempt["retry_type"] == "format_repair" for attempt in attempts[1:]),
        "api_retry_triggered": any(attempt["retry_type"] == "api_retry" for attempt in attempts[1:]),
        "final_success": api_success and final_structured_success,
    }


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def summarize(results: list[dict[str, Any]], planned_runs: int | None = None) -> dict[str, Any]:
    planned = planned_runs if planned_runs is not None else len(results)
    api_success_runs = sum(1 for item in results if item["api_success"])
    api_error_runs = planned - api_success_runs
    api_error_breakdown: dict[str, int] = {}
    for item in results:
        if item["api_success"]:
            continue
        error_type = item.get("error_type") or "unknown_api_error"
        api_error_breakdown[error_type] = api_error_breakdown.get(error_type, 0) + 1

    response_results = [item for item in results if item["api_success"]]
    first_pass_structured_success = sum(
        1
        for item in response_results
        if item["attempts"][0].get("structured_output_success")
    )
    format_retry_triggered = sum(1 for item in response_results if item["format_retry_triggered"])
    format_retry_recovered = sum(
        1
        for item in response_results
        if item["format_retry_triggered"] and item["structured_output_success"]
    )
    final_structured_success = sum(1 for item in response_results if item["structured_output_success"])
    overall_completed_runs = sum(1 for item in results if item["final_success"])

    return {
        "api_reliability": {
            "planned_runs": planned,
            "api_success_runs": api_success_runs,
            "api_error_runs": api_error_runs,
            "api_success_rate": rate(api_success_runs, planned),
            "api_error_breakdown": api_error_breakdown,
        },
        "structured_output_quality": {
            "llm_response_count": len(response_results),
            "first_pass_structured_success": first_pass_structured_success,
            "first_pass_structured_success_rate": rate(first_pass_structured_success, len(response_results)),
            "format_retry_triggered": format_retry_triggered,
            "format_retry_recovered": format_retry_recovered,
            "final_structured_success": final_structured_success,
            "final_structured_success_rate": rate(final_structured_success, len(response_results)),
        },
        "overall": {
            "overall_completed_runs": overall_completed_runs,
            "overall_completion_rate": rate(overall_completed_runs, planned),
        },
        "results": results,
    }


def write_json_report(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(summary, ensure_ascii=False, indent=2)
    json.loads(serialized)
    output_path.write_text(serialized, encoding="utf-8")
    json.loads(output_path.read_text(encoding="utf-8"))


def main() -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    runs = int(os.getenv("STRUCTURED_EVAL_RUNS", "30"))
    max_api_retries = int(os.getenv("STRUCTURED_EVAL_MAX_API_RETRIES", "1"))
    max_format_retries = int(os.getenv("STRUCTURED_EVAL_MAX_FORMAT_RETRIES", "1"))
    output_path = PROJECT_ROOT / "reports" / "structured_output_eval.json"

    results = [
        evaluate_once(
            index,
            DEFAULT_REQUIREMENT,
            max_api_retries=max_api_retries,
            max_format_retries=max_format_retries,
        )
        for index in range(1, runs + 1)
    ]
    summary = summarize(results, planned_runs=runs)
    write_json_report(summary, output_path)

    printable = {key: value for key, value in summary.items() if key != "results"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
