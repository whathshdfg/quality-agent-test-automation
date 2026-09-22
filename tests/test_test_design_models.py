import pytest
from pydantic import ValidationError

from app.models.test_design import (
    AssertionSpec,
    BusinessType,
    CoverageCategory,
    CoverageEvidence,
    CoverageMatrix,
    CoverageSummary,
    ParameterSpec,
    RequirementRule,
    TestCaseSpec,
    TestPoint,
)


def test_legacy_five_field_case_remains_valid():
    case = TestCaseSpec.model_validate({
        "case_id": "TC_CANCEL_001",
        "title": "用户主动取消未接单订单",
        "precondition": "订单状态为 waiting",
        "steps": ["调用取消订单接口", "查询订单状态"],
        "expected_result": "订单状态变为 cancelled",
    })

    assert case.business_type == BusinessType.UNKNOWN
    assert case.generation_source == "unknown"
    assert case.requirement_ids == []


def test_structured_requirement_test_point_and_case_are_valid():
    parameter = ParameterSpec(
        name="order_id",
        data_type="string",
        required=True,
        invalid_values=["order_not_exists"],
    )
    rule = RequirementRule(
        rule_id="REQ_CANCEL_001",
        text="用户取消 waiting 订单后，订单状态变为 cancelled",
        business_type=BusinessType.ORDER_CANCEL,
        actor="user",
        trigger="cancel_order",
        preconditions=["order_status=waiting"],
        action="cancel_order",
        expected_outcomes=["order_status=cancelled"],
        parameters=[parameter],
        risks=["state_transition"],
    )
    point = TestPoint(
        test_point_id="TP_CANCEL_001",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.ORDER_CANCEL,
        level_1=CoverageCategory.STATE_FLOW,
        level_2="合法状态迁移",
        description="验证 waiting 到 cancelled 的状态迁移",
        risk_level="high",
        executable=True,
    )
    case = TestCaseSpec(
        case_id="TC_CANCEL_001",
        title="取消 waiting 订单",
        precondition="订单状态为 waiting",
        steps=["调用取消订单接口", "查询订单详情"],
        expected_result="订单状态为 cancelled",
        generation_source="llm",
        business_type=BusinessType.ORDER_CANCEL,
        requirement_ids=[rule.rule_id],
        test_point_ids=[point.test_point_id],
        level_1=point.level_1,
        level_2=point.level_2,
        assertions=[
            AssertionSpec(
                target="order.order_status",
                operator="equals",
                expected="cancelled",
            )
        ],
        executable=True,
    )

    assert case.requirement_ids == ["REQ_CANCEL_001"]
    assert case.assertions[0].expected == "cancelled"


def test_non_executable_item_requires_reason():
    with pytest.raises(ValidationError, match="unsupported_reason"):
        TestPoint(
            test_point_id="TP_SECURITY_001",
            requirement_ids=["REQ_CANCEL_001"],
            business_type=BusinessType.ORDER_CANCEL,
            level_1=CoverageCategory.SECURITY_PERMISSION,
            level_2="越权访问",
            description="其他用户取消订单",
            executable=False,
        )


def test_covered_evidence_requires_case_ids():
    with pytest.raises(ValidationError, match="case_ids"):
        CoverageEvidence(
            target_id="REQ_CANCEL_001",
            covered=True,
            method="structured_match",
            confidence=0.9,
        )


def test_coverage_matrix_keeps_three_rates_separate():
    matrix = CoverageMatrix(
        requirement_coverage=CoverageSummary(
            total=2,
            covered=2,
            coverage_rate=100,
        ),
        parameter_coverage=CoverageSummary(
            total=4,
            covered=3,
            coverage_rate=75,
            missing_ids=["PARAM_cancel_reason_empty"],
        ),
        risk_coverage=CoverageSummary(
            total=3,
            covered=2,
            coverage_rate=66.67,
            missing_ids=["RISK_idempotency"],
        ),
    )

    assert matrix.requirement_coverage.coverage_rate == 100
    assert matrix.parameter_coverage.coverage_rate == 75
    assert matrix.risk_coverage.coverage_rate == 66.67


def test_coverage_summary_rejects_inconsistent_rate():
    with pytest.raises(ValidationError, match="coverage_rate"):
        CoverageSummary(total=4, covered=3, coverage_rate=80)
