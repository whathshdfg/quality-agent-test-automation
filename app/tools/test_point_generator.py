"""Generate layered test points from validated requirement rules."""

import json
import os
from typing import Callable, Literal, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    RequirementRule,
    TestPoint,
)
from app.tools.requirement_analyzer import extract_json_array


load_dotenv()


class PointGenerationResult(TypedDict):
    test_points: list[TestPoint]
    source: Literal["llm", "rule"]
    fallback_reason: str


RISK_LAYER_MAPPING: dict[str, tuple[CoverageCategory, str]] = {
    "state_transition": (CoverageCategory.STATE_FLOW, "状态迁移"),
    "required_parameter": (CoverageCategory.INPUT_PARAMETER, "必填参数"),
    "parameter_combination": (CoverageCategory.INPUT_PARAMETER, "参数组合"),
    "amount_boundary": (CoverageCategory.INPUT_PARAMETER, "数值边界"),
    "boundary": (CoverageCategory.INPUT_PARAMETER, "边界条件"),
    "idempotency": (CoverageCategory.RELIABILITY, "幂等性"),
    "duplicate_charge": (CoverageCategory.RELIABILITY, "重复操作保护"),
    "duplicate_data": (CoverageCategory.RELIABILITY, "重复数据保护"),
    "failure_rollback": (CoverageCategory.RELIABILITY, "失败回滚"),
    "resource_release": (CoverageCategory.RESOURCE_DEPENDENCY, "资源释放"),
    "resource_allocation": (CoverageCategory.RESOURCE_DEPENDENCY, "资源分配"),
    "data_consistency": (CoverageCategory.DATA_QUALITY, "数据一致性"),
    "unsupported_business": (CoverageCategory.FUNCTIONAL_BEHAVIOR, "人工确认"),
}


BUSINESS_PREFIX = {
    BusinessType.ORDER_CANCEL: "CANCEL",
    BusinessType.PAYMENT: "PAY",
    BusinessType.ORDER_CREATE: "ORDER",
    BusinessType.UNKNOWN: "UNKNOWN",
}


def build_test_point_prompt(rules: list[RequirementRule]) -> str:
    if not rules:
        raise ValueError("requirement_rules 不能为空")

    schema = json.dumps(TestPoint.model_json_schema(), ensure_ascii=False, indent=2)
    rule_data = json.dumps(
        [rule.model_dump(mode="json") for rule in rules],
        ensure_ascii=False,
        indent=2,
    )
    return f"""
你是资深测试分析师。请根据已经结构化的需求规则生成测试点，不要生成测试用例步骤。

一级维度及含义：
- functional_behavior：正常流程、备选流程、业务异常、非法操作
- input_parameter：必填、类型、格式、枚举、等价类、边界、参数组合
- state_flow：前置状态、合法迁移、非法迁移、终态
- resource_dependency：资源分配、资源释放、依赖异常、失败回滚
- data_quality：响应、详情、列表及关联数据的一致性和完整性
- reliability：幂等、重复操作、超时、重试、并发、恢复
- security_permission：身份、权限、越权、数据隔离

要求：
1. 每条需求规则至少关联一个测试点。
2. requirement_ids 只能引用输入中存在的 rule_id。
3. business_type 必须与被引用需求规则一致。
4. level_2 必须是具体检查点，不能只重复一级维度名称。
5. 当前接口能力无法执行的测试点将 executable 设为 false，并填写 unsupported_reason。
6. 不要编造输入规则中不存在的业务能力。
7. 只输出 JSON 数组，不要输出 Markdown 或解释文字。

每个元素必须符合以下 JSON Schema：
{schema}

需求规则：
{rule_data}
""".strip()


def call_test_point_llm(prompt: str) -> str:
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
                "content": "你只输出符合给定 Schema 的测试点 JSON 数组。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    output = response.choices[0].message.content
    if not output:
        raise ValueError("模型返回内容为空")
    return output


def validate_test_points(
    data: list[dict],
    rules: list[RequirementRule],
) -> list[TestPoint]:
    if not rules:
        raise ValueError("requirement_rules 不能为空")

    points = [TestPoint.model_validate(item) for item in data]
    if not points:
        raise ValueError("测试点生成结果不能为空")

    point_ids = [point.test_point_id for point in points]
    if len(point_ids) != len(set(point_ids)):
        raise ValueError("测试点 test_point_id 不能重复")

    rules_by_id = {rule.rule_id: rule for rule in rules}
    referenced_rule_ids: set[str] = set()

    for point in points:
        unknown_ids = set(point.requirement_ids) - set(rules_by_id)
        if unknown_ids:
            raise ValueError(
                f"测试点 {point.test_point_id} 引用了不存在的需求规则: "
                f"{sorted(unknown_ids)}"
            )

        referenced_rules = [rules_by_id[rule_id] for rule_id in point.requirement_ids]
        if any(rule.business_type != point.business_type for rule in referenced_rules):
            raise ValueError(
                f"测试点 {point.test_point_id} 的业务类型与需求规则不一致"
            )
        referenced_rule_ids.update(point.requirement_ids)

    missing_rule_ids = set(rules_by_id) - referenced_rule_ids
    if missing_rule_ids:
        raise ValueError(
            f"以下需求规则没有对应测试点: {sorted(missing_rule_ids)}"
        )
    return points


def _append_point(
    points: list[TestPoint],
    seen: set[tuple[str, CoverageCategory, str]],
    rule: RequirementRule,
    category: CoverageCategory,
    level_2: str,
    description: str,
    risk_level: Literal["low", "medium", "high"] = "medium",
    parameter_names: list[str] | None = None,
    parameter_checks: list[
        Literal["normal", "empty", "invalid", "boundary", "constraint", "combination"]
    ] | None = None,
    risk_tags: list[str] | None = None,
) -> None:
    semantic_key = (rule.rule_id, category, level_2)
    if semantic_key in seen:
        return

    prefix = BUSINESS_PREFIX[rule.business_type]
    point_id = f"TP_{prefix}_AUTO_{len(points) + 1:03d}"
    is_unknown = rule.business_type == BusinessType.UNKNOWN
    points.append(
        TestPoint(
            test_point_id=point_id,
            requirement_ids=[rule.rule_id],
            business_type=rule.business_type,
            level_1=category,
            level_2=level_2,
            description=description,
            risk_level=risk_level,
            parameter_names=parameter_names or [],
            parameter_checks=parameter_checks or [],
            risk_tags=risk_tags or [],
            executable=False if is_unknown else None,
            unsupported_reason=(
                "当前系统不支持该业务类型，需要人工确认"
                if is_unknown
                else ""
            ),
        )
    )
    seen.add(semantic_key)


def generate_rule_based_test_points(
    rules: list[RequirementRule],
) -> list[TestPoint]:
    if not rules:
        raise ValueError("requirement_rules 不能为空")

    points: list[TestPoint] = []
    seen: set[tuple[str, CoverageCategory, str]] = set()

    for rule in rules:
        _append_point(
            points,
            seen,
            rule,
            CoverageCategory.FUNCTIONAL_BEHAVIOR,
            "业务规则验证",
            f"验证需求规则：{rule.text}",
        )

        for parameter in rule.parameters:
            checks = []
            parameter_checks = ["normal"]
            if parameter.required:
                checks.append("必填")
                parameter_checks.append("empty")
            if parameter.invalid_values:
                checks.append("非法值")
                parameter_checks.append("invalid")
            if parameter.boundary_values:
                checks.append("边界值")
                parameter_checks.append("boundary")
            if parameter.constraints:
                checks.append("约束")
                parameter_checks.append("constraint")
            check_text = "、".join(checks) or "正常值"
            _append_point(
                points,
                seen,
                rule,
                CoverageCategory.INPUT_PARAMETER,
                f"{parameter.name} 参数校验",
                f"验证 {parameter.name} 的{check_text}",
                "high" if parameter.required else "medium",
                parameter_names=[parameter.name],
                parameter_checks=parameter_checks,
            )

        for risk in rule.risks:
            mapping = RISK_LAYER_MAPPING.get(risk)
            if not mapping:
                continue
            category, level_2 = mapping
            _append_point(
                points,
                seen,
                rule,
                category,
                level_2,
                f"针对 {rule.rule_id} 验证风险：{risk}",
                "high",
                risk_tags=[risk],
            )

    return points


def generate_test_points(
    rules: list[RequirementRule],
    call_fn: Callable[[str], str] | None = None,
) -> PointGenerationResult:
    """Use the API model first and fall back to deterministic layered points."""

    if not rules:
        raise ValueError("requirement_rules 不能为空")

    model_call = call_fn or call_test_point_llm
    try:
        output = model_call(build_test_point_prompt(rules))
        points = validate_test_points(extract_json_array(output), rules)
        return {
            "test_points": points,
            "source": "llm",
            "fallback_reason": "",
        }
    except Exception as exc:
        return {
            "test_points": generate_rule_based_test_points(rules),
            "source": "rule",
            "fallback_reason": f"{type(exc).__name__}: {exc}",
        }
