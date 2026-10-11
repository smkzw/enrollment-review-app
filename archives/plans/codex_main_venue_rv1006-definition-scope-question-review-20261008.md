# Codex Main-Venue Plan: rv1006-definition-scope-question-review-20261008

Date: 2026-10-08
Objective: 只读核查局部定义依赖疑问与全量范围核对接线，给出保留源含义未知和旧回执的最小恢复建议；不实施不读取临床原件不改运行任务

## Task Decomposition

已完成一次有界源码审阅；登记恢复包另完成两次同会话定向复核。主集成负责生产、验证与采用边界，不新增管理节点。

## Source Packet

context同ID和prompts/conference同ID冻结读窗；结果runs/conference同ID，处置reviews同ID。只读源码/合成测试，不读临床原答。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `codebuddy-cli` | `deepseek-v4.1-flash` | `runs/conference/rv1006-definition-scope-question-review-20261008/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

实际终态均exit0/no fallback，120分钟静默完成等待；用时、工具调用、未知tokens见metrics同ID。不因慢重派，后续同会话不是新模型独立意见。

## Codex Verification Checklist

所有者核实际源码、相连正反例及只读恢复身份；不以顾问信心、引文或检查数量证明完整要求包/病例完成。限制及未完成见reviews同ID和现行implement。
