# Execution Context: phase5-slice61at-repair-source-closure

Created: 2026-08-29 17:50:29 CST
Objective: 修复其他方案控制 Agent 同会话定向修复缺少权威原文闭包导致逐字引文反复失败的问题；保持严格逐字校验与动作增量门控，不写入任何项目特异临床规则，并以通用回归和 D001 心电图受控重放验证。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/auto -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `auto`
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

1. 实现最小共享修复：定向修复提示仅附带授权结构单元的冻结原文及来源定位，并为 FABRICATED_EXCERPT 提供逐字复制指引；不得放松连续原文校验或自动篡改模型引文。
2. 补充通用回归：覆盖弯引号、全角标点等必须逐字保真的原文，验证修复提示包含且仅包含授权原文闭包，同时未授权单元不泄露且严格校验仍拒绝改写引文。
3. 独立审查动作差集与修复收敛边界：确认 PROCEDURE_ACTION_UNCOVERED 仍阻断把已执行/已记录扩张为覆盖准备与计算动作，并运行相关协议控制测试，报告任何跨层回归。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
