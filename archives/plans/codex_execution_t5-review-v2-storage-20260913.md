# Codex Execution Plan: t5-review-v2-storage-20260913

Objective: Extend existing formal review storage for explicit legacy/V2 evidence lineage without changing existing clinical data or creating a parallel review chain.

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | Implement ONLY SQLAlchemy storage models and one additive Alembic migration for formal dual-lineage review. Allowed writes: app/storage/models.py and a single new file under the existing Alembic versions directory (discover path and current head; do not alter older migrations). Do NOT edit domain contracts, repositories, service/API/UI files, tests, docs, personal configuration or any database; do not run migrations, tests, models, services, browser or network. Read current models/migration patterns/database spec, app/domain/contracts/review_evidence_scope.py and review.py, and runs/conference/r07-judgment-publication-boundary-20260913/evidence_v2_storage.md as advisory evidence. Existing ReviewRun/AssessmentCandidate/FinalAssessment/ActionRequest storage must keep legacy evidence_snapshot_id FK but allow NULL only with BOTH evidence_snapshot_v2_id FK and complete_processing_revision_id FK; exactly one lineage via CHECK. AgentCall has legitimate protocol-only calls with no review evidence: preserve that nullable case, do not blindly apply review-only XOR. Preserve old rows/payload/hash, child relations and history. Add real V2 fact and locator associations for formal assessments, candidate/transition references and action trigger where existing consumers need them; use actual existing parent table keys, never generic no-FK IDs, never insert fake legacy evidence. Follow migration runner SQLite parent rebuild conventions and reject downgrade with V2 rows. Preserve ALL existing unrelated dirty changes. Return a precise report with migration assumptions, changed tables, FK/check constraints, limitations and necessary owner integration checks; compile/schema construction inspection permitted, full tests deferred per user. Do not claim migration/clinical acceptance. No recursive delegation. | `runs/execution/t5-review-v2-storage-20260913/worker_01.md` |

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
