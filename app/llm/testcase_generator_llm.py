#LLM 测试用例生成器
import openai  # 或你用的任意LLM接口


def generate_testcases_with_llm(requirement: str, rag_context: str) -> list[dict]:
    """
    使用大模型生成测试用例
    """

    prompt = f"""
你是一个资深测试工程师，请根据以下需求生成测试用例。

要求：
1. 覆盖正常场景
2. 覆盖异常场景
3. 覆盖边界场景
4. 覆盖重复操作
5. 覆盖状态一致性
6. 覆盖资源释放

需求：
{requirement}

参考资料：
{rag_context}

输出格式必须是JSON数组，每个用例包含：
case_id, title, precondition, steps, expected_result
"""

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    text = response["choices"][0]["message"]["content"]

    return eval(text)  # 初学版（后面可以换json.loads）