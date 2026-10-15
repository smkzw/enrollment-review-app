This is optional continuation round 2 in the same session.

Do not restart the task or open a new session. Codex has requested this continuation because the previous output needs additional quality work. Challenge your previous answer against every requirement, source boundary, edge case, and likely user/reviewer objection. Identify concrete omissions or contradictions and propose corrections.

Return the complete updated Markdown output for your role. Keep evidence, inference,
recommendation, and uncertainty separate. Codex remains the final authority.

Current frozen-source followup, read only. No tests (including imports/probes), app/model/DB/browser/network calls, delegation or edits. Same bounds as round1. F1 moved the context requirement after the non-ordering branch; F2 text now states the policy requirement and separately whether records were actually selected. Model AssessmentCandidate rejects ordering audit. Verify actual source, not this account.

New integration requiring scrutiny:
- OrderedObservationAudit now contains selected_fact_ids and excludes overlap/duplicates. Official observation and qualification outcomes require their selected fact IDs match audit.
- control-review-outcome/v3 stores all four layers' audit keyed by atom identity, oldv1/v2 serialization omits field. app/projections/control_review_outcome.py, app/services/frozen_review_calculation.py pass it; app/storage/review_control_repository.py validates sources/policy/selected and nonselected facts.
- app/services/review_history_service.py, app/api/v2/review_history.py expose control_selection_records and excluded locators; frontend reviewHistoryTypes/Http, FrozenReviewReport, frozenReviewExport render all layers separately without misattributing applicability/exception to an obligation. Exact locator equality now includes excluded records but used_fact_ids does not.
- Ordered helper now allows source_validity as well as event_membership to use the SAME existing evaluate_time_constraint; interval_condition remains unresolved rather than filtering a threshold outcome. Check whether this is semantically valid under source-backed observation policy or needs a separate policy selector (e.g. latest overall versus latest valid). No new model approval, runtime or clinical acceptance. EVALUATORv14 PUBLICATIONv5 CONSUMERv10.

Inspect adjacent producer/policy validators when decisive. Find concrete correctness gaps, especially excluded dates, missing/partial date ordering, source matching, all-layer provenance, immutable oldpayloads, frontend exact identity and alternate publication paths. Conditional retest remains open, not claimed implemented. Return ranked findings and concrete smallest fixes; do not generate tests or request them now.
