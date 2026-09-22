#指标统计工具
import json
import os

def calculate_metrics(state: dict) -> dict:
    """
    根据 Agent 最终状态计算指标。
    """

    test_cases = state.get("test_cases", [])
    test_results = state.get("test_results", [])
    coverage_result = state.get("coverage_result", {})
    retry_history = state.get("retry_history", [])
    rag_context = state.get("rag_context", [])
    bug_analysis = state.get("bug_analysis", [])

    total_cases = len(test_cases)
    passed_cases = len([r for r in test_results if r.get("status") == "passed"])
    failed_cases = len([r for r in test_results if r.get("status") == "failed"])

    pass_rate = round(passed_cases / total_cases * 100, 2) if total_cases > 0 else 0

    llm_generated_cases = len([
        c for c in test_cases
        if c.get("generation_source") == "llm"
    ])

    rule_generated_cases = len([
        c for c in test_cases
        if c.get("generation_source") == "rule"
    ])

    auto_supplement_cases = len([
        c for c in test_cases
        if c.get("generation_source") == "auto_supplement"
    ])

    unknown_generated_cases = (
        total_cases
        - llm_generated_cases
        - rule_generated_cases
        - auto_supplement_cases
    )

    added_cases_count = 0
    for retry in retry_history:
        added_cases_count += len(retry.get("added_cases", []))

    failed_case_ids = [
        r.get("case_id")
        for r in test_results
        if r.get("status") == "failed"
    ]

    metrics = {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "pass_rate": pass_rate,
        "coverage_rate": coverage_result.get("coverage_rate", 0),
        "covered_dimensions": coverage_result.get("covered_dimensions", 0),
        "total_dimensions": coverage_result.get("total_dimensions", 0),
        "missing_dimensions": coverage_result.get("missing_dimensions", []),
        "retry_count": state.get("retry_count", 0),
        "added_cases_count": added_cases_count,
        "enhancement_stop_reason": state.get("enhancement_stop_reason", ""),
        "llm_generated_cases": llm_generated_cases,
        "rule_generated_cases": rule_generated_cases,
        "auto_supplement_cases": auto_supplement_cases,
        "unknown_generated_cases": unknown_generated_cases,
        "rag_docs_count": len(rag_context),
        "bug_count": len(bug_analysis),
        "failed_case_ids": failed_case_ids
    }

    return metrics


def save_metrics(
    metrics: dict,
    file_path: str = "app/outputs/metrics_report.json"
) -> None:
    """
    保存指标报告。
    """

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)


def format_metrics_markdown(metrics: dict) -> str:
    """
    把指标转成 Markdown，追加到测试报告里。
    """

    text = "\n## 八、Agent 评测指标\n\n"

    text += f"- 测试用例总数：{metrics['total_cases']}\n"
    text += f"- 通过用例数：{metrics['passed_cases']}\n"
    text += f"- 失败用例数：{metrics['failed_cases']}\n"
    text += f"- 用例通过率：{metrics['pass_rate']}%\n"
    text += f"- 测试覆盖率：{metrics['coverage_rate']}%\n"
    text += f"- Agent 自动补充次数：{metrics['retry_count']}\n"
    text += f"- 自动补充用例数：{metrics['added_cases_count']}\n"
    if metrics.get("enhancement_stop_reason"):
        text += f"- 自动补充退出原因：{metrics['enhancement_stop_reason']}\n"
    text += f"- 大模型生成用例数：{metrics['llm_generated_cases']}\n"
    text += f"- 规则兜底生成用例数：{metrics['rule_generated_cases']}\n"
    text += f"- 自动补充生成用例数：{metrics['auto_supplement_cases']}\n"
    text += f"- RAG 检索文档数：{metrics['rag_docs_count']}\n"
    text += f"- 缺陷分析数量：{metrics['bug_count']}\n"

    if metrics["failed_case_ids"]:
        text += f"- 失败用例编号：{'、'.join(metrics['failed_case_ids'])}\n"
    else:
        text += "- 失败用例编号：无\n"

    text += "\n"

    return text
