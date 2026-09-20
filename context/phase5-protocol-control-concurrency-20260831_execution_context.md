# Execution Context: phase5-protocol-control-concurrency-20260831

Created: 2026-08-31 15:51:49 CST
Objective: 为方案控制发现链实现最小、可恢复、可审计的持久任务内受控并行执行；并行只适用于相互独立的发现批次，必须保持租约、幂等、部分成功、失败、取消和恢复语义，不恢复或修改暂停中的D001任务，不写入项目特异规则。
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

1. 只读审查JobRunner、JobStore、方案控制executor和transport生命周期，提出最小并行边界，明确部分成功/失败、取消、租约丢失和线程安全风险；不得修改代码。
2. 在授权工作树内实现最小租约安全并行执行与配置冻结，仅作用于明确声明可并行的独立发现步骤；补齐必要单元测试，不改临床判定或旧D001数据。
3. 独立设计并执行并发验收测试，覆盖并行峰值、结果顺序、部分成功、可重试/致命失败、取消、租约丢失、恢复和串行兼容；审计是否存在假并发或项目过拟合。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
