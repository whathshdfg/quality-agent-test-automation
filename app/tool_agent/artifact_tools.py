import json

from app.core.config import METRICS_FILE, REPORT_FILE, TRACE_FILE


def get_metrics() -> dict:
    if not METRICS_FILE.exists():
        return {
            "success": False,
            "error": f"{METRICS_FILE.name} does not exist.",
        }
    return {
        "success": True,
        "metrics": json.loads(METRICS_FILE.read_text(encoding="utf-8")),
    }


def get_trace() -> dict:
    if not TRACE_FILE.exists():
        return {
            "success": False,
            "error": f"{TRACE_FILE.name} does not exist.",
        }
    return {
        "success": True,
        "trace": json.loads(TRACE_FILE.read_text(encoding="utf-8")),
    }


def get_report() -> dict:
    if not REPORT_FILE.exists():
        return {
            "success": False,
            "error": f"{REPORT_FILE.name} does not exist.",
        }
    return {
        "success": True,
        "report": REPORT_FILE.read_text(encoding="utf-8"),
    }
