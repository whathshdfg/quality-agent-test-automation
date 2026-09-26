from fastapi.testclient import TestClient

from app.main import app
from app.db.run_repository import RunRepository
import app.api.routes.runs as runs_route


client = TestClient(app)


def test_run_history_api_lists_gets_and_deletes_runs(tmp_path, monkeypatch):
    repository = RunRepository(tmp_path / "runs.db")
    run_id = repository.create_run("history requirement", run_id="run_api_001")
    repository.complete_run(
        run_id=run_id,
        metrics={
            "test_case_count": 1,
            "passed_cases": 1,
            "failed_cases": 0,
            "pass_rate": 100,
            "requirement_coverage_rate": 100,
        },
        trace=[{"node_name": "report"}],
        report="# API report",
    )
    monkeypatch.setattr(runs_route, "repository", repository)

    listed = client.get("/api/runs").json()
    assert listed["runs"][0]["run_id"] == "run_api_001"
    assert listed["runs"][0]["status"] == "completed"

    detail = client.get("/api/runs/run_api_001").json()
    assert detail["metrics"]["pass_rate"] == 100
    assert detail["trace"][0]["node_name"] == "report"
    assert detail["report"] == "# API report"

    deleted = client.delete("/api/runs/run_api_001").json()
    assert deleted == {"deleted": True, "run_id": "run_api_001"}
    assert client.get("/api/runs/run_api_001").status_code == 404
