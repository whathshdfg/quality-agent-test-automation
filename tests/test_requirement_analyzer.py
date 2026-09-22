import json

import pytest

from app.models.test_design import BusinessType
from app.tools.requirement_analyzer import (
    analyze_requirement,
    build_requirement_prompt,
    extract_json_array,
    generate_rule_based_requirement_rules,
    validate_requirement_rules,
)


VALID_RULE = {
    "rule_id": "REQ_CANCEL_001",
    "text": "用户取消 waiting 订单后状态变为 cancelled",
    "business_type": "order_cancel",
    "actor": "user",
    "trigger": "用户取消",
    "preconditions": ["order_status=waiting"],
    "action": "cancel_order",
    "expected_outcomes": ["order_status=cancelled"],
    "parameters": [],
    "risks": ["state_transition"],
}


def test_extract_and_validate_markdown_wrapped_rules():
    output = f"```json\n{json.dumps([VALID_RULE], ensure_ascii=False)}\n```"

    rules = validate_requirement_rules(extract_json_array(output))

    assert rules[0].rule_id == "REQ_CANCEL_001"
    assert rules[0].business_type == BusinessType.ORDER_CANCEL


def test_duplicate_rule_ids_are_rejected():
    with pytest.raises(ValueError, match="不能重复"):
        validate_requirement_rules([VALID_RULE, VALID_RULE])


def test_prompt_requests_rules_instead_of_test_cases():
    prompt = build_requirement_prompt("测试订单取消")

    assert "不要直接生成测试用例" in prompt
    assert "RequirementRule" in prompt
    assert "order_cancel" in prompt


def test_successful_model_result_records_llm_source():
    result = analyze_requirement(
        "用户取消 waiting 订单后状态变为 cancelled",
        call_fn=lambda _: json.dumps([VALID_RULE], ensure_ascii=False),
    )

    assert result["source"] == "llm"
    assert result["fallback_reason"] == ""
    assert result["rules"][0].action == "cancel_order"


def test_invalid_model_output_falls_back_and_records_reason():
    result = analyze_requirement(
        "订单支付失败后保持 unpaid，重复支付返回 REPEAT_PAYMENT",
        call_fn=lambda _: "not-json",
    )

    assert result["source"] == "rule"
    assert "ValueError" in result["fallback_reason"]
    assert all(rule.business_type == BusinessType.PAYMENT for rule in result["rules"])
    assert {rule.rule_id for rule in result["rules"]} == {
        "REQ_PAY_001",
        "REQ_PAY_002",
        "REQ_PAY_003",
    }


def test_cancel_classification_has_priority_over_order_keyword():
    rules = generate_rule_based_requirement_rules(
        "订单取消后释放司机资源，并记录取消原因"
    )

    assert all(rule.business_type == BusinessType.ORDER_CANCEL for rule in rules)
    assert "REQ_CANCEL_004" in {rule.rule_id for rule in rules}


def test_unknown_requirement_is_not_treated_as_order_creation():
    result = analyze_requirement(
        "查询天气预报",
        call_fn=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    assert result["source"] == "rule"
    assert len(result["rules"]) == 1
    assert result["rules"][0].business_type == BusinessType.UNKNOWN
    assert result["rules"][0].rule_id == "REQ_UNKNOWN_001"


def test_empty_requirement_is_rejected_before_model_call():
    with pytest.raises(ValueError, match="不能为空"):
        analyze_requirement("   ", call_fn=lambda _: "[]")


def test_fallback_classification_uses_raw_requirement_not_rag_context():
    result = analyze_requirement(
        "支付成功后状态为 paid\n\n知识库：订单取消后状态为 cancelled",
        call_fn=lambda _: (_ for _ in ()).throw(RuntimeError("offline")),
        fallback_requirement="支付成功后状态为 paid",
    )

    assert result["source"] == "rule"
    assert all(
        rule.business_type == BusinessType.PAYMENT
        for rule in result["rules"]
    )
