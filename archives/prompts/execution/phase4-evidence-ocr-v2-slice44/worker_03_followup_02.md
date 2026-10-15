You are continuing the same Pi execution session for the second WP-44C remediation. Read the current workspace state and do not undo unrelated edits.

Runner-managed report path: `runs/execution/phase4-evidence-ocr-v2-slice44/worker_03_followup_02.md`. Do not write that report file through tools; return the complete report in your final response.

The second independent fresh-context verifier rejected Follow-up 01 after executable counterexamples. WP-44D and all frontend work remain blocked. Remediate every P1 and the supporting test/architecture gaps below. Do not merely weaken claims or tests.

## 1. Build command identity and atomic idempotency

- `EvidenceApiCommandService.build_revision()` must not replay a candidate merely because its globally unique `idempotency_key` matches.
- Compare the complete normalized command identity, including scope, snapshot, base revision, scanner rule version, selected locator IDs, actor/audit identity and the submitted expected revision. A same-key different command returns `409 IDEMPOTENCY_CONFLICT` and creates no new candidate/event/history.
- Same key + the exact same original command replays after later revision advancement. A new key with stale expected revision returns a structured stale conflict.
- Candidate creation, first candidate event and the authoritative idempotency claim must be one transaction. Reuse the existing candidate input hash only if its field set exactly matches the full API command identity; otherwise use an application command record/normalized digest without altering domain contracts unless strictly unavoidable.
- Add an executable build matrix: same/same replay, same/different 409, stale new key, plus history-count assertions.

## 2. Activation and rollback single-transaction recovery

- Current code commits `EvidenceActivationService.activate/rollback()` before separately committing the API idempotency row. This was reproduced as HTTP 500 after the pointer/event committed, followed by `409 STALE_REVISION` on retry.
- Add non-committing `activate_in_session` and `rollback_in_session` application-service paths (or an equivalently clean unit-of-work API). `EvidenceApiCommandService` must own the sole outer `BEGIN IMMEDIATE` and commit event, snapshot status, candidate state, episode paired pointer/revision and idempotency claim together.
- Preserve the already accepted WP-44B atomic activation/rollback semantics. Do not duplicate activation algorithms in the API command service.
- Add deterministic fault-injection tests after each material child write and immediately before outer commit. Every injected failure must leave no activation/rollback event, no pointer/revision change, no snapshot/candidate projection change and no idempotency record. Retrying the exact command after a simulated response/commit-boundary failure must either replay the committed result or execute once; it must never return stale because of a missing idempotency record.
- Add activate and rollback matrices for same/same replay, same/different 409 and stale new key.

## 3. Referenced-document command identity and concurrency

- The create schema's `expected_revision` is currently dropped by the router/service. Pass it through and validate the owning review episode revision before any history is written.
- Define one normalized command identity policy for create/revise/confirm/dismiss/resolve/unresolve. It must include the path-owned resource/scope, every business field, audit actor and the submitted expected revision. Do not exclude actor or expected revision from the digest.
- Same key + exact same command replays; same key + any changed actor, expected revision, path resource or business field returns 409 with no history; a new key with stale episode/chain/resolution revision returns stale conflict.
- For all six command families, add parameterized or explicit executable tests for same/same, same/different and stale-new-key semantics, including immutable history counts.

## 4. Honest and isolated application conflicts

- Every write-side 409 response must contain safe, user-facing `submitted`, `current_record` and `field_diff`. Idempotency conflict may additionally include `existing_result`; pending/build/non-complete/activation-gate conflicts must include the actual current candidate/gate/revision projection and actual unresolved/failed gates where applicable.
- Compute recursive field differences from safe normalized command records; do not fabricate empty placeholders. Persist or recover enough safe first-command identity to compare meaningfully.
- Remove bottom-layer technical exception strings from user-visible contexts/details. No ORM object, internal enum object, absolute path, payload/hash, traceback or storage exception text may leak at any nesting depth.
- Application errors are owned by the application layer. API error mapping must not import re-exported storage exception classes from `evidence_api_command_service`; translate storage/service failures at the service boundary into stable application errors. Add an architecture test for this dependency direction instead of only checking literal API imports.
- Strengthen tests to recursively inspect error context and require the three common fields on every write-side 409 family.

## Already accepted and must remain unchanged

- Exact historical R1 replay of locator/scan/review/correction sets.
- Paired `ReviewEpisode` activity pointer as the only current-version authority; no `latest_effective_for_scope`, time, status, ID, ordering or legacy fallback.
- Direct `app/api/v2` AST boundary and real `ArtifactStore` threading.
- No clinical-fact/rule/ReviewRun behavior and no frontend work.

## Authorized bounded write surface

- Existing WP-44C API files, schemas, vocabulary/error mapping and API/architecture tests.
- `app/services/evidence_api_*`, `evidence_activation_service.py`, `evidence_revision_workflow.py`, `evidence_referenced_document_service.py`, and narrowly related service tests solely for transaction/idempotency/application-error closure.
- Existing idempotency/candidate/activation repositories or models only if required to make the above atomic without a router workaround; do not change domain semantics, migrations, legacy, protocol, workflow runner, frontend, clinical sources or reports.
- If a database schema change would truly be required, stop and report the precise gap instead of silently editing migration/domain contracts in this follow-up.

Run the new counterexample matrix first, then focused API/service/storage/architecture tests, full `tests/v2`, scoped Ruff, production-code Pyright with the project interpreter, and `git diff --check`. Return exact files changed, exact test counts, fault-injection evidence, residual uncertainty and a one-to-one closure table. Do not claim completion from comments or OpenAPI shape.
