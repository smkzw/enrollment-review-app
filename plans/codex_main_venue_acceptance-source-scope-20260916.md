# Codex Main-Venue Plan: acceptance-source-scope-20260916

Date: TODO
Objective: 只读独立审核本工作树方案解构生成合同。范围：app/agents/protocol_deconstructor.py、app/domain/contracts/agent_io.py、tests/v2/agents/test_protocol_source_policy_generation.py、artifacts/acceptance-20260916/source-scope-review-input.json。先核各首批、后续、结构纠错、局部修订和provider schema的source_span_ids生成约束与实际来源校验是否一致、有无误排合法来源、缓存身份遗漏。再对冻结原文和实际单条模型正文检查是否增造资料义务、时点或政策；仅指出有来源支持的缺陷，不作全方案或临床签收。报告按严重度列证据文件:行、最小通用修复建议及未核实项。不读模型reasoning_content，不读本工作树外临床资料，不写任何源代码，不代为解构、不调用产品模型、不递归派发。仅写指定报告。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/acceptance-source-scope-20260916/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
