# Codex Main-Venue Plan: enrollment-mtplx-release-20260916

Date: TODO
Objective: 只读审阅 app/llm/mtplx_owned_server.py 与 app/llm/mtplx_model_lifecycle.py 当前源码，核独立进程组退出、异常父退出、取消、跨进程flock及子进程继承的正确性。只给确证缺陷及文件行号、最小修订建议；不修改源码、不运行模型、不读取临床资料。不要将进程退出等同GPU内存完全释放，指出证据边界。另核 app/llm/page_review_harness.py v16显式region必填与既有PageReviewPayload验证一致性。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/enrollment-mtplx-release-20260916/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
