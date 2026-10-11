按同一只读角色核对 JobRunner 认领/恢复与现有入排任务类型，给出最小可接线边界。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object`, adjacent **runtime wiring**. Fallback `grok-build` / `grok-4.6`. Source only. Not clinical approval.

**Do not** register the four executors without a claim/recovery predicate. Registration alone would execute every queued/retrying/expired-lease job of those types, including historical isolated runs that share `job_type`. Do **not** invent new job-type aliases (`idempotency_key` and receipt rebuilds pin `JOB_TYPE`).

---

### Current boundary (why it is incomplete)

| Mechanism | Behavior |
|---|---|
| `JobRunner._claim` | `claim_next` with `job_type=None` (`runner.py:157-189`) → **any** queued/recovering row |
| Missing executor | Claim still succeeds; step fails `EXECUTOR_MISSING` fatal (`389-395`, `471-476`) |
| Recovery | `recover_expired_jobs` / `requeue_due_retries` / `cancel_expired_cancel_requests` scan **all** types (`recovery.py:33-54`, `jobstore.py:1294-1390`); startup `run_startup_recovery` (`app.py:181`) |
| Registration | `default_executors` has page review / search / evidence / protocol, **not** the four (`app.py:280-323`) |
| Overlap | Same strings: `predicate_binding_candidates`, `control_binding_candidates`, `binding_qualification`, `judgment_content` |
| Durable marker already on payload | Candidate/control/qualification set `review_context_id` **only if** passed (`predicate_binding_job.py:63-68`, `control_binding_job.py:49-54`, `binding_qualification.py:92-94`). Content **always** sets it (`judgment_content_job.py:83`) |
| HTTP | prepare/save registered (`app.py:390`, `qualified_review.py:45-73`); **no** enqueue routes for the four |
| Admission | `PageReviewRuntime._prepare` already shares one `PageReviewAdmission` across page/search (`page_review_runtime.py:54-74, 119-125`) |

`payload_json` is Text JSON (`models.py:82`) so `json_extract(payload_json, '$.review_context_id')` is a durable SQL gate, not an in-memory allowlist.

---

### Minimal ownership predicate (same queue)

Treat a job as **product-owned** iff:

1. `job_type` ∈ registered executor keys (never claim unknown types), **and**
2. If `job_type` is one of the four overlap types: `json_extract(..., '$.review_context_id') IS NOT NULL`.

Keep existing `job_type=` for tests. Extend `_claim` with `job_types: Sequence[str]` (`IN` list) plus the JSON clause **only** for those four (`jobstore.py:407-427`).

`serve`/`run_once` must pass `job_types=tuple(self.executors)` so unknown queued rows are **not** claimed and not `EXECUTOR_MISSING`-killed.

**Why not new types / purpose flags:** receipts and `idempotency_key=f"{JOB_TYPE}:{hash(payload)}"` freeze type and payload. Adding a runtime stamp would fork hashes. `purpose` is already `isolated_*` on product-shaped payloads too.

**Judgment-content leftover:** isolated content jobs always have `review_context_id`. Optional extra SQL: that id exists on `ReviewContextV2` (prepared snapshot). Isolated jobs whose context never landed in this DB stay unclaimed. Isolated jobs that used a **still-present** prepared context would be treated as product-owned — remaining overlap, not worth a new payload field.

---

### Recovery / retry / cancel — same predicate

Do **not** leave the four types in the unfiltered scans after wiring.

| Helper | Change |
|---|---|
| `requeue_due_retries` | Only rows matching the claim predicate (historical isolated `failed_retryable` stay there) |
| `mark_expired_running` + `requeue_recovering` | Same; dead isolated leases of the four types stay `running` with expired lease rather than being queued into the product worker |
| `cancel_expired_cancel_requests` | Same; do not complete isolated cancel-to-`cancelled` as a wiring side effect |
| `prepare_claimed` | Unchanged (runs only after a successful product claim) |
| `run_startup_recovery` | Pass the same type+JSON filter (or skip the four types unless `review_context_id` is set) |

Other registered types (page review, OCR, …) keep current all-of-type recovery.

Restart of a **prepared** job: same payload still has `review_context_id` → claimable; `prepare_claimed` still resets interrupted steps.

---

### Registration / intake (no second queue)

1. In `PageReviewRuntime._prepare`, construct the four executors with the **same** `routes` + `PageReviewAdmission` (`page_review_runtime.py:62-72`). Dispatch in `__call__` like search/targeted (`119-125`).
2. Add the four keys to `default_executors`, all pointing at `app.state.page_review_runtime` (same pattern as `JUDGMENT_SEARCH_JOB_TYPE`).
3. Product intake (new command/HTTP or prepare-follow-on): **always** pass `review_context_id` from `prepare_review`. Qualification already copies it from the candidate. Isolated `enqueue_*` without context stays valid and **unclaimed**.
4. Do not auto-enqueue from prepare. Do not change `JOB_TYPE` / `CONTRACT` / `purpose`.

Compatibility default: missing `review_context_id` ⇒ not product-owned. That is the historical isolated default for candidate/control/qualification.

---

### Do not

- Register executors first and “filter later in memory.”
- Claim all types then no-op unknown (already fatals them).
- Alias job types or add a payload `runtime` stamp.
- A second JobRunner/queue.
- Auto-resume isolated jobs that happen to still be `queued`.

**Limits:** no runtime of `json_extract` on live `payload_json`; leftover `judgment_content` rows whose `review_context_id` still exists in this DB would be in-scope. Not clinical acceptance.
