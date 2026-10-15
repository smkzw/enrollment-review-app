# Execution Context: phase5-zhipu-coding-plan-vlm-20260831

Created: 2026-08-31 20:04:39 CST
Objective: 将独立GLM-5.3-Flash视觉适配器改为与本地OMP zhipu-coding-plan相同的Coding Plan端点和兼容参数，保持来源定位、失败关闭与现有语义/OCR路由隔离，并完成脱敏连通性与回归验证。
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

- Local OMP provider registry: `/Users/smkzw/.bun/install/global/node_modules/@oh-my-pi/pi-ai/src/registry/zhipu-coding-plan.ts`.
- Local OMP model metadata: read-only `~/.omp/agent/models.db` rows for provider `zhipu-coding-plan` and model `glm-5.3-flash`.
- Application contract: `app/config.py`, `app/llm/independent_vlm.py`, `.env.example` and `tests/v2/llm/test_independent_vlm.py` in this worktree.
- The OMP credential database is an authentication source only. Runtime application code must not import or query it.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读核对本地OMP zhipu-coding-plan/glm-5.3-flash的端点、模型元数据、视觉消息和思考参数兼容合同，输出脱敏差异。
2. 基于现有app/llm/independent_vlm.py做最小实现修订与配置迁移，不耦合OMP数据库，不改OCR或语义Agent。
3. 补充独立适配器合同、错误分类、视觉消息和真实脱敏连通性测试；核对无项目特异硬编码并给出接受边界。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
