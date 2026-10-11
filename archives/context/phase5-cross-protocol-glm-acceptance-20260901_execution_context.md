# Execution Context: phase5-cross-protocol-glm-acceptance-20260901

Created: 2026-09-01 15:23:58 CST
Objective: 基于两份不可变方案快照，以纯结构指标选择异构父规则，使用产品内置 GLM-5.3-Flash high 生成一个完整候选，并由当前生产门禁确定性验收；严禁恢复 D001 第20包、修改旧快照或写入项目特异规则。
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

1. 审计两份冻结快照的哈希、结构指标选样算法及 D001 暂停边界，输出只读审计结论。
2. 复用现有生产 ProtocolDeconstructorRunner 与 zhipu-coding-plan GLM-5.3-Flash high，完成选中父规则的一次隔离整候选运行并保留原始响应、模型身份、时延和前后哈希。
3. 独立重放当前完整门禁，核对候选可发布性、跨项目硬编码风险、来源闭包和证据完整性，不把模型自报当作验收。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
