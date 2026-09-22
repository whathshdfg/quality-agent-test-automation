"""Automatic supplement case builder for missing coverage dimensions."""


COVERAGE_DIMENSIONS = [
    "正常场景",
    "异常场景",
    "边界场景",
    "重复操作",
    "状态变更校验",
    "资源释放校验",
    "数据一致性校验",
]


BUSINESS_KEYWORDS = {
    "cancel": ["取消", "撤销", "退单"],
    "payment": ["支付", "付款", "扣款"],
    "order_create": ["创建", "下单", "新建订单", "发起订单", "订单"],
}


BUSINESS_PREFIX = {
    "cancel": "TC_CANCEL_AUTO",
    "payment": "TC_PAY_AUTO",
    "order_create": "TC_ORDER_AUTO",
}


def get_existing_case_ids(test_cases: list[dict]) -> set:
    """Return existing case ids to avoid overwriting generated or original cases."""

    return {case.get("case_id", "") for case in test_cases}


def classify_business(requirement: str) -> str:
    """
    Classify one requirement into exactly one business type.

    Priority is intentional: cancel requirements often contain "订单", so cancel
    must be checked before broad order-create keywords.
    """

    if any(keyword in requirement for keyword in BUSINESS_KEYWORDS["cancel"]):
        return "cancel"

    if any(keyword in requirement for keyword in BUSINESS_KEYWORDS["payment"]):
        return "payment"

    if any(keyword in requirement for keyword in BUSINESS_KEYWORDS["order_create"]):
        return "order_create"

    return "unknown"


def make_case(case_id: str, title: str, precondition: str, steps: list[str], expected_result: str) -> dict:
    return {
        "case_id": case_id,
        "title": title,
        "precondition": precondition,
        "steps": steps,
        "expected_result": expected_result,
    }


CASE_TEMPLATES = {
    "cancel": {
        "正常场景": (
            "用户主动取消未接单订单",
            "用户已创建订单，订单状态为 waiting",
            ["创建未接单订单", "调用取消订单接口", "查询订单状态"],
            "取消成功，订单状态变为 cancelled",
        ),
        "异常场景": (
            "取消不存在订单异常校验",
            "系统中不存在目标 order_id",
            ["使用不存在的 order_id 调用取消订单接口", "检查接口返回码和错误信息"],
            "系统返回 ORDER_NOT_FOUND，不创建新的订单状态",
        ),
        "边界场景": (
            "订单超时自动取消边界校验",
            "订单创建后处于 waiting，达到超时取消条件",
            ["创建未接单订单", "调用超时取消接口", "查询订单状态和取消原因"],
            "系统返回 TIMEOUT_CANCEL_SUCCESS，订单状态为 cancelled，取消原因为 timeout_no_driver",
        ),
        "重复操作": (
            "重复取消订单拦截校验",
            "订单已被用户取消，订单状态为 cancelled",
            ["第一次调用取消订单接口", "再次调用取消订单接口", "查询订单最终状态"],
            "第二次取消返回 REPEAT_CANCEL，订单状态保持 cancelled",
        ),
        "状态变更校验": (
            "司机已接单后用户取消状态变更校验",
            "订单状态为 accepted，且绑定司机",
            ["创建已接单订单", "传入取消原因调用取消接口", "查询订单状态和取消原因"],
            "订单状态从 accepted 变为 cancelled，并记录 cancel_reason",
        ),
        "资源释放校验": (
            "订单取消后司机资源释放校验",
            "司机已被订单占用，driver_status 为 assigned",
            ["创建已接单订单", "调用取消订单接口", "查询司机状态"],
            "取消成功后 driver_status 从 assigned 变为 available",
        ),
        "数据一致性校验": (
            "订单取消后列表与详情数据一致性校验",
            "用户已成功取消订单",
            ["创建订单并取消", "查询订单详情", "查询用户订单列表"],
            "订单详情和用户订单列表中的 order_status、cancel_reason 保持一致",
        ),
    },
    "payment": {
        "正常场景": (
            "订单正常支付成功",
            "订单已创建，payment_status 为 unpaid",
            ["调用支付接口", "传入正确 user_id、order_id、amount", "查询订单支付状态"],
            "支付成功，payment_status 变为 paid，order_status 变为 paid",
        ),
        "异常场景": (
            "支付金额异常拦截校验",
            "订单已创建，payment_status 为 unpaid",
            ["使用 amount 为 0 调用支付接口", "查询订单支付状态"],
            "系统返回 INVALID_AMOUNT，订单 payment_status 保持 unpaid",
        ),
        "边界场景": (
            "最小有效金额支付边界校验",
            "订单已创建，payment_status 为 unpaid",
            ["使用 amount 为 0.01 调用支付接口", "查询订单支付状态"],
            "系统允许最小有效金额支付，payment_status 变为 paid",
        ),
        "重复操作": (
            "重复支付拦截校验",
            "订单已支付成功，payment_status 为 paid",
            ["第一次调用支付接口", "再次调用支付接口", "查询订单支付状态"],
            "第二次支付返回 REPEAT_PAYMENT，避免重复扣款",
        ),
        "状态变更校验": (
            "支付后订单状态变更校验",
            "订单已创建，order_status 为 waiting，payment_status 为 unpaid",
            ["调用支付接口", "查询订单状态和支付状态"],
            "order_status 从 waiting 变为 paid，payment_status 从 unpaid 变为 paid",
        ),
        "资源释放校验": (
            "支付失败不占用司机资源校验",
            "订单未分配司机，司机 driver_status 为 available",
            ["使用无效金额调用支付接口", "查询司机状态"],
            "支付失败后 driver_status 仍为 available，不产生资源占用",
        ),
        "数据一致性校验": (
            "支付后订单详情与列表数据一致性校验",
            "用户已成功支付订单",
            ["创建订单并支付", "查询订单详情", "查询用户订单列表"],
            "订单详情和用户订单列表中的 payment_status、order_status 保持一致",
        ),
    },
    "order_create": {
        "正常场景": (
            "正常创建订单",
            "用户没有未完成订单",
            ["输入有效起点", "输入有效终点", "调用创建订单接口"],
            "订单创建成功，返回 order_id，订单状态为 waiting",
        ),
        "异常场景": (
            "订单创建参数异常校验",
            "用户没有未完成订单",
            ["将起点置为空", "调用创建订单接口", "检查接口返回结果"],
            "系统返回 PARAM_ERROR，不创建订单",
        ),
        "边界场景": (
            "起点终点相同边界校验",
            "用户没有未完成订单",
            ["将起点和终点设置为相同位置", "调用创建订单接口", "检查接口返回结果"],
            "系统返回 SAME_LOCATION，不创建订单",
        ),
        "重复操作": (
            "重复下单拦截校验",
            "用户已经存在未完成订单",
            ["第一次创建订单", "再次使用相同用户创建订单", "检查第二次返回结果"],
            "第二次创建返回 DUPLICATE_ORDER，禁止重复下单",
        ),
        "状态变更校验": (
            "创建已接单订单状态变更校验",
            "用户没有未完成订单，创建请求携带 assign_driver",
            ["调用创建订单接口并分配司机", "查询订单状态和司机编号"],
            "订单状态为 accepted，并返回 driver_id",
        ),
        "资源释放校验": (
            "创建订单分配司机资源占用校验",
            "司机 driver_status 为 available",
            ["调用创建订单接口并分配司机", "查询司机状态"],
            "订单创建后 driver_status 从 available 变为 assigned",
        ),
        "数据一致性校验": (
            "订单创建后详情与列表数据一致性校验",
            "用户没有未完成订单",
            ["创建订单", "查询订单详情", "查询用户订单列表"],
            "订单详情和用户订单列表中的 order_id、order_status、起终点保持一致",
        ),
    },
}


def build_supplement_case(dimension: str, requirement: str, index: int) -> dict | None:
    """Build a concrete supplement case for the requested business and dimension."""

    business_type = classify_business(requirement)
    if business_type == "unknown":
        return None

    template = CASE_TEMPLATES.get(business_type, {}).get(dimension)
    if not template:
        return None

    title, precondition, steps, expected_result = template
    case_id = f"{BUSINESS_PREFIX[business_type]}_{index:03d}"
    return make_case(case_id, title, precondition, steps, expected_result)


def build_semantic_key(case: dict) -> tuple[str, str]:
    """Use title and expected result as a small semantic duplicate guard."""

    return (
        case.get("title", "").strip(),
        case.get("expected_result", "").strip(),
    )


def enhance_test_cases(
    requirement: str,
    test_cases: list[dict],
    coverage_result: dict
) -> tuple[list[dict], list[dict]]:
    """
    Supplement missing coverage dimensions without replacing existing test cases.

    Returns:
    1. merged test cases
    2. cases added in this round
    """

    missing_dimensions = [
        item["dimension"]
        for item in coverage_result.get("details", [])
        if not item.get("covered", False)
    ]

    enhanced_cases = test_cases.copy()
    added_cases = []
    existing_ids = get_existing_case_ids(test_cases)
    semantic_keys = {build_semantic_key(case) for case in test_cases}

    add_index = 1

    for dimension in missing_dimensions:
        new_case = build_supplement_case(
            dimension=dimension,
            requirement=requirement,
            index=add_index
        )

        if not new_case:
            continue

        while new_case["case_id"] in existing_ids:
            add_index += 1
            new_case = build_supplement_case(
                dimension=dimension,
                requirement=requirement,
                index=add_index
            )

        semantic_key = build_semantic_key(new_case)
        if semantic_key in semantic_keys:
            add_index += 1
            continue

        new_case["generation_source"] = "auto_supplement"
        enhanced_cases.append(new_case)
        added_cases.append({
            "missing_dimension": dimension,
            "added_case": new_case
        })
        existing_ids.add(new_case["case_id"])
        semantic_keys.add(semantic_key)
        add_index += 1

    return enhanced_cases, added_cases
