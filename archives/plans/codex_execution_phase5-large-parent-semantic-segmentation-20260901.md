# Codex Execution Plan: phase5-large-parent-semantic-segmentation-20260901

Objective: 为超大官方父规则建立项目无关的结构分段、有限并发和确定性同父规则合并合同，在保留父子编号、逻辑、例外、来源与完整性门禁的前提下降低 GLM 方案语义解构时延；不得按 D001、SAR、疾病、药物、量表、条款编号或时间点硬编码，不恢复旧 D001/SAR 作业。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查现有方案语义提示、批次、会话、缓存、门禁和路由合同，提出超大父规则内部结构分段与同父规则确定性合并设计，重点识别不可安全并行的父级限定语、例外和跨段依赖。 | `runs/execution/phase5-large-parent-semantic-segmentation-20260901/worker_01.md` |
| `worker_02` | 按经审查的通用合同实现超大父规则结构分段、有限并发调度和同父规则确定性合并，保持完整路由审计、失败关闭、缓存模型身份隔离和旧调用兼容；仅修改授权代码与配置。 | `runs/execution/phase5-large-parent-semantic-segmentation-20260901/worker_02.md` |
| `worker_03` | 独立编写并运行跨项目中性样本和对抗测试，验证父级限定语继承、AND/OR、例外、跨段依赖、来源闭包、合并确定性、并发上限、失败回退及无项目特异硬编码；不得以实现者自报作为通过依据。 | `runs/execution/phase5-large-parent-semantic-segmentation-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
