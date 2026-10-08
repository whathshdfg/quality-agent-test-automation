from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from openai import OpenAI


MAX_HTML_BYTES = 300_000
MAX_CURRENT_HTML_CHARS = 180_000


@dataclass(frozen=True)
class GeneratedApp:
    summary: str
    html: str


SYSTEM_PROMPT = """
你是 Quality Agent Studio 的应用生成智能体。你的任务是生成一个真正可操作的单页网页应用。

必须遵守：
1. 只返回 JSON 对象，不要 Markdown，不要解释文字。
2. JSON 格式为 {"summary":"本次实现说明","files":[{"path":"index.html","content":"完整代码"}]}。
3. 只能生成一个 index.html，CSS 和 JavaScript 全部内联，不使用 npm、CDN、远程图片或其他外部依赖。
4. 应用必须有真实交互、完整空状态、输入校验和清晰反馈，并适配桌面与手机。
5. 不得使用 fetch、XMLHttpRequest、WebSocket、EventSource、iframe、object、embed、window.parent、window.top 或 document.cookie。
6. 不得使用 localStorage 或 sessionStorage。需要持久化时，使用异步接口：
   await window.demoStorage.get('key')
   await window.demoStorage.set('key', value)
   await window.demoStorage.remove('key')
7. 所有按钮都必须可用，不要展示虚假加载、虚假成功或虚假模型过程。
8. 生成适合真实演示的产品界面，使用系统字体、CSS 和 Unicode 符号；不依赖外部图标。
9. JavaScript 必须直接在浏览器运行，不允许模块导入或构建步骤。
""".strip()


def build_prompt(
    requirement: str,
    instruction: str,
    current_html: str | None,
) -> str:
    if current_html:
        return f"""
请根据追加要求修改现有应用，并保留没有被要求移除的功能。

原始需求：
{requirement}

追加要求：
{instruction or '修复并完善当前应用'}

当前 index.html：
{current_html[:MAX_CURRENT_HTML_CHARS]}

返回完整的新 index.html，而不是补丁。返回内容必须是合法 JSON。
""".strip()
    return f"""
请根据以下需求生成可运行的单页应用：

{requirement}

请自行补齐合理的交互细节，但不要添加与需求冲突的业务规则。返回内容必须是合法 JSON。
""".strip()


def build_repair_prompt(raw_output: str, errors: list[str]) -> str:
    return f"""
上一次生成结果未通过安全与结构校验。请修复全部问题，返回完整 JSON。

校验错误：
{json.dumps(errors, ensure_ascii=False)}

上一次结果：
{raw_output[:MAX_CURRENT_HTML_CHARS]}
""".strip()


def call_model(prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("服务端未配置 OPENAI_API_KEY，暂时无法调用生成模型")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
        timeout=120,
    )
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("模型返回内容为空")
    return content


def parse_generated_app(raw_output: str) -> GeneratedApp:
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"模型没有返回合法 JSON：{exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ValueError("模型结果必须是 JSON 对象")
    summary = payload.get("summary")
    files = payload.get("files")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("模型结果缺少 summary")
    if not isinstance(files, list) or len(files) != 1:
        raise ValueError("模型必须只返回一个 index.html 文件")
    file_data = files[0]
    if not isinstance(file_data, dict) or file_data.get("path") != "index.html":
        raise ValueError("生成文件路径必须是 index.html")
    html = file_data.get("content")
    if not isinstance(html, str):
        raise ValueError("index.html 内容必须是字符串")
    return GeneratedApp(summary=summary.strip()[:1000], html=html.strip())


def validate_generated_app(app: GeneratedApp) -> list[str]:
    html = app.html
    lowered = html.lower()
    errors: list[str] = []
    if len(html.encode("utf-8")) > MAX_HTML_BYTES:
        errors.append("index.html 超过 300 KB")
    if len(html) < 400:
        errors.append("index.html 内容过短，无法构成完整应用")
    for required in ("<html", "<body", "<script"):
        if required not in lowered:
            errors.append(f"index.html 缺少 {required} 结构")

    forbidden_patterns = {
        r"<\s*iframe\b": "不允许生成 iframe",
        r"<\s*(object|embed)\b": "不允许生成 object 或 embed",
        r"<\s*script[^>]+src\s*=": "不允许加载外部脚本",
        r"\b(fetch|xmlhttprequest|websocket|eventsource)\s*\(": "不允许发起网络请求",
        r"\bwindow\s*\.\s*(parent|top)\b": "不允许访问宿主窗口",
        r"\bdocument\s*\.\s*cookie\b": "不允许访问 Cookie",
        r"(?:\bwindow\s*\.\s*)?\b(localstorage|sessionstorage)\s*(?:\.|\[)": "请使用 window.demoStorage 持久化数据",
        r"(?:src|href)\s*=\s*[\"']\s*https?://": "不允许引用远程资源",
    }
    for pattern, message in forbidden_patterns.items():
        if re.search(pattern, html, flags=re.IGNORECASE):
            errors.append(message)
    return errors
