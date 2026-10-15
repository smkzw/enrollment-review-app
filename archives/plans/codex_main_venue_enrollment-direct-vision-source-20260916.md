# Codex Main-Venue Plan: enrollment-direct-vision-source-20260916

Date: TODO
Objective: 独立只读审阅当前源码中原件双VLM去OCR前置依赖的最小修改。重点检查 evidence_upload_service新任务preparation_policy、evidence_processing_executor跳过外部OCR但保留图像和native text、fact_normalization_source_adapter与job_service仅在include_visual_sources且绑定coverage时允许无OCR页。追踪真实消费者、原件归属/哈希/视觉locator/历史任务恢复，指出会使新上传流程不能继续或错误采信的缺陷。也审阅mtplx_owned_server仅进程驱动尚未正式接线的取消/所有权问题。禁止写应用/原临床库/原件，禁止启动模型或调用推理，禁止递归派发，不新增测试或全面跑套件；仅源码与必要只读命令，报告file:line和确证路径，不以编译通过代表临床验收。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/enrollment-direct-vision-source-20260916/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
