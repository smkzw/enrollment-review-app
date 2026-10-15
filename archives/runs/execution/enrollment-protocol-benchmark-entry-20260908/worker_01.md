# Execution Output: enrollment-protocol-benchmark-entry-20260908 - worker_01

**Fallback declaration:** I am running as the declared `pi` fallback (`opencode-go` / `muse-spark-1.3-contributor`), not the originally pinned `zcode`/`GLM-5.3-Flash` first-line executor. Capability limitation: I performed verification-only work (read APIs, ran the focused offline pytest, smoke-tested CLI help). I made **zero file edits** — both assigned artifacts already existed as untracked new files and satisfy the contract, so rewriting them would add risk with no benefit. I did not perform live model calls, visual/PPT/PDF/clinical acceptance, or production writes; those remain with Codex.

## Boundary And Context Check

- Work confined to the runner-provided worktree (`.`); no production paths read beyond the explicitly authorized source-of-truth files; no credentials, personal harness config, or raw clinical artifacts touched.
- Assigned scope: only `scripts/run_frozen_protocol_comparison.py` (823 lines) and `tests/test_frozen_protocol_comparison.py` (250 lines). Both exist as **untracked new files** (`git status`: `??` for exactly these two). `app/` modifications visible in `git status` are pre-existing worktree changes on `codex/phase5-clinical-facts-profile` (1775 uncommitted per session context), not mine.
- Constraints honored: no `app/` or original-file modifications by me, no package installs, no git operations, no network/model calls, no sibling process or report-file writes (report returned inline per runner rule).

## Work Performed

Verification pass on the two assigned artifacts against every contract clause:

1. **Product-service reuse (no reinvented harness):** script imports and drives `ProtocolWorkbenchService` (`start_first_deconstruction` → `get_identity_review` → `confirm_identity`), `create_protocol_deconstruction_executor` + `ProtocolDeconstructionExecutorConfig` + `load_persisted_route_audit`, and real `JobRunner` with `PROTOCOL_DECONSTRUCTION_JOB_TYPE`. Confirmed all referenced symbols exist with compatible signatures via introspection (`DeepSeekProtocolAgentTransport.__init__` accepts `backend/model/reasoning_effort/max_tokens`; executor config accepts `transport`, `transport_factory`, `page_texts_builder`, `draft_response_builder`; `resolve_data_paths(env_override=...)` exists; `tests.v2.api.protocol_e2e_helpers` exports `build_passing_draft_json`, `build_pipeline_e2e_docx`, `page_texts_from_blocks`).
2. **Prepare/execute separation:** `prepare` runs the real chain register → extract → render/align → identify → confirm → freeze, then stops at `generate_draft` via a non-retryable `StepFailure(STOP_ERROR_CODE)` wrapper around the **production** executor (no model call possible — the stop precedes semantic generation). `execute` re-verifies hashes, `retry_failed`s the same job, and continues with the production executor to the review boundary. Separate `prepare`/`execute` CLI subcommands; `execute` refuses any job not in the frozen-stopped state.
3. **Budget enforcement ≥ 65536:** `resolve_output_budget` rejects `< 65536` pre-send (`ComparisonGuardError`, exit 4); effective budget re-checked against `MTPLX_/OMLX_PROTOCOL_BATCH_MAX_TOKENS` caps with an explicit "raise the cap env var" error instead of silent downgrade. `execute` resolves the budget **before** creating `execute/`, so guard failures leave no half-finished directory (asserted by test).
4. **Native transport only, no masquerade:** `build_transport` allows only `SUPPORTED_PROTOCOL_DECONSTRUCTION_BACKENDS` (`deepseek, glm, mtplx, mtplx-api, omlx, zhipu-coding-plan`); unknown backends and unconfigured-but-supported backends (e.g. empty `DEEPSEEK_API_KEY`) both raise `ComparisonGuardError` without sending. Sampling params keep provider defaults; only model/effort/budget are selectable.
5. **Isolation + receipts:** data/DB under `<run-dir>/data_v2` via `resolve_data_paths(env_override=...)` + migrate-to-head; refuses existing run dirs and source/output overlap (overlap checked **before** existence so the precise violation is reported). Receipts use existing product hooks only — route-audit blob, semantic-batch cache dir, `transport.history(session_id)` dump — no `app` hook additions. Usage/token limitation honestly recorded in `execute_record.limitations`.
6. **No test-time model calls:** offline tests inject `page_texts_builder` (prepare) and `draft_response_builder` + stub `transport`/`transport_factory` (execute) **via function parameters only**; CLI path (`main()`) never passes overrides and the record flags `executor_overrides_used`. History-dump test uses a fake `client.chat.completions.create`. Script contains no `api_key`/`API_KEY`/harness literals (grep: no matches).
7. **No synthetic-smoke contamination:** `scripts/run_protocol_control_smoke.py` untouched; no `draft_response_builder`/`page_texts_builder` literals in the script body.

## Artifacts And Evidence

- `scripts/run_frozen_protocol_comparison.py` — unchanged by me; implements `prepare`, `execute`, `build_transport`, `resolve_output_budget`/`effective_output_budget`, `ComparisonGuardError` (exit 4), `main` with `prepare|execute` subcommands. Manifest + `prepare_record.json` + `execute/execute_record.json` written with `claims_complete: false`, `clinical_acceptance: false`.
- `tests/test_frozen_protocol_comparison.py` — unchanged by me; 8 tests covering budget guard, unsupported/unconfigured backends, non-DOCX rejection, source/output overlap, unprepared-run-dir refusal, prepare→execute offline end-to-end (expects `awaiting_user == "review"`, hash verifications true, `route_audit is None` on the injected-builder path), and product-`history`-hook receipt dump.
- Test result: **8 passed in 1.29s** (only `DeprecationWarning`/SWIG noise), proving zero network/model dependence.
- CLI smoke: `--help` and `prepare --help` render correctly (study-phase choices, identity-override flags, backend/model/effort/budget flags).

## Commands And Observations

| Tool / command | Target | Observation |
|---|---|---|
| `read` | `context/..._execution_context.md`, `plans/codex_execution_....md` | Objective, boundaries, single work item confirmed |
| `glob` | `scripts/*.py; app/services/protocol*; app/agents/protocol*; tests/test_frozen*` | Located actual filenames (`protocol_workbench_service.py`, etc.) |
| `read` | script (1–103, 104–310, 314–500, 504–723, 724–823), test (1–250) | Full contract review; CLI never injects test overrides |
| `bash` introspection | `app.config`, transport, executor config, helpers | All imports resolve; signatures compatible (backends listed above) |
| `bash` pytest | `tests/test_frozen_protocol_comparison.py -q` | **8 passed**, 1.29s, offline |
| `bash` CLI smoke | `--help`, `prepare --help` | Usage text correct |
| `bash` `git status` + `grep` | scope check | Only the 2 assigned files untracked; `app/` diffs pre-existing; no secret/harness literals in script |

## Blockers Or Missing Environment

- None. `.venv/bin/python` present and correct (per memory rule); no installs needed; no missing inputs. Live DOCX end-to-end (real upload → freeze → real model execute) is intentionally **not** run by this worker — owner runs real tests after verification per context.

## Rerun Requests Or Next Step

- No rerun needed for `worker_01`. Suggested Codex acceptance: (1) confirm the two untracked files are the intended final content (I verified, did not author — if authorship/provenance matters, check with the originating worker); (2) owner-run live `prepare` on a real DOCX in a fresh run dir, then live `execute` with an explicitly funded backend, and confirm `execute_record.json` shows `awaiting_user: review` with non-null `route_audit` and populated `transport_histories` receipts; (3) `cleanup-execution` archival after acceptance.
