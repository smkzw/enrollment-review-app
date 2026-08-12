# Hermes Enrollment-Review Audit — MIMO V2.5 (fallback no-tool)

## Preamble

This is a mechanical no-tool audit. I cannot read source, run tests, or inspect the DOM. All findings are derived from the evidence summary Codex provided. Confidence levels reflect how directly the evidence supports each claim. Where evidence is missing (login flow, project admin), I flag the gap rather than guess.

---

## Pass/Fail Summary Table

| # | Area | Pass/Fail | Notes |
|---|------|-----------|-------|
| 1 | Login / Help / Homepage | PARTIAL | Homepage ✅. Help loads but "detailed but long" — may overwhelm. Login flow: **no evidence at all**. |
| 2 | First protocol deconstruct | PASS | Upload area, editable rules draft, LLM feedback panel, save buttons all present. |
| 3 | Existing-project re-deconstruct | PASS | Project selector, current info, original vs new result all present. |
| 4 | Project list / delete / admin | **NO EVIDENCE** | Not mentioned in desktop or mobile runs. Cannot verify. |
| 5 | Project info / center management | **NO EVIDENCE** | Not mentioned. Cannot verify. |
| 6 | Subject list phase cells | PASS | Phase-specific screening/baseline cells, status badges, baseline anchor date inputs per baseline cell present on desktop. |
| 7 | Baseline anchor-date input | PASS (desktop) | Inputs visible per baseline cell. Mobile not tested for this specific control. |
| 8 | Batch / selected actions | PASS | Checkbox selection, batch audit, rerun, reset, export all present. |
| 9 | Report page / status labels | PASS (partial) | Verdict card, source reminder, future-phase reminder, evidence-insufficient and investigator callouts, rule table all present. No evidence on label text clarity. |
| 10 | Desktop / mobile responsiveness | **FAIL (mobile)** | Desktop: clean. Mobile 390×844: SAR subject list AND SAR report both have overflowElements=30, scrollOverflow=0 — table content clipped by overflow:hidden, not scrollable or reflowed. |

---

## Detailed Findings

### Finding 1 — Mobile table clipping on SAR subject list (P0)

**Severity:** P0 — Data invisible to users on mobile

**Symptom:** At 390×844 viewport, the SAR subject list table has 30 overflow elements. The table content is clipped because `overflow: hidden` is applied without horizontal scrolling or responsive reflow.

**Evidence:** "SAR subject list 390x844 has overflowElements=30 and scrollOverflow=0. Codex visual: table content is clipped because horizontal overflow hidden, not scrollable/reflowed."

**Expected:** Tables with multiple columns (phase-specific cells, screening, baseline, status badges, anchor-date inputs) must either (a) be horizontally scrollable on mobile, or (b) reflow into a stacked/card layout. Clipping columns means medical monitors cannot see screening status, baseline dates, or rule-level pass/fail for individual subjects — the core work data.

**Recommended fix:** Add `overflow-x: auto` on the table container, or implement a responsive strategy where columns collapse into rows on narrow viewports. Given the table has screening + baseline + anchor-date inputs per row, horizontal scroll is the simpler fix; stacked layout risks burying the date inputs.

**Confidence:** HIGH — Codex explicitly confirmed visual clipping.

---

### Finding 2 — Mobile table clipping on SAR report (P0)

**Severity:** P0 — Report unreadable on mobile

**Symptom:** Same pattern as Finding 1. The SAR report page at 390×844 also has 30 overflow elements with content clipped by `overflow: hidden`.

**Evidence:** "SAR report 390x844 has overflowElements=30 and scrollOverflow=0. Codex visual: table content is clipped because horizontal overflow hidden, not scrollable/reflowed."

**Expected:** The report contains the verdict card, rule table, evidence callouts — the final output of the review pipeline. On mobile, the rule table (likely the "official rule numbering" table) must be scrollable or the page is unusable.

**Recommended fix:** Same as Finding 1. Priority is higher here because the report is the deliverable medical monitors share and act on.

**Confidence:** HIGH — Codex visual confirmation.

---

### Finding 3 — Login flow completely untested (P1)

**Severity:** P1 — Critical path unverified

**Symptom:** No evidence in the summary about login page rendering, authentication flow, session persistence, or post-login redirect.

**Evidence:** The summary covers "task dashboard, audit project list, first deconstruct, re-deconstruct, SAR subject list, rules, project info, subject reports, and help." Login is absent from this list.

**Expected:** Login page should (a) render cleanly on desktop and mobile, (b) handle invalid credentials gracefully, (c) redirect to task dashboard on success, (d) not expose API keys or internal paths in error messages.

**Recommended fix:** Codex should explicitly run a login flow Playwright trace covering: empty submit, wrong credentials, successful login, session expiry, and mobile viewport login.

**Confidence:** HIGH that this is a gap. Cannot assess current behavior.

---

### Finding 4 — Project list / delete / admin untested (P1)

**Severity:** P1 — Destructive actions unverified

**Symptom:** No evidence about project list rendering, delete confirmation, or admin panel behavior.

**Evidence:** Not mentioned in desktop or mobile Playwright runs.

**Expected:** Project list must (a) show project identity clearly (II vs III distinction, per constraint "preserve II/III project identity separation"), (b) delete requires confirmation and shows what will be lost, (c) admin panel does not expose raw prompts or logs.

**Recommended fix:** Codex should verify: project list page load, delete button presence and confirmation modal, project count display, and II/III label clarity.

**Confidence:** HIGH that this is a testing gap.

---

### Finding 5 — Project info / center management untested (P2)

**Severity:** P2 — Feature unverified, lower risk than P0-P1

**Symptom:** No evidence about project info page or center management (adding/removing centers for a multi-center study).

**Evidence:** Not mentioned.

**Expected:** For a 10-center study (MG-K10-SAR-III), center management should show center names/IDs, allow adding/removing centers, and not break subject-to-center associations.

**Recommended fix:** Codex should run project info page and verify center list renders, center counts match (10 centers), and center labels are human-readable.

**Confidence:** MEDIUM — cannot assess current behavior at all.

---

### Finding 6 — Help page excessive length (P2)

**Severity:** P2 — Usability concern for target audience

**Symptom:** Help page described as "detailed but long." For senior medical monitors who "may not understand AI," a wall of text is likely to be skipped entirely.

**Evidence:** "help page detailed but long."

**Expected:** Help should have a scannable table of contents or collapsible sections so a user can jump to "How do I run a batch review?" or "What does evidence-insufficient mean?" without scrolling through everything.

**Recommended fix:** Add anchor links / collapsible sections at the top. If the help page already has headings, ensure they are visible and clickable. If it's a single unstructured block, add section headers with jump links.

**Confidence:** MEDIUM — "long" is subjective; need visual inspection to determine if it's 3 screens or 15 screens of content.

---

### Finding 7 — Evidence-insufficient vs investigator distinction (verify, P1)

**Severity:** P1 if labels are ambiguous, P3 if already clear

**Symptom:** The constraint says "separate 证据不足 vs 需研究者判定." The evidence says the report has "evidence-insufficient and investigator callouts." But we cannot confirm whether the UI labels use distinct, non-interchangeable text, or whether they look similar enough to confuse.

**Evidence:** "report has verdict card, source reminder, future-phase reminder, evidence-insufficient and investigator callouts, rule table." Visual check: "Codex visual" does not explicitly call out label text.

**Expected:** Two distinct visual treatments:
- 证据不足 (evidence insufficient): amber/yellow tone, text like "本次审核依据不足，无法判定，建议补充证据后重新审核"
- 需研究者判定 (needs investigator): blue/neutral tone, text like "此条标准需研究者结合临床判断，AI无法自动判定"

These must NOT share the same color, icon, or wording pattern.

**Recommended fix:** Codex should visually inspect the report page and confirm: (a) two distinct colors, (b) two distinct icons or badges, (c) two distinct text labels, (d) no shared CSS class that makes them look identical.

**Confidence:** MEDIUM — the evidence says both are "present" but doesn't confirm visual distinction.

---

### Finding 8 — pass_verify display (verify, P2)

**Severity:** P2 — Label semantics matter for medical monitors

**Symptom:** Constraint says "pass_verify remains pass-level reminder." Need to confirm that the pass_verify state displays as pass-level (i.e., a green pass with a reminder note, not a warning or a different verdict).

**Evidence:** No explicit evidence about pass_verify rendering.

**Expected:** pass_verify should show the same visual as pass, with a subtle reminder (e.g., "此条已通过，但建议研究者确认" in small text below the green badge). It must NOT show as a separate verdict type or use warning colors.

**Recommended fix:** Codex should inspect the subject report for a subject in pass_verify state and confirm the label says pass (not pass_verify or "待确认" or similar).

**Confidence:** LOW — no direct evidence about this state's rendering.

---

### Finding 9 — Official rule numbering (verify, P2)

**Severity:** P2 — Regulatory accuracy

**Symptom:** Constraint says "official rule numbering" must be preserved. The report shows a "rule table" but we cannot confirm whether the rule numbers match the protocol's official numbering.

**Evidence:** "rule table" is present in the report page. No evidence about numbering accuracy.

**Expected:** Rule numbers in the report must exactly match the protocol document's numbering (e.g., "纳入标准 2.1" not "Rule 2" or "标准二"). If the deconstruct phase extracts rules from the protocol, the numbering should flow through to the report unchanged.

**Recommended fix:** Cross-check a sample rule number in the report against the corresponding rule in the deconstructed rules draft. If they differ, the numbering is being re-assigned during review — a bug.

**Confidence:** MEDIUM — the rule table exists; numbering accuracy is unverified.

---

### Finding 10 — Baseline anchor-date input on mobile (P2)

**Severity:** P2 — Input usability risk

**Symptom:** Anchor-date inputs are confirmed present on desktop per baseline cell. On mobile, the table itself is clipped (Finding 1), so even if the inputs exist in the DOM, they may be inaccessible.

**Evidence:** "baseline anchor date inputs per baseline cell" on desktop. Mobile overflow = 30 elements, scrollOverflow = 0.

**Expected:** Date inputs on mobile must be tappable and usable. If the table scrolls horizontally, the anchor-date column should be reachable. If the table is clipped and not scrollable, the inputs are invisible.

**Recommended fix:** Address Finding 1 first (make table scrollable). Then re-test anchor-date input on mobile to confirm it's tappable and the date picker opens.

**Confidence:** HIGH that mobile table clipping makes these inputs inaccessible.

---

### Finding 11 — Mobile overflowElements=30 is suspiciously consistent (P2)

**Severity:** P2 — Possible systemic issue

**Symptom:** Both SAR subject list AND SAR report have exactly overflowElements=30 and scrollOverflow=0 at 390×844. The consistency suggests the overflow is caused by a shared parent container or a global CSS rule, not page-specific logic.

**Evidence:** Both pages show overflowElements=30, scrollOverflow=0 at the same viewport.

**Expected:** If both pages use the same table container CSS class, the fix is a single CSS change. If they use different containers with the same bug, there's a pattern issue.

**Recommended fix:** Check if both tables share a parent container class. If yes, fix once. If no, fix both but ensure consistency.

**Confidence:** MEDIUM — 30 is suspicious but could be coincidental.

---

### Finding 12 — "No console errors" on desktop — verify persistence (P3)

**Severity:** P3 — Informational

**Symptom:** Desktop Playwright reported no console errors. This is good but should be verified across navigation paths (not just page loads).

**Evidence:** "no console errors, no failed requests."

**Expected:** Console should remain clean during: login → project list → deconstruct → re-deconstruct → subject list → batch audit → report → export.

**Recommended fix:** Run a multi-page navigation trace that exercises all routes and check console at each step.

**Confidence:** HIGH that desktop is clean for page loads. Low confidence for interactive flows.

---

### Finding 13 — No prompt/log language in UI (verify, P1)

**Severity:** P1 if violated — breaks "not AI" facade for medical monitors

**Symptom:** Constraint says "no prompt/log language in UI." This means terms like "LLM," "token," "prompt," "temperature," "context window," "model," "API," "chunk," "embedding" must not appear anywhere in the user-facing interface.

**Evidence:** The deconstruct page has "LLM feedback panel." The name "LLM feedback panel" is in the evidence summary — but is this a developer-facing label or does it appear in the UI?

**Expected:** The feedback panel should be labeled something like "解构反馈" or "方案解析结果" — never "LLM feedback." If the panel title says "LLM," medical monitors will see AI terminology.

**Recommended fix:** Codex should visually inspect the deconstruct page and confirm no AI/ML/model/API terminology is visible to the user.

**Confidence:** MEDIUM — the evidence uses developer language; unclear if the UI uses the same labels.

---

## Copy / Label Improvements for Non-AI Medical Monitors

These are suggestions based on the evidence. Codex should verify whether the current labels already handle these:

1. **"LLM feedback panel"** → Rename to "方案解析反馈" or "解构结果反馈". Never use "LLM" in user-facing text.

2. **"Deconstruct" / "Re-deconstruct"** → Consider "方案解构" / "重新解构". The English term "deconstruct" is not a standard medical/regulatory term. If the UI is in Chinese, this is fine. If it mixes English labels, standardize.

3. **"evidence-insufficient"** → "本次审核依据不足，无法自动判定" — avoids making the user feel the AI failed; frames it as a data gap.

4. **"investigator callout"** → "此条需研究者结合临床判断" — avoids "AI无法判定" framing, which sounds like a limitation. Instead, it positions the investigator as the authority.

5. **Status badges** → Ensure they use pass/fail/warning icons AND color AND text. Color-blind medical monitors need all three channels. Evidence says "status badges" are present but doesn't confirm multi-channel encoding.

6. **"batch audit"** → "批量审核" is fine if Chinese. If the button says "batch audit" in English, consider whether the audience is more comfortable with Chinese labels.

7. **"export"** → "导出报告" is more specific than just "导出". Medical monitors may not know what's being exported.

---

## Already Fixed — Leave Alone

Based on the evidence, these areas are working correctly and should NOT be re-touched:

- ✅ Homepage three-workflow-card layout — renders cleanly on both desktop and mobile
- ✅ First deconstruct page — upload area, editable rules draft, LLM feedback panel, save buttons all present and functional
- ✅ Re-deconstruct page — project selector, current info, original vs new result comparison all present
- ✅ Subject list phase cells — phase-specific screening and baseline cells with status badges, baseline anchor date inputs
- ✅ Batch/selected actions — checkbox selection, batch audit, rerun, reset, export all present
- ✅ Report page — verdict card, source reminder, future-phase reminder, evidence-insufficient and investigator callouts, rule table all present
- ✅ Desktop overflow — no overflow issues on desktop
- ✅ Desktop console — no errors, no failed requests
- ✅ API health — API ok, deepseek=true

---

## Summary

**Critical (P0):** 2 findings — mobile table clipping on SAR subject list and SAR report. These make the core data invisible on mobile and must be fixed before any mobile release.

**High (P1):** 3 findings — login untested, project admin untested, AI terminology in UI unverified. Login and project admin are critical paths that need explicit Playwright coverage. AI terminology check is a quick visual scan.

**Medium (P2):** 5 findings — help page length, pass_verify label, rule numbering, anchor-date mobile access, overflow pattern consistency. These are usability and correctness issues that degrade experience but don't block core functionality.

**Low (P3):** 1 finding — console cleanliness across navigation paths. Informational, low risk.

**No evidence (cannot audit):** Login flow, project list/delete/admin, project info/center management. These areas need explicit Codex verification before the audit can be considered complete.

**Overall verdict:** FAIL — 2 P0 mobile findings and 3 untested critical paths. The desktop experience appears solid, but mobile is broken for the two most data-dense pages, and the critical authentication/admin paths have zero test coverage in the provided evidence.
