from typing import Any

from pydantic import BaseModel


class RunSummary(BaseModel):
    run_id: str
    requirement: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float
    coverage_rate: float
    retry_count: int
    rag_docs: int
    bug_count: int
    created_at: str
    updated_at: str


class RunDetail(RunSummary):
    metrics: dict[str, Any]
    trace: list[dict[str, Any]]
    report: str
    error_message: str | None = None


class RunListResponse(BaseModel):
    runs: list[RunSummary]
