"""Measure end-to-end Agent workflow latency with time.perf_counter()."""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_graph import run_agent  # noqa: E402


DEFAULT_REQUIREMENT = """
用户主动取消未接单订单后，订单状态变为 cancelled。
如果订单创建后 3 分钟内没有司机接单，系统自动取消订单。
如果司机已接单，用户取消订单时必须记录取消原因。
订单取消后司机资源应释放。
"""


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = min(len(values) - 1, max(0, round((pct / 100) * (len(values) - 1))))
    return values[index]


def main() -> int:
    runs = int(os.getenv("AGENT_PERF_RUNS", "10"))
    output_path = PROJECT_ROOT / "reports" / "agent_performance_eval.json"
    results = []

    for run_id in range(1, runs + 1):
        started = time.perf_counter()
        try:
            run_agent(DEFAULT_REQUIREMENT)
            duration = round(time.perf_counter() - started, 4)
            results.append(
                {
                    "run_id": run_id,
                    "duration_seconds": duration,
                    "success": True,
                    "failed_node": "",
                    "error": "",
                }
            )
        except Exception as exc:
            duration = round(time.perf_counter() - started, 4)
            results.append(
                {
                    "run_id": run_id,
                    "duration_seconds": duration,
                    "success": False,
                    "failed_node": "current project unable to identify failed node without runtime trace",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    durations = [item["duration_seconds"] for item in results]
    successes = [item for item in results if item["success"]]
    summary = {
        "total_runs": runs,
        "successful_runs": len(successes),
        "average_seconds": round(statistics.mean(durations), 4) if durations else 0,
        "p50_seconds": percentile(durations, 50),
        "p95_seconds": percentile(durations, 95),
        "min_seconds": min(durations) if durations else 0,
        "max_seconds": max(durations) if durations else 0,
        "results": results,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False, indent=2))
    print(f"Saved: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
