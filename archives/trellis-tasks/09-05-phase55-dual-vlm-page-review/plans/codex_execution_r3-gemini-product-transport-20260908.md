# Codex Execution Plan: r3-gemini-product-transport-20260908

Objective: 产品原生双读接入Gemini，详细横评后置

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 用户最新授权当前只以GLM-5.3-Flash与gemini-3.7-flash作为产品两个独立主读，先完成产品，停止准备本地MTPLX实跑与详细横评。你仅在当前worktree修改app、tests/v2及必要tests产品传输测试。阅读app/llm/page_review_harness.py及相关预检执行组件、scripts/benchmark_direct_transports.py作为已验证传输参考。把google-antigravity Gemini原生HTTP视觉传输迁入独立app/llm模块，不调用个人harness、不运行时读取OMP/Hermes或任何home配置，不导入benchmark脚本。产品必须显式env配置access token/project ID和端点，凭据不得写日志。主线程后续负责凭据，不读取.env。保留GLM low，Gemini high；模型标识gemini-3.7-flash。支持已有单阶段主读消息完整图像和提示、原生SSE正文与thinking分离、正确finish映射、usage/模型身份/响应id回执、流中断拒绝采信；无temperature；现有取消和429/length预算机制不能破坏。产品预检适配真实Gemini传输而不是错误强制OpenAI models接口，缺凭据明确失败，不自动替换。默认main-B配置改为Gemini但保留历史身份读取，移除活跃MTPLX默认。测试HTTP mock涵盖请求角色/图像/预算/effort、429、截断、过滤、断流、取消、主读身份及正式作业预检。只运行可控本地测试，不网络、不模型、不安装、不读临床资料、不改docs/plans/env/scripts，不递归派发。返回准确实施与测试和剩余问题，不声称真实模型通过。沿用当前两主读无第三读的已完成清理，不能恢复第三读。 | `runs/execution/r3-gemini-product-transport-20260908/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
