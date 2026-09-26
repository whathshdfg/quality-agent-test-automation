from app.tool_agent.artifact_tools import get_metrics, get_report, get_trace
from app.tool_agent.run_history_tools import get_run_detail, get_run_history


TOOL_REGISTRY = {
    "get_metrics": get_metrics,
    "get_trace": get_trace,
    "get_report": get_report,
    "get_run_history": get_run_history,
    "get_run_detail": get_run_detail,
}
