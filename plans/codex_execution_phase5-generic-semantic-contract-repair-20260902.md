# Codex Execution Plan: phase5-generic-semantic-contract-repair-20260902

Objective: 修正方案语义提示合同与确定性门禁之间的通用中文表达不一致，使非限制性人群描述、结构引导语、明确“之一”替代关系、共享期间和否定对象可被正确表达与核对，同时保持所有项目特异临床规则零硬编码。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审查并最小修订方案语义提示合同：覆盖男女不限等非限制性范围、数值 source_term 逐字要求、共享期间来源绑定和否定对象命名，不写任何项目特异规则。 | `runs/execution/phase5-generic-semantic-contract-repair-20260902/worker_01.md` |
| `worker_02` | 审查并最小修订确定性门禁：通用识别非限制性表述与结构引导语，并正确验证“之一/任一”明确替代关系，保持实质条件 fail-closed。 | `runs/execution/phase5-generic-semantic-contract-repair-20260902/worker_02.md` |
| `worker_03` | 新增反过拟合故障注入与回归测试，使用合成中文条款证明新合同消除假阳性但仍拒绝真实遗漏、虚构任选关系、跨来源和未绑定时间窗。 | `runs/execution/phase5-generic-semantic-contract-repair-20260902/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
