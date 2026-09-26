from typing import Literal

from pydantic import BaseModel


class AgentRunRequest(BaseModel):
    requirement: str
    model_mode: Literal["api", "rule"] = "api"


class AgentRunResponse(BaseModel):
    status: str
    run_id: str
    report: str
