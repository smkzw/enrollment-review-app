# Codex Execution Plan: phase5-nextflash-resume-20260903b

Objective: 从最新无损检查点恢复 Phase 5，修复规范化作业中断后的幂等复用，合法完成 SAR 31001 筛选期与基线期事实、Patient Profile 和原始证据临床 QC，并保持项目无关合同。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计并最小修复 fact normalization 在已有成功 call/candidate 但 step checkpoint 缺失时重复调用模型的问题；新增恢复与幂等回归，禁止修改临床规则或运行数据。 | `runs/execution/phase5-nextflash-resume-20260903b/worker_01.md` |
| `worker_02` | 只读核对当前 SAR 31001 作业、快照、租约和配置状态，给出旧 cancel_requested 作业合法终态对账及新受控筛选/基线作业入口；不得启动长任务或修改运行数据库。 | `runs/execution/phase5-nextflash-resume-20260903b/worker_02.md` |
| `worker_03` | 只读梳理 Phase 5 31001 事实发布、事件、用药暴露、Patient Profile、原始证据临床 QC 的剩余验收路径和确定性检查；不得以流程成功替代临床验收。 | `runs/execution/phase5-nextflash-resume-20260903b/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
