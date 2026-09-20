# Codex Execution Plan: phase5-selective-vision-observation-sidecar-20260831

Objective: 为选择性视觉核验建立不可变观察侧车持久化合同、仓储和证据服务后置钩子；只消费已生成的页产物与OCR质量，不改变OCR原文、缓存、租约、方案语义或D001任务。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审阅现有证据合同、SQLAlchemy模型、仓储、迁移和证据处理服务，提出最小观察侧车身份、外键、幂等、失败状态与服务接入边界，不修改文件。 | `runs/execution/phase5-selective-vision-observation-sidecar-20260831/worker_01.md` |
| `worker_02` | 作为唯一生产代码写入者，实现通用视觉观察侧车合同、SQLAlchemy模型、0019迁移、仓储及显式证据服务后处理接口；不得修改测试、OCR执行器核心语义、方案模块、前端或D001工件。 | `runs/execution/phase5-selective-vision-observation-sidecar-20260831/worker_02.md` |
| `worker_03` | 仅新增独立测试文件，覆盖0019迁移、仓储追加/幂等/来源闭包、服务显式调用、原生文字跳过、失败关闭且不改OCR；不得修改生产文件。 | `runs/execution/phase5-selective-vision-observation-sidecar-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

- 合同/仓储必须追加不可变、来源闭包、同一身份幂等复用且冲突拒绝。
- `0019` 必须可升级/降级，并在当前迁移链和空库上验证。
- 服务只能显式消费选择性规划与已落盘页身份；原生文字跳过时不调用模型，失败时不写成功观察、不改OCR。
- 运行迁移、仓储、服务聚焦测试及证据相关回归；真实远端调用不是本切片持久化验收的必要条件。
- Codex复核所有源文件、差异和测试，写验收记录后再运行治理审计；不以worker自报完成代替验收。
