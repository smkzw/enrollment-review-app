# Execution Context: phase5-slice61au-typographic-source-restoration

Created: 2026-08-29 18:22:21 CST
Objective: 在不增加全局修订预算、不放松逐字来源门禁的前提下，仅对模型引文与唯一授权冻结原文之间可证明为引号字形差异的情况进行确定性原文还原，并保留原始输出和还原记录；重新验证 D001 心电图真实重放。
Task type: `finite_code_task`
Risk: `medium`
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

1. 实现最小的引号字形等价映射与唯一连续来源匹配；仅在 runner 解析后、严格水合前还原 source_excerpts，禁止词字、数字、单位、比较符、一般标点或空白变化通过。
2. 补充通用回归，覆盖弯/直单双引号唯一匹配可还原，多重匹配、非引号差异、数字单位比较符和跨来源差异仍失败；验证原始模型文本哈希与审计提示保留。
3. 独立审查全局两轮修订预算、来源闭包、候选动作差集和发布门禁未被绕过，并运行聚焦及协议全量回归；若实现不满足边界则明确拒绝。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
