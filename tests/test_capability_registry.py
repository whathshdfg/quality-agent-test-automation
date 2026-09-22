from app.harness.capability_registry import (
    CAPABILITY_REGISTRY,
    HARNESS_POLICY,
    evaluate_test_point_support,
    get_operation,
    validate_request,
)
from app.models.test_design import BusinessType, CoverageCategory, TestPoint


def make_point(**updates) -> TestPoint:
    data = {
        "test_point_id": "TP_PAY_001",
        "requirement_ids": ["REQ_PAY_001"],
        "business_type": BusinessType.PAYMENT,
        "level_1": CoverageCategory.RELIABILITY,
        "level_2": "支付幂等性",
        "description": "重复支付不会重复扣款",
        "risk_level": "high",
        "risk_tags": ["idempotency", "duplicate_charge"],
        "executable": True,
    }
    data.update(updates)
    return TestPoint.model_validate(data)


def test_registry_contains_only_real_mock_api_operations():
    assert set(CAPABILITY_REGISTRY) == {
        "reset_mock_data",
        "create_order",
        "cancel_order",
        "timeout_cancel_order",
        "get_order",
        "list_user_orders",
        "get_driver",
        "pay_order",
    }
    assert get_operation("pay_order").path_template == "/mock/payment/pay"
    assert get_operation("unknown_action") is None


def test_registered_dynamic_path_and_method_are_allowed():
    result = validate_request("GET", "/mock/order/order_123")

    assert result.allowed is True
    assert result.operation_name == "get_order"
    assert result.reasons == ()


def test_absolute_and_non_mock_urls_are_rejected():
    external = validate_request("GET", "https://example.com/mock/order/1")
    agent_path = validate_request("POST", "/agent/run")

    assert external.allowed is False
    assert "不允许使用绝对 URL" in external.reasons
    assert agent_path.allowed is False
    assert "请求路径不在允许的 Mock API 范围内" in agent_path.reasons


def test_wrong_method_for_registered_path_is_rejected():
    result = validate_request("DELETE", "/mock/order/create")

    assert result.allowed is False
    assert any("HTTP 方法" in reason for reason in result.reasons)
    assert any("未找到匹配" in reason for reason in result.reasons)


def test_per_case_request_budget_is_enforced():
    result = validate_request(
        "POST",
        "/mock/reset",
        request_count=HARNESS_POLICY.max_requests_per_case,
    )

    assert result.allowed is False
    assert any("请求数" in reason for reason in result.reasons)


def test_supported_payment_risk_point_gets_allowlisted_operations():
    decision = evaluate_test_point_support(make_point())

    assert decision.supported is True
    assert "pay_order" in decision.operation_names
    assert "create_order" in decision.operation_names


def test_security_point_is_explicitly_unsupported():
    point = make_point(
        level_1=CoverageCategory.SECURITY_PERMISSION,
        level_2="支付越权",
        description="其他用户支付订单",
        risk_tags=[],
    )

    decision = evaluate_test_point_support(point)

    assert decision.supported is False
    assert any("身份认证" in reason for reason in decision.reasons)


def test_unknown_business_and_unregistered_risk_are_rejected():
    point = make_point(
        business_type=BusinessType.UNKNOWN,
        risk_tags=["network_fault"],
    )

    decision = evaluate_test_point_support(point)

    assert decision.supported is False
    assert any("未知业务" in reason for reason in decision.reasons)
    assert any("网络故障" in reason for reason in decision.reasons)


def test_reliability_point_without_risk_tag_is_not_guessed():
    decision = evaluate_test_point_support(make_point(risk_tags=[]))

    assert decision.supported is False
    assert any("缺少明确 risk_tags" in reason for reason in decision.reasons)


def test_explicit_non_executable_reason_is_preserved():
    point = make_point(
        executable=False,
        unsupported_reason="需要第三方支付沙箱",
    )

    decision = evaluate_test_point_support(point)

    assert decision.supported is False
    assert "需要第三方支付沙箱" in decision.reasons
