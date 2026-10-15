# Execution Context: phase5-slice60zm-bounded-repair-retention-20260828

Created: 2026-08-28 11:42:56
Objective: 基于D001第68包v7-v9保存响应与当前ProtocolControlAgentRunner，定位按结构单元修订授权仍会丢失正确语义的根因，设计可复用、失效关闭、不可泄露金标准的候选/处置细粒度修订状态保留机制；本轮先做独立分析和实现建议，不调用真实模型，不运行受试者、OCR、浏览器或视觉测试。
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

1. 独立只读核对v7-v9每次保存响应和attempt记录，形成候选、处置及字段级漂移表，说明现有mutable_structure_unit_ids为何无法保护已正确内容，并给出可复现的最小反例。
2. 独立审阅ProtocolControlAgentRunner、wire身份推导、修订错误范围和restore逻辑，设计最小通用候选/处置保留合同，重点处理跨多个来源单元候选、候选拆分/合并、schema失败无可水合基线及稳定身份问题。
3. 独立设计确定性回归与验收边界：哪些字段允许局部替换、哪些必须原样保留、何时拒绝自动合并并转需核对，以及如何用保存响应离线验证而不把临床金标准注入Agent。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
