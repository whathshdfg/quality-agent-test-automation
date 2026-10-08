from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from app.agent_graph_v2 import (
    build_agent_graph_v2,
    initial_v2_state,
)
from app.v3.schemas.event import TaskEventType
import pytest

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

        if "result" not in data:
            continue

        error = data.get("error")

        if node_event_sink is None:
            continue

        if error is None:
            node_event_sink(
                TaskEventType.NODE_COMPLETED,
                node_name,
                {
                    "task_run_id": task_run_id,
                },
            )
        else:
            node_event_sink(
                TaskEventType.NODE_FAILED,
                node_name,
                {
                    "task_run_id": task_run_id,
                    "error": str(error)[:2000],
                },
            )

    if final_state is None:
        raise RuntimeError(
            "LangGraph 执行结束，但没有返回最终状态"
        )

    return final_state

class FakeFailingStreamGraph:
    def stream(
        self,
        input,
        config,
        *,
        stream_mode,
    ):
        yield (
            "tasks",
            {
                "id": "node_run_failed_001",
                "name": "execute_tests",
                "input": input,
                "triggers": [
                    "start:execute_tests"
                ],
            },
        )

        yield (
            "tasks",
            {
                "id": "node_run_failed_001",
                "name": "execute_tests",
                "error": "HTTP connection failed",
                "interrupts": [],
                "result": None,
            },
        )

        raise RuntimeError(
            "HTTP connection failed"
        )


def test_run_v3_workflow_emits_node_failed_before_raising():
    graph = FakeFailingStreamGraph()
    recorded_events = []

    def fake_graph_factory(
        operation_runner=None,
        checkpointer=None,
    ):
        return graph

    def record_event(
        event_type,
        node_name,
        payload,
    ):
        recorded_events.append(
            (
                event_type,
                node_name,
                payload,
            )
        )

    with pytest.raises(
        RuntimeError,
        match="HTTP connection failed",
    ):
        run_v3_workflow(
            requirement="测试支付接口异常",
            model_mode="rule",
            run_id="task_failed_001",
            node_event_sink=record_event,
            graph_factory=fake_graph_factory,
        )

    assert recorded_events == [
        (
            TaskEventType.NODE_STARTED,
            "execute_tests",
            {
                "task_run_id": (
                    "node_run_failed_001"
                ),
            },
        ),
        (
            TaskEventType.NODE_FAILED,
            "execute_tests",
            {
                "task_run_id": (
                    "node_run_failed_001"
                ),
                "error": (
                    "HTTP connection failed"
                ),
            },
        ),
    ]