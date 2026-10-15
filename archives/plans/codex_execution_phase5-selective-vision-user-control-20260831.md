# Codex Execution Plan: phase5-selective-vision-user-control-20260831

Objective: 为已冻结证据修订提供选择性视觉核验的用户可读状态、失败范围、人工重试与取消闭环，复用现有持久任务机制，不暴露模型/日志/工程字段，不改变OCR与临床语义。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审阅现有Job、证据修订、观察仓储和API边界，提出最小稳定关联与失败关闭方案；不得修改任何文件。 | `runs/execution/phase5-selective-vision-user-control-20260831/worker_01.md` |
| `worker_02` | 作为唯一生产代码写者，实现后端查询投影、重试/取消校验及前端证据工作台中文状态交互；复用现有任务接口和组件，不新增依赖。 | `runs/execution/phase5-selective-vision-user-control-20260831/worker_02.md` |
| `worker_03` | 只新增或修改本切片专属测试文件，覆盖任务关联、错误类型、重试/取消、刷新恢复、中文文案与无内部字段泄露；不得修改生产文件。 | `runs/execution/phase5-selective-vision-user-control-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
