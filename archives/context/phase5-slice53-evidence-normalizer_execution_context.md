# Execution Context: phase5-slice53-evidence-normalizer

Created: 2026-08-23 03:27:00
Objective: Implement only Phase 5 Slice 5.3 Evidence Normalizer and resumable persistent runs. The model may output immutable candidates and unresolved items only; deterministic Slice 5.2 gates remain authoritative. Reuse current Job/Step/Checkpoint/Lease/idempotency infrastructure. Do not publish facts/Profile, add API/UI, create ReviewRun or eligibility conclusions.
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. Implement Chinese-native Evidence Normalizer input/output contracts, compact strict JSON Schema, system prompt, runtime decoder and bounded transport adapter with structured candidate/unresolved-only output; add focused tests. Own new agent/contracts modules only.
2. Implement deterministic planning from the active complete processing revision and project-effective text into logical-document calls and contiguous page groups, with stable input hashes, explicit full page closure and no cross-episode/implicit date borrowing; add focused tests. Own new planning/source-adapter modules only.
3. Implement persistent normalization job definitions and executor integration by reusing existing Job/Step/Checkpoint/Lease/idempotency and Phase 5 run/call/candidate repositories; reject stale authority, late replies, empty/partial outputs and duplicate requests while preserving the prior active state; add restart/reclaim/idempotency tests. Do not publish facts/Profile or add API/UI.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
