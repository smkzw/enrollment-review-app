I'll execute the assigned independent review for `phase5-env-preflight-20260901` / `worker_03`, starting with the required context files.Next I'll locate the env-contract, GLM credential mapping, and preflight/fault-injection tests that this review must verify.Search terms returned nothing and peer reports are still pending, so I'm widening the scan for GLM/env/preflight-related code under different names.`.env.example` already mentions GLM routing; I'll inspect that and the app config/startup paths next.I'll inspect the semantic router, env loading, and related tests for credential mapping and failure behavior.I've confirmed config still hardcodes `.env`; next I'll check secret-handling in route availability errors and the related fault-injection tests.I'll verify startup behavior, secret redaction in transport errors, and whether a worktree `.env` is actually present.I'll use the worktree `.venv` to prove the empty GLM key after import and run the safe no-network unit checks.I have enough evidence for the independent review verdict; compiling the required report now.# Execution Output: phase5-env-preflight-20260901 - worker_03

## Boundary And Context Check

- Worked only inside the runner CWD / authorized worktree: `.../.worktrees/phase5-clinical-facts-profile`.
- Read assigned context/plan: `context/phase5-env-preflight-20260901_execution_context.md`, `plans/codex_execution_phase5-env-preflight-20260901.md`.
- Additional evidence reads (needed because Source Of Truth is still TODO and worker_02 implementation is not landed): `app/config.py`, `app/agents/protocol_semantic_model_router.py`, `app/agents/deepseek_protocol_transport.py`, `app/services/protocol_deconstruction_executor.py`, `app/api/v2/app.py`, `app/main.py`, `scripts/run_enrollment_review_service.sh`, `scripts/start_enrollment_review.command`, `.env.example`, selected tests under `tests/v2/agents/` and `tests/v2/llm/`, plus authority note in `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` Phase 5 收口项.
- No production writes; no package installs; no secret values printed. Parent `.env` was inspected for **key presence only**.
- Role scope: independent review of implementation/tests for env contract / GLM credential / declared==executable / non-leak / no accidental test network. Not implementing worker_02 fixes. Not performing final acceptance.

## Work Performed

1. Verified whether `ENROLLMENT_ENV_FILE` / startup semantic-route preflight / endpoint fault-injection tests exist in the current tree.
2. Traced worktree env loading vs launcher/service allowlist vs `DECONSTRUCT_GLM_API_KEY` fallback mapping.
3. Compared **declared** graded complex chain vs **executable** candidates after availability checks.
4. Probed failure-path secret handling in `DeepSeekProtocolAgentTransport` via injected fake exception (no network).
5. Ran focused no-network unit tests for Chinese missing-key skip + declared default chain.

## Artifacts And Evidence

### Evidence: worktree process does **not** obtain `DECONSTRUCT_GLM_API_KEY`

| Check | Observation |
|---|---|
| Worktree `.env` | **Missing** (`False`) |
| `ENROLLMENT_ENV_FILE` in `app/config.py` | **Absent** |
| Config loader | Hardcoded `Path(__file__).resolve().parent.parent / ".env"` + `os.environ.setdefault(...)` only |
| Process env at probe | `DECONSTRUCT_GLM_API_KEY` unset; `INDEPENDENT_VLM_API_KEY` unset |
| After `.venv` import of `app.config` | `DECONSTRUCT_GLM_API_KEY` nonempty=`False` (len=0) |
| Parent repo `.env` (names only) | `INDEPENDENT_VLM_API_KEY` present+nonempty; `DECONSTRUCT_GLM_API_KEY` **absent**; `ENROLLMENT_ENV_FILE` absent |
| Launcher `model-services.env` allowlist | Exports GLM provider/model/effort, **not** `DECONSTRUCT_GLM_API_KEY` / `INDEPENDENT_VLM_API_KEY` |
| `run_enrollment_review_service.sh` allowlist | Same omission for API keys |

**Inference:** Mapping `DECONSTRUCT_GLM_API_KEY = env or INDEPENDENT_VLM_API_KEY` exists in config, but a worktree process that does not load parent `.env` (and has no local `.env` / no `ENROLLMENT_ENV_FILE`) still ends with empty GLM credential. This matches the Phase 5 收口 blocker description (GLM skipped because V2 subprocess cannot read the key).

### Evidence: declared route ≠ executable route (no startup gate)

- Declared complex chain from `service_entry_semantic_route_snapshot()`:
  - `zhipu-coding-plan:glm-5.3-flash:high`
  - `mtplx:mtplx-qwen38-27b-optimized-quality:medium`
  - `deepseek:deepseek-v4-flash:high`
- After `candidate_availability_error` in the same worktree import: GLM **skipped** (Chinese reason mentions missing `DECONSTRUCT_GLM_API_KEY`); executable survivors were MTPLX + DeepSeek.
- `candidate_availability_error` checks **credential presence only** for GLM/DeepSeek; **no endpoint connectivity check**.
- V2 lifespan (`app/api/v2/app.py`) and legacy `app/main.py` startup perform recovery/project init only; **no semantic-route credential/endpoint preflight**, no refuse-start / explicit-degrade-before-background-job gate, no startup route audit for undeclared-executable mismatch.
- Launcher UI still **declares** graded GLM→MTPLX→DeepSeek even when keys were never injected.

**Verdict on assigned focus “声明路由等于可执行路由”:** **FAIL** on current tree.

### Evidence: failure path can leak secrets; required fault-injection coverage missing

- Missing-key path is relatively safe: Chinese skip text names the **variable**, not the secret. Existing unit test `test_missing_glm_key_returns_explicit_chinese_skip_reason` covers this and passed.
- Transport failure path is **not** sanitized: `DeepSeekProtocolAgentTransport.start/continue_session` does `ProtocolAgentCallError(..., str(exc))`.
- Local probe (fake client, no network): exception containing `Authorization: Bearer sk-test-secret-leak-probe` was propagated verbatim → `leak_probe_in_error True`.
- Independent VLM tests do assert `api_key not in str(exc)`, but **no equivalent fault-injection test** exists for protocol-semantic / GLM transport, `ENROLLMENT_ENV_FILE`, or endpoint-down startup refusal.

**Verdict on “故障不泄密”:** partial for missing-key skip; **FAIL** for generic transport exceptions. Required preflight fault-injection suite is **not present** (worker_02 still PENDING).

### Evidence: tests do not mis-touch network (current routing suite)

- `tests/v2/agents/test_protocol_semantic_model_routing.py` / `test_protocol_semantic_service_entry_routing.py` use monkeypatch + fake runners/transports; module docstring states no live provider calls.
- Focused run: 4 passed, no live calls.
- Residual risk: ambient `HTTP_PROXY`/`HTTPS_PROXY` are set in this shell; GLM/DeepSeek transport uses `httpx.Client(trust_env=False)` (good), but absent endpoint preflight tests must stay mocked/`trust_env=False` when worker_02 adds them.

### Implementation status for this packet

- `ENROLLMENT_ENV_FILE` contract: **not implemented**
- Startup semantic-route credential+endpoint preflight: **not implemented**
- Fault-injection tests for missing key / bad endpoint / non-leak: **not implemented** (beyond existing missing-key skip unit test)
- worker_02 report still `PENDING`; this review is therefore a **baseline independent rejection**, not a post-fix acceptance.

## Commands And Observations

1. `rg` / file reads across `app/`, `scripts/`, `tests/`, plans/context — located loader, router, transport, launcher gaps; confirmed `ENROLLMENT_ENV_FILE` only in plans/prompts, not app code.
2. Key-presence probe of parent `.env` — `INDEPENDENT_VLM_API_KEY` present; `DECONSTRUCT_GLM_API_KEY` / `ENROLLMENT_ENV_FILE` absent.
3. `.venv/bin/python` import probe — worktree config yields empty `DECONSTRUCT_GLM_API_KEY`; declared complex chain includes GLM; availability skips GLM.
4. Fake-client leak probe — `str(exc)` preserves bearer token material.
5. `pytest` focused subset (4 tests) — **4 passed** in 0.48s; no network required.

## Blockers Or Missing Environment

1. **Blocking functional gap:** worktree lacks `.env` and any `ENROLLMENT_ENV_FILE` contract; process does not receive GLM credential (nor Independent VLM fallback from parent `.env`).
2. **Blocking product gap:** declared graded GLM route is advertised/selected, but becomes non-executable at runtime without startup refuse/explicit degrade+audit.
3. **Blocking test gap:** no fault-injection coverage for endpoint failure or secret non-leak on semantic transport; worker_02 implementation not available to re-verify.
4. Context Source Of Truth still TODO; review used current tree + authority plan text.
5. Did not read peer worker conclusions for judgment (worker_01 file exists/completed; worker_02 pending). Independent findings above stand on primary sources.

## Rerun Requests Or Next Step

Ask Codex / worker_02 to land the minimal fix, then re-dispatch this same worker_03 review against the new diff with these acceptance probes:

1. **Env contract:** with only `ENROLLMENT_ENV_FILE=<worktree or explicit file>` (or explicit exported keys), a fresh Python process in the worktree must show `DECONSTRUCT_GLM_API_KEY` nonempty **without** reading parent CWD `.env` implicitly; print only booleans/lengths.
2. **Declared == executable gate:** before background semantic jobs, every declared candidate is reported 已配置/未配置 + endpoint check result (no secrets); GLM missing/unreachable must refuse start **or** write explicit degrade audit and change the declared executable chain accordingly.
3. **Fault injection (no live network):**  
   - missing key → Chinese failure, startup/job blocked or explicit degrade; secret not in logs/audit/API envelope;  
   - endpoint fault via mocked transport/httpx → same non-leak assertions (`api_key not in` message/audit);  
   - tests must not open real BigModel/DeepSeek/MTPLX sockets (`trust_env=False` / fully mocked).
4. After those land, re-run this worker_03 checklist; current baseline verdict is **reject / not yet fixed**.
