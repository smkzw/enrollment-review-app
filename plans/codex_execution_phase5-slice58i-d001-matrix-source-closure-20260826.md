# Codex Execution Plan: phase5-slice58i-d001-matrix-source-closure-20260826

Objective: 在不修改D001源方案的前提下，将D001 II其他章节控制矩阵的临时来源身份绑定到当前冻结全文清单，完成期别、关系、重复与严格来源闭包验证，并保留人工临床验收边界。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计当前25条其他章节控制、82行合并矩阵和冻结coverage manifest，给出临时su-cross来源到真实结构单元的确定性映射、重复/期别/关系风险及不能自动闭包的项目，不修改文件。 | `runs/execution/phase5-slice58i-d001-matrix-source-closure-20260826/worker_01.md` |
| `worker_02` | 基于审计结果实现最小通用映射与闭包路径，更新生成器或矩阵工件，禁止按source_ref模糊择优、禁止项目特异规则进入共享代码，并补充聚焦回归。 | `runs/execution/phase5-slice58i-d001-matrix-source-closure-20260826/worker_02.md` |
| `worker_03` | 独立运行严格来源、期别、时间、节点、逻辑、例外、重复关系验证，复核D001方案哈希和矩阵claims_complete边界，报告未闭合项并拒绝虚假完成。 | `runs/execution/phase5-slice58i-d001-matrix-source-closure-20260826/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
