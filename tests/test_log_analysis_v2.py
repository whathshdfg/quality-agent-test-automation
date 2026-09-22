from app.tools.log_analysis_v2 import analyze_v2_failures


def test_structured_assertion_failure_keeps_failed_evidence():
    results = [{
        "case_id": "TC_001",
        "title": "支付状态",
        "status": "failed",
        "error_log": "结构化断言失败",
        "assertion_results": [{
            "target": "order.payment_status",
            "expected": "paid",
            "actual": "unpaid",
            "passed": False,
        }],
    }]

    analysis = analyze_v2_failures(results)

    assert analysis[0]["bug_type"] == "业务结果与预期不一致"
    assert analysis[0]["failed_assertions"][0]["actual"] == "unpaid"


def test_harness_failure_is_classified_as_plan_or_capability_problem():
    results = [{
        "case_id": "TC_002",
        "title": "非法计划",
        "status": "failed",
        "error_log": "Harness 执行失败: 变量引用不存在: order",
        "assertion_results": [],
    }]

    analysis = analyze_v2_failures(results)

    assert analysis[0]["bug_type"] == "测试计划或执行能力异常"
    assert "变量引用" in analysis[0]["root_cause"]


def test_passed_results_do_not_create_bug_analysis():
    assert analyze_v2_failures([{"case_id": "TC_OK", "status": "passed"}]) == []
