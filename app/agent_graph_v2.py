"""V2 LangGraph for structured test design under Harness constraints."""

from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from app.harness.test_case_planner import plan_test_cases
from app.harness.structured_executor import execute_structured_cases
from app.models.test_design import (
    CoverageMatrix,
    RequirementRule,
    TestPoint,
)
from app.rag_retriever import retrieve_context
from app.tools.coverage_matcher import build_keyword_coverage_matrix
from app.tools.requirement_analyzer import analyze_requirement
from app.tools.semantic_coverage_matcher import build_semantic_coverage_matrix
from app.tools.test_point_enhancer import actionable_gaps, enhance_test_points
from app.tools.test_point_generator import generate_test_points
from app.tools.report_v2 import (
    calculate_v2_metrics,
    generate_v2_report,
    save_v2_outputs,
)
from app.tools.log_analysis_v2 import analyze_v2_failures
from app.models.test_design import TestCaseSpec
from app.db.run_repository import RunRepository


ModelMode = Literal["api", "rule"]


class AgentV2State(TypedDict):
    run_id: str
    requirement: str
    model_mode: ModelMode
    rag_context: list[dict]
    requirement_rules: list[dict]
    requirement_source: str
    requirement_fallback_reason: str
    test_points: list[dict]
    test_point_source: str
    test_point_fallback_reason: str
    coverage_matrix: dict
    coverage_source: str
    coverage_fallback_reason: str
    enhancement_count: int
    max_enhancements: int
    enhancement_history: list[dict]
    enhancement_stop_reason: str
    test_cases: list[dict]
    unsupported_test_points: list[dict]
    planning_source: str
    planning_fallback_reason: str
    trace: list[dict]
    test_results: list[dict]
    report: str
    metrics: dict
    persist_outputs: bool
    bug_analysis: list[dict]


V2_CHECKPOINTER = InMemorySaver()


def _force_rule(_: str) -> str:
    raise RuntimeError("V2 rule mode")


def _call_fn(state: AgentV2State):
    return _force_rule if state["model_mode"] == "rule" else None


def _rules(state: AgentV2State) -> list[RequirementRule]:
    return [RequirementRule.model_validate(item) for item in state["requirement_rules"]]


def _points(state: AgentV2State) -> list[TestPoint]:
    return [TestPoint.model_validate(item) for item in state["test_points"]]


def _matrix(state: AgentV2State) -> CoverageMatrix:
    return CoverageMatrix.model_validate(state["coverage_matrix"])


def _trace(state: AgentV2State, node: str, detail: dict) -> list[dict]:
    return [*state["trace"], {
        "run_id": state["run_id"],
        "node_name": node,
        "status": "success",
        "detail": detail,
    }]


def retrieve_node(state: AgentV2State) -> dict:
    context = retrieve_context(state["requirement"], top_k=3)
    return {
        "rag_context": context,
        "trace": _trace(state, "retrieve", {
            "document_count": len(context),
            "sources": [item.get("source") for item in context],
        }),
    }


def analyze_requirements_node(state: AgentV2State) -> dict:
    context_text = "\n\n".join(
        f"来源: {item['source']}\n{item['content']}"
        for item in state["rag_context"]
    )
    analysis_input = state["requirement"]
    if context_text:
        analysis_input += f"\n\n相关知识库资料:\n{context_text}"

    result = analyze_requirement(
        analysis_input,
        call_fn=_call_fn(state),
        fallback_requirement=state["requirement"],
    )
    serialized = [rule.model_dump(mode="json") for rule in result["rules"]]
    return {
        "requirement_rules": serialized,
        "requirement_source": result["source"],
        "requirement_fallback_reason": result["fallback_reason"],
        "trace": _trace(state, "analyze_requirements", {
            "rule_count": len(serialized),
            "source": result["source"],
            "rule_ids": [item["rule_id"] for item in serialized],
        }),
    }


def generate_test_points_node(state: AgentV2State) -> dict:
    result = generate_test_points(_rules(state), call_fn=_call_fn(state))
    serialized = [point.model_dump(mode="json") for point in result["test_points"]]
    return {
        "test_points": serialized,
        "test_point_source": result["source"],
        "test_point_fallback_reason": result["fallback_reason"],
        "trace": _trace(state, "generate_test_points", {
            "test_point_count": len(serialized),
            "source": result["source"],
        }),
    }


def coverage_matrix_node(state: AgentV2State) -> dict:
    rules = _rules(state)
    points = _points(state)
    if state["model_mode"] == "api":
        result = build_semantic_coverage_matrix(rules, points)
        matrix = result["matrix"]
        source = result["source"]
        fallback_reason = result["fallback_reason"]
    else:
        matrix, _ = build_keyword_coverage_matrix(rules, points)
        source = "deterministic"
        fallback_reason = ""

    serialized = matrix.model_dump(mode="json")
    return {
        "coverage_matrix": serialized,
        "coverage_source": source,
        "coverage_fallback_reason": fallback_reason,
        "trace": _trace(state, "coverage_matrix", {
            "requirement_rate": matrix.requirement_coverage.coverage_rate,
            "parameter_rate": matrix.parameter_coverage.coverage_rate,
            "risk_rate": matrix.risk_coverage.coverage_rate,
            "gap_count": len(matrix.gaps),
            "source": source,
        }),
    }


def route_after_coverage(state: AgentV2State) -> str:
    gaps = actionable_gaps(_matrix(state))
    if (
        gaps
        and state["enhancement_count"] < state["max_enhancements"]
        and not state["enhancement_stop_reason"]
    ):
        return "enhance_test_points"
    return "plan_test_cases"


def enhance_test_points_node(state: AgentV2State) -> dict:
    before = _matrix(state)
    result = enhance_test_points(
        _rules(state),
        _points(state),
        before,
        call_fn=_call_fn(state),
    )
    count = state["enhancement_count"] + 1
    history_item = {
        "round": count,
        "source": result["source"],
        "added_test_point_ids": [
            point.test_point_id for point in result["added_test_points"]
        ],
        "addressed_gap_ids": result["addressed_gap_ids"],
        "stop_reason": result["stop_reason"],
    }
    return {
        "test_points": [
            point.model_dump(mode="json") for point in result["test_points"]
        ],
        "coverage_matrix": result["matrix"].model_dump(mode="json"),
        "enhancement_count": count,
        "enhancement_history": [*state["enhancement_history"], history_item],
        "enhancement_stop_reason": result["stop_reason"],
        "trace": _trace(state, "enhance_test_points", history_item),
    }


def plan_test_cases_node(state: AgentV2State) -> dict:
    result = plan_test_cases(
        _rules(state),
        _points(state),
        call_fn=_call_fn(state),
    )
    serialized = [case.model_dump(mode="json") for case in result["test_cases"]]
    return {
        "test_cases": serialized,
        "unsupported_test_points": result["unsupported_test_points"],
        "planning_source": result["source"],
        "planning_fallback_reason": result["fallback_reason"],
        "trace": _trace(state, "plan_test_cases", {
            "case_count": len(serialized),
            "unsupported_count": len(result["unsupported_test_points"]),
            "source": result["source"],
        }),
    }


def build_design_graph():
    graph = StateGraph(AgentV2State)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("analyze_requirements", analyze_requirements_node)
    graph.add_node("generate_test_points", generate_test_points_node)
    graph.add_node("coverage_matrix", coverage_matrix_node)
    graph.add_node("enhance_test_points", enhance_test_points_node)
    graph.add_node("plan_test_cases", plan_test_cases_node)

    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "analyze_requirements")
    graph.add_edge("analyze_requirements", "generate_test_points")
    graph.add_edge("generate_test_points", "coverage_matrix")
    graph.add_conditional_edges(
        "coverage_matrix",
        route_after_coverage,
        {
            "enhance_test_points": "enhance_test_points",
            "plan_test_cases": "plan_test_cases",
        },
    )
    graph.add_edge("enhance_test_points", "coverage_matrix")
    graph.add_edge("plan_test_cases", END)
    return graph.compile()


def build_agent_graph_v2(operation_runner=None, checkpointer=None):
    graph = StateGraph(AgentV2State)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("analyze_requirements", analyze_requirements_node)
    graph.add_node("generate_test_points", generate_test_points_node)
    graph.add_node("coverage_matrix", coverage_matrix_node)
    graph.add_node("enhance_test_points", enhance_test_points_node)
    graph.add_node("plan_test_cases", plan_test_cases_node)

    def execute_node(state: AgentV2State) -> dict:
        cases = [TestCaseSpec.model_validate(item) for item in state["test_cases"]]
        if operation_runner is None:
            results = execute_structured_cases(cases)
        else:
            results = execute_structured_cases(cases, runner=operation_runner)
        return {
            "test_results": results,
            "trace": _trace(state, "execute_tests", {
                "total": len(results),
                "passed": sum(item["status"] == "passed" for item in results),
                "failed": sum(item["status"] == "failed" for item in results),
            }),
        }

    def analyze_failures_node(state: AgentV2State) -> dict:
        analyses = analyze_v2_failures(state["test_results"])
        return {
            "bug_analysis": analyses,
            "trace": _trace(state, "analyze_failures", {
                "bug_count": len(analyses),
                "case_ids": [item["case_id"] for item in analyses],
            }),
        }

    def report_node(state: AgentV2State) -> dict:
        metrics = calculate_v2_metrics(state)
        report = generate_v2_report(state, metrics)
        trace = _trace(state, "report", {
            "report_file": "app/outputs/v2_test_report.md",
            "metrics_file": "app/outputs/v2_metrics_report.json",
            "trace_file": "app/outputs/v2_execution_trace.json",
        })
        update = {"metrics": metrics, "report": report, "trace": trace}
        if state["persist_outputs"]:
            save_v2_outputs({**state, **update})
        return update

    graph.add_node("execute_tests", execute_node)
    graph.add_node("analyze_failures", analyze_failures_node)
    graph.add_node("report", report_node)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "analyze_requirements")
    graph.add_edge("analyze_requirements", "generate_test_points")
    graph.add_edge("generate_test_points", "coverage_matrix")
    graph.add_conditional_edges(
        "coverage_matrix",
        route_after_coverage,
        {
            "enhance_test_points": "enhance_test_points",
            "plan_test_cases": "plan_test_cases",
        },
    )
    graph.add_edge("enhance_test_points", "coverage_matrix")
    graph.add_edge("plan_test_cases", "execute_tests")
    graph.add_edge("execute_tests", "analyze_failures")
    graph.add_edge("analyze_failures", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer)


def initial_v2_state(
    requirement: str,
    model_mode: ModelMode = "api",
    run_id: str | None = None,
) -> AgentV2State:
    if not requirement.strip():
        raise ValueError("requirement 不能为空")
    if model_mode not in {"api", "rule"}:
        raise ValueError("model_mode 必须是 api 或 rule")
    return {
        "run_id": run_id or f"run_{uuid4().hex}",
        "requirement": requirement,
        "model_mode": model_mode,
        "rag_context": [],
        "requirement_rules": [],
        "requirement_source": "",
        "requirement_fallback_reason": "",
        "test_points": [],
        "test_point_source": "",
        "test_point_fallback_reason": "",
        "coverage_matrix": {},
        "coverage_source": "",
        "coverage_fallback_reason": "",
        "enhancement_count": 0,
        "max_enhancements": 2,
        "enhancement_history": [],
        "enhancement_stop_reason": "",
        "test_cases": [],
        "unsupported_test_points": [],
        "planning_source": "",
        "planning_fallback_reason": "",
        "trace": [],
        "test_results": [],
        "report": "",
        "metrics": {},
        "persist_outputs": True,
        "bug_analysis": [],
    }


def run_design_agent(
    requirement: str,
    model_mode: ModelMode = "api",
) -> AgentV2State:
    graph = build_design_graph()
    return graph.invoke(initial_v2_state(requirement, model_mode=model_mode))


def run_agent_v2(
    requirement: str,
    model_mode: ModelMode = "api",
    operation_runner=None,
    persist_outputs: bool = True,
    run_id: str | None = None,
    persist_history: bool | None = None,
    repository: RunRepository | None = None,
) -> AgentV2State:
    state = initial_v2_state(requirement, model_mode=model_mode, run_id=run_id)
    state["persist_outputs"] = persist_outputs
    should_persist_history = persist_outputs if persist_history is None else persist_history
    run_repository = repository
    if should_persist_history:
        run_repository = run_repository or RunRepository()
        run_repository.create_run(
            requirement=state["requirement"],
            run_id=state["run_id"],
        )
    graph = build_agent_graph_v2(
        operation_runner=operation_runner,
        checkpointer=V2_CHECKPOINTER,
    )
    try:
        final_state = graph.invoke(
            state,
            config={"configurable": {"thread_id": state["run_id"]}},
        )
    except Exception as exc:
        if should_persist_history:
            assert run_repository is not None
            run_repository.fail_run(state["run_id"], str(exc))
        raise

    if should_persist_history:
        assert run_repository is not None
        run_repository.complete_run(
            run_id=final_state["run_id"],
            metrics=final_state["metrics"],
            trace=final_state["trace"],
            report=final_state["report"],
            rag_docs=len(final_state.get("rag_context", [])),
        )
    return final_state
