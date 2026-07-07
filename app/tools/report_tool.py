from typing import Optional


def generate_report(
    requirement: str,
    test_cases: list[dict],
    test_results: list[dict],
    bug_analysis: list[dict],
    rag_context: Optional[list[dict]] = None,
    coverage_result: Optional[dict] = None,
    retry_history: Optional[list[dict]] = None,
) -> str:
    """Generate a Markdown test report."""

    total = len(test_results)
    passed = len([r for r in test_results if r.get("status") == "passed"])
    failed = len([r for r in test_results if r.get("status") == "failed"])

    report = "# 测试智能化 Agent 执行报告\n\n"

    report += "## 一、测试需求\n\n"
    report += requirement.strip() + "\n\n"

    report += "## 二、RAG 检索依据\n\n"
    if rag_context:
        for index, item in enumerate(rag_context, start=1):
            report += f"### 参考资料 {index}: {item.get('source', 'unknown')}\n\n"
            report += item.get("content", "")[:500] + "\n\n"
    else:
        report += "本次未检索到相关知识库内容。\n\n"

    report += "## 三、测试用例\n\n"
    for case in test_cases:
        report += f"### {case['case_id']} {case['title']}\n"

        generation_source = case.get("generation_source", "unknown")
        report += f"- 生成来源：{generation_source}\n"

        report += f"- 前置条件：{case['precondition']}\n"
        report += "- 操作步骤：\n"

        for step in case["steps"]:
            report += f"  - {step}\n"

        report += f"- 预期结果：{case['expected_result']}\n\n"

    report += "## 四、测试执行结果\n\n"
    report += f"- 总用例数: {total}\n"
    report += f"- 通过数: {passed}\n"
    report += f"- 失败数: {failed}\n\n"

    for result in test_results:
        report += f"### {result.get('case_id', '')} {result.get('title', '')}\n"
        report += f"- 执行状态: {result.get('status', '')}\n"

        if result.get("actual_result"):
            report += f"- 实际结果: {result['actual_result']}\n"

        if result.get("error_log"):
            report += f"- 错误日志: {result['error_log']}\n"

        report += "\n"

    report += "## 五、缺陷分析\n\n"
    if not bug_analysis:
        report += "本次测试未发现失败用例。\n\n"
    else:
        for bug in bug_analysis:
            report += f"### {bug.get('case_id', '')} {bug.get('title', '')}\n"
            report += f"- 缺陷类型: {bug.get('bug_type', '')}\n"
            report += f"- 根因分析: {bug.get('root_cause', '')}\n"
            report += f"- 优化建议: {bug.get('suggestion', '')}\n\n"

    report += "## 六、测试覆盖率分析\n\n"
    if coverage_result:
        report += f"- 覆盖维度总数: {coverage_result.get('total_dimensions', 0)}\n"
        report += f"- 已覆盖维度数: {coverage_result.get('covered_dimensions', 0)}\n"
        report += f"- 覆盖率: {coverage_result.get('coverage_rate', 0)}%\n"

        missing_dimensions = coverage_result.get("missing_dimensions", [])
        if missing_dimensions:
            report += f"- 未覆盖维度: {'、'.join(missing_dimensions)}\n\n"
        else:
            report += "- 未覆盖维度: 无\n\n"

        report += "| 覆盖维度 | 是否覆盖 | 命中关键词 |\n"
        report += "|---|---|---|\n"

        for item in coverage_result.get("details", []):
            status = "已覆盖" if item.get("covered") else "未覆盖"
            matched_keywords = item.get("matched_keywords", [])
            keywords = "、".join(matched_keywords) if matched_keywords else "无"
            report += f"| {item.get('dimension', '')} | {status} | {keywords} |\n"

        report += "\n"
    else:
        report += "本次未进行测试覆盖率分析。\n\n"

    report += "## 七、Agent 自动重试与用例补充记录\n\n"
    if retry_history:
        for retry in retry_history:
            missing_dimensions = retry.get("missing_dimensions", [])
            missing_text = "、".join(missing_dimensions) if missing_dimensions else "无"

            report += f"### 第 {retry.get('retry_round', '')} 次补充\n\n"
            report += f"- 补充前覆盖率: {retry.get('coverage_before', 0)}%\n"
            report += f"- 缺失维度: {missing_text}\n"
            report += f"- 新增用例数: {len(retry.get('added_cases', []))}\n\n"

            for item in retry.get("added_cases", []):
                case = item.get("added_case", {})
                report += f"#### 针对缺失维度: {item.get('missing_dimension', '')}\n"
                report += f"- 新增用例: {case.get('case_id', '')} {case.get('title', '')}\n"
                report += f"- 预期结果: {case.get('expected_result', '')}\n\n"
    else:
        report += "本次覆盖率已满足要求，未触发自动补充。\n\n"

    return report
