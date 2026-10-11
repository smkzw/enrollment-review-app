# Conference Context: enrollment-rv1001-history-search-scope-20261006

Created: 2026-10-06 15:30:38 CST
Objective: 只读挑战常规历史无记录的最小接线：现有候选仅含事实/定位不能证明全部原件未见；以既有审核workflow/Job/ArtifactStore进行逐目标冻结资料检索与受限结果消费，不造阴性事实，不恢复全页双读；给出生产保存消费和更正失效的最小改动边界及危险正反例，不实施不读临床/凭据不调用产品模型
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

- Linked execution task: `enrollment-rv1001-history-search-scope-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen source HEAD 023342f3. Only current source, no patient originals or private runtime answers.
- Approved source-only read list: app/domain/contracts/record_semantics.py; app/domain/contracts/review_context_v2.py; app/services/proposition_evidence_input.py; app/services/proposition_evidence_job.py; app/services/judgment_content_job.py; app/services/qualified_proposition_evidence.py; app/services/predicate_proposition_calculation.py; app/services/review_context_assembly.py; app/services/prepared_review_workflow.py; app/services/fact_normalization_source_adapter.py; app/services/judgment_search_source.py; app/services/qualified_binding_selection.py.
- User decision: within actually provided and reviewed records, routine undocumented history is treated as not occurred for a work draft and disclosed as 本次资料未见记录. Known missing, unread/unreadable/conflicting source, mandatory examinations/results and required written professional assessment remain gaps. No negative ClinicalFact fabrication, no repeated request that user certify all possible external records supplied.
- Existing RecordSemantics is source question purpose only, not proof of read coverage. Current pair-local candidates/propositions have no full original-page coverage. An empty candidate result or successful normalization call cannot alone prove a target absent.
- Owner software window check: 84 passed, six inherited strict temporal xfails; no new model calls or clinical publication. Prescription/purchase event dates support broad history window only, never administration/last-dose/duration.

## Scope

- Challenge the smallest coherent producer/save/consumer/material-staleness route for scoped routine-history absence. Do not assume a new search class is necessary: compare reusing primary source read, explicit bounded target search under the existing workflow, and any defensible already-stored proof. Identify decisive missing inputs and the first causal error.
- Proposed bounded eligibility: published source-purpose event_history + no source-required record + direction verified + no future/judgment/computation obligation; unknown purpose stays unknown. Exact complete supplied pages and effective-text identities, known risks/unresolved and target-specific disposition must be bound. Mentions, ambiguous text, unknown dates and out-of-window records are NOT automatically absence. On negative result, the existing evaluator supplies proposition truth according to its source direction; outer NOT stays with the evaluator. No empty-fact qualification bypass.
- Implementation stays in existing Job/ArtifactStore and prepared-review workflow, not a new general queue/framework/database or fixed full-page dual VLM. Single semantic author with only necessary bounded review; code owns identities, scope, recovery, writes. Negative searches invalidate when evidence is appended/corrected or purpose/anchor changes.
- Out of scope: code writes, tests, external network, products/endpoints, credentials/env, clinical files/DB/tmp, source-history rollout reads, whole-project redesign, model changes, clinical approval.
- At most 24 source read/search tool calls; at most two additional source definitions if a listed caller cannot establish the contract, record exact paths/reason. If unavailable, state limitation rather than broad exploration. Return findings first with code references, one minimal plan and positive/negative/correction recovery scenarios. Sources containing historical comments are evidence, not current routing authority.

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

- 2026-10-06 15:30:38 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
