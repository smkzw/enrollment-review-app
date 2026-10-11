# Conference Context: enrollment-rv1001-front-partition-20261006

Created: 2026-10-06 20:56:48 CST
Objective: 只读审阅现有FLOW的前置逐项关系隔离：真实冻结诊断25陈述19单项合法6关系失败、8物理来源单元中3受影响，10合法点处于无失败单元。是否可在保留全范围硬门禁、原始错误、完整来源、旧预算与终态的条件下，将关系未核单元保持技术pending，仅为其他已核独立单元保存部分装配及有界作者成果；不得将坏提案变临床未决或合法采用。评估依赖/恢复/完整消费及预算边界，给最小可执行建议或否决，不加新框架/数据库/证明真相。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-rv1001-front-partition-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Current code at 366288c4: `app/agents/protocol_control_fixed_flow.py`, `app/agents/protocol_control_source_interpretation.py`, `app/agents/protocol_control_stage_compiler.py`, `app/llm/logical_call_budget.py`. Locate the source-only checkpoint/partial-wire consumers in `app/services/protocol_control_execution.py` and `app/agents/protocol_control_deconstructor.py` only if needed. Tests: locate existing front-stage-flow tests with rg before reading; do not invent file paths.
- Owner's read-only real-source diagnostic: 25 source statements, 19 pass individual relation checks, six reject, eight physical units, three affected units, ten individually valid statements in unaffected units. These ten have ZERO current compiler-supported statement indexes. Their decisions: one covered_by_official, two not_current_control, six additional_requirement, one background_context. This is diagnosis, not independent clinical truth or adoption evidence. No clinical excerpts are supplied to this adviser.
- Rejections: two TARGET_ACTION_LABEL_ONLY_UNPROVEN, two FREQUENCY_ONLY_COVERAGE, two TARGET_ACTION_UNGROUNDED. Old task budget exhausted 6/6, old terminal/database unchanged. Prior once-only correction fixed a single statement but whole review still failed. The latest P2 bounded question fix was committed/pushed separately and is out of this code scope.

## Scope

- In scope: challenge whether relation partition has an actual consumer benefit given zero independently compilable unaffected points; inspect capability causes and the whole-batch proof/checkpoint gates. Recommend the smallest useful next change or explicitly reject partition implementation. Separate preserving audit facts from authoring, final adoption and source fidelity.
- Out of scope: file edits, tests or commands that change data, clinical material/env/database/tmp reads, models/browser/shell/network calls, creating a second proof truth table, new frameworks, increasing or resetting the old task budget. Read-only source tools enabled, no recursive dispatch. Read at most ten complete relevant definitions plus immediately necessary referenced contracts; no whole-history scan.
- If an ungrounded quote/identity error cannot be safely confined, say so. A single-item green is not full-batch proof; don't certify dependency isolation from numerical counts. Do not recommend implementation merely to make the audit green or increase preserved item counts.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Conference Pass Rule

This packet uses one serial Codex-led conference object. Each declared role receives one complete prompt and may use multiple internal tool turns. Codex decides whether a same-session follow-up is needed after reviewing the result; follow-ups do not create a new conference or change the route identity.

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

- 2026-10-06 20:56:48 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
