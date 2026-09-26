import json

from app.tool_agent.agent_loop import dispatch_tool_call
from app.tool_agent.registry import TOOL_REGISTRY
from app.tool_agent.schemas import TOOL_SCHEMAS


def _tool_call(name: str, arguments: dict) -> dict:
    return {
        "function": {
            "name": name,
            "arguments": json.dumps(arguments),
        }
    }


def test_history_tool_dispatch_uses_get_run_history(monkeypatch):
    called = {}

    def fake_history(limit=10, status=None):
        called["tool"] = "get_run_history"
        called["limit"] = limit
        called["status"] = status
        return {"success": True, "runs": []}

    monkeypatch.setitem(TOOL_REGISTRY, "get_run_history", fake_history)

    result = dispatch_tool_call(_tool_call("get_run_history", {"limit": 5}))

    assert result == {"success": True, "runs": []}
    assert called == {
        "tool": "get_run_history",
        "limit": 5,
        "status": None,
    }


def test_run_id_detail_tool_dispatch_uses_get_run_detail(monkeypatch):
    called = {}

    def fake_detail(run_id):
        called["tool"] = "get_run_detail"
        called["run_id"] = run_id
        return {"success": True, "run": {"run_id": run_id}}

    monkeypatch.setitem(TOOL_REGISTRY, "get_run_detail", fake_detail)

    result = dispatch_tool_call(
        _tool_call("get_run_detail", {"run_id": "run_abc"})
    )

    assert result["run"]["run_id"] == "run_abc"
    assert called == {
        "tool": "get_run_detail",
        "run_id": "run_abc",
    }


def test_single_run_tools_do_not_claim_history_intent():
    snapshot_tool_names = {"get_metrics", "get_trace", "get_report"}
    descriptions = {
        item["function"]["name"]: item["function"]["description"]
        for item in TOOL_SCHEMAS
    }

    for name in snapshot_tool_names:
        lowered = descriptions[name].lower()
        assert "current" in lowered
        assert "snapshot" in lowered

    assert "history" in descriptions["get_run_history"].lower()
    assert "do not combine get_metrics" in descriptions["get_run_history"]
    assert "run_id" in descriptions["get_run_detail"]
