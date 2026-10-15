# Codex Execution Plan: phase5-slice60zn-authoritative-target-excerpts-20260828

Objective: 修复全方案控制打包中权威官方规则与流程必做项只有身份、没有逐字来源摘录的问题，使直接上传DOCX/PDF后其他章节控制Agent能够读取跨章节完整逻辑；禁止D001特异硬编码，保持冻结目录哈希、来源一一对应和旧工件兼容。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审阅FrozenCatalogItem、官方规则目录、流程必做目录及ProtocolControlPlanning链，提出最小合同迁移与失效关闭边界。 | `runs/execution/phase5-slice60zn-authoritative-target-excerpts-20260828/worker_01.md` |
| `worker_02` | 在共享合同和两个目录构建器中实现可选逐字来源摘录，并由KnownOfficialRuleTarget/KnownRequiredProcedureTarget原样传给控制Agent；不得修改临床源文件。 | `runs/execution/phase5-slice60zn-authoritative-target-excerpts-20260828/worker_02.md` |
| `worker_03` | 补充官方规则多来源、流程表多来源、旧目录兼容、长度/定位不一致拒绝及打包器传递回归，运行聚焦与协议层检查。 | `runs/execution/phase5-slice60zn-authoritative-target-excerpts-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
