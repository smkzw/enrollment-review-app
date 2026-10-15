# Execution Context: phase5-nextflash-resume-20260903b

Created: 2026-09-03 08:24:23 CST
Objective: 从最新无损检查点恢复 Phase 5，修复规范化作业中断后的幂等复用，合法完成 SAR 31001 筛选期与基线期事实、Patient Profile 和原始证据临床 QC，并保持项目无关合同。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> openai-codex/gpt-5.6-luna:max -> codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
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

1. 审计并最小修复 fact normalization 在已有成功 call/candidate 但 step checkpoint 缺失时重复调用模型的问题；新增恢复与幂等回归，禁止修改临床规则或运行数据。
2. 只读核对当前 SAR 31001 作业、快照、租约和配置状态，给出旧 cancel_requested 作业合法终态对账及新受控筛选/基线作业入口；不得启动长任务或修改运行数据库。
3. 只读梳理 Phase 5 31001 事实发布、事件、用药暴露、Patient Profile、原始证据临床 QC 的剩余验收路径和确定性检查；不得以流程成功替代临床验收。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
