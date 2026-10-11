# Execution Context: phase5-slice58r-affected-package-semantic-validation-20260826

Created: 2026-08-26 22:06:16
Objective: 在当前已接受的 D001 强边界结构基线上，建立可审计的限包语义执行入口，并只为第67、78、79、80、111包准备真实期别语义验证；保持 claims_complete=false，不运行其余包、受试者、浏览器或独立测试者。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `pi` / `mtplx` / `mtplx-qwen38-27b-optimized-quality`
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

1. 实现最小通用限包执行能力：审查 scripts/run_phase_applicability_acceptance.py 及正式计划合同，仅在必要时增加可重复的包序号选择参数；筛选后必须重建自洽的冻结计划身份、目标全集与包身份，不能原地篡改原计划，也不能默默复用历史结果。补充聚焦测试并仅修改被授权的脚本/测试。
2. 只读临床与来源审计当前58q第67、78、79、80、111包：逐包说明目标主题、期别混合点、应重点验证的标题族/直接来源/未决边界，以及哪些旧语义结果因身份变化不得复用。不得修改代码或运行语义模型，输出面向父级的紧凑核对清单。
3. 只读工程验证与执行方案审计：检查当前58q manifest/plan/五包输入能否由正式合同重载，提出最小真实模型串行运行和结果验收步骤，明确源文件不变、结果隔离、失败保留、同会话修复及确定性门禁。不得运行模型、不得修改应用代码或宣称临床完成。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
