# Codex Execution Plan: phase5-normalizer-throughput-20260903

Objective: 在不提前实现 Phase 5.5、不硬编码项目临床内容的前提下，定位并修复 Phase 5 Evidence Normalizer 的小时级单页时延：复用已批准的 zhipu-coding-plan GLM-5.3-Flash 路由，压缩模型可见但保持来源闭包的输入合同，完成定向回归和只读单页速度质量闸门。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计现有 Evidence Normalizer 提示、定位、资料要求和传输调用链，给出可泛化的最小压缩边界与风险，不修改文件。 | `runs/execution/phase5-normalizer-throughput-20260903/worker_01.md` |
| `worker_02` | 实现 Evidence Normalizer 对 zhipu-coding-plan/GLM-5.3-Flash 的供应方中性接入及凭据预检复用，保持现有 MTPLX/DeepSeek/oMLX 路由兼容并增加聚焦测试。 | `runs/execution/phase5-normalizer-throughput-20260903/worker_02.md` |
| `worker_03` | 实现并验证不丢失来源闭包的模型输入瘦身，优先消除重复定位和重复 Schema/字段，不改变冻结审计输入或临床判断；提供体积测量和回归证据。 | `runs/execution/phase5-normalizer-throughput-20260903/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
