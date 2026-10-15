# Execution Context: phase5-slice61cb-package90-ae-causality-assessment-boundary

Created: 2026-08-30 06:48:46 CST
Objective: 为D001 II冻结计划第90包body.p1087-p1097建立模型外不良事件因果关系判断来源闭包、确定性反例门禁、专项测试和父级验收材料，保持零入排候选与相邻包所有权边界。
Task type: `finite_code_task`
Risk: `medium`
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

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 独立核对冻结方案第90包及必要相邻来源，重点审查p1095表7与p1097表9的不一致、五评价要点的综合判断关系和最小只读闭包；只读分析并提交来源建议。
2. 依据执行合同实现Package90配置、专项测试、父级检查清单和dry-run prepare，不修改共享运行器或正式矩阵；运行专项与Phase测试并报告。
3. 独立攻击Package90雏形或合同，重点构造五要点AND化/计分化、表号静默纠正、统计分组扩大、双方判断AND化、报告范围升级、严重程度/严重性/预期性混同与候选升级反例；只读审阅。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
