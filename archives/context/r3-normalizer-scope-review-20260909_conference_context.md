# Conference Context: r3-normalizer-scope-review-20260909

Created: 2026-09-09 10:25:03 CST
Objective: Review verified-observations-only normalizer scope with deterministic pending retention; find clinical/source loss and minimum safe integration requirements
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

- Linked execution task: `r3-normalizer-scope-review-20260909`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Only read current app/agents/evidence_normalizer.py, app/projections/page_review_model_input.py, pending_observations_report.py, page_review_pending_normalization.py, page_review_pending.py, page_review_sources.py; app/domain/contracts/evidence_normalizer.py; app/services/fact_normalization_executor.py and fact_normalization_job_service.py; relevant app/projections/evidence_expectations.py and app/services/evidence_expectation_projection_service.py; focused tests/v2 for these modules; docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md. Source code only, no raw clinical data needed.
- Do not read any artifacts/DB/env/credentials/home files/other runtime directories. Do not run code importing config or invoking model/network. No writes, no servers, no browser. Static source review suffices. Return report in final for runner to persist, not edit tools.
- Owner measured same real 2-page frozen input v22: 56606 prompt tokens, 32077 completion/27236 reasoning, 428.927 seconds; v23 grouped pending metadata and visual marker:49130 prompt,38518 completion/33209 reasoning,613.168 seconds,one stop each. Same product GLM high65536. Both1identifier candidate, no events/exposures; v22 12unresolved,v23 11unresolved. 144pending observations,2accepted observations. These are measurements, not gold quality or proof of causality.

## Scope

- In scope: challenge a proposed next minimal change, NOT YET IMPLEMENTED. Product model only sees accepted observations and their necessary exact source locators/context; pending content is NOT re-summarized by normalizer. Persisted full input remains intact for gates, replay, audits. Deterministic pending_retention_items already produces per-page preserved original explanations; currently v2 appends these after normalizer. Proposal adds a frozen new policy to mark that pending details are retained by code, passes counts/status only to normalizer, removes redundant fact/signal/handwriting conflict payloads from model view only, retains accepted context + relevant requirement text. Model still reports uncertainty of accepted candidates. Empty-accepted pages get deterministic not-yet-verified preservation, no invented facts. Should OCR sidecar/other locators remain to validate source semantics, dates, context? Identify minimum evidence it must still see, and whether full pending text can be omitted safely at this stage or requires a separate downstream requirement gap map first.
- Specifically check loss of investigator written judgment gaps, conflicting values/negation/timing, unknown vs not-done, requirement binding, missing pending reports, old policy compatibility, source cross-binding. User: missing written investigator judgment is a reportable inability to determine, NOT an immediate user stop. Two-model conflict recovery max2rounds remains separate; normalizer must not do that again. No accepted fact from pending, no hidden silent loss, no project-specific fixes. Provide concrete minimal edits and tests, accept/reject proposed scope with reasons, don't broaden into general architecture audit or model comparison. Flag defects in current pending helper independently.
- Out of scope: implementation, runtime calls, provider changes, local model startup, clinical acceptance. Frozen zcode/GLM-5.3:max only; no fallback. Earlier executor was GLM-5.3-Flash:max with terminal wrapper failure and owner corrections; reviewer different variant samefamily, not full model-family independence.

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

- 2026-09-09 10:25:03 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
