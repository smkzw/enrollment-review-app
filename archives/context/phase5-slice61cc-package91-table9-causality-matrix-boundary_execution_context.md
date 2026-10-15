# Execution Context: phase5-slice61cc-package91-table9-causality-matrix-boundary

Created: 2026-08-30 07:19:00 CST
Objective: 依据执行合同，为 D001 II 当前冻结计划第91包 body.t14.r0-r7 建立最小模型外来源闭包、确定性结构/语义回归与可恢复 dry-run prepare；保持零入排候选、合并单元格和符号原义，不调用临床语义模型。
Task type: `finite_code_task`
Risk: `high`
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

1. 实现者：核对冻结计划、现有结构产物及相邻包边界，创建 Package91 配置和父级检查清单；只写执行合同允许路径。
2. 验证者：创建 Package91 确定性测试与 dry-run prepare，覆盖合并单元格错位、符号互换、未知状态阴性化、计分/多数表决/单项充分化和候选升级；只写执行合同允许路径。
3. 攻击审阅者：独立核对真实表格结构、五级列和符号语义，查找配置/测试可绕过点及相邻包吞并风险；不得修改冻结来源或共享运行时，报告可复现证据。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
