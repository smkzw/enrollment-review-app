# Codex Execution Plan: phase5-slice51-authority-contracts

Objective: Active task: .trellis/tasks/08-22-phase5-clinical-facts-profile. Implement only Phase 5 Slice 5.1 authority contracts and persistence foundation. New v2 facts must bind the active Phase 4 evidence snapshot and complete processing revision; candidate and published contracts stay separate; legacy placeholder tables remain read-only. Do not add model calls, clinical gates, API, frontend, eligibility conclusions, ReviewRun, ActionRequest, or project-specific logic.

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | Implement Phase 5 candidate/published domain contracts, authority tuple, partial-date/source-strength/assertion/duration types, and focused contract tests. Do not edit persistence files. | `runs/execution/phase5-slice51-authority-contracts/worker_01.md` |
| `worker_02` | Implement migration 0013 and ORM records for normalization runs/calls/gate results, facts/events/exposures/conflicts/locator links/rule links/expectations/Profile revisions; add migration and schema tests. Do not edit domain contracts or repositories. | `runs/execution/phase5-slice51-authority-contracts/worker_02.md` |
| `worker_03` | Implement v2 repositories and authority validators that reject legacy snapshot IDs, inactive/unpaired episode pointers, non-complete revisions, cross-episode locator references, and stale episode revisions; add focused repository tests. Reuse existing canonical payload and repository patterns. | `runs/execution/phase5-slice51-authority-contracts/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

- Inspect every changed file and compare it with Phase 5 PRD/design, not only worker reports.
- Verify migration upgrade/downgrade, ORM metadata parity, immutable authority tuple, candidate/publication separation, no legacy read path, and focused counterexamples.
- Run repository-wide backend regression only after all three work items are integrated.
- Run `audit-execution`, record actual routes/sessions, then use a fresh independent checker before accepting Slice 5.1.
- This slice has no UI or rendered surface; browser/visual acceptance remains blocked until the Profile slice.
