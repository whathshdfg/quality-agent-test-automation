# Structured Output Failure Analysis

## 当前结果

30 runs  
23 first-pass success  
7 retry triggered  
0 retry recovered

补充观察：

- `reports/structured_output_eval.json` 当前文件无法被 PowerShell `ConvertFrom-Json` 标准解析，原因是 `input` 字段行内字符串未正常闭合，文件本身不是严格合法 JSON。
- 以下失败 Case 信息来自该文件的原始文本内容，以及代码路径 `evals/eval_structured_output.py`、`app/tools/case_generator.py`、`app/agent_graph.py`。
- Eval 结果中没有保存原始 LLM 输出，也没有保存 Retry 后返回内容，因此 Markdown code block、截断、额外自然语言、缺字段、字段类型错误等只能在有证据时判断；当前 7 个失败没有可检查的模型文本。

## 失败 Case

### run_id 24

- 输入：与其他 29 次相同，订单取消场景需求；当前文件中该字段为乱码且未闭合，导致整个 JSON 文件不可被标准 JSON 解析。
- 原始 LLM 输出：未记录；`llm_returned=false`。
- JSON 是否解析失败：结果标记为 `first_json_valid=false`，但失败原因不是可见的非法 JSON，而是 LLM API 请求异常。
- 字段校验是否失败：结果标记为 `first_pydantic_valid=false`，但没有进入可观察的字段校验输出。
- 缺失字段：无证据，未记录。
- 字段类型错误：无证据，未记录。
- 是否包含 Markdown code block：无法判断，未记录原始输出。
- 是否被截断：无法判断，未记录原始输出。
- 是否存在额外自然语言：无法判断，未记录原始输出。
- Retry 实际执行次数：1。
- Retry 后返回内容：未记录；最终错误为 API 402。
- 最终失败原因：`APIStatusError: Error code: 402 - Insufficient Balance`。

### run_id 25

- 输入：同 run_id 24。
- 原始 LLM 输出：未记录；`llm_returned=false`。
- JSON 是否解析失败：结果标记为 `first_json_valid=false`，但可见最终原因是 LLM API 请求异常。
- 字段校验是否失败：结果标记为 `first_pydantic_valid=false`，无字段校验细节。
- 缺失字段：无证据，未记录。
- 字段类型错误：无证据，未记录。
- 是否包含 Markdown code block：无法判断，未记录原始输出。
- 是否被截断：无法判断，未记录原始输出。
- 是否存在额外自然语言：无法判断，未记录原始输出。
- Retry 实际执行次数：1。
- Retry 后返回内容：未记录；最终错误为 API 402。
- 最终失败原因：`APIStatusError: Error code: 402 - Insufficient Balance`。

### run_id 26

- 输入：同 run_id 24。
- 原始 LLM 输出：未记录；`llm_returned=false`。
- JSON 是否解析失败：结果标记为 `first_json_valid=false`，但可见最终原因是 LLM API 请求异常。
- 字段校验是否失败：结果标记为 `first_pydantic_valid=false`，无字段校验细节。
- 缺失字段：无证据，未记录。
- 字段类型错误：无证据，未记录。
- 是否包含 Markdown code block：无法判断，未记录原始输出。
- 是否被截断：无法判断，未记录原始输出。
- 是否存在额外自然语言：无法判断，未记录原始输出。
- Retry 实际执行次数：1。
- Retry 后返回内容：未记录；最终错误为 API 402。
- 最终失败原因：`APIStatusError: Error code: 402 - Insufficient Balance`。

### run_id 27

- 输入：同 run_id 24。
- 原始 LLM 输出：未记录；`llm_returned=false`。
- JSON 是否解析失败：结果标记为 `first_json_valid=false`，但可见最终原因是 LLM API 请求异常。
- 字段校验是否失败：结果标记为 `first_pydantic_valid=false`，无字段校验细节。
- 缺失字段：无证据，未记录。
- 字段类型错误：无证据，未记录。
- 是否包含 Markdown code block：无法判断，未记录原始输出。
- 是否被截断：无法判断，未记录原始输出。
- 是否存在额外自然语言：无法判断，未记录原始输出。
- Retry 实际执行次数：1。
- Retry 后返回内容：未记录；最终错误为 API 402。
- 最终失败原因：`APIStatusError: Error code: 402 - Insufficient Balance`。

### run_id 28

- 输入：同 run_id 24。
- 原始 LLM 输出：未记录；`llm_returned=false`。
- JSON 是否解析失败：结果标记为 `first_json_valid=false`，但可见最终原因是 LLM API 请求异常。
- 字段校验是否失败：结果标记为 `first_pydantic_valid=false`，无字段校验细节。
- 缺失字段：无证据，未记录。
- 字段类型错误：无证据，未记录。
- 是否包含 Markdown code block：无法判断，未记录原始输出。
- 是否被截断：无法判断，未记录原始输出。
- 是否存在额外自然语言：无法判断，未记录原始输出。
- Retry 实际执行次数：1。
- Retry 后返回内容：未记录；最终错误为 API 402。
- 最终失败原因：`APIStatusError: Error code: 402 - Insufficient Balance`。

### run_id 29

- 输入：同 run_id 24。
- 原始 LLM 输出：未记录；`llm_returned=false`。
- JSON 是否解析失败：结果标记为 `first_json_valid=false`，但可见最终原因是 LLM API 请求异常。
- 字段校验是否失败：结果标记为 `first_pydantic_valid=false`，无字段校验细节。
- 缺失字段：无证据，未记录。
- 字段类型错误：无证据，未记录。
- 是否包含 Markdown code block：无法判断，未记录原始输出。
- 是否被截断：无法判断，未记录原始输出。
- 是否存在额外自然语言：无法判断，未记录原始输出。
- Retry 实际执行次数：1。
- Retry 后返回内容：未记录；最终错误为 API 402。
- 最终失败原因：`APIStatusError: Error code: 402 - Insufficient Balance`。

### run_id 30

- 输入：同 run_id 24。
- 原始 LLM 输出：未记录；`llm_returned=false`。
- JSON 是否解析失败：结果标记为 `first_json_valid=false`，但可见最终原因是 LLM API 请求异常。
- 字段校验是否失败：结果标记为 `first_pydantic_valid=false`，无字段校验细节。
- 缺失字段：无证据，未记录。
- 字段类型错误：无证据，未记录。
- 是否包含 Markdown code block：无法判断，未记录原始输出。
- 是否被截断：无法判断，未记录原始输出。
- 是否存在额外自然语言：无法判断，未记录原始输出。
- Retry 实际执行次数：1。
- Retry 后返回内容：未记录；最终错误为 API 402。
- 最终失败原因：`APIStatusError: Error code: 402 - Insufficient Balance`。

## 根因分类

- LLM 请求异常 / APIStatusError 402 Insufficient Balance：7。
- 非法 JSON：0 个有证据支持；当前 7 个没有模型输出文本。
- JSON 外包含额外文本：0 个有证据支持。
- 缺字段：0 个有证据支持。
- 字段类型错误：0 个有证据支持。
- 返回对象而非数组：0 个有证据支持。
- Markdown 包裹解析失败：0 个有证据支持；并且 `extract_json_array()` 有基础 Markdown 去壳逻辑。
- Retry Prompt 没有针对第一次错误进行纠正：7 个代码层面成立；Retry 每次调用 `call_llm(requirement)`，没有传入第一次错误信息。
- Retry 实际没有重新调用模型：0 个有证据支持；`retry_count=1` 且循环逻辑会再次执行 `call_llm(requirement)`。
- Eval 对 Retry 的统计逻辑存在问题：存在记录粒度问题，不能区分首轮错误和 Retry 错误；但 `final_success` 的计数逻辑本身与当前数据一致。
- Rule Fallback 实际成功但 Eval 将其记成失败：否。Eval 没有调用 Rule Fallback，不能说 fallback 成功后被记成失败。
- Eval 输出文件格式问题：1 类问题，当前 `structured_output_eval.json` 不是严格合法 JSON。

## Retry 机制检查

- 首轮失败以后有没有再次调用 LLM：有。`evaluate_once()` 使用 `while attempts <= max_retries`，默认 `STRUCTURED_EVAL_MAX_RETRIES=1` 时最多执行 2 次；失败 Case 的 `retry_count=1` 表示发生了第二次尝试。
- Retry Prompt 是否与第一次 Prompt 完全相同：是。每次都调用 `call_llm(requirement)`，内部仍然使用 `build_prompt(requirement)`，没有任何 retry-specific prompt。
- 是否把第一次错误信息反馈给模型：没有。`except` 中只把异常写入本地 `error_reason`，没有构造修复提示，也没有把错误类型、原始输出、schema 差异传回下一次调用。
- 是否重新解析 Retry 返回值：会。每次尝试都会执行 `extract_json_array(output)`。
- 是否重新进行字段校验：会。每次解析成功后都会执行 `validate_cases(raw_cases)`。
- Retry 成功以后是否正确更新 `final_success`：会。任意一次尝试解析与校验通过后设置 `final_success=True` 并 `break`，`summarize()` 按 `final_success` 统计。
- 是否实际上调用了 Rule Fallback，但 Eval 将其记成失败：没有。`eval_structured_output.py` 直接调用自己的 `call_llm()`，只复用 `build_prompt()` 和 `extract_json_array()`，没有调用 `generate_test_cases()`；业务入口 `generate_test_cases()` 中的 Rule Fallback 不参与这次 Eval。
- 统计/记录问题：`error_reason` 会被后续 Retry 异常覆盖，导致无法知道首轮失败的真实错误；结果中不保存 `raw_output`、`retry_output`、每轮错误、每轮 JSON/字段校验细节，因此无法完成更细的结构化失败归因。

## 优化建议

### P0

- 先修 Eval 观测能力：为每次 attempt 保存 `attempt_no`、是否拿到 LLM 内容、原始输出摘要、解析错误、字段校验错误、缺失字段、类型错误、是否 Markdown 包裹、是否截断、是否额外自然语言。否则后续结构化输出质量问题仍然不可诊断。
- Retry Prompt 需要带上第一次失败信息：包括原始输出、解析/校验错误、目标 schema，并明确要求只返回修正后的 JSON 数组。
- 对 APIStatusError 402 这类不可通过 Prompt 修复的错误单独分类，不应算作“结构化输出格式失败”。

### P1

- 将 Eval 输出保证为严格合法 JSON，并增加生成后自校验。
- 将 `first_json_valid` 和 `first_pydantic_valid` 分开记录。当前首轮任何异常都会把两者都置为 false，无法区分“没拿到 LLM 响应”和“拿到响应但 JSON/Schema 失败”。
- `llm_returned` 不应通过 `error_reason` 字符串包含 `JSON` / `Validation` 推断，应显式记录 `output is not None`。

### P2

- 增加 `final_source` 字段，区分 `llm_first_pass`、`llm_retry`、`rule_fallback`、`api_error`。
- 如需评估业务整体可用性，另建一个调用 `generate_test_cases()` 的 Eval，单独统计 Rule Fallback 恢复率；当前 Eval 只适合评估 LLM 直连结构化输出。
- 对 `extract_json_array()` 增加更多边界测试，例如前后自然语言、Markdown code block、对象包数组、半截 JSON。
