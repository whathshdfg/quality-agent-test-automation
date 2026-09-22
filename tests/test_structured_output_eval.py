import json

import pytest

from evals.eval_structured_output import (
    build_repair_prompt,
    classify_api_exception,
    evaluate_once,
    evaluate_output,
    parse_json_array,
    summarize,
    write_json_report,
)


VALID_CASES = [
    {
        "case_id": "TC_CANCEL_001",
        "title": "cancel waiting order",
        "precondition": "order is waiting",
        "steps": ["create order", "cancel order"],
        "expected_result": "order is cancelled",
    }
]


def as_json(value):
    return json.dumps(value)


class FakeApiError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class FakeTimeoutError(Exception):
    pass


def test_parse_valid_json_array():
    assert parse_json_array(as_json(VALID_CASES)) == VALID_CASES


def test_parse_markdown_wrapped_json_array():
    raw = f"```json\n{as_json(VALID_CASES)}\n```"
    assert parse_json_array(raw) == VALID_CASES


def test_parse_json_array_with_surrounding_text():
    raw = f"Here are cases:\n{as_json(VALID_CASES)}\nDone."
    assert parse_json_array(raw) == VALID_CASES


def test_evaluate_output_missing_field():
    invalid = [{key: value for key, value in VALID_CASES[0].items() if key != "expected_result"}]
    json_valid, schema_valid, error_type, _, validation_errors = evaluate_output(as_json(invalid))
    assert json_valid is True
    assert schema_valid is False
    assert error_type == "missing_field"
    assert validation_errors


def test_evaluate_output_field_type_error():
    invalid = [dict(VALID_CASES[0], steps="not a list")]
    json_valid, schema_valid, error_type, _, validation_errors = evaluate_output(as_json(invalid))
    assert json_valid is True
    assert schema_valid is False
    assert error_type == "field_type_error"
    assert validation_errors


def test_evaluate_output_wrong_root_type():
    json_valid, schema_valid, error_type, _, _ = evaluate_output(as_json({"cases": VALID_CASES}))
    assert json_valid is False
    assert schema_valid is False
    assert error_type == "wrong_root_type"


def test_classify_402_api_error_is_not_retryable():
    error_type, _, status_code, retryable = classify_api_exception(
        FakeApiError("Error code: 402 - Insufficient Balance", status_code=402)
    )
    assert error_type == "insufficient_balance"
    assert status_code == 402
    assert retryable is False


def test_classify_429_api_error_is_retryable():
    error_type, _, status_code, retryable = classify_api_exception(
        FakeApiError("rate limit exceeded", status_code=429)
    )
    assert error_type == "rate_limit"
    assert status_code == 429
    assert retryable is True


def test_classify_timeout_is_retryable():
    error_type, _, status_code, retryable = classify_api_exception(FakeTimeoutError("request timed out"))
    assert error_type == "timeout"
    assert status_code is None
    assert retryable is True


def test_evaluate_once_402_does_not_retry_and_json_schema_are_null():
    calls = []

    def call_fn(_):
        calls.append("call")
        raise FakeApiError("Error code: 402 - Insufficient Balance", status_code=402)

    result = evaluate_once(1, "requirement", call_fn=call_fn, sleep_fn=lambda _: None)

    assert len(calls) == 1
    assert result["api_success"] is False
    assert result["error_type"] == "insufficient_balance"
    assert result["json_valid"] is None
    assert result["schema_valid"] is None
    assert result["attempts"][0]["retryable"] is False


def test_evaluate_once_429_retries_then_succeeds():
    outputs = [FakeApiError("rate limit exceeded", status_code=429), as_json(VALID_CASES)]

    def call_fn(_):
        item = outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    result = evaluate_once(1, "requirement", call_fn=call_fn, sleep_fn=lambda _: None)

    assert result["api_success"] is True
    assert result["final_success"] is True
    assert result["api_retry_triggered"] is True
    assert len(result["attempts"]) == 2


def test_evaluate_once_structured_output_repair_success():
    prompts = []
    outputs = [
        as_json([{"case_id": "TC_001", "title": "missing fields"}]),
        as_json(VALID_CASES),
    ]

    def call_fn(prompt):
        prompts.append(prompt)
        return outputs.pop(0)

    result = evaluate_once(1, "requirement", call_fn=call_fn, sleep_fn=lambda _: None)

    assert result["final_success"] is True
    assert result["format_retry_triggered"] is True
    assert len(result["attempts"]) == 2
    assert "Previous raw model output" in prompts[1]
    assert "Target JSON Schema" in prompts[1]
    assert prompts[0] != prompts[1]


def test_build_repair_prompt_contains_required_context():
    prompt = build_repair_prompt("req", "[bad]", "json error")
    assert "req" in prompt
    assert "[bad]" in prompt
    assert "json error" in prompt
    assert "Target JSON Schema" in prompt
    assert "Do not add Markdown" in prompt


def test_write_json_report_produces_loadable_json(tmp_path):
    result = evaluate_once(1, "requirement", call_fn=lambda _: as_json(VALID_CASES), sleep_fn=lambda _: None)
    summary = summarize([result], planned_runs=1)
    output_path = tmp_path / "structured_output_eval.json"

    write_json_report(summary, output_path)

    with output_path.open(encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["api_reliability"]["planned_runs"] == 1
    assert loaded["structured_output_quality"]["llm_response_count"] == 1


def test_summary_excludes_api_errors_from_structured_output_denominator():
    success = evaluate_once(1, "requirement", call_fn=lambda _: as_json(VALID_CASES), sleep_fn=lambda _: None)

    def api_error(_):
        raise FakeApiError("Error code: 402 - Insufficient Balance", status_code=402)

    failed_api = evaluate_once(2, "requirement", call_fn=api_error, sleep_fn=lambda _: None)
    summary = summarize([success, failed_api], planned_runs=2)

    assert summary["api_reliability"]["api_success_runs"] == 1
    assert summary["api_reliability"]["api_error_breakdown"] == {"insufficient_balance": 1}
    assert summary["structured_output_quality"]["llm_response_count"] == 1
    assert summary["structured_output_quality"]["final_structured_success_rate"] == 100.0
