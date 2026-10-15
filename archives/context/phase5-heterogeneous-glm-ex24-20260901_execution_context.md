# Execution Context: phase5-heterogeneous-glm-ex24-20260901

Created: 2026-09-01 16:11:33 CST
Objective: 以项目无关结构距离选择的只读 D001 EX-24 为异质规则样本，运行产品内置 GLM-5.3-Flash high 整候选并由当前生产门禁与 Codex 临床复核验收；严禁恢复 D001 第20包、修改冻结输入、跨提供方拼接或写入项目特异共享规则。
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

1. 只读审计 parent-rule-selection-v2.json、冻结合同、来源包哈希和共享选择器反过拟合边界，确认 EX-24 是结构距离与最低挑战度共同选择的结果。
2. 运行 heterogeneous-glm-ex24-20260901/run_heterogeneous_glm.py，以 zhipu-coding-plan/glm-5.3-flash:high 完成一次隔离整候选，保留模型身份、原始响应、时延、完整门禁和前后哈希。
3. 在新候选落盘后独立重放当前完整门禁，逐字核对开放列举、例外作用域、来源闭包、复核阶段和跨项目硬编码风险，不把模型自报或旧门禁结果当验收。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
