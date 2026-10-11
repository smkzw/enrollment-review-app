# Conference Context: rv1006-exception-field-review-20261011

Created: 2026-10-11 15:18:15 CST
Objective: 只读审阅单条来源例外限定补正、保存恢复与受影响消费者；只看源码和合成用例，不读真实临床材料，不修改文件，不调用产品模型
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `rv1006-exception-field-review-20261011`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen code basis 53cdd1bb plus current diff limited to app/agents/protocol_control_source_function.py, app/agents/protocol_control_deconstructor.py, app/services/protocol_control_execution.py and tests/v2/protocols/test_slice58c_control_deconstructor.py.
- Read complete changed functions in source_function; Runner.run changed source_exception_field_repair history/dispatch blocks and their consumers; service _saved_source_scope_question_history and _validate_saved_source_review; candidate_alignment validate_candidate_alignment/bind_candidate_alignment. Use git diff for exact bounded scope, not broad history.
- Synthetic tests source_exception_field*, source_function_field*, action_with_source_exception* (last is in tests/v2/agents/test_protocol_control_candidate_alignment.py). Read tests, do not execute them. No clinical material or prior reviewer reasoning in scope.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: does single-statement exception_words/unresolved repair freeze all other fields and raw siblings, preserve honest uncertainty and fresh semantic/source binding, share source budget, persist attempted history through failures, reject corrupted or changed history before another request, and legally save/read/consume the result? Challenge both safe rejection and useful valid result.
- Out of scope: /Users/smkzw/tmp, databases, env, raw protocols/case documents/answers, clinical approval, model calls, tools that write files or run tests. This is a code-only read-only advisory. No generic rewrite, new framework, queue, or clinical special case.

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

- 2026-10-11 15:18:15 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
