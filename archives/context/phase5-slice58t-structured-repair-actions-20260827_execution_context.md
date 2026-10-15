# Execution Context: phase5-slice58t-structured-repair-actions-20260827

Created: 2026-08-27 07:41:17
Objective: 将真实D001第36、60、78包暴露的结构化期别问题转为通用修复动作，不降低来源和期别门禁，并为失败包重跑建立可验收合同
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

1. 仅修改期别语义修复提示：针对成对规则来源被忽略、目标相关支持缺失、证据摘录非逐字三类结构化问题生成通用定向修复要求，不加入D001特异规则
2. 仅增加独立回归：验证三类问题的修复提示要求完整批次回显、成对来源比较、目标自身/同义务来源绑定和逐字摘录，不改生产代码
3. 只读复核slice58s第36、60、78、121包的原文、门禁问题和临床边界，提出父级重跑验收要点，不修改应用代码或临床源文件

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
