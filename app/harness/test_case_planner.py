"""Create structured, capability-constrained test case plans."""

import json
import os
from typing import Callable, Literal, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

from app.harness.capability_registry import (
    BUSINESS_OPERATIONS,
    CAPABILITY_REGISTRY,
    HARNESS_POLICY,
    evaluate_test_point_support,
)
from app.models.test_design import (
    AssertionSpec,
    BusinessType,
    CoverageCategory,
    OperationCallSpec,
    RequirementRule,
    TestCaseSpec,
    TestPoint,
)
from app.tools.requirement_analyzer import extract_json_array


load_dotenv()


class CasePlanningResult(TypedDict):
    test_cases: list[TestCaseSpec]
    unsupported_test_points: list[dict]
    source: Literal["llm", "rule", "not_needed"]
    fallback_reason: str


def _all_actions(case: TestCaseSpec) -> list[OperationCallSpec]:
    return [
        *case.setup_actions,
        *case.test_actions,
        *case.verification_actions,
    ]


def build_case_plan_prompt(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
) -> str:
    if not test_points:
        raise ValueError("没有可规划的测试点")

    registry = {
        name: capability.model_dump(mode="json")
        for name, capability in CAPABILITY_REGISTRY.items()
    }
    payload = {
        "requirement_rules": [rule.model_dump(mode="json") for rule in rules],
        "test_points": [point.model_dump(mode="json") for point in test_points],
        "capability_registry": registry,
        "harness_policy": HARNESS_POLICY.model_dump(mode="json"),
    }
    return f"""
你是自动化接口测试计划器。请把每个测试点转换成结构化测试用例计划。

硬性约束：
1. 每个测试点至少被一个用例的 test_point_ids 引用。
2. operation_name 只能来自 capability_registry。
3. setup_actions 只能使用 setup_allowed=true 的操作。
4. 操作必须支持用例的 business_type。
5. 每条用例总操作数不能超过 {HARNESS_POLICY.max_requests_per_case}。
6. test_actions 和 assertions 不能为空。
7. arguments 可以使用 ${{变量.字段}} 引用前序 save_as 的结果。
8. 不允许生成 URL、HTTP 方法、Shell 命令或注册表外操作。
9. 只输出测试用例 JSON 数组，不要输出 Markdown 或解释文字。

单条测试用例 JSON Schema：
{json.dumps(TestCaseSpec.model_json_schema(), ensure_ascii=False, indent=2)}

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def call_case_planner_llm(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("未配置 OPENAI_API_KEY")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL"),
    )
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {
                "role": "system",
                "content": "你只能使用提供的能力注册表生成结构化测试计划。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    output = response.choices[0].message.content
    if not output:
        raise ValueError("模型返回内容为空")
    return output


def validate_case_plans(
    data: list[dict],
    rules: list[RequirementRule],
    supported_points: list[TestPoint],
) -> list[TestCaseSpec]:
    cases = [TestCaseSpec.model_validate(item) for item in data]
    if not cases:
        raise ValueError("测试计划不能为空")

    case_ids = [case.case_id for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("测试用例 case_id 不能重复")

    rules_by_id = {rule.rule_id: rule for rule in rules}
    points_by_id = {point.test_point_id: point for point in supported_points}
    referenced_points: set[str] = set()

    for case in cases:
        if not case.test_actions:
            raise ValueError(f"用例 {case.case_id} 的 test_actions 不能为空")
        if not case.assertions:
            raise ValueError(f"用例 {case.case_id} 的 assertions 不能为空")

        unknown_rules = set(case.requirement_ids) - set(rules_by_id)
        unknown_points = set(case.test_point_ids) - set(points_by_id)
        if unknown_rules:
            raise ValueError(f"用例引用不存在的需求规则: {sorted(unknown_rules)}")
        if unknown_points:
            raise ValueError(f"用例引用不存在的测试点: {sorted(unknown_points)}")
        if not case.test_point_ids:
            raise ValueError(f"用例 {case.case_id} 必须引用测试点")

        for point_id in case.test_point_ids:
            point = points_by_id[point_id]
            if point.business_type != case.business_type:
                raise ValueError(f"用例 {case.case_id} 与测试点业务类型不一致")
            if not set(point.requirement_ids) <= set(case.requirement_ids):
                raise ValueError(f"用例 {case.case_id} 缺少测试点关联的需求规则")
        referenced_points.update(case.test_point_ids)

        actions = _all_actions(case)
        if len(actions) > HARNESS_POLICY.max_requests_per_case:
            raise ValueError(f"用例 {case.case_id} 超过单用例请求预算")
        call_ids = [action.call_id for action in actions]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError(f"用例 {case.case_id} 的 call_id 不能重复")

        for action in actions:
            capability = CAPABILITY_REGISTRY.get(action.operation_name)
            if not capability:
                raise ValueError(f"未注册操作: {action.operation_name}")
            if case.business_type not in capability.business_types:
                raise ValueError(
                    f"操作 {action.operation_name} 不支持业务 {case.business_type.value}"
                )
        for action in case.setup_actions:
            if not CAPABILITY_REGISTRY[action.operation_name].setup_allowed:
                raise ValueError(f"操作 {action.operation_name} 不允许用于 setup_actions")

        case.generation_source = "llm"

    missing_points = set(points_by_id) - referenced_points
    if missing_points:
        raise ValueError(f"以下测试点没有对应测试用例: {sorted(missing_points)}")
    return cases


def _call(
    call_id: str,
    operation_name: str,
    arguments: dict | None = None,
    save_as: str = "",
) -> OperationCallSpec:
    return OperationCallSpec(
        call_id=call_id,
        operation_name=operation_name,
        arguments=arguments or {},
        save_as=save_as,
    )


def _base_case(point: TestPoint) -> dict:
    return {
        "case_id": point.test_point_id.replace("TP_", "TC_", 1),
        "title": point.description,
        "precondition": "由 setup_actions 创建隔离的 Mock 前置数据",
        "steps": [],
        "expected_result": point.description,
        "generation_source": "rule",
        "business_type": point.business_type,
        "requirement_ids": point.requirement_ids,
        "test_point_ids": [point.test_point_id],
        "level_1": point.level_1,
        "level_2": point.level_2,
        "input_data": {},
        "setup_actions": [_call("setup_reset", "reset_mock_data")],
        "test_actions": [],
        "verification_actions": [],
        "assertions": [],
        "executable": True,
        "unsupported_reason": "",
    }


def _cancel_plan(point: TestPoint) -> TestCaseSpec:
    data = _base_case(point)
    accepted = "resource_release" in point.risk_tags or "required_parameter" in point.risk_tags
    missing_reason = (
        "cancel_reason" in point.parameter_names
        and "empty" in point.parameter_checks
    )
    data["setup_actions"].append(
        _call(
            "setup_order",
            "create_order",
            {"assign_driver": accepted, "start_location": "A", "end_location": "B"},
            "created_order",
        )
    )
    is_timeout = "boundary" in point.risk_tags and "超时" in (point.level_2 + point.description)
    if is_timeout:
        data["test_actions"] = [
            _call(
                "act_timeout_cancel",
                "timeout_cancel_order",
                {"order_id": "${created_order.order_id}"},
                "cancel_result",
            )
        ]
    else:
        reason = None if missing_reason else "user_cancel"
        data["test_actions"] = [
            _call(
                "act_cancel",
                "cancel_order",
                {
                    "order_id": "${created_order.order_id}",
                    "cancel_reason": reason,
                },
                "cancel_result",
            )
        ]
        if "idempotency" in point.risk_tags:
            data["test_actions"].append(
                _call(
                    "act_cancel_again",
                    "cancel_order",
                    {
                        "order_id": "${created_order.order_id}",
                        "cancel_reason": "repeat_cancel",
                    },
                    "repeat_result",
                )
            )
    data["verification_actions"] = [
        _call(
            "verify_order",
            "get_order",
            {"order_id": "${created_order.order_id}"},
            "order_detail",
        )
    ]
    if "resource_release" in point.risk_tags:
        data["verification_actions"].append(
            _call("verify_driver", "get_driver", {"driver_id": "driver_001"}, "driver_detail")
        )
    data["steps"] = [
        action.operation_name
        for action in [
            *data["setup_actions"],
            *data["test_actions"],
            *data["verification_actions"],
        ]
    ]
    if missing_reason:
        data["assertions"] = [
            AssertionSpec(
                target="cancel_result.message",
                operator="equals",
                expected="CANCEL_REASON_REQUIRED",
            ),
            AssertionSpec(
                target="order_detail.order.order_status",
                operator="equals",
                expected="accepted",
            ),
        ]
    else:
        data["assertions"] = [
            AssertionSpec(
                target="order_detail.order.order_status",
                operator="equals",
                expected="cancelled",
            )
        ]
    if "idempotency" in point.risk_tags:
        data["assertions"].append(
            AssertionSpec(
                target="repeat_result.message",
                operator="equals",
                expected="REPEAT_CANCEL",
            )
        )
    if "resource_release" in point.risk_tags:
        data["assertions"].append(
            AssertionSpec(
                target="driver_detail.driver.driver_status",
                operator="equals",
                expected="available",
            )
        )
    return TestCaseSpec(**data)


def _payment_plan(point: TestPoint) -> TestCaseSpec:
    data = _base_case(point)
    data["setup_actions"].append(
        _call(
            "setup_order",
            "create_order",
            {"assign_driver": False, "start_location": "A", "end_location": "B"},
            "created_order",
        )
    )
    amount = 30.0
    if "invalid" in point.parameter_checks:
        amount = 0
    elif "boundary" in point.parameter_checks or "amount_boundary" in point.risk_tags:
        amount = 0.01
    data["test_actions"] = [
        _call(
            "act_pay",
            "pay_order",
            {"order_id": "${created_order.order_id}", "amount": amount},
            "pay_result",
        )
    ]
    if "idempotency" in point.risk_tags or "duplicate_charge" in point.risk_tags:
        data["test_actions"].append(
            _call(
                "act_pay_again",
                "pay_order",
                {"order_id": "${created_order.order_id}", "amount": amount},
                "repeat_result",
            )
        )
    data["verification_actions"] = [
        _call(
            "verify_order",
            "get_order",
            {"order_id": "${created_order.order_id}"},
            "order_detail",
        )
    ]
    data["steps"] = [
        action.operation_name
        for action in [
            *data["setup_actions"],
            *data["test_actions"],
            *data["verification_actions"],
        ]
    ]
    expected = "unpaid" if amount == 0 else "paid"
    data["assertions"] = [
        AssertionSpec(
            target="order_detail.order.payment_status",
            operator="equals",
            expected=expected,
        )
    ]
    if amount == 0:
        data["assertions"].append(
            AssertionSpec(
                target="pay_result.message",
                operator="equals",
                expected="INVALID_AMOUNT",
            )
        )
    if "idempotency" in point.risk_tags or "duplicate_charge" in point.risk_tags:
        data["assertions"].append(
            AssertionSpec(
                target="repeat_result.message",
                operator="equals",
                expected="REPEAT_PAYMENT",
            )
        )
    return TestCaseSpec(**data)


def _order_create_plan(point: TestPoint) -> TestCaseSpec:
    data = _base_case(point)
    start_location = "A"
    end_location = "B"
    if "empty" in point.parameter_checks:
        if "end_location" in point.parameter_names:
            end_location = ""
        else:
            start_location = ""
    if "combination" in point.parameter_checks:
        end_location = start_location
    assign_driver = "resource_allocation" in point.risk_tags
    data["test_actions"] = [
        _call(
            "act_create",
            "create_order",
            {
                "assign_driver": assign_driver,
                "start_location": start_location,
                "end_location": end_location,
            },
            "created_order",
        )
    ]
    if "idempotency" in point.risk_tags or "duplicate_data" in point.risk_tags:
        data["test_actions"].append(
            _call(
                "act_create_again",
                "create_order",
                {
                    "assign_driver": False,
                    "start_location": start_location,
                    "end_location": end_location,
                },
                "repeat_result",
            )
        )
    if start_location and end_location and start_location != end_location:
        data["verification_actions"] = [
            _call(
                "verify_order",
                "get_order",
                {"order_id": "${created_order.order_id}"},
                "order_detail",
            )
        ]
        if assign_driver:
            data["verification_actions"].append(
                _call(
                    "verify_driver",
                    "get_driver",
                    {"driver_id": "${created_order.driver_id}"},
                    "driver_detail",
                )
            )
    data["steps"] = [
        action.operation_name
        for action in [
            *data["setup_actions"],
            *data["test_actions"],
            *data["verification_actions"],
        ]
    ]
    if not start_location or not end_location:
        target, expected = "created_order.message", "PARAM_ERROR"
    elif start_location == end_location:
        target, expected = "created_order.message", "SAME_LOCATION"
    else:
        target, expected = "created_order.order_status", "accepted" if assign_driver else "waiting"
    data["assertions"] = [
        AssertionSpec(target=target, operator="equals", expected=expected)
    ]
    if assign_driver:
        data["assertions"].append(
            AssertionSpec(
                target="driver_detail.driver.driver_status",
                operator="equals",
                expected="assigned",
            )
        )
    if "idempotency" in point.risk_tags or "duplicate_data" in point.risk_tags:
        data["assertions"].append(
            AssertionSpec(
                target="repeat_result.message",
                operator="equals",
                expected="DUPLICATE_ORDER",
            )
        )
    return TestCaseSpec(**data)


def generate_rule_based_case_plans(points: list[TestPoint]) -> list[TestCaseSpec]:
    cases = []
    for point in points:
        if point.business_type == BusinessType.ORDER_CANCEL:
            case = _cancel_plan(point)
        elif point.business_type == BusinessType.PAYMENT:
            case = _payment_plan(point)
        elif point.business_type == BusinessType.ORDER_CREATE:
            case = _order_create_plan(point)
        else:
            continue
        cases.append(case)
    return cases


def plan_test_cases(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
    call_fn: Callable[[str], str] | None = None,
) -> CasePlanningResult:
    supported_points = []
    unsupported = []
    for point in test_points:
        decision = evaluate_test_point_support(point)
        if decision.supported:
            supported_points.append(point)
        else:
            unsupported.append({
                "test_point_id": point.test_point_id,
                "business_type": point.business_type.value,
                "reasons": list(decision.reasons),
            })

    if not supported_points:
        return {
            "test_cases": [],
            "unsupported_test_points": unsupported,
            "source": "not_needed",
            "fallback_reason": "",
        }

    model_call = call_fn or call_case_planner_llm
    try:
        output = model_call(build_case_plan_prompt(rules, supported_points))
        cases = validate_case_plans(
            extract_json_array(output),
            rules,
            supported_points,
        )
        return {
            "test_cases": cases,
            "unsupported_test_points": unsupported,
            "source": "llm",
            "fallback_reason": "",
        }
    except Exception as exc:
        cases = generate_rule_based_case_plans(supported_points)
        cases = validate_case_plans(
            [case.model_dump(mode="json") for case in cases],
            rules,
            supported_points,
        )
        for case in cases:
            case.generation_source = "rule"
        return {
            "test_cases": cases,
            "unsupported_test_points": unsupported,
            "source": "rule",
            "fallback_reason": f"{type(exc).__name__}: {exc}",
        }
