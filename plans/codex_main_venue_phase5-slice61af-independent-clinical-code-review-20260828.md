# Codex Main-Venue Plan: phase5-slice61af-independent-clinical-code-review-20260828

Date: TODO
Objective: 只读独立复核 Phase 5.8d 病毒学 p803-p805 条件性豁免与同源候选定向修订。本轮不是视觉测试。请从三个角度挑战：1）代码是否真正防止把“无需再次检查”误判为必须执行的筛选操作、是否完整识别要求证明“未重复执行”的过度证据；2）同一来源单元拆出多个候选后，按上一轮 wire 位置定向修订是否会导致范围外改写、错位、候选丢失或错误放行；3）真实 v6 工件的三个控制点是否忠实于 body.p804/p805，并避免重复流程第14项和 EX-22。必须读取当前源代码、相关合成测试、v5失败工件与v6接受工件及父级验收摘要；发现问题须给出文件/字段/可复现路径。只读，不修改文件，不把测试通过当作临床接受。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_pi_antigravity` | `google-antigravity` | `gemini-3.7-flash` | `runs/conference/phase5-slice61af-independent-clinical-code-review-20260828/general_pi_antigravity.md` |
| `general_grok46` | `grok-build` | `grok-4.6` | `runs/conference/phase5-slice61af-independent-clinical-code-review-20260828/general_grok46.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
