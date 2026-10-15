# Execution Context: phase5-fresh-subject-runtime-routing-20260901

Created: 2026-09-01 16:42:50 CST
Objective: 修复 Phase 5 代表受试者验收中的旧失败运行身份污染，确保复杂方案语义任务默认 GLM-5.3-Flash high、完整尝试失败后依次 MTPLX medium 与 DeepSeek V4 Flash high；短提示任务默认 MTPLX medium 后回退 DeepSeek，并建立不可复用旧失败数据库的全新 SAR 31001 隔离运行入口及确定性验证。禁止恢复 D001 第20包、禁止修改原始临床资料、禁止项目特异硬编码。
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

1. 审计并最小修正生产语义路由、默认配置和运行审计，使复杂与短任务分级及全尝试隔离真正由服务入口生效；补充聚焦测试。
2. 实现或修正代表受试者新运行目录与身份门禁：拒绝旧 job_id、旧模型配置、已有业务状态数据库被误当新验收；仅复用哈希验证后的不可变隔离输入。
3. 独立构建对抗回归，覆盖旧 SAR failed_final 数据库污染、GLM 首选、MTPLX/DeepSeek 完整尝试回退、短任务 MTPLX 首选、无 D001/SAR/疾病/药物硬编码，并报告剩余阻塞。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
