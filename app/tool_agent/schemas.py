TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": (
                "Read metrics for the current/latest single Agent run from the "
                "snapshot file. Use for current run metrics only, not history."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace",
            "description": (
                "Read the execution trace for the current/latest single Agent run "
                "from the snapshot file. Use for current run trace only."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_report",
            "description": (
                "Read the report for the current/latest single Agent run from the "
                "snapshot file. Use for current run report only."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_run_history",
            "description": (
                "Query SQLite for recent N runs, historical records, comparisons, "
                "trend analysis, pass-rate changes, failed-case changes, and status "
                "summaries. Use this for history; do not combine get_metrics, "
                "get_trace, or get_report to answer history questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10,
                    },
                    "status": {
                        "type": "string",
                        "enum": ["running", "completed", "failed"],
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_run_detail",
            "description": (
                "Query SQLite for one complete Agent run by run_id, including "
                "metrics, trace, report, and error_message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "The Agent run_id primary key.",
                    },
                },
                "required": ["run_id"],
            },
        },
    },
]
