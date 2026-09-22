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
            elif "未配置该测试用例的执行与断言逻辑" in error_log:
                analysis_results.append({
                    "case_id": result["case_id"],
                    "title": result["title"],
                    "bug_type": "测试执行器能力缺失",
                    "root_cause": "测试用例已生成，但 api_test_tool 未配置对应接口调用和结果校验",
                    "suggestion": "为该 case_id 或业务维度补充专门执行路径，不能默认通过"
                })
            elif "未匹配到具体业务类型" in error_log:
                analysis_results.append({
                    "case_id": result["case_id"],
                    "title": result["title"],
                    "bug_type": "业务分类失败",
                    "root_cause": "用例无法归入订单取消、支付或订单创建任一业务类型",
                    "suggestion": "检查 case_id、标题和业务分类关键词，必要时补充明确业务类型"
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
