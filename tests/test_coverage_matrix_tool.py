from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    GapType,
    ParameterSpec,
    RequirementRule,
    TestPoint,
)
from app.tools.coverage_matrix_tool import (
    build_coverage_matrix,
    serialize_coverage_matrix,
)
from app.tools.test_point_generator import generate_rule_based_test_points


def make_rule() -> RequirementRule:
    return RequirementRule(
        rule_id="REQ_PAY_001",
        text="有效金额支付成功后状态变为 paid",
        business_type=BusinessType.PAYMENT,
        action="pay_order",
        expected_outcomes=["payment_status=paid"],
        parameters=[
            ParameterSpec(
                name="amount",
                data_type="number",
                required=True,
                valid_values=[0.01],
                invalid_values=[0, -1],
                boundary_values=[0, 0.01],
                constraints=["amount>0"],
            )
        ],
        risks=["state_transition", "idempotency", "data_consistency"],
    )


def test_generated_structured_points_fully_cover_rule_parameters_and_risks():
    rule = make_rule()
    points = generate_rule_based_test_points([rule])

    matrix = build_coverage_matrix([rule], points)

    assert matrix.requirement_coverage.coverage_rate == 100
    assert matrix.parameter_coverage.coverage_rate == 100
    assert matrix.risk_coverage.coverage_rate == 100
    assert matrix.gaps == []


def test_parameter_matrix_reports_exact_missing_check():
    rule = make_rule()
    point = TestPoint(
        test_point_id="TP_PAY_INPUT_001",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.INPUT_PARAMETER,
        level_2="amount 正常值",
        description="只验证正常金额",
        parameter_names=["amount"],
        parameter_checks=["normal"],
        executable=True,
    )

    matrix = build_coverage_matrix([rule], [point])

    assert matrix.requirement_coverage.coverage_rate == 100
    assert matrix.parameter_coverage.coverage_rate == 20
    assert "REQ_PAY_001:parameter:amount:boundary" in matrix.parameter_coverage.missing_ids
    assert any(
        gap.gap_type == GapType.PARAMETER and "boundary" in gap.target_id
        for gap in matrix.gaps
    )


def test_risk_matrix_does_not_infer_coverage_from_description_text():
    rule = make_rule()
    point = TestPoint(
        test_point_id="TP_PAY_TEXT_ONLY",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.RELIABILITY,
        level_2="重复支付",
        description="文字中提到了幂等性，但没有结构化风险标签",
        executable=True,
    )

    matrix = build_coverage_matrix([rule], [point])

    assert matrix.risk_coverage.coverage_rate == 0
    assert "REQ_PAY_001:risk:idempotency" in matrix.risk_coverage.missing_ids


def test_requirement_without_test_point_becomes_high_priority_gap():
    rule = make_rule()

    matrix = build_coverage_matrix([rule], [])
    gap = next(item for item in matrix.gaps if item.gap_type == GapType.REQUIREMENT)

    assert matrix.requirement_coverage.coverage_rate == 0
    assert gap.target_id == rule.rule_id
    assert gap.priority == "high"


def test_non_executable_point_creates_separate_executability_gap():
    rule = make_rule()
    point = TestPoint(
        test_point_id="TP_PAY_UNSUPPORTED",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.SECURITY_PERMISSION,
        level_2="支付越权",
        description="验证其他用户不能支付订单",
        executable=False,
        unsupported_reason="Mock API 当前没有身份鉴权",
    )

    matrix = build_coverage_matrix([rule], [point])

    assert matrix.requirement_coverage.coverage_rate == 100
    assert any(
        gap.gap_type == GapType.EXECUTABILITY
        and gap.target_id == point.test_point_id
        for gap in matrix.gaps
    )


def test_matrix_serialization_uses_plain_json_values():
    rule = make_rule()
    matrix = build_coverage_matrix(
        [rule],
        generate_rule_based_test_points([rule]),
    )

    data = serialize_coverage_matrix(matrix)

    assert data["requirement_coverage"]["coverage_rate"] == 100
    assert isinstance(data["evidence"], list)
