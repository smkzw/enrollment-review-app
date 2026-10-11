I'll start by reading the initial read set to understand the assignment.

Now I have the full picture. Let me write the new service module using `apply_patch`.

The `apply_patch` heredoc failed on a blank line inside a docstring. Let me write the file with the native tool and verify the diff scope.

One defect found in self-review: a missing snapshot/revision raises `NotFoundError` from inside `_source`, which my `except ReprocessingError` would not catch. Fixing that.

Adding a cheap member-count guard so a review batch of a different size never triggers per-member context reads.

All checks pass. Writing the final report as my response (the runner persists it).

# Execution Output: r05-batch-estimates-20260915 - worker_01

## Boundary And Context Check

- Initial read set read in full: `context/r05-batch-estimates-20260915_execution_context.md`, `plans/codex_execution_r05-batch-estimates-20260915.md`; plus `reviews/codex_conference_r05-batch-estimates-design-20260915_review.md` (owner limits, not authority) and the advisory `runs/conference/r05-batch-estimates-design-20260915/evidence_single_object.md` (design input only).
- Source of truth read: `app/services/batch_review_workflow.py`, `batch_review_view.py`, `batch_evidence_reprocessing.py`, `batch_evidence_reprocessing_view.py`, `evidence_reprocessing.py`, `prepared_review_workflow.py`, `prepared_review_intake.py`, `page_review_job_service.py` (`route_identity`), `fact_normalization_command_service.py` (`authority_from_active_episode`), `review_runtime_ownership.py`, `evidence_app_errors.py` (translation), `app/storage/models.py` (Job/Step/Checkpoint/Event + mixins), `app/storage/review_context_repository.py`, `app/storage/fact_authority.py`, `app/storage/codecs.py`, `app/workflow/jobstore.py`, `app/workflow/states.py`, `app/domain/contracts/{enums,jobs,facts,review_context_v2,page_review}.py`, `app/api/v2/{batch_reviews,batch_evidence_reprocessing}.py` (integration surface, read-only), `.trellis/spec/backend/{database-guidelines,error-handling}.md`, `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:451`.
- Write surface respected: only `app/services/batch_processing_estimates.py` was created. No other file was written. No production path, no test file, no env/credential read, no network, no model call, no application start, no DB connection, no migration, no package install.
- No Trellis task, conference, or peer review was started. No delegation, no subagents.
- Tool deviation (disclosed): the contract's preferred editor `apply_patch` rejected the initial `*** Add File` hunk ("Invalid patch hunk on line 284: '' is not a valid hunk header" — a blank line inside a docstring without the `+` prefix in a large heredoc). The file was created with the native file-write tool instead; both subsequent edits were applied with `apply_patch` successfully. The material constraint (single authorized path) is verified by `git status --porcelain`.

## Work Performed

Implemented `estimate_processing_batch(session, *, project_id, kind, members, routes=None, adapter=None) -> dict` in a new read-only service, per the Concrete Contract.

1. **Sample definition (whole-batch wall clock, gaps included).** A sample is one historical batch of the same kind in the same project, whose parent job is `completed` and whose **entire window is `JobRecord.created_at` → the parent's single `COMPLETED` event**. This is the user-perceived duration and inherently contains member-to-member maintenance-loop polling gaps, child queueing, and retry backoff. No summation of child durations, no page-count multiplication, no per-page medians.
2. **Members are matched exactly and in order.** Requested members are normalized to the ordered source 4-tuple `(subject_id, review_episode_id, snapshot_id, complete_id)` (1..50, no repeated episode, strict key set). A batch is eligible only if its own ordered member tuple list equals the requested list exactly.
   - `ocr`: the tuple is read from the frozen batch payload `members`.
   - `review`: the payload member identity is `context_id` (as in the enqueue path and `app/api/v2/batch_reviews.py`), so the tuple is derived from the frozen `ReviewContextSnapshotV2.authority` (snapshot + complete revision), with `context_sha256` re-verified against the frozen member entry.
3. **Comparability identity is frozen, not discovered.**
   - `review`: `payload["routes"] == {lane.value: route_identity(route)}` for caller-supplied routes **and** `payload["task_versions"] == current_review_task_versions()` (the same comparison `change_batch_review` uses), **and** each member's frozen `FactAuthority` must equal `authority_from_active_episode(session, review_episode_id)` — i.e. current episode revision, protocol version, rule-set id/revision, and active pointers all match. Stale preparation contexts are therefore never pooled.
   - `ocr`: `payload["profile_sha256"] == adapter.profile_fingerprint` (caller-supplied adapter). No private config discovery anywhere.
4. **Strict sample eligibility** (each unmet condition excludes the batch; no partial trust):
   - payload hash/contract/owner/members via the existing `material(...)` validators of both batch modules;
   - child ownership via `owned_workflows` / `owned_children` and completed-member checkpoints via `validate_completed_members` (reused as-is); additionally **every** member step and its recorded `member_state` must be `completed`, all member steps must be present, and **all owned children must currently be `completed`** (a child that was later retried can never be the original sample);
   - no `step_failed`/`failed`/`retry_scheduled`/`cancel_requested`/`cancelled`/`waiting_user`/`user_resumed`/`user_updated` events on the parent **or any child**, plus rejection of recovery markers in event payloads (`recovered_from_checkpoint`, `lease_recovery`, `attempt_budget_exhausted_during_recovery`, `recovery_attempts_exhausted`);
   - the parent event stream must end with exactly one `COMPLETED` event (the timestamp used), and the same "unique COMPLETED last" invariant is required of every child;
   - timestamps must exist and be comparable (`to_utc_naive` normalizes naive/aware); seconds must be finite and non-negative.
   - Rationale for the failure-event rule is the owner's conference decision: cancelled/failed or human-waiting attempts must not silently become successful completion samples (`reviews/codex_conference_r05-batch-estimates-design-20260915_review.md`), and a completed batch parent cycles through `queued`/`failed_retryable` while waiting for children (`jobstore.py:523-548`) without emitting events, so those benign states do not disqualify a completed batch.
5. **Bounded scan.** Same-project, same-job-type, same-`execution_owner` rows, ordered `created_at DESC, job_id DESC`, `limit(HISTORY_LIMIT + 1)`; the first 100 are scanned, and the extra row only sets `history_truncated`. Query shape is copied from the existing `recent_review_batches` / `recent_reprocessing_batches` projections. A cheap member-count guard prevents any per-member context read for batches that cannot match.
6. **Aggregation.** `n=0` → all three duration fields `null` (honest "cannot estimate"); `n=1..2` → median only, range `null`; `n>=3` → `statistics.median` plus `statistics.quantiles(values, n=4, method="inclusive")` lower/upper, rounded to milliseconds (`round(x, 3)`) for deterministic, reproducible output.
7. **Fees are unknown, not zero.** `cost` is always `{"amount": null, "currency": null, "reason": "no_verified_billing_basis"}`; there is no fork on task type (no "local = free" claim), no rates table, no token aggregation.
8. **Returned shape is exactly the frozen contract** (11 top-level keys + `cost`). The "不可估算原因" requirement is served by (a) the module docstring's explicit rule list and (b) a single debug-log channel `_exclude(batch_id, reason)` with stable reason codes: `batch_not_completed`, `batch_payload_unverifiable`, `batch_project_mismatch`, `review_config_mismatch`, `ocr_profile_mismatch`, `batch_members_unverifiable`, `member_selection_mismatch`, `member_completion_unverified`, `batch_events_invalid`, `timestamps_missing`, `duration_invalid`.
9. **Request-side validation (read-only, no prepare/write).** Project existence (`ProjectRepository.get`); per-member current identity via existing read validators — `authority_from_active_episode` for `review`, `_source` + episode active pointers + `EvidenceSnapshotRepository.current_status == ACTIVE` for `ocr`. All request/identity failures raise `ScopeViolationError` (message preserved → API maps it to `AppScopeMismatchError` via the existing `translate_storage_error`, `evidence_app_errors.py:788-789`, the same channel `batch_review_view` already uses).

## Artifacts And Evidence

- **New file (only artifact): `app/services/batch_processing_estimates.py`** — 387 lines, untracked-new (`?? app/services/batch_processing_estimates.py`).
  - Module docstring (boundary, sample rules, explicit limits/absence conventions) lines 1-66; constants 67-83 (`METHOD`, `MEMBER_KEYS`, `MEMBER_LIMIT=50`, `HISTORY_LIMIT=100`, `COST_UNKNOWN_REASON`, rejected-event and recovery-reason sets).
  - `estimate_processing_batch` 86-120 (return shape 115-120); `_requested_member_keys` 123-139; `_comparability_identity` 142-161; `_current_review_authority` 164-177; `_require_current_ocr_source` 180-196; `_recent_project_batches` 199-208; `_sample_seconds` 211-239; `_exclude` 242-245; `_batch_material` 248-251; `_batch_children` 254-257; `_batch_validate` 260-264; `_ocr_member_keys` 267-278; `_review_member_keys` 281-316; `_members_completed` 319-342; `_completed_window_seconds` 345-357; `_verified_events` 360-375; `_duration_summary` 378-387.
- **Rule-to-source evidence used to build the contract** (for owner verification):
  - batch parent payload freezes `members`/`routes`/`task_versions`: `batch_review_workflow.py:49-69`; member ownership/reconciliation: `:72-95`; completed checkpoint semantics: `:106-122`; continuation `start_step/complete_step/finish_success`: `:233-254`.
  - OCR batch payload freezes `profile_sha256` + 4-key members: `batch_evidence_reprocessing.py:37-64`; ownership: `:67-100`; completed checkpoints (`activated is False`): `:103-120`; enqueue-time current-pointer gate: `:130-181`; continuation: `:314-338`.
  - review batch `task_versions` equality used by retry: `batch_review_workflow.py:149-151`; route freezing helper: `page_review_job_service.py:68-73`; `current_review_task_versions`: `prepared_review_workflow.py:41-50`.
  - event vocabulary: `app/domain/contracts/enums.py:198-211`; terminal states: `app/workflow/states.py:57-66`; completion event + single-winner UPDATE: `jobstore.py:1091-1141`; failures/retries: `:707-830`, `:1228-1259`; recovery markers: `:1450-1516`; deferred release (no event, `queued`/`failed_retryable`): `:523-548`.
  - payload-hash verification and UTC-naive normalization: `app/storage/codecs.py:47-57, 73-90`; job columns: `app/storage/models.py:1371-1454`; mixin timestamps: `:60-83`.
  - read-projection precedent (bounded query, `ScopeViolationError`): `batch_review_view.py:16-38`, `batch_evidence_reprocessing_view.py:33-56`.
  - member-shape collision exposed: `app/api/v2/batch_reviews.py:11-21` (review member = `context_id`) vs `app/api/v2/batch_evidence_reprocessing.py:13-19` (OCR member = the same 4 keys I implement) — see Q1 below.
  - requirement "批量运行前显示按历史中位数估计的时间和费用区间，明确标注为估算": `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:451`.

## Commands And Observations

- `apply_patch` (Add File heredoc) → `Invalid patch hunk on line 284` (blank docstring line lacked `+`); no file written. Fallback: native file create (single authorized path).
- `.venv/bin/python -m py_compile app/services/batch_processing_estimates.py` → exit 0, `PY_COMPILE_OK`. System `python3` is not 3.12 in this machine, so the project venv (3.12.13) was used; no `uv` sync/install was run.
- `git diff --check` (whole worktree) → exit 0, `DIFF_CHECK_OK`.
- `git status --porcelain -- app/services/batch_processing_estimates.py` → `?? app/services/batch_processing_estimates.py`; no other path was created or edited by this pass.
- `git status --porcelain --ignored -- app/services/__pycache__/` → `!! app/services/__pycache__/` (the `.pyc` produced by the authorized `py_compile` is gitignored, `pyproject`/`.gitignore:10-11`).
- Pre-existing worktree dirtiness (not mine, FYI for commit scoping): 27 modified + 59 untracked files under `app/services/` before my file.
- Symbol-existence verification for every import (grep only, no import run): `SnapshotStatus`, `JobEventType.{COMPLETED,FAILED,USER_RESUMED,USER_UPDATED}`, `EventRow`, `to_utc_naive`, `EvidenceSnapshotRepository.current_status`, `EpisodeRepository`, `ProjectRepository`, `authority_from_active_episode`, `route_identity`, `current_review_task_versions`, `material`/`owned_workflows`/`owned_children`/`validate_completed_members` of both batch modules, module attributes `BATCH_JOB_TYPE`/`OWNER` of both batch modules — all present.
- Self-review defect found and fixed during the pass: `_source` raises `NotFoundError` (a `RepositoryError`) for a missing snapshot/revision, not `ReprocessingError`; the OCR handler now catches `(ReprocessingError, RepositoryError)`. Second hardening: member-count guard before per-member context reads.

## Blockers Or Missing Environment

- No hard blocker; the assigned item is complete for review.
- Checks that the contract did not authorize and therefore remain unverified (owner-owned): import/wiring execution (no `import`/app start allowed), any real DB read (sample density, `n` values, `excluded_count` realism), API/UI integration, and full tests.
- Assumptions recorded (each is a decision Codex can overturn):
  1. Review comparability key is the ordered 4-tuple derived from the frozen context authority, with full authority equality to the current authority also required (stricter than the tuple alone).
  2. Batch duration = parent `created_at` → single `COMPLETED` event; member gaps are intentionally included and no decomposition is offered in this scope.
  3. `excluded_count` counts every scanned recent batch not used as a sample (including different selections/configs), not only near-miss samples.
  4. `history_truncated` means "more than 100 same-project batches of this kind exist", so matching samples older than the window are honest misses.
  5. `n>=3` uses inclusive quartiles for the range and `statistics.median` for the median; for the inclusive method `q2` equals the median (inference from the standard-library definition, not executed here).
  6. Fees are represented only by the fixed unknown-cost object; no currency is inferable in this scope.

## Rerun Requests Or Next Step

1. **Q1 (integration shape, highest impact):** my contract implements the 4-key member for **both** kinds, but the review enqueue path and `app/api/v2/batch_reviews.py:11-21` identify members by `context_id`. The API layer must therefore pass `snapshot_id`/`complete_id` from the episode's current active pointers (`episode.active_evidence_snapshot_id` / `active_evidence_processing_revision_id`). Do you want (a) keep exactly this (my implementation), or (b) also accept an optional 5th key `context_id` for `review` and additionally require the historical member's exact `context_id`? (b) is a small change: extend `_review_member_keys` to compare it when present.
2. **Q2 (missing reason surfacing):** non-estimable/comparability reasons currently live in the docstring and the `_exclude` debug log only, because the returned dict is frozen at 11 keys + `cost`. If the UI must explain "暂无可比历史", authorize adding e.g. `unavailable_reason` / `excluded_reasons` — otherwise Codex's API layer can infer "no compatible history" from `sample_count == 0` plus `excluded_count`/`history_truncated`.
3. **Q3 (strictness confirmation):** the per-contract "reject any failure event" rule also rejects batches whose child step failed transiently and then auto-retried to `completed` (e.g. `evidence_processing` has `max_attempts>1, retryable=True`). Confirm this conservative exclusion is intended rather than sampling eventually-successful runs.
4. **Q4 (error vocabulary, minor):** all request/identity failures raise `ScopeViolationError` (single read-only channel, message preserved). If you prefer per-kind app errors (OCR's own `ReprocessingError`/`AppStaleAuthorityError` wording or the "recovery action" text), say so and it becomes a one-line change per branch.
5. **Owner verification still needed before acceptance:** import/app-start wiring (`uv run python -c "import app.services.batch_processing_estimates"` or app boot), one real read against a project with completed batches to confirm `n`, and API/UI integration + tests after product construction (as deferred by the user). Resume point: this module plus Q1/Q2 answers; no rerun of this pass is required.
