# Execution Context: phase5-slice61al-p804-source-closure-repair-20260828

Created: 2026-08-28 22:12:05
Objective: 在不写入 D001 项目特异规则的前提下，为 CONDITIONAL_EXEMPTION_SCOPE_SPLIT 建立同一来源闭包内候选合并或重写的有界修订合同；冻结不同来源候选，先完成确定性测试和父级可复核证据，不运行语义模型、不发布控制点。
Task type: `finite_code_task`
Risk: `high`
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

1. 只读审查真实 v8 第4到第5次响应、离线恢复工件和当前门禁/修订路径，给出最小通用不变量、失败模式及测试矩阵；不得修改文件。
2. 实现最小的同源候选闭包修订合同：允许获授权来源键内候选合并或重写，要求来源全集守恒，并恢复所有不同来源候选；只改共享代码和聚焦测试，不触碰临床工件。
3. 以对抗视角补充或运行确定性回归，覆盖同源合并、同源拆分、跨来源吸收、来源丢失、不同来源多候选冻结和候选乱序；核对中文提示不泄露父级金标准，不运行模型。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
