# Execution Context: phase5-mtplx-default-semantic-agent-20260827

Created: 2026-08-27 09:44:14
Objective: 将入排审核系统后续内置语义Agent默认路由切换为MTPLX/mtplx-qwen38-27b-optimized-quality，默认推理强度medium，同时保持OCR继续使用oMLX，并用真实本地服务证明配置和传输兼容。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
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

1. 审计并实现共享模型配置与方案解构、期别语义、证据规范化、旧审核调用链的MTPLX OpenAI兼容传输；不得把MTPLX误接到OCR。
2. 审计并实现桌面启动入口对oMLX OCR与MTPLX语义服务的双服务启动、健康检查和中文故障提示，保持用户双击即用。
3. 补充配置、传输和启动脚本聚焦回归，执行真实MTPLX连通性与严格结构化输出探针，独立核对未发生静默回退或源资料修改。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
