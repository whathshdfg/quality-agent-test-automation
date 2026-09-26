import json

from fastapi import APIRouter

from app.core.config import METRICS_FILE, REPORT_FILE, TRACE_FILE
from app.agent_graph_v2 import run_agent_v2
from app.schemas.agent import AgentRunRequest, AgentRunResponse
from app.services.agent_runner import execute_agent


router = APIRouter(tags=["Agent"])


@router.post("/agent/run", response_model=AgentRunResponse)
def run_quality_agent(request: AgentRunRequest):
    state = execute_agent(
        request.requirement,
        model_mode=request.model_mode,
    )
    return {
        "status": "success",
        "run_id": state["run_id"],
        "report": state["report"],
    }


@router.get("/agent/metrics")
def get_metrics_report():
    if not METRICS_FILE.exists():
        return {
            "status": "not_found",
            "message": "No metrics report has been generated yet.",
        }
    return {
        "status": "success",
        "metrics": json.loads(METRICS_FILE.read_text(encoding="utf-8")),
    }


@router.get("/agent/trace")
def get_execution_trace():
    if not TRACE_FILE.exists():
        return {
            "status": "not_found",
            "message": "No execution trace has been generated yet.",
        }
    return {
        "status": "success",
        "trace": json.loads(TRACE_FILE.read_text(encoding="utf-8")),
    }


@router.get("/agent/report")
def get_latest_report():
    if not REPORT_FILE.exists():
        return {
            "status": "not_found",
            "message": "No test report has been generated yet.",
        }
    return {
        "status": "success",
        "report": REPORT_FILE.read_text(encoding="utf-8"),
    }


@router.post("/agent/v2/run")
def run_quality_agent_v2(request: AgentRunRequest):
    state = run_agent_v2(
        request.requirement,
        model_mode=request.model_mode,
        persist_outputs=True,
    )
    return {
        "status": "success",
        "run_id": state["run_id"],
        "report": state["report"],
        "metrics": state["metrics"],
        "requirement_rules": state["requirement_rules"],
        "test_points": state["test_points"],
        "coverage_matrix": state["coverage_matrix"],
        "test_cases": state["test_cases"],
        "test_results": state["test_results"],
        "bug_analysis": state["bug_analysis"],
        "unsupported_test_points": state["unsupported_test_points"],
        "trace": state["trace"],
    }


@router.get("/agent/v2/metrics")
def get_v2_metrics_report():
    return get_metrics_report()


@router.get("/agent/v2/trace")
def get_v2_execution_trace():
    return get_execution_trace()


@router.get("/agent/v2/report")
def get_v2_latest_report():
    return get_latest_report()
