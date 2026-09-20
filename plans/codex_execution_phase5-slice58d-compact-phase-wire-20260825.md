# Codex Execution Plan: phase5-slice58d-compact-phase-wire-20260825

Objective: 以 provider wire 分组压缩消除期别语义重复输出，同时保持逐单元领域结果和严格来源门禁。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 设计并实现紧凑 v2 provider wire、严格分组校验及确定性逐目标展开，保留现有领域结果和 gate。 | `runs/execution/phase5-slice58d-compact-phase-wire-20260825/worker_01.md` |
| `worker_02` | 增加独立边界测试：排序/重复/身份漂移/漏目标/异质组/证据归属，以及 v1 历史兼容或明确迁移。 | `runs/execution/phase5-slice58d-compact-phase-wire-20260825/worker_02.md` |
| `worker_03` | 用修复后的 D001 内存清单对真实首批及一个非元数据批次运行本地系统 Agent，比较输出字符、耗时、逐单元结论和 gate。 | `runs/execution/phase5-slice58d-compact-phase-wire-20260825/worker_03.md` |

## Codex Acceptance

Codex 独立复核 provider 分组没有改变领域合同与临床处置粒度，真实结果可逐字回源，并据实决定是否用新 wire 执行剩余 D001 闭包。
