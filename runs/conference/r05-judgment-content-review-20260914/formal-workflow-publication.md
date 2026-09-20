按同一只读角色核对已落地的正式保存命令、工作流取消修复，以及前端刷新/状态是否会误导。I'll continue the read-only source review of publication, workflow cancel-fixes, and the frontend refresh/abort paths, then return prioritized findings with exact lines.I have the publication and frontend surfaces; next I’ll trace command provenance, cancel-boundary code, and whether GET labels still claim the report is unsaved after publish.# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Fallback:** primary `zcode`/`GLM-5.3` unavailable; this pass is `grok-build`/`grok-4.6`. Source inspection only. No clinical adoption. Runtime/tests explicitly deferred (not defects).

**Imports (source-resolved, not compiled):** `prepared_review_publication.py` → `PreparedReviewContinuation`, `require_workflow_scope`, `submit_qualified_review`, `ScopeViolationError`, `JobStore.get_last_checkpoint` (tuple `[1]` payload). API lazy-imports the command + `ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID`. Signatures match. Command does not create approval; empty env gate is rejected (`publication.py:18-19`, `config.py:108-110`).

**Cancel-fix audit (applied vs missed):** `_cancel_boundary` `109-113` does `cancel_at_boundary` then `_cancel_owned`. `_children(..., for_cancellation=True)` `95-99` skips corrupt with `logger.exception`; default/GET/retry/publish stay strict. Authority/scope `214-217` cancel verified children. `ReviewDependencyFailed` `253-254` is `RuntimeError` so `209-213` fail-step parent only.

---

**P0 — HTTP cancel still strict, so a corrupt sibling blocks parent cancel**

`change_review_workflow` `320-324` calls `_children` **without** `for_cancellation=True` *before* `request_cancel`. One `PersistedContractInvalid`/`ScopeViolationError` aborts the txn: parent `cancel_requested` never sets, verified children keep running. Maintenance skip-corrupt (`_cancel_children` `128-133`) only runs after `parent.cancel_requested`. UI cancel therefore cannot reach the cascade the last review asked for.

Minimal fix: on `operation == "cancel"` only, `request_cancel(workflow_id)` first, then `_cancel_owned` (skip-corrupt + log). Keep strict `_children` on retry/GET/publish.

---

**P1 — Successful publish still reads as “unsaved”; Generate stays armed**

Parent completion is checks-only (`workflow.py:260-261`, `publication.py:32-33` require `clinical_adoption is False`). Publish does not change job state. GET `qualified_review.py:151-153` always maps `state==completed` → “核对完成，尚未保存审核报告”. Panel `PreparedReviewPanel.tsx:41-42` still shows 生成审核报告. `usePreparedReview.ts:69-72` will POST again (idempotent, not a second clinical save).

Repeat save is otherwise sound: key `prepared-review-publication:{workflow_id}` (`publication.py:46`); `publish_frozen_review` `52-69` returns the same `review_run_id` when hash matches, conflicts when it does not. First persist **does** call `FactAuthorityValidator.validate` (`frozen_review_publication.py:71`) inside the same nested txn as authorization gates (`qualified_review_command.py:152-159`) — stale current snapshot/revision is rejected; idempotent replay does not re-validate (correct). Catalog currency is `_material` `77-78`. Wrapper need not duplicate the validator.

Minimal fix: GET/view: if `context.review_run_id` already has a completed run, label “审核报告已保存” (or equivalent) and omit generate. Do not flip workflow `state` to imply clinical adoption.

---

**P1 — Poll stops on first GET error; retryable parent is also treated as terminal**

`usePreparedReview.ts:8,36-45`: `terminal` includes `failed_retryable` and `waiting_user`. Catch sets `errorMessage` and does **not** reschedule the 3s timer; last `data` is kept. In-progress server work continues with a frozen UI until 刷新 (`68`) or retry (`92`). `mutate` `52` silently returns if another mutate is in flight (cancel during prepare/start is dropped, not aborted).

Minimal fix: on poll failure, keep `data` but schedule the next tick (cap retries). Treat only `completed|cancelled|failed_final` as stop-poll. If `operation.current` is set, abort it before starting cancel.

---

**P2 — Fail-closed provenance (not false-accept)**

Omitted/wrong-type/wrong-`candidate_job_id` fail `_dependencies_complete` `233-252` (`set(children)!=expected`, `CHILD_TYPES`, origin candidate). Extra owned jobs are not published, but **any** corrupt owned row fails strict `_children` inside that check (`238`) and therefore blocks publish. Content pairing is not in the wrapper; `verify_qualified_content` runs later in `qualified_binding_selection.py:318-323` inside the persist nested txn (rollback on mismatch). `ReviewDependencyFailed` from `_dependencies_complete` is not `ScopeViolationError` — a post-complete cancelled child would be an untranslated 500 (`qualified_review.py:82-86`). Checkpoint `ScopeViolationError` still cancels siblings (`214-217`); only child `failed_final|cancelled` preserve them.

Minimal fix: in `publish_prepared_review`, catch `ReviewDependencyFailed` → `ScopeViolationError`. Optionally verify only checkpoint IDs, not extra owned rows.

---

**Txn / selection (not defects):** API `session.begin()` owns commit (`qualified_review.py:76`). Command does not `begin`. `ReportsPage.tsx:243-244` sets `run` and `history.retry()`; `useLoad` `57` goes through `loading`, so the “记录不属于该节点” branch is not taken on that refresh. `onPublished` does not clear `workflow` (same P1).

**Unverified (deferred):** no process import, no HTTP/DB, no publish/cancel race execution, no browser.
