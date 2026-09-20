# Codex Execution Plan: phase5-sar31001-qc-contract-closeout-20260905

Objective: 在不硬编码 SAR 或 31001 的前提下，查明最新不可变事实规范化运行的临床漏项根因，完成最小通用合同修复与确定性验证，为一次有价值的全量重跑做好准备；不得提前收口 Phase 5 或启动 Phase 5.5。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计最新 31001 运行包、候选门禁和活动 Profile，对照原始证据确认真正遗漏与已有旧修订覆盖，形成逐项可验证的临床 QC 清单。 | `runs/execution/phase5-sar31001-qc-contract-closeout-20260905/worker_01.md` |
| `worker_02` | 沿共享调用链审计数值/单位规范化、来源语义对齐、事件与用药暴露引用闭包，定位能解释漏项且项目无关的最小根因与测试边界。 | `runs/execution/phase5-sar31001-qc-contract-closeout-20260905/worker_02.md` |
| `worker_03` | 审查拟议最小修复的跨项目泛化性、不可变历史与 fail-closed 行为，提出聚焦回归和重跑前退出门槛，不修改源临床资料。 | `runs/execution/phase5-sar31001-qc-contract-closeout-20260905/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
