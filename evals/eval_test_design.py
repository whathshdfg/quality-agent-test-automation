"""Evaluate requirement extraction and layered test-point generation."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.models.test_design import RequirementRule  # noqa: E402
from app.tools.requirement_analyzer import analyze_requirement  # noqa: E402
from app.tools.test_point_generator import generate_test_points  # noqa: E402


DATASET_PATH = PROJECT_ROOT / "evals" / "test_design_acceptance_dataset.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "test_design_eval.json"


def load_dataset(path: Path = DATASET_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100, 2) if denominator else 0.0


def force_rule_fallback(_: str) -> str:
    raise RuntimeError("rule-only evaluation")


def evaluate_acceptance_case(
    acceptance_case: dict[str, Any],
    requirement_call_fn: Callable[[str], str] | None = None,
    test_point_call_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    requirement_result = analyze_requirement(
        acceptance_case["requirement"],
        call_fn=requirement_call_fn,
    )
    rules = requirement_result["rules"]
    point_result = generate_test_points(rules, call_fn=test_point_call_fn)
    points = point_result["test_points"]

    expected_business = acceptance_case["business_type"]
    actual_businesses = {rule.business_type.value for rule in rules}
    business_classification_correct = actual_businesses == {expected_business}

    expected_rule_ids = {
        item["rule_id"] for item in acceptance_case["requirement_rules"]
    }
    actual_rule_ids = {rule.rule_id for rule in rules}
    matched_rule_ids = expected_rule_ids & actual_rule_ids

    expected_categories = {
        item["level_1"] for item in acceptance_case["expected_test_points"]
    }
    actual_categories = {point.level_1.value for point in points}
    matched_categories = expected_categories & actual_categories

    referenced_rule_ids = {
        rule_id
        for point in points
        for rule_id in point.requirement_ids
    }
    invalid_reference_ids = sorted(referenced_rule_ids - actual_rule_ids)
    covered_actual_rule_ids = referenced_rule_ids & actual_rule_ids

    return {
        "case_id": acceptance_case["case_id"],
        "expected_business_type": expected_business,
        "actual_business_types": sorted(actual_businesses),
        "business_classification_correct": business_classification_correct,
        "expected_rule_ids": sorted(expected_rule_ids),
        "actual_rule_ids": sorted(actual_rule_ids),
        "matched_rule_ids": sorted(matched_rule_ids),
        "rule_recall_rate": rate(len(matched_rule_ids), len(expected_rule_ids)),
        "expected_categories": sorted(expected_categories),
        "actual_categories": sorted(actual_categories),
        "matched_categories": sorted(matched_categories),
        "layer_coverage_rate": rate(
            len(matched_categories),
            len(expected_categories),
        ),
        "rule_to_test_point_rate": rate(
            len(covered_actual_rule_ids),
            len(actual_rule_ids),
        ),
        "invalid_reference_ids": invalid_reference_ids,
        "non_executable_test_points": sum(
            1 for point in points if point.executable is False
        ),
        "requirement_source": requirement_result["source"],
        "test_point_source": point_result["source"],
        "fallback_count": sum(
            source == "rule"
            for source in [
                requirement_result["source"],
                point_result["source"],
            ]
        ),
        "requirement_fallback_reason": requirement_result["fallback_reason"],
        "test_point_fallback_reason": point_result["fallback_reason"],
        "requirement_rule_count": len(rules),
        "test_point_count": len(points),
    }


def summarize(results: list[dict[str, Any]], dataset_version: str) -> dict[str, Any]:
    total_cases = len(results)
    classification_passed = sum(
        item["business_classification_correct"] for item in results
    )
    invalid_reference_count = sum(
        len(item["invalid_reference_ids"]) for item in results
    )

    return {
        "dataset_version": dataset_version,
        "total_cases": total_cases,
        "business_classification_accuracy": rate(
            classification_passed,
            total_cases,
        ),
        "average_rule_recall_rate": round(
            sum(item["rule_recall_rate"] for item in results) / total_cases,
            2,
        ) if total_cases else 0.0,
        "average_rule_to_test_point_rate": round(
            sum(item["rule_to_test_point_rate"] for item in results) / total_cases,
            2,
        ) if total_cases else 0.0,
        "average_layer_coverage_rate": round(
            sum(item["layer_coverage_rate"] for item in results) / total_cases,
            2,
        ) if total_cases else 0.0,
        "invalid_reference_count": invalid_reference_count,
        "non_executable_test_point_count": sum(
            item["non_executable_test_points"] for item in results
        ),
        "fallback_count": sum(item["fallback_count"] for item in results),
        "details": results,
    }


def evaluate_dataset(
    dataset: dict[str, Any],
    mode: str = "rule",
) -> dict[str, Any]:
    if mode not in {"rule", "api"}:
        raise ValueError("mode 必须是 rule 或 api")

    requirement_call_fn = force_rule_fallback if mode == "rule" else None
    test_point_call_fn = force_rule_fallback if mode == "rule" else None
    results = [
        evaluate_acceptance_case(
            acceptance_case,
            requirement_call_fn=requirement_call_fn,
            test_point_call_fn=test_point_call_fn,
        )
        for acceptance_case in dataset["cases"]
    ]
    summary = summarize(results, dataset["dataset_version"])
    summary["mode"] = mode
    return summary


def write_report(summary: dict[str, Any], path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    mode = os.getenv("TEST_DESIGN_EVAL_MODE", "rule").strip().lower()
    summary = evaluate_dataset(load_dataset(), mode=mode)
    write_report(summary)

    printable = {key: value for key, value in summary.items() if key != "details"}
    print(json.dumps(printable, ensure_ascii=False, indent=2))
    print(f"Saved: {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

