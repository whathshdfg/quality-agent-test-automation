import sqlite3

from app.db.run_repository import RunRepository


def test_run_repository_crud_uses_sqlite_rows(tmp_path):
    repository = RunRepository(tmp_path / "runs.db")

    run_id = repository.create_run("pay order twice", run_id="run_sql_001")
    repository.complete_run(
        run_id=run_id,
        metrics={
            "test_case_count": 3,
            "passed_cases": 2,
            "failed_cases": 1,
            "pass_rate": 66.67,
            "requirement_coverage_rate": 90,
            "enhancement_count": 1,
            "bug_count": 1,
        },
        trace=[{"node_name": "report"}],
        report="# report",
        rag_docs=2,
    )

    run = repository.get_run(run_id)
    assert run["run_id"] == "run_sql_001"
    assert run["status"] == "completed"
    assert run["total_cases"] == 3
    assert run["coverage_rate"] == 90
    assert run["rag_docs"] == 2
    assert run["metrics"]["test_case_count"] == 3
    assert run["trace"][0]["node_name"] == "report"

    rows = repository.list_runs(status="completed")
    assert [row["run_id"] for row in rows] == ["run_sql_001"]
    assert repository.latest_run()["run_id"] == "run_sql_001"
    assert repository.delete_run(run_id) is True
    assert repository.get_run(run_id) is None


def test_run_repository_parameterizes_lookup_values(tmp_path):
    repository = RunRepository(tmp_path / "runs.db")
    repository.create_run("safe run", run_id="run_safe")

    malicious_id = "run_safe' OR '1'='1"
    assert repository.get_run(malicious_id) is None

    with sqlite3.connect(tmp_path / "runs.db") as connection:
        count = connection.execute("SELECT COUNT(*) FROM agent_runs").fetchone()[0]
    assert count == 1
