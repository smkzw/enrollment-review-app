# Codex Conference Review: enrollment_review_design_conference_20260812

Date: 2026-08-12

## Verdict

**Pass after Codex synthesis and document revision.** Both independent outputs were complete enough to challenge the design. No additional participant rerun is required before user design approval.

## Boundary Compliance

- Both participants remained in the workspace and did not mutate source code, clinical payloads or legacy projects.
- Neither participant claimed final clinical, browser or visual authority.
- The daytime route overlay was correctly applied to the declared Qwen participant.
- Grok Build's incomplete first response was preserved and resumed in the same session; it was not silently redispatched.
- The conference was initialized and gated through `hermes_workflow_guard.py`, but no Hermes participant/model route was assigned; the two recorded routes were Pi and Grok Build, with Codex as final authority.

## Participant Outputs Reviewed

- `runs/conference/enrollment_review_design_conference_20260812/general_pi_qwen38.md`
- `runs/conference/enrollment_review_design_conference_20260812/general_grok45.md`
- Preserved incomplete evidence: `runs/conference/enrollment_review_design_conference_20260812/general_grok45_round1_incomplete.md`

## Conference Panel Review

### Accepted

1. Clinical truth must be represented as versioned facts, events, rule components, evidence spans, conflicts and actions rather than one Markdown verdict.
2. Judgment state and gap reason require a deterministic consistency matrix; an invalid combination is rejected, not text-corrected.
3. Conflicting sources are displayed together and hard-block the contested component. The old prompt instruction to prefer prior source is not carried into V2.
4. Enhanced provenance reminders are non-blocking but visible, countable ActionRequests.
5. Runtime spine is SQLite/WAL + persistent Job/Checkpoint + explicit state machine. Agent calls are bounded typed steps, not peers sharing mutable memory.
6. The Critic is conditional and can veto, reduce certainty or open an action; it cannot silently rewrite an assessment.
7. New frontend shell and target-schema fixtures are required for the visual prototype; the 3,115-line static SPA is not a V2 foundation.

### Accepted With Adjustment

1. The clinical participant proposed disabling auto-close for professional judgment, source conflict and interpretation conflict. The user's explicit choice allows system auto-close, so V2 permits it only when a gap-specific, source-linked resolution predicate is satisfied in a new ReviewRun. An arbitrary upload or rerun cannot close it.
2. The architecture participant suggested deferring the Critic. V2 keeps it in the design but invokes it only for high-risk rules, conflicts, OCR polarity/numeric risk or Gate anomalies.
3. Conservative incremental recomputation starts at every RuleComponent linked to facts from a changed document. Later optimization requires dependency evidence.

### Rejected

- Day-one LangGraph as the business/runtime spine.
- A free-running multi-Agent discussion or always-on three-Agent chain.
- Importing old project verdicts or reports as V2 truth, or continuing to write imported legacy state.
- Auto-selecting a source when evidence conflicts.
- LLM-authored blocking level, action transitions, parent/child logic, thresholds, time windows or final report rollups.

## Main-Venue Codex Review

The final design and Phase 0-9 plan implement the accepted conference findings. The remaining decision is product approval, not an unresolved technical question. Implementation is intentionally stopped before Phase 0/1 per the user's requested discuss-then-build sequence.

## Codex Independent Verification

- Cross-checked the two participant reports against `app/models.py`, `app/router/pipeline.py`, `app/pipeline/ocr.py`, `app/pipeline/reviewer.py`, `app/processing_locks.py`, `static/index.html`, the consolidated discovery and the existing regression inventory.
- Confirmed the direct contradiction between the current reviewer prompt's prior-source preference and the confirmed no-auto-pick conflict rule; V2 design now specifies a conflict hard block.
- Confirmed the final design covers full/incremental snapshots, immutable ReviewRuns, OCR correction, stage isolation, ActionRequest closure/override, source linkage, Patient Profile and read-only legacy anchors.
- Confirmed the plan requires real Playwright/DPI/browser checks in Phase 1 and representative clinical reruns in Phase 8. Those checks cannot be performed before implementation and are correctly not claimed here.
- No source code or legacy clinical data was changed during the conference.

## Final Decision

Approve `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` as the implementation baseline and `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` as the gated sequence. Begin with Phase 0 isolation and Phase 1 interactive prototype only after explicit user approval.
