# C03 targeted repair verification

Read-only same scope and restrictions as previous round. No tests, product model, app, DB, browser, delegate or source edits. Verify final changed definitions, write only named output.

P1-1: stored_inheritance now treats no-op reprocess as fallback when there is no producing upload lineage; conflicting upload lineages still fail, no cache mutation.
P1-2: inheritance loading now after processing transition; explicit retryable DB-busy vs nonretryable identity failure.
UI: failed attempt can retry same job rather than pay full new attempt; source result selection persists URL ocrSnapshot/ocrRevision and still verifies exact loaded snapshot/revision, no autoactivation. Build/other command idempotency keys now persist before POST keyed by subject/episode/action, release after confirmed result. read actual changed EvidencePage definitions for candidate scope/reload and errors. Error decoder uses existing error envelope, translate_storage_error/EvidenceAppError handler supports it.

Report whether your concrete P1 defects are source-resolved and any new concrete defect. Explicitly keep runtime/browser/clinical acceptance unverified. This is narrow repair verification, not another redesign round. LocalStorage history is intentionally retained for task recovery, no general cleanup.
