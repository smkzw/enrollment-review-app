# Conference Context: enrollment-rv1001-target-scope-cause-20261006

Created: 2026-10-06 22:55:00 CST
Objective: 查明来源目标核对把日内建议与访视范围混淆的首因，只审冻结有源两条记录和有界校验定义，不关闭门禁、不盲重读
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

- Linked execution task: `enrollment-rv1001-target-scope-cause-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen artifacts/clinical-source-review-20261006/{source.json,manifest.json,protocol_control_source_interpretation-definitions.txt,protocol_control_gate-definitions.txt}, bound to f2603a9fea5dfc0615abf5a1c0d5f21915168d8c. Local controlled source, excluded from Git delivery; no patient DB or original document browsing.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: only artifacts/clinical-source-review-20261006/{source.json,manifest.json,protocol_control_source_interpretation-definitions.txt,protocol_control_gate-definitions.txt}. Actual protocol source and target traces are locally controlled and Git ignored, not patient records. Frozen commit f2603a9fea5dfc0615abf5a1c0d5f21915168d8c. Read these files once with read tools, no recursive source exploration. Packet extraction omits unrelated dependencies; unknown behavior must be reported, not inferred.
- Out of scope: writes, shell, tests, directories, credentials, databases, browser, network, any other source or artifact; no medical/adoption approval, no new model/framework, no whole-protocol rerun.

Two actual production target reviews rejected indexes 14/19, TARGET_VISIT_SCOPE_UNPROVEN. Latest once-only request used current v6 prompt with force and real shared-location context; 41.555 seconds, one call, source hashes unchanged. It returned the same morning-use advice as covered_by_procedure for two individual visit targets. Determine whether the first error is missing source scope/dependency in SourceInterpretation, a known bad target proposal, an overly broad guard conflating within-day time with visit scope, or an actual source ambiguity. Do not choose by model confidence or relax a guard only to pass. Compare concrete source/action/object/period evidence and the frozen target excerpts. Scope_quote is null in both statements; classify what that does and does not prove.

Recommend one smallest coherent next action with positive, same-meaning, counterfactual and unsupported cases. Distinguish a missing source attribute producer from a clinical missing record. A citation existing does not prove full coverage. If the packet lacks decisive scope evidence, say exactly what frozen source/relationship to retrieve, not another entire model call. The review is session/context independent but uses the same named model as product calls, not model-independent proof.

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

- 2026-10-06 22:55:00 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
- Terminal: CodeBuddy/DeepSeek-v4.1-flash/max, one round, 631.697 seconds, exit0, no fallback. Owner review and boundary limitations recorded in reviews/codex_conference_enrollment-rv1001-target-scope-cause-20261006_review.md; source-wide applicability was not established or approved. User requested lossless pause after stage close.
