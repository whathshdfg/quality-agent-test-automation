import json
import time
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = PROJECT_ROOT / "app"

sys.path.append(str(APP_DIR))

from agent_graph import run_agent


EVAL_CASES_PATH = PROJECT_ROOT / "app" / "eval" / "eval_cases.json"
METRICS_PATH = PROJECT_ROOT / "app" / "outputs" / "metrics_report.json"
EVAL_SUMMARY_PATH = PROJECT_ROOT / "app" / "outputs" / "eval_summary.json"


def load_eval_cases() -> list[dict]:
    with open(EVAL_CASES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_latest_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {}

    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_one_case(eval_case: dict) -> dict:
    case_name = eval_case["case_name"]
    requirement = eval_case["requirement"]
    expected_keywords = eval_case.get("expected_keywords", [])

    print(f"\n正在评测：{case_name}")

    start_time = time.time()

    report = run_agent(requirement)

    elapsed_time = round(time.time() - start_time, 2)

    metrics = load_latest_metrics()

    keyword_hits = []

    for keyword in expected_keywords:
        if keyword in report:
            keyword_hits.append(keyword)

    keyword_hit_rate = (
        round(len(keyword_hits) / len(expected_keywords) * 100, 2)
        if expected_keywords
        else 0
    )

    result = {
        "case_name": case_name,
        "elapsed_time_seconds": elapsed_time,
        "expected_keywords": expected_keywords,
        "keyword_hits": keyword_hits,
        "keyword_hit_rate": keyword_hit_rate,
        "metrics": metrics
    }

    print(f"完成：{case_name}")
    print(f"耗时：{elapsed_time} 秒")
    print(f"关键词命中率：{keyword_hit_rate}%")
    print(f"覆盖率：{metrics.get('coverage_rate', 0)}%")
    print(f"用例通过率：{metrics.get('pass_rate', 0)}%")

    return result


def summarize_results(results: list[dict]) -> dict:
    total = len(results)

    if total == 0:
        return {
            "total_eval_cases": 0,
            "message": "没有评测数据"
        }

    avg_keyword_hit_rate = round(
        sum(item["keyword_hit_rate"] for item in results) / total,
        2
    )

    avg_coverage_rate = round(
        sum(item["metrics"].get("coverage_rate", 0) for item in results) / total,
        2
    )

    avg_pass_rate = round(
        sum(item["metrics"].get("pass_rate", 0) for item in results) / total,
        2
    )

    avg_retry_count = round(
        sum(item["metrics"].get("retry_count", 0) for item in results) / total,
        2
    )

    total_llm_cases = sum(
        item["metrics"].get("llm_generated_cases", 0)
        for item in results
    )

    total_rule_cases = sum(
        item["metrics"].get("rule_generated_cases", 0)
        for item in results
    )

    summary = {
        "total_eval_cases": total,
        "avg_keyword_hit_rate": avg_keyword_hit_rate,
        "avg_coverage_rate": avg_coverage_rate,
        "avg_pass_rate": avg_pass_rate,
        "avg_retry_count": avg_retry_count,
        "total_llm_generated_cases": total_llm_cases,
        "total_rule_generated_cases": total_rule_cases,
        "details": results
    }

    return summary


def save_eval_summary(summary: dict) -> None:
    EVAL_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(EVAL_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def main():
    eval_cases = load_eval_cases()

    results = []

    for eval_case in eval_cases:
        result = evaluate_one_case(eval_case)
        results.append(result)

    summary = summarize_results(results)
    save_eval_summary(summary)

    print("\n评测完成")
    print(f"总任务数：{summary['total_eval_cases']}")
    print(f"平均关键词命中率：{summary['avg_keyword_hit_rate']}%")
    print(f"平均覆盖率：{summary['avg_coverage_rate']}%")
    print(f"平均用例通过率：{summary['avg_pass_rate']}%")
    print(f"平均重试次数：{summary['avg_retry_count']}")
    print(f"评测结果已保存：{EVAL_SUMMARY_PATH}")


if __name__ == "__main__":
    main()