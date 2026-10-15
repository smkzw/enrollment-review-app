# Execution Context: phase5-large-parent-segmented-glm-live-probe-20260901

Created: 2026-09-01 11:30:16 CST
Objective: 在不修改冻结临床源资料、旧探针、旧任务和已暂停 D001 的前提下，使用生产 ProtocolDeconstructorRunner 与 GLM-5.3-Flash high 对大型父规则执行四段真实语义解构，记录耗时、模型身份、原始响应、确定性合并和发布门结果，并与既有整段 GLM 探针进行独立质量及性能对照；不得触发未授权 fallback。
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

1. 只读预检冻结源包、生产运行器、GLM 传输适配器和凭据加载路径；形成最小真实探针方案，证明规划器输出四段且不泄露凭据、不改写旧产物。
2. 运行新的真实分段 GLM-5.3-Flash high 探针：复用生产运行器和传输，最多两路并发，保存每次调用的模型身份、耗时、原始响应、合并候选与发布门结果到新的独立产物目录；失败时保留证据并停止，不自动切换模型。
3. 独立只读比较新分段结果与既有整段 GLM 结果：核对源覆盖、义务项、逻辑/时间锚点、例外、证据要求、发布门、错误和耗时；检查是否存在 D001/SAR 特异硬编码，仅给出证据化结论，不自行宣布临床最终验收。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
