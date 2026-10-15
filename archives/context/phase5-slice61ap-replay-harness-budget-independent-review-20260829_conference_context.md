# Conference Context: phase5-slice61ap-replay-harness-budget-independent-review-20260829

Created: 2026-08-29 03:35:15 CST
Objective: 只读独立审查 Phase 5.8d 模型无关方案重放 harness 与串行修订预算合同。挑战原始 DOCX 到稳定 source_ref 包的真实产品链、人工矩阵及项目特异依赖隔离、来源哈希和时间钉住、本机路径泄漏、整包外部指纹、双运行可重现性、全局修订预算与无进展终止。核对 Codex 修订后的实际代码与测试，不运行临床模型，不发布控制点，不把 DOCX-only 写成 PDF 已支持。
Task type: `complex_delivery_conference`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
- This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy-cli/deepseek-v4-flash:max -> grok-build/grok-4.6:medium -> cursor/cursor-grok-4.6:medium -> openai-codex/gpt-5.6-luna:max`; it is resolved once at packet creation and filtered against the actual execution route nodes recorded below before dispatch.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `phase5-slice61ao-replay-harness-budget-contract-20260829`
- Execution evidence status: `linked`
- Excluded provider/model nodes: `codebuddy-cli/glm-5.3-flash`, `mtplx/mtplx-qwen38-27b-optimized-quality`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `app/protocols/protocol_replay_harness.py`
- `scripts/run_protocol_replay_harness.py`
- `app/agents/protocol_control_deconstructor.py`
- `app/protocols/protocol_control_repair_errors.py`
- `tests/v2/protocols/test_protocol_replay_harness.py`
- `tests/v2/protocols/test_slice61ao_repair_budget_contract.py`
- D001 p803-p805 test-only config and checkpoint under the active Trellis task.
- Linked execution reports and Codex's own test/double-build evidence.

## Scope

- In scope: model-free DOCX product chain, deterministic pack identity, path isolation, external fingerprint, toolchain provenance, repair budget, structured error classes and independent challenge.
- Out of scope: clinical model replay, control publication, PDF-to-structure implementation, subject review, OCR, Patient Profile, frontend and browser acceptance.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; explicit user routes also proceed when the catalog is stale or incomplete, while a genuinely missing CLI or native transport boundary may block. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-08-29 03:35:15 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-08-29: Initial independent pass identified F1-F6; Codex implemented bounded corrections and ran focused/full regression plus two D001 model-free builds.
- 2026-08-29: Same session `0d351472-ed0c-499a-b38c-314106f37570` resumed for targeted round 4; reviewer confirmed F1-F6 closed and retained PDF/clinical boundaries.
