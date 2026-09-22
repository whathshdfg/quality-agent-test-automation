# 面向质量效能的测试智能化 AI Agent 系统：项目全景 Prompt

> 更新提示：本文主体记录旧版兼容链路。项目现已新增推荐的 V2 结构化链路，
> 在发送本 Prompt 前还应附上 `docs/v2_architecture.md`，并以 V2 文档描述为准。

> 使用方式：将本文件从“Prompt 正文开始”到结尾完整发送给 GPT。若希望 GPT 修改代码，还应同时上传仓库文件，或继续粘贴它要求查看的具体文件。此 Prompt 用于快速建立准确的项目全貌，不能代替源代码本身。

---

## Prompt 正文开始

你现在是一名资深测试开发工程师、Python 后端工程师和 AI Agent 架构师。请先完整理解下面这个真实项目，再回答我后续提出的问题。

项目名称：**面向质量效能的测试智能化 AI Agent 系统**（仓库名 `quality-agent`）。

请严格遵守以下原则：

1. 只能依据我提供的项目事实进行分析，不要虚构项目中不存在的能力。
2. 必须区分“当前已实现”“仅用于 Mock/演示”“评估脚本”“未来可扩展项”。
3. 当前项目不是生产级测试平台，也没有向量数据库、真实生产数据库、Docker、鉴权、任务队列、流式输出或真正的语义检索。
4. 如果我要求修改代码，请先指出涉及的真实文件、数据流和可能影响，再给出与现有结构一致的实现。
5. 不要把关键词命中率叫作模型准确率，不要把 Mock API 测试描述成生产接口测试，也不要把规则补充用例描述成 LLM 自主推理。
6. 未识别或未配置执行逻辑的用例必须失败，不能默认通过。

## 一、项目目标

这是一个网约车业务场景下的测试智能化 Agent。用户输入自然语言需求后，系统依次完成：

```text
用户需求
  -> 本地知识库检索
  -> LLM 结构化生成测试用例（失败时规则兜底）
  -> 7 个测试维度覆盖率分析
  -> 覆盖不足时自动补充用例并重新分析
  -> 通过 HTTP 调用 Mock 业务 API 执行测试和断言
  -> 分析失败用例
  -> 生成 Markdown 报告、Trace JSON、Metrics JSON
  -> React 页面展示报告、指标和执行链路
```

核心价值是把需求、测试知识、用例设计、覆盖检查、自动执行、缺陷归因和结果展示串成一个可运行闭环。

## 二、技术栈与运行形态

- Python 3，FastAPI，Pydantic
- LangGraph：编排有状态 Agent 工作流
- OpenAI Python SDK：调用 OpenAI 兼容的 Chat Completions 接口
- `python-dotenv`：读取 `.env`
- `requests`：测试执行器调用本机 Mock HTTP API
- pytest：单元测试和接口测试
- React 19 + Vite：Web 控制台
- 数据持久化：没有数据库；Mock 业务数据存在进程内字典，报告写本地文件
- Agent 调用模式：同步执行，`POST /agent/run` 会等待整个流程完成

环境变量：

```text
OPENAI_API_KEY=模型服务密钥
OPENAI_MODEL=模型名，默认 gpt-4.1-mini
OPENAI_BASE_URL=可选的 OpenAI 兼容服务地址
MOCK_API_BASE_URL=http://127.0.0.1:8000
VITE_API_BASE_URL=http://127.0.0.1:8000
```

后端启动：

```powershell
python -m uvicorn app.api_server:app --reload
```

前端启动：

```powershell
cd frontend
npm install
npm run dev
```

测试命令：

```powershell
python -m pytest -q
```

最近一次实际验证结果是 `32 passed, 1 warning`。README 中的 `23 passed` 和部分接口数量是旧统计，不应当作为当前事实。

## 三、核心目录与职责

```text
quality-agent/
├─ app/
│  ├─ api_server.py                 FastAPI 服务入口、Agent API、挂载 Mock API
│  ├─ agent_graph.py                LangGraph 状态、7 个节点、条件边和主入口
│  ├─ mock_business_api.py          内存版网约车 Mock 业务 API
│  ├─ rag_retriever.py              本地 Markdown 关键词/字符重合检索
│  ├─ main.py                       命令行演示入口
│  ├─ data/                         需求、接口、测试规范、历史缺陷知识库
│  ├─ tools/
│  │  ├─ case_generator.py          LLM Prompt、JSON 提取、Schema 基础校验、规则回退
│  │  ├─ case_generator_rule.py     取消/支付/创建三类规则用例
│  │  ├─ coverage_tool.py           7 维覆盖率关键词分析
│  │  ├─ case_enhancer.py           按业务和缺失维度补充可执行用例
│  │  ├─ api_test_tool.py           HTTP 调用、业务分发、实际断言
│  │  ├─ log_analysis_tool.py       失败日志分类和修复建议
│  │  ├─ report_tool.py             Markdown 测试报告
│  │  ├─ metrics_tool.py            指标统计和 JSON 输出
│  │  └─ trace_tool.py              节点执行 Trace
│  └─ outputs/                      最近一次报告、Trace 和 Metrics
├─ frontend/src/App.jsx             单页 Agent 控制台
├─ tests/                           pytest 测试
├─ evals/                           RAG、结构化输出、端到端耗时评估
├─ app/eval/                        另一套基于关键词命中的 Agent 评测
├─ reports/                         已生成的评估结果和分析材料
├─ demos/                           辅助演示代码，不是主链路
└─ PythonProject/                   历史/学习目录，不是主项目运行依赖
```

## 四、LangGraph 完整流程

### 1. AgentState

`app/agent_graph.py` 使用 `TypedDict` 保存全链路状态：

```python
class AgentState(TypedDict):
    requirement: str
    rag_context: list[dict]
    test_cases: list[dict]
    coverage_result: dict
    test_results: list[dict]
    bug_analysis: list[dict]
    report: str
    retry_count: int
    max_retries: int
    retry_history: list[dict]
    trace: list[dict]
    metrics: dict
    enhancement_stop_reason: str
```

初始 `max_retries=2`，其他结果字段为空。

### 2. 图结构

```text
retrieve
  -> generate_cases
  -> coverage
       ├─ 覆盖不足且仍可重试 -> enhance_cases -> coverage
       └─ 覆盖满足/达到上限/无进展 -> run_tests
  -> analyze
  -> report
  -> END
```

覆盖阈值固定为 90%。进入增强必须同时满足：

```text
coverage_rate < 90
missing_dimensions 非空
retry_count < max_retries
enhancement_stop_reason 为空
```

### 3. 各节点输入输出

- `retrieve`：以用户需求查询 `app/data/*.md`，返回 Top 3 文档，并记录来源。
- `generate_cases`：把需求与 RAG 文本拼成 Prompt；优先调用 LLM；任意调用、解析或校验异常时切到规则生成器。
- `coverage`：扫描全部用例文本，计算 7 维覆盖情况。增强后还会写入 `coverage_after`；若新增用例但覆盖率未提升，设置无进展退出原因。
- `enhance_cases`：根据业务类型和缺失维度追加模板用例，不替换旧用例；记录补充前覆盖率、新增用例和退出原因。
- `run_tests`：逐条将用例分发到取消、支付或创建执行器，真实请求本机 FastAPI Mock 接口并做断言。
- `analyze`：仅分析 `status == "failed"` 的结果。
- `report`：生成 Markdown，统计 Metrics，将 Trace 和 Metrics 保存为 JSON。

`run_agent(requirement)` 当前只返回报告字符串，不返回完整 State。完整细节通过输出文件和查询 API 获取。

## 五、RAG 的真实实现

知识库文件：

- `requirement.md`：创建、取消、支付业务规则
- `api_spec.md`：创建、取消、支付接口字段说明；文档路径是 `/api/*`，实际 Mock 路径是 `/mock/*`
- `test_standard.md`：正常、异常、边界、重复、状态变化、数据一致性等测试规范
- `bug_hitory.md`：重复下单、取消后司机未释放、重复支付等历史缺陷；文件名存在 `hitory` 拼写错误

`app/rag_retriever.py` 的实现不是向量 RAG：

1. 读取 `app/data` 下所有 Markdown。
2. 固定业务关键词在 query 和正文同时出现时加分。
3. 用户 query 的每个字符若出现在文档中也加分。
4. 按分数降序返回 `top_k=3`。
5. 没有切片、Embedding、向量库、Rerank、引用可信度阈值或“无法回答”拒答机制。

因此它更准确的名字是“本地文档轻量相关性检索”。现有 RAG Eval 历史结果中，可回答问题的预期来源命中较好，但不可回答问题的正确拒绝为 `0/10`，不能宣称 RAG 准确率 100%。

## 六、测试用例生成

统一用例结构：

```json
{
  "case_id": "TC_CANCEL_001",
  "title": "用户主动取消未接单订单",
  "precondition": "用户已创建订单，订单状态为 waiting",
  "steps": ["调用取消接口", "查询订单状态"],
  "expected_result": "订单状态变为 cancelled",
  "generation_source": "llm | rule | auto_supplement"
}
```

### LLM 路径

`case_generator.py` 要求模型只返回 JSON 数组，并覆盖正常、异常、边界、重复、状态、资源、数据一致性。解析器支持纯 JSON、Markdown JSON 代码块，以及从混合文本中截取首个 `[` 到最后一个 `]`。基础校验只检查五个必填字段存在，以及 `steps` 是列表；没有严格校验每个字符串字段的类型、ID 唯一性或业务正确性。

LLM 调用使用 `client.chat.completions.create(...)`。主链路没有格式修复重试；失败就直接使用规则生成器。独立的结构化输出评估脚本才实现 API 重试和格式修复重试。

### 规则兜底路径

`case_generator_rule.py`：

- 需求包含“取消”：生成 4 条取消用例。
- 否则包含“支付”：生成 2 条支付用例。
- 其他所有需求：默认生成 2 条订单创建用例。

这个默认分支意味着未知领域会被误归为订单创建，这是当前限制。

## 七、覆盖率与自动补充

覆盖率固定为 7 个维度：

1. 正常场景
2. 异常场景
3. 边界场景
4. 重复操作
5. 状态变更校验
6. 资源释放校验
7. 数据一致性校验

`coverage_tool.py` 将所有用例的 ID、标题、前置条件、步骤和预期结果拼成一段文本，只要某维度任一关键词命中，就判定该维度已覆盖。覆盖率为 `命中维度数 / 7`。参数 `requirement` 当前没有参与计算。

注意：这是启发式文本覆盖率，不是代码覆盖率、接口覆盖率或需求追踪矩阵。宽泛关键词（如“状态”“查询”“校验”）可能造成覆盖率偏高。

`case_enhancer.py` 支持三类业务乘以七个维度，共 21 个具体模板：

| 业务 | 分类关键词 | 自动用例前缀 |
|---|---|---|
| 订单取消 | 取消、撤销、退单 | `TC_CANCEL_AUTO` |
| 支付 | 支付、付款、扣款 | `TC_PAY_AUTO` |
| 订单创建 | 创建、下单、新建订单、发起订单、订单 | `TC_ORDER_AUTO` |

分类优先级是“取消 > 支付 > 订单创建”，防止“订单取消”因为包含“订单”而进入创建逻辑。未知业务不生成补充用例。

增强器保留原始用例，通过 `case_id` 及 `(title, expected_result)` 防止重复，并把新增用例标记为 `generation_source="auto_supplement"`。

三类业务各自的 7 维场景是：

| 维度 | 订单取消 | 支付 | 订单创建 |
|---|---|---|---|
| 正常 | 主动取消 waiting 订单 | 正常支付 | 正常创建 |
| 异常 | 不存在订单 | 金额为 0 | 起点为空 |
| 边界 | 超时自动取消 | 最小金额 0.01 | 起终点相同 |
| 重复 | 重复取消 | 重复支付 | 重复下单 |
| 状态 | accepted -> cancelled | waiting/unpaid -> paid/paid | 创建并分配司机后 accepted |
| 资源 | 取消后司机 available | 支付失败不占司机 | 分配司机后 assigned |
| 一致性 | 详情与列表取消状态一致 | 详情与列表支付状态一致 | 详情与列表订单字段一致 |

无进展保护：若某轮没有新增用例，或新增后覆盖率没有提高，就设置 `enhancement_stop_reason`，停止继续增强；最大轮数仍为 2。

## 八、Mock 业务系统

`app/mock_business_api.py` 使用全局内存字典：

```python
MOCK_DB = {
    "orders": {},
    "drivers": {
        "driver_001": {
            "driver_id": "driver_001",
            "driver_status": "available"
        }
    }
}
```

实际接口：

| 方法 | 路径 | 作用 |
|---|---|---|
| POST | `/mock/reset` | 重置内存数据 |
| POST | `/mock/order/create` | 创建订单，可选 `assign_driver` |
| POST | `/mock/order/cancel` | 用户取消订单 |
| POST | `/mock/order/timeout_cancel` | 模拟超时取消，不真实等待 3 分钟 |
| GET | `/mock/order/{order_id}` | 查询订单详情 |
| GET | `/mock/orders/user/{user_id}` | 查询用户订单列表 |
| GET | `/mock/driver/{driver_id}` | 查询司机 |
| POST | `/mock/payment/pay` | 支付订单 |

核心业务规则：

- 起点或终点为空：`PARAM_ERROR`。
- 起终点相同：`SAME_LOCATION`。
- 同一用户存在 waiting/accepted/running/unpaid 订单：`DUPLICATE_ORDER`。
- `assign_driver=true` 时订单为 accepted，司机变 assigned。
- 取消不存在订单：`ORDER_NOT_FOUND`。
- 重复取消：`REPEAT_CANCEL`。
- accepted 订单取消未提供原因：`CANCEL_REASON_REQUIRED`。
- accepted 订单取消成功后释放司机为 available。
- 超时取消仅允许 waiting 订单，原因写为 `timeout_no_driver`。
- 支付金额小于等于 0：`INVALID_AMOUNT`。
- 重复支付：`REPEAT_PAYMENT`。
- 支付成功后 `payment_status` 和 `order_status` 都变为 paid。

这是演示用 Mock：没有认证、并发控制、事务、数据持久化、真实时间推进、金额精度模型或用户所有权校验。

## 九、API 测试执行器

`app/tools/api_test_tool.py` 不是 pytest 动态生成器，而是 Agent 运行期间的业务执行器。每条用例执行前会调用 `/mock/reset`，然后用 `requests` 发起真实 HTTP 请求，超时 5 秒。

业务分发顺序：

```text
case_id 含 CANCEL 或标题含“取消” -> cancel
case_id 含 PAY 或标题含“支付/付款” -> payment
case_id 含 ORDER 或标题含“创建/下单” -> order_create
否则 -> failed
```

每个业务执行器根据固定 `case_id` 或标题/步骤/预期中的关键词选择场景，建立前置数据，调用接口，再断言返回码、message、订单状态、支付状态、司机状态或详情/列表一致性。

结果结构：

```json
{
  "case_id": "...",
  "title": "...",
  "status": "passed | failed",
  "error_log": "",
  "actual_result": "实际接口响应摘要"
}
```

关键原则：

- 没有 `skipped` 状态，只有 passed/failed。
- 未匹配业务的用例返回 failed。
- 匹配业务但没有具体断言分支的用例返回 failed。
- 连接不到 Mock API 时返回 failed，并提示启动 Uvicorn。
- 不存在任何“未知用例默认通过”逻辑。

局限：LLM 可以生成格式正确但措辞与关键词分支不匹配的用例，此时会失败为“执行器能力缺失”；执行器与生成器之间还没有稳定的结构化 `business_type/scenario_type` 契约。

## 十、失败分析、报告和可观测性

`log_analysis_tool.py` 当前只显式识别：

- 司机资源仍为 assigned -> 资源释放异常
- 未配置执行断言 -> 测试执行器能力缺失
- 未识别业务 -> 业务分类失败
- 其他 -> 未知异常

报告 `app/outputs/test_report.md` 包含八部分：需求、RAG 依据、测试用例、执行结果、缺陷分析、覆盖率、自动补充历史、Agent 指标。

Trace 项结构：

```json
{
  "timestamp": "本地 ISO 时间",
  "node_name": "coverage",
  "action": "测试覆盖率分析",
  "status": "success",
  "detail": {}
}
```

Trace 记录的是节点级业务摘要，不包含 token 数、模型延迟、HTTP 请求耗时、异常堆栈或分布式 trace id。默认 `status` 总是 success，节点抛异常时通常无法完成保存。

Metrics 主要字段：

```text
total_cases, passed_cases, failed_cases, pass_rate
coverage_rate, covered_dimensions, total_dimensions, missing_dimensions
retry_count, added_cases_count, enhancement_stop_reason
llm_generated_cases, rule_generated_cases, auto_supplement_cases
unknown_generated_cases, rag_docs_count, bug_count, failed_case_ids
```

输出文件只保存最近一次执行，重复运行会覆盖之前结果。

## 十一、FastAPI 与前端

Agent API：

| 方法 | 路径 | 返回 |
|---|---|---|
| GET | `/` | 服务状态文本 |
| POST | `/agent/run` | 同步运行 Agent，返回报告 |
| GET | `/agent/trace` | 最近一次 Trace |
| GET | `/agent/metrics` | 最近一次 Metrics |
| GET | `/agent/report` | 最近一次报告 |

CORS 只允许本机 `localhost:5173` 和 `127.0.0.1:5173`。

React 前端是单页控制台：

- 左侧输入业务需求，可运行 Agent 或读取最近报告。
- 右侧展示 6 个摘要指标。
- 三个 Tab 展示 Markdown 原文、Metrics JSON、Trace 列表。
- 前端没有 Markdown 渲染器，报告用 `<pre>` 原样显示。
- 没有登录、历史任务列表、进度推送、取消任务、报告下载或并发任务隔离。
- `App.css` 与 Vite 模板遗留的 `index.css` 同时存在，部分全局样式可能冲突。

## 十二、测试与评估体系

pytest 当前共 32 个测试：

- Mock API 业务测试：创建成功、参数错误、相同起终点、重复创建、取消、取消原因、司机释放、订单列表、超时取消、支付、重复支付。
- 增强器/执行器测试：取消分类优先级、21 个模板完整性、未知业务不补充、保留旧用例、未知执行用例失败、无进展停止重试。
- 结构化输出评估单测：JSON 提取、Markdown 包裹、字段缺失、字段类型、根类型、402/429/超时分类、API 重试、格式修复、JSON 报告和统计分母。

独立评估脚本：

- `evals/eval_rag.py`：评估 Top-K 来源命中、不可回答拒绝和 citation source 校验。
- `evals/eval_structured_output.py`：直接调用模型，使用 Pydantic 严格校验；区分 API reliability 与 structured output quality；支持可重试 API 错误和格式修复。
- `evals/eval_agent_performance.py`：测量整个 `run_agent` 的平均、P50、P95、最小和最大耗时。
- `app/eval/evaluate_agent.py`：按报告关键词命中率、覆盖率、通过率和重试次数汇总；它是较早的一套评测实现。

评估边界：结构化输出 Eval 与生产主链路并非同一实现；Eval 的严格 Schema 和修复重试不能自动算作主 Agent 已具备的能力。

## 十三、关键设计事实和风险

1. Agent 有真实 LangGraph 条件回路，不是普通函数列表；但状态只存在单次同步调用内。
2. LLM 失败有规则兜底，所以“流程成功”不代表“LLM 成功”。必须结合 `generation_source` 判断。
3. 覆盖率是文本关键词启发式指标，不能代表业务真实覆盖充分性。
4. 自动增强是 21 个预设模板，不是 LLM 自主规划。
5. API 执行是真实 HTTP 调用，但目标是同进程 FastAPI 中的内存 Mock 服务。
6. Mock DB 是全局共享字典，`reset` 会影响其他并发任务；系统不适合并发运行。
7. 测试执行器依赖 case ID 和自然语言关键词，LLM 自由措辞可能导致无法路由。
8. API 响应始终多为 HTTP 200，业务失败通过 JSON `code` 表达，这不等于标准 REST 错误处理。
9. 报告、Trace、Metrics 是固定路径，后一次执行覆盖前一次。
10. 部分旧文件存在中文编码显示历史问题，README 的部分统计和描述已落后于代码。
11. `api_spec.md` 写 `/api/*`，真实接口是 `/mock/*`，存在文档与实现路径差异。
12. `case_generator_rule.py` 会把未知需求默认为创建订单，而增强器会把未知需求识别为 unknown，两者策略不一致。

## 十四、理解项目时的回答要求

收到这份上下文后，请先用简洁语言确认你理解了以下五点：

1. 这是“LLM + 规则 + LangGraph + HTTP Mock 测试”的混合系统。
2. 主流程有 7 个节点和覆盖不足时的条件回路。
3. 三类业务是订单取消、支付、订单创建；每类都有 7 维补充模板。
4. 未配置执行逻辑的用例会失败，不会默认通过。
5. RAG、覆盖率、Mock API 和评估都有明确边界，不能夸大。

然后再处理我的后续问题。若我的问题是：

- **解释项目**：按“目标 -> 架构 -> 数据流 -> 核心模块 -> 限制”回答。
- **排查 Bug**：沿 `requirement -> test_cases -> coverage -> executor -> result -> report` 定位，并指出具体文件和函数。
- **新增业务**：同时考虑知识库、生成器、7 维模板、覆盖关键词、Mock API、执行器、失败分析、指标、测试和前端展示，不能只改一个文件。
- **优化 RAG**：先承认当前是关键词检索，再讨论分块、Embedding、向量库、Rerank、阈值与不可回答拒绝。
- **优化用例执行**：优先建议增加结构化 `business_type`、`scenario_type`、`input_data`、`assertions`，降低对中文关键词路由的依赖。
- **用于简历/答辩**：准确描述为可运行原型；强调闭环、条件回路、降级策略、可观测性和评估，但不要声称生产落地或高准确率。
- **修改代码**：保持现有技术栈和数据结构，补充最小必要测试，并说明运行验证结果。

现在请先确认你已理解项目全貌，并等待我的具体问题。

## Prompt 正文结束
