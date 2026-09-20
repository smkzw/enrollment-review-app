# Execution Context: phase5-slice60zw-candidate-action-semantic-coverage-20260828

Created: 2026-08-28 18:26:40
Objective: 建立项目无关的候选义务动作覆盖证明合同：冻结来源动作若未被流程目录覆盖，只有在其他控制候选的义务陈述逐项保留该动作且来源闭包正确时才可通过；先用保存响应和合成反例离线验证，不调用产品模型、不发布控制点。
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

1. 只读审查现有动作冻结、流程目录动作覆盖和候选水合结构，提出最小通用门控位置、错误范围与误报边界；不得修改文件。
2. 实现候选义务动作覆盖证明及聚焦回归，复用共享动作语义检测，不写 D001 专属词句或项目编号，不调用模型，不发布。
3. 独立对保存的 60zv 响应和合成候选进行对抗核验，验证仅改 disposition 不能绕过、逐项动作都必须进入义务陈述、来源摘录不能冒充义务表达；不得修改实现文件。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
