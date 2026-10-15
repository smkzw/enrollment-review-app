# Execution Context: phase5-normalizer-throughput-20260903

Created: 2026-09-03 09:37:52 CST
Objective: 在不提前实现 Phase 5.5、不硬编码项目临床内容的前提下，定位并修复 Phase 5 Evidence Normalizer 的小时级单页时延：复用已批准的 zhipu-coding-plan GLM-5.3-Flash 路由，压缩模型可见但保持来源闭包的输入合同，完成定向回归和只读单页速度质量闸门。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/qwen3.8-flash-next-mtplx-optimized-speed:medium -> openai-codex/gpt-5.6-luna:xhigh`

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

1. 只读审计现有 Evidence Normalizer 提示、定位、资料要求和传输调用链，给出可泛化的最小压缩边界与风险，不修改文件。
2. 实现 Evidence Normalizer 对 zhipu-coding-plan/GLM-5.3-Flash 的供应方中性接入及凭据预检复用，保持现有 MTPLX/DeepSeek/oMLX 路由兼容并增加聚焦测试。
3. 实现并验证不丢失来源闭包的模型输入瘦身，优先消除重复定位和重复 Schema/字段，不改变冻结审计输入或临床判断；提供体积测量和回归证据。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
