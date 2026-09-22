"""Extract structured requirement rules before generating test cases."""

import json
import os
import re
from typing import Callable, Literal, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

from app.models.test_design import BusinessType, ParameterSpec, RequirementRule
from app.tools.case_enhancer import classify_business


load_dotenv()


class RequirementAnalysisResult(TypedDict):
    rules: list[RequirementRule]
    source: Literal["llm", "rule"]
    fallback_reason: str


def extract_json_array(text: str) -> list[dict]:
    """Extract one JSON array from plain or Markdown-wrapped model output."""

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("模型输出中没有找到需求规则 JSON 数组")
        data = json.loads(cleaned[start:end + 1])

    if not isinstance(data, list):
        raise ValueError("需求拆解结果必须是 JSON 数组")
    return data


def validate_requirement_rules(data: list[dict]) -> list[RequirementRule]:
    """Validate model output and reject duplicate rule identifiers."""

    rules = [RequirementRule.model_validate(item) for item in data]
    if not rules:
        raise ValueError("需求拆解结果不能为空")

    rule_ids = [rule.rule_id for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise ValueError("需求规则 rule_id 不能重复")
    return rules


def build_requirement_prompt(requirement: str) -> str:
    schema = json.dumps(
        RequirementRule.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )
    return f"""
你是资深测试分析师。请先拆解业务需求，不要直接生成测试用例。

任务：
1. 将每一条可独立验证的业务约束拆成一条需求规则。
2. 明确业务类型、参与者、触发条件、前置状态、动作和预期结果。
3. 提取输入参数的类型、必填性、有效值、非法值、边界值和约束。
4. 标记幂等性、状态迁移、资源释放、失败回滚和数据一致性等风险。
5. 只输出 JSON 数组，不要输出 Markdown 或解释文字。
6. 不确定的信息使用空字符串或空数组，不要编造接口或业务规则。

业务类型只能是：
- order_cancel
- payment
- order_create
- unknown

每个数组元素必须符合以下 JSON Schema：
{schema}

待拆解需求：
{requirement.strip()}
""".strip()


def call_requirement_llm(prompt: str) -> str:
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
                "content": "你只输出符合给定 Schema 的 JSON 数组。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    output = response.choices[0].message.content
    if not output:
        raise ValueError("模型返回内容为空")
    return output


def _cancel_fallback(requirement: str) -> list[RequirementRule]:
    rules = [
        RequirementRule(
            rule_id="REQ_CANCEL_001",
            text="用户取消未完成订单后，订单状态变为 cancelled",
            business_type=BusinessType.ORDER_CANCEL,
            actor="user",
            trigger="用户主动取消订单",
            preconditions=["order_status=waiting 或 accepted"],
            action="cancel_order",
            expected_outcomes=["order_status=cancelled"],
            parameters=[
                ParameterSpec(
                    name="order_id",
                    data_type="string",
                    required=True,
                    invalid_values=["order_not_exists"],
                    constraints=["订单必须存在"],
                )
            ],
            risks=["state_transition", "idempotency"],
        )
    ]

    if any(keyword in requirement for keyword in ["3 分钟", "超时", "没有司机", "未接单"]):
        rules.append(
            RequirementRule(
                rule_id="REQ_CANCEL_002",
                text="waiting 订单满足未接单超时条件后自动取消",
                business_type=BusinessType.ORDER_CANCEL,
                actor="system",
                trigger="timeout_no_driver",
                preconditions=["order_status=waiting"],
                action="timeout_cancel_order",
                expected_outcomes=[
                    "order_status=cancelled",
                    "cancel_reason=timeout_no_driver",
                ],
                risks=["boundary", "state_transition"],
            )
        )

    if any(keyword in requirement for keyword in ["已接单", "取消原因", "原因"]):
        rules.append(
            RequirementRule(
                rule_id="REQ_CANCEL_003",
                text="accepted 订单取消时必须提供取消原因",
                business_type=BusinessType.ORDER_CANCEL,
                actor="user",
                trigger="用户取消已接单订单",
                preconditions=["order_status=accepted"],
                action="cancel_order",
                expected_outcomes=["cancel_reason 被记录"],
                parameters=[
                    ParameterSpec(
                        name="cancel_reason",
                        data_type="string",
                        required=True,
                        invalid_values=[None, ""],
                        constraints=["accepted 订单不能为空"],
                    )
                ],
                risks=["required_parameter", "data_consistency"],
            )
        )

    if any(keyword in requirement for keyword in ["资源", "释放", "司机"]):
        rules.append(
            RequirementRule(
                rule_id="REQ_CANCEL_004",
                text="已分配司机的订单取消后释放司机资源",
                business_type=BusinessType.ORDER_CANCEL,
                actor="system",
                trigger="accepted 订单取消成功",
                preconditions=["driver_status=assigned"],
                action="release_driver",
                expected_outcomes=["driver_status=available"],
                risks=["resource_release", "data_consistency"],
            )
        )
    return rules


def _payment_fallback(requirement: str) -> list[RequirementRule]:
    rules = [
        RequirementRule(
            rule_id="REQ_PAY_001",
            text="有效金额支付成功后订单和支付状态变为 paid",
            business_type=BusinessType.PAYMENT,
            actor="user",
            trigger="提交支付",
            preconditions=["payment_status=unpaid"],
            action="pay_order",
            expected_outcomes=["payment_status=paid", "order_status=paid"],
            parameters=[
                ParameterSpec(
                    name="amount",
                    data_type="number",
                    required=True,
                    valid_values=[0.01, 30.0],
                    invalid_values=[0, -1],
                    boundary_values=[0, 0.01],
                    constraints=["amount>0"],
                )
            ],
            risks=["state_transition", "amount_boundary"],
        )
    ]

    if any(keyword in requirement for keyword in ["失败", "unpaid", "无效金额", "金额"]):
        rules.append(
            RequirementRule(
                rule_id="REQ_PAY_002",
                text="支付校验失败时订单保持 unpaid",
                business_type=BusinessType.PAYMENT,
                actor="system",
                trigger="支付校验失败",
                preconditions=["payment_status=unpaid"],
                action="reject_payment",
                expected_outcomes=["payment_status=unpaid"],
                risks=["failure_rollback", "data_consistency"],
            )
        )

    if any(keyword in requirement for keyword in ["重复", "再次", "REPEAT_PAYMENT"]):
        rules.append(
            RequirementRule(
                rule_id="REQ_PAY_003",
                text="已支付订单再次支付时返回 REPEAT_PAYMENT",
                business_type=BusinessType.PAYMENT,
                actor="user",
                trigger="重复提交支付",
                preconditions=["payment_status=paid"],
                action="pay_order",
                expected_outcomes=["message=REPEAT_PAYMENT", "不重复扣款"],
                risks=["idempotency", "duplicate_charge"],
            )
        )
    return rules


def _order_create_fallback(requirement: str) -> list[RequirementRule]:
    rules = [
        RequirementRule(
            rule_id="REQ_ORDER_001",
            text="有效起点和终点创建订单后返回 order_id，状态为 waiting",
            business_type=BusinessType.ORDER_CREATE,
            actor="user",
            trigger="提交创建订单请求",
            preconditions=["用户不存在未完成订单"],
            action="create_order",
            expected_outcomes=["返回 order_id", "order_status=waiting"],
            parameters=[
                ParameterSpec(
                    name="start_location",
                    data_type="string",
                    required=True,
                    invalid_values=[None, ""],
                    constraints=["不能为空", "不能与 end_location 相同"],
                ),
                ParameterSpec(
                    name="end_location",
                    data_type="string",
                    required=True,
                    invalid_values=[None, ""],
                    constraints=["不能为空", "不能与 start_location 相同"],
                ),
            ],
            risks=["required_parameter", "parameter_combination"],
        )
    ]

    if any(keyword in requirement for keyword in ["重复", "未完成订单", "DUPLICATE_ORDER"]):
        rules.append(
            RequirementRule(
                rule_id="REQ_ORDER_002",
                text="用户存在未完成订单时返回 DUPLICATE_ORDER",
                business_type=BusinessType.ORDER_CREATE,
                actor="user",
                trigger="重复创建订单",
                preconditions=["用户存在未完成订单"],
                action="create_order",
                expected_outcomes=["message=DUPLICATE_ORDER", "不创建新订单"],
                risks=["idempotency", "duplicate_data"],
            )
        )

    if any(keyword in requirement for keyword in ["分配司机", "司机状态", "assigned"]):
        rules.append(
            RequirementRule(
                rule_id="REQ_ORDER_003",
                text="创建订单并分配司机后订单为 accepted，司机为 assigned",
                business_type=BusinessType.ORDER_CREATE,
                actor="system",
                trigger="assign_driver=true",
                preconditions=["driver_status=available"],
                action="create_order_and_assign_driver",
                expected_outcomes=["order_status=accepted", "driver_status=assigned"],
                risks=["resource_allocation", "state_transition"],
            )
        )
    return rules


def generate_rule_based_requirement_rules(requirement: str) -> list[RequirementRule]:
    business_type = classify_business(requirement)
    if business_type == "cancel":
        return _cancel_fallback(requirement)
    if business_type == "payment":
        return _payment_fallback(requirement)
    if business_type == "order_create":
        return _order_create_fallback(requirement)

    return [
        RequirementRule(
            rule_id="REQ_UNKNOWN_001",
            text=requirement.strip() or "未提供有效需求",
            business_type=BusinessType.UNKNOWN,
            action="manual_requirement_review",
            expected_outcomes=["需要人工确认业务类型和验收规则"],
            risks=["unsupported_business"],
        )
    ]


def analyze_requirement(
    requirement: str,
    call_fn: Callable[[str], str] | None = None,
    fallback_requirement: str | None = None,
) -> RequirementAnalysisResult:
    """Use the configured API model first and fall back to deterministic rules."""

    if not requirement.strip():
        raise ValueError("requirement 不能为空")

    model_call = call_fn or call_requirement_llm
    try:
        output = model_call(build_requirement_prompt(requirement))
        rules = validate_requirement_rules(extract_json_array(output))
        return {"rules": rules, "source": "llm", "fallback_reason": ""}
    except Exception as exc:
        return {
            "rules": generate_rule_based_requirement_rules(
                fallback_requirement
                if fallback_requirement is not None
                else requirement
            ),
            "source": "rule",
            "fallback_reason": f"{type(exc).__name__}: {exc}",
        }
