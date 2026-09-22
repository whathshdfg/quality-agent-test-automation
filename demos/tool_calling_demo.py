
import json
from pathlib import Path
import os
import requests
from dotenv import load_dotenv

load_dotenv()
def get_metrics() -> dict:
    """
    读取最近一次 V2 Agent 执行生成的指标。
    """
    metrics_path = Path(
        "app/outputs/v2_metrics_report.json"
    )
    if not metrics_path.exists():
        return {
            "success": False,
            "error": "v2_metrics_report.json 不存在"
        }
    with open(
        metrics_path,
        "r",
        encoding="utf-8"
    ) as file:
        metrics = json.load(file)
    return {
        "success": True,
        "metrics": metrics
    }

def get_trace() -> dict:
    """
    读取最近一次 V2 Agent 的执行链路。
    """
    trace_path = Path(
        "app/outputs/v2_execution_trace.json"
    )
    if not trace_path.exists():
        return {
            "success": False,
            "error": "v2_execution_trace.json 不存在"
        }
    with open(
        trace_path,
        "r",
        encoding="utf-8"
    ) as file:
        trace = json.load(file)
    return {
        "success": True,
        "trace": trace
    }

def get_report() -> dict:
    """
    读取最近一次 V2 Agent 生成的完整测试报告。
    """
    report_path = Path(
        "app/outputs/v2_test_report.md"
    )
    if not report_path.exists():
        return {
            "success": False,
            "error": "v2_test_report.md 不存在"
        }
    with open(
        report_path,
        "r",
        encoding="utf-8"
    ) as file:
        report = file.read()
    return {
        "success": True,
        "report": report
    }

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_metrics",
            "description": (
                "读取最近一次测试智能化 Agent 执行的指标数据，"
                "包括测试用例数量、通过率、失败数量、"
                "需求覆盖率、参数覆盖率、风险覆盖率等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trace",
            "description": (
                "读取最近一次测试智能化 Agent 的执行链路，"
                "用于查询 Agent 执行了哪些节点、"
                "节点执行顺序以及各节点执行状态。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_report",
            "description": (
                "读取最近一次测试智能化 Agent 生成的完整测试报告，"
                "包括测试需求、需求规则、测试点、覆盖矩阵、"
                "测试执行结果、失败分析和运行指标。"
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]


def call_llm(messages: list[dict]) -> dict:
    api_key=os.getenv("OPENAI_API_KEY")
    base_url=os.getenv("OPENAI_BASE_URL")
    model=os.getenv("OPENAI_MODEL")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": messages,
            "tools": TOOLS,
            "thinking": {
                "type": "disabled"}
        },
        timeout=60
    )
    if not response.ok:
        print("\n===== API Error =====")
        print(response.text)
    response.raise_for_status()
    return response.json()

TOOL_REGISTRY = {
    "get_metrics": get_metrics,
    "get_trace": get_trace,
    "get_report": get_report
}



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
        result = tool_function(**arguments)
        return result
    except Exception as e:
        return {
            "success": False,
            "tool_name": tool_name,
            "error_type": "tool_execution_error",
            "error": str(e)
        }

if __name__ == "__main__":
    user_question = input("请输入问题：")
    messages = [
        {
            "role": "user",
            "content": user_question
        }
    ]
    max_iterations = 5
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        # 1. 调用 LLM
        result = call_llm(messages)
        message = result["choices"][0]["message"]
        # 2. 获取这一轮 LLM 请求的所有 Tool Calls
        tool_calls = message.get("tool_calls", [])
        # 3. 如果没有 Tool Call，说明模型已经得到最终答案
        if not tool_calls:
            print("\n===== Final Answer =====")
            print(message.get("content", ""))
            break
        # 4. 先把 assistant 的完整 tool_calls 消息保存下来
        messages.append(message)
        # 5. 遍历这一轮的所有 Tool Calls
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            print("\n===== Selected Tool =====")
            print(tool_name)
            # 6. Dispatcher 执行真正的 Python Tool
            tool_result = dispatch_tool_call(
                tool_call
            )
            print("\n===== Tool Result =====")
            print(
                json.dumps(
                    tool_result,
                    ensure_ascii=False,
                    indent=2
                )
            )
            # 7. 每一个 Tool Call 都必须有自己的 Tool Result
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
    else:
       print(
        "\n Agent达到最大工具调用轮数，"
        "为避免无限循环已停止执行。"
       )