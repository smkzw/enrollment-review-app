I'll do a read-only review of the Phase 5 env preflight scope and start from the assigned context/plan files.Context confirms work item 1 is read-only review. Next I’ll locate config loading, startup, semantic routing, and related tests.Broader search missed the app symbols; narrowing to config, GLM/deconstruct routing, and startup scripts.Found the routing and startup entry points; reading those next for the failure boundary.Checkpoint confirms the GLM key miss in the V2 process; next I’ll inspect the executor preflight and env loading path.I have enough evidence for the read-only root-cause and fix-boundary report; no code changes were made.

# Execution Output: phase5-env-preflight-20260901 - worker_01

## Boundary And Context Check
- Role: `worker_01` read-only review only (work item 1). No implementation, no production writes, no secret printing.
- Authorized cwd: phase5 worktree `.` (= `.worktrees/phase5-clinical-facts-profile`).
- Initial reads: `context/phase5-env-preflight-20260901_execution_context.md`, `plans/codex_execution_phase5-env-preflight-20260901.md`.
- Context Source-of-Truth was still `TODO`; additional evidence was gathered inside the worktree only.
- Report file not written by this worker; returned in-response for runner persistence.

## Work Performed
Read-only root-cause review of config load → launcher/runtime env → graded semantic routing → V2 lifespan/job start → existing tests, against the live SAR pause evidence.

### Evidence: current loading / startup / routing
1. **Config load is hardcoded to worktree `.env`, with no `ENROLLMENT_ENV_FILE`.**
   - `app/config.py` always loads `Path(__file__).parent.parent / ".env"` via `os.environ.setdefault(...)`, then binds module constants including:
     - `DECONSTRUCT_GLM_API_KEY = os.getenv("DECONSTRUCT_GLM_API_KEY","").strip() or INDEPENDENT_VLM_API_KEY`
   - Repo-wide search: `ENROLLMENT_ENV_FILE` exists only in plans/context/prompts, **not in executable code**.
   - FS check: `worktree_has_.env=no`; `main_repo_has_.env=yes`.

2. **Launch scripts also hardcode `$APP_DIR/.env` and intentionally omit secrets from runtime env.**
   - `scripts/start_enrollment_review.command` `dotenv_value()` reads only `$APP_DIR/.env`.
   - `write_model_runtime_env()` writes model identity vars only (route mode/provider/model/effort), **not** `DECONSTRUCT_GLM_API_KEY` / `DECONSTRUCT_GLM_BASE_URL` / `INDEPENDENT_VLM_API_KEY`.
   - `scripts/run_enrollment_review_service.sh` allowlist re-exports those non-secret identity keys only.

3. **Declared route ≠ executable route today.**
   - Graded complex default: GLM → MTPLX → DeepSeek (`protocol_semantic_model_router._default_complex_candidates`).
   - `candidate_availability_error()` only checks key presence for GLM/DeepSeek; MTPLX/oMLX always “available”.
   - Missing GLM key → Chinese skip + continue (`PROVIDER_UNAVAILABLE`), not fail-closed at service start.
   - `service_entry_semantic_route_snapshot()` reports declared identities and explicitly excludes credentials.
   - V2 `create_app` lifespan upgrades DB / recovers jobs / starts `JobRunner`; **no semantic credential/endpoint preflight**.

4. **Live incident confirms the gap.**
   - `artifacts/.../service-start.json`: dedicated V2 started as  
     `.venv/bin/python -m uvicorn app.api.v2.app:create_app --factory --host 127.0.0.1 --port 8910` with cwd `.`, non-secret route env set, credentials “loaded from application configuration only”.
   - Snapshot declared `zhipu-coding-plan:glm-5.3-flash:high` first.
   - Matching `route-audit.json`: attempt 1 skipped with  
     `缺少 DECONSTRUCT_GLM_API_KEY` / `PROVIDER_UNAVAILABLE`.
   - Checkpoint / plan text match: dedicated V2 child process did not see GLM key.

5. **Test construction today.**
   - Subprocess env probes in `tests/v2/protocols/test_deconstruction_transport_config.py` for GLM←VLM reuse/override (`_glm_key_probe`).
   - Monkeypatch-based skip/fallback tests in `tests/v2/agents/test_protocol_semantic_model_routing.py` (`test_missing_glm_key_returns_explicit_chinese_skip_reason`, graded fallback).
   - Secret non-leak pattern exists for Independent VLM (`tests/v2/llm/test_independent_vlm.py`), **not** for semantic-route startup preflight / endpoint fault injection / worktree env-file contract.
   - No test asserts `ENROLLMENT_ENV_FILE` → process-visible `DECONSTRUCT_GLM_API_KEY`.

### Inference (root cause)
Minimal causal chain:
1. Secrets live in main-repo `.env`.
2. Dedicated V2 runs from worktree cwd/package path with **no worktree `.env`**.
3. Loader has no explicit env-file override.
4. Launcher runtime state deliberately does not inject keys.
5. Service still advertises GLM-first graded route, then silently skips GLM at job time.

Secondary gap: even with keys present, there is no startup gate proving declared candidates are credential-complete / endpoint-reachable before `JobRunner` accepts work.

### Recommendation: minimal fix boundary for `worker_02`
**In-scope files (smallest set):**
1. `app/config.py` — resolve env file as `ENROLLMENT_ENV_FILE` (required for dedicated/worktree runs) else legacy `<repo>/.env`; keep `setdefault` process-env precedence; preserve GLM←`INDEPENDENT_VLM_API_KEY` fallback.
2. `.env.example` — document `ENROLLMENT_ENV_FILE` and GLM mapping (no secrets).
3. `app/agents/protocol_semantic_model_router.py` (or tiny adjacent helper) — pure preflight: for declared graded/pinned candidates return configured/missing + endpoint status **without secrets**; Chinese failure text.
4. `app/api/v2/app.py` lifespan — run preflight **before** starting `JobRunner`; fail-closed or explicit degrade only if Codex chooses a degrade flag (default should fail-closed for declared primary GLM in graded mode).
5. Dedicated acceptance start path that launched the SAR V2 (same command pattern as `service-start.json`) — must export `ENROLLMENT_ENV_FILE` to an authorized env file; do **not** broaden LaunchAgent `model-services.env` secret allowlist unless Codex explicitly accepts that larger secret surface.
6. Focused tests under `tests/v2/` — subprocess load of temp env file; missing-key Chinese gate; endpoint fault via injectable transport/http stub; assert key material absent from exceptions/audit/preflight payloads; no live network.

**Out of scope / compatibility risks:**
- Do not write API keys into `output/runtime_state/model-services.env` by default (LaunchAgent inheritance + plaintext secret expansion).
- Do not change import-time constant semantics carelessly; keep subprocess probe style or reload helpers.
- Do not remove GLM←VLM key reuse.
- Do not relax DeepSeek source-closure gate or resume SAR job in this item.
- Do not auto-copy main-repo `.env` into worktree.
- Endpoint preflight must be injectable/stubbed in tests to avoid flaky network and accidental remote calls.
- Keep mid-route `candidate_availability_error` skip as defense-in-depth; startup gate is what closes “declared ≠ executable”.

**Uncertainty:** exact operator-owned env file path for SAR recovery (main `.env` vs a worktree-local authorized copy) is a Codex decision; this worker did not read `.env` contents.

## Artifacts And Evidence
| Kind | Path / symbol | Observation |
|---|---|---|
| Loader | `app/config.py` | Hardcoded `.env` + `setdefault`; GLM key falls back to VLM key; no `ENROLLMENT_ENV_FILE`. |
| Router | `app/agents/protocol_semantic_model_router.py` | Declared GLM-first chain; availability = key check; snapshot never includes secrets. |
| Transport | `app/agents/deepseek_protocol_transport.py` | GLM uses `DECONSTRUCT_GLM_*`; missing key raises Chinese ValueError. |
| Executor | `app/services/protocol_deconstruction_executor.py` | Skips unavailable candidates during `generate_draft`; exhausts route. |
| V2 app | `app/api/v2/app.py` | Lifespan has DB/recovery/runner; no credential preflight. |
| Launchers | `scripts/start_enrollment_review.command`, `scripts/run_enrollment_review_service.sh` | Hardcoded `.env`; runtime env omits secrets. |
| Live start | `artifacts/.../service-start.json` | Dedicated uvicorn on 8910; declared GLM-first; credentials not injected explicitly. |
| Live audit | `.../route-audit.json` | GLM skipped for missing `DECONSTRUCT_GLM_API_KEY`. |
| Checkpoint/plan | `CHECKPOINT_20260901_...`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` | Same root cause; calls for `ENROLLMENT_ENV_FILE` + preflight + non-leak tests. |
| FS | `.` vs main repo | Worktree lacks `.env`; main repo has `.env`. |

## Commands And Observations
- Read: execution context/plan; `app/config.py`; router; transport; executor; V2 app; launch scripts; selected tests; checkpoint; service-start + route-audit.
- Shell/`rg`: confirmed no executable `ENROLLMENT_ENV_FILE`; mapped DECONSTRUCT/GLM/preflight/secret-related symbols; verified `.env` presence asymmetry.
- `mcp_pi-agent_pi-worker` unavailable in this environment (`unknown flags: --no-prompt-templates, --no-context-files`); continued with direct reads/searches.
- No package installs; no `.env` content read; no code edits; no tests executed (read-only item).

## Blockers Or Missing Environment
- Context Source-of-Truth still TODO; mitigated with in-tree incident artifacts.
- Codex must choose: (a) require `ENROLLMENT_ENV_FILE` for all V2 starts vs only dedicated/worktree starts; (b) fail-closed vs explicit degrade when declared GLM is unconfigured; (c) whether endpoint probe is mandatory at startup or credential-presence-only for MVP.
- No authorization in this item to create/copy env files or implement fixes (`worker_02`).

## Rerun Requests Or Next Step
Hand off to `worker_02` with this boundary:
1. Implement `ENROLLMENT_ENV_FILE` in `app/config.py` + `.env.example`.
2. Add declared-route preflight (Chinese, no secrets) and invoke it in `app/api/v2/app.py` before `JobRunner`.
3. Ensure dedicated V2 start exports `ENROLLMENT_ENV_FILE` to an authorized file that actually contains GLM/VLM mapping inputs.
4. Add fault-injection tests for missing key / bad endpoint, proving non-leak and no live network.
5. Do not resume SAR job `da944f6e...` until Codex verifies process-visible configured GLM (configured/unconfigured only).
