# Execution Context: phase5-slice58-dnf-categorical-logic-hardening-20260824

Created: 2026-08-24 16:17:11
Objective: 基于 D001 dnf-v1 首批真实回包，从共享合同层消除分类单位任意字符串、分类/标量形状歧义和无原文依据的反向替代分支，并以真实反例和完整协议回归证明不弱化正式领域语义。
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

- `artifacts/phase5-acceptance/20260824/probe-wire-dnf-v1-r1/source-input-first-batch.json`
- `artifacts/phase5-acceptance/20260824/probe-wire-dnf-v1-r1/raw-response.json`
- `app/domain/contracts/rules.py`
- `app/protocols/deconstruction_gate.py`
- `app/agents/protocol_deconstructor.py`
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 收紧 oMLX dnf-v1 Schema、中文合同和确定性校验：数值标量与分类集合形状明确，分类单位固定 unitless，原文无或/任一时禁止生成替代分支，否定仅来自直接原文。
2. 迁移并扩展契约/水合测试，覆盖 unit=非、字符串 scalar、数值 set、IN-01 虚构未签署替代分支、缺失批次规则及候选/修订同形状；不得改正式 RuleExpression 或非紧凑 DeepSeek 路径。
3. 独立审阅真实 D001 r1 回包与原文，运行聚焦和完整 tests/v2/protocols 回归，检查旧语义能力是否被误删并报告仍需真实 oMLX 复跑的边界。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
