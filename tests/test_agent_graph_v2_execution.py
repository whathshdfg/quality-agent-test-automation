from fastapi.testclient import TestClient

from app.agent_graph_v2 import run_agent_v2
from app.api_server import app


client = TestClient(app)


def runner(operation_name, arguments):
    if operation_name == "reset_mock_data":
        return client.post("/mock/reset").json()
    if operation_name == "create_order":
        return client.post("/mock/order/create", json={
            "user_id": "user_001",
            "start_location": arguments.get("start_location", "A"),
            "end_location": arguments.get("end_location", "B"),
            "assign_driver": arguments.get("assign_driver", False),
        }).json()
    if operation_name == "pay_order":
        return client.post("/mock/payment/pay", json={
            "user_id": "user_001",
            "order_id": arguments["order_id"],
            "amount": arguments.get("amount", 30),
        }).json()
    if operation_name == "get_order":
        return client.get(f"/mock/order/{arguments['order_id']}").json()
    if operation_name == "get_driver":
        return client.get(f"/mock/driver/{arguments.get('driver_id', 'driver_001')}").json()
    if operation_name == "list_user_orders":
        return client.get("/mock/orders/user/user_001").json()
    if operation_name == "cancel_order":
        return client.post("/mock/order/cancel", json={
            "user_id": "user_001",
            "order_id": arguments["order_id"],
            "cancel_reason": arguments.get("cancel_reason"),
        }).json()
    if operation_name == "timeout_cancel_order":
        return client.post("/mock/order/timeout_cancel", json={
            "order_id": arguments["order_id"],
        }).json()
    raise AssertionError(operation_name)


def test_full_v2_graph_executes_and_reports_in_rule_mode():
    state = run_agent_v2(
        "重复支付应返回 REPEAT_PAYMENT",
        model_mode="rule",
        operation_runner=runner,
        persist_outputs=False,
    )

    assert state["test_results"]
    assert state["run_id"].startswith("run_")
    assert state["metrics"]["run_id"] == state["run_id"]
    assert state["metrics"]["test_case_count"] == len(state["test_cases"])
    assert state["metrics"]["passed_cases"] == len(state["test_results"])
    assert state["metrics"]["failed_cases"] == 0
    assert "测试智能化 Agent V2 执行报告" in state["report"]
    assert state["bug_analysis"] == []
    assert [item["node_name"] for item in state["trace"]][-3:] == [
        "execute_tests",
        "analyze_failures",
        "report",
    ]
