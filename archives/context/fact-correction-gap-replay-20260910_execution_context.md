# Execution Context: fact-correction-gap-replay-20260910

Created: 2026-09-10 01:01:26 CST
Objective: 合成测试复现事实修订后资料缺口丢失，不改产品实现，查清最小同源修复入口
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

- Read app/services/fact_correction_service.py, app/services/fact_normalization_executor.py, app/services/evidence_expectation_projection_service.py, app/projections/evidence_expectations.py, app/storage/fact_repositories.py, related contracts, and existing tests/v2/services/test_fact_correction_job.py and their synthetic fixtures. You may trace adjacent source/tests only as necessary. Do not read real artifacts, databases, credentials, original clinical files, home configuration, or other projects.
- ONLY writable path: tests/v2/services/test_fact_correction_gap_reprojection.py. Use apply_patch, no other edits. No product model/network calls, dependencies, cleanup, dispatch, or actual service startup. Pytest uses existing temporary test databases.
- Scope: demonstrate two suspected defects in actual _reproject_expectations/correction flow: (1) previous explicit OCR/observation-unverified risk lost, complete facts silently produce observed; (2) no coverage and no signals causes ProjectionInputError and may roll back correction. Write desired-behavior regression tests; mark strict xfail with precise known reason if still failing. Do not assert wrong behavior as correct. Prefer seeded service integration; if monkeypatching necessary, state exactly what is and is not reproduced. Run only the new file and smallest prerequisite test if needed. Do not modify implementation.
- Report how original normalization runs/unresolved items/gate records can be selected with immutable authority and correction lineage. Do not recommend blindly gathering all historical runs or carrying previous gap_type without evidence. Candidate/record supersession and multiple runs must not silently clear uncertainty. Distinguish proven test failure from inferred outer rollback. Owner will choose repair after source checks.
- This pass uses approved primary zcode/zcode/GLM-5.3-Flash:max without automatic fallback: local resources are owned by another task. Independent source-scope review already provided the hypothesis, not proof; current worker is executor only.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 仅新建tests/v2/services/test_fact_correction_gap_reprojection.py，复现非默认风险丢失导致升级和无覆盖无信号导致回滚两种情况；阅读既有修订测试和仓储，报告源运行关联及最小修复建议，不修改产品、不读真实数据

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
