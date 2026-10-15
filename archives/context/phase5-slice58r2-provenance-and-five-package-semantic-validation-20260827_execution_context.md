# Execution Context: phase5-slice58r2-provenance-and-five-package-semantic-validation-20260827

Created: 2026-08-27 00:46:02
Objective: 修复限定包执行映射与检查点可能互相矛盾的持久化缺陷，随后在隔离目录中为D001当前第67、78、79、80、111包建立可审计的真实语义验证前置条件；保持claims_complete=false，不扩大到其余包、受试者或前端。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
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

1. 在授权脚本和测试内修复既有包映射与丢失检查点场景的前置冲突核验，确保冲突选择不写入新检查点；补充决定性反例并运行聚焦回归。
2. 只读核查当前产品内置期别语义模型配置、oMLX运行入口、健康与模型身份验证方法、实际执行参数及速度质量测量字段，输出最小可复现实行命令，不调用模型。
3. 只读复核五个受影响包的临床主题、直接来源与标题族边界，形成真实模型输出的逐包验收矩阵；明确历史第79包只能人工对照且不得机械复用，识别此前执行报告中的过度结论。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
