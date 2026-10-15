# Conference Context: r05-judgment-content-review-20260914

Created: 2026-09-14 21:46:30 CST
Objective: Read-only review of written-judgment content producer/receipt chain and minimal safe integration into formal calculation; identify concrete defects and whether qualification/content can share one call without losing separate evidence.
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

- Linked execution task: `r05-judgment-content-job-20260914`
- Execution evidence status: `linked`
- Excluded route identities: `pi/cursor/default`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- app/domain/contracts/judgment_content.py; app/llm/judgment_content.py; app/services/judgment_fact_linkage.py, judgment_content_input.py, judgment_content_comparison.py, judgment_content_job.py, judgment_content_receipts.py. Review their full definitions.
- Adjacent source: app/services/qualified_binding_selection.py, review_method_evidence.py, qualified_review_command.py; app/domain/contracts/review_method_adoption.py; app/services/binding_qualification.py and binding_qualification_support.py; app/llm/binding_qualification.py. Expand only decisive dependencies.
- docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section 17 and plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md T5 for product contract, not old reports as proof.
- Source-only implementation. Actual runtime, clinical correctness and any method approval remain unproven. Product must handle positive written judgments and multiple observations, not permanent unknown-only behavior.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: read-only code review with concrete file:line findings. Trace frozen source/excerpt identity, deduplication, pair scoping, JSON persistence, calls/receipts, cancellation/retry, route/resource admission, incomplete coverage and comparison to formal consumer. Do not assume existing qualification code is correct merely because reused. Check all new modules including owner edits.
- Give a minimal producer-to-consumer integration plan with explicit evaluation/approval requirements, and whether content fidelity can share the existing qualification model request without conflating five content dimensions with six source dimensions. Identify which repeated work costs are actually source-evidenced vs speculative; no invented timing gains.
- Preserve clinical requirement: missing investigator judgment is reported, not user reconfirmation; found content is not automatically eligibility truth. No new fact construction or model-specific disease shortcuts. Require full source/node/object applicability and recorded authorization before positive consumption.
- Out of scope: ALL writes (report returned to runner only), tests, Python/app imports/execution, models, DB, clinical raw materials, browser, internet, installers, recursive workers/conferences. Only read/search commands within worktree. Do not read worker report/private reasoning. Do not run acceptance or declare clinical PASS.
- Output findings by severity with exact source locations, then concrete smallest integration sequence and remaining uncertainty. This review can finish once decisive source evidence is obtained, not after a full-repo tour.

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

- 2026-09-14 21:46:30 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
