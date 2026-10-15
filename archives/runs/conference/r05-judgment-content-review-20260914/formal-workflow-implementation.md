按同一只读角色核对已落地的 `prepared_review_workflow` 父任务：先读工作流、认领/恢复与取消路径，再查失败与竞态。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object`. Fallback `grok-build` / `grok-4.6`. Source findings only (no runtime). Not clinical approval.

Parent-as-job + maintenance continuation is the right primitive: no inter-job `depends_on`, no `waiting_user`, no second queue. Wait path does not `start_step` (`154-156`), so attempts are not burned. Child `JOB_TYPE`s unchanged. Completion checkpoint `clinical_adoption: False` (`228-229`).

---

### Genuine bugs (minimum fixes)

**1. Parent cancel at continuation boundary does not cancel children in that txn.**  
`_advance` / `_release` only `cancel_at_boundary(lease)` (`162-163`, `180-181`, `192-193`). JobRunner never claims the parent, so `on_cancelled` → `cancel_workflow_children` (`app.py:198-200`) does **not** run. Children keep running until the next `_cancel_children` tick (`91-106`).  
**Fix:** after parent `cancel_at_boundary`, `request_cancel` those `_children` in the same writer txn (same as `change_review_workflow` `290-294`).

**2. `_children` strict raise poisons all workflow maintenance.**  
Hash/owner/routes mismatch (`84-88`) aborts `_cancel_children` and `_dependencies_complete`. `__call__` has no try around `_cancel_children` (`108-113`); a bad child blocks cancel of siblings **and** parent recovery that tick.  
**Fix:** cancel path: `request_cancel` by `workflow_job_id` extract without verify-or-raise; advance path may still fail-closed that parent only.

**3. Authority/scope failure leaves in-flight children.**  
`FactAuthorityValidator` (`147`) / `_material` catalog drift (`73-74`) throw into `except Exception` → parent `fail_step` (`183-186`) without canceling children.  
**Fix:** on those `ScopeViolationError`s, `request_cancel` owned children in the fail txn (work already completed stays `completed`).

Not invented: wait/release, dedicated parent recovery (`109-112` vs runner `job_scope` excluding unregistered type), retry only `failed_*` steps (`jobstore.py:1236-1245` + `304-306`), live routes must equal frozen payload (`231-232`, `51-53`), zero-pair child jobs still enqueued, control skipped unless frozen `includes_controls`. Hash mismatch on progress GET remains visible (`prepared_review_progress.py:40-41`); workflow GET uses `_material` sha check (`70-71`). Authority is **not** sha: validator on advance/retry (`147`, `298`), not on GET (acceptable for historical DTO).

---

### Residual (not blockers)

- One queued parent per maintenance tick (`115-118`); wait is cheap; `run_once` still claims children.  
- `routes_provider()` inside the lease on `_schedule` can preflight; enqueue path already `_prepare()`s (`page_review_runtime.py:107-110`).  
- Workflow GET `stage_label` = first incomplete `list_steps` row (`created_at` order) (`workflow_view.py:21-27`) — OK if steps were created in order.  
- Manual `kind` POST still works without `workflow_job_id`; parent ignores those children.

**Min patch:** (1)+(2)+(3) cancel/fail paths. Then read-side DTO. No auto-publish. No tests run.
