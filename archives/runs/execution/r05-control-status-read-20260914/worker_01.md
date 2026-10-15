Trellis SessionStart context loaded. Reading the initial read set now.

Now writing the read-only status service.

Checks pass. Producing the report.

# Execution Output: r05-control-status-read-20260914 - worker_01

## Boundary And Context Check

- Read the initial read set in full: `context/r05-control-status-read-20260914_execution_context.md`, `plans/codex_execution_r05-control-status-read-20260914.md`.
- Extra context read only because the assigned contract depends on it (all read-only): `app/services/protocol_control_execution.py` (job payload, gate step, replay guard, closure step creation), `app/services/protocol_control_catalog_publication.py`, `app/api/v2/protocol_control.py`, `app/api/v2/protocol_control_schemas.py`, `app/services/protocol_control_job_service.py`, `app/services/protocol_control_executor.py`, `app/storage/models.py` (Job/Step/Checkpoint rows), `app/workflow/jobstore.py` (`complete_step`, `finish_success`, `get_last_checkpoint`), `app/workflow/states.py`, `app/api/v2/errors.py`, `app/services/evidence_app_errors.py`, `app/api/v2/jobs.py` (existing GET conventions), `app/services/page_review_status.py`, `app/services/judgment_search_status.py` (status-service precedent), `app/api/v2/app.py:300-360` (state wiring, router include), `app/api/v2/protocol_schemas.py:298-308` + `app/api/v2/protocols.py:580-606` (publish request consumes `control_job_id`/`control_checkpoint_id`), `runs/conference/r05-control-publication-20260914/evidence_single_object.md`, `.trellis/spec/backend/error-handling.md`.
- Writes stayed inside the owner contract exactly: new `app/services/protocol_control_status.py`; edited `app/api/v2/protocol_control.py` and `app/api/v2/protocol_control_schemas.py`. No change to execution, publication, storage, models, frontend, docs, tests, or `app.py`. Worktree was already dirty (1672 paths); the three target paths were clean before editing (`git status --porcelain` empty for them).
- No model call, no DB, no `create_app`, no server, no test, no package install, no network, no credential handling, no reading of original clinical material.
- I did not verify final acceptance and do not claim it. Codex owns source authority, integration, and acceptance.

## Work Performed

**1. New read-only service `app/services/protocol_control_status.py` (new file, 212 lines)**

- `protocol_control_execution_status(session_factory, *, job_id)` (`:84-134`), decorated with the established `app_error_boundary`.
  - Job missing or `job_type != PROTOCOL_CONTROL_JOB_TYPE` → `AppNotFoundError` (404 `NOT_FOUND` envelope), matching `page_review_status.py:16-24` and `judgment_search_status.py:62-71`.
  - Job payload restored through `verify_payload_sha256` (hash + JSON verified; corruption follows the established `PersistedContractInvalid → AppInternalError` path, `evidence_app_errors.py:826-830`).
  - Version binding: `payload["execution_version"] != PROTOCOL_CONTROL_EXECUTION_VERSION` or a missing/empty `payload["source_deconstruction_job_id"]` → fail closed (409). Source job id field confirmed in `protocol_control_execution.py:718`.
  - `state == "completed" and not cancel_requested` → verify the package, then report `candidate_ready` with the checkpoint and count. Otherwise `processing` (non-terminal) or `stopped` (`TERMINAL_JOB_STATES` or `waiting_user`), with `publishable_checkpoint_id=None` and `candidate_count=None` — no guessed zero, no checkpoint.
- Checkpoint selection and verification `_verified_candidate_package` (`:137-187`): the completed `gate` step record must exist (`session.get(JobStepRecord, (job_id, STEP_GATE))`), the checkpoint must be the last checkpoint of exactly that step (`JobStore.get_last_checkpoint`), and the checkpoint row must be bound to `(job_id, "gate")` — the same binding `prepare_control_catalog_publication` uses (`protocol_control_catalog_publication.py:43-48`). No "newest checkpoint of the job" and no source-job draft is ever used as candidate evidence.
- Verified fields mirror (not weaken) the executor's gate replay guard (`protocol_control_execution.py:941-1000`): `stage == "gate"`, `accepted is True`, `gate_version == CONTROL_PUBLICATION_GATE_VERSION`, `result_kind == CANDIDATE_CONTROL_PACKAGE_RESULT_KIND`, `formal_catalog_status == FORMAL_CATALOG_STATUS_NOT_MATERIALIZED`, `ProtocolControlBatchPlan` + every `ProtocolControlBatchDispositionHydrated` re-validated, `candidate_ids == sorted(set(candidate ids from validated dispositions))`, `publication_plan_id == plan.plan_id`. Added closure bindings: `coverage_manifest_id == payload["coverage_manifest"]["manifest_id"]` and 1:1 batch coverage (`batch_id` set and count equal to the plan's batches). Count = number of verified candidate identities.
- Anything inconsistent on a completed job (`ProtocolControlCheckpointInvalidError`, `:59-68`) → 409 with a natural-Chinese envelope and fixed detail: no payload text, no exception text, no logs, no credentials. A candidate-ready package is never described as published or clinically approved.

**2. API wiring (two authorized files)**

- `app/api/v2/protocol_control_schemas.py:26-36`: `ProtocolControlExecutionStatusResponse` (`job_id`, `state`, `state_label`, `source_job_id`, `status`, `status_label`, `publishable_checkpoint_id: str | None`, `candidate_count: int | None = Field(default=None, ge=0)`).
- `app/api/v2/protocol_control.py:54-72`: `GET /api/v2/protocol/control-executions/{job_id}`; reuses the existing `app.state.protocol_control_job_service.session_factory` per the owner contract, keeps `state_label` in the API layer (`JOB_STATE_LABELS`), and constructs the response explicitly. `publishable_checkpoint_id` maps 1:1 onto `PublishRequest.control_checkpoint_id`.
- POST behavior untouched (verified by route introspection, below). Returned values: candidate status `candidate_ready` with label `补充审核要求已整理，等待随方案发布`.

## Artifacts And Evidence

| Artifact | Status | Key evidence |
|---|---|---|
| `app/services/protocol_control_status.py` | new (untracked) | `:84-134` entry, `:137-187` verification, `:59-68` 409 error, `:47-52` labels |
| `app/api/v2/protocol_control.py` | modified (+24/−1) | `:54-72` GET route |
| `app/api/v2/protocol_control_schemas.py` | modified (+13) | `:26-36` response model |

Code-derived invariants used (read, not executed): the runner writes checkpoint payloads as `{"attempt": n, **step_payload}` and the `gate` step is created dynamically by the closure step (`jobstore.py:664-696`, `protocol_control_execution.py:1325-1343`); a job only reaches `completed` when the cancel flag is false and every step is terminal (`jobstore.py:1083-1129`), so `completed` implies a completed `gate` step — the 409 branches for a missing gate step or an outstanding cancel request are fail-closed guards, not expected normal states. Only the runner writes checkpoints for control steps; post-completion partial checkpoints exist only for deconstruction workbench steps (`protocol_workbench_service.py:1363,2407,2672,2687`), so a partial delta cannot shadow the gate completion here.

Never exposed: credentials, payload source text, exception/log text, backend identifiers beyond the checkpoint id the publication flow must echo back.

## Commands And Observations

Read-only/compile only; no tests, DB, server, or app construction (per owner contract).

1. `ls app/api/v2/ && ls app/services/`, `wc -l ...` — located the source-of-truth modules and sizes (`protocol_control_execution.py` 1873 lines, `protocol_control.py` 49 lines before edit).
2. `grep -n "def |checkpoint|source_deconstruction_job_id"` on the executor; targeted `Read` of `:400-800`, `:826-1005`, `:1238-1350`, `:1530-1830` — confirmed payload fields, gate result shape, step creation, and replay semantics.
3. `grep` over `app/` for `prepare_control_catalog_publication|source_checkpoint_id|control_checkpoint_id` and for existing `control-executions` references — confirmed the downstream consumer contract and that no status endpoint existed yet (`tests/v2/api/test_protocol_control_execution.py` covers POST only; frontend has no references).
4. `git status --porcelain <three target paths>` before editing — clean; `ls app/services/protocol_control_status.py` — did not exist.
5. `.venv/bin/python -m py_compile app/services/protocol_control_status.py app/api/v2/protocol_control.py app/api/v2/protocol_control_schemas.py` → exit 0, `PY_COMPILE_OK`.
6. `.venv/bin/python -c "from app.api.v2.protocol_control import router; ..."` → import succeeded and printed:
   - `['POST'] /api/v2/protocol/control-executions StartProtocolControlExecutionResponse`
   - `['GET'] /api/v2/protocol/control-executions/{job_id} ProtocolControlExecutionStatusResponse`
   - schema fields `['job_id','state','state_label','source_job_id','status','status_label','publishable_checkpoint_id','candidate_count']`
   (module import only — no app creation, no DB, no server.)
7. `git status --porcelain`/`git diff --stat` after editing → `M app/api/v2/protocol_control.py`, `M app/api/v2/protocol_control_schemas.py`, `?? app/services/protocol_control_status.py`; nothing else touched (bytecode caches are gitignored).

## Blockers Or Missing Environment

None. `.venv/bin/python` present; all imports resolved, so no missing dependency or environment gap. No package installation or external setup is needed.

Unverified boundaries (honest scope statement):
- No runtime execution of any branch (no DB, no fixture, no test). The 404 / `processing` / `stopped` / `candidate_ready` / 409-on-corrupt paths are reasoned from read code and precedent, not observed.
- The exact HTTP envelope for the new 409 (status, `code`, Chinese title/detail/recovery) is derived from `register_error_handlers`/`map_exception`; not exercised.
- The zero-candidate verified package path (a legitimate outcome per `control_catalog_materialization.py:32-36`) was not exercised; it returns `candidate_ready` with `candidate_count=0`.
- Timestamp/ordering assumptions: checkpoint selection is "last checkpoint of step `gate`". Correct today because only the runner writes control-step checkpoints; if a future change appends post-completion partial checkpoints to control steps (the pattern documented in `jobstore.list_checkpoints`), selection must move to the `STEP_COMPLETED` event's `checkpoint_id`.

## Rerun Requests Or Next Step

Decisions I made that Codex should confirm or override (all cheap to change):
1. **Error class/status for a completed-but-unverifiable package**: new `EvidenceAppError` subclass in the new module, 409 `PROTOCOL_CONTROL_CHECKPOINT_INVALID`. Rationale: "must not look ready" + established envelope conventions; forward-reference-safe and cannot silently fail a publication later. Hash/JSON corruption still maps to the pre-existing 500 `AppInternalError` (untouched convention).
2. **Version mismatch is treated as unverifiable in every state** (including in-flight jobs), not as 404. If Codex prefers "not this contract → 404", that is a one-line change.
3. **Zero-candidate verified package reports `candidate_ready` + `candidate_count: 0` with the single specified label.** If the product wants different wording (e.g. `本次未整理出需要随方案发布的新增审核要求`), the label table `app/services/protocol_control_status.py:48-52` is the only place to change.
4. **Service result is a frozen dataclass**, not a dict like `page_review_status`/`judgment_search_status`; the route constructs the response explicitly and keeps `state_label` in the API layer so the service never imports `app.api.v2`.
5. **No new `app.state` entry** (app.py is outside my write set); the route reads `session_factory` off the existing `protocol_control_job_service`. If Codex wants a dedicated registered status service, the owner adds it in `app/api/v2/app.py`.
6. **Added batch-coverage closure** beyond the executor's replay guard (dispositions 1:1 with plan batches). It can only fire on foreign/tampered records because `_execute_hydrate` already enforces 1:1 at write time (`protocol_control_execution.py:1614-1619`).

Requested next steps for the owner:
- Integrate and run the deferred staged tests (user explicitly deferred all tests until complete construction): 404 for missing/foreign job; `processing`/`stopped` without checkpoint or count; `candidate_ready` only with the exact gate checkpoint id and verified count; 409 when the gate checkpoint is replaced by another step's checkpoint, by a non-accepted result, or by a mismatched candidate set; POST contract unchanged.
- Confirm the field name `publishable_checkpoint_id` is what the pending frontend will send back as `control_checkpoint_id`.
- No rerun of this worker is needed for compilation; a follow-up worker pass would only be required if Codex changes decisions 1-3.

No sibling process files were created; the runner owns this report.
