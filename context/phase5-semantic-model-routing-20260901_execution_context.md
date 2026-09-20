# Execution Context: phase5-semantic-model-routing-20260901

Created: 2026-09-01 08:21:44 CST
Objective: 为Phase 5方案语义解构实现通用任务分级模型路由：复杂方案语义主用GLM-5.3-Flash，失败后依次MTPLX、DeepSeek V4 Flash high；短提示小任务优先MTPLX，并保证回退显式、作业隔离、可审计且不含项目特异硬编码。
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

1. 审阅现有方案语义传输、配置、执行器和缓存合同，形成最小兼容的任务分级与显式回退设计，指出不得混合不同模型批次的边界。
2. 在当前工作树实现通用模型配置、GLM OpenAI兼容传输接入、复杂任务与短任务路由选择、显式全尝试回退和审计记录；保留旧导入兼容且不修改原始临床资料。
3. 新增独立确定性测试，覆盖默认路由、短任务分流、回退触发、提供方切换后的候选隔离、缓存不跨模型复用、中文诊断和无项目特异硬编码。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
