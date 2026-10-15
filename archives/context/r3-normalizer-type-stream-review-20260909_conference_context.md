# Conference Context: r3-normalizer-type-stream-review-20260909

Created: 2026-09-09 03:20:39 CST
Objective: Read-only scoped engineering review of app/agents/evidence_normalizer.py (new identifier value_kind v21), app/agents/deepseek_evidence_normalizer_transport.py (GLM streaming), app/services/fact_normalization_job_service.py retry, scripts/run_isolated_page_revision.py and focused tests. Challenge identifier strings retaining leading zeros without weakening numeric measurement unit checks, partial stream rejection and resource release, request identity, retry state correctness, historical compatibility. Do not read clinical artifacts, env or credentials; do not call models/API or modify files. Report concrete severity/file/line findings and minimal fixes; no clinical acceptance. Product remains own HTTP harness GLM+Gemini. One independent reviewer only, no fallback.
Task type: `C03`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3:max -> xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r3-normalizer-stream-20260909`
- Execution evidence status: `linked`
- Excluded provider/model nodes: `zcode/glm-5.3-flash`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Authoritative boundary: current product has own harness, GLM low/Gemini high page readers and GLM high normalizer. Typed numbered identifiers must retain exact string and leading zeros; quantities still require units. See app/agents/evidence_normalizer.py, app/domain/contracts/facts.py, app/domain/gates/fact_candidate_gates.py, app/projections/page_review_sources.py; streaming and retry files specified in objective; tests/v2/agents/test_evidence_normalizer_adapter.py and test_evidence_normalizer_transport_config.py, tests/v2/services/test_fact_normalization_persistence.py. No clinical or credentials access. Do not trust the owner's fixes: probe misclassified identifier bypasses, downstream type meaning and legacy contracts. Local mock tests permitted, no new files outside test cache. Report recommendations; never edit app/tests.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: read-only code review and deterministic tests, minimum fix recommendations.
- Out of scope: clinical interpretation, model API calls, credential access, production data and any source edits. No fallback dispatch.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

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

- 2026-09-09 03:20:39 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
