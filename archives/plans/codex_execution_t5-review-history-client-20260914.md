# Codex Execution Plan: t5-review-history-client-20260914

Objective: 实现正式审核历史只读前端HTTP适配器，供后续报告页读取固定审核记录；不读取实时投影、不计算临床结论。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只允许新增frontend/src/api/review-history/reviewHistoryTypes.ts和reviewHistoryHttp.ts；读取app/api/v2/review_history.py作为API合同、现有eligibility-review HTTP及严格解码模式。提供listRuns/getRun及完整类型/运行时校验，含run/context/assessments/actions/transitions；检查路径归属、上下文与run绑定、重复身份、动作引用结论、状态与时间一致性，未知值拒绝。公开工厂支持fetch注入和signal；错误复用EligibilityReviewApiError以接现有useLoad。不得修改其他源码、测试、数据库、配置；不得运行模型、浏览器、测试套件、服务器；可作tsc noEmit编译并如实区分已有报错。不创建测试文件。不把当前任务当临床验收，输出到指定worker报告。 | `runs/execution/t5-review-history-client-20260914/worker_01.md` |

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
