import os

import requests


BASE_URL = os.getenv("MOCK_API_BASE_URL", "http://127.0.0.1:8000")
USER_ID = "user_001"
DRIVER_ID = "driver_001"


def call_api(method: str, path: str, json_data: dict | None = None) -> dict:
    """Send one HTTP request to the mock business API."""

    url = BASE_URL + path
    response = requests.request(
        method=method,
        url=url,
        json=json_data,
        timeout=5
    )
    return response.json()


def reset_mock_data():
    return call_api("POST", "/mock/reset")


def create_order(
    assign_driver: bool = False,
    start_location: str = "A",
    end_location: str = "B",
) -> dict:
    return call_api(
        "POST",
        "/mock/order/create",
        {
            "user_id": USER_ID,
            "start_location": start_location,
            "end_location": end_location,
            "assign_driver": assign_driver
        }
    )


def cancel_order(order_id: str, reason: str | None = "user_cancel") -> dict:
    return call_api(
        "POST",
        "/mock/order/cancel",
        {
            "user_id": USER_ID,
            "order_id": order_id,
            "cancel_reason": reason
        }
    )


def timeout_cancel_order(order_id: str) -> dict:
    return call_api("POST", "/mock/order/timeout_cancel", {"order_id": order_id})


def get_order(order_id: str) -> dict:
    return call_api("GET", f"/mock/order/{order_id}")


def list_user_orders(user_id: str = USER_ID) -> dict:
    return call_api("GET", f"/mock/orders/user/{user_id}")


def get_driver(driver_id: str = DRIVER_ID) -> dict:
    return call_api("GET", f"/mock/driver/{driver_id}")


def pay_order(order_id: str, amount: float = 30.0) -> dict:
    return call_api(
        "POST",
        "/mock/payment/pay",
        {
            "user_id": USER_ID,
            "order_id": order_id,
            "amount": amount
        }
    )


def build_pass_result(case: dict, actual_result: str = "") -> dict:
    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "status": "passed",
        "error_log": "",
        "actual_result": actual_result
    }


def build_fail_result(case: dict, error_log: str, actual_result: str = "") -> dict:
    return {
        "case_id": case["case_id"],
        "title": case["title"],
        "status": "failed",
        "error_log": error_log,
        "actual_result": actual_result
    }


def fail_unconfigured_case(case: dict, business_type: str) -> dict:
    return build_fail_result(
        case,
        error_log=f"未配置该测试用例的执行与断言逻辑，business_type={business_type}",
    )


def has_text(case: dict, *keywords: str) -> bool:
    text = "\n".join([
        case.get("case_id", ""),
        case.get("title", ""),
        case.get("precondition", ""),
        case.get("expected_result", ""),
        "\n".join(case.get("steps", [])),
    ])
    return any(keyword in text for keyword in keywords)


def assert_order_in_user_list(order: dict, orders: list[dict], fields: list[str]) -> bool:
    matched = next(
        (item for item in orders if item.get("order_id") == order.get("order_id")),
        None
    )
    if not matched:
        return False

    return all(matched.get(field) == order.get(field) for field in fields)


def run_cancel_case(case: dict) -> dict:
    """Execute order-cancel cases with concrete API calls and result checks."""

    case_id = case["case_id"]
    reset_mock_data()

    if case_id == "TC_CANCEL_001" or has_text(case, "用户主动取消", "正常场景"):
        create_resp = create_order(assign_driver=False)
        cancel_resp = cancel_order(create_resp["order_id"], reason="user_cancel")
        query_resp = get_order(create_resp["order_id"])
        order = query_resp["order"]

        if cancel_resp["code"] == 0 and order["order_status"] == "cancelled":
            return build_pass_result(case, actual_result=f"cancel_resp={cancel_resp}, order={order}")
        return build_fail_result(case, f"主动取消失败：cancel_resp={cancel_resp}, order={order}", str(order))

    if has_text(case, "不存在", "ORDER_NOT_FOUND"):
        cancel_resp = cancel_order("order_not_exists", reason="not_found_test")
        if cancel_resp["code"] == 404 and cancel_resp["message"] == "ORDER_NOT_FOUND":
            return build_pass_result(case, actual_result=f"cancel_resp={cancel_resp}")
        return build_fail_result(case, f"不存在订单未正确返回 ORDER_NOT_FOUND：{cancel_resp}", str(cancel_resp))

    if case_id == "TC_CANCEL_002" or has_text(case, "超时", "边界"):
        create_resp = create_order(assign_driver=False)
        timeout_resp = timeout_cancel_order(create_resp["order_id"])
        query_resp = get_order(create_resp["order_id"])
        order = query_resp["order"]

        if (
            timeout_resp["code"] == 0
            and order["order_status"] == "cancelled"
            and order["cancel_reason"] == "timeout_no_driver"
        ):
            return build_pass_result(case, actual_result=f"timeout_resp={timeout_resp}, order={order}")
        return build_fail_result(case, f"超时取消失败：timeout_resp={timeout_resp}, order={order}", str(order))

    if has_text(case, "重复取消", "重复操作"):
        create_resp = create_order(assign_driver=False)
        first_cancel = cancel_order(create_resp["order_id"], reason="first_cancel")
        second_cancel = cancel_order(create_resp["order_id"], reason="second_cancel")
        query_resp = get_order(create_resp["order_id"])
        order = query_resp["order"]

        if (
            first_cancel["code"] == 0
            and second_cancel["code"] == 409
            and second_cancel["message"] == "REPEAT_CANCEL"
            and order["order_status"] == "cancelled"
        ):
            return build_pass_result(case, actual_result=f"first={first_cancel}, second={second_cancel}, order={order}")
        return build_fail_result(case, f"重复取消校验失败：first={first_cancel}, second={second_cancel}, order={order}", str(order))

    if case_id == "TC_CANCEL_003" or has_text(case, "司机已接单", "状态变更"):
        create_resp = create_order(assign_driver=True)
        cancel_resp = cancel_order(create_resp["order_id"], reason="driver_accepted_user_cancel")
        query_resp = get_order(create_resp["order_id"])
        order = query_resp["order"]

        if (
            cancel_resp["code"] == 0
            and order["order_status"] == "cancelled"
            and order["cancel_reason"] == "driver_accepted_user_cancel"
        ):
            return build_pass_result(case, actual_result=f"cancel_resp={cancel_resp}, order={order}")
        return build_fail_result(case, f"已接单取消状态变更失败：cancel_resp={cancel_resp}, order={order}", str(order))

    if case_id == "TC_CANCEL_004" or has_text(case, "司机资源释放", "资源释放"):
        create_resp = create_order(assign_driver=True)
        cancel_resp = cancel_order(create_resp["order_id"], reason="resource_release_test")
        driver_resp = get_driver(create_resp["driver_id"])
        driver_status = driver_resp["driver"]["driver_status"]

        if cancel_resp["code"] == 0 and driver_status == "available":
            return build_pass_result(case, actual_result=f"cancel_resp={cancel_resp}, driver_resp={driver_resp}")
        return build_fail_result(
            case,
            f"资源释放校验失败：cancel_resp={cancel_resp}, driver_resp={driver_resp}",
            str(driver_resp)
        )

    if has_text(case, "数据一致性", "列表与详情"):
        create_resp = create_order(assign_driver=False)
        cancel_order(create_resp["order_id"], reason="consistency_test")
        detail_resp = get_order(create_resp["order_id"])
        list_resp = list_user_orders()
        order = detail_resp["order"]

        if assert_order_in_user_list(order, list_resp["orders"], ["order_status", "cancel_reason"]):
            return build_pass_result(case, actual_result=f"detail={detail_resp}, list={list_resp}")
        return build_fail_result(case, f"取消后详情与列表不一致：detail={detail_resp}, list={list_resp}", str(list_resp))

    return fail_unconfigured_case(case, "cancel")


def run_payment_case(case: dict) -> dict:
    """Execute payment cases with concrete API calls and result checks."""

    case_id = case["case_id"]
    reset_mock_data()
    create_resp = create_order(assign_driver=False)
    order_id = create_resp["order_id"]

    if case_id == "TC_PAY_001" or has_text(case, "正常支付", "支付成功", "正常场景"):
        pay_resp = pay_order(order_id, amount=30.0)
        query_resp = get_order(order_id)
        order = query_resp["order"]

        if pay_resp["code"] == 0 and order["payment_status"] == "paid" and order["order_status"] == "paid":
            return build_pass_result(case, actual_result=f"pay_resp={pay_resp}, order={order}")
        return build_fail_result(case, f"正常支付失败：pay_resp={pay_resp}, order={order}", str(order))

    if has_text(case, "金额异常", "INVALID_AMOUNT", "异常场景"):
        pay_resp = pay_order(order_id, amount=0)
        query_resp = get_order(order_id)
        order = query_resp["order"]

        if pay_resp["code"] == 400 and pay_resp["message"] == "INVALID_AMOUNT" and order["payment_status"] == "unpaid":
            return build_pass_result(case, actual_result=f"pay_resp={pay_resp}, order={order}")
        return build_fail_result(case, f"异常金额未正确拦截：pay_resp={pay_resp}, order={order}", str(order))

    if has_text(case, "最小有效金额", "边界"):
        pay_resp = pay_order(order_id, amount=0.01)
        query_resp = get_order(order_id)
        order = query_resp["order"]

        if pay_resp["code"] == 0 and order["payment_status"] == "paid":
            return build_pass_result(case, actual_result=f"pay_resp={pay_resp}, order={order}")
        return build_fail_result(case, f"最小有效金额支付失败：pay_resp={pay_resp}, order={order}", str(order))

    if case_id == "TC_PAY_002" or has_text(case, "重复支付", "重复操作"):
        first_pay = pay_order(order_id, amount=30.0)
        second_pay = pay_order(order_id, amount=30.0)

        if first_pay["code"] == 0 and second_pay["code"] == 409 and second_pay["message"] == "REPEAT_PAYMENT":
            return build_pass_result(case, actual_result=f"first_pay={first_pay}, second_pay={second_pay}")
        return build_fail_result(case, f"重复支付未被拦截：first={first_pay}, second={second_pay}", str(second_pay))

    if has_text(case, "状态变更"):
        pay_resp = pay_order(order_id, amount=30.0)
        query_resp = get_order(order_id)
        order = query_resp["order"]

        if pay_resp["code"] == 0 and order["order_status"] == "paid" and order["payment_status"] == "paid":
            return build_pass_result(case, actual_result=f"pay_resp={pay_resp}, order={order}")
        return build_fail_result(case, f"支付状态变更失败：pay_resp={pay_resp}, order={order}", str(order))

    if has_text(case, "资源释放", "资源占用"):
        pay_resp = pay_order(order_id, amount=0)
        driver_resp = get_driver()
        driver_status = driver_resp["driver"]["driver_status"]

        if pay_resp["code"] == 400 and driver_status == "available":
            return build_pass_result(case, actual_result=f"pay_resp={pay_resp}, driver_resp={driver_resp}")
        return build_fail_result(case, f"支付失败资源状态异常：pay_resp={pay_resp}, driver_resp={driver_resp}", str(driver_resp))

    if has_text(case, "数据一致性", "列表数据一致性"):
        pay_order(order_id, amount=30.0)
        detail_resp = get_order(order_id)
        list_resp = list_user_orders()
        order = detail_resp["order"]

        if assert_order_in_user_list(order, list_resp["orders"], ["payment_status", "order_status"]):
            return build_pass_result(case, actual_result=f"detail={detail_resp}, list={list_resp}")
        return build_fail_result(case, f"支付后详情与列表不一致：detail={detail_resp}, list={list_resp}", str(list_resp))

    return fail_unconfigured_case(case, "payment")


def run_create_order_case(case: dict) -> dict:
    """Execute order-create cases with concrete API calls and result checks."""

    case_id = case["case_id"]
    reset_mock_data()

    if case_id == "TC_ORDER_001" or has_text(case, "正常创建", "正常场景"):
        create_resp = create_order(assign_driver=False)
        if create_resp["code"] == 0 and create_resp["order_id"] and create_resp["order_status"] == "waiting":
            return build_pass_result(case, actual_result=f"create_resp={create_resp}")
        return build_fail_result(case, f"正常创建订单失败：create_resp={create_resp}", str(create_resp))

    if case_id == "TC_ORDER_002" or has_text(case, "参数异常", "起点为空", "PARAM_ERROR"):
        resp = create_order(assign_driver=False, start_location="", end_location="B")
        if resp["code"] == 400 and resp["message"] == "PARAM_ERROR":
            return build_pass_result(case, actual_result=f"create_resp={resp}")
        return build_fail_result(case, f"参数异常未被拦截：resp={resp}", str(resp))

    if has_text(case, "起点终点相同", "SAME_LOCATION", "边界"):
        resp = create_order(assign_driver=False, start_location="A", end_location="A")
        if resp["code"] == 400 and resp["message"] == "SAME_LOCATION":
            return build_pass_result(case, actual_result=f"create_resp={resp}")
        return build_fail_result(case, f"相同起终点未被拦截：resp={resp}", str(resp))

    if has_text(case, "重复下单", "重复操作", "DUPLICATE_ORDER"):
        first_create = create_order(assign_driver=False)
        second_create = create_order(assign_driver=False)
        if first_create["code"] == 0 and second_create["code"] == 409 and second_create["message"] == "DUPLICATE_ORDER":
            return build_pass_result(case, actual_result=f"first={first_create}, second={second_create}")
        return build_fail_result(case, f"重复下单未被拦截：first={first_create}, second={second_create}", str(second_create))

    if has_text(case, "已接单", "状态变更"):
        create_resp = create_order(assign_driver=True)
        if create_resp["code"] == 0 and create_resp["order_status"] == "accepted" and create_resp["driver_id"]:
            return build_pass_result(case, actual_result=f"create_resp={create_resp}")
        return build_fail_result(case, f"创建已接单订单状态异常：create_resp={create_resp}", str(create_resp))

    if has_text(case, "司机资源占用", "资源释放"):
        create_resp = create_order(assign_driver=True)
        driver_resp = get_driver(create_resp["driver_id"])
        driver_status = driver_resp["driver"]["driver_status"]
        if create_resp["code"] == 0 and driver_status == "assigned":
            return build_pass_result(case, actual_result=f"create_resp={create_resp}, driver_resp={driver_resp}")
        return build_fail_result(case, f"创建订单后司机资源状态异常：create_resp={create_resp}, driver_resp={driver_resp}", str(driver_resp))

    if has_text(case, "数据一致性", "详情与列表"):
        create_resp = create_order(assign_driver=False)
        detail_resp = get_order(create_resp["order_id"])
        list_resp = list_user_orders()
        order = detail_resp["order"]

        if assert_order_in_user_list(order, list_resp["orders"], ["order_status", "start_location", "end_location"]):
            return build_pass_result(case, actual_result=f"detail={detail_resp}, list={list_resp}")
        return build_fail_result(case, f"创建后详情与列表不一致：detail={detail_resp}, list={list_resp}", str(list_resp))

    return fail_unconfigured_case(case, "order_create")


def run_single_api_test(case: dict) -> dict:
    """Dispatch one test case to exactly one business executor."""

    case_id = case.get("case_id", "")
    title = case.get("title", "")

    if "CANCEL" in case_id or "取消" in title:
        return run_cancel_case(case)

    if "PAY" in case_id or "支付" in title or "付款" in title:
        return run_payment_case(case)

    if "ORDER" in case_id or "创建" in title or "下单" in title:
        return run_create_order_case(case)

    return build_fail_result(
        case,
        error_log="未匹配到具体业务类型，不能默认标记为通过"
    )


def run_api_tests(test_cases: list[dict]) -> list[dict]:
    """Execute HTTP API tests and never default unknown cases to passed."""

    results = []

    for case in test_cases:
        try:
            result = run_single_api_test(case)
            results.append(result)

        except requests.exceptions.ConnectionError:
            results.append(
                build_fail_result(
                    case,
                    error_log=(
                        "无法连接模拟业务接口。请确认已经启动服务："
                        "uvicorn app.api_server:app --reload"
                    )
                )
            )

        except Exception as e:
            results.append(
                build_fail_result(
                    case,
                    error_log=f"接口测试执行异常：{str(e)}"
                )
            )

    return results
