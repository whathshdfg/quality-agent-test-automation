from fastapi.testclient import TestClient

from app.api_server import app
from app.mock_business_api import reset_mock_db


client = TestClient(app)


def setup_function():
    reset_mock_db()


def test_create_order_success():
    response = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": False,
        },
    )
    body = response.json()
    assert body["code"] == 0
    assert body["order_id"]
    assert body["order_status"] == "waiting"


def test_create_order_param_error():
    response = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "",
            "end_location": "B",
            "assign_driver": False,
        },
    )
    body = response.json()
    assert body["code"] == 400
    assert body["message"] == "PARAM_ERROR"


def test_create_order_same_location_rejected():
    response = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "A",
            "assign_driver": False,
        },
    )
    body = response.json()
    assert body["code"] == 400
    assert body["message"] == "SAME_LOCATION"


def test_repeat_create_order_rejected():
    payload = {
        "user_id": "user_001",
        "start_location": "A",
        "end_location": "B",
        "assign_driver": False,
    }
    first = client.post("/mock/order/create", json=payload).json()
    second = client.post("/mock/order/create", json=payload).json()
    assert first["code"] == 0
    assert second["code"] == 409
    assert second["message"] == "DUPLICATE_ORDER"


def test_cancel_waiting_order_success():
    order = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": False,
        },
    ).json()
    cancel = client.post(
        "/mock/order/cancel",
        json={
            "user_id": "user_001",
            "order_id": order["order_id"],
            "cancel_reason": "user_cancel",
        },
    ).json()
    queried = client.get(f"/mock/order/{order['order_id']}").json()
    assert cancel["code"] == 0
    assert queried["order"]["order_status"] == "cancelled"


def test_cancel_accepted_order_requires_reason():
    order = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": True,
        },
    ).json()
    cancel = client.post(
        "/mock/order/cancel",
        json={
            "user_id": "user_001",
            "order_id": order["order_id"],
            "cancel_reason": None,
        },
    ).json()
    assert cancel["code"] == 400
    assert cancel["message"] == "CANCEL_REASON_REQUIRED"


def test_cancel_accepted_order_releases_driver():
    order = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": True,
        },
    ).json()
    cancel = client.post(
        "/mock/order/cancel",
        json={
            "user_id": "user_001",
            "order_id": order["order_id"],
            "cancel_reason": "resource_release_test",
        },
    ).json()
    driver = client.get(f"/mock/driver/{order['driver_id']}").json()
    assert cancel["code"] == 0
    assert driver["driver"]["driver_status"] == "available"


def test_list_user_orders_contains_created_order():
    order = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": False,
        },
    ).json()
    listed = client.get("/mock/orders/user/user_001").json()
    assert listed["code"] == 0
    assert [item["order_id"] for item in listed["orders"]] == [order["order_id"]]


def test_timeout_cancel_waiting_order():
    order = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": False,
        },
    ).json()
    timeout = client.post("/mock/order/timeout_cancel", json={"order_id": order["order_id"]}).json()
    assert timeout["code"] == 0
    assert timeout["order_status"] == "cancelled"
    assert timeout["cancel_reason"] == "timeout_no_driver"


def test_pay_order_success():
    order = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": False,
        },
    ).json()
    pay = client.post(
        "/mock/payment/pay",
        json={"user_id": "user_001", "order_id": order["order_id"], "amount": 30.0},
    ).json()
    assert pay["code"] == 0
    assert pay["payment_status"] == "paid"
    assert pay["order_status"] == "paid"


def test_repeat_payment_rejected():
    order = client.post(
        "/mock/order/create",
        json={
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": False,
        },
    ).json()
    first = client.post(
        "/mock/payment/pay",
        json={"user_id": "user_001", "order_id": order["order_id"], "amount": 30.0},
    ).json()
    second = client.post(
        "/mock/payment/pay",
        json={"user_id": "user_001", "order_id": order["order_id"], "amount": 30.0},
    ).json()
    assert first["code"] == 0
    assert second["code"] == 409
    assert second["message"] == "REPEAT_PAYMENT"
