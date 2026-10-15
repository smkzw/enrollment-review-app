执行器在工作线程（`ThreadPoolExecutor`）中运行同步解构，因此受限的 `time.sleep` 回退是在事件循环之外执行的，这与现有的同步 600 秒 HTTP 等待一致。实现已完成并经核实。最终报告如下：

# 执行输出：phase5-semantic-transient-retry-20260901 - worker_01

## 边界与上下文检查

- 在运行器绑定的工作空间（phase5 worktree，分支 `codex/phase5-clinical-facts-profile`）内工作；除了初始读取集外，仅读取了分配的实现所需的项目文件。
- 上下文的 `Source Of Truth` 部分是一个 TODO 占位符，没有明确授权编辑文件列表。我从任务描述中推导出了实现目标（"方案语义模型" = protocol-deconstruction semantic model transport），并将编辑范围仅限于 `app/agents/deepseek_protocol_transport.py`，该文件已包含此分支中未提交的 phase 5 更改（我仅在当前工作树状态上进行了增量修改）。
- 根据 `work-item` 分工，未编写测试文件（worker_02 负责），未运行 `focused-regression` 套件（worker_03 负责），未创建报告或进程文件。

## 已完成工作

**异常边界审查（修改前）。**
- `app/agents/deepseek_protocol_transport.py` 构建了其同步的 `OpenAI` 客户端，其中 `max_retries=0` 且 `timeout=600.0`。`_complete()` 对 `chat.completions.create` 进行单次 HTTP 尝试；只有内容级别的缺陷（长度截断、格式错误的 JSON、空主体）在 2 次尝试的循环内进行重试。传输异常会传播到 `start()`/`continue_session()`，将其包装为 `ProtocolAgentCallError`：将超时类异常映射为 `TRANSPORT_TIMEOUT`，将所有其他异常映射为默认的 `SEMANTIC_CALL_FAILED`。
- SAR 恢复路径（`app/agents/protocol_deconstructor.py:3617-3665`）仅针对 `TRANSPORT_TIMEOUT` 通过 `transport_factory()` 以新鲜传输方式重试一次，在重试前后校验传输标识（缓存键、线路契约、分段支持）。5xx/429/连接错误在任何层级都没有被重试 —— 这是缺失的部分。
- 异步同级（`app/llm/client.py` `_retry`）重试 `APIConnectionError/APITimeoutError/RateLimitError`，但值得注意的是，在该路径上也不重试 5xx (`InternalServerError`)。
- 环境已验证：`.venv` 使用 openai 2.37.0 / httpx 0.28.1；`APITimeoutError` 继承自 `APIConnectionError`，`RateLimitError`/`InternalServerError` 继承自 `APIStatusError`，`httpx.TimeoutException` 继承自 `httpx.TransportError` —— 异常元组中的子类排序很重要。

**最小化实现**（三个局部修改，供应商无关，适用于所有六个后端）：
1. Imports：添加了 `logging`、`time`，并扩展了 `openai` 导入以包含 `APIConnectionError`、`InternalServerError`、`RateLimitError`。
2. 模块常量：`TRANSPORT_TRANSIENT_MAX_ATTEMPTS = 3`（1 次尝试 + 2 次重试），`TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS = 2.0`（线性 `2s × 尝试次数` → 2s, 4s），`_TRANSPORT_TIMEOUT_ERRORS`（首先检查 `APITimeoutError`、`httpx.TimeoutException`、`TimeoutError` 以保持子类顺序），`_TRANSIENT_RETRYABLE_ERRORS`（`InternalServerError` = 5xx, `RateLimitError` = 429, `APIConnectionError`，原始 `httpx.TransportError`）；模块 `logger`。
3. 新的 `_send_completion()` 方法，带有每次尝试的中文警告日志；`_complete()` 现在调用它而不是原始的 `create(...)`。每次尝试都会重新发送**相同的预构建 kwargs**（相同的模型、消息、响应格式），因此会话历史记录和模型路由不会改变。超时类型立即重新抛出 —— 现有的 `TRANSPORT_TIMEOUT` → SAR 新鲜传输契约保持不变，600s 的等待时间不会乘以 N。非瞬态 4xx 也会立即传播。

**设计上的刻意决策**（供 Codex 确认）：429 不遵循 `Retry-After` 标头（匹配 `app/llm/client.py` 中现有的 `_retry` 惯例；将 429 恶意滥用限制在 ≤ ~6s 内）；SDK `max_retries` 保持为 0，因此重试完全明确且可测试（SDK 默认重试也会重试超时，并会静默破坏 SAR 契约）；最坏情况下，每次逻辑请求的 HTTP 调用次数受限于 2（内容修复）× 3（传输）= 6，外加 SAR 的一次超时重试。

## 产物与证据

- `app/agents/deepseek_protocol_transport.py` — 唯一编辑的文件（导入；常量 + 元组；`_send_completion` + 一个调用点）。
- 没有提交新的测试；错误注入行为通过一次性内联脚本进行了验证（未创建文件），语义如下，全部通过：
  - 5xx×2 然后成功 → 在第 3 次尝试时成功，重新发送相同的有效载荷，等待 `[2.0, 4.0]s`。
  - 429 然后成功；原始 `httpx.ConnectError` 然后成功 → 每次都在第 2 次尝试时成功。
  - 持续 500 → **正好 3 次尝试**，然后 `ProtocolAgentCallError` `SEMANTIC_CALL_FAILED`，消息中没有 API 密钥，等待 `[2.0, 4.0]s`。
  - 400 → 单次尝试，零重试，零睡眠。
  - `httpx.ReadTimeout` 和 `APITimeoutError` → 单次尝试，保留 `TRANSPORT_TIMEOUT`（SAR 契约保持不变）。
  - 失败的 `start()` 会保持会话前注册的历史记录完整（用户仅审计恢复）；`continue_session` 重试瞬态错误，同时保持会话 ID 和 user/assistant/user/assistant 顺序；`semantic_cache_identity()` 不受影响。

## 命令与观察结果

- `.venv/bin/python -c` 异常层次结构检查 → openai 2.37.0，httpx 0.28.1；子类化确认如上所述。
- `.venv/bin/python -m py_compile app/agents/deepseek_protocol_transport.py` → OK。
- 内联错误注入脚本（两个 heredoc 运行；第二个修复了 **harness** 中的一个错误 — 单输出模拟在重试时引发 `IndexError`，这掩盖了 exhaust 路径；实现是正确的） → 所有检查均通过。
- `.venv/bin/python -m pytest tests/v2/protocols/test_deepseek_protocol_transport_slice3.py -q` → **18 passed**，包含未更改的超时分类和内容修复测试。
- 线程检查：执行器在 `ThreadPoolExecutor` 工作线程中运行同步去重构（`app/services/evidence_processing_executor.py:844`），因此传输回退的 `time.sleep` 在事件循环之外阻塞，与今天现有的同步 600s HTTP 等待相同。

记录的观察结果（超出分配的范围，仅供 Codex 使用，未采取行动）：
- `app/llm/client.py` 的异步 `_retry` 在 OCR/审查/遗留的 `deconstruct_chat` 路径上不重试 5xx (`openai.InternalServerError`)。
- 同级同步传输 `app/agents/deepseek_evidence_normalizer_transport.py` 和 `app/agents/phase_applicability_transport.py` 也以 `max_retries=0` 构建 OpenAI 客户端，并暴露相同的瞬态故障；如果 Codex 需要对它们进行同等的处理，`_send_completion` 模式可以直接移植。

## 阻碍或缺失的环境

无。环境完整（`.venv`，pytest），所有允许的检查均已运行。

## 重跑请求或下一步

无需重跑。给同行/Codex 的移交说明：
- worker_02 可以通过构造函数注入模拟 `client` 并引发 `openai.InternalServerError/RateLimitError`/`httpx.ConnectError`/`APITimeoutError` 来注入错误；通过 `monkeypatch.setattr("app.agents.deepseek_protocol_transport.time.sleep", ...)` 或修补 `TRANSPORT_TRANSIENT_RETRY_BACKOFF_SECONDS` 来中和/记录睡眠；`TRANSPORT_TRANSIENT_MAX_ATTEMPTS`/`..._BACKOFF_SECONDS` 是模块级 monkeypatch 常量。
- worker_03 应在既定的 SAR 审查范围内运行聚焦回归；未更改的预期：超时 → `TRANSPORT_TIMEOUT`（一次新鲜传输 SAR 重试），耗尽的瞬态错误 → `SEMANTIC_CALL_FAILED`，任何传输层都没有历史记录变动，没有模型路由更改，`semantic_cache_identity` 相同。
