"""
 LangGraph 开发的自动化测试生成智能 Agent，
 专门用于接口 / 功能测试全流程自动化，
 输入产品需求，自动输出完整测试报告
 """
from typing import TypedDict, List, Dict
from langgraph.graph import StateGraph, END

from app.rag_retriever import retrieve_context
from app.tools.case_generator import generate_test_cases
from app.tools.api_test_tool import run_api_tests
from app.tools.log_analysis_tool import analyze_failed_cases
from app.tools.report_tool import generate_report
from app.tools.coverage_tool import analyze_test_coverage
from app.tools.case_enhancer import enhance_test_cases
from app.tools.trace_tool import add_trace, save_trace
from app.tools.metrics_tool import calculate_metrics, format_metrics_markdown, save_metrics


class AgentState(TypedDict):
    requirement: str
    rag_context: List[Dict]
    test_cases: List[Dict]
    coverage_result: Dict
    test_results: List[Dict]
    bug_analysis: List[Dict]
    report: str
    retry_count: int
    max_retries: int
    retry_history: List[Dict]
    trace: List[Dict]
    metrics: Dict
    enhancement_stop_reason: str


def retrieve_node(state: AgentState) -> AgentState:
    print("Agent 节点 1：知识库检索")

    state["rag_context"] = retrieve_context(
        query=state["requirement"],
        top_k=3
    )

    state = add_trace(
        state,
        node_name="retrieve",
        action="知识库检索",
        detail={
            "retrieved_docs_count": len(state["rag_context"]),
            "retrieved_sources": [
                item.get("source") for item in state["rag_context"]
            ]
        }
    )

    return state


def generate_cases_node(state: AgentState) -> AgentState:
    print("Agent 节点 2：测试用例生成")

    rag_text = ""

    for item in state["rag_context"]:
        rag_text += f"\n来源：{item['source']}\n"
        rag_text += item["content"] + "\n"

    enhanced_requirement = (
        state["requirement"]
        + "\n\n以下是知识库检索到的相关资料：\n"
        + rag_text
    )

    state["test_cases"] = generate_test_cases(enhanced_requirement)

    llm_count = len([
        case for case in state["test_cases"]
        if case.get("generation_source") == "llm"
    ])

    rule_count = len([
        case for case in state["test_cases"]
        if case.get("generation_source") == "rule"
    ])

    state = add_trace(
        state,
        node_name="generate_cases",
        action="生成测试用例",
        detail={
            "test_cases_count": len(state["test_cases"]),
            "llm_generated_cases": llm_count,
            "rule_generated_cases": rule_count,
            "case_ids": [
                case.get("case_id") for case in state["test_cases"]
            ]
        }
    )

    return state


def coverage_node(state: AgentState) -> AgentState:
    print("Agent 节点 3：测试覆盖率分析")

    state["coverage_result"] = analyze_test_coverage(
        requirement=state["requirement"],
        test_cases=state["test_cases"]
    )

    print(f"当前覆盖率：{state['coverage_result']['coverage_rate']}%")

    if state["retry_history"]:
        latest_retry = state["retry_history"][-1]
        if "coverage_after" not in latest_retry:
            coverage_after = state["coverage_result"].get("coverage_rate", 0)
            latest_retry["coverage_after"] = coverage_after

            if (
                latest_retry.get("added_cases")
                and coverage_after <= latest_retry.get("coverage_before", 0)
            ):
                state["enhancement_stop_reason"] = "本轮已新增用例，但覆盖率没有提升，停止无效增强"

    state = add_trace(
        state,
        node_name="coverage",
        action="测试覆盖率分析",
        detail={
            "coverage_rate": state["coverage_result"].get("coverage_rate"),
            "covered_dimensions": state["coverage_result"].get("covered_dimensions"),
            "total_dimensions": state["coverage_result"].get("total_dimensions"),
            "missing_dimensions": state["coverage_result"].get("missing_dimensions", [])
        }
    )

    return state


def should_retry_or_continue(state: AgentState) -> str:
    """
    根据覆盖率判断是否需要自动补充测试用例。
    """

    coverage_rate = state["coverage_result"].get("coverage_rate", 0)
    missing_dimensions = state["coverage_result"].get("missing_dimensions", [])

    coverage_threshold = 90

    if (
        coverage_rate < coverage_threshold
        and len(missing_dimensions) > 0
        and state["retry_count"] < state["max_retries"]
        and not state.get("enhancement_stop_reason")
    ):
        print("覆盖率不足，进入自动补充测试用例节点")
        return "enhance_cases"

    print("覆盖率满足要求、已达到最大重试次数或已触发无进展退出，进入测试执行节点")
    return "run_tests"


def enhance_cases_node(state: AgentState) -> AgentState:
    print("Agent 节点 4：自动补充测试用例")

    coverage_before = state["coverage_result"].get("coverage_rate", 0)
    missing_dimensions = state["coverage_result"].get("missing_dimensions", [])

    enhanced_cases, added_cases = enhance_test_cases(
        requirement=state["requirement"],
        test_cases=state["test_cases"],
        coverage_result=state["coverage_result"]
    )

    state["test_cases"] = enhanced_cases
    state["retry_count"] += 1

    stop_reason = ""
    if not added_cases:
        stop_reason = "本轮未新增测试用例，停止无效增强"
        state["enhancement_stop_reason"] = stop_reason

    state["retry_history"].append({
        "retry_round": state["retry_count"],
        "coverage_before": coverage_before,
        "missing_dimensions": missing_dimensions,
        "added_cases": added_cases,
        "stop_reason": stop_reason
    })

    print(f"本次新增测试用例数：{len(added_cases)}")

    state = add_trace(
        state,
        node_name="enhance_cases",
        action="自动补充测试用例",
        detail={
            "retry_round": state["retry_count"],
            "coverage_before": coverage_before,
            "missing_dimensions": missing_dimensions,
            "added_cases_count": len(added_cases),
            "added_case_ids": [
                item["added_case"].get("case_id")
                for item in added_cases
            ],
            "stop_reason": stop_reason
        }
    )

    return state


def run_tests_node(state: AgentState) -> AgentState:
    print("Agent 节点 5：执行接口测试工具")

    state["test_results"] = run_api_tests(state["test_cases"])

    passed_count = len([
        result for result in state["test_results"]
        if result.get("status") == "passed"
    ])

    failed_count = len([
        result for result in state["test_results"]
        if result.get("status") == "failed"
    ])

    state = add_trace(
        state,
        node_name="run_tests",
        action="真实接口测试执行",
        detail={
            "total_results": len(state["test_results"]),
            "passed_count": passed_count,
            "failed_count": failed_count,
            "failed_case_ids": [
                result.get("case_id")
                for result in state["test_results"]
                if result.get("status") == "failed"
            ]
        }
    )

    return state


def analyze_node(state: AgentState) -> AgentState:
    print("Agent 节点 6：缺陷分析")

    state["bug_analysis"] = analyze_failed_cases(state["test_results"])

    state = add_trace(
        state,
        node_name="analyze",
        action="失败用例缺陷分析",
        detail={
            "bug_count": len(state["bug_analysis"]),
            "bug_case_ids": [
                bug.get("case_id") for bug in state["bug_analysis"]
            ]
        }
    )

    return state


def report_node(state: AgentState) -> AgentState:
    print("Agent 节点 7：生成测试报告与指标报告")

    state["report"] = generate_report(
        requirement=state["requirement"],
        test_cases=state["test_cases"],
        test_results=state["test_results"],
        bug_analysis=state["bug_analysis"],
        rag_context=state["rag_context"],
        coverage_result=state["coverage_result"],
        retry_history=state["retry_history"]
    )

    state["metrics"] = calculate_metrics(state)

    state["report"] += format_metrics_markdown(state["metrics"])

    state = add_trace(
        state,
        node_name="report",
        action="生成测试报告、执行链路和指标报告",
        detail={
            "report_file": "app/outputs/test_report.md",
            "trace_file": "app/outputs/execution_trace.json",
            "metrics_file": "app/outputs/metrics_report.json"
        }
    )

    save_metrics(state["metrics"])
    save_trace(state["trace"])

    return state


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate_cases", generate_cases_node)
    graph.add_node("coverage", coverage_node)
    graph.add_node("enhance_cases", enhance_cases_node)
    graph.add_node("run_tests", run_tests_node)
    graph.add_node("analyze", analyze_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("retrieve")

    graph.add_edge("retrieve", "generate_cases")
    graph.add_edge("generate_cases", "coverage")

    graph.add_conditional_edges(
        "coverage",
        should_retry_or_continue,
        {
            "enhance_cases": "enhance_cases",
            "run_tests": "run_tests"
        }
    )

    graph.add_edge("enhance_cases", "coverage")
    graph.add_edge("run_tests", "analyze")
    graph.add_edge("analyze", "report")
    graph.add_edge("report", END)

    return graph.compile()


def run_agent(requirement: str) -> str:
    app = build_graph()

    initial_state = {
        "requirement": requirement,
        "rag_context": [],
        "test_cases": [],
        "coverage_result": {},
        "test_results": [],
        "bug_analysis": [],
        "report": "",
        "retry_count": 0,
        "max_retries": 2,
        "retry_history": [],
        "trace": [],
        "metrics": {},
        "enhancement_stop_reason": ""
    }

    final_state = app.invoke(initial_state)

    return final_state["report"]
