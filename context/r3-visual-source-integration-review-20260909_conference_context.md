# Conference Context: r3-visual-source-integration-review-20260909

Created: 2026-09-09 05:42:55 CST
Objective: 独立审阅新增视觉来源合同及其正式接线方案：不以OCR为图像事实权威，不破坏既有修订/覆盖，不形成来源验证旁路。给出最小完整接线边界和实质缺陷。
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

- Linked execution task: `r3-visual-source-contract-20260909`
- Execution evidence status: `linked`
- Excluded provider/model nodes: `zcode/glm-5.3-flash`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read docs/REARCHITECTURE_FINAL_DESIGN_20260812.md sections 3.3/4.2/7.2 and docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md; app/domain/page_review_evidence_sources.py, app/domain/page_source_association.py and their tests; app/domain/contracts/evidence_normalizer.py, facts.py, evidence_locator.py; app/services/fact_normalization_source_adapter.py, fact_publication_service.py; app/storage/fact_authority.py and app/domain/gates/fact_evidence_closure.py. Other app/tests may be read to trace adjacent consumers. Do not read worker reports/private reasoning, credentials, DBs, clinical raw files or other workspaces. No network/model calls. No writes.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: independent review of the new source contract and minimal complete integration design. Product sources are original images plus two accepted independent GLM/Gemini readings; OCR is sidecar. Current OCR-only locator membership blocks a valid image excerpt even with both readers agreeing. New module is not connected yet. Review actual code, not this description as authority; identify concrete defects with paths/lines and focused tests if useful (synthetic only).
- Evaluate a typed additional source branch, bound to original immutable processing revision, coverage and raw review records, reconstructed/validated deterministically; reject fabricated or stale source IDs. Preserve explicit image hash and literal excerpt hash, page_excerpt precision without authenticated model boxes. It must reach Normalizer input, candidate gate, publication, replay and evidence/Profile APIs, not only relax the first validator. Existing text path remains unchanged. Existing coverage bound to revision R1 cannot simply become R2 without circular invalidation; assess that tradeoff explicitly. Compare minimum coherent paths and recommend a concrete file-level order, schema changes and acceptance tests. Do not demand a fresh OCR-only authority for visual text. Don't silently omit accepted handwriting or accept clause signals as atomic facts.
- Out of scope: implementation, raw clinical adjudication, provider changes, deployments and broad refactoring. Current product only GLM-5.3-Flash plus Gemini-3.7-Flash; no third reader. Report remaining interpretive uncertainty honestly; do not certify clinical completion.

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

- 2026-09-09 05:42:55 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
