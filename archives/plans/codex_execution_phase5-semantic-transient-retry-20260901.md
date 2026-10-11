# Codex Execution Plan: phase5-semantic-transient-retry-20260901

Objective: 以供应商无关的最小改动补齐方案语义模型暂态服务错误重试，确保同一请求有限重试、非暂态失败不重试，并以故障注入和回归测试验证后支持 SAR 受控恢复。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 检查现有 OpenAI 兼容传输异常边界，给出最小的暂态 5xx/429/连接错误重试实现，不改变会话历史和模型路由。 | `runs/execution/phase5-semantic-transient-retry-20260901/worker_01.md` |
| `worker_02` | 补充故障注入测试，证明暂态错误有限重试后成功、非暂态 4xx 不重试、最终错误不泄露凭据且保持中文恢复语义。 | `runs/execution/phase5-semantic-transient-retry-20260901/worker_02.md` |
| `worker_03` | 运行聚焦回归并独立审阅 SAR 恢复路径，确认不会削弱完整性门禁、不会硬编码项目规则，也不会重复结构提取。 | `runs/execution/phase5-semantic-transient-retry-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
