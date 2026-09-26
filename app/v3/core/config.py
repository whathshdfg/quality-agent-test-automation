from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[3]

class V3Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    api_prefix: str = "/api/v3"
    service_name: str = "quality-agent-v3"
    version: str = "3.0.0"
    database_path: Path = (
        PROJECT_ROOT / "data" / "quality_agent_v3.db"
    )
    max_concurrent_jobs: int = Field(default=2, ge=1)
    task_timeout_seconds: int = Field(default=600, ge=1)

settings = V3Settings()