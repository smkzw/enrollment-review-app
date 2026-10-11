# Codex Main-Venue Plan: r3-gemini-format-boundary-review-20260909

Date: TODO
Objective: 只读独立工程复查：当前app/llm/gemini_transport.py、gemini_oauth.py、page_review_format_repair.py、page_review_harness.py及执行/回执/恢复消费者与相关tests。产品当前仅GLM low与Gemini3.7 high，原生OAuth直连而非个人harness。核验一次格式纠正同模型同图不删事实不改数值、严格失败边界、可取消、响应记录和版本闭包；Gemini原生SSE错误/截断/OAuth刷新与凭据不外泄、实际high后缀映射及预检。指出实质缺陷与最小修复，不写代码不读.env/个人配置/临床原件，不调用模型/网络，不递归派发。产品已有真实24页18通过，一次失败页重读22通过，剩两页格式错；这些数量不是临床验收。不要依赖执行者论述，以当前代码与测试为据。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/r3-gemini-format-boundary-review-20260909/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
