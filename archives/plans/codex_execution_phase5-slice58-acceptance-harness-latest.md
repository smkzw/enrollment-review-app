# Codex Execution Plan: phase5-slice58-acceptance-harness-latest

Objective: 为 Phase 5.8 建立可审计的真实项目隔离输入清单、病例级 P5-AC01 至 P5-AC13 验收账本与真实浏览器端到端验收工具；不得修改原始临床资料，不提前给出入排结论，不以 fixture 冒充真实运行。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现只读源目录盘点与内容哈希清单、排除照片/压缩包规则、隔离复制计划和源文件不变性校验；工具只生成工作区内清单/副本，不写外部原始目录。 | `runs/execution/phase5-slice58-acceptance-harness-latest/worker_01.md` |
| `worker_02` | 实现 P5-AC01 至 P5-AC13 机器可读验收账本与病例级数据库/文件/定位核对器，能区分观察、自动检查、人工临床核对和测试者证据，不把测试通过冒充临床正确。 | `runs/execution/phase5-slice58-acceptance-harness-latest/worker_02.md` |
| `worker_03` | 实现新架构 D001 II 与 MG-K10-SAR III 新项目的浏览器验收编排骨架，覆盖项目创建、方案期别选择、受试者资料上传、真实 Normalizer、Patient Profile、原文定位和历史回放；保持执行者与独立测试者角色分离。 | `runs/execution/phase5-slice58-acceptance-harness-latest/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Accepted as bounded acceptance infrastructure after Codex remediation and deterministic checks. Real browser/model acceptance remains blocked by a verified product integration gap: no user-facing FactNormalization job trigger and no automatic Patient Profile materialization after normalization. This is the next implementation task, not evidence that Phase 5.8 passed.
