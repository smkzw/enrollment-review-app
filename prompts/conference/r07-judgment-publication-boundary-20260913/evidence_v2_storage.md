# Formal V2 review: resolve the physical storage boundary

Continue approved read-only session 9a3a54fb-4f70-4e12-95c4-9e1d6c20bcd5. No edits, tests, services, external requests, raw clinical data, credentials or delegation. Return the report as final text for the runner. Codex integrates.

New decisive source evidence after your previous review: ReviewRunRecord, AssessmentCandidateRecord and FinalAssessmentRecord in app/storage/models.py all have evidence_snapshot_id foreign keys to legacy evidence_snapshots. _check_run_scope and _check_assessment_scope in app/storage/repositories.py also enforce legacy episode/run snapshot identities. A context-only amendment cannot implement a V2 formal review. Do not repeat the previous context-only proposal as sufficient.

Read those complete definitions, ActionRequestRecord and ActionRequestRepository, app/domain/contracts/review.py, app/domain/contracts/context.py, existing publication functions and the current V2 eligibility projection. Read .trellis/spec/backend/database-guidelines.md. Follow narrow adjacent migration/publication references if needed; no broad repository dumps.

Choose and justify the smallest complete migration approach: versioned dual-snapshot support in the existing review/assessment/action chain versus a separately versioned V2 formal chain. Prefer reuse of existing transitions, publication invariants and historical readers, but never fake a V2 ID as a legacy snapshot or synthesize legacy evidence. Identify physical FK/check changes, contract version/discriminant, canonical byte compatibility, scope/history checks and the minimal ordered implementation set. Do not propose a new workflow engine or copy the evaluator. Domain code must stay SQLAlchemy-free. Distinguish an unresolved completed review from approved enrollment.

The new exact get_entry(summary_id, authority=...) in judgment_search_repository.py binds existing summary identity/hash and row mirrors; it is provenance, not proof. Formal context must verify originating job/receipts and exact frozen references, never reselect latest at publication. Positive semantic predicate binding is still not authorized for automatic acceptance. Report incomplete facts honestly, not by forcing verdicts.

Focus on a concrete bounded storage decision the owner can implement, with file:line evidence and affected consumers. Latest user defers staged tests until overall construction; do not run tests or ask for a new test round. No product model changes. Prior conference findings remain evidence, not instructions.
