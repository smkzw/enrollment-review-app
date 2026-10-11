Delegated mode. Continue the same bounded execution session. Do not start a conference or claim final acceptance.

# Targeted correction after Codex review

Your first pass made subject create/delete operable, but Codex rejects it as incomplete because a newly created subject has no review episodes and therefore cannot reach the evidence workspace. Fix the shared contract, not a fixture-specific path.

## Required behavior

1. Creating a subject for a formally published project must atomically instantiate one `ReviewEpisode` for every published `WorkflowStage` whose `review_required` is true, using the project's current published RuleSet revision, study phase and protocol version.
2. Preserve workflow-stage identity. Multiple visit instances may share the same broad `ReviewStage`; they must remain separate episodes. Add the minimum durable field/API projection required to carry `workflow_stage_id` and show the workflow stage's native Chinese display name/visit window in the catalog. Legacy fixtures must remain readable.
3. A newly created episode has no legacy Phase 2/3 evidence snapshot. Correct the domain/database contract so `ReviewEpisode.evidence_snapshot_id` may be null; do not fabricate a placeholder snapshot or sentinel ID. Add an append-only migration after current head and migration tests, including upgrade/downgrade/data-integrity behavior.
4. Subject deletion may atomically delete auto-created empty episodes plus the subject. Refuse with Chinese `409` recovery when any episode has legacy evidence, an active V2 pointer, any V2 evidence snapshot/candidate, or any dependent clinical/audit content. Never delete immutable evidence. Double-delete and cross-project remain 404.
5. Add a direct Chinese entry from successful protocol publication to the subject catalog with that project preselected.
6. Keep failure input and recovery behavior. Remove the new narrow/mobile media query: this product targets maximized desktop 1080P through 4K only. Do not add login/ownership, Phase 5 facts/Profile, eligibility judgments, project-specific rules, or clinical conclusions.

## Verification

Add deterministic backend/API/frontend tests for atomic subject+episode creation, multiple same-stage visit instances, transaction rollback, empty deletion, deletion refusal after evidence, API DTO labels, and post-publish/catalog flow. Run focused tests first, then the relevant full V2/frontend suites, type/build/lint checks available in the project. Record exact results and any unresolved boundary.

Return the complete execution report; the runner owns `runs/execution/phase4-real-project-entry-20260821/worker_02.md`.
