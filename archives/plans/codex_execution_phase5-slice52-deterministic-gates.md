# Codex Execution Plan: phase5-slice52-deterministic-gates

Objective: Implement only Phase 5 Slice 5.2 deterministic candidate gates on structured fixtures. Validate page coverage, authenticated locator and text hash closure, polarity/assertion, value-unit/date/source semantics, scoped OCR risks, exact deduplication and unresolved conflicts. Persist per-candidate accepted/rejected outcomes and affected scope. Do not call a model, publish facts/Profile, add API/UI, create eligibility conclusions, or add project-specific logic.

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | Implement gate-domain contracts and pure deterministic validators for polarity/assertion, value/unit, partial date bounds, record time, source derivation inputs, and candidate-reference closure; add focused tests. Limit edits to new Phase 5 gate modules/contracts/tests and coordinate with existing facts contracts. | `runs/execution/phase5-slice52-deterministic-gates/worker_01.md` |
| `worker_02` | Implement Phase 4 evidence closure adapter for run/call page coverage, authenticated current-revision locator verification, effective-text/hash matching, and candidate-scoped blocking OCR risk checks; add focused repository-backed tests. Do not edit fact publication repositories. | `runs/execution/phase5-slice52-deterministic-gates/worker_02.md` |
| `worker_03` | Implement deterministic batch gate orchestration for stable exact-duplicate grouping, semantic conflict detection without winner selection, per-candidate outcomes/affected scope, and failure behavior for empty output or incomplete page coverage; add property/counterexample tests. Do not publish facts or create Profile revisions. | `runs/execution/phase5-slice52-deterministic-gates/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Accepted for Slice 5.2 only. Codex inspected the integrated contracts, deterministic gates,
repository closure, stable identities and migrations; ran focused and complete V2 regressions;
and required a fresh Trellis verifier after the immutable `0014` migration was added. This
acceptance does not authorize model calls, fact publication, Profile generation, API/UI,
ReviewRun, eligibility conclusions or real-project UAT.
