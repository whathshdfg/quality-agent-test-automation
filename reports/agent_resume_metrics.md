# Agent 项目量化评测报告

生成日期：2026-09-10

## 1. 项目规模

| 指标 | 结果 | 证据 |
| --- | ---: | --- |
| Agent Workflow 节点 | 7 | `app/agent_graph.py` 中 7 次 `graph.add_node` |
| Workflow 普通 Edge | 5 | `retrieve -> generate_cases -> coverage`、`enhance_cases -> coverage`、`run_tests -> analyze -> report -> END` |
| Conditional Edge | 1 | `coverage` 节点根据覆盖率进入 `enhance_cases` 或 `run_tests` |
| FastAPI API | 12 | `app.api_server` 5 个，`app.mock_business_api` 7 个 |
| 业务 API | 6 | `/mock/order/*`、`/mock/driver/*`、`/mock/payment/pay`；`/mock/reset` 是测试辅助接口 |
| Agent 自身 API | 4 | `/agent/run`、`/agent/trace`、`/agent/metrics`、`/agent/report` |
| 健康/首页 API | 1 | `/` |
| 测试辅助 API | 1 | `/mock/reset` |
| 既有 requests API 测试分支 | 11 | `app/tools/api_test_tool.py` 中取消 6、支付 2、创建订单 3 个校验分支 |
| 新增 pytest testcase | 8 | `tests/test_mock_business_api.py` |
| 新增 pytest assertions | 22 | `tests/test_mock_business_api.py` 中 22 条 `assert` |
| 当前可验证 pytest 结果 | 当前项目无法验证 | 本机 `pytest` 不在 PATH，`.venv` 指向不存在的 Python |
| Python 文件数 | 25 | 排除 `.venv`、`.git`、`node_modules`、`dist`、`build` 后统计 |
| Python 有效代码行 | 2180 | 非空且非注释行；包含本次新增 eval/test 文件 |
| 原项目 Python 有效代码行 | 1788 | 不含本次新增 `evals/`、`tests/` |
| 测试代码行 | 138 | `tests/test_mock_business_api.py` 有效代码行 |
| 核心 Agent 文件数 | 12 | `agent_graph`、`rag_retriever`、LLM 与 tools 下核心模块 |
| React 前端文件 | 18 | `frontend` 下排除生成目录；其中 `src` 代码/样式文件 4 个 |

## 2. Agent Workflow

完整主流程：

`retrieve -> generate_cases -> coverage -> (enhance_cases -> coverage)* -> run_tests -> analyze -> report -> END`

节点说明：

| Node | 作用 |
| --- | --- |
| `retrieve` | 调用 `retrieve_context` 从 `app/data/*.md` 检索 RAG 上下文 |
| `generate_cases` | 拼接需求与 RAG 文档，优先调用 LLM 生成测试用例，失败后回退规则生成 |
| `coverage` | 根据测试用例文本命中关键字，计算 7 个测试维度覆盖率 |
| `enhance_cases` | 当覆盖率低于 90% 且未超过最大重试次数时，补充缺失维度用例 |
| `run_tests` | 调用 `run_api_tests`，通过 requests 访问 mock 业务 API |
| `analyze` | 对失败用例进行缺陷分析 |
| `report` | 生成 Markdown 报告，计算 metrics，并保存 trace/metrics 文件 |

条件分支：

- `coverage_rate < 90`
- `missing_dimensions` 非空
- `retry_count < max_retries`

同时满足时进入 `enhance_cases`，否则进入 `run_tests`。

主要 State 字段：

`requirement`、`rag_context`、`test_cases`、`coverage_result`、`test_results`、`bug_analysis`、`report`、`retry_count`、`max_retries`、`retry_history`、`trace`、`metrics`。

## 3. FastAPI API

| Method | Path | Function | 分类 | Purpose |
| --- | --- | --- | --- | --- |
| GET | `/` | `home` | 健康/首页 | 返回 Agent 服务启动信息 |
| POST | `/agent/run` | `run_quality_agent` | Agent API | 执行完整 Agent 并保存报告 |
| GET | `/agent/trace` | `get_execution_trace` | Agent API | 读取最近一次执行 trace |
| GET | `/agent/metrics` | `get_metrics_report` | Agent API | 读取最近一次 metrics |
| GET | `/agent/report` | `get_latest_report` | Agent API | 读取最近一次 Markdown 报告 |
| POST | `/mock/reset` | `reset` | 测试辅助 API | 重置 mock 内存数据库 |
| POST | `/mock/order/create` | `create_order` | 业务 API | 创建订单 |
| POST | `/mock/order/cancel` | `cancel_order` | 业务 API | 取消订单 |
| POST | `/mock/order/timeout_cancel` | `timeout_cancel_order` | 业务 API | 超时取消订单 |
| GET | `/mock/order/{order_id}` | `get_order` | 业务 API | 查询订单 |
| GET | `/mock/driver/{driver_id}` | `get_driver` | 业务 API | 查询司机 |
| POST | `/mock/payment/pay` | `pay_order` | 业务 API | 支付订单 |

## 4. API 测试结果

既有项目中没有 pytest 测试文件；原有 `app/tools/api_test_tool.py` 是 requests 驱动的业务 API 测试执行器。

| 指标 | 结果 |
| --- | ---: |
| requests 覆盖业务 API | 6 |
| requests 覆盖测试辅助 API | 1 |
| requests 业务校验分支 | 11 |
| 新增 pytest testcase | 8 |
| 新增 pytest assertions | 22 |
| `pytest --collect-only -q` | 当前项目无法验证：`pytest` 命令不存在 |
| `pytest -q` | 当前项目无法验证：本机无可用 Python/pytest |

无法运行原因：

- PATH 中的 `python` 是 WindowsApps 启动占位符，`python --version` 退出码为 1。
- 项目 `.venv\Scripts\python.exe` 指向 `E:\Anaconda Desktop\envs\my_project\python.exe`，该路径不存在。
- `pytest` 不在 PATH。

## 5. Structured Output

当前真实实现：

- `app/tools/case_generator.py` 使用 OpenAI 兼容 API。
- `extract_json_array` 支持直接 JSON 和 Markdown code block 中提取 JSON 数组。
- `validate_test_cases` 手写校验字段：`case_id`、`title`、`precondition`、`steps`、`expected_result`。
- `generate_test_cases` 捕获 LLM/JSON/校验异常后回退到 `generate_rule_based_test_cases`。
- 项目已有 Pydantic `BaseModel` 用于 FastAPI 请求体，但既有 LLM 测试用例校验没有使用 Pydantic。

新增脚本：

- `evals/eval_structured_output.py`
- 默认 30 轮，可用 `STRUCTURED_EVAL_RUNS` 调整。
- 每轮记录 `run_id`、输入、LLM 返回、JSON 合法性、Pydantic 校验、retry、最终成功、错误原因、耗时。

本次动态结果：

| 指标 | 结果 |
| --- | --- |
| 测试次数 | 当前项目无法验证 |
| 首轮成功 | 当前项目无法验证 |
| 首轮成功率 | 当前项目无法验证 |
| Retry | 当前项目无法验证 |
| 最终成功 | 当前项目无法验证 |
| 最终成功率 | 当前项目无法验证 |

原因：本机没有可用 Python 解释器，无法执行 eval 脚本；未伪造 LLM 调用结果。

## 6. RAG Eval

当前真实 RAG 实现：

| RAG 环节 | 当前实现 |
| --- | --- |
| Document Loading | `app/rag_retriever.py` 读取 `app/data/*.md` |
| Chunk | 未实现，整篇 Markdown 作为一个文档 |
| Embedding | 未实现 |
| Vector / Memory Index | 未实现向量索引；运行时遍历文档列表 |
| Cosine Similarity | 未实现 |
| Top-K | `retrieve_context(query, top_k=3)` |
| Threshold | 只有 `score > 0` 的轻量过滤 |
| Context | `generate_cases_node` 将检索内容拼进需求 |
| LLM Generation | 测试用例生成阶段使用 LLM |
| Reject | 未实现明确拒答策略 |
| Citation | 返回 `source` 字段，但最终报告未做模型引用约束 |
| Citation Validator | 原项目未实现；本次 `evals/eval_rag.py` 增加来源存在性检查 |

新增数据集：

- `evals/rag_eval_dataset.json`
- 20 个问题：10 个知识库内 answerable，10 个知识库外 unanswerable。

本次动态结果：

| 指标 | 结果 |
| --- | --- |
| RAG Eval 总问题 | 20（数据集已创建） |
| Answerable | 10 |
| Top-K 命中预期来源 | 当前项目无法验证 |
| Unanswerable | 10 |
| 正确拒答 | 当前项目无法验证 |
| Citation Validator | 当前项目无法验证 |

原因：本机没有可用 Python 解释器，无法执行 `evals/eval_rag.py`；未强行计算准确率。

## 7. Agent Performance

新增脚本：

- `evals/eval_agent_performance.py`
- 默认 10 次端到端 `run_agent()`，使用 `time.perf_counter()`。
- 每次记录 `run_id`、`duration_seconds`、`success`、`failed_node`、`error`。

本次动态结果：

| 指标 | 结果 |
| --- | --- |
| 端到端测试 | 当前项目无法验证 |
| 成功 | 当前项目无法验证 |
| 平均耗时 | 当前项目无法验证 |
| P50 | 当前项目无法验证 |
| P95 | 当前项目无法验证 |
| 最短/最长 | 当前项目无法验证 |

原因：本机 Python 环境不可用；同时 Agent 中 `run_api_tests` 依赖已启动的 HTTP 服务。

## 8. Trace / Metrics

当前真实实现：

- `app/tools/trace_tool.py`
  - 字段：`timestamp`、`node_name`、`action`、`status`、`detail`
  - 保存：`app/outputs/execution_trace.json`
- `app/tools/metrics_tool.py`
  - 字段：`total_cases`、`passed_cases`、`failed_cases`、`pass_rate`
  - 覆盖率：`coverage_rate`、`covered_dimensions`、`total_dimensions`、`missing_dimensions`
  - Retry/补充：`retry_count`、`added_cases_count`
  - 生成来源：`llm_generated_cases`、`rule_generated_cases`、`unknown_generated_cases`
  - RAG/缺陷：`rag_docs_count`、`bug_count`、`failed_case_ids`
  - 保存：`app/outputs/metrics_report.json`

Trace 可追踪的 workflow 节点：7 个业务节点均调用 `add_trace`。

当前限制：trace 记录每个节点的一条业务事件，但没有记录 `start_time`、`end_time`、节点级 `duration`，所以不能从既有 trace 直接计算节点耗时。

## 9. 可以真实写入简历的数据

仅选择静态代码和本次可核验文件能证明的数据：

- 构建 7 节点 LangGraph 测试智能化 Agent Workflow，覆盖 RAG 检索、用例生成、覆盖率分析、自动补充、接口测试、缺陷分析、报告生成。
- 实现 12 个 FastAPI 路由，其中 6 个模拟业务 API、4 个 Agent 运行/trace/metrics/report API、1 个健康接口、1 个测试重置接口。
- 基于 requests 封装真实 HTTP API 测试执行器，静态覆盖订单创建、订单取消、超时取消、订单查询、司机查询、支付等 6 个业务 API。
- 在 API 测试执行器中实现 11 个业务校验分支，覆盖正常、异常、边界、重复操作、状态变更、资源释放、数据一致性等场景。
- 实现 LLM JSON 结构化输出提取与字段校验，LLM 失败时自动回退到规则测试用例生成。
- 实现轻量 RAG 检索，从 4 份 Markdown 知识文档中按 Top-K 召回上下文，并注入测试用例生成流程。
- 实现 workflow trace 与 metrics 输出，7 个 Agent 节点均记录执行链路，metrics 覆盖用例数、通过率、覆盖率、retry、RAG 文档数、缺陷数等字段。
- 本次新增 20 条 RAG Eval Dataset、3 个 eval 脚本、8 个 pytest testcase 和 22 条 pytest assertion；因本机 Python 环境不可用，本次未验证通过率。

## 10. Agent 开发实习生简历项目描述

1. 构建面向质量效能场景的 LangGraph Agent，设计 7 节点 Workflow，串联 RAG 检索、测试用例生成、覆盖率分析、自动补充、接口测试、缺陷分析与报告生成。

2. 实现 OpenAI 兼容 LLM 用例生成链路，支持 JSON 结构化提取、字段校验与规则回退，并接入 4 份 Markdown 知识文档完成 Top-K RAG 上下文注入。

3. 基于 FastAPI 与 requests 搭建订单/支付模拟业务测试环境，覆盖 6 个业务 API 与 11 个业务校验分支，包含正常、异常、边界和重复操作场景。

4. 实现 Agent trace 与 metrics 工程化输出，7 个节点均记录执行链路；新增 20 条 RAG Eval 数据、8 个 pytest 用例和 22 条断言用于后续回归验证。

## 11. 新增文件

- `evals/eval_structured_output.py`
- `evals/rag_eval_dataset.json`
- `evals/eval_rag.py`
- `evals/eval_agent_performance.py`
- `tests/test_mock_business_api.py`
- `reports/agent_resume_metrics.md`

## 12. 修改文件

未修改核心业务逻辑，仅新增评测/测试/报告文件。
