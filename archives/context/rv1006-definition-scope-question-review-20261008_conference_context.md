# Conference Context: rv1006-definition-scope-question-review-20261008

Created: 2026-10-08 09:13:47 CST
Objective: 只读核查局部定义依赖疑问与全量范围核对接线，给出保留源含义未知和旧回执的最小恢复建议；不实施不读取临床原件不改运行任务
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

- Linked execution task: `rv1006-definition-scope-question-review-20261008`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Code HEAD 8b1cb65e, current worktree. Source files listed in the prompt are frozen for this review; the owned isolated product Job continues on the same code, and is not your assignment.
- `app/services/protocol_control_definition_scope.py` (complete 1-135): inventory builder drops local unresolved reasons; closer retains non-sentinel reasons even when global choice is complete.
- `app/agents/protocol_control_definition_scope.py` (complete 1-110): global Schema and prompt; no field binds a local question to a checked resolution.
- `app/services/protocol_control_execution.py:4153-4310`: merges statement, target review and declaration questions into the same unresolved string set; `4524-4710`: scope production, persistence and readback.
- `app/agents/protocol_control_source_interpretation.py:787-821,908-1050,1855-1945`: actual local registration contract, prompt and validator.
- `app/domain/contracts/protocol_controls.py:2100-2140`; `app/services/protocol_control_catalog_publication.py:256-357`: existing fail-closed release.
- `tests/v2/services/test_control_definition_scope.py:1-230`: existing genuine-unknown, missing registration and scope disagreement counterexamples. Review these exact existing definitions, not repository history.
- Owner-only real checkpoint observation: first three source groups are saved; some declaration questions ask whether different wording or a target outside the local list shares the definition. They are not missing local calls. No real source text, IDs, DB, model answers or patient data are provided to the reviewer. This observation is not an independent semantic approval.
- Synthetic distinction for review: (1) definition itself has an ambiguous time anchor; (2) definition is sourced and clear, but local registration asks whether target B in another chapter consumes it; (3) registration has no genuine receipt. All three currently become unresolved strings, but only (2) could be resolved by a sufficiently sourced complete-scope review.

## Scope

- In scope: challenge the diagnosis, compare the smallest alternatives for carrying the local question through a source-bound global check versus rerunning only local registration with justified added context. Explain what evidence would be required, which original uncertainties must remain, and which downstream contracts must revalidate.
- Out of scope: no implementation, tests, shell, network, credentials, databases, clinical files, product calls, any running Job, global settings, cleanup, publication or approval. No new framework or duplicate rule/fact store. No removal of questions based solely on model confidence, word matching or majority vote.
- Recommend only after distinguishing record origin, scope question, source meaning and technical missing proof. Do not assume a future global choice will be complete or medically correct; the actual global step is not yet run.
- Current execution mode is direct integration plus one bounded C03 because changing the handling of unresolved scope evidence is materially interpretive. Healthy product work continues unchanged. Codex decides whether any recommendation enters the frozen delivery window after decisive evidence; this packet is not migration authority.

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

- 2026-10-08 09:13:47 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
