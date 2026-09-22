from fastapi.testclient import TestClient

import app.api_server as api_server


client = TestClient(api_server.app)


def fake_state():
    return {
        "run_id": "run_test_001",
        "report": "# V2 report",
        "metrics": {"test_case_count": 1, "passed_cases": 1},
        "requirement_rules": [{"rule_id": "REQ_001"}],
        "test_points": [{"test_point_id": "TP_001"}],
        "coverage_matrix": {"requirement_coverage": {"coverage_rate": 100}},
        "test_cases": [{"case_id": "TC_001"}],
        "test_results": [{"case_id": "TC_001", "status": "passed"}],
        "bug_analysis": [],
        "unsupported_test_points": [],
        "trace": [{"node_name": "report"}],
    }


def test_v2_run_endpoint_returns_structured_result(monkeypatch):
    captured = {}

    def fake_run(requirement, model_mode, persist_outputs):
        captured.update({
            "requirement": requirement,
            "model_mode": model_mode,
            "persist_outputs": persist_outputs,
        })
        return fake_state()

    monkeypatch.setattr(api_server, "run_agent_v2", fake_run)
    response = client.post(
        "/agent/v2/run",
        json={"requirement": "测试重复支付", "model_mode": "rule"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["run_id"] == "run_test_001"
    assert data["metrics"]["passed_cases"] == 1
    assert data["requirement_rules"][0]["rule_id"] == "REQ_001"
    assert captured == {
        "requirement": "测试重复支付",
        "model_mode": "rule",
        "persist_outputs": True,
    }


def test_v2_run_endpoint_rejects_invalid_model_mode():
    response = client.post(
        "/agent/v2/run",
        json={"requirement": "测试支付", "model_mode": "local"},
    )

    assert response.status_code == 422


def test_v2_output_endpoints_read_saved_files(tmp_path, monkeypatch):
    output_dir = tmp_path / "app" / "outputs"
    output_dir.mkdir(parents=True)
    (output_dir / "v2_metrics_report.json").write_text(
        '{"passed_cases": 2}', encoding="utf-8"
    )
    (output_dir / "v2_execution_trace.json").write_text(
        '[{"node_name": "report"}]', encoding="utf-8"
    )
    (output_dir / "v2_test_report.md").write_text(
        "# saved report", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    metrics = client.get("/agent/v2/metrics").json()
    trace = client.get("/agent/v2/trace").json()
    report = client.get("/agent/v2/report").json()

    assert metrics["metrics"]["passed_cases"] == 2
    assert trace["trace"][0]["node_name"] == "report"
    assert report["report"] == "# saved report"
