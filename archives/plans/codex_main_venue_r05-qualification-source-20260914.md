# Codex Main-Venue Plan: r05-qualification-source-20260914

Date: 2026-09-14（派发合同见prompt，此索引事后补齐）
Objective: Read-only challenge of new binding qualification producer, source/receipt/prompt/JobRunner correctness and clinical boundary; find blocking defects with exact source evidence, no runtime/model/tests.

## Task Decomposition

一个独立C03只读源码审阅，Codex核对建议并修复。无额外主席或重复实施者。

## Source Packet

四个binding_qualification模块与现行设计/Plan、实际候选任务和控制合同；完整read set在prompt。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/r05-qualification-source-20260914/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

exit0，无fallback，一轮，完整报告已读；session与用量见metrics。无未结束等待。

## Codex Verification Checklist

源码逐项复核、编译、标准库全局名检查及diff。未执行阶段测试/运行/临床/视觉检查，不能报最终通过。
