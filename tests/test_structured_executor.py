from app.harness.structured_executor import (
    execute_structured_case,
    resolve_value,
)
from app.models.test_design import BusinessType, TestCaseSpec


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, operation_name, arguments):
        self.calls.append((operation_name, arguments))
        if operation_name == "reset_mock_data":
            return {"code": 0}
        if operation_name == "create_order":
            return {
                "code": 0,
                "order_id": "order_001",
                "order_status": "waiting",
            }
        if operation_name == "pay_order":
            return {
                "code": 0,
                "payment_status": "paid",
                "order_status": "paid",
            }
        if operation_name == "get_order":
            return {
                "code": 0,
                "order": {
                    "order_id": arguments["order_id"],
                    "payment_status": "paid",
                    "order_status": "paid",
                },
            }
        raise AssertionError(f"unexpected operation: {operation_name}")


def make_case() -> TestCaseSpec:
    return TestCaseSpec.model_validate({
        "case_id": "TC_PAY_STRUCTURED_001",
        "title": "正常支付",
        "precondition": "创建未支付订单",
        "steps": ["重置", "创建", "支付", "查询"],
        "expected_result": "支付状态为 paid",
        "generation_source": "rule",
        "business_type": BusinessType.PAYMENT,
        "requirement_ids": ["REQ_PAY_001"],
        "test_point_ids": ["TP_PAY_001"],
        "setup_actions": [
            {"call_id": "reset", "operation_name": "reset_mock_data"},
            {
                "call_id": "create",
                "operation_name": "create_order",
                "arguments": {"start_location": "A", "end_location": "B"},
                "save_as": "created_order",
            },
        ],
        "test_actions": [
            {
                "call_id": "pay",
                "operation_name": "pay_order",
                "arguments": {
                    "order_id": "${created_order.order_id}",
                    "amount": 30,
                },
                "save_as": "pay_result",
            }
        ],
        "verification_actions": [
            {
                "call_id": "query",
                "operation_name": "get_order",
                "arguments": {"order_id": "${created_order.order_id}"},
                "save_as": "order_detail",
            }
        ],
        "assertions": [
            {
                "target": "order_detail.order.payment_status",
                "operator": "equals",
                "expected": "paid",
            }
        ],
        "executable": True,
    })


def test_structured_case_executes_actions_resolves_variables_and_passes():
    runner = FakeRunner()

    result = execute_structured_case(make_case(), runner=runner)

    assert result["status"] == "passed"
    assert result["error_log"] == ""
    assert len(result["action_results"]) == 4
    assert result["assertion_results"][0]["passed"] is True
    assert runner.calls[2] == (
        "pay_order",
        {"order_id": "order_001", "amount": 30},
    )


def test_unknown_variable_fails_before_target_operation_runs():
    runner = FakeRunner()
    case = make_case()
    case.test_actions[0].arguments["order_id"] = "${missing.order_id}"

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "failed"
    assert "变量引用不存在" in result["error_log"]
    assert [name for name, _ in runner.calls] == [
        "reset_mock_data",
        "create_order",
    ]


def test_partial_string_placeholder_is_rejected():
    try:
        resolve_value("order-${created.order_id}", {"created": {"order_id": "1"}})
        raise AssertionError("expected execution error")
    except ValueError as exc:
        assert "必须占据完整字符串" in str(exc)


def test_failed_assertion_returns_failed_with_evidence():
    runner = FakeRunner()
    case = make_case()
    case.assertions[0].expected = "unpaid"

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "failed"
    assert result["error_log"] == "结构化断言失败"
    assert result["assertion_results"][0]["actual"] == "paid"
    assert result["assertion_results"][0]["passed"] is False


def test_unregistered_operation_is_blocked_before_runner_call():
    runner = FakeRunner()
    case = make_case()
    case.test_actions[0].operation_name = "run_shell"

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "failed"
    assert "未注册操作" in result["error_log"]
    assert runner.calls == []


def test_first_setup_action_must_reset_mock_data():
    runner = FakeRunner()
    case = make_case()
    case.setup_actions = case.setup_actions[1:]

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "failed"
    assert "第一个 setup 操作必须是 reset_mock_data" in result["error_log"]
    assert runner.calls == []


def test_request_budget_is_checked_before_execution():
    runner = FakeRunner()
    case = make_case()
    case.test_actions = [
        case.test_actions[0].model_copy(update={"call_id": f"pay_{index}"})
        for index in range(12)
    ]

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "failed"
    assert "请求数不能超过" in result["error_log"]
    assert runner.calls == []


def test_duplicate_save_alias_is_rejected():
    runner = FakeRunner()
    case = make_case()
    case.verification_actions[0].save_as = "created_order"

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "failed"
    assert "save_as 不能重复" in result["error_log"]
    assert runner.calls == []


def test_non_executable_case_preserves_reason():
    runner = FakeRunner()
    case = make_case()
    case.executable = False
    case.unsupported_reason = "需要第三方支付环境"

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "failed"
    assert "需要第三方支付环境" in result["error_log"]
    assert runner.calls == []


def test_exists_and_not_exists_assertions_are_safe():
    runner = FakeRunner()
    case = make_case()
    case.assertions = [
        case.assertions[0].model_copy(
            update={"target": "order_detail.order.order_id", "operator": "exists"}
        ),
        case.assertions[0].model_copy(
            update={"target": "order_detail.order.secret", "operator": "not_exists"}
        ),
    ]

    result = execute_structured_case(case, runner=runner)

    assert result["status"] == "passed"
    assert all(item["passed"] for item in result["assertion_results"])
