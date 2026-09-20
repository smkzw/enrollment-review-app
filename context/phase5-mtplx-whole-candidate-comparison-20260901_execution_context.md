# Execution Context: phase5-mtplx-whole-candidate-comparison-20260901

Created: 2026-09-01 14:10:56 CST
Objective: 在同一冻结 EX-06 输入上运行完全隔离的 MTPLX 整候选，复用生产方案解构合同与完整门禁，记录时效、调用、来源闭包和问题分类；禁止跨模型拼接，禁止恢复 D001。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
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

1. 只读核对冻结输入、GLM 负向证据与生产 MTPLX 传输合同，提出最小整候选验收入口和不可变性检查。
2. 实现或复用隔离 MTPLX 整候选验收脚本，完成短连通性预检、真实调用、调用台账和完整门禁；只允许写入新验收目录。
3. 独立设计并运行确定性核验，检查来源闭包、候选隔离、门禁问题分类、冻结哈希和 D001 暂停边界，拒绝以 API 成功代替语义质量。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
