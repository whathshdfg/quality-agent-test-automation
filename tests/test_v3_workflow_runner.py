import pytest

from app.v3.schemas.event import TaskEventType
from app.v3.services.workflow_runner import (
    run_v3_workflow,
)


class FakeStreamGraph:
    def __init__(self):
        self.received_state = None
        self.received_config = None
        self.received_stream_mode = None

    def stream(
        self,
        input,
        config,
        *,
        stream_mode,
    ):
        self.received_state = input
        self.received_config = config
        self.received_stream_mode = stream_mode

        yield (
            "tasks",
            {
                "id": "node_run_001",
                "name": "retrieve",
                "input": input,
                "triggers": [
                    "start:retrieve"
                ],
            },
        )

        yield (
            "tasks",
            {
                "id": "node_run_001",
                "name": "retrieve",
                "error": None,
                "interrupts": [],
                "result": {
                    "rag_context": [],
                },
            },
        )

        final_state = {
            **input,
            "report": "# V3 测试报告",
            "metrics": {
                "total_cases": 1,
            },
        }

        yield (
            "values",
            final_state,
        )


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
                "error": (
                    "HTTP connection failed"
                ),
                "interrupts": [],
                "result": None,
            },
        )

        raise RuntimeError(
            "HTTP connection failed"
        )


def test_run_v3_workflow_converts_task_stream_to_node_events():
    graph = FakeStreamGraph()
    graph_factory_arguments = {}
    recorded_events = []

    def fake_graph_factory(
        operation_runner=None,
        checkpointer=None,
    ):
        graph_factory_arguments[
            "operation_runner"
        ] = operation_runner
        graph_factory_arguments[
            "checkpointer"
        ] = checkpointer
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

    final_state = run_v3_workflow(
        requirement="测试重复支付",
        model_mode="rule",
        run_id="task_test_001",
        node_event_sink=record_event,
        graph_factory=fake_graph_factory,
    )

    assert graph_factory_arguments == {
        "operation_runner": None,
        "checkpointer": None,
    }

    assert graph.received_state is not None
    assert (
        graph.received_state["run_id"]
        == "task_test_001"
    )
    assert (
        graph.received_state["requirement"]
        == "测试重复支付"
    )
    assert (
        graph.received_state["model_mode"]
        == "rule"
    )
    assert (
        graph.received_state[
            "persist_outputs"
        ]
        is False
    )

    assert graph.received_config == {
        "configurable": {
            "thread_id": "task_test_001",
        }
    }
    assert graph.received_stream_mode == [
        "tasks",
        "values",
    ]

    assert recorded_events == [
        (
            TaskEventType.NODE_STARTED,
            "retrieve",
            {
                "task_run_id": (
                    "node_run_001"
                ),
            },
        ),
        (
            TaskEventType.NODE_COMPLETED,
            "retrieve",
            {
                "task_run_id": (
                    "node_run_001"
                ),
            },
        ),
    ]

    assert (
        final_state["report"]
        == "# V3 测试报告"
    )
    assert final_state["metrics"] == {
        "total_cases": 1,
    }


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