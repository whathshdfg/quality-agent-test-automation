from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from app.agent_graph_v2 import (
    build_agent_graph_v2,
    initial_v2_state,
)
from app.v3.schemas.event import TaskEventType


NodeEventSink = Callable[
    [
        TaskEventType,
        str,
        dict[str, Any],
    ],
    None,
]


class StreamGraph(Protocol):
    def stream(
        self,
        input: dict[str, Any],
        config: dict[str, Any],
        *,
        stream_mode: list[str],
    ):
        ...


GraphFactory = Callable[..., StreamGraph]


def run_v3_workflow(
    requirement: str,
    model_mode: str = "api",
    operation_runner=None,
    persist_outputs: bool = False,
    persist_history: bool = False,
    run_id: str | None = None,
    node_event_sink: NodeEventSink | None = None,
    graph_factory: GraphFactory = build_agent_graph_v2,
) -> dict[str, Any]:
    """
    运行 V2 LangGraph，并把真实节点执行过程转换为 V3 节点事件。

    tasks 流提供节点开始和结束事件；
    values 流提供每一步执行后的完整状态。
    """
    if persist_history:
        raise ValueError(
            "V3 workflow runner 不负责写入 V2 运行历史"
        )

    state = initial_v2_state(
        requirement=requirement,
        model_mode=model_mode,
        run_id=run_id,
    )
    state["persist_outputs"] = persist_outputs

    graph = graph_factory(
        operation_runner=operation_runner,
        checkpointer=None,
    )

    config = {
        "configurable": {
            "thread_id": state["run_id"],
        }
    }

    final_state: dict[str, Any] | None = None

    for stream_mode, data in graph.stream(
        state,
        config=config,
        stream_mode=["tasks", "values"],
    ):
        if stream_mode == "values":
            final_state = data
            continue

        if stream_mode != "tasks":
            continue

        node_name = str(data.get("name", ""))
        task_run_id = str(data.get("id", ""))

        if not node_name:
            continue

        if "input" in data:
            if node_event_sink is not None:
                node_event_sink(
                    TaskEventType.NODE_STARTED,
                    node_name,
                    {
                        "task_run_id": task_run_id,
                    },
                )
            continue

        if "result" in data:
            error = data.get("error")

            if error is None and node_event_sink is not None:
                node_event_sink(
                    TaskEventType.NODE_COMPLETED,
                    node_name,
                    {
                        "task_run_id": task_run_id,
                    },
                )

    if final_state is None:
        raise RuntimeError(
            "LangGraph 执行结束，但没有返回最终状态"
        )

    return final_state