from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "quality_agent.db"
OUTPUT_DIR = PROJECT_ROOT / "app" / "outputs"

METRICS_FILE = OUTPUT_DIR / "v2_metrics_report.json"
TRACE_FILE = OUTPUT_DIR / "v2_execution_trace.json"
REPORT_FILE = OUTPUT_DIR / "v2_test_report.md"

V1_METRICS_FILE = OUTPUT_DIR / "metrics_report.json"
V1_TRACE_FILE = OUTPUT_DIR / "execution_trace.json"
V1_REPORT_FILE = OUTPUT_DIR / "test_report.md"
