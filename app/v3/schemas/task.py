from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"


class TaskCreateRequest(BaseModel):
    requirement: str = Field(
        min_length=1,
        max_length=10_000,
    )
    model_mode: Literal["api", "rule"] = "api"

    @field_validator("requirement")
    @classmethod
    def normalize_requirement(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("requirement 不能为空")

        return normalized


class TaskAcceptedResponse(BaseModel):
    task_id: str
    status: TaskStatus
    status_url: str
    events_url: str


class TaskSnapshot(BaseModel):
    task_id: str
    requirement: str
    model_mode: Literal["api", "rule"]

    status: TaskStatus
    current_node: str | None = None
    progress: int = Field(default=0, ge=0, le=100)

    result: dict[str, Any] | None = None
    error_message: str | None = None

    created_at: datetime
    updated_at: datetime