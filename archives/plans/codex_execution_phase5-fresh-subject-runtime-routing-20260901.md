# Codex Execution Plan: phase5-fresh-subject-runtime-routing-20260901

Objective: 修复 Phase 5 代表受试者验收中的旧失败运行身份污染，确保复杂方案语义任务默认 GLM-5.3-Flash high、完整尝试失败后依次 MTPLX medium 与 DeepSeek V4 Flash high；短提示任务默认 MTPLX medium 后回退 DeepSeek，并建立不可复用旧失败数据库的全新 SAR 31001 隔离运行入口及确定性验证。禁止恢复 D001 第20包、禁止修改原始临床资料、禁止项目特异硬编码。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计并最小修正生产语义路由、默认配置和运行审计，使复杂与短任务分级及全尝试隔离真正由服务入口生效；补充聚焦测试。 | `runs/execution/phase5-fresh-subject-runtime-routing-20260901/worker_01.md` |
| `worker_02` | 实现或修正代表受试者新运行目录与身份门禁：拒绝旧 job_id、旧模型配置、已有业务状态数据库被误当新验收；仅复用哈希验证后的不可变隔离输入。 | `runs/execution/phase5-fresh-subject-runtime-routing-20260901/worker_02.md` |
| `worker_03` | 独立构建对抗回归，覆盖旧 SAR failed_final 数据库污染、GLM 首选、MTPLX/DeepSeek 完整尝试回退、短任务 MTPLX 首选、无 D001/SAR/疾病/药物硬编码，并报告剩余阻塞。 | `runs/execution/phase5-fresh-subject-runtime-routing-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
