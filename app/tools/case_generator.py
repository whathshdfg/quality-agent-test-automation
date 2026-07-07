import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from app.tools.case_generator_rule import generate_rule_based_test_cases


load_dotenv()


def extract_json_array(text: str) -> list[dict]:
    """
    从大模型输出中提取 JSON 数组。

    大模型有时会输出：
    ```json
    [...]
    ```

    这个函数负责把真正的 JSON 数组提取出来。
    """

    text = text.strip()

    # 去掉 markdown 代码块
    text = re.sub(r"^```json", "", text)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    text = text.strip()

    # 尝试直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 如果直接解析失败，就从文本中截取第一个 [ 到最后一个 ]
    start = text.find("[")
    end = text.rfind("]")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("大模型输出中没有找到 JSON 数组")

    json_text = text[start:end + 1]
    data = json.loads(json_text)

    if not isinstance(data, list):
        raise ValueError("大模型输出不是 JSON 数组")

    return data


def validate_test_cases(data: Any) -> list[dict]:
    """
    校验大模型生成的测试用例格式。
    每条测试用例必须包含：
    case_id、title、precondition、steps、expected_result
    """

    if not isinstance(data, list):
        raise ValueError("测试用例必须是列表")

    required_fields = [
        "case_id",
        "title",
        "precondition",
        "steps",
        "expected_result"
    ]

    validated_cases = []

    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"第 {index} 条测试用例不是字典格式")

        for field in required_fields:
            if field not in item:
                raise ValueError(f"第 {index} 条测试用例缺少字段：{field}")

        if not isinstance(item["steps"], list):
            raise ValueError(f"第 {index} 条测试用例的 steps 必须是列表")

        item["generation_source"] = "llm"
        validated_cases.append(item)

    if len(validated_cases) == 0:
        raise ValueError("大模型没有生成任何测试用例")

    return validated_cases


def build_prompt(requirement: str) -> str:
    """
    构造给大模型的提示词。
    这里的 requirement 已经包含：
    1. 用户输入的需求
    2. RAG 检索到的相关资料
    """

    return f"""
你是一个资深测试开发工程师，正在为网约车业务设计自动化测试用例。

请根据下面的需求和相关资料，生成结构化测试用例。

要求：
1. 只输出 JSON 数组，不要输出解释文字，不要使用 Markdown。
2. 每条测试用例必须包含以下字段：
   - case_id
   - title
   - precondition
   - steps
   - expected_result
3. steps 必须是字符串数组。
4. 测试用例要尽量覆盖：
   - 正常场景
   - 异常场景
   - 边界场景
   - 重复操作
   - 状态变更校验
   - 资源释放校验
   - 数据一致性校验
5. 如果是订单取消场景，优先使用这些用例编号：
   - TC_CANCEL_001 用户主动取消未接单订单
   - TC_CANCEL_002 订单超时自动取消
   - TC_CANCEL_003 司机已接单后用户取消订单
   - TC_CANCEL_004 订单取消后司机资源释放校验
6. 如果是支付场景，优先使用这些用例编号：
   - TC_PAY_001 订单正常支付成功
   - TC_PAY_002 重复支付拦截
7. 如果是订单创建场景，优先使用这些用例编号：
   - TC_ORDER_001 正常创建订单
   - TC_ORDER_002 起点为空时创建订单失败

下面是需求和相关资料：

{requirement}

请直接输出 JSON 数组。
"""


def generate_cases_by_llm(requirement: str) -> list[dict]:
    """
    调用大模型生成测试用例。
    """

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    if not api_key:
        raise ValueError("未配置 OPENAI_API_KEY")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL")
    )
    prompt = build_prompt(requirement)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是一个严谨的测试开发工程师，只输出符合要求的 JSON。"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    output_text = response.choices[0].message.content

    raw_cases = extract_json_array(output_text)
    test_cases = validate_test_cases(raw_cases)

    return test_cases


def generate_test_cases(requirement: str) -> list[dict]:
    """
    V6 总入口：
    优先使用大模型生成测试用例。
    如果失败，则自动回退到规则生成。
    """

    try:
        print("正在使用大模型生成测试用例...")
        test_cases = generate_cases_by_llm(requirement)
        print(f"大模型生成成功，共生成 {len(test_cases)} 条测试用例")
        return test_cases

    except Exception as e:
        print(f"大模型生成失败，自动回退到规则生成。原因：{e}")
        return generate_rule_based_test_cases(requirement)
