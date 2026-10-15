# Codex Execution Plan: phase5-mtplx-default-semantic-agent-20260827

Objective: 将入排审核系统后续内置语义Agent默认路由切换为MTPLX/mtplx-qwen38-27b-optimized-quality，默认推理强度medium，同时保持OCR继续使用oMLX，并用真实本地服务证明配置和传输兼容。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计并实现共享模型配置与方案解构、期别语义、证据规范化、旧审核调用链的MTPLX OpenAI兼容传输；不得把MTPLX误接到OCR。 | `runs/execution/phase5-mtplx-default-semantic-agent-20260827/worker_01.md` |
| `worker_02` | 审计并实现桌面启动入口对oMLX OCR与MTPLX语义服务的双服务启动、健康检查和中文故障提示，保持用户双击即用。 | `runs/execution/phase5-mtplx-default-semantic-agent-20260827/worker_02.md` |
| `worker_03` | 补充配置、传输和启动脚本聚焦回归，执行真实MTPLX连通性与严格结构化输出探针，独立核对未发生静默回退或源资料修改。 | `runs/execution/phase5-mtplx-default-semantic-agent-20260827/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
