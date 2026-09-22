import pytest

from app.agent_graph_v2 import initial_v2_state, run_design_agent


@pytest.mark.parametrize(
    ("requirement", "business_type"),
    [
        ("订单取消后释放司机资源，并校验重复取消", "order_cancel"),
        ("支付成功后状态为 paid，重复支付应被拦截", "payment"),
        ("创建订单时起终点不能为空，并禁止重复下单", "order_create"),
    ],
)
def test_rule_mode_builds_structured_design_for_supported_businesses(
    requirement,
    business_type,
):
    state = run_design_agent(requirement, model_mode="rule")

    assert state["requirement_rules"]
    assert state["test_points"]
    assert state["test_cases"]
    assert {item["business_type"] for item in state["requirement_rules"]} == {
        business_type
    }
    assert all(case["setup_actions"] for case in state["test_cases"])
    assert all(case["test_actions"] for case in state["test_cases"])
    assert all(case["assertions"] for case in state["test_cases"])
    assert state["coverage_matrix"]["requirement_coverage"]["coverage_rate"] == 100
    assert state["coverage_matrix"]["parameter_coverage"]["coverage_rate"] == 100
    assert state["coverage_matrix"]["risk_coverage"]["coverage_rate"] == 100


def test_v2_trace_uses_explicit_design_nodes():
    state = run_design_agent("测试重复支付", model_mode="rule")
    node_names = [item["node_name"] for item in state["trace"]]

    assert node_names == [
        "retrieve",
        "analyze_requirements",
        "generate_test_points",
        "coverage_matrix",
        "plan_test_cases",
    ]


def test_unknown_business_is_reported_as_unsupported_without_cases():
    state = run_design_agent("查询未来天气", model_mode="rule")

    assert state["requirement_rules"][0]["business_type"] == "unknown"
    assert state["test_cases"] == []
    assert state["unsupported_test_points"]
    assert state["planning_source"] == "not_needed"


def test_invalid_initial_input_is_rejected():
    with pytest.raises(ValueError, match="不能为空"):
        initial_v2_state(" ", model_mode="rule")

    with pytest.raises(ValueError, match="api 或 rule"):
        initial_v2_state("测试支付", model_mode="local")
