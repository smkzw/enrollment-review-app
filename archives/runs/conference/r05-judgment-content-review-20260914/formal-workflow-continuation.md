按同一只读角色核对已落地的 prepared-review 运行时与 JobRunner 依赖原语，找出最小可持久续跑路径。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object`. Fallback `grok-build` / `grok-4.6`. Source only.

**No cross-job dependency hook exists.** `StepSpec.depends_on` / `job_step_dependencies` are **intra-job** (`job_service.py:40-47`). `waiting_user` is an explicit human boundary (`jobstore.py:837-860`, `runner.py:414-420`) — do not use it for “parent not done.” JobRunner has no deferred-dependency outcome. Sequencing must be **outside** a single job.

**Choose reconciler in `_maintenance`, not a new runner state.** `serve` already does maintenance then `run_once` (`runner.py:138-155`). Enqueues are idempotent (`JOB_TYPE:{payload hash}`). That is crash-safe without recursive runners or a second queue.

### Smallest continuation

1. **One user action (new intake contract, not UI-only).** Today POST requires `kind` (`qualified_review.py:48-53`) so the client must start each step. Replace with `POST .../prepared-review-jobs` `{context_id}` only: enqueue owned **predicate** candidates; enqueue **control** only if `catalog.controls` else skip (`control_binding_job.py:33-34`). Browser close is irrelevant: jobs are queued.

2. **Reconciler** (new ~one function, called from `JobRunner._maintenance` after `requeue_due_retries`): scan owned incomplete pipelines by `execution_owner` + `review_context_id`. For each **completed** owned parent:
   - predicate/control → `enqueue_binding_qualification(..., product_runtime=True, candidate_job_id=parent)` (already copies context; empty pairs → summary-only, `binding_qualification.py:99-105`);
   - completed **predicate** → `enqueue_judgment_content` (empty pairs already handled, `judgment_content_job.py:99`).
   Reuse `mark_prepared_review_job` parent checks (`review_runtime_ownership.py:33-39`). Idempotent re-POST is a no-op (`created=False`).

3. **Pin child routes from the parent payload `routes`**, reconstruct `EvaluatedRoute`; do **not** call live preflight for children. Parent run stays pinned; don’t cascade current model config.

4. **Stale context:** if live `context.context_sha256` ≠ job payload, **stop enqueueing** (do not fail completed jobs). Same as intake (`prepared_review_intake.py:35-38`).

5. **Ready ≠ publish.** Progress should expose `ready_for_publication` when required owned jobs are `completed` (predicate qual + content; control qual if a control job exists). Formal save stays `submit_qualified_review` + existing approval (`qualified_review.py:21-28`). Never auto-call it.

6. **Ownership already correct:** `prepared_review_job_scope` (`review_runtime_ownership.py:16-24`) + runner `job_scope` (`runner.py:111-112`, `app.py:346`). Isolated jobs stay unowned; don’t cancel them.

**Do not** add `waiting_user` / `StepAwaitingUser` for dependencies, mega-job of all four types (would break receipts/`JOB_TYPE`), or new job-type aliases.

### Progress faults (`prepared_review_progress.py`)

- **Pagination:** `.order_by(JobRecord.job_id)` + `after_job_id >` (`33-36, 53`) is UUID lexicographic, not enqueue order. Use `created_at, job_id`.
- **Integrity over-fail:** one row with `review_context_sha256 !=` live context raises for the whole GET (`40-41`). Filter that sha in SQL (jobs of **this** snapshot) instead of 400-ing the page.
- No pipeline/ready fields — UI cannot be one-button without the reconciler + these fields. `next_cursor` keyset itself is fine (`53`).

**Reuse as-is:** executors + shared admission (`page_review_runtime.py:68-73, 143-144`); `enqueue_prepared_review_task`; empty-pair jobs; JobService idempotency; claim/recovery scope.

**New contract:** start-without-`kind` (+ progress `ready_for_publication` / missing next). **UI only:** prepare → one start → poll; later save with approval. No staged tests here. Not clinical acceptance.
