# Codex Main-Venue Plan: r3-durable-reader-review-20260906

Date: TODO
Objective: 只读审阅 R3 页任务调度、成功结果逐读道持久化、恢复身份与原响应留存。范围仅 app/workflow/runner.py、app/services/page_review_job_service.py、page_review_job_executor.py、page_review_recovery.py、相关合成测试。禁止读取 .env、临床源文件、artifacts 中临床内容、任何外部 harness 配置；禁止修改代码或调用产品模型。依据代码独立查明：并行波次是否延迟已成功结果提交，进程死亡/取消/租约丢失下是否丢成功读道，旧任务新增execution_control兼容是否过宽，response_attempts在失败恢复中的缺口。给出有文件行号的风险与最小完整修复建议和测试。不作临床结论。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `zcode` | `GLM-5.3-Flash` | `runs/conference/r3-durable-reader-review-20260906/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
