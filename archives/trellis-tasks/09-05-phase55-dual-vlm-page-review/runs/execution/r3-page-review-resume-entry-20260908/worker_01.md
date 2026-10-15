The three service/API files are untracked phase work in this branch (the entire page-review module is new, uncommitted phase work — hence empty `git diff`), and my changes live only in them plus the new test file. Everything is verified. Final state:

# Execution Output: r3-page-review-resume-entry-20260908 - worker_01

## Boundary And Context Check

- Worked only inside the runner-bound worktree (`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`). No production paths, `.env`, `artifacts/`, clinical materials, databases, home harness config, models, servers, browsers, or local runtime services were touched. No packages installed.
- Edits confined to the four authorized paths: `app/services/page_review_job_service.py`, `app/services/page_review_runtime.py`, `app/api/v2/page_review.py`, new `tests/v2/api/test_page_review_resume.py`. Global `JobStore`/`runner` and frontend untouched; all preexisting uncommitted work preserved (those files are untracked phase work in this branch, so my edits add to the working tree without disturbing anything).
- No final visual/clinical/regulatory acceptance claimed; no conference, no peer review, no model calls.

## Work Performed

Implemented the formal, node-scoped resume entry for cancelled page-review jobs on top of the existing `JobStore.resume_cancelled`, with explicit identity gates before any state transition:

1. **`app/services/page_review_job_service.py`**
   - Extracted the frozen-payload builder from `enqueue` into a shared module function `plan_page_review_payload(session, *, subject_id, review_episode_id, routes)` — `enqueue` is behavior-identical, and resume validation reuses the exact same authority/pack/source/page/route freezing logic (no duplicated planning code).
   - New `PageReviewResumeNotReady` (409, `PAGE_REVIEW_RESUME_NOT_READY`) app error following the `PageRereadNotReady` convention.
   - New `resume_route_identity()`: entry-time comparable public-route identity. The handwriting lane's `model` id is excluded because it is resolved by the startup `/models` probe and cannot be reproduced from configuration alone; its configured `model_match` is still compared exactly, and any exact derived-model drift is still refused at run time by the executor's existing `R3_ROUTE_CHANGED` gate.
   - New `PageReviewJobService.resume()`: in one short transaction — 404 for missing job / wrong job type / cross-subject-cross-episode job ids (matches `page_review_status` scoping conventions); **no-op `changed=False`** response when the job is not `cancelled` (duplicate clicks, already resumed, completed — mirrors `request_cancel`'s no-op convention); when `cancelled`, rebuilds the fresh plan and refuses with 409 unless the frozen payload (minus `recovery`) equals it — covering active evidence authority, rule/pack identity, association sources, pages/image hashes, public routes, `execution_control`, and all five frozen execution-version fields (legacy serial jobs get the same `execution_control` allowance as `plan_page_reread`). Only then calls `JobStore.resume_cancelled(job_id)`, which keeps completed checkpoints/history untouched and does not touch failed-step retry budgets (failed jobs are not accepted here at all).

2. **`app/services/page_review_runtime.py`** — new `resume()` entry. Route identity comes from the already-prepared routes or `require_page_reader_routes(require_credentials=False)` (configuration read only, **no model calls, no preflight**, mirroring `main_reader_identity`); config errors map to the existing 503 `PAGE_REVIEW_UNAVAILABLE`. After resume, the actual run still goes through `__call__` → `_prepare()` with the normal product preflight.

3. **`app/api/v2/page_review.py`** — new route `POST /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/page-review-jobs/{job_id}/resume`, node-scoped like sibling endpoints, guarded by `require_subject_episode`, returning the existing `JobActionResponse` (job_id/state/state_label/changed).

**Concurrency decision:** duplicate clicks are safe by construction — the second click either sees the post-resume state and gets a 200 `changed=false` no-op, or (true simultaneous transactions on SQLite) fails with a translatable busy error (503 `DATABASE_BUSY`, retryable, no corruption); `resume_cancelled` re-validates state inside the same transaction, so there is a single database-level winner. No automatic resume, no silent job selection, no fresh job creation anywhere.

## Artifacts And Evidence

- `app/services/page_review_job_service.py` — planner extraction + `resume` + `PageReviewResumeNotReady` + `resume_route_identity`.
- `app/services/page_review_runtime.py` — `PageReviewRuntime.resume` (config-only verification).
- `app/api/v2/page_review.py` — resume endpoint.
- `tests/v2/api/test_page_review_resume.py` — 9 tests, all passing.

## Commands And Observations

- `.venv/bin/python -m pytest tests/v2/api/test_page_review_resume.py -q` → **9 passed**. Coverage: positive resume of a job cancelled mid-read (entry proven not to call `_prepare`; completed read receipts preserved byte-identical; completed lanes not re-read; completion → `ready`; duplicate click no-op; post-completion no-op); refusal on changed `PAGE_REVIEW_JOB_CONTRACT` (409, steps stay `cancelled`); refusal on changed main-reader `reasoning_effort`; tolerance of derived handwriting model with unchanged `model_match` + refusal when `model_match` changes; refusal on advanced episode revision (authority drift); refusal on clause-pack content drift at the same rule-set (id, revision); node scoping (foreign node/unknown id/non-page-review job → 404, job stays cancelled); cancelled targeted-review job rejected (404, two-round budget intact); 503 `PAGE_REVIEW_UNAVAILABLE` when reader config is unreadable (steps untouched).
- Regression neighbors: `tests/v2/api/test_page_review.py`, `tests/v2/services/test_page_review_job_executor.py`, `tests/v2/api/test_page_length_recovery.py`, `tests/v2/api/test_jobs_api.py` → **44 passed**; `tests/v2/services/test_page_review_execution.py` → 16 passed; `test_page_review_job_service.py` + `test_targeted_page_review_jobs.py` + `test_page_review_model_input.py` + `test_r3_page_review_normalizer_wiring.py` → 16 passed.
- `python -c "import app.api.v2.app; ..."` → imports ok. Ruff is not installed in this venv and I did not install it (boundary), so lint was not run.

## Blockers Or Missing Environment

- None blocking. Two environment notes: (1) `ruff` absent from `.venv` (not installed per boundaries); (2) `_seed_chain` does not support mixing fixture indexes in one database (FK/duplicate-subject collisions), so the cross-node test clones the fixture's subject/episode rows for the second node instead — a test-local workaround, no production impact.

## Rerun Requests Or Next Step

- One design decision for Codex to ratify: the resume entry intentionally tolerates a changed *derived* handwriting `model` id (config-only check; exact drift still refused by the executor's `R3_ROUTE_CHANGED` at run time with history preserved). Exact-entry enforcement would require a `/models` probe at the entry, which the assignment excludes for non-run operations.
- Suggested follow-up (not done, outside this pass): frontend affordance for the new resume endpoint; optional wiring of a cancelled-job recovery hint into `page_review_status` (`can_resume` field) if the UI needs a server-driven flag.
