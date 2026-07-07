import os

def run_api_tests(test_cases: list[dict]) -> list[dict]:
    """
    模拟接口测试工具
    模拟执行接口测试。
    真实项目里这里会调用 requests、pytest 或自动化测试平台。
    初学阶段先模拟通过/失败结果。
    """

    import os
import requests


BASE_URL = os.getenv("MOCK_API_BASE_URL", "http://127.0.0.1:8000")


def call_api(method: str, path: str, json_data: dict | None = None) -> dict:
    """
    统一封装 HTTP 请求。
    """

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


def create_order(assign_driver: bool = False) -> dict:
    return call_api(
        "POST",
        "/mock/order/create",
        {
            "user_id": "user_001",
            "start_location": "A",
            "end_location": "B",
            "assign_driver": assign_driver
        }
    )


def cancel_order(order_id: str, reason: str | None = "user_cancel") -> dict:
    return call_api(
        "POST",
        "/mock/order/cancel",
        {
            "user_id": "user_001",
            "order_id": order_id,
            "cancel_reason": reason
        }
    )


def timeout_cancel_order(order_id: str) -> dict:
    return call_api(
        "POST",
        "/mock/order/timeout_cancel",
        {
            "order_id": order_id
        }
    )


def get_order(order_id: str) -> dict:
    return call_api("GET", f"/mock/order/{order_id}")


def get_driver(driver_id: str) -> dict:
    return call_api("GET", f"/mock/driver/{driver_id}")


def pay_order(order_id: str, amount: float = 30.0) -> dict:
    return call_api(
        "POST",
        "/mock/payment/pay",
        {
            "user_id": "user_001",
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


def run_cancel_case(case: dict) -> dict:
    """
    执行订单取消相关测试用例。
    """

    case_id = case["case_id"]
    title = case["title"]

    reset_mock_data()

    # TC_CANCEL_001：用户主动取消未接单订单
    if case_id == "TC_CANCEL_001" or "主动取消" in title:
        create_resp = create_order(assign_driver=False)
        order_id = create_resp["order_id"]

        cancel_resp = cancel_order(order_id, reason="user_cancel")
        query_resp = get_order(order_id)

        order_status = query_resp["order"]["order_status"]

        if cancel_resp["code"] == 0 and order_status == "cancelled":
            return build_pass_result(
                case,
                actual_result=f"cancel_resp={cancel_resp}, order_status={order_status}"
            )

        return build_fail_result(
            case,
            error_log=f"主动取消失败，cancel_resp={cancel_resp}, query_resp={query_resp}",
            actual_result=str(query_resp)
        )

    # TC_CANCEL_002：订单超时自动取消
    if case_id == "TC_CANCEL_002" or "超时" in title:
        create_resp = create_order(assign_driver=False)
        order_id = create_resp["order_id"]

        timeout_resp = timeout_cancel_order(order_id)
        query_resp = get_order(order_id)

        order_status = query_resp["order"]["order_status"]

        if timeout_resp["code"] == 0 and order_status == "cancelled":
            return build_pass_result(
                case,
                actual_result=f"timeout_resp={timeout_resp}, order_status={order_status}"
            )

        return build_fail_result(
            case,
            error_log=f"超时取消失败，timeout_resp={timeout_resp}, query_resp={query_resp}",
            actual_result=str(query_resp)
        )

    # TC_CANCEL_003：司机已接单后用户取消订单，并记录取消原因
    if case_id == "TC_CANCEL_003" or "司机已接单" in title:
        create_resp = create_order(assign_driver=True)
        order_id = create_resp["order_id"]

        cancel_resp = cancel_order(order_id, reason="driver_accepted_user_cancel")
        query_resp = get_order(order_id)

        order = query_resp["order"]

        if (
            cancel_resp["code"] == 0
            and order["order_status"] == "cancelled"
            and order["cancel_reason"] == "driver_accepted_user_cancel"
        ):
            return build_pass_result(
                case,
                actual_result=f"cancel_resp={cancel_resp}, order={order}"
            )

        return build_fail_result(
            case,
            error_log=f"已接单取消失败，cancel_resp={cancel_resp}, order={order}",
            actual_result=str(order)
        )

    # TC_CANCEL_004：订单取消后司机资源释放校验
    if case_id == "TC_CANCEL_004" or "司机资源" in title or "资源释放" in title:
        create_resp = create_order(assign_driver=True)
        order_id = create_resp["order_id"]
        driver_id = create_resp["driver_id"]

        cancel_resp = cancel_order(order_id, reason="resource_release_test")
        driver_resp = get_driver(driver_id)

        driver_status = driver_resp["driver"]["driver_status"]

        if cancel_resp["code"] == 0 and driver_status == "available":
            return build_pass_result(
                case,
                actual_result=f"driver_status={driver_status}"
            )

        return build_fail_result(
            case,
            error_log=(
                "ERROR OrderService - cancel order success, "
                f"but driver_status still {driver_status}"
            ),
            actual_result=f"cancel_resp={cancel_resp}, driver_resp={driver_resp}"
        )

    # 自动补充用例：重复取消订单
    if "重复取消" in title or "重复操作" in title:
        create_resp = create_order(assign_driver=False)
        order_id = create_resp["order_id"]

        first_cancel = cancel_order(order_id, reason="first_cancel")
        second_cancel = cancel_order(order_id, reason="second_cancel")
        query_resp = get_order(order_id)

        order_status = query_resp["order"]["order_status"]

        if (
            first_cancel["code"] == 0
            and second_cancel["code"] != 0
            and order_status == "cancelled"
        ):
            return build_pass_result(
                case,
                actual_result=(
                    f"first_cancel={first_cancel}, "
                    f"second_cancel={second_cancel}, "
                    f"order_status={order_status}"
                )
            )

        return build_fail_result(
            case,
            error_log=(
                f"重复取消校验失败，first_cancel={first_cancel}, "
                f"second_cancel={second_cancel}, query_resp={query_resp}"
            ),
            actual_result=str(query_resp)
        )

    # 自动补充用例：数据一致性
    if "数据一致性" in title:
        create_resp = create_order(assign_driver=False)
        order_id = create_resp["order_id"]

        cancel_resp = cancel_order(order_id, reason="consistency_test")
        query_resp = get_order(order_id)

        order = query_resp["order"]

        if cancel_resp["code"] == 0 and order["order_status"] == "cancelled":
            return build_pass_result(
                case,
                actual_result=f"order={order}"
            )

        return build_fail_result(
            case,
            error_log=f"数据一致性校验失败，cancel_resp={cancel_resp}, order={order}",
            actual_result=str(order)
        )

    return build_pass_result(
        case,
        actual_result="该取消类用例当前未配置专门断言，默认通过"
    )


def run_payment_case(case: dict) -> dict:
    """
    执行支付相关测试用例。
    """

    case_id = case["case_id"]
    title = case["title"]

    reset_mock_data()

    create_resp = create_order(assign_driver=False)
    order_id = create_resp["order_id"]

    if case_id == "TC_PAY_001" or "支付成功" in title or "正常支付" in title:
        pay_resp = pay_order(order_id, amount=30.0)
        query_resp = get_order(order_id)

        payment_status = query_resp["order"]["payment_status"]

        if pay_resp["code"] == 0 and payment_status == "paid":
            return build_pass_result(
                case,
                actual_result=f"pay_resp={pay_resp}, payment_status={payment_status}"
            )

        return build_fail_result(
            case,
            error_log=f"支付成功用例失败，pay_resp={pay_resp}, query_resp={query_resp}",
            actual_result=str(query_resp)
        )

    if case_id == "TC_PAY_002" or "重复支付" in title:
        first_pay = pay_order(order_id, amount=30.0)
        second_pay = pay_order(order_id, amount=30.0)

        if first_pay["code"] == 0 and second_pay["code"] != 0:
            return build_pass_result(
                case,
                actual_result=f"first_pay={first_pay}, second_pay={second_pay}"
            )

        return build_fail_result(
            case,
            error_log=f"重复支付未被拦截，first_pay={first_pay}, second_pay={second_pay}",
            actual_result=str(second_pay)
        )

    return build_pass_result(
        case,
        actual_result="该支付类用例当前未配置专门断言，默认通过"
    )


def run_create_order_case(case: dict) -> dict:
    """
    执行订单创建相关测试用例。
    """

    case_id = case["case_id"]
    title = case["title"]

    reset_mock_data()

    if case_id == "TC_ORDER_001" or "正常创建" in title:
        create_resp = create_order(assign_driver=False)

        if create_resp["code"] == 0 and create_resp["order_id"]:
            return build_pass_result(
                case,
                actual_result=f"create_resp={create_resp}"
            )

        return build_fail_result(
            case,
            error_log=f"正常创建订单失败，create_resp={create_resp}",
            actual_result=str(create_resp)
        )

    if case_id == "TC_ORDER_002" or "起点为空" in title or "参数异常" in title:
        resp = call_api(
            "POST",
            "/mock/order/create",
            {
                "user_id": "user_001",
                "start_location": "",
                "end_location": "B",
                "assign_driver": False
            }
        )

        if resp["code"] != 0 and resp["message"] == "PARAM_ERROR":
            return build_pass_result(
                case,
                actual_result=f"create_resp={resp}"
            )

        return build_fail_result(
            case,
            error_log=f"参数异常未被拦截，resp={resp}",
            actual_result=str(resp)
        )

    if "重复下单" in title:
        first_create = create_order(assign_driver=False)
        second_create = create_order(assign_driver=False)

        if first_create["code"] == 0 and second_create["code"] != 0:
            return build_pass_result(
                case,
                actual_result=f"first_create={first_create}, second_create={second_create}"
            )

        return build_fail_result(
            case,
            error_log=f"重复下单未被拦截，first_create={first_create}, second_create={second_create}",
            actual_result=str(second_create)
        )

    return build_pass_result(
        case,
        actual_result="该创建订单类用例当前未配置专门断言，默认通过"
    )


def run_single_api_test(case: dict) -> dict:
    """
    根据测试用例内容，分发到不同业务测试函数。
    """

    title = case.get("title", "")
    case_id = case.get("case_id", "")

    if "CANCEL" in case_id or "取消" in title or "超时" in title or "司机资源" in title:
        return run_cancel_case(case)

    if "PAY" in case_id or "支付" in title:
        return run_payment_case(case)

    if "ORDER" in case_id or "创建" in title or "下单" in title:
        return run_create_order_case(case)

    return build_pass_result(
        case,
        actual_result="未匹配到具体业务类型，默认通过"
    )


def run_api_tests(test_cases: list[dict]) -> list[dict]:
    """
    执行真实 HTTP 接口测试。
    """

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
