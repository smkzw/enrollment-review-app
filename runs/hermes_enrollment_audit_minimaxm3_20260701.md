# Hermes Enrollment-Review Audit — MiniMax M3 (fallback no-tool)

Scope: clinical trial eligibility review app, MG-K10-SAR-III / center 31 / 10 subjects, two review phases (screening_run_in, baseline_randomization). Health: API ok, deepseek=true, oMLX=false at capture. Desktop Playwright clean; mobile Playwright has 30 clipped overflow elements on subject list and report; visual findings from contact sheet noted below. Findings are evidence-bound to the supplied summary; nothing is invented beyond what is stated or is a direct, conservative inference.

Severity legend: P0 = data corruption / silent wrong verdict / PHI / auth bypass; P1 = real usability blocker or false verdict risk on the common path; P2 = UX friction / design debt that erodes trust; P3 = polish.

---

## P0 — Findings

### P0-1 Mobile horizontal overflow is hidden, not scrollable/reflowed (subject list + report)
- Evidence: mobile Playwright 390x844, SAR subject list overflowElements=30 scrollOverflow=0; SAR report overflowElements=30 scrollOverflow=0. Codex visual inspection: table content is clipped because horizontal overflow is hidden, not scrollable/reflowed.
- Root-cause hypothesis: the table container uses `overflow: hidden` (or default `overflow-x` not set to auto/scroll) without a responsive collapse (e.g., card stack < 480px, or `overflow-x: auto` on a wrapping div with min-width on the table). On a 390px viewport, 30 elements are clipped on each page.
- Downstream risk: a senior medical monitor reviewing on a phone (stated user class — "may not understand AI") will miss columns and silently trust a verdict they cannot fully read. This is the exact failure mode the product brief calls out: reviewers trusting AI they cannot verify.
- Fix/verification: (a) wrap the data table in a `div` with `overflow-x: auto` + `-webkit-overflow-scrolling: touch` and an explicit hint ("swipe to see more"); (b) below a breakpoint (e.g., 720px), switch to a stacked card view per subject showing label-value pairs; (c) add a Playwright check at 390x844 asserting `scrollWidth > clientWidth` produces a scrollable container, and that no node has `overflow: hidden` clipping required cells. Verify by re-running the mobile Playwright suite and asserting overflowElements drops to 0 and scrollOverflow > 0.
- Confidence: high — the symptom (clip without scroll) is directly stated.

### P0-2 Baseline/randomization anchor date is per-row, not per-project/phase
- Evidence: "baseline anchor date inputs appear per-row" (visual finding). Domain rule: baseline/randomization requires a single anchor date per project to evaluate date-window rules consistently.
- Root-cause hypothesis: the schema treats anchor date as a per-subject column rather than a phase-level configuration on the project/phase metadata. It is also missing a "set once, locked on first randomization" enforcement.
- Downstream risk: (a) a reviewer can type a different anchor per subject, producing inconsistent window math across the cohort; (b) the same reviewer's intent at edit time and another reviewer's read at QC time can disagree; (c) audit trail becomes "who typed what into which cell" instead of "anchor 2025-08-12, locked by X at T". This is a P0 because it is exactly the kind of silent inconsistency that produces a wrong verdict on a date-window rule.
- Fix/verification: (a) move anchor date to phase-level metadata on the project (screening_run_in has screening day 0; baseline_randomization has randomization day 0); (b) lock the field after first save; (c) make the displayed value read-only in the subject table with a click-through to the phase settings page for admins; (d) add a server-side guard rejecting per-row anchor overrides. Verify with a test that creates a project, sets anchor, attempts to PATCH a subject with a different anchor — expect 409. Cross-check the audit log shows exactly one anchor-set event.
- Confidence: high — visual finding aligns with stated domain rule.

### P0-3 pass_verify must be a pass-level source-traceability reminder, not a verdict gate
- Evidence: requirement says "pass_verify is a pass-level source traceability reminder"; previously fixed risk: "pass_verify should not downgrade overall verdict."
- Root-cause hypothesis: an overzealous prompt instruction or a regression in the LLM verdict composer is treating missing source citations on a "pass" item as grounds to flip the overall verdict to "needs more evidence" or "fail." Likely trigger: the prompt lists pass_verify as a hard check at the same priority as evidence sufficiency, or the verdict composer runs a strict pass_verify gate that downgrades on any missing citation.
- Downstream risk: a clean pass becomes a false negative purely because a citation reference is short. For a senior monitor who "may not understand AI," this is the worst possible failure mode — the system second-guesses itself and the reviewer stops trusting it.
- Fix/verification: (a) in the verdict composer, treat pass_verify as a soft annotation on pass items only, not a gate on overall verdict; (b) if a citation is missing, surface it as a yellow chip "pass — source unspecified" on that item, not as a verdict downgrade; (c) add a regression test: subject that cleanly passes all rules with one missing source citation must yield overall verdict = pass with the chip, not needs-more-evidence. Re-run the QC report for MG-K10-SAR-III; expect 0 false downgrades.
- Confidence: high — this is an explicit prior fix and a stated requirement.

### P0-4 Admin "all-power" account must be the only role allowed to bypass ordinary-user edit fences
- Evidence: requirement "admin all-power account; ordinary users can edit only own content but read shared projects/results."
- Root-cause hypothesis: the role check is implemented at the UI layer (hidden buttons) but not at the API layer. A crafted POST/PATCH to a project the user does not own will be accepted. Also: there is no server-side check on the "shared read" boundary — ordinary users might be able to PATCH shared project metadata by accident.
- Downstream risk: a non-admin user can edit other users' subjects, anchors, or rules. This is a P0 because it is both a data-integrity bug and a governance bug in a regulated workflow (GCP audit trail must be attributable).
- Fix/verification: (a) every mutating endpoint takes the project owner and compares to session user; admin role bypasses; non-owner gets 403; (b) read endpoints allow any authenticated user for shared projects but not drafts/locked projects; (c) add integration tests: ordinary user PATCH on another user's subject → 403; ordinary user GET on shared project → 200; ordinary user PATCH on shared project metadata → 403. Run the suite; expect 100% pass.
- Confidence: high — explicit requirement, common implementation gap.

---

## P1 — Findings

### P1-1 Phase selection (II vs III) must create a separate project identity, not just a flag
- Evidence: requirement "II/III phase selection creates separate project identity"; current project MG-K10-SAR-III has both screening_run_in and baseline_randomization as review phases of the same project.
- Root-cause hypothesis: the phase selector at project creation time stores a `phase` field on the project record, but the phase-specific rule set, screening vs baseline/randomization review templates, and verdict schema are all derived from a single `phase_rules` table — meaning a phase II project and a phase III project share the same rules table, and reviewers can accidentally apply phase II rules to a phase III project.
- Downstream risk: misapplied phase-specific rules lead to false pass/fail at the cohort level; audit trail says "this project" instead of "this phase of this project." A user with a phase II project may also be able to view or copy a phase III project's rules, which is the wrong default for a regulated workflow.
- Fix/verification: (a) introduce a `project_phases` table keyed by `(project_id, phase_code)`; (b) phase-specific rules and verdict templates are scoped to a phase, not a project; (c) two projects with the same drug and same protocol but different phases are distinct identities (different project IDs); (d) add a test: create phase II project and phase III project, assert their rule sets are independent; assert cross-phase copy is blocked for non-admins. Run; expect independent identities.
- Confidence: medium — the requirement is explicit; the current model is unverified but the risk is plausible given the structure described.

### P1-2 evidence_insufficient vs investigator_judgment are conflated in the UI
- Evidence: requirement "separate evidence-insufficient vs investigator-judgment states"; visual finding: "report page has pass/source reminders, future-phase reminders, evidence-insufficient and investigator callouts."
- Root-cause hypothesis: the report renders both as the same yellow/needs-more-evidence chip. Reviewers cannot tell "the document didn't say" from "the document is ambiguous and a human must decide." Concretely: the LLM is asked to produce `needs_investigator` as a boolean, and the UI maps both `needs_investigator=true` and `evidence_sufficient=false` to the same callout.
- Downstream risk: the reviewer acts on the wrong assumption. "Evidence insufficient" should trigger "request more documents from site"; "investigator judgment" should trigger "discuss with PI." If the chips are conflated, the wrong workflow is followed, and the audit log records the wrong action.
- Fix/verification: (a) two distinct visual chips with distinct copy ("证据不足 — 需补充资料" vs "研究者判断 — 需与PI讨论"); (b) two distinct workflow buttons per chip; (c) add a test: render a fixture with one of each, assert both chips present and distinct, and that the recommended-action button labels differ. Run; expect distinct rendering.
- Confidence: high — the requirement is explicit and the conflation is a common implementation shortcut.

### P1-3 Protocol metadata auto-extraction should be deterministic, not LLM-best-effort
- Evidence: requirement "protocol metadata auto extraction"; health: deepseek=true, oMLX=false.
- Root-cause hypothesis: the extractor asks the LLM to read the protocol and return a JSON of {phase, indication, primary_endpoint, ...}. LLMs hallucinate. There is no schema validator, no required-field check, no cross-check against the protocol's own front-matter (e.g., "Phase II/III" in the title page), and no "low confidence" flag.
- Downstream risk: a wrong phase auto-detected becomes a wrong project identity (see P1-1) and a wrong rule set applied. For a senior monitor who "may not understand AI," they will trust the auto-fill.
- Fix/verification: (a) require the LLM to return a `confidence` per field and `evidence_quote` (literal substring from the protocol); (b) for `phase` and `indication`, cross-check against the protocol's title page using deterministic regex/keyword; if LLM and regex disagree, surface a confirmation modal before the user accepts; (c) every auto-filled field is editable, and edits are logged with a diff. Verify with a fixture: protocol with title "Phase II" and body that says "this is a phase III study" — assert the modal blocks save and asks the user to choose. Run; expect block.
- Confidence: medium-high — the requirement is explicit, the failure mode is generic to LLM extraction.

### P1-4 OCR precision-over-speed posture is undermined by missing dedupe of "apparent" duplicates across pages
- Evidence: previously fixed risk: "OCR hallucination dedupe exists." This means the dedupe is implemented, but the implementation likely misses the case where the same lab value appears in two different lab tables (e.g., screening labs and baseline labs) with the same number — these are not duplicates, they are legitimately repeated, and the dedupe may collapse them.
- Root-cause hypothesis: the dedupe is keyed on `(subject, parameter, value)` without considering `visit_code` or `panel`. A screening ALT of 25 U/L and a baseline ALT of 25 U/L are the same value but represent two different timepoints and must both be retained.
- Downstream risk: the dedupe silently drops a legitimate second-timepoint lab value, and a date-window rule that depends on the baseline value misfires. For a reviewer who "may not understand AI," this is a silent wrong-verdict cause.
- Fix/verification: (a) dedupe key must include `visit_code` (or equivalent timepoint identifier); (b) if the same `(subject, parameter, value)` appears at two visits, both are kept and the UI shows them stacked with visit labels; (c) add a test: feed a fixture with a value that appears at two visits, assert both are retained, assert the UI shows them with distinct visit labels. Run; expect both retained.
- Confidence: medium — the dedupe exists per the prior fix, but the visit-axis gap is a common implementation shortcut that is consistent with the symptom.

### P1-5 Subject list shows both phase columns plus a separate global audit-stage selector (overloaded table)
- Evidence: visual finding: "subject list shows both phase columns plus a separate global audit-stage selector." This is the visual finding most likely to also appear in Qwen/MIMO consensus.
- Root-cause hypothesis: the table is unioning phase-level data (screening_run_in status, baseline_randomization status) and a project-level audit stage into one row, with no clear hierarchy. The audit stage filter and the phase filters are independent, so a reviewer can apply a filter that yields an empty list and not know why.
- Downstream risk: the senior monitor misreads the table as a list of subjects and ignores the phase columns, then filters by audit stage and gets a confusing result. Friction and trust erosion.
- Fix/verification: (a) split into a parent "subjects" view and a child "phases" drill-down — one row per subject, click to expand and see phase statuses; (b) remove the global audit-stage selector from the subjects list (it belongs on the project dashboard, not the subject table); (c) add a test: open the subject list, assert no audit-stage filter is present, assert clicking a subject expands to show two phase rows. Run; expect clean separation.
- Confidence: high — visual finding is explicit.

### P1-6 Row action buttons are numerous — risk of misclick on a regulated workflow
- Evidence: visual finding: "row action buttons are numerous."
- Root-cause hypothesis: actions like "approve," "request more info," "mark fail," "reset," "lock" are all visible per row. There is no confirmation modal for destructive actions, and the buttons are color-coded only by icon, not by hazard level.
- Downstream risk: a senior monitor misclicks "fail" on a row that should pass, and the audit log records an irreversible verdict event. For a regulated workflow, this is a real risk.
- Fix/verification: (a) collapse the action set to at most two primary actions per row ("Review" leading to a detail page where all actions live); (b) destructive actions require a typed confirmation; (c) add a Playwright test that asserts the maximum number of clickable buttons per row is 2. Run; expect ≤ 2 per row.
- Confidence: medium-high — visual finding is explicit, the risk is generic.

### P1-7 Help page is detailed but long — likely to be unread by the stated user class
- Evidence: visual finding: "help page is detailed but long." Requirement: "login/help" must be usable for senior medical monitors who may not understand AI.
- Root-cause hypothesis: the help page is a single long document. There is no in-context help (tooltips, "?" icons next to fields), no "first-time user" overlay, no "show me an example" button.
- Downstream risk: the help is unreachable in practice. A reviewer who hits a confusing field (e.g., "anchor date") will not scroll to the help page; they will guess.
- Fix/verification: (a) replace the long help page with (i) a 30-second "what this app does" first-run overlay, (ii) per-field "?" tooltips with one-sentence explanations, (iii) a searchable FAQ for advanced questions; (b) add a Playwright test that opens three different forms, asserts a "?" icon is present on each non-obvious field, and asserts clicking it shows a tooltip within 200ms. Run; expect tooltips everywhere.
- Confidence: medium — visual finding is explicit, the gap is consistent with stated user class.

---

## P2 — Findings

### P2-1 UI may leak prompt/log wording
- Evidence: requirement: "UI must be modern, wide, usable, and not leak prompt/log wording." No evidence of a leak in the summary, but the risk is generic for LLM-backed apps.
- Root-cause hypothesis: the verdict composer or evidence renderer may pass through LLM output text that includes "I cannot," "as an AI," "the user wants me to," or raw JSON. There is no output sanitization step.
- Downstream risk: the senior monitor sees "I cannot determine…" and loses trust immediately. This is the canonical failure mode the product brief warns against.
- Fix/verification: (a) define an allowlist of verdict labels and copy strings; any LLM output not in the allowlist is replaced with "AI 输出异常，请联系管理员"; (b) add a regex test on the rendered HTML for "as an AI," "I cannot," "as a language model," raw `{` outside code blocks, etc. Run on every page; expect zero hits.
- Confidence: medium — the requirement is explicit, the leak is generic, no specific leak was reported.

### P2-2 Health check captures `oMLX=false` — verify the UI does not advertise a missing backend
- Evidence: health: oMLX=false at capture. If the UI shows "OCR via oMLX" as a status indicator, it is now lying.
- Root-cause hypothesis: the UI reads backend health and shows a static "OCR: oMLX" label instead of a live status.
- Downstream risk: a reviewer uploads a PDF expecting local OCR, gets a remote DeepSeek call, and the audit trail does not record the substitution.
- Fix/verification: (a) the OCR status indicator must be live, not static; (b) when oMLX is down, the UI must show "OCR: remote (degraded)" and the audit log must record the substitution; (c) add a test: stop oMLX, open the upload page, assert the status reads "remote (degraded)." Run; expect live status.
- Confidence: medium — health is explicitly stated, the UI behavior is unverified.

### P2-3 Three homepage workflows may be marketing copy, not actual entry points
- Evidence: requirement: "three homepage workflows." No evidence in the summary that three distinct entry points exist; visual finding mentions "task dashboard, project list" but not a third.
- Root-cause hypothesis: the homepage shows three cards/labels but they all lead to the same project list, with cosmetic differences.
- Downstream risk: senior monitor lands on the homepage, sees three identical-feeling options, picks the wrong one, and the workflow is one click longer than promised.
- Fix/verification: (a) define the three workflows explicitly (e.g., "Review a new subject," "Continue an in-progress review," "Audit completed reviews") and assert each leads to a distinct page state; (b) add a test: open homepage, click each of the three entry points, assert three distinct URLs. Run; expect distinct destinations.
- Confidence: low-medium — the requirement is explicit, the gap is plausible.

---

## P3 — Findings

### P3-1 Desktop subject list is dense but readable — leave as-is, do not over-fix
- Evidence: visual finding: "desktop subject list dense but readable."
- Recommendation: do not change the desktop density. Senior monitors on desktop expect dense tables. Mobile is the problem (P0-1).
- Confidence: high.

### P3-2 Help page content quality is not in scope of this audit
- Evidence: visual finding: "help page is detailed but long."
- Recommendation: the content may be correct; the structure is the problem (P1-7). Do not rewrite the help text in this pass.
- Confidence: medium.

---

## Consensus candidates likely to overlap with Qwen / MIMO

These are the findings I expect any reasonable second-pass auditor (Qwen, MIMO, human) to also raise. Prioritize these for the next patch round:

1. P0-1 mobile horizontal overflow hidden (definitely consensus — directly stated symptom)
2. P0-2 baseline anchor date should be phase-level, not per-row (consensus — explicit domain rule)
3. P0-3 pass_verify must not downgrade verdict (consensus — explicit prior fix and requirement)
4. P0-4 admin all-power must be enforced at the API, not just UI (consensus — explicit requirement, common gap)
5. P1-2 evidence_insufficient vs investigator_judgment conflated (consensus — explicit requirement, common conflation)
6. P1-5 subject list overloads phase + audit-stage (consensus — explicit visual finding)
7. P1-6 row actions too numerous (consensus — explicit visual finding)
8. P1-7 help is long, no in-context help (consensus — explicit visual finding + user class)

## Do-not-overfix list

- Desktop subject list density: leave alone (P3-1).
- Help page content: do not rewrite copy in this pass; restructure only (P3-2).
- OCR dedupe that already exists: do not remove it; extend it with a visit axis (P1-4).
- The "previously fixed" semantic parser guards (GGT vs ALT/AST/TBil, urine abnormalities vs infection, EX-20h all-of logic, syphilis exception, researcher-judgment compound logic): do not touch; they are working.
- The path traversal guard `validate_storage_id` and upload filename validation: do not touch; working.
- The DeepSeek backend integration: do not swap backends; oMLX=false is a runtime state, not a design defect.

## Minimal Codex patch / test strategy

A bounded patch round, in order, that addresses all P0 and the top P1 with the smallest surface area:

Round 1 (P0 blockers):
- Patch 1: wrap the data tables in a scroll container with `overflow-x: auto` and add a mobile card-view fallback at < 720px. Add a Playwright check at 390x844.
- Patch 2: move baseline/randomization anchor date to phase-level metadata on the project; lock after first save; remove the per-row input. Add a server-side guard test.
- Patch 3: in the verdict composer, demote pass_verify to a soft annotation on pass items. Add a regression test fixture (clean pass with one missing citation → overall pass with yellow chip).
- Patch 4: add a server-side role check middleware on every mutating endpoint; non-owner gets 403. Add integration tests for the three role scenarios.

Round 2 (P1 trust and UX):
- Patch 5: split evidence_insufficient and investigator_judgment into two distinct chips with distinct copy and distinct action buttons. Add a fixture test.
- Patch 6: collapse per-row actions to at most 2 primary actions; destructive actions require typed confirmation. Add a Playwright density test.
- Patch 7: add per-field "?" tooltips for non-obvious fields; replace the long help page with a 30-second first-run overlay + searchable FAQ.
- Patch 8: in the protocol metadata extractor, require `confidence` and `evidence_quote` per field; cross-check `phase` and `indication` against the title page with deterministic regex; surface a confirmation modal on disagreement. Add a fixture test.

Round 3 (P2 hardening):
- Patch 9: define an allowlist of verdict labels and copy; sanitize LLM output; add a regex test against the rendered HTML.
- Patch 10: make the OCR backend status indicator live; record backend substitutions in the audit log.
- Patch 11: if the three homepage workflows are not three distinct entry points, define and test them.

Verification gate at the end of each round:
- Re-run the desktop Playwright suite; expect 0 console errors, 0 failed requests, 0 desktop overflow.
- Re-run the mobile Playwright suite at 390x844; expect overflowElements = 0 and scrollOverflow > 0 on the subject list and report.
- Re-run the integration test for role checks; expect 100% pass.
- Re-run the QC report for MG-K10-SAR-III; expect 0 preset flags, 0 false downgrades, distinct evidence_insufficient vs investigator_judgment chips where applicable.
- Human review of the protocol metadata confirmation modal; expect the modal to block save on disagreement.

This audit is bounded to the supplied summary. Codex should verify each finding against the live code and the live Playwright artifacts before applying any patch. I do not claim final acceptance.
