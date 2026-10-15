# Execution Context: phase5-slice51-authority-contracts

Created: 2026-08-22 21:47:56
Objective: Active task: .trellis/tasks/08-22-phase5-clinical-facts-profile. Implement only Phase 5 Slice 5.1 authority contracts and persistence foundation. New v2 facts must bind the active Phase 4 evidence snapshot and complete processing revision; candidate and published contracts stay separate; legacy placeholder tables remain read-only. Do not add model calls, clinical gates, API, frontend, eligibility conclusions, ReviewRun, ActionRequest, or project-specific logic.
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `AGENTS.md` and `.trellis/workflow.md`: project and task workflow boundaries.
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`: approved Phase 5 requirements, technical design, and slice order.
- `.trellis/spec/backend/{index.md,database-guidelines.md,persistent-jobs.md,error-handling.md,quality-guidelines.md}` and `.trellis/spec/guides/{index.md,cross-layer-thinking-guide.md}`: coding and verification requirements.
- `app/domain/contracts/`, `app/storage/models.py`, `app/storage/repositories.py`, `app/storage/evidence_*`, and migrations through `0012`: current implementation authority and reusable Phase 4 patterns.
- `tests/v2/`: current deterministic regression patterns. Do not read raw clinical material or paths outside this worktree.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. Implement Phase 5 candidate/published domain contracts, authority tuple, partial-date/source-strength/assertion/duration types, and focused contract tests. Do not edit persistence files.
2. Implement migration 0013 and ORM records for normalization runs/calls/gate results, facts/events/exposures/conflicts/locator links/rule links/expectations/Profile revisions; add migration and schema tests. Do not edit domain contracts or repositories.
3. Implement v2 repositories and authority validators that reject legacy snapshot IDs, inactive/unpaired episode pointers, non-complete revisions, cross-episode locator references, and stale episode revisions; add focused repository tests. Reuse existing canonical payload and repository patterns.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## Required Worker Preparation

Before editing, read the active task PRD/design/implement files and the backend spec index plus the specific guideline files relevant to the assignment. Reuse existing contract, canonical payload, migration, and repository patterns. Run focused tests for the files changed; do not claim the slice complete from a narrow test alone.
