def generate_rule_based_test_cases(requirement: str) -> list[dict]:
    """
    规则版测试用例生成器。
    当大模型不可用、API Key 缺失、JSON 解析失败时，回退到这个版本。
    """

    test_cases = []

    if "取消" in requirement:
        test_cases = [
            {
                "case_id": "TC_CANCEL_001",
                "title": "用户主动取消未接单订单",
                "precondition": "用户已创建订单，订单状态为 waiting",
                "steps": [
                    "调用取消订单接口",
                    "传入 user_id、order_id、cancel_reason",
                    "查询订单状态"
                ],
                "expected_result": "订单状态变为 cancelled"
            },
            {
                "case_id": "TC_CANCEL_002",
                "title": "订单超时自动取消",
                "precondition": "订单创建后 3 分钟内无司机接单",
                "steps": [
                    "创建订单",
                    "等待超过 3 分钟",
                    "查询订单状态"
                ],
                "expected_result": "订单状态自动变为 cancelled"
            },
            {
                "case_id": "TC_CANCEL_003",
                "title": "司机已接单后用户取消订单",
                "precondition": "订单状态为 accepted",
                "steps": [
                    "调用取消订单接口",
                    "传入取消原因",
                    "查询订单状态和取消原因"
                ],
                "expected_result": "订单取消成功，并记录 cancel_reason"
            },
            {
                "case_id": "TC_CANCEL_004",
                "title": "订单取消后司机资源释放校验",
                "precondition": "司机已被订单占用",
                "steps": [
                    "取消订单",
                    "查询司机状态"
                ],
                "expected_result": "司机状态从 assigned 变为 available"
            }
        ]

    elif "支付" in requirement:
        test_cases = [
            {
                "case_id": "TC_PAY_001",
                "title": "订单正常支付成功",
                "precondition": "订单状态为 unpaid",
                "steps": [
                    "调用支付接口",
                    "传入 user_id、order_id、amount",
                    "查询支付状态"
                ],
                "expected_result": "payment_status 变为 paid"
            },
            {
                "case_id": "TC_PAY_002",
                "title": "重复支付拦截",
                "precondition": "订单已经 paid",
                "steps": [
                    "再次调用支付接口",
                    "查询接口返回结果"
                ],
                "expected_result": "系统返回 REPEAT_PAYMENT"
            }
        ]

    else:
        test_cases = [
            {
                "case_id": "TC_ORDER_001",
                "title": "正常创建订单",
                "precondition": "用户没有未完成订单",
                "steps": [
                    "输入起点",
                    "输入终点",
                    "调用创建订单接口"
                ],
                "expected_result": "订单创建成功，返回 order_id"
            },
            {
                "case_id": "TC_ORDER_002",
                "title": "起点为空时创建订单失败",
                "precondition": "用户没有未完成订单",
                "steps": [
                    "起点传空",
                    "终点传入有效地址",
                    "调用创建订单接口"
                ],
                "expected_result": "系统返回 PARAM_ERROR"
            }
        ]

    for case in test_cases:
        case["generation_source"] = "rule"

    return test_cases