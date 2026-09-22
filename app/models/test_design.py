"""Pydantic contracts for requirement analysis and test design.

These models are intentionally not wired into the Agent graph yet. They define
the contract that later migration stages can adopt without changing the current
runtime behavior in one large step.
"""

from enum import Enum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    """Reject undeclared fields so model output cannot silently drift."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BusinessType(str, Enum):
    ORDER_CANCEL = "order_cancel"
    PAYMENT = "payment"
    ORDER_CREATE = "order_create"
    UNKNOWN = "unknown"


class CoverageCategory(str, Enum):
    FUNCTIONAL_BEHAVIOR = "functional_behavior"
    INPUT_PARAMETER = "input_parameter"
    STATE_FLOW = "state_flow"
    RESOURCE_DEPENDENCY = "resource_dependency"
    DATA_QUALITY = "data_quality"
    RELIABILITY = "reliability"
    SECURITY_PERMISSION = "security_permission"


class GapType(str, Enum):
    REQUIREMENT = "requirement"
    PARAMETER = "parameter"
    RISK = "risk"
    EXECUTABILITY = "executability"


class ParameterSpec(ContractModel):
    name: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    required: bool
    description: str = ""
    valid_values: list[Any] = Field(default_factory=list)
    invalid_values: list[Any] = Field(default_factory=list)
    boundary_values: list[Any] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


class RequirementRule(ContractModel):
    rule_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    business_type: BusinessType
    source: str = "user_requirement"
    actor: str = ""
    trigger: str = ""
    preconditions: list[str] = Field(default_factory=list)
    action: str = ""
    expected_outcomes: list[str] = Field(default_factory=list)
    parameters: list[ParameterSpec] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class TestPoint(ContractModel):
    __test__: ClassVar[bool] = False

    test_point_id: str = Field(min_length=1)
    requirement_ids: list[str] = Field(min_length=1)
    business_type: BusinessType
    level_1: CoverageCategory
    level_2: str = Field(min_length=1)
    description: str = Field(min_length=1)
    risk_level: Literal["low", "medium", "high"] = "medium"
    parameter_names: list[str] = Field(default_factory=list)
    parameter_checks: list[
        Literal["normal", "empty", "invalid", "boundary", "constraint", "combination"]
    ] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)
    executable: bool | None = None
    unsupported_reason: str = ""

    @model_validator(mode="after")
    def validate_execution_support(self) -> "TestPoint":
        if self.executable is False and not self.unsupported_reason:
            raise ValueError("unsupported_reason is required when executable is false")
        return self


class AssertionSpec(ContractModel):
    target: str = Field(min_length=1)
    operator: Literal[
        "equals",
        "not_equals",
        "contains",
        "exists",
        "not_exists",
        "in",
        "greater_than",
        "greater_than_or_equal",
        "less_than",
        "less_than_or_equal",
    ]
    expected: Any = None
    description: str = ""


class OperationCallSpec(ContractModel):
    call_id: str = Field(min_length=1)
    operation_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    save_as: str = ""


class TestCaseSpec(ContractModel):
    """Current five fields remain required; structured fields are additive."""

    __test__: ClassVar[bool] = False

    case_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    precondition: str
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    generation_source: Literal[
        "llm",
        "rule",
        "auto_supplement",
        "unknown",
    ] = "unknown"
    business_type: BusinessType = BusinessType.UNKNOWN
    requirement_ids: list[str] = Field(default_factory=list)
    test_point_ids: list[str] = Field(default_factory=list)
    level_1: CoverageCategory | None = None
    level_2: str = ""
    input_data: dict[str, Any] = Field(default_factory=dict)
    setup_actions: list[OperationCallSpec] = Field(default_factory=list)
    test_actions: list[OperationCallSpec] = Field(default_factory=list)
    verification_actions: list[OperationCallSpec] = Field(default_factory=list)
    assertions: list[AssertionSpec] = Field(default_factory=list)
    executable: bool | None = None
    unsupported_reason: str = ""

    @model_validator(mode="after")
    def validate_execution_support(self) -> "TestCaseSpec":
        if self.executable is False and not self.unsupported_reason:
            raise ValueError("unsupported_reason is required when executable is false")
        return self


class CoverageEvidence(ContractModel):
    target_id: str = Field(min_length=1)
    covered: bool
    method: Literal[
        "explicit_reference",
        "structured_match",
        "keyword_match",
        "semantic_match",
        "model_judgment",
        "none",
    ]
    confidence: float = Field(ge=0, le=1)
    case_ids: list[str] = Field(default_factory=list)
    test_point_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_covered_case_ids(self) -> "CoverageEvidence":
        if self.covered and not (self.case_ids or self.test_point_ids):
            raise ValueError(
                "case_ids or test_point_ids cannot both be empty when covered is true"
            )
        return self


class CoverageGap(ContractModel):
    gap_id: str = Field(min_length=1)
    gap_type: GapType
    target_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    business_type: BusinessType = BusinessType.UNKNOWN
    priority: Literal["low", "medium", "high"] = "medium"
    suggested_test_point: str = ""


class CoverageSummary(ContractModel):
    total: int = Field(ge=0)
    covered: int = Field(ge=0)
    coverage_rate: float = Field(ge=0, le=100)
    missing_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> "CoverageSummary":
        if self.covered > self.total:
            raise ValueError("covered cannot be greater than total")

        expected_rate = round(self.covered / self.total * 100, 2) if self.total else 0
        if abs(self.coverage_rate - expected_rate) > 0.01:
            raise ValueError(
                f"coverage_rate must match covered/total ({expected_rate})"
            )
        return self


class CoverageMatrix(ContractModel):
    requirement_coverage: CoverageSummary
    parameter_coverage: CoverageSummary
    risk_coverage: CoverageSummary
    evidence: list[CoverageEvidence] = Field(default_factory=list)
    gaps: list[CoverageGap] = Field(default_factory=list)
