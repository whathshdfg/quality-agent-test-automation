import json
from pathlib import Path

from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    RequirementRule,
    TestPoint,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_PATH = PROJECT_ROOT / "evals" / "test_design_acceptance_dataset.json"


def load_dataset() -> dict:
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def test_acceptance_dataset_has_three_supported_businesses():
    dataset = load_dataset()
    business_types = {item["business_type"] for item in dataset["cases"]}

    assert dataset["dataset_version"] == "1.0.0"
    assert business_types == {
        BusinessType.ORDER_CANCEL.value,
        BusinessType.PAYMENT.value,
        BusinessType.ORDER_CREATE.value,
    }


def test_acceptance_rules_and_test_points_follow_contracts():
    dataset = load_dataset()
    all_rule_ids = set()
    all_test_point_ids = set()

    for acceptance_case in dataset["cases"]:
        business_type = BusinessType(acceptance_case["business_type"])
        rules = [
            RequirementRule.model_validate(item)
            for item in acceptance_case["requirement_rules"]
        ]
        test_points = [
            TestPoint.model_validate(item)
            for item in acceptance_case["expected_test_points"]
        ]
        local_rule_ids = {rule.rule_id for rule in rules}

        assert acceptance_case["case_id"]
        assert acceptance_case["requirement"].strip()
        assert local_rule_ids
        assert all(rule.business_type == business_type for rule in rules)
        assert all(point.business_type == business_type for point in test_points)
        assert all(set(point.requirement_ids) <= local_rule_ids for point in test_points)
        assert not (all_rule_ids & local_rule_ids)

        local_point_ids = {point.test_point_id for point in test_points}
        assert len(local_point_ids) == len(test_points)
        assert not (all_test_point_ids & local_point_ids)

        all_rule_ids.update(local_rule_ids)
        all_test_point_ids.update(local_point_ids)


def test_each_business_has_core_layered_coverage_expectations():
    dataset = load_dataset()
    required_categories = {
        CoverageCategory.FUNCTIONAL_BEHAVIOR,
        CoverageCategory.INPUT_PARAMETER,
        CoverageCategory.STATE_FLOW,
        CoverageCategory.DATA_QUALITY,
        CoverageCategory.RELIABILITY,
    }

    for acceptance_case in dataset["cases"]:
        test_points = [
            TestPoint.model_validate(item)
            for item in acceptance_case["expected_test_points"]
        ]
        categories = {point.level_1 for point in test_points}

        assert required_categories <= categories


def test_every_requirement_rule_has_at_least_one_test_point():
    dataset = load_dataset()

    for acceptance_case in dataset["cases"]:
        rule_ids = {
            item["rule_id"]
            for item in acceptance_case["requirement_rules"]
        }
        referenced_rule_ids = {
            requirement_id
            for point in acceptance_case["expected_test_points"]
            for requirement_id in point["requirement_ids"]
        }

        assert rule_ids <= referenced_rule_ids
