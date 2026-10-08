from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class TaskEventType(str, Enum):
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    NODE_STARTED = "node.started"
    NODE_COMPLETED = "node.completed"
    NODE_FAILED = "node.failed"

class TaskEvent(BaseModel):
    event_id: int
    task_id: str
    event_type: TaskEventType
    node_name: str | None = None
    payload: dict[str, Any]
    created_at: datetime


class TaskEventListResponse(BaseModel):
    events: list[TaskEvent]
    next_after_id: int