# Conference Context: r05-observation-consumer-review-20260915

Created: 2026-09-15 09:39:31 CST
Objective: 只读审阅通用观察政策、逐事实范围对账、确定性排序与any/all消费、报告未选记录的来源和历史兼容；禁止运行测试、产品、模型、数据库或浏览器；不修改源码，仅出具具体证据与修订建议。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/zcode/glm-5.3:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-observation-consumer-review-20260915`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` section17, `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` current T0-T7. Read focused sections, not all historical context.
- Contracts: `app/domain/contracts/{observation_selection,rules,control_evaluation_spec,qualified_binding_selection,review}.py`.
- Producer: `app/agents/{protocol_deconstructor,protocol_control_deconstructor}.py`; source gates `app/protocols/{deconstruction_gate,protocol_control_gate}.py`.
- Candidate/accounting: `app/llm/{candidate_fact_accounting,predicate_binding_candidates,control_binding_candidates}.py`, `app/services/{binding_candidate_comparison,binding_qualification_support}.py`.
- Consumers: `app/services/{ordered_observation_selection,qualified_binding_selection,frozen_review_calculation,frozen_review_publication,review_history_service}.py`, `app/domain/expression.py`, `app/api/v2/review_history.py`.
- UI: `frontend/src/api/review-history/{reviewHistoryTypes,reviewHistoryHttp}.ts`, `frontend/src/components/review/FrozenReviewReport.tsx`, `frontend/src/domain/{reviewConditionNotes,frozenReviewExport}.ts`.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: source review for definite bugs, history/hash compatibility, policy/source validity, false completeness, time filtering/order/partial dates, deterministic any/all, bypasses, persistent trace and UI correspondence. Give file:line and concrete minimal remedies; distinguish code defect from unimplemented next scope. Other files only for decisive adjacent calls.
- Out of scope: all execution/testing, new clinical/model approvals, credentials/data/production, unrelated refactors. No source modifications. User defers tests until whole product built.
- Known pending: conditional retest requires a richer source-backed policy; control report has not yet acquired unselected-record audit. These are open scope, not declared complete. Official report audit was just added. Existing codebase is largely uncommitted; review actual files, not only git diff. Owner compile and tsc are static, not clinical verification.
- Current policy change is generic, no disease/drug/project/model special cases. Full supplied-fact accounting is not evidence of full clinical history. Missing/incomplete source remains upstream obligation. No new adoption permissions were issued.

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

- 2026-09-15 09:39:31 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
