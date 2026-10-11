# Execution Context: r3-pending-retention-20260909

Created: 2026-09-09 09:44:51 CST
Objective: Implement deterministic retention of unresolved page observations alongside normalizer output without clinical inference or modifying accepted facts
Task type: `E03`
Risk: `high`
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

- Read app/projections/page_review_pending.py, page_review_pending_normalization.py, page_review_sources.py; app/domain/contracts/evidence_normalizer.py; app/services/fact_normalization_executor.py; tests/v2/services/test_page_review_visual_sources.py and focused pending fixtures under tests/v2. Follow current contracts, not old model-role prose.
- Never read artifacts, databases, credentials, raw clinical files, or home configuration; no model calls, browser, network, package installation, or broad workspace scans. Engineering source only.
- Only write NEW app/projections/pending_observations_report.py and NEW tests/v2/projections/test_pending_observations_report.py. Owner edits executor and prompt. Do not edit other files.
- Implement a pure helper which takes EvidenceNormalizerInput and returns deterministic EvidenceNormalizerUnresolvedItem records for ALL pending_page_observations (both mixed accepted/pending and pending-only pages). Use existing source-bound pending projection. Preserve exact original excerpt, raw value/text and context without clinical inference; no new facts, no direction/clinical gap categorization, no invented locator. Native Chinese message, page binding, internal stable code. Return no records for legacy/no attachment or fully accepted pages. Avoid duplicate identical reader observations only if exact identity duplicate; never merge distinct dates/objects. Consider per-page aggregated original evidence explanation rather than hundreds of UI cards; ensure all observations retained in deterministic structured serialization within reason if necessary, but explain tradeoffs and do not expose engineering keys in user text. Must retain provenance in input, not copy or mutate source.
- Tests: empty, accepted-only, mixed, same value different dates/objects, handwriting uncertainty, original unchanged, deterministic repeat. You may read further app domain/projection and tests/v2 source to construct fixtures, not unrelated directories. Run only focused pytest on new file, PYTHONPATH=. or uv run python -m pytest. Do not integrate executor. Report exact integration suggestion and limitations for owner.
- Frozen dispatch uses zcode/GLM-5.3-Flash:max only, no fallback. User sees a clinical product, not model internals. No clinical acceptance claimed.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. Bounded pending retention helper and focused tests; owner integrates executor

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
