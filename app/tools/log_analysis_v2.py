"""Classify failures emitted by the structured Harness executor."""


def analyze_v2_failures(test_results: list[dict]) -> list[dict]:
    analyses = []
    for result in test_results:
        if result.get("status") != "failed":
            continue

        error = result.get("error_log", "")
        failed_assertions = [
            item
            for item in result.get("assertion_results", [])
            if not item.get("passed")
        ]
        if error == "结构化断言失败":
            bug_type = "业务结果与预期不一致"
            root_cause = "接口已执行，但至少一个结构化断言不满足"
            suggestion = "根据 actual、expected 和对应业务规则检查实现或测试预期"
        elif "变量引用" in error or "Harness 执行失败" in error:
            bug_type = "测试计划或执行能力异常"
            root_cause = error
            suggestion = "检查操作依赖、变量引用、能力注册和 Harness 策略"
        elif "无法连接" in error or "Connection" in error:
            bug_type = "测试环境异常"
            root_cause = "Mock API 无法访问"
            suggestion = "确认后端服务、MOCK_API_BASE_URL 和端口状态"
        else:
            bug_type = "未知执行异常"
            root_cause = error or "没有可用错误日志"
            suggestion = "检查动作响应和结构化断言证据"

        analyses.append({
            "case_id": result.get("case_id", ""),
            "title": result.get("title", ""),
            "bug_type": bug_type,
            "root_cause": root_cause,
            "suggestion": suggestion,
            "failed_assertions": failed_assertions,
        })
    return analyses

