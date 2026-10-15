# Codex Execution Plan: phase5-zhipu-coding-plan-vlm-20260831

Objective: 将独立GLM-5.3-Flash视觉适配器改为与本地OMP zhipu-coding-plan相同的Coding Plan端点和兼容参数，保持来源定位、失败关闭与现有语义/OCR路由隔离，并完成脱敏连通性与回归验证。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读核对本地OMP zhipu-coding-plan/glm-5.3-flash的端点、模型元数据、视觉消息和思考参数兼容合同，输出脱敏差异。 | `runs/execution/phase5-zhipu-coding-plan-vlm-20260831/worker_01.md` |
| `worker_02` | 基于现有app/llm/independent_vlm.py做最小实现修订与配置迁移，不耦合OMP数据库，不改OCR或语义Agent。 | `runs/execution/phase5-zhipu-coding-plan-vlm-20260831/worker_02.md` |
| `worker_03` | 补充独立适配器合同、错误分类、视觉消息和真实脱敏连通性测试；核对无项目特异硬编码并给出接受边界。 | `runs/execution/phase5-zhipu-coding-plan-vlm-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
