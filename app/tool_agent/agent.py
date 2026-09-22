import json
import os

import requests
from dotenv import load_dotenv

from app.tool_agent.tools import TOOLS, TOOL_REGISTRY


load_dotenv()

def dispatch_tool_call(tool_call: dict) -> dict:
    function_info = tool_call["function"]

    tool_name = function_info["name"]

    try:
        arguments = json.loads(
            function_info.get("arguments", "{}")
        )
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "tool_name": tool_name,
            "error_type": "arguments_parse_error",
            "error": str(e)
        }

    tool_function = TOOL_REGISTRY.get(tool_name)

    if tool_function is None:
        return {
            "success": False,
            "tool_name": tool_name,
            "error_type": "unknown_tool",
            "error": f"未知工具: {tool_name}"
        }

    try:
        return tool_function(**arguments)

    except Exception as e:
        return {
            "success": False,
            "tool_name": tool_name,
            "error_type": "tool_execution_error",
            "error": str(e)
        }

def call_llm(messages: list[dict]) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "thinking": {
                "type": "disabled"
            }
        },
        timeout=60
    )

    if not response.ok:
        print("\n===== API Error =====")
        print(response.text)

    response.raise_for_status()

    return response.json()

def run_tool_agent(
    user_question: str,
    max_iterations: int = 5
) -> str:

    messages = [
        {
            "role": "user",
            "content": user_question
        }
    ]

    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        print(
            f"\n===== Agent Iteration {iteration} ====="
        )

        result = call_llm(messages)

        message = result["choices"][0]["message"]

        tool_calls = message.get(
            "tool_calls",
            []
        )

        # 没有 Tool Call，说明得到最终答案
        if not tool_calls:
            return message.get("content", "")

        # 保存 assistant 的 Tool Call 请求
        messages.append(message)

        # 执行这一轮所有 Tool
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]

            print("\n===== Selected Tool =====")
            print(tool_name)

            tool_result = dispatch_tool_call(
                tool_call
            )

            if not tool_result.get(
                "success",
                False
            ):
                print("\n===== Tool Error =====")
                print(
                    json.dumps(
                        tool_result,
                        ensure_ascii=False,
                        indent=2
                    )
                )

            # 每个 Tool Call 都必须写回对应结果
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(
                        tool_result,
                        ensure_ascii=False
                    )
                }
            )

    return (
        "Agent 达到最大执行轮数，"
        "为避免无限循环已停止。"
    )