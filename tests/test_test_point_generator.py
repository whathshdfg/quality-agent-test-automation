import json

import pytest

from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    ParameterSpec,
    RequirementRule,
)
from app.tools.test_point_generator import (
    build_test_point_prompt,
    generate_rule_based_test_points,
    generate_test_points,
    validate_test_points,
)


def make_rule(
    rule_id: str = "REQ_CANCEL_001",
    business_type: BusinessType = BusinessType.ORDER_CANCEL,
) -> RequirementRule:
    return RequirementRule(
        rule_id=rule_id,
        text="用户取消 waiting 订单后状态变为 cancelled",
        business_type=business_type,
        action="cancel_order",
        expected_outcomes=["order_status=cancelled"],
        parameters=[
            ParameterSpec(
                name="order_id",
                data_type="string",
                required=True,
                invalid_values=["order_not_exists"],
            )
        ],
        risks=["state_transition", "idempotency", "data_consistency"],
    )


def valid_point() -> dict:
    return {
        "test_point_id": "TP_CANCEL_001",
        "requirement_ids": ["REQ_CANCEL_001"],
        "business_type": "order_cancel",
        "level_1": "state_flow",
        "level_2": "合法状态迁移",
        "description": "waiting 状态迁移为 cancelled",
        "risk_level": "high",
        "executable": True,
        "unsupported_reason": "",
    }


def test_prompt_contains_layer_definitions_and_serialized_rules():
    prompt = build_test_point_prompt([make_rule()])

    assert "不要生成测试用例步骤" in prompt
    assert "functional_behavior" in prompt
    assert "resource_dependency" in prompt
    assert "REQ_CANCEL_001" in prompt


def test_validate_test_points_accepts_valid_references():
    points = validate_test_points([valid_point()], [make_rule()])

    assert points[0].level_1 == CoverageCategory.STATE_FLOW


def test_validate_test_points_rejects_unknown_requirement_reference():
    point = valid_point()
    point["requirement_ids"] = ["REQ_NOT_EXISTS"]

    with pytest.raises(ValueError, match="不存在的需求规则"):
        validate_test_points([point], [make_rule()])


def test_validate_test_points_rejects_business_mismatch():
    point = valid_point()
    point["business_type"] = "payment"

    with pytest.raises(ValueError, match="业务类型"):
        validate_test_points([point], [make_rule()])


def test_validate_test_points_requires_every_rule_to_be_covered():
    second_rule = make_rule("REQ_CANCEL_002")

    with pytest.raises(ValueError, match="没有对应测试点"):
        validate_test_points([valid_point()], [make_rule(), second_rule])


def test_successful_model_result_records_llm_source():
    result = generate_test_points(
        [make_rule()],
        call_fn=lambda _: json.dumps([valid_point()], ensure_ascii=False),
    )

    assert result["source"] == "llm"
    assert result["fallback_reason"] == ""
    assert result["test_points"][0].test_point_id == "TP_CANCEL_001"


def test_invalid_model_result_falls_back_to_layered_rule_points():
    result = generate_test_points(
        [make_rule()],
        call_fn=lambda _: "not-json",
    )
    categories = {point.level_1 for point in result["test_points"]}

    assert result["source"] == "rule"
    assert "ValueError" in result["fallback_reason"]
    assert CoverageCategory.FUNCTIONAL_BEHAVIOR in categories
    assert CoverageCategory.INPUT_PARAMETER in categories
    assert CoverageCategory.STATE_FLOW in categories
    assert CoverageCategory.RELIABILITY in categories
    assert CoverageCategory.DATA_QUALITY in categories


def test_unknown_business_rule_creates_non_executable_point():
    unknown_rule = RequirementRule(
        rule_id="REQ_UNKNOWN_001",
        text="查询天气",
        business_type=BusinessType.UNKNOWN,
        action="manual_requirement_review",
        expected_outcomes=["人工确认"],
        risks=["unsupported_business"],
    )

    points = generate_rule_based_test_points([unknown_rule])

    assert points
    assert all(point.executable is False for point in points)
    assert all(point.unsupported_reason for point in points)


def test_empty_rule_list_is_rejected_before_model_call():
    with pytest.raises(ValueError, match="不能为空"):
        generate_test_points([], call_fn=lambda _: "[]")
