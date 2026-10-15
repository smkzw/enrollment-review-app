# Execution Context: phase5-slice58g-phase-rationale-quality-20260826

Created: 2026-08-26 00:45:51
Objective: 建立期别语义Agent理由完整性与处置一致性的通用质量门，使含中文但语义残缺或未说明本期、对侧期、两期共用、待确认依据的回包自动进入同会话修复，同时避免项目特异硬编码。
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

1. 只读审计现有中文理由校验、四类处置语义和真实坏回包，提出可解释、低误伤的通用完整性合同及反例。
2. 实现处置特异的理由完整性校验与中文修复提示，覆盖v1/v2 wire但保持历史结构可读，不改领域身份和来源闭包。
3. 增加合成与真实坏回包回归，证明该段为方案摘要中一类残句被拒绝、合格理由仍通过，并跑期别Agent及相关协议测试。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
