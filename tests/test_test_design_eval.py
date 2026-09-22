import json

import pytest

from evals.eval_test_design import (
    evaluate_acceptance_case,
    evaluate_dataset,
    force_rule_fallback,
    load_dataset,
    summarize,
    write_report,
)


def test_rule_mode_evaluates_all_acceptance_cases_without_api():
    dataset = load_dataset()

    summary = evaluate_dataset(dataset, mode="rule")

    assert summary["mode"] == "rule"
    assert summary["total_cases"] == 3
    assert summary["business_classification_accuracy"] == 100
    assert summary["average_rule_recall_rate"] == 100
    assert summary["average_rule_to_test_point_rate"] == 100
    assert summary["invalid_reference_count"] == 0
    assert summary["fallback_count"] == 6


def test_evaluation_exposes_layer_gaps_instead_of_hiding_them():
    summary = evaluate_dataset(load_dataset(), mode="rule")
    order_result = next(
        item
        for item in summary["details"]
        if item["case_id"] == "ACCEPT_ORDER_CREATE_001"
    )

    assert "data_quality" in order_result["expected_categories"]
    assert "data_quality" not in order_result["actual_categories"]
    assert order_result["layer_coverage_rate"] < 100
    assert summary["average_layer_coverage_rate"] < 100


def test_single_case_records_sources_and_fallback_reasons():
    acceptance_case = load_dataset()["cases"][0]

    result = evaluate_acceptance_case(
        acceptance_case,
        requirement_call_fn=force_rule_fallback,
        test_point_call_fn=force_rule_fallback,
    )

    assert result["requirement_source"] == "rule"
    assert result["test_point_source"] == "rule"
    assert "rule-only evaluation" in result["requirement_fallback_reason"]
    assert "rule-only evaluation" in result["test_point_fallback_reason"]


def test_summary_handles_empty_results():
    summary = summarize([], dataset_version="test")

    assert summary["total_cases"] == 0
    assert summary["business_classification_accuracy"] == 0
    assert summary["average_rule_recall_rate"] == 0


def test_write_report_creates_valid_json(tmp_path):
    output_path = tmp_path / "test_design_eval.json"
    summary = evaluate_dataset(load_dataset(), mode="rule")

    write_report(summary, output_path)
    loaded = json.loads(output_path.read_text(encoding="utf-8"))

    assert loaded["dataset_version"] == "1.0.0"
    assert loaded["total_cases"] == 3


def test_invalid_mode_is_rejected():
    with pytest.raises(ValueError, match="rule 或 api"):
        evaluate_dataset(load_dataset(), mode="unsupported")
