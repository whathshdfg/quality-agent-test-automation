"""Add test points for concrete uncovered requirement, parameter, and risk gaps."""

import json
import os
from typing import Callable, Literal, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    CoverageGap,
    CoverageMatrix,
    CoverageSummary,
    GapType,
    RequirementRule,
    TestPoint,
)
from app.tools.coverage_matcher import build_keyword_coverage_matrix
from app.tools.requirement_analyzer import extract_json_array


load_dotenv()


class PointEnhancementResult(TypedDict):
    test_points: list[TestPoint]
    added_test_points: list[TestPoint]
    matrix: CoverageMatrix
    addressed_gap_ids: list[str]
    source: Literal["llm", "rule", "not_needed", "stopped"]
    fallback_reason: str
    stop_reason: str


BUSINESS_PREFIX = {
    BusinessType.ORDER_CANCEL: "CANCEL",
    BusinessType.PAYMENT: "PAY",
    BusinessType.ORDER_CREATE: "ORDER",
    BusinessType.UNKNOWN: "UNKNOWN",
}


def actionable_gaps(matrix: CoverageMatrix) -> list[CoverageGap]:
    return [
        gap
        for gap in matrix.gaps
        if gap.gap_type in {
            GapType.REQUIREMENT,
            GapType.PARAMETER,
            GapType.RISK,
        }
    ]


def build_enhancement_prompt(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
    matrix: CoverageMatrix,
) -> str:
    gaps = actionable_gaps(matrix)
    if not gaps:
        raise ValueError("没有可通过新增测试点解决的覆盖缺口")

    payload = {
        "requirement_rules": [rule.model_dump(mode="json") for rule in rules],
        "existing_test_points": [
            point.model_dump(mode="json") for point in test_points
        ],
        "coverage_gaps": [gap.model_dump(mode="json") for gap in gaps],
    }
    schema = TestPoint.model_json_schema()
    return f"""
你是测试设计补充器。请只针对给出的 coverage_gaps 新增最少数量的测试点。

要求：
1. 每个新增测试点必须解决至少一个具体 target_id。
2. requirement 缺口通过 requirement_ids 建立显式关联。
3. parameter 缺口必须填写 parameter_names 和 parameter_checks。
4. risk 缺口必须填写 risk_tags。
5. 不能重复 existing_test_points 中已有的测试点。
6. 不能修改或删除已有测试点。
7. executability 缺口不能通过新增测试点解决，不会出现在输入中。
8. 只输出新增测试点 JSON 数组，不要输出 Markdown 或解释文字。

单条测试点 JSON Schema：
{json.dumps(schema, ensure_ascii=False, indent=2)}

输入：
{json.dumps(payload, ensure_ascii=False, indent=2)}
""".strip()


def call_enhancement_llm(prompt: str) -> str:
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
                "content": "你只输出用于填补指定缺口的测试点 JSON 数组。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    output = response.choices[0].message.content
    if not output:
        raise ValueError("模型返回内容为空")
    return output


def validate_supplement_points(
    data: list[dict],
    rules: list[RequirementRule],
    existing_points: list[TestPoint],
) -> list[TestPoint]:
    points = [TestPoint.model_validate(item) for item in data]
    if not points:
        raise ValueError("模型没有生成补充测试点")

    rule_map = {rule.rule_id: rule for rule in rules}
    existing_ids = {point.test_point_id for point in existing_points}
    new_ids = [point.test_point_id for point in points]
    if len(new_ids) != len(set(new_ids)):
        raise ValueError("补充测试点 test_point_id 不能重复")
    if existing_ids & set(new_ids):
        raise ValueError("补充测试点不能复用已有 test_point_id")

    for point in points:
        unknown_rules = set(point.requirement_ids) - set(rule_map)
        if unknown_rules:
            raise ValueError(f"补充测试点引用了不存在的规则: {sorted(unknown_rules)}")
        for rule_id in point.requirement_ids:
            if point.business_type != rule_map[rule_id].business_type:
                raise ValueError("补充测试点与需求规则业务类型不一致")
    return points


def _next_point_id(
    business_type: BusinessType,
    used_ids: set[str],
    index: int,
) -> tuple[str, int]:
    prefix = BUSINESS_PREFIX[business_type]
    while True:
        point_id = f"TP_{prefix}_GAP_{index:03d}"
        index += 1
        if point_id not in used_ids:
            return point_id, index


def generate_rule_based_supplement_points(
    rules: list[RequirementRule],
    existing_points: list[TestPoint],
    matrix: CoverageMatrix,
) -> list[TestPoint]:
    rule_map = {rule.rule_id: rule for rule in rules}
    used_ids = {point.test_point_id for point in existing_points}
    points: list[TestPoint] = []
    index = 1

    for gap in actionable_gaps(matrix):
        rule_id = gap.target_id.split(":", 1)[0]
        rule = rule_map.get(rule_id)
        if not rule:
            continue
        point_id, index = _next_point_id(rule.business_type, used_ids, index)
        used_ids.add(point_id)

        if gap.gap_type == GapType.REQUIREMENT:
            point = TestPoint(
                test_point_id=point_id,
                requirement_ids=[rule.rule_id],
                business_type=rule.business_type,
                level_1=CoverageCategory.FUNCTIONAL_BEHAVIOR,
                level_2="需求规则补充验证",
                description=gap.suggested_test_point or rule.text,
                risk_level=gap.priority,
                executable=None,
            )
        elif gap.gap_type == GapType.PARAMETER:
            parts = gap.target_id.split(":")
            if len(parts) != 4:
                continue
            _, _, parameter_name, check = parts
            point = TestPoint(
                test_point_id=point_id,
                requirement_ids=[rule.rule_id],
                business_type=rule.business_type,
                level_1=CoverageCategory.INPUT_PARAMETER,
                level_2=f"{parameter_name} {check} 定向检查",
                description=gap.suggested_test_point or gap.description,
                risk_level=gap.priority,
                parameter_names=[parameter_name],
                parameter_checks=[check],
                executable=None,
            )
        else:
            parts = gap.target_id.split(":", 2)
            if len(parts) != 3:
                continue
            risk = parts[2]
            category = CoverageCategory.RELIABILITY
            if risk.startswith("resource_"):
                category = CoverageCategory.RESOURCE_DEPENDENCY
            elif risk == "data_consistency":
                category = CoverageCategory.DATA_QUALITY
            elif risk == "state_transition":
                category = CoverageCategory.STATE_FLOW
            elif risk in {
                "required_parameter",
                "parameter_combination",
                "amount_boundary",
                "boundary",
            }:
                category = CoverageCategory.INPUT_PARAMETER

            point = TestPoint(
                test_point_id=point_id,
                requirement_ids=[rule.rule_id],
                business_type=rule.business_type,
                level_1=category,
                level_2=f"{risk} 风险定向检查",
                description=gap.suggested_test_point or gap.description,
                risk_level=gap.priority,
                risk_tags=[risk],
                executable=None,
            )

        points.append(point)
    return points


def _preserve_prior_coverage(
    previous: CoverageMatrix,
    current: CoverageMatrix,
    rules: list[RequirementRule],
) -> CoverageMatrix:
    merged = current.model_copy(deep=True)
    previous_covered = {
        item.target_id: item
        for item in previous.evidence
        if item.covered
    }

    for item in merged.evidence:
        old_item = previous_covered.get(item.target_id)
        if old_item and not item.covered:
            item.covered = True
            item.method = old_item.method
            item.confidence = old_item.confidence
            item.case_ids = old_item.case_ids
            item.test_point_ids = old_item.test_point_ids
            item.evidence = old_item.evidence

    covered_targets = {item.target_id for item in merged.evidence if item.covered}
    merged.gaps = [
        gap for gap in merged.gaps if gap.target_id not in covered_targets
    ]

    requirement_ids = {rule.rule_id for rule in rules}
    parameter_ids = {
        item.target_id for item in merged.evidence if ":parameter:" in item.target_id
    }
    risk_ids = {
        item.target_id for item in merged.evidence if ":risk:" in item.target_id
    }

    def rebuild(target_ids: set[str]) -> CoverageSummary:
        missing = sorted(target_ids - covered_targets)
        covered = len(target_ids) - len(missing)
        return CoverageSummary(
            total=len(target_ids),
            covered=covered,
            coverage_rate=round(covered / len(target_ids) * 100, 2) if target_ids else 0,
            missing_ids=missing,
        )

    merged.requirement_coverage = rebuild(requirement_ids)
    merged.parameter_coverage = rebuild(parameter_ids)
    merged.risk_coverage = rebuild(risk_ids)
    return merged


def _matrix_after_addition(
    rules: list[RequirementRule],
    all_points: list[TestPoint],
    previous_matrix: CoverageMatrix,
) -> CoverageMatrix:
    current, _ = build_keyword_coverage_matrix(rules, all_points)
    return _preserve_prior_coverage(previous_matrix, current, rules)


def _addressed_gaps(
    before: CoverageMatrix,
    after: CoverageMatrix,
) -> list[str]:
    after_covered = {item.target_id for item in after.evidence if item.covered}
    return sorted(
        gap.gap_id
        for gap in actionable_gaps(before)
        if gap.target_id in after_covered
    )


def _contributing_point_ids(
    matrix: CoverageMatrix,
    gap_ids: list[str],
    gaps: list[CoverageGap],
) -> set[str]:
    targets = {gap.target_id for gap in gaps if gap.gap_id in gap_ids}
    return {
        point_id
        for item in matrix.evidence
        if item.target_id in targets
        for point_id in item.test_point_ids
    }


def enhance_test_points(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
    matrix: CoverageMatrix,
    call_fn: Callable[[str], str] | None = None,
) -> PointEnhancementResult:
    gaps = actionable_gaps(matrix)
    if not gaps:
        return {
            "test_points": test_points,
            "added_test_points": [],
            "matrix": matrix,
            "addressed_gap_ids": [],
            "source": "not_needed",
            "fallback_reason": "",
            "stop_reason": "没有可通过新增测试点解决的覆盖缺口",
        }

    model_call = call_fn or call_enhancement_llm
    fallback_reason = ""
    source: Literal["llm", "rule", "not_needed", "stopped"] = "llm"

    try:
        output = model_call(build_enhancement_prompt(rules, test_points, matrix))
        added = validate_supplement_points(
            extract_json_array(output),
            rules,
            test_points,
        )
        candidate_points = [*test_points, *added]
        candidate_matrix = _matrix_after_addition(rules, candidate_points, matrix)
        addressed = _addressed_gaps(matrix, candidate_matrix)
        contributors = _contributing_point_ids(candidate_matrix, addressed, gaps)
        if not addressed:
            raise ValueError("模型生成的测试点没有填补任何具体缺口")
        if any(point.test_point_id not in contributors for point in added):
            raise ValueError("模型生成了与当前覆盖缺口无关的测试点")
    except Exception as exc:
        fallback_reason = f"{type(exc).__name__}: {exc}"
        source = "rule"
        added = generate_rule_based_supplement_points(rules, test_points, matrix)
        candidate_points = [*test_points, *added]
        candidate_matrix = _matrix_after_addition(rules, candidate_points, matrix)
        addressed = _addressed_gaps(matrix, candidate_matrix)

    if not added or not addressed:
        return {
            "test_points": test_points,
            "added_test_points": [],
            "matrix": matrix,
            "addressed_gap_ids": [],
            "source": "stopped",
            "fallback_reason": fallback_reason,
            "stop_reason": "没有新增有效测试点或覆盖矩阵没有提升",
        }

    return {
        "test_points": candidate_points,
        "added_test_points": added,
        "matrix": candidate_matrix,
        "addressed_gap_ids": addressed,
        "source": source,
        "fallback_reason": fallback_reason,
        "stop_reason": "",
    }
