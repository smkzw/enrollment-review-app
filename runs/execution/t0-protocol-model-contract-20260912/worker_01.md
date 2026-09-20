# Execution Output: t0-protocol-model-contract-20260912 - worker_01

## Boundary And Context Check

- Worked only inside the runner-bound workspace (`enrollment-review-app/.worktrees/phase5-clinical-facts-profile`). Read initial read set (`context/t0-..._execution_context.md`, `plans/codex_execution_t0-....md`), the five allowed modules, `app/config.py` (read-only, owner-modified), `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §6 only, `.trellis/tasks/09-11-e2e-eligibility-review/ENGINEERING_REVIEW_20260912_CODEX.md` R10/R11 only, plus consumers/tests needed to keep contracts intact (`protocol_deconstruction_executor.py`, `protocol_control_execution.py`, `scripts/run_frozen_protocol_comparison.py`, `phase_applicability_transport.py` — all read-only).
- Edits confined to the five allowed modules + allowed test files (all edited test files are existing tests/v2 files specifically covering the five modules, plus one new narrowly named discovery test file). Did not touch config.py, page_review*, targeted_page*, frontend, docs, task files, env, or databases. No commits, no resets; the working tree's unrelated untracked files were left alone.
- Offline only: no model servers, no requests, no browser/web, no package installs.

## Work Performed

**1. `app/agents/protocol_semantic_model_router.py` — no implicit third model.**
`_default_complex_candidates()`/`_default_short_candidates()` now both return only the single configured GLM candidate (`_default_glm_candidate()`, zhipu-coding-plan / glm-5.3-flash / high from `DECONSTRUCT_GLM_*`). Explicit `DECONSTRUCT_ROUTE_COMPLEX`/`_SHORT` specs, pinned mode, startup activation filtering, `candidate_availability_error` skip diagnostics, whole-attempt isolation, and `semantic_repair_limit_for_candidate` are unchanged. Removed now-unused `MTPLX_MODEL`/`MTPLX_REASONING_EFFORT`/`DECONSTRUCT_FALLBACK_DEEPSEEK_*` imports. Module docstring updated.

**2. `app/agents/protocol_semantic_transport.py` — sampling, budgets, retry.**
- `provider_defaults` now defaults `True` for new direct calls; explicit `False` keeps historical overrides. The GLM (zhipu) branch now actually honors the flag (`temperature 0.1` only when `provider_defaults=False`); the trailing fallback branch honors it too. DeepSeek never sent temperature; MTPLX/oMLX already honored the flag.
- Added `PROTOCOL_LENGTH_RETRY_MAX_TOKENS = 131072`. On `finish_reason=length`, the single retry raises the shared reasoning+content budget to `min(budget*2, 131072)` (was: same budget); at most one length retry (existing 2-attempt loop); `local_early_length` now compares against the actually-requested budget; diagnostics record the request budget. Usage comes only from the provider receipt — no fabricated usage.
- Explicit `max_tokens` above the backend's configured platform cap now raises a clear Chinese ValueError naming the cap env (`MTPLX/OMLX/MLX_SERVE_PROTOCOL_BATCH_MAX_TOKENS`) instead of silently `min()`-shrinking; env-inherited default above cap keeps the legacy clamp. Frozen explicit settings within cap pass through untouched. `_completion_kwargs`/`_send_completion` gained an internal `max_tokens` override; transient retries still resend byte-identical payloads.

**3. `app/agents/protocol_control_agent_transport.py` — GLM profile, sampling, retry, caps.**
- Added `zhipu-coding-plan`/`glm` to `_SUPPORTED_BACKENDS` with a Coding Plan connection profile: `PROTOCOL_CONTROL_GLM_BASE_URL` (default `DECONSTRUCT_GLM_BASE_URL`, `.../paas/v4` preserved, no `/v1` appended) and `PROTOCOL_CONTROL_GLM_API_KEY` (default `DECONSTRUCT_GLM_API_KEY`, i.e. the same BigModel credential chain as semantic/normalizer), `trust_env=False` like the approved GLM routes. This was required because the owner's `PROTOCOL_CONTROL_BACKEND=zhipu-coding-plan` default previously failed construction at every production control job (`_resolve_transport` falls through to `from_environment()`).
- GLM wire: reasoning effort resolved/validated onto low/high/max at construction (""/default/auto → configured control default; unsupported e.g. xhigh raises instead of mapping down), `extra_body {"thinking": {"type": "enabled", "clear_thinking": False}}`; MTPLX keeps `generation_mode=ar`.
- `_effective_temperature()` no longer forces 0.0: temperature is omitted entirely unless explicitly configured; explicit `0.0` is sent as a real value. `temperature` property type is now `float | None` (identity/audit code already tolerates `None`).
- Length retry: budget `min(max_tokens*2, PROTOCOL_CONTROL_LENGTH_RETRY_MAX_TOKENS=131072)`, once per logical request. Explicit budget above local platform cap fails closed; env-derived keeps legacy clamp.

**4. `app/agents/protocol_control_discovery_transport.py`.** `_connection_defaults` gained zhipu branches (dedicated `PROTOCOL_CONTROL_DISCOVERY_GLM_*` env overrides falling back to the shared control GLM constants); explicit discovery budget above local cap raises instead of `min()`; inherits sampling/temperature/wire changes from the shared base.

**5. `app/agents/deepseek_evidence_normalizer_transport.py`.** Both streaming (GLM) and non-streaming length retries now cap the doubled budget at `EVIDENCE_NORMALIZER_LENGTH_RETRY_MAX_TOKENS = 131072`, still at most once. Sampling behavior was already correct (temperature omitted unless explicitly configured); GLM effort vocabulary untouched.

**Tests — honest updates + new regression coverage** (285 tests in the affected files, all passing):
- No-third-route: `test_protocol_semantic_model_routing.py` (default complex/short = single GLM high; explicit specs restore ordered chains), `test_protocol_semantic_service_entry_routing.py` (snapshot GLM-only both grades), `test_fresh_subject_runtime_routing_adversarial.py` (rewritten: GLM-only defaults; multi-candidate whole-attempt isolation/fallback/repair-budget coverage retained via explicitly declared candidate chains; live-defaults test now locks the pinned `zhipu-coding-plan:glm-5.3-flash:high` identity), `test_protocol_semantic_route_preflight.py` (missing GLM key + DeepSeek key present now fails closed in degrade mode instead of silently substituting; explicit mtplx spec passes as fully declared; secret-redaction assertions kept).
- Sampling/AR/caps/retry/cache: `test_deconstruction_transport_config.py` (new probe expectations for owner defaults `glm-5.3-flash/zhipu/high/131072/131072`; explicit legacy `provider_defaults=False` keeps 0.0/0.1; GLM honors flag; explicit 60000 kept within cap; explicit > cap raises; env-derived > cap clamps; length retry 65536→131072, 70000→capped 131072, two lengths fail; cache identity separates sampling flag and budget), `test_protocol_control_agent_transport.py` (new GLM defaults probe `zhipu-coding-plan/glm-5.3-flash/high/65536/131072`; temperature omitted unless explicit; explicit 0.0 honored; GLM Coding Plan profile/wire tests; GLM xhigh rejected; missing GLM credential fails before client build; control length retry 16384→32768 and 100000→131072 cap; explicit cap overflow raises), `test_protocol_benchmark_defaults.py` (default = provider sampling; explicit `False` = legacy; GLM honors flag; MLX explicit 131072 honored with raised cap), `test_evidence_normalizer_transport_config.py` (+100000→131072 cap test), new `test_protocol_control_discovery_transport_config.py` (discovery GLM connection, discovery-only schema + no temperature, explicit cap overflow).

## Artifacts And Evidence

- Source (5): `app/agents/protocol_semantic_model_router.py`, `app/agents/protocol_semantic_transport.py`, `app/agents/protocol_control_agent_transport.py`, `app/agents/protocol_control_discovery_transport.py`, `app/agents/deepseek_evidence_normalizer_transport.py` (diff stat: 235 insertions, 64 deletions).
- Tests (12): 11 modified as listed above + new `tests/v2/protocols/test_protocol_control_discovery_transport_config.py`. No other files created or modified; nothing committed.

## Commands And Observations

- `.venv/bin/python -m pytest` over all 18 affected test files (protocols/agents/scripts/services): **285 passed, 0 failed** (~22s).
- Broader sweep `tests/v2/agents tests/v2/protocols`: 1658 passed; the only failures are the two pre-existing phase-applicability tests (owner's config change, see below). Sweep `tests/v2/services`: 587 passed; one failure in the owner's in-flight page-review harness domain.
- Observation: transient-retry tests still pass byte-identical-payload assertions because the length budget override is constant within one attempt's retry set.

## Blockers Or Missing Environment

None blocking execution. Known pre-existing failures outside my allowed paths (evidence, not my changes): `tests/v2/protocols/test_phase_applicability_live_execution.py::test_real_transport_uses_phase_schema_and_restorable_same_session_history` and `::test_mtplx_phase_transport_uses_quality_output_budget` fail because the owner's cap changes (8192/16384→131072) hit `phase_applicability_transport.py` (unmodified module, not in my allowed list) and its old clamp assumptions; `tests/v2/services/test_isolated_normalization_entry.py::test_frozen_readers_match_explicit_configuration[12000-False]` fails against the owner's concurrently edited `page_review_harness.py` validation (65536 floor vs a 12000 test input).

## Rerun Requests Or Next Step

No rerun needed. Items for Codex/owner decision (I did not act outside scope):
1. **`app/agents/phase_applicability_transport.py` (neighbor needing owner action):** it inherits `DECONSTRUCT_BACKEND` (now `zhipu-coding-plan`) but has no zhipu connection profile, and its tests assume the old silent min() clamp. Owner should add the GLM profile, adopt the no-silent-shrink budget rule, and update its two failing tests.
2. **Live verification needed (offline task):** whether BigModel Coding Plan serves `/v1/models`. The control/discovery identity gate auto-enables for zhipu and fails closed with `probe_failed` if the endpoint is unsupported; if that surfaces in the smoke runner, the owner should either confirm the endpoint or explicitly pass `model_identity_check=False` at the control execution call sites.
3. `.env.example` comments (lines 71–72) still describe the old three-model default chain; harmless to tests but should be reworded by the owner.
4. Not verified live (by assignment): real GLM high ≥65536 budget acceptance and actual length-retry behavior on the provider. I do not claim T0 completion or any clinical/regulatory acceptance.
