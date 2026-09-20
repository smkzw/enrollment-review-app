# 执行输出：r3-gemini-product-transport-20260908 - worker_01

## 边界与上下文检查

- 执行者上下文和计划已在 `.trellis/tasks/09-05-phase55-dual-vlm-page-review/{context,plans}/` 中找到（提示中的顶层 `context/`、`plans/` 路径相对于数据包根目录，而非工作树根目录；已使用 `find` 定位并记录）。
- 所有编辑均保持在当前工作树的 `app/` 和 `tests/` 内。未修改 `docs/`、`plans/`、`.env*`、`scripts/`；未读取临床资料；未进行网络/模型/安装操作；未进行递归分发。
- 运行时未读取 OMP/Hermes/home 配置：`rg` 已确认 `app/llm/gemini_transport.py` 中没有 `Path.home`、`expanduser`、`.env` 或 sqlite 身份验证读取。`scripts/benchmark_direct_transports.py` 仅作为只读传输形状参考使用（请求体、标头、SSE 处理、完成映射）；产品模块不导入它。
- 未声明最终的临床/监管验收；未执行实际模型运行。

## 已执行的工作

产品现在运行两个独立的主读取器：main-A = GLM-5.3-Flash（zhipu 直连，effort `low`，未更改），main-B = `gemini-3.7-flash`，通过新的原生 google-antigravity 传输（effort `high`）。双读取器结构保持不变；未恢复第三个读取器。

1. **新模块 `app/llm/gemini_transport.py`**（独立，产品所有）：
   - `build_gemini_request` 将现有的单阶段主读取消息（`build_page_review_messages` 输出）转换为原生 `v1internal:streamGenerateContent` 请求体：系统消息合并到 `systemInstruction` 中，user/assistant → `user`/`model` 内容，`image_url` 数据 URI → `inlineData{mimeType,data}`（基础 base64 未改动），`generationConfig = {maxOutputTokens, thinkingConfig{thinkingLevel: HIGH, includeThoughts: true}}`。拒绝系统/user/assistant 之外的角色（不重新标记）；effort 限制为 {low, high}。请求体中任何地方都没有 `temperature`。
   - `direct_gemini_completion(route, messages, max_tokens) -> PageCompletion` 流式传输原生 SSE（`data:` 行，跳过 `[DONE]`），将思考部分与正文分开，并记录 `usageMetadata`、`modelVersion`、`responseId` 收据，以及 `output_lengths.content_characters` / `reasoning_content_characters`。
   - 完成映射：`STOP/completed→stop`，`MAX_TOKENS→length`，`SAFETY/RECITATION/BLOCKLIST/PROHIBITED_CONTENT/SPII→content_filter`；不带候选者的 `promptFeedback.blockReason` → content_filter。未知完成映射保持原样传递，并被 `read_page` 的非终结保护机制拒绝。
   - 流中断（流中间的 `httpx.HTTPError` 或格式错误的 SSE JSON）会引发 `GeminiTransportError`；部分正文从不返回，因此永远不会被接受。`modelVersion` ≠ 已配置模型 → 拒绝（无静默替换）。非 200 响应会引发带有 `status_code` 的相同错误，因此现有的 429 等待循环和长度预算加倍功能保持不变。`CancelledError` 传播（job 取消保持不变）。凭据从不记录（模块中没有日志记录；错误携带 ≤400 字符的服务器响应片段）。
2. **预检已适应原生 Gemini** (`app/llm/page_review_harness.py`)：`resolve_route_model` 现在在 `google-antigravity` 上提前返回——无需 OpenAI `/models` 调用——而是验证 access token、project ID、HTTPS 端点，并在缺少任何内容时明确失败。main-A 继续像以前一样解析 `/models`。
3. **路由配置**：`require_page_reader_routes` 支持 `PAGE_REVIEW_MAIN_B_PROVIDER=google-antigravity`，并使用明确的 env 凭据：`GEMINI_ACCESS_TOKEN`（或 `PAGE_REVIEW_MAIN_B_API_KEY`）、`GEMINI_PROJECT_ID`、`GEMINI_BASE_URL`/`PAGE_REVIEW_MAIN_B_BASE_URL`；缺少的项目在 `PageReviewConfigError` 中按名称列出；Gemini 端点必须为 HTTPS。`PageReaderRoute` 增加了一个可选的 `project_id` 字段（非 Gemini 为空）。
4. **默认值** (`app/config.py`)：`PAGE_REVIEW_MAIN_B_PROVIDER` 默认 → `google-antigravity`，`PAGE_REVIEW_MAIN_B_MODEL` 默认 → `gemini-3.7-flash`；添加了 `GEMINI_ACCESS_TOKEN/GEMINI_PROJECT_ID/GEMINI_BASE_URL` 常量。激活的 MTPLX 默认值已被移除，而历史提供商（`mlx-serve`、`mtplx`、`cms-smk`）保持完全可解析，以便通过明确的 env 读取历史标识（保留了 `mtplx` 仅限本地的默认 base URL）。
5. **调度**：新的 `harness.direct_completion` 按提供商进行路由（google-antigravity → 原生 Gemini 传输，其他所有 → `direct_openai_completion`）并将其作为 `read_page`、`PageReviewAdmission`、`PageReviewJobExecutor`、`review_page`/`review_pages`、`read_page_batch` 和 `page_review_context_layout` 中的默认值连接；`direct_openai_completion` 本身未更改（GLM 通道 + 现有测试）。

## 工件和证据

- `app/llm/gemini_transport.py` (new) — native transport, request builder, finish map.
- `app/llm/page_review_harness.py` — gemini route resolution, `project_id` field, preflight branch, `direct_completion` dispatch, exports.
- `app/config.py` — GEMINI_* constants; main-B defaults switched to Gemini (historical providers preserved).
- `app/llm/page_review_admission.py`, `app/llm/page_review_batch_experiment.py`, `app/llm/page_review_context_layout.py`, `app/services/page_review_execution.py`, `app/services/page_review_job_executor.py` — default completion now dispatch-aware.
- `tests/v2/llm/test_gemini_transport.py` (new, 19 tests) — HTTP-mock coverage: request roles/inlineData image/budget/HIGH effort/no temperature, 429→60s wait→retry, MAX_TOKENS→budget doubling (12000→24000 observed in captured bodies), SAFETY finish and prompt-block → content_filter, stream interruption and malformed SSE → partial text rejected (endpoint failure), mid-stream `CancelledError` propagation, `modelVersion` mismatch rejection, missing `GEMINI_PROJECT_ID`/`GEMINI_ACCESS_TOKEN` explicit failures, HTTPS endpoint enforcement, read-only main-reader identity without credentials (64-hex) under new Gemini defaults, formal-job preflight resolving both lanes with zero requests to the Gemini host (only main-A `/models`), lane dispatch selection, full `read_page` record identity (provider/model/effort/endpoint/usage), and historical mtplx identity still resolvable.
- `tests/v2/services/test_isolated_normalization_entry.py` — test env now pins main-B explicitly (was implicitly relying on the removed mtplx default).

## 命令和观察

- `.venv/bin/python -m pytest tests/v2/llm/ tests/v2/services/test_isolated_normalization_entry.py -q` → **131 passed, 1 skipped** (skip = live-connectivity gate, untouched).
- `.venv/bin/python -m pytest tests/v2/services/ tests/v2/api/{test_page_review,test_page_length_recovery,test_page_review_resume,test_fact_normalization}.py tests/v2/llm/ -q` → **618 passed, 2 skipped**.
- `.venv/bin/python -m pytest tests/test_page_review_context_layout.py -q` → **5 passed**.
- Import/signature probe confirmed `read_page` and `PageReviewAdmission` defaults resolve to `direct_completion`; `py_compile` clean on all touched files.
- Prototype probe of httpx mock semantics (async-iterator content, mid-stream `ReadError`, cancellation) validated before writing tests.

## 阻碍或缺失的环境

无阻碍。两项决策需 Codex 验收审查：
1. **端点默认**：`GEMINI_BASE_URL` 将已验证的主机 (`https://daily-cloudcode-pa.googleapis.com`) 作为代码默认值，可被 env 覆盖；access token 和 project ID 没有默认值，在缺失时会明确失败。这使得在未配置 Gemini 时，只读的 `main_reader_identity` 合约（现有测试 `test_read_only_identity_needs_no_model_credentials`）能继续工作。如果您改为要求严格的 env 配置端点，则只读标识路径需要重新设计。
2. **`project_id` 特意从 `route_identity`/`main_reader_identity` 中排除**（与凭据相邻；避免作业负载变动）。提供商/端点/模型的更改仍然会使作业路由标识失效。

## 重发请求或后续步骤

- 无需重发。剩余未验证（按边界）：未进行实际的 `gemini-3.7-flash` 网络/模型运行——SSE 事件形状、`thinkingLevel` 映射和 `modelVersion` 语义均遵循 `scripts/benchmark_direct_transports.py` 中已验证的基准传输，但未针对实时端点进行重新确认。Codex 可能需要在配置真实凭据后运行一次正式的实时预检。
- `.env.example` 仍记录了 mtplx 作为 main-B 默认值（env 文件超出本次修改边界）；如果接受，Codex 可能希望对其进行更新。
- 产品施工已完成；根据分配，详细的跨模型基准测试 (MTPLX 本地运行) 特意未准备。
