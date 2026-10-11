# Execution Context: phase5-slice61by-package87-death-overdose-medication-error-boundary

Created: 2026-08-30 05:43:04 CST
Objective: 依据执行合同，为 D001 II 冻结计划 Package 87 body.p1074-p1083 建立模型外来源闭包、确定性反例门禁与可恢复准备产物；严格区分死亡结果与事件术语、药物过量/给药错误定义及双表记录逻辑，不发布控制点或触及受试者与前端。
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

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读核对冻结来源、标题与语义层级、前后包所有权及死亡结果/事件术语、过量/给药错误、双表记录的原文边界，输出紧凑来源报告。
2. 仅在执行合同允许路径新增 Package87 配置、专项测试、父级清单并运行模型外 dry-run，复用 Package86 最小模式，不修改共享运行器或正式矩阵。
3. 独立只读反例挑战：攻击死亡结果与独立事件混同、通常一项绝对化、不明死因替换、猝死限定、漏服错归给药错误、过量定义增删条件、双表逻辑互斥化及 Package86/88/93 吞并，输出可验证问题。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
