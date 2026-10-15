# Execution Context: phase5-slice61am-p804-source-closure-current-route-verification-20260828

Created: 2026-08-28 22:32:04 CST
Objective: 在不修改临床工件、不运行语义模型、不发布控制点的前提下，使用最新执行路线独立验收 p804 同源来源闭包修订合同、主线程 runner 路径补漏及真实 v8 离线边界；确认它是通用合同且没有把工程通过误写为临床通过。
Task type: `finite_code_task`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; resolved once at packet creation in `Asia/Shanghai`.
Effective worker chain: `codebuddy-cli/glm-5.3:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `glm-5.3`
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

1. 只读核查共享实现：追踪 CONDITIONAL_EXEMPTION_SCOPE_SPLIT 从发布门禁、修订错误映射、runner 授权到 bounded restore/validate 的完整路径；重点验证 source closure 与 atom-level obligation span 互斥、闭包外来源冻结及无 D001 特异硬编码。
2. 独立检查聚焦测试与完整协议层回归：运行明确的确定性测试，审查新增测试是否真实经过 runner 路径并覆盖合并、拆分、跨来源吸收、来源丢失、乱序和失败关闭；不得以测试数量替代断言质量。
3. 只读复核真实 v8 A4/A5 离线来源闭包恢复证据：确认 p805 越界变化被恢复、p804 仍未被旧响应正确闭合，明确工程合同可用与临床内容仍拒绝的边界，并给出是否具备进入独立会商的证据判断。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
