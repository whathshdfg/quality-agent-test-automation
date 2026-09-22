"""Keyword fallback matching for test points missing structured coverage tags."""

from typing import TypedDict

from app.models.test_design import CoverageMatrix, RequirementRule, TestPoint
from app.tools.coverage_matrix_tool import build_coverage_matrix


class KeywordMatch(TypedDict):
    test_point_id: str
    target_id: str
    target_type: str
    matched_keywords: list[str]
    confidence: float


PARAMETER_ALIASES = {
    "order_id": ["order_id", "订单编号", "订单id", "订单 ID"],
    "user_id": ["user_id", "用户编号", "用户id", "用户 ID"],
    "cancel_reason": ["cancel_reason", "取消原因"],
    "amount": ["amount", "支付金额", "金额"],
    "start_location": ["start_location", "起点", "出发地"],
    "end_location": ["end_location", "终点", "目的地"],
}


PARAMETER_CHECK_KEYWORDS = {
    "normal": ["正常", "有效值", "有效金额", "成功"],
    "empty": ["为空", "空值", "缺失", "必填", "不传", "null", "None"],
    "invalid": ["非法", "无效", "错误", "不存在", "负数", "异常"],
    "boundary": ["边界", "最小", "最大", "临界", "0.01", "超时"],
    "constraint": ["约束", "必须", "不能", "大于", "小于", "相同"],
    "combination": ["组合", "同时", "起终点", "起点终点"],
}


RISK_KEYWORDS = {
    "state_transition": ["状态迁移", "状态变更", "变为", "保持"],
    "required_parameter": ["必填", "为空", "不传", "缺失"],
    "parameter_combination": ["参数组合", "起终点", "起点终点", "相同"],
    "amount_boundary": ["金额边界", "最小金额", "0.01", "金额为 0", "金额为0"],
    "boundary": ["边界", "超时", "3 分钟", "临界"],
    "idempotency": ["幂等", "重复操作", "重复取消", "重复支付", "重复下单"],
    "duplicate_charge": ["重复扣款", "重复支付"],
    "duplicate_data": ["重复数据", "重复订单", "重复下单"],
    "failure_rollback": ["失败回滚", "失败后保持", "保持 unpaid"],
    "resource_release": ["资源释放", "释放司机", "恢复 available"],
    "resource_allocation": ["资源分配", "分配司机", "变为 assigned"],
    "data_consistency": ["数据一致性", "详情与列表", "保持一致"],
    "unsupported_business": ["不支持", "人工确认"],
}


def _point_text(point: TestPoint) -> str:
    return "\n".join([point.level_2, point.description]).lower()


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword.lower() in text]


def _parameter_aliases(parameter_name: str) -> list[str]:
    aliases = PARAMETER_ALIASES.get(parameter_name, [])
    return list(dict.fromkeys([parameter_name, *aliases]))


def enrich_test_points_with_keywords(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
) -> tuple[list[TestPoint], list[KeywordMatch]]:
    """Return enriched copies and auditable keyword match records."""

    rules_by_id = {rule.rule_id: rule for rule in rules}
    enriched_points: list[TestPoint] = []
    matches: list[KeywordMatch] = []
    seen_targets: set[tuple[str, str]] = set()

    for original in test_points:
        point = original.model_copy(deep=True)
        text = _point_text(point)

        for rule_id in point.requirement_ids:
            rule = rules_by_id.get(rule_id)
            if not rule:
                continue

            for parameter in rule.parameters:
                alias_hits = _matched_keywords(
                    text,
                    _parameter_aliases(parameter.name),
                )
                if not alias_hits:
                    continue

                if parameter.name not in point.parameter_names:
                    point.parameter_names.append(parameter.name)

                for check, keywords in PARAMETER_CHECK_KEYWORDS.items():
                    check_hits = _matched_keywords(text, keywords)
                    if not check_hits or check in point.parameter_checks:
                        continue

                    point.parameter_checks.append(check)
                    target_id = f"{rule.rule_id}:parameter:{parameter.name}:{check}"
                    match_key = (point.test_point_id, target_id)
                    if match_key in seen_targets:
                        continue
                    matches.append(
                        {
                            "test_point_id": point.test_point_id,
                            "target_id": target_id,
                            "target_type": "parameter",
                            "matched_keywords": list(dict.fromkeys(alias_hits + check_hits)),
                            "confidence": 0.65,
                        }
                    )
                    seen_targets.add(match_key)

            for risk in rule.risks:
                if risk in point.risk_tags:
                    continue
                risk_hits = _matched_keywords(text, RISK_KEYWORDS.get(risk, []))
                if not risk_hits:
                    continue

                point.risk_tags.append(risk)
                target_id = f"{rule.rule_id}:risk:{risk}"
                match_key = (point.test_point_id, target_id)
                if match_key in seen_targets:
                    continue
                matches.append(
                    {
                        "test_point_id": point.test_point_id,
                        "target_id": target_id,
                        "target_type": "risk",
                        "matched_keywords": risk_hits,
                        "confidence": 0.65,
                    }
                )
                seen_targets.add(match_key)

        enriched_points.append(point)

    return enriched_points, matches


def build_keyword_coverage_matrix(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
) -> tuple[CoverageMatrix, list[KeywordMatch]]:
    enriched_points, matches = enrich_test_points_with_keywords(rules, test_points)
    matrix = build_coverage_matrix(rules, enriched_points)

    matches_by_target: dict[str, list[KeywordMatch]] = {}
    for match in matches:
        matches_by_target.setdefault(match["target_id"], []).append(match)

    for item in matrix.evidence:
        target_matches = matches_by_target.get(item.target_id, [])
        if not target_matches:
            continue

        item.method = "keyword_match"
        item.confidence = max(match["confidence"] for match in target_matches)
        item.evidence = [
            (
                f"{match['test_point_id']} 关键词命中: "
                f"{', '.join(match['matched_keywords'])}"
            )
            for match in target_matches
        ]

    return matrix, matches

