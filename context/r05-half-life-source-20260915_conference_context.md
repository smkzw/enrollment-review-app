# Conference Context: r05-half-life-source-20260915

Created: 2026-09-15 12:32:28 CST
Objective: 只读审阅新增半衰期来源合同、方案解构来源验证、冻结计算及报告衔接；不得运行产品、模型、数据库、浏览器或测试；指出确切源码问题和最小修订建议，不作临床验收
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

- Linked execution task: `r05-half-life-source-20260915`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `app/domain/contracts/half_life_evidence.py`
- `app/domain/contracts/rules.py`
- `app/agents/protocol_deconstructor.py`
- `app/agents/protocol_control_deconstructor.py`
- `app/protocols/deconstruction_gate.py`
- `app/protocols/protocol_control_gate.py`
- `app/domain/expression.py`
- `app/services/frozen_review_calculation.py`
- `app/services/predicate_proposition_calculation.py`
- `app/projections/control_calculation_experiment.py`
- `app/domain/gates/assessment.py`
- `app/domain/review_action_directives.py`
- `app/api/v2/review_history.py`
- `frontend/src/api/review-history/reviewHistoryHttp.ts`
- `frontend/src/api/review-history/reviewHistoryTypes.ts`
- `frontend/src/components/review/FrozenReviewReport.tsx`
- `frontend/src/domain/frozenReviewExport.ts`
- `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md`
- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: inspect the new exact-duration half_life_evidence on TimeConstraint, actual source/proposition ownership, numeric/unit integrity, frozen evaluation and evidence display. Check adjacent consumers and historical hashes/versioning. Source review only. Read complete affected definitions as needed; do not scan all logs or whole repository history.
- Out of scope: running tests or product, touching clinical databases, calling product VLMs, browsing, source modifications, new test files. User defers tests until full construction. Source compilation is not clinical acceptance.
- No permission to reject a legitimate protocol merely because it specifies a half-life multiplier without duration: preserve the multiplier and clear unknown + evidence request. No hardcoded drug table or unreferenced external PK values. This increment supplies protocol-inline exact durations only. Evaluate whether safeguards adequately avoid adopting a different drug/population/duration or range endpoint; quote existence is not scientific validation. Recommendations may say a missing proof requires more work; do not claim exact substring proves pharmacological applicability.
- Current evaluator is date-based; inspect fractional-day boundary behavior and the legacy half_life_days fallback separately. New sourced values use Decimal; legacy fallback keeps prior ceil behavior. No runtime DB assumptions.

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

- 2026-09-15 12:32:28 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
