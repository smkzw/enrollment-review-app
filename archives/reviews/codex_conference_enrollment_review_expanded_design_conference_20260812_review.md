# Codex Conference Review: enrollment_review_expanded_design_conference_20260812

Date: 2026-08-12

## Verdict

**Pass after Codex synthesis and document revision.** Kimi K3 and CodeBuddy GLM-5.2 both completed independent full passes. Their convergent findings materially tightened the product contract, Agent boundary, evidence provenance and acceptance LOOP. No Qwen 3.8 run or additional participant is required.

## Boundary Compliance

- Active participants were exactly `pi/kimi-code/k3-256k:max` and `codebuddy/codebuddy-cli/glm-5.2:max`; neither used a fallback.
- The requested Qwen participant was superseded before dispatch. No other output is represented as Qwen.
- Both active participants were read-only and did not modify application source, legacy projects or clinical data.
- GLM-5.2 disclosed that it used targeted/partial source reads rather than claiming exhaustive line-by-line review.
- K3 stated it read only the fixed packet, but its own source list included `app/llm/client.py` and one official PaddleOCR documentation query, neither included in the fixed local read list. This is a process deviation, not a clinical-data or write-boundary breach. Codex independently rechecked the affected locator claim before accepting it.
- Conference initialization and review gating use `hermes_workflow_guard.py`; Hermes was not a participant route.

## Participant Outputs Reviewed

- `runs/conference/enrollment_review_expanded_design_conference_20260812/expanded_pi_kimi_k3.md`
- `runs/conference/enrollment_review_expanded_design_conference_20260812/expanded_codebuddy_glm52.md`
- Runner evidence in `logs/conference/enrollment_review_expanded_design_conference_20260812/`
- The generated `general_pi_qwen38.md` and `general_grok45.md` placeholders contain no accepted participant work and are excluded.

## Conference Panel Review

### Accepted

1. Add a Phase 0.5 domain/interaction contract: fixture JSON Schema, OpenAPI draft, Agent contracts, RuleExpression grammar, rollup truth table and scripted UAT.
2. Phase 1 uses the real React product shell against a stub API, not a throwaway HTML prototype; Phase 1.5 measured UAT blocks backend implementation.
3. Add `EvidenceRequirement` and per-episode `EvidenceExpectation` so missing expected records/procedures are rendered and actionable rather than invisible.
4. Make EvidenceSpan precision explicit: `bbox > text_range > page_excerpt > page_only`, with locator metadata and visible degradation.
5. Eligibility Assessor emits semantic candidates only; deterministic Evaluator/Gates own final component state, rollup, blocking and Action transitions.
6. Add AgentCall/PromptVersion audit, optimistic revision checks, stale impact scope, per-item Job UX and ReviewRun diff.
7. Expand the QC LOOP to contract, deterministic/property/mutation, Agent eval, OCR gold pages, clinical regression, crash/fault injection, API/E2E, visual/accessibility, performance, prototype UAT and full-flow UAT.
8. Retain both `今日工作` and `项目看板` as first-class pages and test both default-home variants in UAT.

### Accepted With Adjustment

1. K3 proposed numeric model accuracy thresholds. Hard invariants are fixed now, but P/R and agreement thresholds require a measured calibration set and user approval before release.
2. GLM proposed possibly splitting Safety and Provenance critics. V2 keeps one conditional Critic; deterministic provenance/expectation logic should handle routine cases. Split only if evaluation demonstrates material benefit.
3. GLM suggested no horizontal scroll at all widths. The contract is no page-level horizontal scroll; dense components may scroll internally or convert to tabs/drawers.
4. Comparator information architecture is useful for structured summary, source pairing and three-pane review, but its branding, login, role workflow and pixel styling are not copied.

### Rejected Or Deferred

- Qwen 3.8 redispatch; the user explicitly ended that route.
- Day-one LangGraph, free-running Agent swarms, always-on Critic or extra Profile/Report Agent.
- Parallel backend/database implementation before Phase 1.5 user approval.
- Fake bbox highlighting, silent source preference, regex repair of invalid clinical logic, or model-authored final rollup/action transitions.
- Migrating legacy verdicts/reports into V2 truth or keeping the legacy SPA as the V2 foundation.

## Main-Venue Codex Review

The revised design preserves all confirmed product decisions and resolves the two largest remaining ambiguities: what the frontend prototype must prove, and how absent/low-precision evidence is represented. The result remains a bounded multi-Agent workflow: semantic extraction and assessment nodes are replaceable; durable state, final logic, actions, projections and acceptance are deterministic.

## Codex Independent Verification

- Confirmed current prompt auto-prefers prior source on conflict: `app/pipeline/reviewer.py:108-120`, contradicting the V2 conflict hard block.
- Confirmed OCR cache uses file mtimes: `app/pipeline/ocr.py:98-101`.
- Confirmed review work is owned by an SSE request and canceled on disconnect: `app/router/pipeline.py:225-397`.
- Confirmed current domain stores one subject `overall_verdict`: `app/models.py:130-146`.
- Confirmed the OCR adapter returns plain text and strips LOC tokens: `app/llm/client.py:382-421`; therefore bbox cannot be promised without a Phase 4 capability spike.
- Visually inspected the current subject report/rule editor and both supplied comparator screenshots. The current UI is report/Markdown centered; the comparator usefully demonstrates structured summary + source and rule/text/original linkage, but not the target single-user workflow.
- Verified exact route/session/effort from runner logs. No application tests or live browser flow were rerun because this conference changed design documents only and implementation remains intentionally blocked.

## Final Decision

Approve the revised `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` and `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` as the discussion baseline. If the user approves implementation, begin only Phase 0, Phase 0.5 and Phase 1; stop again at Phase 1.5 for measured user acceptance before building the backend core.
