#连接LLM 应用与外部知识库
from pathlib import Path


def load_documents() -> list[dict]:
    """
    读取 app/data 目录下的所有 Markdown 文档。
    返回格式：
    [
        {
            "source": "requirements.md",
            "content": "文档内容..."
        }
    ]
    """

    data_dir = Path("app/data")
    documents = []

    for file_path in data_dir.glob("*.md"):
        with open(file_path, "r", encoding="utf-8") as f:
            documents.append({
                "source": file_path.name,
                "content": f.read()
            })

    return documents


def calculate_score(query: str, content: str) -> int:
    """
    根据关键词重合度计算相关性分数。
    这是轻量级检索，后面可以升级成向量检索。
    """

    keywords = [
        "订单", "取消", "支付", "创建", "司机", "用户",
        "接口", "异常", "测试", "用例", "Bug", "缺陷",
        "状态", "超时", "重复", "资源", "日志"
    ]

    score = 0

    for keyword in keywords:
        if keyword in query and keyword in content:
            score += 2

    # 如果用户输入中的词直接出现在文档里，也加分
    for char in query:
        if char in content:
            score += 1

    return score


def retrieve_context(query: str, top_k: int = 3) -> list[dict]:
    """
    根据用户需求，从知识库中检索最相关的文档。
    """

    documents = load_documents()
    scored_docs = []

    for doc in documents:
        score = calculate_score(query, doc["content"])

        if score > 0:
            scored_docs.append({
                "source": doc["source"],
                "content": doc["content"],
                "score": score
            })

    scored_docs.sort(key=lambda x: x["score"], reverse=True)

    return scored_docs[:top_k]