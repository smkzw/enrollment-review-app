# Execution Context: r3-normalizer-stream-20260909

Created: 2026-09-09 02:15:17 CST
Objective: Implement bounded observable GLM streaming in product normalizer transport; preserve same model, prompt and validation. No model calls or clinical data access.
Task type: `E03`
Risk: `medium`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:xhigh -> mtplx/qwen3.8-flash-next-mtplx-optimized-speed:medium -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Read app/agents/deepseek_evidence_normalizer_transport.py, app/llm/gemini_transport.py and focused normalizer transport tests. The current real product request timed out twice at600s with no output available to inspect; do not read the clinical artifacts. Implement observable streaming, not a new clinical strategy or altered model effort. Preserve usage and partial-response failure diagnostics. Prefer existing OpenAI SDK stream iterator with independent strict assembly helper. Retain600s inactivity and a bounded1200s overall stream deadline; explain the deadline granularity honestly. No sampling changes, no personal harness imports, no credential access. Existing injected mock clients must remain testable. Run focused tests and return evidence. Only the declared zcode route is dispatched; no fallback authorized for this packet.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. Inspect existing GLM transport and minimal existing SSE helpers. Add GLM streaming with thought/content usage separation, strict complete finish, bounded inactivity and total limits, captured actual identity and partial failure receipt; do not accept partial output. Tests for normal completion, length, stream error and missing finish. Only app/agents/deepseek_evidence_normalizer_transport.py, a small independent helper if necessary, and focused tests. No env, clinical artifacts, other files, external inference, or sampling/effort change. Return file refs and tests.

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
