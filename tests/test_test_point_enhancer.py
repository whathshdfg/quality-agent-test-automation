import json

from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    ParameterSpec,
    RequirementRule,
    TestPoint,
)
from app.tools.coverage_matrix_tool import build_coverage_matrix
from app.tools.test_point_enhancer import enhance_test_points


def make_rule() -> RequirementRule:
    return RequirementRule(
        rule_id="REQ_PAY_001",
        text="支付金额必须大于 0，重复支付不能重复扣款",
        business_type=BusinessType.PAYMENT,
        action="pay_order",
        expected_outcomes=["payment_status=paid"],
        parameters=[
            ParameterSpec(
                name="amount",
                data_type="number",
                required=True,
                invalid_values=[0],
                boundary_values=[0, 0.01],
            )
        ],
        risks=["idempotency"],
    )


def make_partial_point() -> TestPoint:
    return TestPoint(
        test_point_id="TP_PAY_EXISTING_001",
        requirement_ids=["REQ_PAY_001"],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.INPUT_PARAMETER,
        level_2="amount 正常值",
        description="验证 amount 正常值",
        parameter_names=["amount"],
        parameter_checks=["normal"],
        executable=True,
    )


def test_rule_fallback_adds_points_for_exact_remaining_gaps():
    rule = make_rule()
    existing = [make_partial_point()]
    matrix = build_coverage_matrix([rule], existing)

    result = enhance_test_points(
        [rule],
        existing,
        matrix,
        call_fn=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert result["source"] == "rule"
    assert result["added_test_points"]
    assert result["addressed_gap_ids"]
    assert result["matrix"].parameter_coverage.coverage_rate == 100
    assert result["matrix"].risk_coverage.coverage_rate == 100
    assert result["stop_reason"] == ""


def test_llm_supplement_is_accepted_when_it_fills_requested_gap():
    rule = make_rule()
    existing = [make_partial_point()]
    matrix = build_coverage_matrix([rule], existing)
    point = {
        "test_point_id": "TP_PAY_LLM_001",
        "requirement_ids": ["REQ_PAY_001"],
        "business_type": "payment",
        "level_1": "reliability",
        "level_2": "支付幂等性",
        "description": "验证重复支付不会重复扣款",
        "risk_level": "high",
        "risk_tags": ["idempotency"],
        "executable": True,
    }

    result = enhance_test_points(
        [rule],
        existing,
        matrix,
        call_fn=lambda _: json.dumps([point], ensure_ascii=False),
    )

    assert result["source"] == "llm"
    assert result["added_test_points"][0].test_point_id == "TP_PAY_LLM_001"
    assert any("idempotency" in gap_id for gap_id in result["addressed_gap_ids"])


def test_irrelevant_llm_point_triggers_rule_fallback():
    rule = make_rule()
    existing = [make_partial_point()]
    matrix = build_coverage_matrix([rule], existing)
    irrelevant = {
        "test_point_id": "TP_PAY_LLM_IRRELEVANT",
        "requirement_ids": ["REQ_PAY_001"],
        "business_type": "payment",
        "level_1": "functional_behavior",
        "level_2": "页面颜色",
        "description": "检查按钮颜色",
        "executable": True,
    }

    result = enhance_test_points(
        [rule],
        existing,
        matrix,
        call_fn=lambda _: json.dumps([irrelevant], ensure_ascii=False),
    )

    assert result["source"] == "rule"
    assert "没有填补任何具体缺口" in result["fallback_reason"]
    assert all(
        point.test_point_id != "TP_PAY_LLM_IRRELEVANT"
        for point in result["test_points"]
    )


def test_existing_points_are_preserved_and_ids_are_unique():
    rule = make_rule()
    existing = [make_partial_point()]
    matrix = build_coverage_matrix([rule], existing)

    result = enhance_test_points(
        [rule],
        existing,
        matrix,
        call_fn=lambda _: "invalid-json",
    )
    ids = [point.test_point_id for point in result["test_points"]]

    assert result["test_points"][0] == existing[0]
    assert len(ids) == len(set(ids))


def test_no_actionable_gap_skips_model_call():
    rule = make_rule()
    complete = [
        TestPoint(
            test_point_id="TP_PAY_COMPLETE",
            requirement_ids=[rule.rule_id],
            business_type=BusinessType.PAYMENT,
            level_1=CoverageCategory.INPUT_PARAMETER,
            level_2="完整检查",
            description="完整参数和风险检查",
            parameter_names=["amount"],
            parameter_checks=["normal", "empty", "invalid", "boundary"],
            risk_tags=["idempotency"],
            executable=True,
        )
    ]
    matrix = build_coverage_matrix([rule], complete)
    called = False

    def should_not_call(_: str) -> str:
        nonlocal called
        called = True
        return "[]"

    result = enhance_test_points([rule], complete, matrix, call_fn=should_not_call)

    assert result["source"] == "not_needed"
    assert called is False
    assert result["added_test_points"] == []


def test_executability_gap_is_not_hidden_by_new_test_point():
    rule = RequirementRule(
        rule_id="REQ_PAY_SECURITY",
        text="只有订单所属用户可以支付",
        business_type=BusinessType.PAYMENT,
        action="authorize_payment",
        expected_outcomes=["拒绝越权支付"],
    )
    point = TestPoint(
        test_point_id="TP_PAY_SECURITY",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.SECURITY_PERMISSION,
        level_2="支付越权",
        description="其他用户尝试支付订单",
        executable=False,
        unsupported_reason="Mock API 没有身份鉴权",
    )
    matrix = build_coverage_matrix([rule], [point])

    result = enhance_test_points([rule], [point], matrix, call_fn=lambda _: "[]")

    assert result["source"] == "not_needed"
    assert result["added_test_points"] == []
    assert any(gap.gap_type.value == "executability" for gap in result["matrix"].gaps)


def test_previous_semantic_coverage_is_preserved_after_supplement():
    rule = make_rule()
    existing = [make_partial_point()]
    matrix = build_coverage_matrix([rule], existing)
    boundary_target = "REQ_PAY_001:parameter:amount:boundary"
    evidence = next(item for item in matrix.evidence if item.target_id == boundary_target)
    evidence.covered = True
    evidence.method = "model_judgment"
    evidence.confidence = 0.9
    evidence.test_point_ids = [existing[0].test_point_id]
    evidence.evidence = ["语义判断覆盖最低金额"]
    matrix.parameter_coverage = matrix.parameter_coverage.model_copy(
        update={
            "covered": matrix.parameter_coverage.covered + 1,
            "coverage_rate": 50,
            "missing_ids": [
                item for item in matrix.parameter_coverage.missing_ids
                if item != boundary_target
            ],
        }
    )
    matrix.gaps = [gap for gap in matrix.gaps if gap.target_id != boundary_target]

    result = enhance_test_points(
        [rule],
        existing,
        matrix,
        call_fn=lambda _: "invalid-json",
    )
    preserved = next(
        item for item in result["matrix"].evidence
        if item.target_id == boundary_target
    )

    assert preserved.covered is True
    assert preserved.method == "model_judgment"
    assert preserved.confidence == 0.9
