Continue same engineering advisory session, zcode/GLM-5.3/max, no fallback. Read-only code review, no writes, models, tests, database, browser, application imports, network or delegation. Output complete report with source lines and concrete corrections. Owner acceptance remains separate; no clinical acceptance.

Decisions: same project only; strictly sequential member workflows; completed/failed_final/cancelled members are recorded and next member proceeds; creation/context/config failure stops orchestration visibly; no auto-publication. Batch-specific workflow payload ownership isolates cancellation; ordinary single workflow refuses a simultaneously active differently-owned workflow on same context. Max50. Existing per-member retry remains available separately, batch retry only failed orchestration. No new queue or migration. New backend implementation exists but has not run.

Review complete affected definitions:
- app/services/batch_review_workflow.py
- app/services/batch_review_view.py
- app/services/prepared_review_workflow.py enqueue_review_workflow modification
- app/api/v2/batch_reviews.py
- app/api/v2/app.py batch registration, cancel callback, maintenance composition, retry mapping.
Use existing JobStore/JobService/recovery/ownership/prepared-intake source as needed. Check correctness deeply: lease cancellation race, crash after child creation, duplicate workflows, checkpoints, no accidental clinical completion, no blocking single-member continuation, config unavailable cancellation, read API source identity. Frontend not yet attached; no claim of feature completion. Identify required fixes vs scope expansion. Don't merely repeat earlier recommendations or approve based on compilation.
