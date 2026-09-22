"""Safely execute structured test plans against allowlisted Mock API operations."""

import json
import re
from typing import Any, Callable

from app.harness.capability_registry import (
    CAPABILITY_REGISTRY,
    HARNESS_POLICY,
)
from app.models.test_design import AssertionSpec, OperationCallSpec, TestCaseSpec
from app.tools.api_test_tool import (
    cancel_order,
    create_order,
    get_driver,
    get_order,
    list_user_orders,
    pay_order,
    reset_mock_data,
    timeout_cancel_order,
)


OperationRunner = Callable[[str, dict[str, Any]], dict[str, Any]]
PLACEHOLDER_PATTERN = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)\}$")
MISSING = object()


class ExecutionPlanError(ValueError):
    pass


def run_registered_operation(
    operation_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Explicit dispatcher; never call functions by generated names."""

    if operation_name == "reset_mock_data":
        return reset_mock_data()
    if operation_name == "create_order":
        return create_order(
            assign_driver=bool(arguments.get("assign_driver", False)),
            start_location=arguments.get("start_location", "A"),
            end_location=arguments.get("end_location", "B"),
        )
    if operation_name == "cancel_order":
        return cancel_order(
            order_id=arguments["order_id"],
            reason=arguments.get("cancel_reason"),
        )
    if operation_name == "timeout_cancel_order":
        return timeout_cancel_order(order_id=arguments["order_id"])
    if operation_name == "get_order":
        return get_order(order_id=arguments["order_id"])
    if operation_name == "list_user_orders":
        return list_user_orders(user_id=arguments.get("user_id", "user_001"))
    if operation_name == "get_driver":
        return get_driver(driver_id=arguments.get("driver_id", "driver_001"))
    if operation_name == "pay_order":
        return pay_order(
            order_id=arguments["order_id"],
            amount=arguments.get("amount", 30.0),
        )
    raise ExecutionPlanError(f"未注册操作: {operation_name}")


def _read_path(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return MISSING
    return current


def resolve_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: resolve_value(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_value(item, context) for item in value]
    if not isinstance(value, str):
        return value

    match = PLACEHOLDER_PATTERN.fullmatch(value)
    if not match:
        if "${" in value:
            raise ExecutionPlanError(
                f"变量引用必须占据完整字符串且格式合法: {value}"
            )
        return value

    reference = match.group(1)
    alias, _, nested_path = reference.partition(".")
    if alias not in context:
        raise ExecutionPlanError(f"变量引用不存在: {alias}")
    resolved = context[alias]
    if nested_path:
        resolved = _read_path(resolved, nested_path)
        if resolved is MISSING:
            raise ExecutionPlanError(f"变量字段不存在: {reference}")
    return resolved


def _validate_plan(case: TestCaseSpec) -> None:
    if case.executable is False:
        raise ExecutionPlanError(
            case.unsupported_reason or "测试用例已标记为不可执行"
        )
    if not case.test_actions:
        raise ExecutionPlanError("结构化测试计划缺少 test_actions")
    if not case.assertions:
        raise ExecutionPlanError("结构化测试计划缺少 assertions")
    if HARNESS_POLICY.reset_before_each_case:
        if (
            not case.setup_actions
            or case.setup_actions[0].operation_name != "reset_mock_data"
        ):
            raise ExecutionPlanError("每条用例的第一个 setup 操作必须是 reset_mock_data")

    actions = [
        *case.setup_actions,
        *case.test_actions,
        *case.verification_actions,
    ]
    if len(actions) > HARNESS_POLICY.max_requests_per_case:
        raise ExecutionPlanError(
            f"单用例请求数不能超过 {HARNESS_POLICY.max_requests_per_case}"
        )

    call_ids = [action.call_id for action in actions]
    if len(call_ids) != len(set(call_ids)):
        raise ExecutionPlanError("单条用例内 call_id 不能重复")

    aliases = [action.save_as for action in actions if action.save_as]
    if len(aliases) != len(set(aliases)):
        raise ExecutionPlanError("单条用例内 save_as 不能重复")

    for action in actions:
        capability = CAPABILITY_REGISTRY.get(action.operation_name)
        if not capability:
            raise ExecutionPlanError(f"未注册操作: {action.operation_name}")
        if case.business_type not in capability.business_types:
            raise ExecutionPlanError(
                f"操作 {action.operation_name} 不支持业务 {case.business_type.value}"
            )
    for action in case.setup_actions:
        if not CAPABILITY_REGISTRY[action.operation_name].setup_allowed:
            raise ExecutionPlanError(
                f"操作 {action.operation_name} 不允许用于 setup_actions"
            )


def _execute_action(
    action: OperationCallSpec,
    context: dict[str, Any],
    runner: OperationRunner,
) -> dict[str, Any]:
    arguments = resolve_value(action.arguments, context)
    response = runner(action.operation_name, arguments)
    if not isinstance(response, dict):
        raise ExecutionPlanError(
            f"操作 {action.operation_name} 返回值必须是字典"
        )

    context[action.call_id] = response
    if action.save_as:
        context[action.save_as] = response
    return {
        "call_id": action.call_id,
        "operation_name": action.operation_name,
        "arguments": arguments,
        "save_as": action.save_as,
        "response": response,
    }


def _assertion_passed(assertion: AssertionSpec, actual: Any) -> bool:
    operator = assertion.operator
    expected = assertion.expected

    if operator == "exists":
        return actual is not MISSING
    if operator == "not_exists":
        return actual is MISSING
    if actual is MISSING:
        return False
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        try:
            return expected in actual
        except TypeError:
            return False
    if operator == "in":
        try:
            return actual in expected
        except TypeError:
            return False
    if operator == "greater_than":
        return actual > expected
    if operator == "greater_than_or_equal":
        return actual >= expected
    if operator == "less_than":
        return actual < expected
    if operator == "less_than_or_equal":
        return actual <= expected
    raise ExecutionPlanError(f"不支持的断言操作符: {operator}")


def evaluate_assertion(
    assertion: AssertionSpec,
    context: dict[str, Any],
) -> dict[str, Any]:
    actual = _read_path(context, assertion.target)
    try:
        passed = _assertion_passed(assertion, actual)
        error = ""
    except (TypeError, ValueError) as exc:
        passed = False
        error = f"断言比较失败: {type(exc).__name__}: {exc}"

    return {
        "target": assertion.target,
        "operator": assertion.operator,
        "expected": assertion.expected,
        "actual": None if actual is MISSING else actual,
        "target_exists": actual is not MISSING,
        "passed": passed,
        "description": assertion.description,
        "error": error,
    }


def execute_structured_case(
    case: TestCaseSpec,
    runner: OperationRunner = run_registered_operation,
) -> dict[str, Any]:
    context: dict[str, Any] = {}
    action_results: list[dict[str, Any]] = []
    assertion_results: list[dict[str, Any]] = []

    try:
        _validate_plan(case)
        for phase_name, actions in [
            ("setup", case.setup_actions),
            ("test", case.test_actions),
            ("verification", case.verification_actions),
        ]:
            for action in actions:
                result = _execute_action(action, context, runner)
                result["phase"] = phase_name
                action_results.append(result)

        assertion_results = [
            evaluate_assertion(assertion, context)
            for assertion in case.assertions
        ]
        failed_assertions = [
            result for result in assertion_results if not result["passed"]
        ]
        if failed_assertions:
            return {
                "case_id": case.case_id,
                "title": case.title,
                "status": "failed",
                "error_log": "结构化断言失败",
                "actual_result": json.dumps(
                    failed_assertions,
                    ensure_ascii=False,
                ),
                "action_results": action_results,
                "assertion_results": assertion_results,
            }

        return {
            "case_id": case.case_id,
            "title": case.title,
            "status": "passed",
            "error_log": "",
            "actual_result": json.dumps(
                assertion_results,
                ensure_ascii=False,
            ),
            "action_results": action_results,
            "assertion_results": assertion_results,
        }
    except Exception as exc:
        return {
            "case_id": case.case_id,
            "title": case.title,
            "status": "failed",
            "error_log": f"Harness 执行失败: {type(exc).__name__}: {exc}",
            "actual_result": "",
            "action_results": action_results,
            "assertion_results": assertion_results,
        }


def execute_structured_cases(
    cases: list[TestCaseSpec],
    runner: OperationRunner = run_registered_operation,
) -> list[dict[str, Any]]:
    return [execute_structured_case(case, runner=runner) for case in cases]

