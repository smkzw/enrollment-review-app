I'll execute the assigned inventory work: reading the execution context and plan, then mapping model entry points for the shared vision adapter proposal.Context confirms inventory-only scope for `worker_01`. Next I’ll locate model entry points across protocol, evidence, facts, and subject-review harnesses.Worker helper failed; continuing with direct codebase search for LLM/VLM clients and harness model hooks.Found `app/agents` and `app/llm`. I'll inventory those transports and any subject-review harness hooks next.`.env.example` already declares `INDEPENDENT_VLM_*`, but `config.py` may not wire it yet. I'll verify harness and fact-normalization entry points next.Inventory is complete. Delivering the worker report with the shared vision-adapter proposal and migration checklist.# Execution Output: phase5-independent-glm53-vlm-20260831 - worker_01

## Boundary And Context Check

- Role: `worker_01` inventory/proposal only; no production writes; no package installs; no clinical/regulatory acceptance.
- Initial reads: `context/phase5-independent-glm53-vlm-20260831_execution_context.md`, `plans/codex_execution_phase5-independent-glm53-vlm-20260831.md`.
- Context Source Of Truth is still `TODO`; additional reads were limited to in-workspace model entry points needed for the inventory.
- Existing report stub `runs/execution/phase5-independent-glm53-vlm-20260831/worker_01.md` is `PENDING`; this response is the complete report for runner persistence (no direct write to that path).
- Scope boundary respected: propose shared vision adapter + migration checklist; do **not** implement BigModel transport (worker_02) or adaptive batching (worker_03).

## Work Performed

### Evidence: current model entry map

| Domain | Entry | Path / symbols | Modality | Provider/model today | Notes |
|---|---|---|---|---|---|
| 方案解构 | Sync transport | `app/agents/deepseek_protocol_transport.py` (`SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS`, `_completion_kwargs`) | text-only (`messages: list[dict[str,str]]`) | `DECONSTRUCT_*` → default `mtplx` / `mtplx-qwen38-27b-optimized-quality`; also `omlx`, `deepseek` | DeepSeek-v4 maps effort → `reasoning_effort` + `extra_body.thinking.enabled`; MTPLX uses `generation_mode=ar` |
| 方案解构 | Agent runner | `app/agents/protocol_deconstructor.py` (`ProtocolDeconstructorRunner`, `ProtocolAgentTransport`) | text prompts/JSON wire | via injected transport | No image attach API |
| 方案解构 | Legacy async helper | `app/llm/client.py::deconstruct_chat` | text-only | `DECONSTRUCT_*` | Parallel stack to agent transport |
| 方案控制 | Deep transport | `app/agents/protocol_control_agent_transport.py` (`OpenAICompatibleProtocolControlAgentTransport`) | text-only | `PROTOCOL_CONTROL_*`; backends `{mtplx,mtplx-api,omlx,local-omlx,deepseek,deepseek-api}` | Model-identity probe before semantic call; no BigModel; no thinking map like DeepSeek-v4 |
| 方案控制 | Discovery transport | `app/agents/protocol_control_discovery_transport.py` | text-only | `PROTOCOL_CONTROL_DISCOVERY_*` falling back to control defaults | Same OpenAI-compatible pattern |
| 方案控制 | Agent / execution | `app/agents/protocol_control_deconstructor.py`, `app/services/protocol_control_execution.py` | text | env transport factories | Live path uses transports; not vision |
| 方案控制 replay harness | Model-free pack builder | `app/protocols/protocol_replay_harness.py`, `scripts/run_protocol_replay_harness.py` | **no model** | N/A (`REPLAY_PACK_MODE=model_free`) | Builds deterministic prompts/packs only; explicitly does not instantiate transports |
| 方案控制 live smoke | Production harness | `scripts/run_protocol_control_smoke.py` | text live model | env discovery+deep transports | Identity verify then two-stage control chain |
| 期别适用 | Transport | `app/agents/phase_applicability_transport.py` | text-only | defaults inherit `DECONSTRUCT_*` via `PHASE_APPLICABILITY_*` | Related semantic entry; not VLM |
| 证据 OCR / page vision | Async OCR VLM | `app/llm/client.py` (`ocr_image`, `call_vision_ocr`, `_build_vision_message`), `app/pipeline/ocr.py` | vision (page images → markdown) | `OCR_BACKEND=omlx|minimax`; models `OCR_MODEL_LONG/SHORT` (PaddleOCR-VL) or MiniMax | Existing vision path; **not** Independent VLM / BigModel |
| 证据 OCR gate | Local GLM-OCR probe path | `app/services/omlx_gate.py` (+ `tests/v2/evidence/probe_omlx_glm.py`) | vision | local `GLM-OCR-bf16` via oMLX | Slice capability / OCR gate; separate from智谱开放平台 |
| 证据规范化 | Transport | `app/agents/deepseek_evidence_normalizer_transport.py` | text-only | `EVIDENCE_NORMALIZER_*`; providers deepseek/mtplx/omlx | No thinking/image; MTPLX AR only for json_schema |
| 事实规范化 | Command/executor/job | `app/services/fact_normalization_command_service.py`, `fact_normalization_executor.py`, `fact_normalization_job_service.py` | text via Evidence Normalizer | frozen `ModelConfigContract` | Must keep deterministic clinical boundary; provider allowlist excludes `bigmodel` today |
| 受试者审核 harness | Legacy review pipeline | `app/pipeline/reviewer.py::run_review` → `app/llm/client.py::review_chat`; routed by `app/router/pipeline.py` | text-only (`evidence_bundle` markdown) | `REVIEW_*` → default MTPLX | Consumes OCR text, not raw page images |
| 受试者审核 | V2 contract node | `app/domain/contracts/agents.py` (`AgentNode.ELIGIBILITY_ASSESSOR`) | contract only | N/A in this inventory path | No dedicated BigModel vision adapter found |

### Evidence: config skew

- `.env.example` already declares Independent VLM:
  - `INDEPENDENT_VLM_PROVIDER=bigmodel`
  - `INDEPENDENT_VLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4`
  - `INDEPENDENT_VLM_MODEL=glm-5.3-flash`
  - `INDEPENDENT_VLM_REASONING_EFFORT=high`
- `app/config.py` does **not** define/load any `INDEPENDENT_VLM_*` symbols (`INDEPENDENT_VLM in config.py == False`).
- No production caller currently binds to智谱 BigModel GLM-5.3-Flash vision.

### Inference: architectural split already present

1. **Semantic agents** (deconstruct / control / normalizer / review) are OpenAI-compatible **text** transports with per-task env isolation.
2. **OCR vision** is a separate local/minimax path that emits markdown for later semantic use.
3. **Protocol replay harness** is intentionally model-free; live control smoke is a separate explicit action.
4. Therefore the Independent VLM should be a **third, shared capability plane** for raw DOCX/PDF page verification + source-locator fidelity — not a silent replacement of MTPLX semantic backends, and not a merge into OCR Paddle/MiniMax.

### Recommendation: minimal shared vision adapter

Proposed minimal module (for worker_02 implementation; not created in this pass):

1. **Config surface** (extend `app/config.py` to match `.env.example`):
   - `INDEPENDENT_VLM_PROVIDER|BASE_URL|API_KEY|MODEL|REASONING_EFFORT`
   - Optional timeout/max_tokens later; keep fail-closed if key empty when vision route is selected.

2. **Shared adapter API** (prefer new `app/llm/independent_vlm.py`, thin re-exports from `app/llm/client.py` if needed):
   - `get_independent_vlm_client()` → OpenAI-compatible client to BigModel paas v4
   - `build_page_vision_messages(prompt, pages: Sequence[PageVisionInput])` where page input carries:
     - image bytes/data-URL
     - stable `source_ref` / page ordinal / media type
     - optional bbox/locator hints already known from structure extraction
   - `independent_vlm_chat(...)` returning text + raw diagnostics (finish_reason, usage)
   - `map_reasoning_effort(effort)` with explicit BigModel mapping:
     - `high` → thinking enabled (provider-native body; exact key owned by worker_02 tests)
     - unsupported effort → fail closed or documented no-op; do not invent project-specific rules
   - `classify_remote_failure(exc)` → distinguish **balance insufficient / auth / quota** and **fail closed** (no silent OCR/semantic fallback)

3. **Compatibility seam** (non-breaking):
   - Keep semantic transports’ `messages: list[dict[str,str]]` unchanged initially.
   - Call Independent VLM only from explicit vision-verification call sites (DOCX/PDF page audit, locator fidelity checks), then feed **verified text/locator facts** into existing deterministic gates.
   - Do **not** add `bigmodel` into Evidence Normalizer / Protocol Control provider allowlists unless Codex later authorizes semantic reroute.
   - Do **not** change `protocol_replay_harness` model-free default; live/vision remains opt-in.

### Compatibility migration checklist

1. Wire `INDEPENDENT_VLM_*` into `app/config.py` + health/check helper (mirror `check_mtplx` style) without changing defaults of `REVIEW_/DECONSTRUCT_/PROTOCOL_CONTROL_/EVIDENCE_NORMALIZER_/OCR_*`.
2. Implement BigModel client + `high→thinking enabled` mapping + balance fail-closed tests (**worker_02**).
3. Preserve source-locator fidelity contract: page image request must round-trip `source_ref`/page identity in prompt or structured side-car; reject responses that invent locators.
4. Leave OCR (`call_vision_ocr` / oMLX GLM-OCR / MiniMax) as extraction path; Independent VLM is verification/reading of original pages, not a drop-in OCR backend rename.
5. Subject review harness (`run_review`) remains text-on-OCR-bundle unless Codex authorizes an optional “page-vision spot check” pre-step; no deterministic clinical verdict change.
6. Fact normalization continues to freeze `ModelConfigContract` on text normalizer providers; do not register GLM-5.3-Flash as Evidence Normalizer provider in this packet.
7. Protocol control serial replay performance is **out of scope here**; inventory confirms replay harness itself is model-free, while live smoke/control transports are the model cost centers — adaptive batching belongs to **worker_03**.
8. Regression guard: extend/add focused unit tests that Independent VLM config is isolated from MTPLX semantic route tests (`tests/v2/agents/test_mtplx_semantic_route_regressions.py` pattern).
9. Docs/env: keep `.env.example` comment that semantic routes stay task-isolated; Independent VLM is for direct raw-page reading only.
10. No project-specific (D001/etc.) rules inside the shared adapter.

## Artifacts And Evidence

- No new code artifacts written (inventory/proposal only; implementation assigned to worker_02/03).
- Key evidence files inspected:
  - `.env.example` (Independent VLM declared)
  - `app/config.py` (Independent VLM not wired)
  - `app/llm/client.py` (OCR vision + review/deconstruct clients)
  - `app/agents/deepseek_protocol_transport.py`
  - `app/agents/protocol_control_agent_transport.py`
  - `app/agents/protocol_control_discovery_transport.py`
  - `app/agents/deepseek_evidence_normalizer_transport.py`
  - `app/agents/phase_applicability_transport.py`
  - `app/protocols/protocol_replay_harness.py` (model-free)
  - `app/pipeline/reviewer.py`, `app/pipeline/ocr.py`
  - `app/services/fact_normalization_*.py`, `app/services/omlx_gate.py`
  - `scripts/run_protocol_replay_harness.py`, `scripts/run_protocol_control_smoke.py`
- Uncertainty: exact BigModel request field for “thinking enabled” under paas v4 was not verified against live API docs in this pass (deferred to worker_02 with fail-closed tests).

## Commands And Observations

| Tool/command | Target | Observation |
|---|---|---|
| Read | execution context + plan | Work item 1 = inventory + shared vision adapter proposal |
| Glob / rg | `app/agents`, `app/llm`, harness scripts | Confirmed text transports + separate OCR vision path |
| Shell `rg` + `.venv/bin/python` | `INDEPENDENT_VLM` wiring | Present in `.env.example`; absent in `app/config.py` |
| Read | `protocol_replay_harness.py` header/API | Default path never instantiates model transport |
| Read | transport `_completion_kwargs` | Only DeepSeek-v4 currently maps to `thinking.enabled`; control/normalizer do not |
| `mcp_pi-agent_pi-worker` | inventory prompt | Failed: `unknown flags: --no-prompt-templates, --no-context-files`; continued with direct tools |

## Blockers Or Missing Environment

- Context “Source Of Truth” still TODO; inventory used in-repo code as provisional authority.
- No live BigModel credential/probe performed (correct for worker_01; worker_02 owns implementation/tests and balance fail-closed behavior).
- Host `python` missing on PATH; `.venv/bin/python` works.

## Rerun Requests Or Next Step

1. Codex: accept or adjust the recommended seam — Independent VLM as **shared page-vision verification plane**, not a semantic-provider swap.
2. Hand off to **worker_02**: implement config wiring + BigModel GLM-5.3-Flash transport + `high→thinking enabled` + raw-page/source-locator fidelity + balance fail-closed tests.
3. Hand off to **worker_03**: adaptive token/output-budget batching / limited concurrency for live control replay metrics (do not alter model-free harness default).
4. Precise Codex decision needed if any: should subject-review `run_review` gain an optional page-vision spot-check hook in this packet, or remain OCR-text-only until a later slice?
