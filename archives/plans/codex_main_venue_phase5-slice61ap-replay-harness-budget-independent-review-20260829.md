# Codex Main-Venue Plan: phase5-slice61ap-replay-harness-budget-independent-review-20260829

Date: 2026-08-29
Objective: 只读独立审查 Phase 5.8d 模型无关方案重放 harness 与串行修订预算合同。挑战原始 DOCX 到稳定 source_ref 包的真实产品链、人工矩阵及项目特异依赖隔离、来源哈希和时间钉住、本机路径泄漏、整包外部指纹、双运行可重现性、全局修订预算与无进展终止。核对 Codex 修订后的实际代码与测试，不运行临床模型，不发布控制点，不把 DOCX-only 写成 PDF 已支持。

## Task Decomposition

1. Independently trace raw DOCX through the actual product chain without invoking a model.
2. Challenge determinism, source identity, external anchoring, project isolation and repair-budget semantics.
3. Convert material findings into bounded shared-contract fixes and deterministic tests.
4. Resume the same reviewer session to verify each fix, then let Codex run acceptance checks.

## Source Packet

- Product harness, CLI, repair-budget implementation and focused tests.
- Test-only D001 source/config/checkpoint under the active Trellis task.
- Linked execution packet and immutable v8 rejection boundary.

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `codebuddy-cli` | `deepseek-v4-flash` | `runs/conference/phase5-slice61ap-replay-harness-budget-independent-review-20260829/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- Initial pass completed in 315.602s with 43 tool calls.
- Targeted same-session continuation completed in 129.069s with 17 tool calls after a 26.121s continuation setup round.
- No timeout, terminal failure or fallback occurred; the same session id was retained.

## Codex Verification Checklist

- Confirm F1-F6 against current files rather than prose.
- Run focused and full protocol tests independently of the reviewer.
- Rebuild D001 twice into different temporary directories and compare external fingerprints and identities.
- Validate JSON, compile Python, run `git diff --check`, and retain no-model/no-publication boundary.
- Record PDF structural ingestion as incomplete.
