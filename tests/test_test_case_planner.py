import json

from app.harness.test_case_planner import (
    build_case_plan_prompt,
    plan_test_cases,
    validate_case_plans,
)
from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    RequirementRule,
    TestPoint,
)


def make_rule() -> RequirementRule:
    return RequirementRule(
        rule_id="REQ_PAY_001",
        text="重复支付不能重复扣款",
        business_type=BusinessType.PAYMENT,
        action="pay_order",
        expected_outcomes=["message=REPEAT_PAYMENT"],
        risks=["idempotency", "duplicate_charge"],
    )


def make_point() -> TestPoint:
    return TestPoint(
        test_point_id="TP_PAY_001",
        requirement_ids=["REQ_PAY_001"],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.RELIABILITY,
        level_2="支付幂等性",
        description="重复支付不会重复扣款",
        risk_level="high",
        risk_tags=["idempotency", "duplicate_charge"],
        executable=True,
    )


def valid_case() -> dict:
    return {
        "case_id": "TC_PAY_001",
        "title": "重复支付",
        "precondition": "订单未支付",
        "steps": ["reset_mock_data", "create_order", "pay_order", "pay_order"],
        "expected_result": "第二次支付返回 REPEAT_PAYMENT",
        "business_type": "payment",
        "requirement_ids": ["REQ_PAY_001"],
        "test_point_ids": ["TP_PAY_001"],
        "setup_actions": [
            {"call_id": "reset", "operation_name": "reset_mock_data"},
            {
                "call_id": "create",
                "operation_name": "create_order",
                "arguments": {"start_location": "A", "end_location": "B"},
                "save_as": "order"
            }
        ],
        "test_actions": [
            {
                "call_id": "pay1",
                "operation_name": "pay_order",
                "arguments": {"order_id": "${order.order_id}", "amount": 30},
                "save_as": "first"
            },
            {
                "call_id": "pay2",
                "operation_name": "pay_order",
                "arguments": {"order_id": "${order.order_id}", "amount": 30},
                "save_as": "second"
            }
        ],
        "assertions": [
            {"target": "second.message", "operator": "equals", "expected": "REPEAT_PAYMENT"}
        ],
        "executable": True
    }


def test_prompt_contains_registry_and_forbids_raw_urls():
    prompt = build_case_plan_prompt([make_rule()], [make_point()])

    assert "capability_registry" in prompt
    assert "pay_order" in prompt
    assert "不允许生成 URL" in prompt
    assert "max_requests_per_case" in prompt


def test_valid_model_plan_is_accepted_and_marked_llm():
    result = plan_test_cases(
        [make_rule()],
        [make_point()],
        call_fn=lambda _: json.dumps([valid_case()], ensure_ascii=False),
    )

    assert result["source"] == "llm"
    assert result["test_cases"][0].generation_source == "llm"
    assert len(result["test_cases"][0].test_actions) == 2


def test_unknown_operation_triggers_rule_fallback():
    case = valid_case()
    case["test_actions"][0]["operation_name"] = "run_shell"

    result = plan_test_cases(
        [make_rule()],
        [make_point()],
        call_fn=lambda _: json.dumps([case], ensure_ascii=False),
    )

    assert result["source"] == "rule"
    assert "未注册操作" in result["fallback_reason"]
    assert all(
        action.operation_name != "run_shell"
        for action in result["test_cases"][0].test_actions
    )


def test_non_setup_operation_cannot_be_used_as_setup():
    case = valid_case()
    case["setup_actions"].append(
        {"call_id": "bad_setup", "operation_name": "pay_order"}
    )

    result = plan_test_cases(
        [make_rule()],
        [make_point()],
        call_fn=lambda _: json.dumps([case], ensure_ascii=False),
    )

    assert result["source"] == "rule"
    assert "不允许用于 setup_actions" in result["fallback_reason"]


def test_request_budget_is_enforced():
    case = valid_case()
    case["test_actions"] = [
        {
            "call_id": f"pay_{index}",
            "operation_name": "pay_order",
            "arguments": {"order_id": "x", "amount": 1},
        }
        for index in range(13)
    ]

    result = plan_test_cases(
        [make_rule()],
        [make_point()],
        call_fn=lambda _: json.dumps([case], ensure_ascii=False),
    )

    assert result["source"] == "rule"
    assert "超过单用例请求预算" in result["fallback_reason"]


def test_missing_test_point_reference_is_rejected():
    case = valid_case()
    case["test_point_ids"] = []

    try:
        validate_case_plans([case], [make_rule()], [make_point()])
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "必须引用测试点" in str(exc)


def test_unsupported_security_point_is_reported_without_model_call():
    point = make_point().model_copy(
        update={
            "level_1": CoverageCategory.SECURITY_PERMISSION,
            "level_2": "支付越权",
            "description": "其他用户支付订单",
            "risk_tags": [],
        }
    )
    called = False

    def should_not_call(_: str) -> str:
        nonlocal called
        called = True
        return "[]"

    result = plan_test_cases([make_rule()], [point], call_fn=should_not_call)

    assert result["source"] == "not_needed"
    assert result["test_cases"] == []
    assert result["unsupported_test_points"][0]["test_point_id"] == point.test_point_id
    assert called is False


def test_rule_fallback_plan_uses_registered_operations_and_assertions():
    result = plan_test_cases(
        [make_rule()],
        [make_point()],
        call_fn=lambda _: "invalid-json",
    )
    case = result["test_cases"][0]

    assert result["source"] == "rule"
    assert case.test_actions
    assert case.assertions
    assert {action.operation_name for action in case.setup_actions} == {
        "reset_mock_data",
        "create_order",
    }
    assert len(case.setup_actions + case.test_actions + case.verification_actions) <= 12
