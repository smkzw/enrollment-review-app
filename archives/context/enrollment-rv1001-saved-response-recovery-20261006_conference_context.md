# Conference Context: enrollment-rv1001-saved-response-recovery-20261006

Created: 2026-10-06 23:28:20 CST
Objective: 独立审阅同一失败调用原答恢复的请求身份、当前校验、保存与重启消费；不批准临床事实、不放松来源门禁
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

- Linked execution task: `enrollment-rv1001-saved-response-recovery-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read the six frozen files under artifacts/normalizer-saved-recovery-review-20261006, once each. Manifest binds base HEAD f2603a9f and each local patch hash. Packet contains complete affected definitions, synthetic tests and a sanitized zero-call production preflight summary; NO raw clinical material, credentials or database.
- Current connected test window: 173 passed, 5 third-party SWIG warnings, 130.73 seconds, exit 0. Preceding window: 160 passed / 12 failed because the new synthetic failed-job fixture omitted the real run-status callback; the fixture was corrected, not the retry guard. A first command failed collection due to a wrong test filename, exit 4.
- Real job has six saved successful groups, one failed and seven unexecuted. An original complete answer is currently source-valid after bounded partition; the later retry is still invalid (one invented loc1 locator). Recovery must not accept that new answer, mutate the original failed job or conceal selection/provenance.

## Scope

- In scope: audit explicit first-answer revalidation, exact current request/response/call identity, partition proof, lease-bound saving, checkpoint/finalizer restart checks and proof removal counterexamples.
- Out of scope: clinical approval, model reading, changing files, running tests, scanning the repository/history, contacting endpoints, reformulating clinical content, selecting other answers or extra models.
- Invocation uses an optional explicit executor mapping, disabled by default, not a new source library or public UI recovery feature. Reading method model_response means original source was a real model answer; response_recovery_sha256 and model_called=false explicitly distinguish no new read. Decide if this is sufficiently clear at affected consumers.

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

- 2026-10-06 23:28:20 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
