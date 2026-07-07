def analyze_failed_cases(test_results: list[dict]) -> list[dict]:
    """
    日志分析工具
    分析失败用例，根据错误日志判断失败原因。
    """

    analysis_results = []

    for result in test_results:
        if result["status"] == "failed":
            error_log = result["error_log"]

            if "driver_status still assigned" in error_log:
                analysis_results.append({
                    "case_id": result["case_id"],
                    "title": result["title"],
                    "bug_type": "资源释放异常",
                    "root_cause": "订单取消后，只更新了订单状态，没有释放司机资源",
                    "suggestion": "在 cancel_order 逻辑中增加 driver_status 从 assigned 到 available 的状态更新"
                })
            else:
                analysis_results.append({
                    "case_id": result["case_id"],
                    "title": result["title"],
                    "bug_type": "未知异常",
                    "root_cause": "需要进一步查看日志",
                    "suggestion": "补充日志字段并重新执行测试"
                })

    return analysis_results