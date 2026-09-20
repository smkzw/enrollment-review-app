# Codex Execution Plan: phase5-slice58d-mixed-table-atomization-20260825

Objective: 按真实表格成员期别原子化混合行，避免将 II/III 并列内容误判为跨期共用。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实施通用混合期别表格行原子化，保持普通同范围行聚合和全部表格来源上下文。 | `runs/execution/phase5-slice58d-mixed-table-atomization-20260825/worker_01.md` |
| `worker_02` | 增加边界与回归测试，重点验证成员唯一覆盖、selected/opposite 分离、unknown 不冒充 shared、嵌套表不串行。 | `runs/execution/phase5-slice58d-mixed-table-atomization-20260825/worker_02.md` |
| `worker_03` | 只读重建真实 D001 II，量化单元/模糊/批次变化，逐成员审查原 package 32 和表 5，运行相邻回归。 | `runs/execution/phase5-slice58d-mixed-table-atomization-20260825/worker_03.md` |

## Codex Acceptance

Codex 复核技术 gate 与临床含义一致后，才重新冻结 D001 清单并继续真实语义闭包。
