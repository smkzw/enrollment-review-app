# Codex Execution Plan: phase5-independent-glm53-vlm-20260831

Objective: 为入排审核系统建立统一的智谱GLM-5.3-Flash视觉模型配置与调用契约，覆盖直接DOCX/PDF来源处理所需的视觉核验能力，并修正旧串行方案控制回放的性能边界；不得改变确定性临床判定边界或写入项目特异规则。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 盘点现有方案解构、方案控制、证据处理、事实规范化和受试者审核harness的模型入口，提出最小共享视觉适配层及兼容迁移清单。 | `runs/execution/phase5-independent-glm53-vlm-20260831/worker_01.md` |
| `worker_02` | 实现并测试BigModel GLM-5.3-Flash视觉传输配置、high到thinking enabled的映射、原始页面输入和来源定位保真契约；远程余额不足必须明确失效关闭。 | `runs/execution/phase5-independent-glm53-vlm-20260831/worker_02.md` |
| `worker_03` | 实现或收紧基于输入令牌和输出预算的自适应批次、有限并发与运行指标，避免继续D001逐固定包串行回放，并做通用性/过拟合审计。 | `runs/execution/phase5-independent-glm53-vlm-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
