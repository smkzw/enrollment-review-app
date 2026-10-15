# Conference Context: r05-core-consumption-review-20260914

Created: 2026-09-14 17:06:29 CST
Objective: 只读审阅研究者书面判断与多观察消费缺口，提出复用现有合同的最小完整闭环，不把双路一致当采用批准。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> codex-subagent/codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-core-consumption-review-20260914`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section17, plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md T5; app/services/qualified_binding_selection.py, binding_qualification_support.py, frozen_review_calculation.py, judgment_gap_selection.py; app/domain/contracts/rules.py, binding_qualification.py, app/domain/expression.py. Follow only necessary adjacent definitions.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: source-only gap analysis and concrete minimal-complete next implementation. Explain which existing fields can prove a written investigator judgment versus only source eligibility, and how multiple observations must be selected without guessing policy. Identify exact missing contracts, producers, consumers and version impacts. Do not recommend blanket suppression or treating requires_professional_judgment alone as a semantic truth. Existing EvidenceRequirement.predicate_ids is real; inspect it before concluding attribution is absent.
- Out of scope: all writes, tests, runtime/model calls, browser, databases, raw clinical files, web, recursive dispatch. Return report via final output only. User deferred tests until whole product construction complete. New automatic adoption still needs evaluation and explicit approval; do not create it.
- Output: prioritized findings with file:line evidence, a concrete implementation sequence (not another accepted=false-only shell), unavoidable decisions if any, and what is already implemented. Focus on the core missing positive/negative semantic judgment and multi-observation consumption, not further peripheral checks. This is independent source review, not clinical or product acceptance.

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

- 2026-09-14 17:06:29 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
