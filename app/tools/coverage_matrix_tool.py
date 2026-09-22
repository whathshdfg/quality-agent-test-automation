"""Build deterministic requirement, parameter, and risk coverage matrices."""

from app.models.test_design import (
    BusinessType,
    CoverageEvidence,
    CoverageGap,
    CoverageMatrix,
    CoverageSummary,
    GapType,
    RequirementRule,
    TestPoint,
)


def _summary(total: int, covered: int, missing_ids: list[str]) -> CoverageSummary:
    return CoverageSummary(
        total=total,
        covered=covered,
        coverage_rate=round(covered / total * 100, 2) if total else 0,
        missing_ids=missing_ids,
    )


def _parameter_checks(parameter) -> list[str]:
    checks = ["normal"]
    if parameter.required:
        checks.append("empty")
    if parameter.invalid_values:
        checks.append("invalid")
    if parameter.boundary_values:
        checks.append("boundary")
    if parameter.constraints:
        checks.append("constraint")
    return checks


def _linked_points(rule_id: str, points: list[TestPoint]) -> list[TestPoint]:
    return [point for point in points if rule_id in point.requirement_ids]


def build_coverage_matrix(
    rules: list[RequirementRule],
    test_points: list[TestPoint],
) -> CoverageMatrix:
    """Calculate coverage from explicit structured links only."""

    evidence: list[CoverageEvidence] = []
    gaps: list[CoverageGap] = []

    requirement_missing: list[str] = []
    requirement_covered = 0

    for rule in rules:
        linked = _linked_points(rule.rule_id, test_points)
        point_ids = [point.test_point_id for point in linked]
        covered = bool(point_ids)
        if covered:
            requirement_covered += 1
        else:
            requirement_missing.append(rule.rule_id)
            gaps.append(
                CoverageGap(
                    gap_id=f"GAP_REQ_{rule.rule_id}",
                    gap_type=GapType.REQUIREMENT,
                    target_id=rule.rule_id,
                    description=f"需求规则 {rule.rule_id} 没有对应测试点",
                    business_type=rule.business_type,
                    priority="high",
                    suggested_test_point=rule.text,
                )
            )

        evidence.append(
            CoverageEvidence(
                target_id=rule.rule_id,
                covered=covered,
                method="explicit_reference" if covered else "none",
                confidence=1 if covered else 0,
                test_point_ids=point_ids,
                evidence=[f"{point_id} 引用 {rule.rule_id}" for point_id in point_ids],
            )
        )

    parameter_targets: list[tuple[RequirementRule, str, str]] = []
    for rule in rules:
        for parameter in rule.parameters:
            for check in _parameter_checks(parameter):
                parameter_targets.append((rule, parameter.name, check))

    parameter_missing: list[str] = []
    parameter_covered = 0

    for rule, parameter_name, check in parameter_targets:
        target_id = f"{rule.rule_id}:parameter:{parameter_name}:{check}"
        matched = [
            point
            for point in _linked_points(rule.rule_id, test_points)
            if parameter_name in point.parameter_names
            and check in point.parameter_checks
        ]
        point_ids = [point.test_point_id for point in matched]
        covered = bool(point_ids)
        if covered:
            parameter_covered += 1
        else:
            parameter_missing.append(target_id)
            gaps.append(
                CoverageGap(
                    gap_id=f"GAP_PARAM_{rule.rule_id}_{parameter_name}_{check}",
                    gap_type=GapType.PARAMETER,
                    target_id=target_id,
                    description=(
                        f"参数 {parameter_name} 缺少 {check} 类型测试点"
                    ),
                    business_type=rule.business_type,
                    priority="high" if check in {"empty", "invalid", "boundary"} else "medium",
                    suggested_test_point=(
                        f"为 {parameter_name} 增加 {check} 参数检查"
                    ),
                )
            )

        evidence.append(
            CoverageEvidence(
                target_id=target_id,
                covered=covered,
                method="structured_match" if covered else "none",
                confidence=1 if covered else 0,
                test_point_ids=point_ids,
                evidence=[
                    f"{point_id} 显式覆盖 {parameter_name}:{check}"
                    for point_id in point_ids
                ],
            )
        )

    risk_targets = [
        (rule, risk)
        for rule in rules
        for risk in dict.fromkeys(rule.risks)
    ]
    risk_missing: list[str] = []
    risk_covered = 0

    for rule, risk in risk_targets:
        target_id = f"{rule.rule_id}:risk:{risk}"
        matched = [
            point
            for point in _linked_points(rule.rule_id, test_points)
            if risk in point.risk_tags
        ]
        point_ids = [point.test_point_id for point in matched]
        covered = bool(point_ids)
        if covered:
            risk_covered += 1
        else:
            risk_missing.append(target_id)
            gaps.append(
                CoverageGap(
                    gap_id=f"GAP_RISK_{rule.rule_id}_{risk}",
                    gap_type=GapType.RISK,
                    target_id=target_id,
                    description=f"风险 {risk} 没有对应测试点",
                    business_type=rule.business_type,
                    priority="high",
                    suggested_test_point=f"为 {rule.rule_id} 增加 {risk} 风险检查",
                )
            )

        evidence.append(
            CoverageEvidence(
                target_id=target_id,
                covered=covered,
                method="structured_match" if covered else "none",
                confidence=1 if covered else 0,
                test_point_ids=point_ids,
                evidence=[
                    f"{point_id} 显式覆盖风险 {risk}"
                    for point_id in point_ids
                ],
            )
        )

    for point in test_points:
        if point.executable is False:
            gaps.append(
                CoverageGap(
                    gap_id=f"GAP_EXEC_{point.test_point_id}",
                    gap_type=GapType.EXECUTABILITY,
                    target_id=point.test_point_id,
                    description=(
                        point.unsupported_reason
                        or f"测试点 {point.test_point_id} 当前不可执行"
                    ),
                    business_type=point.business_type,
                    priority="medium",
                    suggested_test_point="补充执行器能力或安排人工验证",
                )
            )

    return CoverageMatrix(
        requirement_coverage=_summary(
            len(rules),
            requirement_covered,
            requirement_missing,
        ),
        parameter_coverage=_summary(
            len(parameter_targets),
            parameter_covered,
            parameter_missing,
        ),
        risk_coverage=_summary(
            len(risk_targets),
            risk_covered,
            risk_missing,
        ),
        evidence=evidence,
        gaps=gaps,
    )


def serialize_coverage_matrix(matrix: CoverageMatrix) -> dict:
    return matrix.model_dump(mode="json")

