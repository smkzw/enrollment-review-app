# Execution Context: phase5-slice58f-phase-context-dedup-20260826

Created: 2026-08-26 00:09:35
Objective: 消除期别语义Agent提示中上下文单元的重复正文注入，在保留完整来源闭包、索引可追溯性和中文临床语义合同的前提下显著缩短真实D001批次输入，并验证技术与临床语义不回退。
Task type: `long_horizon_code`
Risk: `medium`
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

1. 只读审计当前context_units与context_packets重复渲染的合同边界，提出不丢来源、不改变身份与水合逻辑的最小压缩方案。
2. 实现上下文正文单次呈现、上下文包只保留类型与索引的通用提示压缩，并更新相关合同说明，不加入项目特异规则。
3. 更新合成回归，重建真实D001 package 32并量化提示长度、索引闭包与模型前置条件，核对MG-K10相关回归和源文件只读性。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
