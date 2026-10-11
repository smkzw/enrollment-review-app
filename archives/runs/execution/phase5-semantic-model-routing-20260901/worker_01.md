I'll execute the assigned design-review work: first reading the provided execution context and plan, then inspecting the semantic transmission/config/executor/cache contracts.Context confirms this is a design-only review for worker_01. Next I’ll locate the semantic transport, config, executor, and cache contracts in the worktree.I'll dig into the transport, config, executor cache key, and existing route tests next.I have enough contract evidence for a minimal compatible design. Emitting the worker report now.# Execution Output: phase5-semantic-model-routing-20260901 - worker_01

## Boundary And Context Check

- Role: `worker_01` design-only review; no implementation (worker_02) and no tests (worker_03).
- Working directory bound to authorized workspace; no production writes performed.
- Initial reads: `context/phase5-semantic-model-routing-20260901_execution_context.md`, `plans/codex_execution_phase5-semantic-model-routing-20260901.md`.
- Context `Source Of Truth` is still TODO; no design-file write path authorized → design is delivered in this report only.
- Additional reads were required to ground the design in current contracts: transport, config, executor cache, deconstructor runner, Independent VLM (GLM exists but is vision-isolated), and MTPLX no-silent-fallback regressions.

## Work Performed

### Evidence: current contracts

| Area | Current contract | Gap vs objective |
|---|---|---|
| Config | Single pin: `DECONSTRUCT_BACKEND`/`DECONSTRUCT_MODEL`/`DECONSTRUCT_REASONING_EFFORT` (default `mtplx` / `mtplx-qwen38-27b-optimized-quality` / `medium`) | No task grade; no ordered fallback chain; no GLM semantic profile |
| Transport | `DeepSeekProtocolAgentTransport` / alias `OpenAICompatibleProtocolAgentTransport`; backends `{deepseek,omlx,mtplx,mtplx-api}` | No GLM/zhipu backend; in-transport retries are same-model only |
| Executor | `_resolve_transport()` builds one transport from `DECONSTRUCT_BACKEND`; job-scoped batch cache | No route selector; no attempt audit for provider switches |
| Cache | `protocol-semantic-batch/v1`; key includes `semantic_cache_identity(backend,model,reasoning,request)` + prompt + batch_id + rule_codes; root `protocol-semantic-batches/{job_id}` | Already model-aware for compact local routes; not a multi-provider attempt ledger |
| Session | `start`/`continue_session` immutable history; runner aborts if `session_id` changes | Mid-session provider switch is unsafe by construction |
| GLM today | `INDEPENDENT_VLM_*` / `app/llm/independent_vlm.py` for page vision only; comments forbid semantic inheritance | Cannot silently reuse as deconstruct default without a separate semantic profile |
| Policy tests | `test_mtplx_semantic_route_regressions.py` asserts no silent remote/OCR fallback | Future fallbacks must be explicit and auditable, not silent |

### Recommended minimal compatible design

**1. Task grades (project-agnostic)**

- `complex_protocol_semantic`: default for protocol semantic deconstruction when the planned work is not “short”.
- `short_prompt_semantic`: short, new-session prompts only.

Suggested default classifier (no protocol/project hardcoding):

- Compute at **session-start / run-entry only** (never mid-`continue_session`).
- `short` iff **all** hold:
  - planned parent-rule count for this call ≤ 1, **and**
  - `estimate_text_tokens(prompt) ≤ SHORT_PROMPT_MAX_INPUT_TOKENS` (propose default `4096`, overridable), **and**
  - call kind is not multi-batch complex collection (`batch_total > 1` ⇒ complex).
- Else `complex`.
- Repairs that `continue_session` **inherit** the session’s locked route; they do not re-grade.

**2. Explicit route profiles (config, not code literals of study IDs)**

Keep legacy single-pin override: if `DECONSTRUCT_BACKEND` + `DECONSTRUCT_MODEL` are explicitly set as a force-pin (or a new `DECONSTRUCT_ROUTE_MODE=pinned`), use that one profile and do not auto-chain.

Otherwise:

| Grade | Ordered candidates | Notes |
|---|---|---|
| `complex_protocol_semantic` | 1) GLM-5.3-Flash (`zhipu-coding-plan` / BigModel Coding Plan OpenAI-compatible) → 2) MTPLX (`mtplx` + `MTPLX_MODEL`) → 3) DeepSeek V4 Flash high (`deepseek` + `deepseek-v4-flash`, `reasoning_effort=high`) | “全尝试回退”: exhaust a candidate’s local retry budget before advancing |
| `short_prompt_semantic` | 1) MTPLX → optional same remaining chain without putting GLM first | Prefer cheap/local for short prompts |

Introduce **deconstruct-owned** env keys (do not inherit Independent VLM by reference alone), e.g.:

- `DECONSTRUCT_GLM_PROVIDER`, `DECONSTRUCT_GLM_BASE_URL`, `DECONSTRUCT_GLM_API_KEY`, `DECONSTRUCT_GLM_MODEL` (default `glm-5.3-flash`), `DECONSTRUCT_GLM_REASONING_EFFORT` (map to GLM vocabulary `low|high|max`).
- `DECONSTRUCT_ROUTE_COMPLEX`, `DECONSTRUCT_ROUTE_SHORT` as optional JSON/CSV of `backend:model:effort` for auditability/override.
- Extend `SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS` with an explicit GLM backend id (recommend `zhipu-coding-plan` or `glm`; Codex to pick one name).

Wire-contract rule:

- MTPLX/oMLX remain `uses_compact_wire_contract=True` (grammar + batch cache).
- GLM and DeepSeek remain non-compact (`json_object`), like current DeepSeek path — **no local grammar assumption**.

**3. Explicit fallback executor semantics**

Add a thin router above transport construction (executor/factory), not inside chat history:

1. Grade task → select ordered candidate list.
2. For each candidate `i`:
   - Build a **fresh** transport instance with that backend/model/effort.
   - Run collection+repairs as today on **one** transport/`same_session_id`.
   - Record audit: `{route_attempt, grade, backend, model, reasoning_effort, outcome, error_class, session_id, cache_hits}`.
   - Advance only on explicit failure classes (transport/config unavailable, empty/truncated after local retries, schema invalid after budget, session anomaly). Do **not** advance on “soft quality dislike.”
3. If candidate `i` fails after any **accepted** batch/candidate materialization: **discard that attempt’s merged candidate**; next candidate starts a clean generation (no cross-model merge).
4. Preserve old import alias `DeepSeekProtocolAgentTransport` / `OpenAICompatibleProtocolAgentTransport`.

**4. Boundaries that must not mix different model batches**

Hard non-mix rules for worker_02/03:

1. **No cross-backend `continue_session`.** Session history is provider-specific; runner already fails on `session_id` change — extend to fail closed if transport identity changes.
2. **No merged candidate across providers.** `candidate_id` / repaired graph from model A must not accept batch/repair text from model B.
3. **No cache reuse across models.** Keep `semantic_cache_identity` in the key; on provider switch, previous cache entries remain readable only under matching identity (already true). Do not strip identity from the key.
4. **Fallback boundary = whole route attempt**, not mid-batch. If batch `1/N` validated under GLM and GLM later fails on `2/N`, either restart entire attempt on next provider, or only continue GLM; **never** fill remaining batches with MTPLX into the same merged candidate.
5. **Job isolation stays job_id-scoped.** Cache root and attempt audit remain under the durable deconstruction job; do not share in-memory histories across jobs.
6. **Task isolation from other agents.** Do not route OCR, Independent VLM vision, protocol-control, or evidence-normalizer through this deconstruct chain by default.
7. **No project-specific hardcoding.** Classifier uses token/rule-count/call-kind only; no protocol codes, study names, or package IDs in routing.
8. **No silent fallback.** Missing GLM key ⇒ explicit skip/fail record then next candidate (or fail closed if policy requires), never pretend MTPLX was primary.

**5. Audit minimum**

Per job generation, persist (checkpoint or sidecar under existing job boundary):

- selected grade + classifier inputs (rule_count, token_estimate, batch_total)
- ordered candidates
- each attempt’s backend/model/effort/outcome/error
- final selected identity
- cache hit/miss per batch keyed by model identity

This satisfies “回退显式、作业隔离、可审计.”

### Inference vs recommendation

- **Evidence:** single-pin MTPLX default; cache already hashes transport identity; session continuity forbids mid-chat provider swap; GLM exists only as isolated vision transport.
- **Inference:** objective’s “短提示小任务” maps cleanly to new-session short prompts / single-rule small packs, not mid-repair turns.
- **Recommendation:** implement router at transport-factory / run-entry; treat GLM like DeepSeek for wire compactness; restart whole attempt on provider advance after any accepted batch.
- **Uncertainty / Codex decisions needed:**
  1. Exact backend id string for GLM semantic (`zhipu-coding-plan` vs `glm` vs `bigmodel`).
  2. Numeric `SHORT_PROMPT_MAX_INPUT_TOKENS` and whether short grade may include `rule_count==0` schema-only probes.
  3. If GLM API key missing: skip-to-MTPLX with audit, or fail closed before MTPLX.

## Artifacts And Evidence

- Design artifact: this report only (no extra files written; context did not authorize a design path).
- Source files reviewed:
  - `app/agents/deepseek_protocol_transport.py` (backends, `semantic_cache_identity`, session APIs)
  - `app/services/protocol_deconstruction_executor.py` (`_ProtocolSemanticBatchFileCache`, `_resolve_transport`)
  - `app/agents/protocol_deconstructor.py` (`_semantic_batch_cache_key`, batch collection, runner session lock)
  - `app/config.py`, `.env.example` (DECONSTRUCT_* vs INDEPENDENT_VLM_*)
  - `app/llm/independent_vlm.py`, `app/llm/client.py`
  - `app/domain/contracts/agents.py` (`ModelConfigContract`)
  - `tests/v2/agents/test_mtplx_semantic_route_regressions.py`, `tests/v2/protocols/test_deconstruction_transport_config.py`
- Peer worker outputs not reviewed (per instructions).

## Commands And Observations

- `pwd` / path checks: workspace = phase5 worktree.
- `rg` scans over transport/executor/config/tests: confirmed no existing task-grade router; cache contract `protocol-semantic-batch/v1`; GLM not in `SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS`.
- `mcp_pi-agent_pi-worker` failed (`unknown flags: --no-prompt-templates`); continued with direct file reads/`rg`.
- No tests executed (not authorized for worker_01).

## Blockers Or Missing Environment

- Context `Source Of Truth` still TODO; design grounded on in-tree contracts instead.
- No Codex-authorized writable design path under `artifacts/` — none created.
- Three naming/threshold decisions above should be fixed by Codex before/while worker_02 implements.

## Rerun Requests Or Next Step

- Codex: accept or amend this design (especially GLM backend id, short threshold, missing-key policy).
- worker_02: implement generic config + GLM OpenAI-compatible semantic transport + grade router + explicit attempt fallback/audit; keep legacy imports; do not modify raw clinical source blobs.
- worker_03: deterministic tests for default complex route, short→MTPLX, explicit fallback, post-switch candidate isolation, cache non-reuse across models, Chinese diagnostics, and absence of project-specific hardcoding.
- No same-session rerun needed for worker_01 unless Codex rejects the classifier or non-mix boundaries.
