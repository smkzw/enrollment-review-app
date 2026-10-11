# Codex Execution Plan: phase5-slice61bi-mtplx-structured-output-diagnosis

Objective: 定位 MTPLX 长提示词与严格结构化输出组合导致 500 的真实边界；仅使用非临床诊断夹具，保留服务端证据，必要时实施最小系统修复并验证，不运行真实方案重放。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 检查 MTPLX 服务端 response_format、异常处理和 flight recorder 路径，形成可验证故障假设。 | `archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/phase5-slice61bi-mtplx-structured-output-diagnosis/worker_01.md` |
| `worker_02` | 运行非临床诊断矩阵，隔离提示长度、Schema 大小和严格结构化输出的影响。 | `archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/phase5-slice61bi-mtplx-structured-output-diagnosis/worker_02.md` |
| `worker_03` | 依据证据实施最小修复或记录外部基础设施阻断，并完成确定性回归与恢复检查点。 | `archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/phase5-slice61bi-mtplx-structured-output-diagnosis/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

已由 Codex 完成有限范围验收；执行过程已归档，见 `archives/execution/phase5-slice61bi-mtplx-structured-output-diagnosis/cleanup_manifest.json`。当前恢复入口为 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_VITAL_SIGN_MODALITY_AR_ACCEPTED.md`。
