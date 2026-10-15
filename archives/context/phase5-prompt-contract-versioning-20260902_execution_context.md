# Execution Context: phase5-prompt-contract-versioning-20260902

Created: 2026-09-02 06:04:33 CST
Objective: 在不改写 D001 v1/v2 历史检查点、不改变临床规则内容的前提下，将当前方案控制提示词显式版本化，建立当前可重建的新重放检查点，并恢复完整协议回归。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `zcode` / `zcode` / `GLM-5.3-Flash`
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

1. 只读分析现有提示词版本、重放配置与 v1/v2 检查点，给出最小兼容边界和不得修改项。
2. 实现当前提示词版本声明、重放包版本记录和新的只读检查点；禁止写入项目特异生产逻辑。
3. 独立审查旧历史不可变性、当前重建确定性及聚焦/完整协议测试，记录剩余风险。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
