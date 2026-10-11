# Codex Execution Plan: phase5-segment-capability-checkpoint-recovery-20260901

Objective: 修复真实 GLM 父规则分段探针暴露的通用机制缺陷：将分段能力与 compact wire 解耦，按确定性分段身份持久复用成功结果，区分远端超时与 Schema 错误并仅对同模型同分段有限恢复；不得加入项目、疾病、药物、量表、条款号或时间点硬编码，不得恢复 D001 或改写冻结临床源与旧探针。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读追踪 GLM 传输能力声明、父规则分段进入条件、并发执行、错误映射、缓存/检查点接口及调用方；提出最小通用修复边界和兼容性风险，不修改生产文件。 | `runs/execution/phase5-segment-capability-checkpoint-recovery-20260901/worker_01.md` |
| `worker_02` | 单写者实施通用修复：独立的父规则分段能力声明；来源哈希、提示版本、模型身份、分段身份组成的成功段检查点；同模型同分段有限超时恢复；超时与 Schema 错误分离；保持部分结果不可发布和跨 provider 不拼接。 | `runs/execution/phase5-segment-capability-checkpoint-recovery-20260901/worker_02.md` |
| `worker_03` | 独立编写并运行对抗测试：GLM 可进入分段、非分段传输不误入、成功段复用、只恢复失败段、缓存身份漂移失效、超时分类、并发上限、合并完整性、失败关闭及项目特异硬编码扫描；不得改生产实现。 | `runs/execution/phase5-segment-capability-checkpoint-recovery-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
