#FastAPI 官方示例就是创建 FastAPI() 实例并定义接口路径；它适合把 Python 功能封装成 API 服务。
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.agent_graph import run_agent
from app.agent_graph_v2 import run_agent_v2
from app.mock_business_api import router as mock_router


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mock_router)


class AgentRequest(BaseModel):
    requirement: str


class AgentV2Request(BaseModel):
    requirement: str
    model_mode: Literal["api", "rule"] = "api"


@app.get("/")
def home():
    return {
        "message": "测试智能化 AI Agent 系统已启动"
    }


@app.post("/agent/run")
def run_quality_agent(request: AgentRequest):
    report = run_agent(request.requirement)

    with open("app/outputs/test_report.md", "w", encoding="utf-8") as f:
        f.write(report)

    return {
        "status": "success",
        "report": report
    }


@app.get("/agent/trace")
def get_execution_trace():
    path = Path("app/outputs/execution_trace.json")

    if not path.exists():
        return {
            "status": "not_found",
            "message": "还没有生成执行链路，请先运行 /agent/run"
        }

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "status": "success",
        "trace": data
    }


@app.get("/agent/metrics")
def get_metrics_report():
    path = Path("app/outputs/metrics_report.json")

    if not path.exists():
        return {
            "status": "not_found",
            "message": "还没有生成指标报告，请先运行 /agent/run"
        }

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {
        "status": "success",
        "metrics": data
    }


@app.get("/agent/report")
def get_latest_report():
    path = Path("app/outputs/test_report.md")

    if not path.exists():
        return {
            "status": "not_found",
            "message": "还没有生成测试报告，请先运行 /agent/run"
        }

    with open(path, "r", encoding="utf-8") as f:
        report = f.read()

    return {
        "status": "success",
        "report": report
    }


@app.post("/agent/v2/run")
def run_quality_agent_v2(request: AgentV2Request):
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


def _read_v2_json(file_name: str, result_key: str):
    path = Path("app/outputs") / file_name
    if not path.exists():
        return {
            "status": "not_found",
            "message": "还没有生成 V2 运行结果，请先运行 /agent/v2/run",
        }
    return {
        "status": "success",
        result_key: json.loads(path.read_text(encoding="utf-8")),
    }


@app.get("/agent/v2/trace")
def get_v2_execution_trace():
    return _read_v2_json("v2_execution_trace.json", "trace")


@app.get("/agent/v2/metrics")
def get_v2_metrics_report():
    return _read_v2_json("v2_metrics_report.json", "metrics")


@app.get("/agent/v2/report")
def get_v2_latest_report():
    path = Path("app/outputs/v2_test_report.md")
    if not path.exists():
        return {
            "status": "not_found",
            "message": "还没有生成 V2 测试报告，请先运行 /agent/v2/run",
        }
    return {
        "status": "success",
        "report": path.read_text(encoding="utf-8"),
    }
