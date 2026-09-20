# Execution Context: phase5-slice60zz-cross-stage-supplement-contract-20260828

Created: 2026-08-28 18:51:52
Objective: 修复流程必做项在较早访视完成、但其新增结果有效窗只能在后续首次给药或基线节点最终判定时，补充关系与时间锚点门禁互相冲突的通用合同；不得写项目特例，必须用保存的病毒学失败回包和合成反例验证。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `cursor` / `cursor-cli` / `auto`
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

1. 只读分析三轮保存回包、提示合同和双重门禁，建立跨阶段补充关系的通用语义、不变量、拒绝边界及最小修复建议。
2. 实现通用跨阶段补充关系合同：仅当义务增量是后续锚点的时间有效性等后续控制时，允许受影响节点晚于流程执行节点；同步 wire 水合、发布门禁、提示词和聚焦回归，不写 D001 特例。
3. 独立用保存的三轮病毒学回包和合成正反例审查修复，验证不放宽普通同阶段补充、早期最终判定、证据到期、流程目标访视错配或其他绕过，并运行聚焦协议测试。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
