import json
from pathlib import Path


# app/outputs
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"


def get_metrics() -> dict:
    """
    读取最近一次 V2 Agent 指标。
    """
    path = OUTPUT_DIR / "v2_metrics_report.json"

    if not path.exists():
        return {
            "success": False,
            "error": "v2_metrics_report.json 不存在"
        }

    with open(path, "r", encoding="utf-8") as file:
        metrics = json.load(file)

    return {
        "success": True,
        "metrics": metrics
    }


def get_trace() -> dict:
    """
    读取最近一次 V2 Agent 执行链路。
    """
    path = OUTPUT_DIR / "v2_execution_trace.json"

    if not path.exists():
        return {
            "success": False,
            "error": "v2_execution_trace.json 不存在"
        }

    with open(path, "r", encoding="utf-8") as file:
        trace = json.load(file)

    return {
        "success": True,
        "trace": trace
    }


def get_report() -> dict:
    """
    读取最近一次 V2 Agent 测试报告。
    """
    path = OUTPUT_DIR / "v2_test_report.md"

    if not path.exists():
        return {
            "success": False,
            "error": "v2_test_report.md 不存在"
        }

    report = path.read_text(encoding="utf-8")

    return {
        "success": True,
        "report": report
    }


TOOL_REGISTRY = {
    "get_metrics": get_metrics,
    "get_trace": get_trace,
    "get_report": get_report,
}


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": (
                "读取最近一次测试智能化 Agent 的指标，"
                "例如测试用例数量、通过率、失败数量和覆盖率。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace",
            "description": (
                "读取最近一次测试智能化 Agent 的执行链路，"
                "用于查询执行过哪些节点、节点顺序和状态。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_report",
            "description": (
                "读取最近一次测试智能化 Agent 的完整测试报告，"
                "包括需求规则、测试点、覆盖矩阵、"
                "执行结果和失败分析。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]