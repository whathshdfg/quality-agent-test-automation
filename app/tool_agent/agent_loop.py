import json
import os

import requests
from dotenv import load_dotenv

from app.tool_agent.registry import TOOL_REGISTRY
from app.tool_agent.schemas import TOOL_SCHEMAS


load_dotenv()


TOOL_SELECTION_RULES = """
Tool selection rules:
- Current single-run metrics: get_metrics
- Current execution trace: get_trace
- Current report: get_report
- Recent N runs, history, trends, previous-run summaries: get_run_history
- Details for a specified run_id: get_run_detail
Do not combine get_metrics, get_trace, and get_report to answer history questions.
"""


def dispatch_tool_call(tool_call: dict) -> dict:
    function_info = tool_call["function"]
    tool_name = function_info["name"]

    try:
        arguments = json.loads(
            function_info.get("arguments", "{}")
        )
    except json.JSONDecodeError as exc:
        return {
            "success": False,
            "tool_name": tool_name,
            "error_type": "arguments_parse_error",
            "error": str(exc),
        }

    tool_function = TOOL_REGISTRY.get(tool_name)

    if tool_function is None:
        return {
            "success": False,
            "tool_name": tool_name,
            "error_type": "unknown_tool",
            "error": f"unknown tool: {tool_name}",
        }

    try:
        return tool_function(**arguments)
    except Exception as exc:
        return {
            "success": False,
            "tool_name": tool_name,
            "error_type": "tool_execution_error",
            "error": str(exc),
        }


def call_llm(messages: list[dict]) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL")

    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "thinking": {
                "type": "disabled",
            },
        },
        timeout=60,
    )

    if not response.ok:
        print("\n===== API Error =====")
        print(response.text)

    response.raise_for_status()
    return response.json()


def run_tool_agent(
    user_question: str,
    max_iterations: int = 5,
) -> str:
    messages = [
        {
            "role": "system",
            "content": TOOL_SELECTION_RULES,
        },
        {
            "role": "user",
            "content": user_question,
        },
    ]

    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        result = call_llm(messages)
        message = result["choices"][0]["message"]
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            return message.get("content", "")

        messages.append(message)

        for tool_call in tool_calls:
            tool_result = dispatch_tool_call(tool_call)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

    return "Agent reached the maximum tool-call iterations and stopped."
