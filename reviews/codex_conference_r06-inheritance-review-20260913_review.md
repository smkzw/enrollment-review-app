# Codex Conference Review: r06-inheritance-review-20260913

Date: 2026-09-13

## Verdict

Revise. R06 not closed.

## Current Integration After Same-session Rounds 2 and 3

Both continuations completed on grok/grok-build/grok-4.6 high without fallback; complete reports read. Source-only event/exposure/expectation revisions now preserve clinical content, status/gaps and original acceptance records. Direct-parent-only references, three-run Profile generation, real correction/replay and unresolved-conflict rollback pass in the 231-test focused run (100.45s). No clinical database changed; legacy 24-reference recovery remains unverified.

Round3 P1 is not a demonstrated production transaction defect: the reviewer explicitly did not inspect the caller. Owner traced fact_normalization_executor.execute_finalize -> PreparedStepResult.apply -> JobRunner._commit_step_success, which runs in session.begin() and propagates StepFailure out of that transaction. The publication service explicitly does not own commit/rollback. Do not add a savepoint only after facts are written; that would not undo earlier writes and would also interact with the runner's before_commit fence. Added a real JobRunner test that invokes actual publication, verifies the newly written fact is present, then injects FactPublicationError; persisted facts/links/expectations/Profile remain absent and the job fails. Executor/Profile suite 12 passed in7.69s. Keep the caller-owned transaction contract.

Round3 supports this narrow deterministic append path, not R06 closure. Source-only conflict revision remains unimplemented and fail-closed; any later implementation must preserve unresolved state, all members, old rows, and explicit lineage before changing Profile head selection. Additional stale/foreign/legacy-expectation negative cases remain useful test work. Full backend regression started before this last test-only addition and is tracked separately.

## Boundary Compliance

Read-only source review; runner terminal grok/grok-build/grok-4.6 high, one round, no fallback.

## Participant Outputs Reviewed

runs/conference/r06-inheritance-review-20260913/evidence_single_object.md fully reviewed.

## Conference Panel Review

Accepted findings: successor fact IDs leave prior dependent references outside Profile heads; selecting after correction filtering can select an older ancestor; original-run replay must use unfiltered published history. Explicit current increment must not use legacy empty-list fallback.

## Main-Venue Codex Review

Implemented historical replay before filtering, reject corrected latest fact instead of older inheritance, explicit nonempty increment, and same-transaction Profile closure rejection for inherited facts. Do not claim dependency cascade implemented. Source-only triple-run publication works; event-dependent inheritance is currently rejected, preserving the prior state.

## Codex Independent Verification

Pure publication/correction/Profile adjacent tests 123 passed before later guards; then 16 publication tests passed after guards, including dependent-event nested transaction rollback. First event fixture used incompatible source strength and was corrected to match its frozen objective source, not by changing production validation. Real correction and full cascade acceptance remain pending.

## Final Decision

Later affected-scope verification: 178 passed in69.43s, r06-inheritance-focused-20260913.xml. Includes real persisted FactCorrectionRepository linkage after third publication: original run replays without new rows, old corrected identity is rejected. Legacy payload hash decode covered. Continue with explicit dependent-revision rebuilding design and tests. No formal clinical acceptance; do not silently remap or drop old event/exposure/expectation references.
