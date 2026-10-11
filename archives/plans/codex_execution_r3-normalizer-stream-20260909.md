# Codex Execution Plan: r3-normalizer-stream-20260909

Objective: Implement bounded observable GLM streaming in product normalizer transport; preserve same model, prompt and validation. No model calls or clinical data access.

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | Inspect existing GLM transport and minimal existing SSE helpers. Add GLM streaming with thought/content usage separation, strict complete finish, bounded inactivity and total limits, captured actual identity and partial failure receipt; do not accept partial output. Tests for normal completion, length, stream error and missing finish. Only app/agents/deepseek_evidence_normalizer_transport.py, a small independent helper if necessary, and focused tests. No env, clinical artifacts, other files, external inference, or sampling/effort change. Return file refs and tests. | `runs/execution/r3-normalizer-stream-20260909/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
