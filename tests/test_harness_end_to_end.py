from fastapi.testclient import TestClient

from app.api_server import app
from app.harness.structured_executor import execute_structured_case
from app.harness.test_case_planner import plan_test_cases
from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    RequirementRule,
    TestPoint,
)


client = TestClient(app)


def mock_api_runner(operation_name, arguments):
    if operation_name == "reset_mock_data":
        return client.post("/mock/reset").json()
    if operation_name == "create_order":
        return client.post(
            "/mock/order/create",
            json={
                "user_id": "user_001",
                "start_location": arguments.get("start_location", "A"),
                "end_location": arguments.get("end_location", "B"),
                "assign_driver": arguments.get("assign_driver", False),
            },
        ).json()
    if operation_name == "cancel_order":
        return client.post(
            "/mock/order/cancel",
            json={
                "user_id": "user_001",
                "order_id": arguments["order_id"],
                "cancel_reason": arguments.get("cancel_reason"),
            },
        ).json()
    if operation_name == "timeout_cancel_order":
        return client.post(
            "/mock/order/timeout_cancel",
            json={"order_id": arguments["order_id"]},
        ).json()
    if operation_name == "get_order":
        return client.get(f"/mock/order/{arguments['order_id']}").json()
    if operation_name == "list_user_orders":
        return client.get(
            f"/mock/orders/user/{arguments.get('user_id', 'user_001')}"
        ).json()
    if operation_name == "get_driver":
        return client.get(
            f"/mock/driver/{arguments.get('driver_id', 'driver_001')}"
        ).json()
    if operation_name == "pay_order":
        return client.post(
            "/mock/payment/pay",
            json={
                "user_id": "user_001",
                "order_id": arguments["order_id"],
                "amount": arguments.get("amount", 30),
            },
        ).json()
    raise AssertionError(f"unexpected operation: {operation_name}")


def rule_plan(rule, point):
    result = plan_test_cases(
        [rule],
        [point],
        call_fn=lambda _: (_ for _ in ()).throw(RuntimeError("force rule plan")),
    )
    assert result["source"] == "rule"
    assert len(result["test_cases"]) == 1
    return result["test_cases"][0]


def test_cancel_resource_release_plan_executes_real_mock_flow():
    rule = RequirementRule(
        rule_id="REQ_CANCEL_RELEASE",
        text="accepted 订单取消后释放司机",
        business_type=BusinessType.ORDER_CANCEL,
        action="cancel_order",
        expected_outcomes=["order_status=cancelled", "driver_status=available"],
        risks=["resource_release", "state_transition"],
    )
    point = TestPoint(
        test_point_id="TP_CANCEL_RELEASE",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.ORDER_CANCEL,
        level_1=CoverageCategory.RESOURCE_DEPENDENCY,
        level_2="司机资源释放",
        description="取消 accepted 订单后司机恢复 available",
        risk_tags=["resource_release"],
        executable=True,
    )

    result = execute_structured_case(rule_plan(rule, point), runner=mock_api_runner)

    assert result["status"] == "passed"
    assert len(result["assertion_results"]) == 2
    assert all(item["passed"] for item in result["assertion_results"])


def test_cancel_required_reason_plan_asserts_rejection_and_unchanged_state():
    rule = RequirementRule(
        rule_id="REQ_CANCEL_REASON",
        text="accepted 订单取消时必须填写原因",
        business_type=BusinessType.ORDER_CANCEL,
        action="cancel_order",
        expected_outcomes=["message=CANCEL_REASON_REQUIRED", "order_status=accepted"],
        risks=["required_parameter", "state_transition"],
    )
    point = TestPoint(
        test_point_id="TP_CANCEL_REASON_EMPTY",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.ORDER_CANCEL,
        level_1=CoverageCategory.INPUT_PARAMETER,
        level_2="取消原因为空",
        description="accepted 订单不填写取消原因时拒绝取消",
        parameter_names=["cancel_reason"],
        parameter_checks=["empty"],
        risk_tags=["required_parameter"],
        executable=True,
    )

    case = rule_plan(rule, point)
    result = execute_structured_case(case, runner=mock_api_runner)

    assert result["status"] == "passed"
    assert any(
        assertion.target == "cancel_result.message"
        and assertion.expected == "CANCEL_REASON_REQUIRED"
        for assertion in case.assertions
    )
    assert any(
        assertion.target == "order_detail.order.order_status"
        and assertion.expected == "accepted"
        for assertion in case.assertions
    )


def test_repeat_payment_plan_asserts_repeat_payment_response():
    rule = RequirementRule(
        rule_id="REQ_PAY_REPEAT",
        text="重复支付返回 REPEAT_PAYMENT",
        business_type=BusinessType.PAYMENT,
        action="pay_order",
        expected_outcomes=["message=REPEAT_PAYMENT"],
        risks=["idempotency", "duplicate_charge"],
    )
    point = TestPoint(
        test_point_id="TP_PAY_REPEAT",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.RELIABILITY,
        level_2="支付幂等性",
        description="第二次支付返回 REPEAT_PAYMENT",
        risk_tags=["idempotency", "duplicate_charge"],
        executable=True,
    )

    case = rule_plan(rule, point)
    result = execute_structured_case(case, runner=mock_api_runner)

    assert result["status"] == "passed"
    assert any(
        assertion.target == "repeat_result.message"
        and assertion.expected == "REPEAT_PAYMENT"
        for assertion in case.assertions
    )


def test_order_create_empty_parameter_plan_asserts_param_error():
    rule = RequirementRule(
        rule_id="REQ_ORDER_START",
        text="起点不能为空",
        business_type=BusinessType.ORDER_CREATE,
        action="create_order",
        expected_outcomes=["message=PARAM_ERROR"],
        risks=["required_parameter"],
    )
    point = TestPoint(
        test_point_id="TP_ORDER_START_EMPTY",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.ORDER_CREATE,
        level_1=CoverageCategory.INPUT_PARAMETER,
        level_2="起点为空",
        description="start_location 为空时返回 PARAM_ERROR",
        parameter_names=["start_location"],
        parameter_checks=["empty"],
        risk_tags=["required_parameter"],
        executable=True,
    )

    case = rule_plan(rule, point)
    result = execute_structured_case(case, runner=mock_api_runner)

    assert result["status"] == "passed"
    assert case.assertions[0].target == "created_order.message"
    assert case.assertions[0].expected == "PARAM_ERROR"


def test_order_resource_allocation_plan_asserts_driver_assigned():
    rule = RequirementRule(
        rule_id="REQ_ORDER_DRIVER",
        text="分配司机后订单 accepted，司机 assigned",
        business_type=BusinessType.ORDER_CREATE,
        action="create_order_and_assign_driver",
        expected_outcomes=["order_status=accepted", "driver_status=assigned"],
        risks=["resource_allocation", "state_transition"],
    )
    point = TestPoint(
        test_point_id="TP_ORDER_DRIVER",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.ORDER_CREATE,
        level_1=CoverageCategory.RESOURCE_DEPENDENCY,
        level_2="司机资源分配",
        description="创建订单并分配司机后状态为 assigned",
        risk_tags=["resource_allocation"],
        executable=True,
    )

    case = rule_plan(rule, point)
    result = execute_structured_case(case, runner=mock_api_runner)

    assert result["status"] == "passed"
    assert any(
        assertion.target == "driver_detail.driver.driver_status"
        and assertion.expected == "assigned"
        for assertion in case.assertions
    )


def test_duplicate_order_plan_asserts_duplicate_order_response():
    rule = RequirementRule(
        rule_id="REQ_ORDER_REPEAT",
        text="存在未完成订单时返回 DUPLICATE_ORDER",
        business_type=BusinessType.ORDER_CREATE,
        action="create_order",
        expected_outcomes=["message=DUPLICATE_ORDER"],
        risks=["idempotency", "duplicate_data"],
    )
    point = TestPoint(
        test_point_id="TP_ORDER_REPEAT",
        requirement_ids=[rule.rule_id],
        business_type=BusinessType.ORDER_CREATE,
        level_1=CoverageCategory.RELIABILITY,
        level_2="重复下单",
        description="第二次创建订单返回 DUPLICATE_ORDER",
        risk_tags=["idempotency", "duplicate_data"],
        executable=True,
    )

    case = rule_plan(rule, point)
    result = execute_structured_case(case, runner=mock_api_runner)

    assert result["status"] == "passed"
    assert any(
        assertion.target == "repeat_result.message"
        and assertion.expected == "DUPLICATE_ORDER"
        for assertion in case.assertions
    )
