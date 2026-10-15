我将作为独立验收者进行 Phase 2 验收。首先读取起始文件并启动浏览器探索。

让我启动浏览器探索UI和API，同时运行测试。

我需要继续读取更多文件来完善验收分析，同时检查是否可以通过其他方式运行测试。

Trellis SessionStart ✓

Continuing the Phase 2 acceptance review. I need to read the migration files and remaining test coverage, then attempt live verification.

I have completed the code review for Phase 2. However, I must inform you of a blocker first.

**Blocker: Live verification unavailable**
Both `Bash` (for running tests and checking services) and `WebFetch` (for browser/API exploration) are denied in this non-interactive session. I was unable to:
- Run the test suite (`pytest tests/v2/`)
- Access `http://127.0.0.1:4173` or `http://127.0.0.1:8912/openapi.json`
- Verify live service status on ports 4173/8912

My review below is based entirely on static code analysis and test code reading. I recommend running the full test suite manually before final sign-off.

---

## Phase 2 Acceptance Review: SQLite Domain Layer & Persistent Jobs

### Verdict: 结论：ACCEPT（附 P2 观察项）

The implementation demonstrates a sound architecture with extensive test coverage. I found **no P1 (critical) issues** that would cause data loss, deadlock, or unrecoverable corruption. The design correctly implements: WAL + PRAGMA contracts, atomic event sequencing, lease-based execution with generation checks, checkpoint-aware recovery, idempotency with canonical hash, optimistic concurrency with field diff, stale tracking with ReviewRun-scoped closure, SSE resume with `after_seq`, migration backup/integrity/rollback, Chinese error envelopes, write boundary protection, and honest frontend prototype disclaimers.

---

### Findings

#### P2 — Significant (should fix in Phase 3 or follow-up)

**1. Recovery event progress is stale**
- **File:** `app/workflow/jobstore.py:948-1011` (`_reset_interrupted_steps`)
- **Issue:** When recovery marks a running step as `completed` from its Checkpoint, the emitted `STEP_COMPLETED` event uses `progress_completed=job.progress_completed`, which is the **old** value (before counting the recovered step). `_sync_progress` updates the job row only after the event is appended.
- **Impact:** SSE clients will see a progress value that doesn't reflect the recovered step (e.g., 1/2 when it should be 2/2), causing the progress bar to stall or jump later.
- **Evidence:** Code trace in `_reset_interrupted_steps` vs. `complete_step` (which counts completed steps before emitting the event).

**2. `_sse_stream` blocking sleep risks thread pool exhaustion under concurrent subscriptions**
- **File:** `app/api/v2/jobs.py:251`
- **Issue:** The sync generator calls `time.sleep(poll_interval)` in a `while True` loop. FastAPI runs sync generators in a thread pool. If many clients hold SSE connections, threads are blocked.
- **Impact:** For a single-user local app this is likely acceptable, but it is a scalability boundary that should be documented or converted to an async generator.
- **Evidence:** `time.sleep(poll_interval)` inside `_sse_stream` with no async yield.

**3. `finish_failure` lacks a terminal job-level event**
- **File:** `app/workflow/jobstore.py:698-713`
- **Issue:** `finish_success` emits a `COMPLETED` event, but `finish_failure` does not emit any job-level terminal event (there is no `FAILED_FINAL` event type in the enum). The SSE stream relies on polling `snapshot.state` to emit `done`.
- **Impact:** Event log consumers must infer final failure from step events rather than a definitive terminal event. Inconsistent with the success path.
- **Evidence:** `JobEventType` enum lacks failure terminal type; `finish_failure` calls `session.flush()` without `append_event`.

#### P3 — Minor

**4. `Last-Event-ID` header typing is strict**
- **File:** `app/api/v2/jobs.py:163`
- **Issue:** `last_event_id: int | None = Header(..., ge=0)` expects an integer. While browsers send the last `id:` value, some proxies or clients might send an empty string or non-integer, triggering a 422 instead of graceful ignore.
- **Impact:** Low; standard EventSource usage is fine.

**5. `retry_not_before` in migration 0003 is nullable without default**
- **File:** `app/storage/migrations/versions/0003_job_retry_schedule.py:24`
- **Issue:** The added column is `nullable=True` with no default. Existing rows will have `NULL`, which is handled correctly by the code (`retry_not_before is None` means "no delay"), but a schema-level default would be more explicit.
- **Impact:** None on correctness; purely defensive.

---

### Verified Areas (positive)

| Area | Evidence | Assessment |
|------|----------|------------|
| **Migration failure recovery** | `app/storage/migrate.py:318-341`, `tests/v2/storage/test_migrations.py:254-318` | Backup + integrity check + auto-rollback on failure; first-migration partial cleanup confirmed. |
| **First-failure half-products** | `migrate.py:321-334` (unlink partial DB), test `test_failed_first_migration_removes_partial_database` | Partial DB removed if first migration fails. |
| **Version/scope foreign keys** | `0002_domain_schema.py:191-195` (composite FK `rule_set_id` + `revision`), `job_steps` composite PK `(job_id, step_id)` | Composite keys enforced at DB level. |
| **Canonical hash** | `app/storage/codecs.py`, `app/storage/idempotency.py`, `tests/v2/storage/test_idempotency.py:79-81` | `canonical_hash` == `request_hash`; deterministic ordering. |
| **Revision conflicts & diff** | `app/storage/concurrency.py`, `tests/v2/storage/test_optimistic_concurrency.py:41-77` | Two-session race detected; field diff envelope returned. |
| **Idempotency conflicts** | `app/storage/idempotency.py`, `tests/v2/storage/test_idempotency.py:40-65` | Same scope+key with different hash raises `IdempotencyConflict`. |
| **Stale closure** | `app/storage/staleness.py`, `tests/v2/storage/test_staleness.py:50-87` | `close_covered` with ReviewRun ID; partial closure works. |
| **Dependency cycles** | `app/services/job_service.py:153-187`, `tests/v2/api/test_jobs_api.py:60-83` | DFS cycle detection rejects job creation with 422. |
| **Atomic event sequences** | `app/storage/repositories.py` (`append_event` uses `UPDATE ... RETURNING`), `tests/v2/workflow/test_runner.py:52-73` | `(job_id, seq)` monotonic; same transaction as step state. |
| **Long task lease renewal** | `app/workflow/runner.py:225-272`, `tests/v2/workflow/test_runner.py:212-236` | Heartbeat thread renews every `ttl/3`; recovery scan doesn't steal during execution. |
| **Process interruption recovery** | `app/workflow/recovery.py`, `tests/v2/workflow/test_recovery.py:51-80` | Checkpoint-aware: completed if checkpoint exists, else requeued or failed_final based on budget. |
| **SSE reconnection** | `app/api/v2/jobs.py:158-184`, `tests/v2/api/test_sse.py:29-67` | `after_seq` + `Last-Event-ID` resume; no duplicates; disconnect doesn't modify job. |
| **UTC timestamps** | `app/api/v2/jobs.py:38-44` (`_as_utc`), tests assert `.endswith(("Z", "+00:00"))` | All API timestamps normalized to UTC. |
| **Chinese error messages** | `app/api/v2/errors.py`, `tests/v2/api/test_error_envelope.py` | No SQL/stack/enum leakage; stable codes; recovery actions present. |
| **Write boundary** | `app/storage/boundaries.py`, `tests/v2/test_architecture_boundaries.py` | V2 cannot write to `projects/`; hard/symlink crossing rejected. |
| **Frontend synthetic data honesty** | `frontend/src/pages/TodayPage.tsx`, `frontend/src/api/stubRepository.ts` | `UI_PHRASES.prototypeOnly` displayed; stub explicitly marked non-persistent. |

---

### Unverified Items

These require live execution or manual confirmation:

1. **Full test suite pass rate** — I could not run `pytest tests/v2/`.
2. **End-to-end job lifecycle** — Creating, cancelling, retrying a job via the live API.
3. **SSE reconnection under load** — Browser disconnect/reconnect with `Last-Event-ID`.
4. **Migration rollback on real corruption** — Injecting a failing migration and verifying backup restore.
5. **WAL file growth** — Long-running usage could accumulate `-wal` files if checkpoints are infrequent.

---

### Recommendation

**Accept Phase 2** for merge. Address P2 item #1 (recovery event progress accuracy) in the next iteration or Phase 3, as it directly impacts user-visible progress indicators. Run the full test suite and a manual API walkthrough before closing the task.
