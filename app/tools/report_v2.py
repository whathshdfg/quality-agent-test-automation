"""Reporting and metrics for the structured V2 Agent workflow."""

import json
from pathlib import Path


OUTPUT_DIR = Path("app/outputs")


def calculate_v2_metrics(state: dict) -> dict:
    results = state.get("test_results", [])
    passed = sum(item.get("status") == "passed" for item in results)
    failed = sum(item.get("status") == "failed" for item in results)
    matrix = state.get("coverage_matrix", {})
    fallback_fields = [
        "requirement_fallback_reason",
        "test_point_fallback_reason",
        "coverage_fallback_reason",
        "planning_fallback_reason",
    ]
    return {
        "run_id": state.get("run_id", ""),
        "requirement_rule_count": len(state.get("requirement_rules", [])),
        "test_point_count": len(state.get("test_points", [])),
        "test_case_count": len(state.get("test_cases", [])),
        "passed_cases": passed,
        "failed_cases": failed,
        "pass_rate": round(passed / len(results) * 100, 2) if results else 0,
        "requirement_coverage_rate": matrix.get("requirement_coverage", {}).get("coverage_rate", 0),
        "parameter_coverage_rate": matrix.get("parameter_coverage", {}).get("coverage_rate", 0),
        "risk_coverage_rate": matrix.get("risk_coverage", {}).get("coverage_rate", 0),
        "coverage_gap_count": len(matrix.get("gaps", [])),
        "unsupported_test_point_count": len(state.get("unsupported_test_points", [])),
        "enhancement_count": state.get("enhancement_count", 0),
        "requirement_source": state.get("requirement_source", ""),
        "test_point_source": state.get("test_point_source", ""),
        "coverage_source": state.get("coverage_source", ""),
        "planning_source": state.get("planning_source", ""),
        "fallback_count": sum(bool(state.get(field)) for field in fallback_fields),
        "failed_case_ids": [
            item.get("case_id") for item in results if item.get("status") == "failed"
        ],
        "bug_count": len(state.get("bug_analysis", [])),
    }


def generate_v2_report(state: dict, metrics: dict) -> str:
    lines = [
        "# 测试智能化 Agent V2 执行报告",
        "",
        f"运行编号：`{state.get('run_id', '')}`",
        "",
        "## 一、测试需求",
        "",
        state.get("requirement", ""),
        "",
        "## 二、结构化需求规则",
        "",
    ]
    for rule in state.get("requirement_rules", []):
        lines.extend([
            f"### {rule['rule_id']} {rule['text']}",
            f"- 业务类型：{rule['business_type']}",
            f"- 动作：{rule.get('action', '')}",
            f"- 预期：{'；'.join(rule.get('expected_outcomes', [])) or '无'}",
            f"- 风险：{'、'.join(rule.get('risks', [])) or '无'}",
            "",
        ])

    lines.extend(["## 三、分层测试点", ""])
    for point in state.get("test_points", []):
        lines.extend([
            f"### {point['test_point_id']} {point['description']}",
            f"- 层级：{point['level_1']} / {point['level_2']}",
            f"- 关联需求：{'、'.join(point.get('requirement_ids', []))}",
            f"- 参数检查：{'、'.join(point.get('parameter_checks', [])) or '无'}",
            f"- 风险标签：{'、'.join(point.get('risk_tags', [])) or '无'}",
            "",
        ])

    matrix = state.get("coverage_matrix", {})
    lines.extend([
        "## 四、覆盖矩阵",
        "",
        f"- 需求覆盖率：{metrics['requirement_coverage_rate']}%",
        f"- 参数覆盖率：{metrics['parameter_coverage_rate']}%",
        f"- 风险覆盖率：{metrics['risk_coverage_rate']}%",
        f"- 剩余缺口：{metrics['coverage_gap_count']}",
        "",
    ])
    for gap in matrix.get("gaps", []):
        lines.append(f"- `{gap['target_id']}`：{gap['description']}")
    lines.append("")

    lines.extend(["## 五、Harness 测试计划与执行结果", ""])
    results_by_id = {
        item.get("case_id"): item for item in state.get("test_results", [])
    }
    for case in state.get("test_cases", []):
        result = results_by_id.get(case["case_id"], {})
        lines.extend([
            f"### {case['case_id']} {case['title']}",
            f"- 状态：{result.get('status', 'not_run')}",
            f"- 关联测试点：{'、'.join(case.get('test_point_ids', []))}",
            f"- 操作数：{len(case.get('setup_actions', [])) + len(case.get('test_actions', [])) + len(case.get('verification_actions', []))}",
            f"- 断言数：{len(case.get('assertions', []))}",
        ])
        if result.get("error_log"):
            lines.append(f"- 错误：{result['error_log']}")
        lines.append("")

    lines.extend(["## 六、失败分析", ""])
    analyses = state.get("bug_analysis", [])
    if analyses:
        for item in analyses:
            lines.extend([
                f"### {item['case_id']} {item['title']}",
                f"- 类型：{item['bug_type']}",
                f"- 原因：{item['root_cause']}",
                f"- 建议：{item['suggestion']}",
                "",
            ])
    else:
        lines.extend(["本次没有失败用例。", ""])

    lines.extend(["## 七、不可执行测试点", ""])
    unsupported = state.get("unsupported_test_points", [])
    if unsupported:
        for item in unsupported:
            lines.append(
                f"- `{item['test_point_id']}`：{'；'.join(item.get('reasons', []))}"
            )
    else:
        lines.append("无。")

    lines.extend([
        "",
        "## 八、运行指标",
        "",
        f"- 测试用例：{metrics['test_case_count']}",
        f"- 通过：{metrics['passed_cases']}",
        f"- 失败：{metrics['failed_cases']}",
        f"- 通过率：{metrics['pass_rate']}%",
        f"- 自动补充轮数：{metrics['enhancement_count']}",
        f"- 降级次数：{metrics['fallback_count']}",
        "",
    ])
    return "\n".join(lines)


def save_v2_outputs(state: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "v2_test_report.md").write_text(
        state["report"], encoding="utf-8"
    )
    (OUTPUT_DIR / "v2_metrics_report.json").write_text(
        json.dumps(state["metrics"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "v2_execution_trace.json").write_text(
        json.dumps(state["trace"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
