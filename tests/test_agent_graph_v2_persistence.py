import pytest

import app.agent_graph_v2 as agent_graph_v2
from app.db.run_repository import RunRepository


class SuccessfulGraph:
    def invoke(self, state, config):
        return {
            **state,
            "rag_context": [{"source": "doc"}],
            "metrics": {
                "test_case_count": 2,
                "passed_cases": 2,
                "failed_cases": 0,
                "pass_rate": 100,
                "requirement_coverage_rate": 100,
            },
            "trace": [{"node_name": "report"}],
            "report": "# persisted",
        }


class FailingGraph:
    def invoke(self, state, config):
        raise RuntimeError("graph failed")


def test_run_agent_v2_persists_completed_history(tmp_path, monkeypatch):
    repository = RunRepository(tmp_path / "runs.db")
    monkeypatch.setattr(
        agent_graph_v2,
        "build_agent_graph_v2",
        lambda operation_runner, checkpointer: SuccessfulGraph(),
    )

    state = agent_graph_v2.run_agent_v2(
        "persist this run",
        model_mode="rule",
        persist_outputs=False,
        persist_history=True,
        run_id="run_persist_001",
        repository=repository,
    )

    persisted = repository.get_run("run_persist_001")
    assert state["run_id"] == "run_persist_001"
    assert persisted["status"] == "completed"
    assert persisted["total_cases"] == 2
    assert persisted["rag_docs"] == 1
    assert persisted["report"] == "# persisted"


def test_run_agent_v2_marks_failed_history(tmp_path, monkeypatch):
    repository = RunRepository(tmp_path / "runs.db")
    monkeypatch.setattr(
        agent_graph_v2,
        "build_agent_graph_v2",
        lambda operation_runner, checkpointer: FailingGraph(),
    )

    with pytest.raises(RuntimeError, match="graph failed"):
        agent_graph_v2.run_agent_v2(
            "persist failed run",
            model_mode="rule",
            persist_outputs=False,
            persist_history=True,
            run_id="run_failed_001",
            repository=repository,
        )

    persisted = repository.get_run("run_failed_001")
    assert persisted["status"] == "failed"
    assert persisted["error_message"] == "graph failed"
