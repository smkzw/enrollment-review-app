# Codex Main-Venue Plan: enrollment-context-benchmark-review-20260908

Date: TODO
Objective: 只读审阅产品逐页harness上下文组织对照方案：检查app/llm/page_review_harness.py、app/projections/page_review_prompt_pack.py及领域合同、scripts/run_frozen_product_reader.py，提出最小可用于产品的逐页短上下文、关联页小批、整批对照设计，保留所有临床条件和来源。不调用被测模型、不读取.env/OMP/Hermes配置或原始病例、不改文件；审阅现有长规则重复输入与schema失败如何归因，给出具体可验证的建议与代码位置。最终临床验收不在范围内。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `zcode` | `GLM-5.3-Flash` | `runs/conference/enrollment-context-benchmark-review-20260908/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
