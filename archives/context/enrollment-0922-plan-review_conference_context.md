# Conference Context: enrollment-0922-plan-review

Created: 2026-09-22 14:53:39 CST
Objective: 只读审阅e7f34d05入排审核实现与0922V2专家意见，核对完整资格选择、新来源采信、跨章发布、更正失效及连续交付计划；不修改产品、不启动模型或服务
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-0922-plan-review`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen code baseline: e7f34d0508c05481164cf13569f66ddf64e2e74f, this worktree and GitHub branch verified identical. No product changes this turn.
- Read .trellis/tasks/09-11-e2e-eligibility-review/research/0922-expert/enrollment_review_0922V2/README.md and FINDINGS.md if present; discover exact expert filenames before reading. Expert opinions are evidence to challenge, not authority to execute.
- Read .trellis/tasks/09-11-e2e-eligibility-review/delivery_20260922/{01_REVIEW,02_EXECUTION_RULES,03_PLAN,04_WORK_PACKAGES,05_ACCEPTANCE,07_FORK_PROMPT,09_REVIEW_EVIDENCE}.md.
- Verify decisive definitions in app/services/eligibility_review_projection.py, qualified_binding_selection.py, frozen_review_calculation.py, published_clause_pack.py, fact_correction_service.py; app/domain/expression.py; app/domain/contracts/{source_policy,page_review}.py; app/agents/protocol_control_deconstructor.py; app/services/page_review_job_service.py.

## Scope

- In scope: read-only challenge of the proposed delivery plan and source-supported review, prioritizing clinical semantic integrity, real-source provenance, whole-predicate selection, cross-chapter coverage, correction/invalidation, and proportional testing. Identify factual overclaims and unnecessary abstractions.
- Out of scope: implementation, file edits, raw clinical materials/databases, credentials, network calls, other agents, model or service startup, test execution. Only read source and supplied planning material within this worktree. Return report in your final answer for the runner to persist.
- Output: severity-ordered findings with exact file/line evidence; distinguish confirmed defects from design risks and unverified hypotheses. For each propose the smallest concrete plan correction. Explicitly assess whether W0-W7 plus Q1-Q3 can be handed to gpt-5.6-sol:medium without new decisions. Do not demand exhaustive tests after every edit or a new framework.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- Application source is authorized read-only. No clinical production data, application writes or running services; Codex retains final acceptance.

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

- 2026-09-22 14:53:39 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
