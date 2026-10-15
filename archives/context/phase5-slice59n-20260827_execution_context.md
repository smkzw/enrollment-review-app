# Execution Context: phase5-slice59n-20260827

Created: 2026-08-27 22:45:55
Objective: 在不扩大到全量包的前提下，对 D001 II 方案中病毒学/结核筛查这一跨章节代表组建立可重复的控制点真实重放，验证流程必做项、排除标准、条件检测、例外及随机前时间锚的来源闭包；修复必须保持通用且不得改动无关条目。
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

1. 只读核对冻结包72及其与官方排除标准、流程表的来源关系，形成逐项临床预期和停止条件，不修改临床源文件。
2. 把现有表5专用重放脚本收敛为最小可配置的代表组重放能力，复用产品 ProtocolControlAgentRunner 与发布门禁，不复制临床推理。
3. 为配置化重放、跨章节来源闭包和修复范围保护补充独立回归并审查实际模型输出；任何来源缺失、期别错配或逻辑弱化均拒绝。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
