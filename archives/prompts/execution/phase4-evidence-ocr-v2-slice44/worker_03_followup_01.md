You are continuing the same Pi execution session for WP-44C remediation. Read the current workspace state and do not undo unrelated edits.

Runner-managed report path: `runs/execution/phase4-evidence-ocr-v2-slice44/worker_03_followup_01.md`. Do not write that report file through tools; return the complete report in your final response.

The independent fresh-context verifier rejected the first WP-44C pass. Remediate every item below before claiming completion. This is an authorized, bounded reopening of the specific WP-44A/B public-contract gaps exposed by WP-44C; WP-44D and all frontend work remain blocked.

Required fixes:

1. Thin API boundary
- Move page/revision/referenced-head reads, gate summaries, idempotent command orchestration and activation replay out of `app/api/v2/evidence_processing.py` into public application services.
- API modules may import domain contracts, application services, API schemas/vocabulary and FastAPI only. They must not import SQLAlchemy, storage models, storage repositories or `IdempotencyRepository`.
- All complete-revision/locator reads and builds must receive the real `ArtifactStore`; do not instantiate a builder/query path without it.
- Add an AST architecture test that fails if `app/api/v2` imports SQLAlchemy or `app.storage`.

2. Exact historical replay
- When a processing revision is requested, return only the risk scans, risk reviews, corrections and locators frozen by that complete revision and belonging to the requested page.
- A later scan/review/correction/locator must never appear when replaying R1. Add explicit R1-then-later-artifact regression tests for every sidecar category.

3. Idempotency and optimistic concurrency for every write
- Correction, risk review, build, activate, rollback, referenced-document create/revise/confirm/dismiss/resolve/unresolve must use a stable idempotency key.
- Same key + same normalized request replays the original result even after the episode/head revision advances. Same key + different request must return 409 and create no new history. New requests then check their expected revision/head revision.
- Add required expected revision fields appropriate to the owned mutable chain. Do not simulate concurrency only in the router; the application service owns it atomically.
- Add tests for same-key/different-request, replay after later revision, and two-tab stale submission for each command family.

4. Honest 409 contexts
- Every write-side 409 must carry structured `submitted`, `current_record` and `field_diff`; pending review and gate failures must additionally list the actual unresolved/failed gates.
- Do not expose ORM objects, enums, absolute paths, hashes not needed by the user, or technical exception text.
- Add behavior tests for idempotency conflict, stale revision, pending review, non-complete revision and activation gate failure.

5. Remove forbidden current fallback
- `EvidenceSnapshotRepository.latest_effective_for_scope()` must no longer select current/effective data by ACTIVE status, created_at, ID or list order. Replace it with a pointer-authoritative API that takes/loads the review episode and validates the paired pointer, or remove it and migrate all callers.
- Tests must cover pointer null while ACTIVE rows exist, multiple ACTIVE rows, reversed/equal timestamps and shuffled IDs. Legacy `evidence_snapshot_id` remains ignored.

6. Test and static quality
- Replace OpenAPI claims of append-only behavior with actual persistence-history assertions; OpenAPI tests remain shape-only.
- Fix the scoped Pyright error in the modified `errors.py`; zero production-code errors are required.
- Keep all user-visible text native Chinese and do not add frontend, clinical-fact, rule or ReviewRun behavior.

Authorized write expansion for this remediation only:
- Existing WP-44C API files and API tests.
- New or existing `app/services/evidence_*` application/query/command services and focused `tests/v2/services/test_slice44_*` tests.
- `app/storage/evidence_repositories.py` and its focused storage tests solely to eliminate the forbidden current fallback.
- `tests/v2/test_architecture_boundaries.py` for the API dependency gate.
- No domain contract, migration, workflow runner, frontend, legacy, protocol, clinical source or report changes.

Run focused API/service/storage/architecture tests, full `tests/v2`, scoped Ruff, production-code Pyright and `git diff --check`. Return a complete execution report with exact files changed, commands, results, residual uncertainty, and a one-to-one closure table for the six verifier findings.
