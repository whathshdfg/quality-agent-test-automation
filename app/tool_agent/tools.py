from app.tool_agent.artifact_tools import get_metrics, get_report, get_trace
from app.tool_agent.registry import TOOL_REGISTRY
from app.tool_agent.run_history_tools import get_run_detail, get_run_history
from app.tool_agent.schemas import TOOL_SCHEMAS


def list_agent_runs(limit: int = 10, status: str | None = None) -> dict:
    return get_run_history(limit=limit, status=status)


def get_agent_run(run_id: str) -> dict:
    return get_run_detail(run_id=run_id)


def get_latest_agent_run() -> dict:
    history = get_run_history(limit=1)
    if not history["runs"]:
        return {
            "success": False,
            "error": "agent run history is empty",
        }
    return get_run_detail(history["runs"][0]["run_id"])


TOOLS = TOOL_SCHEMAS

__all__ = [
    "get_metrics",
    "get_trace",
    "get_report",
    "get_run_history",
    "get_run_detail",
    "TOOL_REGISTRY",
    "TOOL_SCHEMAS",
    "TOOLS",
]
