"""Allowlisted capabilities and safety policy for the current Mock API harness."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.test_design import BusinessType, CoverageCategory, TestPoint


class HarnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OperationCapability(HarnessModel):
    name: str
    method: Literal["GET", "POST"]
    path_template: str
    business_types: frozenset[BusinessType]
    purpose: str
    setup_allowed: bool = False


class HarnessPolicy(HarnessModel):
    allowed_path_prefixes: tuple[str, ...] = ("/mock/",)
    allowed_methods: frozenset[str] = frozenset({"GET", "POST"})
    request_timeout_seconds: int = Field(default=5, ge=1, le=30)
    max_requests_per_case: int = Field(default=12, ge=1, le=50)
    allow_absolute_urls: bool = False
    reset_before_each_case: bool = True
    unknown_action_policy: Literal["reject"] = "reject"


class RequestValidation(HarnessModel):
    allowed: bool
    operation_name: str = ""
    reasons: tuple[str, ...] = ()


class CapabilityDecision(HarnessModel):
    supported: bool
    business_type: BusinessType
    operation_names: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


ALL_BUSINESSES = frozenset({
    BusinessType.ORDER_CANCEL,
    BusinessType.PAYMENT,
    BusinessType.ORDER_CREATE,
})


CAPABILITY_REGISTRY: dict[str, OperationCapability] = {
    "reset_mock_data": OperationCapability(
        name="reset_mock_data",
        method="POST",
        path_template="/mock/reset",
        business_types=ALL_BUSINESSES,
        purpose="每条测试用例执行前重置内存 Mock 数据",
        setup_allowed=True,
    ),
    "create_order": OperationCapability(
        name="create_order",
        method="POST",
        path_template="/mock/order/create",
        business_types=ALL_BUSINESSES,
        purpose="创建 waiting 或 accepted 订单作为测试对象",
        setup_allowed=True,
    ),
    "cancel_order": OperationCapability(
        name="cancel_order",
        method="POST",
        path_template="/mock/order/cancel",
        business_types=frozenset({BusinessType.ORDER_CANCEL}),
        purpose="取消订单并验证状态、原因和资源释放",
    ),
    "timeout_cancel_order": OperationCapability(
        name="timeout_cancel_order",
        method="POST",
        path_template="/mock/order/timeout_cancel",
        business_types=frozenset({BusinessType.ORDER_CANCEL}),
        purpose="模拟 waiting 订单达到超时条件后的系统取消",
    ),
    "get_order": OperationCapability(
        name="get_order",
        method="GET",
        path_template="/mock/order/{order_id}",
        business_types=ALL_BUSINESSES,
        purpose="查询订单详情用于状态和数据断言",
    ),
    "list_user_orders": OperationCapability(
        name="list_user_orders",
        method="GET",
        path_template="/mock/orders/user/{user_id}",
        business_types=ALL_BUSINESSES,
        purpose="查询用户订单列表用于一致性断言",
    ),
    "get_driver": OperationCapability(
        name="get_driver",
        method="GET",
        path_template="/mock/driver/{driver_id}",
        business_types=frozenset({
            BusinessType.ORDER_CANCEL,
            BusinessType.ORDER_CREATE,
            BusinessType.PAYMENT,
        }),
        purpose="查询司机状态用于资源分配或释放断言",
    ),
    "pay_order": OperationCapability(
        name="pay_order",
        method="POST",
        path_template="/mock/payment/pay",
        business_types=frozenset({BusinessType.PAYMENT}),
        purpose="支付订单并验证支付状态和幂等保护",
    ),
}


HARNESS_POLICY = HarnessPolicy()


BUSINESS_OPERATIONS: dict[BusinessType, tuple[str, ...]] = {
    BusinessType.ORDER_CANCEL: (
        "reset_mock_data",
        "create_order",
        "cancel_order",
        "timeout_cancel_order",
        "get_order",
        "list_user_orders",
        "get_driver",
    ),
    BusinessType.PAYMENT: (
        "reset_mock_data",
        "create_order",
        "pay_order",
        "get_order",
        "list_user_orders",
        "get_driver",
    ),
    BusinessType.ORDER_CREATE: (
        "reset_mock_data",
        "create_order",
        "get_order",
        "list_user_orders",
        "get_driver",
    ),
    BusinessType.UNKNOWN: (),
}


SUPPORTED_PARAMETER_CHECKS: dict[BusinessType, frozenset[str]] = {
    BusinessType.ORDER_CANCEL: frozenset({
        "normal", "empty", "invalid", "boundary", "constraint",
    }),
    BusinessType.PAYMENT: frozenset({
        "normal", "empty", "invalid", "boundary", "constraint",
    }),
    BusinessType.ORDER_CREATE: frozenset({
        "normal", "empty", "invalid", "boundary", "constraint", "combination",
    }),
    BusinessType.UNKNOWN: frozenset(),
}


SUPPORTED_RISKS: dict[BusinessType, frozenset[str]] = {
    BusinessType.ORDER_CANCEL: frozenset({
        "state_transition",
        "required_parameter",
        "boundary",
        "idempotency",
        "resource_release",
        "data_consistency",
    }),
    BusinessType.PAYMENT: frozenset({
        "state_transition",
        "amount_boundary",
        "idempotency",
        "duplicate_charge",
        "failure_rollback",
        "data_consistency",
    }),
    BusinessType.ORDER_CREATE: frozenset({
        "required_parameter",
        "parameter_combination",
        "state_transition",
        "idempotency",
        "duplicate_data",
        "resource_allocation",
        "data_consistency",
    }),
    BusinessType.UNKNOWN: frozenset(),
}


UNSUPPORTED_CATEGORIES: dict[CoverageCategory, str] = {
    CoverageCategory.SECURITY_PERMISSION: "Mock API 当前没有身份认证和权限模型",
}


UNSUPPORTED_RISK_REASONS = {
    "concurrency": "内存 Mock 数据库没有并发隔离和并发测试驱动",
    "network_fault": "当前 Harness 没有网络故障注入能力",
    "retry": "当前 Mock API 没有可观测的业务重试机制",
    "performance": "当前 Harness 不提供负载和性能测试能力",
}


def get_operation(name: str) -> OperationCapability | None:
    return CAPABILITY_REGISTRY.get(name)


def _path_pattern(path_template: str) -> re.Pattern[str]:
    escaped = re.escape(path_template)
    pattern = re.sub(r"\\\{[^{}]+\\\}", r"[^/?#]+", escaped)
    return re.compile(f"^{pattern}$")


def validate_request(
    method: str,
    path: str,
    request_count: int = 0,
    policy: HarnessPolicy = HARNESS_POLICY,
) -> RequestValidation:
    normalized_method = method.upper().strip()
    reasons: list[str] = []

    if request_count >= policy.max_requests_per_case:
        reasons.append(
            f"单用例请求数不能超过 {policy.max_requests_per_case}"
        )
    if normalized_method not in policy.allowed_methods:
        reasons.append(f"HTTP 方法不在允许列表中: {normalized_method}")
    if not policy.allow_absolute_urls and re.match(r"^[a-z]+://", path, re.I):
        reasons.append("不允许使用绝对 URL")
    if not any(path.startswith(prefix) for prefix in policy.allowed_path_prefixes):
        reasons.append("请求路径不在允许的 Mock API 范围内")

    matched_operation = next(
        (
            operation
            for operation in CAPABILITY_REGISTRY.values()
            if operation.method == normalized_method
            and _path_pattern(operation.path_template).fullmatch(path)
        ),
        None,
    )
    if not matched_operation:
        reasons.append("未找到匹配的已注册操作")

    return RequestValidation(
        allowed=not reasons,
        operation_name=matched_operation.name if matched_operation else "",
        reasons=tuple(dict.fromkeys(reasons)),
    )


def evaluate_test_point_support(point: TestPoint) -> CapabilityDecision:
    reasons: list[str] = []

    if point.executable is False:
        reasons.append(point.unsupported_reason or "测试点已标记为不可执行")
    if point.business_type == BusinessType.UNKNOWN:
        reasons.append("未知业务类型不允许进入自动执行")

    category_reason = UNSUPPORTED_CATEGORIES.get(point.level_1)
    if category_reason:
        reasons.append(category_reason)

    supported_checks = SUPPORTED_PARAMETER_CHECKS.get(
        point.business_type,
        frozenset(),
    )
    unsupported_checks = sorted(set(point.parameter_checks) - supported_checks)
    if unsupported_checks:
        reasons.append(f"不支持的参数检查: {', '.join(unsupported_checks)}")

    supported_risks = SUPPORTED_RISKS.get(point.business_type, frozenset())
    unsupported_risks = sorted(set(point.risk_tags) - supported_risks)
    for risk in unsupported_risks:
        reasons.append(
            UNSUPPORTED_RISK_REASONS.get(
                risk,
                f"当前业务执行器不支持风险类型: {risk}",
            )
        )

    if point.level_1 == CoverageCategory.RELIABILITY and not point.risk_tags:
        reasons.append("可靠性测试点缺少明确 risk_tags，无法选择执行能力")

    operation_names = BUSINESS_OPERATIONS.get(point.business_type, ())
    if not operation_names:
        reasons.append("没有为该业务注册可执行操作")

    return CapabilityDecision(
        supported=not reasons,
        business_type=point.business_type,
        operation_names=operation_names if not reasons else (),
        reasons=tuple(dict.fromkeys(reasons)),
    )

