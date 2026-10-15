# Execution Context: r3-gemini-product-transport-20260908

Created: 2026-09-08 23:16:54 CST
Objective: 产品原生双读接入Gemini，详细横评后置
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:xhigh -> mtplx/qwen3.8-flash-next-mtplx-optimized-speed:medium -> openai-codex/gpt-5.6-luna:max`

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

1. 用户最新授权当前只以GLM-5.3-Flash与gemini-3.7-flash作为产品两个独立主读，先完成产品，停止准备本地MTPLX实跑与详细横评。你仅在当前worktree修改app、tests/v2及必要tests产品传输测试。阅读app/llm/page_review_harness.py及相关预检执行组件、scripts/benchmark_direct_transports.py作为已验证传输参考。把google-antigravity Gemini原生HTTP视觉传输迁入独立app/llm模块，不调用个人harness、不运行时读取OMP/Hermes或任何home配置，不导入benchmark脚本。产品必须显式env配置access token/project ID和端点，凭据不得写日志。主线程后续负责凭据，不读取.env。保留GLM low，Gemini high；模型标识gemini-3.7-flash。支持已有单阶段主读消息完整图像和提示、原生SSE正文与thinking分离、正确finish映射、usage/模型身份/响应id回执、流中断拒绝采信；无temperature；现有取消和429/length预算机制不能破坏。产品预检适配真实Gemini传输而不是错误强制OpenAI models接口，缺凭据明确失败，不自动替换。默认main-B配置改为Gemini但保留历史身份读取，移除活跃MTPLX默认。测试HTTP mock涵盖请求角色/图像/预算/effort、429、截断、过滤、断流、取消、主读身份及正式作业预检。只运行可控本地测试，不网络、不模型、不安装、不读临床资料、不改docs/plans/env/scripts，不递归派发。返回准确实施与测试和剩余问题，不声称真实模型通过。沿用当前两主读无第三读的已完成清理，不能恢复第三读。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
