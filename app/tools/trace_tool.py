#执行链路追踪工具
import json
import os
from datetime import datetime
from typing import Any


def add_trace(
    state: dict,
    node_name: str,
    action: str,
    status: str = "success",
    detail: dict[str, Any] | None = None
) -> dict:
    """
    记录 Agent 每个节点的执行过程。
    """

    if "trace" not in state or state["trace"] is None:
        state["trace"] = []

    state["trace"].append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "node_name": node_name,
        "action": action,
        "status": status,
        "detail": detail or {}
    })

    return state


def save_trace(
    trace: list[dict],
    file_path: str = "app/outputs/execution_trace.json"
) -> None:
    """
    保存 Agent 执行链路到 JSON 文件。
    """

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, indent=2)