# Codex Execution Plan: phase4-evidence-ocr-v2-slice42

Objective: 完成Phase 4 Slice 4.2：受试者审核节点范围内的补充资料/完整资料快照上传预览、确认幂等、候选快照与持久任务，以及康哲site宽屏证据工作台骨架

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现上传预览领域合同、0008a迁移、暂存文件指纹/格式探测、差异分类、取消清理、补充/完整集合计算及确认事务服务，并建立确定性迁移/服务测试 | `runs/execution/phase4-evidence-ocr-v2-slice42/worker_01.md` |
| `worker_02` | 实现上传预览/查询/取消/确认及快照查询V2 API，连接持久Job与幂等记录，补齐中文错误信封、作用域与并发冲突API测试 | `runs/execution/phase4-evidence-ocr-v2-slice42/worker_02.md` |
| `worker_03` | 实现subjects evidence深链、运行时解码、补充/完整方式预览交互和三栏宽屏证据工作台骨架，按康哲site设计与中文临床语境补齐Vitest/Playwright无辅助任务测试 | `runs/execution/phase4-evidence-ocr-v2-slice42/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Execution Order And File Ownership

工作项严格按 `worker_01 -> worker_02 -> worker_03` 顺序执行。后续 worker 必须先读取前一份
紧凑报告和真实 diff，不得并行覆盖共享文件。

- worker_01：领域合同、存储/迁移、暂存与确认服务及其 Python 测试。
- worker_02：V2 evidence API、DTO/中文错误映射、应用注册及 API 测试。
- worker_03：React evidence API 解码、路由/入口、宽屏工作台骨架、样式与前端测试。

任何超出上述边界的缺口先记录给 Codex，不自行提前进入 Slice 4.3/4.4。

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
