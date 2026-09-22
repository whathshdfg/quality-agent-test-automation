"""API-assisted semantic adjudication for unresolved coverage gaps."""

import json
import os
from typing import Callable, Literal, TypedDict

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.test_design import (
    CoverageMatrix,
    CoverageSummary,
    GapType,
    RequirementRule,
    TestPoint,
)
from app.tools.coverage_matcher import build_keyword_coverage_matrix
from app.tools.requirement_analyzer import extract_json_array


load_dotenv()


class SemanticCoverageDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_id: str = Field(min_length=1)
    covered: bool
    test_point_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_covered_references(self) -> "SemanticCoverageDecision":
        if self.covered and not self.test_point_ids:
            raise ValueError("covered=true 时必须提供 test_point_ids")
        return self


class SemanticMatchResult(TypedDict):
    matrix: CoverageMatrix
    decisions: list[SemanticCoverageDecision]
    accepted_target_ids: list[str]
    source: Literal["llm", "fallback", "not_needed"]
    fallback_reason: str


def _semantic_gaps(matrix: CoverageMatrix) -> list:
    return [
        gap
        for gap in matrix.gaps
        if gap.gap_type in {GapType.PARAMETER, GapType.RISK}
    ]


def build_semantic_coverage_prompt(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
    matrix: CoverageMatrix,
) -> str:
    gaps = _semantic_gaps(matrix)
    if not gaps:
        raise ValueError("没有需要语义判断的覆盖缺口")

    unresolved = [gap.model_dump(mode="json") for gap in gaps]
    rule_data = [rule.model_dump(mode="json") for rule in rules]
    point_data = [
        {
            "test_point_id": point.test_point_id,
            "requirement_ids": point.requirement_ids,
            "business_type": point.business_type.value,
            "level_1": point.level_1.value,
            "level_2": point.level_2,
            "description": point.description,
        }
        for point in test_points
    ]
    schema = SemanticCoverageDecision.model_json_schema()

    return f"""
你是测试覆盖审查器。结构化字段和关键词规则已经处理完毕，请只判断剩余覆盖缺口。

约束：
1. 只能使用 unresolved_gaps 中存在的 target_id。
2. 只能引用 test_points 中存在的 test_point_id。
3. 测试点必须关联目标所属的需求规则，且业务类型一致。
4. 只有测试点语义明确验证目标时 covered 才能为 true。
5. 不确定时 covered=false，不允许为了提高覆盖率猜测。
6. 每个判断必须给出简短 reason 和 0 到 1 的 confidence。
7. 只输出 JSON 数组，不要输出 Markdown 或解释文字。

单条判断 JSON Schema：
{json.dumps(schema, ensure_ascii=False, indent=2)}

requirement_rules:
{json.dumps(rule_data, ensure_ascii=False, indent=2)}

test_points:
{json.dumps(point_data, ensure_ascii=False, indent=2)}

unresolved_gaps:
{json.dumps(unresolved, ensure_ascii=False, indent=2)}
""".strip()


def call_semantic_match_llm(prompt: str) -> str:
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
                "content": "你只输出覆盖判断 JSON 数组，不能虚构任何 ID。",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    output = response.choices[0].message.content
    if not output:
        raise ValueError("模型返回内容为空")
    return output


def validate_semantic_decisions(
    data: list[dict],
    rules: list[RequirementRule],
    test_points: list[TestPoint],
    matrix: CoverageMatrix,
) -> list[SemanticCoverageDecision]:
    decisions = [SemanticCoverageDecision.model_validate(item) for item in data]
    target_ids = [decision.target_id for decision in decisions]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError("语义判断 target_id 不能重复")

    gaps_by_target = {gap.target_id: gap for gap in _semantic_gaps(matrix)}
    points_by_id = {point.test_point_id: point for point in test_points}
    rules_by_id = {rule.rule_id: rule for rule in rules}

    for decision in decisions:
        gap = gaps_by_target.get(decision.target_id)
        if not gap:
            raise ValueError(f"模型返回了未请求的 target_id: {decision.target_id}")

        unknown_point_ids = set(decision.test_point_ids) - set(points_by_id)
        if unknown_point_ids:
            raise ValueError(
                f"模型引用了不存在的 test_point_id: {sorted(unknown_point_ids)}"
            )

        rule_id = decision.target_id.split(":", 1)[0]
        rule = rules_by_id.get(rule_id)
        if not rule:
            raise ValueError(f"覆盖目标无法关联需求规则: {decision.target_id}")

        for point_id in decision.test_point_ids:
            point = points_by_id[point_id]
            if rule_id not in point.requirement_ids:
                raise ValueError(
                    f"测试点 {point_id} 未关联需求规则 {rule_id}"
                )
            if point.business_type != rule.business_type:
                raise ValueError(
                    f"测试点 {point_id} 与需求规则 {rule_id} 业务类型不一致"
                )
    return decisions


def _updated_summary(
    summary: CoverageSummary,
    accepted_target_ids: set[str],
) -> CoverageSummary:
    remaining = [
        target_id
        for target_id in summary.missing_ids
        if target_id not in accepted_target_ids
    ]
    newly_covered = len(summary.missing_ids) - len(remaining)
    covered = summary.covered + newly_covered
    return CoverageSummary(
        total=summary.total,
        covered=covered,
        coverage_rate=round(covered / summary.total * 100, 2) if summary.total else 0,
        missing_ids=remaining,
    )


def apply_semantic_decisions(
    matrix: CoverageMatrix,
    decisions: list[SemanticCoverageDecision],
    confidence_threshold: float,
) -> tuple[CoverageMatrix, list[str]]:
    updated = matrix.model_copy(deep=True)
    accepted = {
        decision.target_id: decision
        for decision in decisions
        if decision.covered and decision.confidence >= confidence_threshold
    }
    accepted_ids = set(accepted)

    for item in updated.evidence:
        decision = accepted.get(item.target_id)
        if not decision:
            continue
        item.covered = True
        item.method = "model_judgment"
        item.confidence = decision.confidence
        item.test_point_ids = decision.test_point_ids
        item.evidence = [decision.reason]

    updated.parameter_coverage = _updated_summary(
        updated.parameter_coverage,
        accepted_ids,
    )
    updated.risk_coverage = _updated_summary(
        updated.risk_coverage,
        accepted_ids,
    )
    updated.gaps = [
        gap for gap in updated.gaps if gap.target_id not in accepted_ids
    ]
    return updated, sorted(accepted_ids)


def build_semantic_coverage_matrix(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
    call_fn: Callable[[str], str] | None = None,
    confidence_threshold: float = 0.8,
) -> SemanticMatchResult:
    if not 0 <= confidence_threshold <= 1:
        raise ValueError("confidence_threshold 必须在 0 到 1 之间")

    matrix, _ = build_keyword_coverage_matrix(rules, test_points)
    if not _semantic_gaps(matrix):
        return {
            "matrix": matrix,
            "decisions": [],
            "accepted_target_ids": [],
            "source": "not_needed",
            "fallback_reason": "",
        }

    model_call = call_fn or call_semantic_match_llm
    try:
        output = model_call(build_semantic_coverage_prompt(rules, test_points, matrix))
        decisions = validate_semantic_decisions(
            extract_json_array(output),
            rules,
            test_points,
            matrix,
        )
        updated, accepted_ids = apply_semantic_decisions(
            matrix,
            decisions,
            confidence_threshold,
        )
        return {
            "matrix": updated,
            "decisions": decisions,
            "accepted_target_ids": accepted_ids,
            "source": "llm",
            "fallback_reason": "",
        }
    except Exception as exc:
        return {
            "matrix": matrix,
            "decisions": [],
            "accepted_target_ids": [],
            "source": "fallback",
            "fallback_reason": f"{type(exc).__name__}: {exc}",
        }

