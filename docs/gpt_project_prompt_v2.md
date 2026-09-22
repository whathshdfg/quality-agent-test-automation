# 可直接发送给 GPT 的项目全貌 Prompt

你现在需要协助我继续开发真实项目“面向质量效能的测试智能化 AI Agent 系统”。
请严格基于下面给出的现状分析和修改，不要虚构项目中不存在的能力、接口或测试结果。
在提出改动前先说明理由、影响文件和验证方式；保持旧版兼容，不要无关重构。

## 1. 项目目标与技术栈

项目把需求检索、需求规则拆解、分层测试点生成、覆盖分析、缺口补充、
受约束测试计划、Mock API 执行、失败分析和报告串成 LangGraph 工作流。

- 后端：Python、FastAPI、LangGraph、Pydantic、OpenAI 兼容 API、pytest
- 前端：React、Vite、ESLint
- 数据：本地 Markdown 轻量 RAG；Mock 数据保存在进程内字典
- 模型策略：保留 API 调用，不做本地大模型部署；API 失败或输出校验失败时规则兜底
- 推荐入口：`POST /agent/v2/run`
- 兼容入口：旧版 `POST /agent/run` 仍保留

## 2. V2 完整流程

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

1. `retrieve` 从 `app/data/*.md` 检索 Top-K 资料。
2. `analyze_requirements` 先把原始需求拆成 `RequirementRule[]`，不直接生成用例。
3. `generate_test_points` 生成分层 `TestPoint[]`，并显式引用规则、参数检查和风险。
4. `coverage_matrix` 分别计算需求、参数、风险覆盖，不再使用单一七维百分比。
5. 覆盖判断依次使用结构化引用、关键词匹配、API 语义判断；语义结果需达到 0.8 置信度。
6. `enhance_test_points` 只针对具体 `CoverageGap.target_id` 补充，最多两轮，无提升即停止。
7. `plan_test_cases` 只使用 Harness 注册能力生成结构化 setup/test/verification 动作和断言。
8. `execute_tests` 通过固定分发表调用 Mock API，不允许 `eval`、Shell、绝对 URL 或动态函数。
9. `analyze_failures` 区分断言失败、计划失败、执行失败、环境失败和未知失败。
10. `report` 输出报告、指标和执行 Trace。

## 3. 核心数据契约

契约位于 `app/models/test_design.py`：

- `RequirementRule`：规则 ID、业务类型、参与者、触发器、前置条件、动作、预期、参数、风险
- `ParameterSpec`：类型、必填、正常值、非法值、边界值、约束
- `TestPoint`：一级/二级维度、关联规则、参数、检查类型、风险、可执行性
- `TestCaseSpec`：兼容旧五字段，并增加结构化 setup/test/verification 动作、断言和来源
- `CoverageEvidence`：目标、测试点、匹配方式、置信度和理由
- `CoverageGap`：缺口类型、目标 ID、原因、建议和是否可由当前 Harness 执行
- `CoverageMatrix`：需求、参数、风险三类汇总及证据、缺口

一级测试维度为：`functional_behavior`、`input_parameter`、`state_flow`、
`resource_dependency`、`data_quality`、`reliability`、`security_permission`。
它们是分类维度，不是要求每条需求机械覆盖的七个场景。

## 4. 覆盖与定向补充

- 需求覆盖：每条 `RequirementRule` 至少被一个测试点显式引用。
- 参数覆盖：按字段检查 normal、empty、invalid、boundary、constraint、combination。
- 风险覆盖：按规则中声明的风险逐项检查，例如 idempotency、state_transition、
  resource_release、failure_rollback、data_consistency。
- 结构化证据置信度为 1.0，关键词补充为 0.65，API 语义判断默认至少 0.8。
- 语义判断只能引用现有目标 ID 和测试点 ID，不能虚构目标，也不能隐藏未解决缺口。
- Harness 不支持的能力会保持为不可执行缺口，不用多生成测试点伪造覆盖。

## 5. Harness 真实能力与安全边界

能力注册表位于 `app/harness/capability_registry.py`，目前只有 8 个真实操作：

- 重置 Mock 数据
- 创建订单
- 取消订单
- 超时取消订单
- 查询订单
- 查询用户订单
- 查询司机
- 支付订单

约束：只允许 `/mock/*`，只允许 GET/POST，每条用例最多 12 次请求，HTTP 超时 5 秒，
第一步 setup 必须重置 Mock 数据，业务类型必须匹配注册操作。安全、并发、网络故障、
性能和真实生产接口尚未实现，必须明确标记为不可执行。

## 6. 关键文件

- `app/agent_graph_v2.py`：V2 状态、节点、条件循环、运行入口和进程内 checkpointer
- `app/models/test_design.py`：所有结构化契约
- `app/tools/requirement_analyzer.py`：API 优先的需求拆解及规则兜底
- `app/tools/test_point_generator.py`：分层测试点生成
- `app/tools/coverage_matrix_tool.py`：确定性覆盖矩阵
- `app/tools/coverage_matcher.py`：关键词补充
- `app/tools/semantic_coverage_matcher.py`：API 语义覆盖判断
- `app/tools/test_point_enhancer.py`：按缺口定向补充
- `app/harness/test_case_planner.py`：受约束测试计划
- `app/harness/structured_executor.py`：白名单结构化执行器
- `app/tools/log_analysis_v2.py`：失败分类
- `app/tools/report_v2.py`：报告、指标和 Trace
- `app/api_server.py`：V1/V2 API 和 Mock 路由挂载
- `app/mock_business_api.py`：订单、取消、司机和支付 Mock 行为
- `frontend/src/App.jsx`：V2 控制台、模式切换、矩阵、报告、指标和 Trace
- `evals/test_design_acceptance_dataset.json`：三类业务的验收数据集
- `tests/`：后端单元、集成、API 和真实 Harness 端到端测试

## 7. API 与输出

`POST /agent/v2/run` 请求：

```json
{
  "requirement": "重复支付应返回 REPEAT_PAYMENT",
  "model_mode": "api"
}
```

- `api`：优先调用配置的模型 API，失败后规则兜底。
- `rule`：完全离线、确定性运行，用于演示和回归。

响应含 `run_id`、规则、测试点、覆盖矩阵、用例、结果、失败分析、不可执行项、
报告、指标和 Trace。查询最近结果：

```text
GET /agent/v2/report
GET /agent/v2/metrics
GET /agent/v2/trace
```

最近一次结果写入：

```text
app/outputs/v2_test_report.md
app/outputs/v2_metrics_report.json
app/outputs/v2_execution_trace.json
```

每次运行都有独立 `run_id`，同时作为 LangGraph `thread_id`。当前使用 `InMemorySaver`，
只支持单进程生命周期内 checkpoint；服务重启后不保留，输出文件也会被下一次运行覆盖。

## 8. 已验证事实

- 后端：`140 passed, 1 warning`；warning 是 Starlette TestClient 的 AnyIO 弃用提示。
- 设计验收：业务分类 100%，规则召回 100%，规则到测试点映射 100%，分层覆盖 94.44%，非法引用 0。
- 前端：ESLint 通过，Vite 8.1.3 production build 通过。
- 真实 HTTP 冒烟：重复支付需求生成 2 条规则、7 个测试点、7 个用例，7/7 通过；
  需求、参数和风险覆盖均为 100%，Trace 包含上述 8 个节点，输出 `run_id` 一致。

## 9. 当前边界与后续优化原则

- RAG 仍是关键词/字符重合检索，不是向量检索。
- API 模式依赖密钥、网络、余额和模型质量，不能把规则兜底结果冒充模型结果。
- Mock 存储不支持生产级事务、并发和持久化。
- 尚无人工审批中断；接真实环境前应使用持久化 checkpointer，并在执行节点前加审批。
- Harness 只执行注册的本地 Mock 能力，不能声称支持真实生产系统或任意工具。
- 优化时优先扩展数据契约、能力注册表和验收集，再扩展执行逻辑；任何新增能力都要有测试。

请先根据这些事实复述你对系统边界和数据流的理解，再给出分阶段优化建议。涉及代码时，
必须指出具体文件、兼容性风险和测试方案；没有看到源码的部分应明确说明需要检查，不能猜测。
