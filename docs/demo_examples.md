# Demo Examples

## Example Requirement

```json
{
  "requirement": "用户主动取消未接单订单后，订单状态变为 cancelled。如果订单创建后 3 分钟内没有司机接单，系统自动取消订单。如果司机已接单，用户取消订单时必须记录取消原因。订单取消后司机资源应释放。"
}

Expected Output Files
app/outputs/test_report.md
app/outputs/execution_trace.json
app/outputs/metrics_report.json
app/outputs/eval_summary.json

Typical Failed Case
TC_CANCEL_004 订单取消后司机资源释放校验

Reason:

订单取消成功，但 driver_status 仍然是 assigned，预期应为 available。

Diagnosis:

缺陷类型：资源释放异常
根因分析：订单取消后只更新了订单状态，没有释放司机资源
修复建议：在 cancel_order 逻辑中增加 driver_status 从 assigned 到 available 的状态更新