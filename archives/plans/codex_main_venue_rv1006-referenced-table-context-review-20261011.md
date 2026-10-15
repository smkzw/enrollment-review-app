# Codex Main-Venue Plan: rv1006-referenced-table-context-review-20261011

Date: 2026-10-11
Objective: 只读评审冻结的原文明确表号上下文闭合：真实物理表身份、同号歧义、non_control只读准入、旧计划恢复和提示消费；不读临床、不改代码、不运行产品或测试

## Task Decomposition

只读独审物理表闭合、同号歧义、冻结清单与批次证明、恢复上下文及旧失败版本。所有者实施/验收；无其他执行者或主持人。

## Source Packet

context/rv1006-referenced-table-context-review-20261011_conference_context.md及该包route manifest；prompts/conference/rv1006-referenced-table-context-review-20261011/下三个实际prompt。原件/临床库/env不在顾问范围。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.7` | `runs/conference/rv1006-referenced-table-context-review-20261011/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

初审、followup、resume_validation_followup均完成exit0/no fallback，同会话3fc66dd8-25df-429a-ad24-1ec90fad5b9e，120分钟完成等待。不是重派或临床读取。实际runner回执留runs/conference本包；stdout不作为业务证明或公开交付。

## Codex Verification Checklist

顾问完成必要节点；所有者取舍/未决/运行边界见 .trellis/tasks/09-11-e2e-eligibility-review/reviews/rv1006-conditional-and-referenced-table-owner-disposition-20261011.md。工程审阅不代表规则采用或临床验收。
