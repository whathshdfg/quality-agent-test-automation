from app.db.run_repository import RunRepository
import app.tool_agent.tools as tools
import app.tool_agent.run_history_tools as run_history_tools


def test_tool_agent_can_query_sqlite_run_history(tmp_path, monkeypatch):
    repository = RunRepository(tmp_path / "runs.db")
    run_id = repository.create_run("tool query", run_id="run_tool_001")
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
        report="# tool report",
    )
    monkeypatch.setattr(run_history_tools, "RunRepository", lambda: repository)

    listed = tools.get_run_history(limit=5)
    detail = tools.get_run_detail("run_tool_001")
    latest = tools.get_latest_agent_run()

    assert listed["success"] is True
    assert listed["runs"][0]["run_id"] == "run_tool_001"
    assert detail["run"]["metrics"]["passed_cases"] == 1
    assert latest["run"]["report"] == "# tool report"
    assert "get_run_history" in tools.TOOL_REGISTRY
    assert "get_run_detail" in tools.TOOL_REGISTRY
    assert any(
        item["function"]["name"] == "get_run_history"
        for item in tools.TOOLS
    )
    assert any(
        item["function"]["name"] == "get_run_detail"
        for item in tools.TOOLS
    )


def test_tool_agent_returns_not_found_for_missing_run(tmp_path, monkeypatch):
    repository = RunRepository(tmp_path / "runs.db")
    monkeypatch.setattr(run_history_tools, "RunRepository", lambda: repository)

    result = tools.get_run_detail("missing")

    assert result["success"] is False
    assert "missing" in result["error"]


def test_tool_registry_and_schema_are_in_sync():
    registry_names = set(tools.TOOL_REGISTRY)
    schema_names = {item["function"]["name"] for item in tools.TOOLS}

    assert registry_names == {
        "get_metrics",
        "get_trace",
        "get_report",
        "get_run_history",
        "get_run_detail",
    }
    assert schema_names == registry_names
