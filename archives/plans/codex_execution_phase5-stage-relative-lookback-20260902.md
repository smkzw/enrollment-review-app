# Codex Execution Plan: phase5-stage-relative-lookback-20260902

Objective: 建立项目无关的节点相对回溯窗口机制：医学解释只澄清未命名锚点，正式条款阈值和逻辑不变；筛选与基线按各自节点日期形成独立评判实例，并为 SAR EX-07 的正式局部修订提供可审计入口。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查现有 InterpretationSource、草稿反馈、TimeConstraint、审核节点与发布门禁，提出最小通用合同和兼容边界，明确哪些临床语义不得写入共享代码。 | `runs/execution/phase5-stage-relative-lookback-20260902/worker_01.md` |
| `worker_02` | 实现通用节点相对回溯窗口合同、项目级解释来源接入和确定性门禁；更新提示框架，使独立模型可依据显式解释生成一个正式条件及多节点资料要求，不直接修改 SAR 数据库。 | `runs/execution/phase5-stage-relative-lookback-20260902/worker_02.md` |
| `worker_03` | 独立审查实现，使用词汇中立的合成协议验证筛选/基线独立锚定、节点历史不覆盖、无解释时失败关闭、解释越权被拒绝及反过拟合护栏；运行受影响与完整协议回归。 | `runs/execution/phase5-stage-relative-lookback-20260902/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Codex 必须逐文件核对最小改动，确认无 SAR/EX-07/蠕虫/固定 6 个月硬编码；验证无解释时仍阻断、合法医学解释只解析节点相对锚点、越权解释失败关闭、筛选与基线实例及历史隔离；运行聚焦和完整协议回归。此包不写 SAR 数据库，也不构成 SAR 规则发布或临床接受。
