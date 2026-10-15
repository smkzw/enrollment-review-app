# Codex Execution Plan: phase5-slice58g-phase-rationale-quality-20260826

Objective: 建立期别语义Agent理由完整性与处置一致性的通用质量门，使含中文但语义残缺或未说明本期、对侧期、两期共用、待确认依据的回包自动进入同会话修复，同时避免项目特异硬编码。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计现有中文理由校验、四类处置语义和真实坏回包，提出可解释、低误伤的通用完整性合同及反例。 | `runs/execution/phase5-slice58g-phase-rationale-quality-20260826/worker_01.md` |
| `worker_02` | 实现处置特异的理由完整性校验与中文修复提示，覆盖v1/v2 wire但保持历史结构可读，不改领域身份和来源闭包。 | `runs/execution/phase5-slice58g-phase-rationale-quality-20260826/worker_02.md` |
| `worker_03` | 增加合成与真实坏回包回归，证明该段为方案摘要中一类残句被拒绝、合格理由仍通过，并跑期别Agent及相关协议测试。 | `runs/execution/phase5-slice58g-phase-rationale-quality-20260826/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
