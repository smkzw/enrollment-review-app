# Conference Context: acceptance-protocol-cost-20260916

Created: 2026-09-16 10:29:32 CST
Objective: 只读审阅真实SAR解构失败的来源政策Schema修复及跨批上下文成本；基于冻结请求与源码指出安全的最小优化，不做临床验收，不修改产品或资料。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `acceptance-protocol-cost-20260916`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read-only: app/agents/protocol_deconstructor.py, app/agents/protocol_semantic_transport.py, app/domain/contracts/agent_io.py; their directly used schema helpers if necessary.
- Read-only: tests/v2/agents/test_protocol_source_policy_generation.py; artifacts/acceptance-20260916/source-policy-generation.xml and source-policy-adjacent.xml.
- Frozen evidence: artifacts/acceptance-20260916/fresh-sar-protocol/execute/execute_record.json and execute/receipts/request-*.json, receipt-*.json, response-*.json. Read bounded excerpts, do not dump all full files. No other clinical documents/DBs or credentials.

## Scope

- In scope: challenge new generation-only explicit source-policy requirements; verify old persisted read compatibility; examine whether GLM batching carries unnecessary prior history, why supports_bounded_batch_context is local-only, and whether enabling bounded contexts would lose source context. Recommend a concrete bounded comparison/check before any route-wide change. Check prompt/Schema mismatch and remediation scope.
- Out of scope: all writes, runtime/model calls, package installs, delegation/Explore subagents, browser/server/DB access, private configuration or network research. This is advisory code review, not clinical judgment. Bash may be unavailable; use read tools and report limitations rather than spawning children.
- Return findings by severity, exact file/line or receipt evidence, minimum remedy, counterexamples, and verification gaps. Do not declare passing tests from static function counts. State if no material defect found. No automatic fallback authorized in this pass; owner handles terminal errors.

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

- 2026-09-16 10:29:32 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
