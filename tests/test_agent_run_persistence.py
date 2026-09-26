import pytest
from fastapi.testclient import TestClient

from app.db.run_repository import RunRepository
from app.main import app
from app.services.agent_runner import execute_agent
import app.api.routes.agent as agent_routes


client = TestClient(app)


def test_execute_agent_persists_real_final_state(tmp_path):
    repository = RunRepository(tmp_path / "runs.db")
    calls = {"count": 0}

    def fake_workflow(requirement, model_mode, persist_outputs, persist_history, run_id):
        calls["count"] += 1
        return {
            "run_id": run_id,
            "requirement": requirement,
            "rag_context": [{"source": "api_spec.md"}],
            "metrics": {
                "run_id": run_id,
                "total_cases": 12,
                "passed_cases": 7,
                "failed_cases": 5,
                "pass_rate": 58.33,
                "coverage_rate": 100.0,
                "retry_count": 1,
                "bug_count": 5,
            },
            "trace": [{"run_id": run_id, "node_name": "report"}],
            "report": f"# real report\n\nrun_id: {run_id}",
        }

    state = execute_agent(
        "Chinese requirement: pay twice",
        model_mode="rule",
        repository=repository,
        workflow=fake_workflow,
    )

    assert calls["count"] == 1
    run = repository.get_run(state["run_id"])
    assert run["requirement"] == "Chinese requirement: pay twice"
    assert run["status"] == "completed"
    assert run["total_cases"] == 12
    assert run["passed_cases"] == 7
    assert run["failed_cases"] == 5
    assert run["pass_rate"] == 58.33
    assert run["coverage_rate"] == 100.0
    assert run["retry_count"] == 1
    assert run["rag_docs"] == 1
    assert run["bug_count"] == 5
    assert run["metrics"]["run_id"] == state["run_id"]
    assert run["trace"][0]["run_id"] == state["run_id"]
    assert state["run_id"] in run["report"]


def test_execute_agent_marks_failed_and_reraises(tmp_path):
    repository = RunRepository(tmp_path / "runs.db")

    def fake_workflow(*_args, **_kwargs):
        raise RuntimeError("workflow exploded")

    with pytest.raises(RuntimeError, match="workflow exploded"):
        execute_agent(
            "failing requirement",
            model_mode="rule",
            repository=repository,
            workflow=fake_workflow,
        )

    runs = repository.list_runs()
    assert len(runs) == 1
    detail = repository.get_run(runs[0]["run_id"])
    assert detail["status"] == "failed"
    assert detail["error_message"] == "workflow exploded"


def test_agent_run_api_returns_run_id(monkeypatch):
    def fake_execute_agent(requirement, model_mode):
        return {
            "run_id": "run_api_response_001",
            "requirement": requirement,
            "model_mode": model_mode,
            "report": "# API report",
        }

    monkeypatch.setattr(agent_routes, "execute_agent", fake_execute_agent)
    response = client.post(
        "/agent/run",
        json={"requirement": "pay twice", "model_mode": "rule"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "run_id": "run_api_response_001",
        "report": "# API report",
    }
