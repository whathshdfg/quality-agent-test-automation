#模拟业务接口文件
from fastapi import APIRouter
from pydantic import BaseModel
from uuid import uuid4


router = APIRouter(prefix="/mock", tags=["Mock Business API"])


MOCK_DB = {
    "orders": {},
    "drivers": {
        "driver_001": {
            "driver_id": "driver_001",
            "driver_status": "available"
        }
    }
}


class CreateOrderRequest(BaseModel):
    user_id: str
    start_location: str | None = None
    end_location: str | None = None
    assign_driver: bool = False


class CancelOrderRequest(BaseModel):
    user_id: str
    order_id: str
    cancel_reason: str | None = None


class TimeoutCancelRequest(BaseModel):
    order_id: str


class PayRequest(BaseModel):
    user_id: str
    order_id: str
    amount: float


def reset_mock_db():
    MOCK_DB["orders"] = {}
    MOCK_DB["drivers"] = {
        "driver_001": {
            "driver_id": "driver_001",
            "driver_status": "available"
        }
    }


@router.post("/reset")
def reset():
    reset_mock_db()
    return {
        "code": 0,
        "message": "mock database reset success"
    }


@router.post("/order/create")
def create_order(request: CreateOrderRequest):
    if not request.start_location or not request.end_location:
        return {
            "code": 400,
            "message": "PARAM_ERROR",
            "order_id": None
        }

    for order in MOCK_DB["orders"].values():
        if (
            order["user_id"] == request.user_id
            and order["order_status"] in ["waiting", "accepted", "running", "unpaid"]
        ):
            return {
                "code": 409,
                "message": "DUPLICATE_ORDER",
                "order_id": None
            }

    order_id = "order_" + str(uuid4())[:8]
    driver_id = "driver_001" if request.assign_driver else None

    order_status = "accepted" if request.assign_driver else "waiting"

    if request.assign_driver:
        MOCK_DB["drivers"]["driver_001"]["driver_status"] = "assigned"

    MOCK_DB["orders"][order_id] = {
        "order_id": order_id,
        "user_id": request.user_id,
        "start_location": request.start_location,
        "end_location": request.end_location,
        "order_status": order_status,
        "driver_id": driver_id,
        "cancel_reason": None,
        "payment_status": "unpaid"
    }

    return {
        "code": 0,
        "message": "CREATE_ORDER_SUCCESS",
        "order_id": order_id,
        "order_status": order_status,
        "driver_id": driver_id
    }


@router.post("/order/cancel")
def cancel_order(request: CancelOrderRequest):
    order = MOCK_DB["orders"].get(request.order_id)

    if not order:
        return {
            "code": 404,
            "message": "ORDER_NOT_FOUND"
        }

    if order["order_status"] == "cancelled":
        return {
            "code": 409,
            "message": "REPEAT_CANCEL",
            "order_status": "cancelled"
        }

    if order["order_status"] == "accepted" and not request.cancel_reason:
        return {
            "code": 400,
            "message": "CANCEL_REASON_REQUIRED"
        }

    order["order_status"] = "cancelled"
    order["cancel_reason"] = request.cancel_reason

    # 注意：这里故意保留一个 Bug
    # 正确逻辑应该是：如果订单绑定了 driver_id，取消订单后应释放司机资源。
    # 但这里没有释放 driver_status，所以后面的 TC_CANCEL_004 会失败。
    # 这正好用于演示 Agent 的缺陷发现能力。

    return {
        "code": 0,
        "message": "CANCEL_ORDER_SUCCESS",
        "order_status": order["order_status"],
        "cancel_reason": order["cancel_reason"]
    }


@router.post("/order/timeout_cancel")
def timeout_cancel_order(request: TimeoutCancelRequest):
    order = MOCK_DB["orders"].get(request.order_id)

    if not order:
        return {
            "code": 404,
            "message": "ORDER_NOT_FOUND"
        }

    if order["order_status"] != "waiting":
        return {
            "code": 400,
            "message": "ORDER_STATUS_NOT_WAITING",
            "order_status": order["order_status"]
        }

    order["order_status"] = "cancelled"
    order["cancel_reason"] = "timeout_no_driver"

    return {
        "code": 0,
        "message": "TIMEOUT_CANCEL_SUCCESS",
        "order_status": "cancelled",
        "cancel_reason": "timeout_no_driver"
    }


@router.get("/order/{order_id}")
def get_order(order_id: str):
    order = MOCK_DB["orders"].get(order_id)

    if not order:
        return {
            "code": 404,
            "message": "ORDER_NOT_FOUND",
            "order": None
        }

    return {
        "code": 0,
        "message": "SUCCESS",
        "order": order
    }


@router.get("/driver/{driver_id}")
def get_driver(driver_id: str):
    driver = MOCK_DB["drivers"].get(driver_id)

    if not driver:
        return {
            "code": 404,
            "message": "DRIVER_NOT_FOUND",
            "driver": None
        }

    return {
        "code": 0,
        "message": "SUCCESS",
        "driver": driver
    }


@router.post("/payment/pay")
def pay_order(request: PayRequest):
    order = MOCK_DB["orders"].get(request.order_id)

    if not order:
        return {
            "code": 404,
            "message": "ORDER_NOT_FOUND"
        }

    if request.amount <= 0:
        return {
            "code": 400,
            "message": "INVALID_AMOUNT"
        }

    if order["payment_status"] == "paid":
        return {
            "code": 409,
            "message": "REPEAT_PAYMENT",
            "payment_status": "paid"
        }

    order["payment_status"] = "paid"
    order["order_status"] = "paid"

    return {
        "code": 0,
        "message": "PAY_SUCCESS",
        "payment_status": "paid",
        "order_status": "paid"
    }