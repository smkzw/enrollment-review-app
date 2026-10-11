# Codex Main-Venue Plan: phase5-slice61ak-v8-bounded-repair-audit-20260828

Date: TODO
Objective: 只读独立审查 Phase 5.8d v8 失败后新增的有界修订隔离：当一个来源键内有多个候选且仅一个位置获授权时，模型对不同来源候选的越界改写应由系统恢复上一轮内容；同源未授权兄弟、候选数量变化或来源分区变化仍必须拒绝。核对实现、28项聚焦测试、988项方案层回归、v8真实第4到第5次离线恢复，以及恢复后仍被CONDITIONAL_EXEMPTION_SCOPE_SPLIT拒绝的临床边界。不得修改文件、不得启动模型重放、不得发布控制点。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_antigravity` | `google-antigravity` | `gemini-3.7-flash` | `runs/conference/phase5-slice61ak-v8-bounded-repair-audit-20260828/general_pi_antigravity.md` |
| `general_grok46` | `grok-build` | `grok-4.6` | `runs/conference/phase5-slice61ak-v8-bounded-repair-audit-20260828/general_grok46.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
