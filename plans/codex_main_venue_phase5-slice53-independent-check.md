# Codex Main-Venue Plan: phase5-slice53-independent-check

Date: TODO
Objective: 只读独立审查 Phase 5.3 Evidence Normalizer 与持久运行的未提交实现。重点检查：审核节点/资料类型/来源方/记录时间/EvidenceRequirement 是否进入冻结输入及幂等哈希；活动权威、页闭合、locator 真实性、空输出、租约丢失、重启幂等是否存在绕过；不得修改文件，不得把测试通过当作验收。输出按严重度列出具体文件与问题；无问题时明确残余风险。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_qwen38` | `alibaba` | `qwen3.8-max` | `runs/conference/phase5-slice53-independent-check/general_pi_qwen38.md` |
| `general_grok46` | `grok-build` | `grok-4.6` | `runs/conference/phase5-slice53-independent-check/general_grok46.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
