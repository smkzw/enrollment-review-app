# Execution Context: phase5-slice58d-table-cell-phase-context-20260825

Created: 2026-08-25 19:53:59
Objective: 修复方案表格单元格内期别段落继承及数字斜杠误识别，使混合 II/III 内容按真实结构原子化且不误判普通临床数值。
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

1. 收紧通用期别词法识别，避免PGA 3/4、访视周数等数字斜杠被误识别为II/III期，同时保留真实2/3期、II/III期写法。
2. 建立同一表格单元格内明确期别段标题的窄范围上下文切换，后续段落继承最近阶段，普通叙述期别提及不得扩散。
3. 增加合成反例与真实D001只读重建核对，量化单元、待处置和批次数，检查原批次32及表5并验证源文件未变。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
