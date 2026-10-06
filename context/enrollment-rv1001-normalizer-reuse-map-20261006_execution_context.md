# Execution Context: enrollment-rv1001-normalizer-reuse-map-20261006

Created: 2026-10-06 21:30:24 CST
Objective: Map existing legal normalization result reuse and its actual consumers; recommend minimal recovery for changed repair-only prompt identity, without claiming current model reads or relaxing source authority.
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Read-only bounded source map: app/services/fact_normalization_job_service.py, fact_normalization_executor.py, fact_normalization_command_service.py, fact_normalization_replay_sources.py; app/agents/evidence_normalizer.py, deepseek_evidence_normalizer_transport.py; app/storage/fact_repositories.py; tests/v2/services/test_fact_normalization_persistence.py and test_evidence_question_repair_persistence.py. At most twelve decisive complete definitions with required directly referenced contracts. Identify actual saved request/model/schema proof, same-Job versus new-run restoration, raw/draft identity and final publication consumers. Propose smallest executable plan for reuse after repair instructions changed while source and successful base answers stayed unchanged. Reject unsafe guessed compatibility. No file edits, raw clinical/tmp/env/database/history reads, shell/tests/model/browser/network or recursive dispatch. Return concise function-level map, exact missing prerequisites and discriminating negative tests via runner only; no new framework, no finished implementation claim.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
