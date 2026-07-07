#失败重试机制 / 自动补充测试用例机制
#当 Agent 发现测试覆盖率不足时，不直接进入测试执行，而是自动判断缺失了哪些测试维度，并补充对应测试用例，然后重新计算覆盖率。
def get_existing_case_ids(test_cases: list[dict]) -> set:
    """
    获取已有测试用例编号，避免重复添加。
    """
    return {case.get("case_id", "") for case in test_cases}


def build_supplement_case(dimension: str, requirement: str, index: int) -> dict | None:
    """
    根据缺失的覆盖维度，生成补充测试用例。
    """

    # 订单取消场景
    if "取消" in requirement:
        if dimension == "重复操作":
            return {
                "case_id": f"TC_RETRY_{index:03d}",
                "title": "重复取消订单校验",
                "precondition": "订单已被用户取消，订单状态为 cancelled",
                "steps": [
                    "再次调用取消订单接口",
                    "传入相同 user_id 和 order_id",
                    "查询接口返回结果和订单状态"
                ],
                "expected_result": "系统应拒绝重复取消操作，订单状态保持 cancelled，不产生异常状态变更"
            }

        if dimension == "数据一致性校验":
            return {
                "case_id": f"TC_RETRY_{index:03d}",
                "title": "订单取消后数据一致性校验",
                "precondition": "用户已成功取消订单",
                "steps": [
                    "查询订单状态",
                    "查询司机状态",
                    "查询用户订单列表"
                ],
                "expected_result": "订单状态、司机状态和用户订单列表数据保持一致"
            }

        if dimension == "边界场景":
            return {
                "case_id": f"TC_RETRY_{index:03d}",
                "title": "接近超时时间边界的订单取消校验",
                "precondition": "订单创建后接近 3 分钟仍无司机接单",
                "steps": [
                    "创建订单",
                    "等待接近 3 分钟",
                    "查询订单状态"
                ],
                "expected_result": "系统应在 3 分钟超时边界正确触发自动取消逻辑"
            }

    # 支付场景
    if "支付" in requirement:
        if dimension == "重复操作":
            return {
                "case_id": f"TC_RETRY_{index:03d}",
                "title": "重复支付拦截校验",
                "precondition": "订单已支付成功，payment_status 为 paid",
                "steps": [
                    "再次调用支付接口",
                    "传入相同 user_id、order_id 和 amount",
                    "查询支付状态"
                ],
                "expected_result": "系统应返回 REPEAT_PAYMENT，避免重复扣款"
            }

        if dimension == "异常场景":
            return {
                "case_id": f"TC_RETRY_{index:03d}",
                "title": "支付失败场景校验",
                "precondition": "订单状态为 unpaid",
                "steps": [
                    "模拟支付渠道返回失败",
                    "调用支付接口",
                    "查询订单支付状态"
                ],
                "expected_result": "系统应返回支付失败，订单保持 unpaid 状态"
            }

    # 订单创建场景
    if "创建" in requirement or "下单" in requirement or "订单" in requirement:
        if dimension == "重复操作":
            return {
                "case_id": f"TC_RETRY_{index:03d}",
                "title": "重复下单拦截校验",
                "precondition": "用户已经存在未完成订单",
                "steps": [
                    "用户再次提交创建订单请求",
                    "传入相同 user_id、start_location 和 end_location",
                    "查询接口返回结果"
                ],
                "expected_result": "系统应返回 DUPLICATE_ORDER，禁止重复下单"
            }

        if dimension == "异常场景":
            return {
                "case_id": f"TC_RETRY_{index:03d}",
                "title": "订单创建参数异常校验",
                "precondition": "用户没有未完成订单",
                "steps": [
                    "将起点或终点设置为空",
                    "调用创建订单接口",
                    "查询接口返回结果"
                ],
                "expected_result": "系统应返回 PARAM_ERROR"
            }

    return None


def enhance_test_cases(
    requirement: str,
    test_cases: list[dict],
    coverage_result: dict
) -> tuple[list[dict], list[dict]]:
    """
    根据覆盖率分析结果，自动补充缺失维度的测试用例。

    返回：
    1. 补充后的测试用例列表
    2. 本次新增的测试用例列表
    """

    missing_dimensions = []

    for item in coverage_result.get("details", []):
        if not item.get("covered", False):
            missing_dimensions.append(item["dimension"])

    enhanced_cases = test_cases.copy()
    added_cases = []
    existing_ids = get_existing_case_ids(test_cases)

    add_index = 1

    for dimension in missing_dimensions:
        new_case = build_supplement_case(
            dimension=dimension,
            requirement=requirement,
            index=add_index
        )

        if new_case and new_case["case_id"] not in existing_ids:
            new_case["generation_source"] = "auto_supplement"
            enhanced_cases.append(new_case)
            added_cases.append({
                "missing_dimension": dimension,
                "added_case": new_case
            })
            existing_ids.add(new_case["case_id"])
            add_index += 1

    return enhanced_cases, added_cases
