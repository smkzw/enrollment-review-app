# Execution Context: phase5-slice58-reference-free-wire-design-20260824

Created: 2026-08-24 09:45:10
Objective: 基于连续真实 oMLX 失败证据，选择一个不依赖跨数组节点引用、能无损表达临床入排布尔逻辑、且可由 provider 严格 Schema 最大程度约束的 compact wire 结构，并形成可实施与可验收的迁移设计。
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

1. 独立评估 ANY-of-ALL 无引用布尔组加原子否定的表达完备性、临床可解释性、重复项风险及从 wire 到正式领域树的确定性水合方案。
2. 独立比较固定深度树、布尔 DSL、位置引用、DNF/CNF 布尔组等候选结构在 oMLX provider Schema 支持、模型稳定性、领域等价性和失败可诊断性上的权衡。
3. 基于 v6-v9 真实失败回包制定迁移边界、稳定身份生成、Schema/水合/提示词测试矩阵和 D001/MG-K10-SAR 真实验收门槛，并给出明确推荐。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
