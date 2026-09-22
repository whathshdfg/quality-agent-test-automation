from app.agent_graph import should_retry_or_continue
from app.tools.api_test_tool import run_single_api_test
from app.tools.case_enhancer import (
    CASE_TEMPLATES,
    build_supplement_case,
    classify_business,
    enhance_test_cases,
)


def test_cancel_requirement_has_priority_over_order_keyword():
    assert classify_business("测试订单取消功能") == "cancel"


def test_all_business_dimensions_have_templates():
    for business_type, templates in CASE_TEMPLATES.items():
        requirement = {
            "cancel": "测试订单取消功能",
            "payment": "测试订单支付功能",
            "order_create": "测试订单创建功能",
        }[business_type]

        for index, dimension in enumerate(templates.keys(), start=1):
            case = build_supplement_case(dimension, requirement, index)
            assert case is not None
            assert case["case_id"]
            assert case["title"]
            assert case["steps"]
            assert case["expected_result"]


def test_unknown_business_does_not_generate_supplement_case():
    case = build_supplement_case("正常场景", "测试用户资料编辑功能", 1)
    assert case is None


def test_enhance_keeps_existing_cases_and_marks_auto_source():
    original = {
        "case_id": "TC_CANCEL_001",
        "title": "用户主动取消未接单订单",
        "precondition": "用户已创建订单",
        "steps": ["调用取消接口"],
        "expected_result": "订单状态变为 cancelled",
        "generation_source": "rule",
    }
    coverage_result = {
        "details": [
            {"dimension": "异常场景", "covered": False},
            {"dimension": "重复操作", "covered": False},
        ]
    }

    enhanced_cases, added_cases = enhance_test_cases(
        requirement="测试订单取消功能",
        test_cases=[original],
        coverage_result=coverage_result,
    )

    assert enhanced_cases[0] == original
    assert len(added_cases) == 2
    assert all(item["added_case"]["generation_source"] == "auto_supplement" for item in added_cases)
    assert len({case["case_id"] for case in enhanced_cases}) == len(enhanced_cases)


def test_unmatched_api_case_fails_instead_of_default_pass():
    result = run_single_api_test(
        {
            "case_id": "TC_UNKNOWN_001",
            "title": "未知业务用例",
            "precondition": "无",
            "steps": ["执行未知操作"],
            "expected_result": "不应默认通过",
        }
    )
    assert result["status"] == "failed"
    assert "不能默认标记为通过" in result["error_log"]


def test_no_progress_stop_prevents_retry():
    state = {
        "coverage_result": {
            "coverage_rate": 80,
            "missing_dimensions": ["异常场景"],
        },
        "retry_count": 1,
        "max_retries": 2,
        "enhancement_stop_reason": "本轮未新增测试用例，停止无效增强",
    }

    assert should_retry_or_continue(state) == "run_tests"
