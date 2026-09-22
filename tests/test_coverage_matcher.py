from app.models.test_design import (
    BusinessType,
    CoverageCategory,
    ParameterSpec,
    RequirementRule,
    TestPoint,
)
from app.tools.coverage_matcher import (
    build_keyword_coverage_matrix,
    enrich_test_points_with_keywords,
)


def make_rule() -> RequirementRule:
    return RequirementRule(
        rule_id="REQ_PAY_001",
        text="支付金额必须大于 0，重复支付不能重复扣款",
        business_type=BusinessType.PAYMENT,
        action="pay_order",
        expected_outcomes=["payment_status=paid"],
        parameters=[
            ParameterSpec(
                name="amount",
                data_type="number",
                required=True,
                invalid_values=[0, -1],
                boundary_values=[0, 0.01],
                constraints=["amount>0"],
            )
        ],
        risks=["amount_boundary", "idempotency", "duplicate_charge"],
    )


def make_unstructured_point() -> TestPoint:
    return TestPoint(
        test_point_id="TP_PAY_TEXT_001",
        requirement_ids=["REQ_PAY_001"],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.INPUT_PARAMETER,
        level_2="支付金额边界和重复支付",
        description="使用无效金额和最小金额 0.01，并验证重复支付不会重复扣款",
        executable=True,
    )


def test_keyword_enrichment_returns_copy_without_mutating_original():
    original = make_unstructured_point()

    enriched, matches = enrich_test_points_with_keywords([make_rule()], [original])

    assert original.parameter_names == []
    assert original.parameter_checks == []
    assert original.risk_tags == []
    assert enriched[0].parameter_names == ["amount"]
    assert "invalid" in enriched[0].parameter_checks
    assert "boundary" in enriched[0].parameter_checks
    assert "amount_boundary" in enriched[0].risk_tags
    assert "idempotency" in enriched[0].risk_tags
    assert matches


def test_keyword_matrix_records_method_confidence_and_hit_text():
    matrix, matches = build_keyword_coverage_matrix(
        [make_rule()],
        [make_unstructured_point()],
    )
    evidence = next(
        item
        for item in matrix.evidence
        if item.target_id == "REQ_PAY_001:parameter:amount:boundary"
    )

    assert evidence.covered is True
    assert evidence.method == "keyword_match"
    assert evidence.confidence == 0.65
    assert any("0.01" in text or "最小" in text for text in evidence.evidence)
    assert any(match["target_id"] == evidence.target_id for match in matches)


def test_existing_structured_match_is_not_downgraded_to_keyword_match():
    point = make_unstructured_point().model_copy(
        update={
            "parameter_names": ["amount"],
            "parameter_checks": ["boundary"],
        }
    )

    matrix, matches = build_keyword_coverage_matrix([make_rule()], [point])
    evidence = next(
        item
        for item in matrix.evidence
        if item.target_id == "REQ_PAY_001:parameter:amount:boundary"
    )

    assert evidence.method == "structured_match"
    assert not any(match["target_id"] == evidence.target_id for match in matches)


def test_unrelated_text_does_not_create_parameter_or_risk_evidence():
    point = TestPoint(
        test_point_id="TP_PAY_UNRELATED",
        requirement_ids=["REQ_PAY_001"],
        business_type=BusinessType.PAYMENT,
        level_1=CoverageCategory.FUNCTIONAL_BEHAVIOR,
        level_2="展示支付页面",
        description="检查页面标题",
        executable=True,
    )

    enriched, matches = enrich_test_points_with_keywords([make_rule()], [point])

    assert enriched[0].parameter_names == []
    assert enriched[0].risk_tags == []
    assert matches == []


def test_point_with_unknown_rule_reference_is_ignored_by_keyword_matcher():
    point = make_unstructured_point().model_copy(
        update={"requirement_ids": ["REQ_NOT_EXISTS"]}
    )

    enriched, matches = enrich_test_points_with_keywords([make_rule()], [point])

    assert enriched[0].parameter_names == []
    assert enriched[0].risk_tags == []
    assert matches == []


def test_keyword_matching_does_not_invent_risks_not_declared_by_rule():
    rule = make_rule().model_copy(update={"risks": ["amount_boundary"]})
    point = make_unstructured_point()

    enriched, matches = enrich_test_points_with_keywords([rule], [point])

    assert "amount_boundary" in enriched[0].risk_tags
    assert "idempotency" not in enriched[0].risk_tags
    assert "duplicate_charge" not in enriched[0].risk_tags
    assert all(
        not match["target_id"].endswith(":idempotency")
        for match in matches
    )
