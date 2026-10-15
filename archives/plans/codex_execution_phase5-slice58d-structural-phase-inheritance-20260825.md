# Codex Execution Plan: phase5-slice58d-structural-phase-inheritance-20260825

Objective: 修复通用期别结构继承缺陷，并用真实 D001 II 量化验证，避免把可由原始标题结构确定的单元浪费在语义 Agent 上。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 追踪正文标题层级与表格上位上下文，实施最小通用根因修复，不引入项目特异规则。 | `runs/execution/phase5-slice58d-structural-phase-inheritance-20260825/worker_01.md` |
| `worker_02` | 增加边界测试：阶段标题下同级/多层子标题与表格继承、离开分支关闭、普通叙述不扩散。 | `runs/execution/phase5-slice58d-structural-phase-inheritance-20260825/worker_02.md` |
| `worker_03` | 只读重建 D001 II 覆盖清单和冻结计划，量化前后模糊单元/批次，运行聚焦回归并记录仍需真实 Agent 的范围。 | `runs/execution/phase5-slice58d-structural-phase-inheritance-20260825/worker_03.md` |

## Codex Acceptance

Codex 独立复核修复没有把 UNKNOWN 默认成 shared/selected，没有跨同级阶段边界泄漏，源 DOCX 哈希不变，并根据真实 D001 量化结果决定后续语义闭包路线。
