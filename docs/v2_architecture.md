# 测试智能化 AI Agent V2 架构说明

## 定位

V2 是与旧 Agent 并行存在的结构化测试设计与安全执行链路。它继续使用 API
模型，不依赖本地大模型。API 不可用、输出格式错误或数据契约校验失败时，
需求拆解、测试点生成、定向补充和测试计划均有明确的规则兜底。

旧接口 `/agent/run` 未删除；前端和新开发默认使用 `/agent/v2/run`。

## 完整流程

```text
retrieve
  -> analyze_requirements
  -> generate_test_points
  -> coverage_matrix
       -> enhance_test_points -> coverage_matrix（最多 2 轮）
  -> plan_test_cases
  -> execute_tests
  -> analyze_failures
  -> report
```

### 1. 需求拆解

`app/tools/requirement_analyzer.py` 将原始需求和 RAG 资料提交给 API 模型，输出
严格的 `RequirementRule[]`。规则兜底只依据原始用户需求分类，避免 RAG 中其他
业务关键词污染分类。

### 2. 分层测试点

`app/tools/test_point_generator.py` 将规则转换为 `TestPoint[]`。一级维度为：

- `functional_behavior`
- `input_parameter`
- `state_flow`
- `resource_dependency`
- `data_quality`
- `reliability`
- `security_permission`

测试点通过 `requirement_ids`、`parameter_names`、`parameter_checks` 和
`risk_tags` 建立可追踪关系。

### 3. 覆盖矩阵

`app/tools/coverage_matrix_tool.py` 分别计算：

- 需求覆盖：每条规则是否有测试点显式引用。
- 参数覆盖：每个字段的正常、空值、非法、边界、约束和组合检查。
- 风险覆盖：状态、幂等、资源、回滚和数据一致性等风险。

覆盖判断按以下优先级运行：

```text
结构化关联（confidence=1.0）
-> 关键词补充（confidence=0.65）
-> API 语义判断（默认 confidence>=0.8）
-> 保留缺口
```

语义判断只能处理已存在的目标和测试点 ID；低置信度、虚构引用或 API 失败
都不能提升覆盖率。

### 4. 定向补充

`app/tools/test_point_enhancer.py` 只根据具体 `CoverageGap.target_id` 补充测试点。
新增点必须实际消除缺口，否则进入规则补充；仍无提升时停止，不进行无效循环。
执行器能力缺口不会通过多生成测试点来掩盖。

### 5. Harness

`app/harness/capability_registry.py` 是执行能力白名单。目前只允许项目真实存在
的 8 个 Mock 操作，禁止绝对 URL、Shell、动态函数调用和注册表外操作。

核心限制：

- 只允许 `/mock/*`。
- 只允许 GET/POST。
- 每条用例最多 12 个请求。
- 默认 5 秒 HTTP 超时。
- 每条用例第一个 setup 操作必须重置 Mock 数据。
- 操作必须与业务类型匹配。
- 安全、并发、网络故障和性能能力未实现时明确标记不可执行。

`app/harness/test_case_planner.py` 把测试点转换为包含 setup、test、verification
动作和结构化断言的 `TestCaseSpec`。`structured_executor.py` 仅通过显式分发表
执行操作，并使用固定断言操作符，不使用 `eval`。

### 6. 状态与可观测性

每次 V2 运行都有独立 `run_id`，同时作为 LangGraph `thread_id`。当前使用
`InMemorySaver` 保存进程内 checkpoint，可用于单进程状态追踪；它不是跨重启
持久化。若以后需要暂停恢复或多实例部署，应替换为数据库 checkpointer。

V2 输出：

```text
app/outputs/v2_test_report.md
app/outputs/v2_metrics_report.json
app/outputs/v2_execution_trace.json
```

这些文件仍只保存最近一次运行。

## API

### POST `/agent/v2/run`

```json
{
  "requirement": "重复支付应返回 REPEAT_PAYMENT",
  "model_mode": "api"
}
```

`model_mode`：

- `api`：优先调用配置的 API 模型，失败时规则兜底。
- `rule`：不调用模型，用于离线演示、测试和确定性回归。

响应包括 `run_id`、报告、指标、需求规则、测试点、覆盖矩阵、测试计划、执行
结果、不可执行测试点、失败分析和 Trace。

查询最近一次结果：

```text
GET /agent/v2/report
GET /agent/v2/metrics
GET /agent/v2/trace
```

## 运行

```powershell
python -m uvicorn app.api_server:app --reload
```

另开终端：

```powershell
cd frontend
npm run dev
```

前端默认访问 V2，可切换 API 模型或规则模式，并展示三种覆盖率、报告、矩阵、
Metrics 和 Trace。

## 测试与评估

```powershell
python -m pytest -q
python evals/eval_test_design.py
cd frontend
npm run lint
npm run build
```

黄金验收数据位于 `evals/test_design_acceptance_dataset.json`，包含订单取消、支付、
订单创建三类业务的需求规则和分层测试点。

## 当前边界

- API 模式质量取决于模型服务、余额、网络和模型能力。
- RAG 仍是本地关键词与字符重合检索，不是向量检索。
- Mock 数据库是进程内字典，不支持生产级并发与事务。
- Checkpoint 当前仅在进程内保存，服务重启后丢失。
- V2 输出文件仍会被下一次运行覆盖。
- Harness 只允许当前注册的 Mock 能力，不支持真实生产接口或任意工具执行。
- 人工审批中断尚未开放，因为当前动作全部限定在可重置的本机 Mock API；接入
  真实环境前应在执行节点前增加持久化 checkpointer 和人工审批。
