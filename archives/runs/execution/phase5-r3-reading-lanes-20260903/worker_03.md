# 执行输出：phase5-r3-reading-lanes-20260903 - worker_03

## 边界与上下文检查

- 仅在运行器绑定的工作区（仓库工作树 `phase5-clinical-facts-profile`）内工作；未读取或写入任何生产路径。
- 已阅读初始读取集：`context/phase5-r3-reading-lanes-20260903_execution_context.md`, `plans/codex_execution_phase5-r3-reading-lanes-20260903.md`。
- 分配的项目（工作项 3）：运行聚焦回归测试 + 独立验证 (a) MTPLX 未进入主读取，(b) DeepSeek 不在读取通道中，(c) 仅将 OCR 作为 sidecar。
- **时序观察（证据）：** 上下文创建于 2026-09-03 09:02:29 CST；在 09:05:27 进行验证时，最后一次与读取相关的文件修改时间为 08:58（例如 `app/agents/evidence_normalizer.py`，`app/config.py`）。Worker_02 的 R3 更改尚未写入树中。因此，我的运行是**基准（R3 前）回归 + 针对当前代码的独立不变性审计**，它为 Codex 提供了在 worker_02 的工作落地后可以重新运行的确切重新验证命令集。
- 未进行源代码编辑（我的项目是验证，而非实现）。未创建同级进程文件；根据运行器策略，此报告在最终消息中返回。

## 已执行工作

### 1. 聚焦回归（基准，R3 前树）—— 全部通过

环境：`.venv/bin/python` (Python 3.12.13)，pytest。四个批次共 200 个通过，1 个跳过；该跳过是实时网络门控 `test_independent_vlm.py:552`（"Set INDEPENDENT_VLM_LIVE=1…"）—— 按设计不出网络。

| 套件 (Suite) | 结果 |
|---|---|
| `tests/v2/agents/test_mtplx_semantic_route_regressions.py` | 通过 |
| `tests/v2/agents/test_evidence_normalizer_transport_config.py` | 通过 |
| `tests/v2/agents/test_fresh_subject_runtime_routing_adversarial.py` | 通过 |
| `tests/v2/llm/test_independent_vlm.py` | 53 通过, 1 跳过 |
| `tests/v2/agents/test_evidence_normalizer_adapter.py` | 通过 |
| `tests/v2/evidence/test_ocr_adapter_cache.py` | 通过 |
| `tests/v2/evidence/test_selective_vision_review.py` | 通过 |
| `tests/tools/test_fresh_run_identity_adversarial.py` | 通过 |
| `tests/v2/services/test_evidence_sidecar_preparation.py` | 通过 |
| `tests/v2/services/test_fact_normalization_command_service.py` | 通过 |
| `tests/v2/api/test_fact_normalization.py` | 通过 |
| `tests/tools/test_phase5_acceptance_fresh_runtime.py` | 通过 |
| `tests/v2/agents/test_mtplx_whole_candidate_ex06_deterministic_verification.py` + `tests/v2/protocols/test_protocol_control_model_identity.py` | 20 通过 |

结论：基准是绿色的，但其中几个现有的门控**强制执行了旧世界**（见下文），因此这种绿色是“旧的门控通过了”，而不是“R3 成立”。

### 2. 不变性 1 — MTPLX 不得进入主读取：**失败（当前树）**

观察（文件:行）：
- `app/config.py:286-294` — `EVIDENCE_NORMALIZER_PROVIDER` 默认为 `"mtplx"`；`EVIDENCE_NORMALIZER_MODEL` 默认为 `MTPLX_MODEL` (`mtplx-flash-next-optimized-speed`)。MTPLX *是* 当前受试者逐页读取（事实规范化）的默认主读取器。
- `app/config.py:149-155` — `REVIEW_BACKEND` 默认为 `"mtplx"`，带有注释“语义审查默认路由到 MTPLX”（用于旧版 v1 的 `app/pipeline/reviewer.py:24`）——这是 R3 要消除的旧降级主读取表述的代码级实例。
- 读取通道提供者白名单 `app/agents/evidence_normalizer.py:88-95` = `{deepseek, deepseek-api, mtplx, mtplx-api, omlx, local-omlx}` — **GLM 和 MiniMax 不是受试者读取通道的选项**，且代码中任何地方都不存在手写第三读取通道（在 `app/services|api|domain|workflow` 中 grep `handwriting|手写` = 0 命中）。
- 现有的回归门控主动断言了旧的默认值：`tests/v2/agents/test_mtplx_semantic_route_regressions.py:123-143` `test_default_semantic_route_is_mtplx_and_ocr_stays_omlx` 断言 `EVIDENCE_NORMALIZER_PROVIDER == "mtplx"` 且 `REVIEW_BACKEND == "mtplx"`。其他旧世界门控：相同文件的第 190、223、237、340 行。
- 运行时选择链：`app/services/fact_normalization_command_service.py:176,233-241` 验证并冻结了 `runtime_config.EVIDENCE_NORMALIZER_PROVIDER`（=mtplx 默认值）。

### 3. 不变性 2 — DeepSeek 不得进入读取通道：**失败（当前树）**

观察：
- `SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS` (`app/agents/evidence_normalizer.py:88-95`) 中的 `"deepseek"`/`"deepseek-api"`。
- 显式 DeepSeek 分支：`app/agents/deepseek_evidence_normalizer_transport.py:104-108`（使用 `DEEPSEEK_API_KEY`/`DEEPSEEK_BASE_URL` 的构造函数）和 `:218-230`（`evidence_normalizer_transport_from_model_config` 中的工厂分支）。此类名本身携带 DeepSeek 标识（`DeepSeekEvidenceNormalizerTransport`，别名 `OpenAICompatibleEvidenceNormalizerTransport`）。
- 范围说明（观察 vs 推断）：协议*解构* DeepSeek 回退（`DECONSTRUCT_FALLBACK_DEEPSEEK_MODEL`, `app/config.py:253-258`; 门控 `tests/tools/test_fresh_run_identity_adversarial.py:414-442`）位于协议侧，而非受试者读取通道中。我将其视为超出 R3 读取通道范围，但特此标记以便 Codex 确认范围。

### 4. 不变性 3 — 仅将 OCR 作为 sidecar：**部分成立（v2 语义成立；存在两个残余表面）**

成立（v2 观察）：
- OCR 是一个确定性的提取后端（`OCR_BACKEND=omlx`, PaddleOCR-VL, `app/config.py:165-171`），生成不可变的 OCR 页面；风险/定位器 sidecar 纯粹在不可变的 OCR 页面之上派生（`app/services/evidence_sidecar_preparation.py` 模块文档："只在不可变 OCR 页之上追加旁路记录，不修改原文，也不产生临床事实或入排判断"）。
- 注入到 normalizer 提示中的视觉观察被明确标记为补充：`app/agents/evidence_normalizer.py:467-485` — OCR 未绑定的观察将其 `risk_reasons` 置空；第 591-596 行将其标记为“视觉观察补充材料（来源绑定引用，非 OCR 原文）”。
- OCR 保持其自身的后端/模型标识，与 MTPLX 分开（由 `test_mtplx_semantic_route_regressions.py:140-143` 门控：`OCR_BACKEND == "omlx"`, `OCR_MODEL_LONG != MTPLX_MODEL`）。

残余（观察）：
- **A.** 主读取唯一的页面内容是 OCR 派生的有效文本：`app/services/fact_normalization_source_adapter.py:462-472` 构建 `pages[].effective_text`；`app/agents/evidence_normalizer.py:519-527` 仅将 `effective_text` 投影到模型输入中。没有任何原始页面图像会到达主读取器。如果 R3 的“OCR仅作侧车”意味着 GLM/MiniMax 主读取器直接读取页面，而 OCR 文本降级为 sidecar 输入，则当前的输入契约尚未满足这一点（见问题）。
- **B.** 旧版 v1 仍然挂载：`app/main.py:20,46` 包含 `pipeline_router` → `app/pipeline/ocr.py:299-303`（OCR 内部的百度手写 OCR 增强回退）和带有 `REVIEW_BACKEND=mtplx` 的 `app/pipeline/reviewer.py`，外加 `app/llm/client.py:166-173` 中的 `deepseek` 审查客户端分支。

## 工件与证据

- 未创建或修改任何工件（只读验证过程）。所有证据均为上述引用的仓库路径；命令输出在 `## 命令与观察` 中。
- 供 Codex/worker_02 参考（证据，非指令）：
  - 可重用的门控机制已存在：`tests/tools/test_phase5_acceptance_fresh_runtime.py` 中的 fresh-runtime `forbidden_model_identities` 合约机制（第 205-208, 234-237 行）— 节点范围的读取通道身份禁止可以扩展它。
  - 无 temperature 合约已有一个门控：`tests/v2/agents/test_evidence_normalizer_transport_config.py:79` `test_factory_omits_temperature_when_frozen_config_uses_vendor_default`。
  - `app/config.py:162` — `MINIMAX_BASE_URL` 默认值 `"https://mimimax.cn/v1"` 看起来像是拼写错误的域名（观察；按照边界未进行互联网验证）。由于 MiniMax 将成为主读取器，worker_02 应确认正确的默认值。

## 命令与观察

```
.venv/bin/python -m pytest tests/v2/agents/test_mtplx_semantic_route_regressions.py \
  tests/v2/agents/test_evidence_normalizer_transport_config.py \
  tests/v2/agents/test_fresh_subject_runtime_routing_adversarial.py \
  tests/v2/llm/test_independent_vlm.py -q
→ 53 passed, 1 skipped (live INDEPENDENT_VLM_LIVE gate), 1.53s

.venv/bin/python -m pytest tests/v2/agents/test_evidence_normalizer_adapter.py \
  tests/v2/evidence/test_ocr_adapter_cache.py tests/v2/evidence/test_selective_vision_review.py \
  tests/tools/test_fresh_run_identity_adversarial.py -q
→ 99 passed, 7.33s

.venv/bin/python -m pytest tests/v2/services/test_evidence_sidecar_preparation.py \
  tests/v2/services/test_fact_normalization_command_service.py \
  tests/v2/api/test_fact_normalization.py tests/tools/test_phase5_acceptance_fresh_runtime.py -q
→ 28 passed, 10.56s

.venv/bin/python -m pytest tests/v2/agents/test_mtplx_whole_candidate_ex06_deterministic_verification.py \
  tests/v2/protocols/test_protocol_control_model_identity.py -q
→ 20 passed, 0.37s
```

R3 落地后的重新验证（相同的命令集是验收重运行）：运行所有四个批次；R3 门控通过要求翻转的断言已更改（默认值不再是 mtplx/deepseek），并且上述每个不变性证据点都处于 R3 状态。

## 阻碍或缺失环境

- 没有阻碍运行。唯一的差距是顺序上的：R3 实现不在树中（worker_02 在我验证时尚未落地），因此目前无法进行端到端验证 R3 的*目标*不变性；上述基准审计是其前半部分。
- 不变性的字面意思无需更改环境；实时网络检查按设计保持跳过（`INDEPENDENT_VLM_LIVE`），这不会影响通道边界验证。

## 重跑请求或下一步

1. Codex：在 worker_02 的更改落地后，重新运行四个 pytest 批次（上面的精确命令）作为 R3 回归门控验收；预期新的失败仅出现在worker_02 有意翻转旧世界的地方（`test_default_semantic_route_is_mtplx_and_ocr_stays_omlx` 及相关），其他所有地方都必须保持绿色。
2. Codex：确认 R3 范围内两个决定：
   - “OCR仅作侧车”是否要求主读取器接收原始页面图像（视觉双重读取），同时将 OCR 派生的 `effective_text` 降级为 sidecar 输入（残余 A），或者 `effective_text` 是否可以保留为主要输入，前提是 OCR 不是模型读取通道。
   - 读取通道边界是否也必须涵盖旧版 v1 面（`app/main.py` 管道路由器：`REVIEW_BACKEND=mtplx` 中的审查器，`app/llm/client.py:166-173` 中的 deepseek 审查分支，`app/pipeline/ocr.py:299-303` 中的百度手写回退），或者 v1 是否明确不在范围内。
3. worker_02 的范围，由本审计提供信息（证据支持的最低表面）：`SUPPORTED_EVIDENCE_NORMALIZER_PROVIDERS`（移除 mtplx/deepseek，添加 GLM+MiniMax 主读取标识 + mtplx 仅手写第三读取并带手写输出限制），`app/config.py:149-155,286-294` 默认值和 `MINIMAX_BASE_URL` 拼写错误，`deepseek_evidence_normalizer_transport.py` 分支，旧世界门控 `test_mtplx_semantic_route_regressions.py`，以及可选地扩展 fresh-runtime `forbidden_model_identities` 以进行节点范围通道禁止。
4. 给 Codex 的精确问题（推理/不确定性标记）：Qwen3.8-Flash-Next 手写第三读取的输出权限（“只能写handwriting”）——现有的候选合同带有 `AssertionBasis`/lane 枚举；worker_02 是应该添加一个专用的手写通道枚举值，还是将写入限制在现有的手写标记字段中？此决定会影响我可以重用于验收的门控断言。
