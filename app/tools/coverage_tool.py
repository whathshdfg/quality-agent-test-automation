#覆盖率只根据测试用例判断，不再直接根据需求文本判断
def analyze_test_coverage(requirement: str, test_cases: list[dict]) -> dict:
    """
    分析测试用例覆盖情况。

    V4 版本：
    主要根据测试用例内容判断覆盖情况，而不是只看需求文本。
    """

    coverage_rules = {
        "正常场景": ["正常", "成功", "主动取消", "创建成功", "支付成功"],
        "异常场景": ["异常", "失败", "为空", "错误", "不存在", "ORDER_NOT_FOUND", "PARAM_ERROR", "INVALID_AMOUNT"],
        "边界场景": ["边界", "3 分钟", "超过", "接近", "超时", "最小有效金额", "起点终点相同", "SAME_LOCATION"],
        "重复操作": ["重复", "再次", "连续点击", "重复支付", "重复下单", "重复取消"],
        "状态变更校验": ["状态变更", "状态", "cancelled", "paid", "waiting", "accepted", "unpaid"],
        "资源释放校验": ["资源", "资源释放", "资源占用", "司机状态", "driver_status", "available", "assigned"],
        "数据一致性校验": ["一致", "数据一致性", "校验", "查询", "order_id", "payment_status", "订单列表"],
    }

    all_case_text = ""

    for case in test_cases:
        all_case_text += case.get("case_id", "") + "\n"
        all_case_text += case.get("title", "") + "\n"
        all_case_text += case.get("precondition", "") + "\n"
        all_case_text += case.get("expected_result", "") + "\n"

        for step in case.get("steps", []):
            all_case_text += step + "\n"

    coverage_details = []
    covered_count = 0

    for dimension, keywords in coverage_rules.items():
        matched_keywords = []

        for keyword in keywords:
            if keyword in all_case_text:
                matched_keywords.append(keyword)

        is_covered = len(matched_keywords) > 0

        if is_covered:
            covered_count += 1

        coverage_details.append({
            "dimension": dimension,
            "covered": is_covered,
            "matched_keywords": matched_keywords
        })

    total_dimensions = len(coverage_rules)
    coverage_rate = round(covered_count / total_dimensions * 100, 2)

    missing_dimensions = [
        item["dimension"]
        for item in coverage_details
        if not item["covered"]
    ]

    return {
        "total_dimensions": total_dimensions,
        "covered_dimensions": covered_count,
        "coverage_rate": coverage_rate,
        "missing_dimensions": missing_dimensions,
        "details": coverage_details
    }
