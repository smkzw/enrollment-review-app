# Codex Execution Plan: r3-two-main-readers-only-20260908

Objective: 删除过时手写第三读产品实现，完整接通双主读与规范化回放

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 仅修改当前worktree的app与tests/v2中页级判读相关源码和测试。用户明确新产品只允许GLM low main-A与MTPLX mtplx-flash-next-optimized-speed high main-B，MTPLX不是手写第三读，不保留旧第三读功能、配置、提示、代码注释或旧功能备份。删除活动harness中C配置/预检/提示/模型调用及临时provider条件保留C的实现；删除不用的第三读合同/枚举/检查。手写[]必须继续由A/B各自完整输出，双源一致才采信，分歧保留。清除对账中的第三读trigger/missing假设，并同步coverage selection/normalizer重放等全部消费者；特别当前page_review_coverage_selection.py重放仍默认handwriting_third_read_expected=True，而新产品实际False，会造成正常覆盖不能用于整理，必须用正式HTTP测试覆盖。复用当前持久任务与来源合同，版本化新语义，保留已完成主读的取消/恢复验证，不改原始资料或数据库。原有已应用迁移不要改写，不运行数据迁移或模型，只读源码，可用本地pytest；如需新迁移只建立确定性新增迁移并测试，禁止删除历史数据。不得访问.env、临床artifacts、home配置、网络、浏览器或执行别的harness，不递归派发。不要改docs/plans/.env.example，Codex会处理。只清这项旧功能，不删正常手写提取功能，不扩大到其他模型路由重构。不创建旧代码备份或清理报告文件；仅向runner返回实施结果、准确测试、剩余限制。优先标准库最小完整修改。运行相关合同/执行/正式API/存储测试，旧第三读测试改成双主读和禁止第三票的反例，不通过删正确性断言凑绿。当前取消辅助与正式resume是主线程已完成的新功能须保留。 | `runs/execution/r3-two-main-readers-only-20260908/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
