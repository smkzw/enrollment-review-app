# Execution Context: phase5-slice58-reference-free-wire-implementation-20260824

Created: 2026-08-24 10:01:26
Objective: 将连续真实失败的 oMLX 引用图紧凑输出替换为 versioned dnf-v1 无引用结构，在不改变正式领域表达式和三值评估器的前提下，实现严格 Schema、确定性水合、系统所有身份、显式复杂度和旧合同拒绝，并通过真实项目之前的全面自动回归。
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

1. 实现 dnf-v1 provider 严格 Schema 与中文原生提示合同，候选和修订输出统一迁移，删除模型侧节点引用与正式 predicate 身份。
2. 实现 dnf-v1 确定性解析和水合，包括原子否定、来源/单位/时间保真、系统生成稳定身份、重复/空组/复杂度/旧图字段显式拒绝。
3. 迁移并补充 Schema、解析、水合、三值等价、候选与修订、v6-v9 反例和旧合同拒绝测试，运行聚焦及完整协议回归。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
