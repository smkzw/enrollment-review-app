# Execution Context: phase5-slice58-wire-domain-parity-20260824

Created: 2026-08-24 08:23:57
Objective: 修复 oMLX 方案解构 wire 严格结构与领域合同不等价：原子定位字段互斥，NOT 与 ALL/ANY 逻辑元数精确，并以捕获的真实 D001 首批反例和通用回归证明。
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

1. 在共享 compact wire Schema 中表达 source_clause/source_clauses 互斥且至少一种定位存在，不使用项目特异逻辑，并保持 provider 兼容。
2. 将逻辑节点按 NOT 与 ALL/ANY 的不同元数约束拆分或等价表达，保持统一图身份、循环/孤儿/共享子节点校验与无损水合。
3. 增加独立 Schema 与水合回归覆盖真实反例、合法单段/多段定位、NOT=1、ALL/ANY不少于2，并运行聚焦及协议测试。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
