import json

from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    ParameterSpec,
    RequirementRule,
    TestPoint,
)
from app.tools.coverage_matcher import build_keyword_coverage_matrix
from app.tools.semantic_coverage_matcher import (
    build_semantic_coverage_matrix,
    build_semantic_coverage_prompt,
)


def make_rule() -> RequirementRule:
    return RequirementRule(
        rule_id="REQ_PAY_001",
        text="支付金额必须大于 0",
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
        risks=["amount_boundary"],
    )


def make_ambiguous_point() -> TestPoint:
    return TestPoint(
        test_point_id="TP_PAY_SEMANTIC_001",
        requirement_ids=["REQ_PAY_001"],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.INPUT_PARAMETER,
        level_2="特殊数值验证",
        description="使用刚好可支付的最低数值完成交易",
        executable=True,
    )


def decision(target_id: str, confidence: float = 0.9) -> str:
    return json.dumps(
        [
            {
                "target_id": target_id,
                "covered": True,
                "test_point_ids": ["TP_PAY_SEMANTIC_001"],
                "confidence": confidence,
                "reason": "最低可支付数值在语义上对应 amount 边界检查",
            }
        ],
        ensure_ascii=False,
    )


def test_high_confidence_valid_decision_updates_only_requested_target():
    target_id = "REQ_PAY_001:parameter:amount:boundary"

    result = build_semantic_coverage_matrix(
        [make_rule()],
        [make_ambiguous_point()],
        call_fn=lambda _: decision(target_id),
    )
    evidence = next(
        item for item in result["matrix"].evidence
        if item.target_id == target_id
    )

    assert result["source"] == "llm"
    assert result["accepted_target_ids"] == [target_id]
    assert evidence.covered is True
    assert evidence.method == "model_judgment"
    assert evidence.confidence == 0.9
    assert target_id not in result["matrix"].parameter_coverage.missing_ids


def test_low_confidence_decision_keeps_gap():
    target_id = "REQ_PAY_001:parameter:amount:boundary"

    result = build_semantic_coverage_matrix(
        [make_rule()],
        [make_ambiguous_point()],
        call_fn=lambda _: decision(target_id, confidence=0.7),
        confidence_threshold=0.8,
    )

    assert result["source"] == "llm"
    assert result["accepted_target_ids"] == []
    assert target_id in result["matrix"].parameter_coverage.missing_ids


def test_model_cannot_invent_target_id():
    result = build_semantic_coverage_matrix(
        [make_rule()],
        [make_ambiguous_point()],
        call_fn=lambda _: decision("REQ_PAY_001:risk:invented"),
    )

    assert result["source"] == "fallback"
    assert result["accepted_target_ids"] == []
    assert "未请求的 target_id" in result["fallback_reason"]


def test_model_cannot_reference_unknown_test_point():
    payload = json.loads(decision("REQ_PAY_001:parameter:amount:boundary"))
    payload[0]["test_point_ids"] = ["TP_NOT_EXISTS"]

    result = build_semantic_coverage_matrix(
        [make_rule()],
        [make_ambiguous_point()],
        call_fn=lambda _: json.dumps(payload, ensure_ascii=False),
    )

    assert result["source"] == "fallback"
    assert "不存在的 test_point_id" in result["fallback_reason"]


def test_api_or_format_failure_preserves_keyword_matrix():
    rules = [make_rule()]
    points = [make_ambiguous_point()]
    before, _ = build_keyword_coverage_matrix(rules, points)

    result = build_semantic_coverage_matrix(
        rules,
        points,
        call_fn=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert result["source"] == "fallback"
    assert result["matrix"].model_dump() == before.model_dump()
    assert "offline" in result["fallback_reason"]


def test_prompt_contains_only_unresolved_targets():
    rules = [make_rule()]
    points = [make_ambiguous_point()]
    matrix, _ = build_keyword_coverage_matrix(rules, points)

    prompt = build_semantic_coverage_prompt(rules, points, matrix)

    assert "unresolved_gaps" in prompt
    assert "REQ_PAY_001:parameter:amount:boundary" in prompt
    assert "不能虚构" not in prompt


def test_no_model_call_when_structured_coverage_is_complete():
    point = make_ambiguous_point().model_copy(
        update={
            "parameter_names": ["amount"],
            "parameter_checks": ["normal", "empty", "invalid", "boundary"],
            "risk_tags": ["amount_boundary"],
        }
    )
    called = False

    def should_not_call(_: str) -> str:
        nonlocal called
        called = True
        return "[]"

    result = build_semantic_coverage_matrix(
        [make_rule()],
        [point],
        call_fn=should_not_call,
    )

    assert result["source"] == "not_needed"
    assert called is False


def test_invalid_confidence_threshold_is_rejected():
    try:
        build_semantic_coverage_matrix(
            [make_rule()],
            [make_ambiguous_point()],
            confidence_threshold=1.1,
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "0 到 1" in str(exc)
