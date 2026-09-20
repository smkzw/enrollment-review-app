# Execution Context: phase5-slice61bz-package88-ae-severity-assessment-boundary

Created: 2026-08-30 06:01:35 CST
Objective: 依据执行合同，为 D001 II 当前冻结计划 Package 88 body.p1084-p1086 建立模型外来源闭包、确定性反例门禁与可恢复准备产物；严格保留 CTCAE 6.0 与方案/表8回退层级，分离严重程度与 SAE 严重性，不发布控制点或触及受试者与前端。
Task type: `finite_code_task`
Risk: `low`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy-cli/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `glm-5.3-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Parent execution contract: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61bz-package88-ae-severity-assessment-boundary-execution-contract.md`.
- Current authoritative frozen plan: `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`, plan id `papl-40b1237a22e538a278b4fd5e`, package 88 id `pap-c83571533332e92881f82dd1`.
- The execution contract declares the only writable paths and the exact owned/read-only source boundary. Every worker must read it before additional exploration or edits.
- Historical package plans are read-only counterexamples, not authority for this execution.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读核对当前冻结来源、标题层级、前后包所有权、CTCAE 版本与未收录事件回退语义，输出紧凑来源报告。
2. 仅在执行合同允许路径新增 Package88 配置、专项测试、父级清单并运行模型外 dry-run，复用 Package87 最小模式，不修改共享运行器或正式矩阵。
3. 独立只读反例挑战：攻击 CTCAE 版本漂移、可参考义务强弱反转、未收录事件回退顺序、表8提前拥有、严重程度与 SAE 严重性混同、相邻包吞并和候选升级。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
