# Codex Execution Plan: phase5-slice53-evidence-normalizer

Objective: Implement only Phase 5 Slice 5.3 Evidence Normalizer and resumable persistent runs. The model may output immutable candidates and unresolved items only; deterministic Slice 5.2 gates remain authoritative. Reuse current Job/Step/Checkpoint/Lease/idempotency infrastructure. Do not publish facts/Profile, add API/UI, create ReviewRun or eligibility conclusions.

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | Implement Chinese-native Evidence Normalizer input/output contracts, compact strict JSON Schema, system prompt, runtime decoder and bounded transport adapter with structured candidate/unresolved-only output; add focused tests. Own new agent/contracts modules only. | `runs/execution/phase5-slice53-evidence-normalizer/worker_01.md` |
| `worker_02` | Implement deterministic planning from the active complete processing revision and project-effective text into logical-document calls and contiguous page groups, with stable input hashes, explicit full page closure and no cross-episode/implicit date borrowing; add focused tests. Own new planning/source-adapter modules only. | `runs/execution/phase5-slice53-evidence-normalizer/worker_02.md` |
| `worker_03` | Implement persistent normalization job definitions and executor integration by reusing existing Job/Step/Checkpoint/Lease/idempotency and Phase 5 run/call/candidate repositories; reject stale authority, late replies, empty/partial outputs and duplicate requests while preserving the prior active state; add restart/reclaim/idempotency tests. Do not publish facts/Profile or add API/UI. | `runs/execution/phase5-slice53-evidence-normalizer/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
