# Codex Execution Plan: r05-real-action-worklist-20260914

Objective: 实现正式待办只读清单服务和薄API，复用已有冻结审核历史与ActionRequest，不读trial，不新建状态机。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 新增app/services/review_action_worklist.py及app/api/v2/review_action_worklist.py：项目作用域、分页、真实冻结审核来源、历史未办结不静默消失；仅源码实现，禁止测试/数据库/模型/浏览器，不注册应用、不改既有文件。 | `runs/execution/r05-real-action-worklist-20260914/worker_01.md` |

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
