# Codex Execution Plan: phase5-slice61ag-conditional-waiver-scope-20260828

Objective: 修复方案控制解构中条件豁免被拆成无条件执行、同源候选乱序修订以及豁免证据过度声明问题，并以项目无关门禁和回归证明，不运行真实模型、不发布控制点。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 独立审查 protocol_control_gate.py 的条件豁免绑定、证据模态和跨候选范围，提出最小通用修复与反例测试，不修改临床来源。 | `runs/execution/phase5-slice61ag-conditional-waiver-scope-20260828/worker_01.md` |
| `worker_02` | 独立审查 protocol_control_deconstructor.py 同源多候选有界修订在乱序、重复、兄弟候选变化时的身份保持，补充或修订最小测试。 | `runs/execution/phase5-slice61ag-conditional-waiver-scope-20260828/worker_02.md` |
| `worker_03` | 独立核对 v6 p804 临床语义与现有测试覆盖，创建不可变重评记录并检查中文错误提示、完整方案层回归入口。 | `runs/execution/phase5-slice61ag-conditional-waiver-scope-20260828/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
