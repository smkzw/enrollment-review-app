# Codex Execution Plan: phase5-slice58r2-provenance-and-five-package-semantic-validation-20260827

Objective: 修复限定包执行映射与检查点可能互相矛盾的持久化缺陷，随后在隔离目录中为D001当前第67、78、79、80、111包建立可审计的真实语义验证前置条件；保持claims_complete=false，不扩大到其余包、受试者或前端。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 在授权脚本和测试内修复既有包映射与丢失检查点场景的前置冲突核验，确保冲突选择不写入新检查点；补充决定性反例并运行聚焦回归。 | `runs/execution/phase5-slice58r2-provenance-and-five-package-semantic-validation-20260827/worker_01.md` |
| `worker_02` | 只读核查当前产品内置期别语义模型配置、oMLX运行入口、健康与模型身份验证方法、实际执行参数及速度质量测量字段，输出最小可复现实行命令，不调用模型。 | `runs/execution/phase5-slice58r2-provenance-and-five-package-semantic-validation-20260827/worker_02.md` |
| `worker_03` | 只读复核五个受影响包的临床主题、直接来源与标题族边界，形成真实模型输出的逐包验收矩阵；明确历史第79包只能人工对照且不得机械复用，识别此前执行报告中的过度结论。 | `runs/execution/phase5-slice58r2-provenance-and-five-package-semantic-validation-20260827/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
