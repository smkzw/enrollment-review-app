# Codex Execution Plan: phase5-selective-vision-postfreeze-orchestration-20260831

Objective: 在不阻塞OCR核心事务、不延长OCR租约、不改写OCR原文的前提下，将已验收的选择性视觉观察服务接入证据修订冻结后的独立持久任务；先修复远端VLM调用占用数据库事务的问题，并提供幂等入队、崩溃恢复、重复调用和失败关闭的确定性证据。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查EvidenceProcessingExecutor、JobRunner、JobService和选择性视觉服务，给出最小事务拆分与独立任务边界；不得写生产或测试文件。 | `runs/execution/phase5-selective-vision-postfreeze-orchestration-20260831/worker_01.md` |
| `worker_02` | 作为唯一生产代码写者，实现事务外VLM调用、短事务持久化以及冻结修订后的独立持久视觉后处理任务/执行器接线；不得修改测试、前端、D001或OCR核心页处理语义。 | `runs/execution/phase5-selective-vision-postfreeze-orchestration-20260831/worker_02.md` |
| `worker_03` | 只写新的独立测试文件，验证冻结修订只幂等入队且不等待VLM、远端调用不持有数据库事务、任务重复/恢复/失败关闭、原生文字跳过和OCR不可变；不得修改生产文件或既有测试。 | `runs/execution/phase5-selective-vision-postfreeze-orchestration-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
