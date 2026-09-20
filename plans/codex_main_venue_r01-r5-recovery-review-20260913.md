# Codex Main-Venue Plan: r01-r5-recovery-review-20260913

Date: 2026-09-13
Objective: 只读审阅R01 r5失败证据与下一步最小恢复方案，区分来源语义、900秒超时、长事务；不修改产品、不调用临床模型，不把候选当采信。

## Task Decomposition

主线程直接执行数据核验；单个独立会商复核语义及恢复边界，因为候选来源存在解释分歧，不能靠结构测试关闭。先检验已冻结证据，再裁定最小修复，不增加产品模型调用。

## Source Packet

以同任务conference_context的Source Of Truth为完整源包；不要读取PROJECT_CONTEXT长历史替代原请求/代码。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `grok-build` | `grok-4.6` | `runs/conference/r01-r5-recovery-review-20260913/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

本次一轮，runner健康预检，最长7200秒；等待完成后核对实际路由/报告再采纳，不重派健康会话。

## Codex Verification Checklist

核对失败回执SHA、实际超时与无用量；11份回答不能代表完整双读；恢复须冻结身份一致，旧失败不可改写。核验建议不绕过来源校验，不扩自动采信。审阅终态后填reviews/metrics。
