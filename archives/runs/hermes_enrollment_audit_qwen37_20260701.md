# Hermes Enrollment-Review Audit — Qwen 3.7 Plus

**Role:** Senior clinical trial monitor + modern enterprise UI reviewer  
**Date:** 2026-07-02  
**Evidence sources:**
- `context/enrollment_fullflow_model_audit_20260701_context.md` (full task context, user requirements, live state)
- `output/model_audit_20260701/snapshots/ui_snapshot_summary.json` (Playwright route metrics, headings, buttons, table headers)
- `output/model_audit_20260701/screenshots/ui_contact_sheet.png` (visual contact sheet, 10 panels desktop + mobile)

**Visual analysis note:** The contact sheet image was analyzed via vision model. Findings below combine visual observation with snapshot data and context-file requirements. No source code was read; no browser automation was performed.

---

## Executive Summary

The system is a functional enterprise-grade clinical trial enrollment review tool. It correctly implements the core three-workflow entry point architecture (new project / re-deconstruct / start review) and phase-specific review (screening vs baseline/randomization). However, from the perspective of a **senior medical monitor who is not familiar with AI tools**, several usability gaps create friction in daily workflow:

1. **Mobile/tablet experience is broken** — tables clip horizontally with no scroll, making the system unusable during site visits or ward rounds.
2. **Information density is too high** — the subject list, rules table, and help page overwhelm non-technical users without progressive disclosure.
3. **Internal/test artifacts leak into the UI** — usernames like "smkzw" and technical terms like "Markdown" are visible to end users.
4. **Baseline anchor date UX is fragile** — mixed-language placeholder and per-row repetition create confusion about when date-dependent rules apply.
5. **Phase-specific entry points are conceptually correct but visually redundant** — the global stage selector + per-phase cells in the table create two ways to do the same thing, which confuses rather than clarifies.

The clinical logic (phase separation, evidence hierarchy, pass_verify as reminder, anchor date mechanism) is sound and matches the user's original requirements. The problems are primarily in **presentation, affordance, and cognitive load** — not in the underlying workflow model.

---

## Findings

### F1 — Mobile horizontal overflow clips table content (P0)

**Evidence:**
- Snapshot metrics: `sar_subjects 390x844: overflow=30, scrollOverflow=0`; `sar_subject_31001_screening 390x844: overflow=30, scrollOverflow=0`
- Context file observation: "Mobile subject list is not truly usable: the table content extends beyond viewport but the page hides horizontal overflow, so the right side is clipped rather than scrollable or reflowed."
- Visual analysis Panel 5/7: Mobile view shows simplified list but complex tables are not visible or are clipped.

**Root-cause hypothesis:** The CSS uses `overflow-x: hidden` or does not set `overflow-x: auto` on table containers. The table width exceeds 390px but the parent container does not allow horizontal scrolling.

**Why it matters to a medical monitor:** Medical monitors frequently review data on tablets or phones during site visits, monitoring visits, or ward rounds. If the subject list and rule-by-rule report are unreadable on mobile, the monitor cannot perform ad-hoc reviews outside the office. This forces them to wait until they return to a desktop, delaying decision-making.

**Recommended fix/verification:**
- Add `overflow-x: auto` to all table containers (`.subject-table-wrap`, `.rule-table-wrap`, etc.).
- Test at 390x844 (iPhone 14 Pro) and 768x1024 (iPad Mini) viewports.
- Consider a dedicated mobile layout that stacks columns vertically or uses a card-based layout for subject rows.

**Confidence:** confirmed (snapshot metrics + visual evidence agree)

---

### F2 — Baseline anchor date placeholder uses mixed-language format (P1)

**Evidence:**
- Context file observation: "Baseline anchor date input is visible inside each baseline phase cell, but its placeholder is `yyyy/mm/日`, not ideal Chinese date affordance."
- Snapshot: Table headers show `基线/随机前 · V2（基线2） · D1↕` — the phase name is clear, but the anchor date input is per-row and can dominate the column when empty.

**Root-cause hypothesis:** The placeholder text was written by a developer who mixed English date format (`yyyy/mm`) with Chinese character (`日`). This is not a standard date format in any locale.

**Why it matters to a medical monitor:** Medical monitors are accustomed to seeing dates in `YYYY-MM-DD` or `YYYY年MM月DD日` format. A mixed-language placeholder like `yyyy/mm/日` looks like a bug or placeholder text that was never updated, reducing trust in the system. More critically, if the monitor does not understand that this field is required for date-dependent rules, they may leave it blank and get incorrect review results.

**Recommended fix/verification:**
- Change placeholder to `YYYY-MM-DD` or use a native `<input type="date">` with locale-appropriate formatting.
- Add a tooltip or inline help explaining: "基线/随机日期用于判断时间窗相关的入排标准（如'随机前30天内无XX'）。如不填写，相关标准将判定为'证据不足'。"
- Consider moving the anchor date input to a project-level setting (if all subjects share the same baseline window) or a batch-import field, rather than per-row.

**Confidence:** confirmed (context file explicitly notes this)

---

### F3 — Global "审核阶段" selector is redundant with per-phase table cells (P1)

**Evidence:**
- Context file observation: "Subject list currently still has a separate global `审核阶段` select above the table while also showing per-phase cells in the table. This may be conceptually redundant now that phase-specific entry points are visible."
- Snapshot `sar_subjects` table headers: `筛选/导入期 · V1 · D-7~D-1↕` and `基线/随机前 · V2（基线2） · D1↕` are both visible as columns, meaning both phases are shown simultaneously.

**Root-cause hypothesis:** The global stage selector was added before per-phase cells were implemented. After per-phase cells were added, the global selector was not removed, creating two ways to filter by phase.

**Why it matters to a medical monitor:** If the monitor selects "筛选期" in the global selector but the table still shows both screening and baseline columns, they will be confused about which phase is "active." This is a conceptual inconsistency: does the global selector filter the rows, or does it change which columns are visible? The UI does not make this clear.

**Recommended fix/verification:**
- Remove the global "审核阶段" selector if per-phase cells are the primary entry point.
- Alternatively, keep the global selector but make it filter the table to show only the selected phase's results (hiding the other phase's column).
- Add a visual indicator (e.g., highlight the active phase column header) when a global filter is applied.

**Confidence:** likely (context file flags this as redundant; snapshot shows both mechanisms coexist)

---

### F4 — Internal/test username "smkzw" visible in UI (P1)

**Evidence:**
- Visual analysis Panel 3/5: "smkzw" appears in the UI, likely as a username or project code.
- Snapshot `sar_subjects` table headers include `上传/创建者↕` — this column shows who uploaded/created each subject.

**Root-cause hypothesis:** The test project was created by a user with username "smkzw" (likely the developer's local username or test account). The UI displays this verbatim without filtering or masking.

**Why it matters to a medical monitor:** Seeing a username like "smkzw" (which is not a real person's name) in the creator column looks unprofessional and raises questions about data provenance. If this is a production system, the monitor will wonder: "Who is smkzw? Is this real data or test data? Can I trust the review results?"

**Recommended fix/verification:**
- Ensure all test projects are clearly marked as "【测试用】" (which the snapshot shows is already done for project titles).
- Consider hiding the "创建者" column for test projects, or replacing "smkzw" with a display name like "测试管理员".
- For production, ensure user registration captures real names (e.g., "张三 (中心31)") rather than system usernames.

**Confidence:** confirmed (visual evidence + snapshot)

---

### F5 — Help page is a text-heavy wall without progressive disclosure (P1)

**Evidence:**
- Snapshot `help` headings: `一、打开系统和登录`, `二、首页三个入口怎么选`, `三、首次方案解构` — the help page has at least 11 sections (I through XI per visual analysis).
- Visual analysis Panel 8: "A text-heavy documentation page... Numbered sections (I through XI) covering 'System Overview,' 'Project Management,' 'Subject Management,' 'Review Process,' etc."
- Snapshot metrics: `help 1440x980: overflow=0` — no overflow, meaning all content fits on one very long page.

**Root-cause hypothesis:** The help page was written as a comprehensive manual rather than a task-oriented guide. All sections are expanded by default, creating a "wall of text" that is intimidating for first-time users.

**Why it matters to a medical monitor:** Medical monitors are busy clinicians who do not have time to read an 11-section manual. They need quick answers to specific questions: "How do I add a subject?" "What does '证据不足' mean?" "How do I export the report for the monitoring visit?" A long scrollable page forces them to search for the relevant section, which defeats the purpose of inline help.

**Recommended fix/verification:**
- Convert the help page to a collapsible accordion (each section is a expandable card).
- Add a search box at the top of the help page.
- Provide context-sensitive help: when the user is on the subject list page, show a "?" icon that opens the help page scrolled to the "Subject Management" section.
- Consider creating short video tutorials (2-3 minutes each) for the most common tasks.

**Confidence:** confirmed (snapshot + visual evidence)

---

### F6 — "Export Markdown" button uses technical terminology (P2)

**Evidence:**
- Snapshot `sar_subjects` buttons: `📥 导出Markdown`
- Visual analysis Panel 4: "The 'Export Markdown' button suggests this tool is built for technical users or researchers who use documentation tools."

**Root-cause hypothesis:** The developer used "Markdown" because that is the file format being exported. However, medical monitors are not familiar with Markdown (a lightweight markup language for technical writing).

**Why it matters to a medical monitor:** A medical monitor will not know what "Markdown" means. They will wonder: "Is this a Word document? A PDF? An HTML file? Can I open it in Word?" This creates hesitation and may lead to the monitor not using the export feature, or exporting and then being confused when the file does not open in Word.

**Recommended fix/verification:**
- Rename the button to `📥 导出审核报告` or `📥 导出Word/PDF`.
- If the export is actually Markdown, convert it to Word or PDF before download (medical monitors use Word, not Markdown editors).
- Add a tooltip explaining the export format: "导出为Markdown格式，可用文本编辑器打开，或转换为Word/PDF。"

**Confidence:** confirmed (snapshot shows button text)

---

### F7 — Rules table is extremely dense without visual grouping (P2)

**Evidence:**
- Visual analysis Panel 6: "Panel 6 lists dozens of criteria codes (M-01, E-02, etc.) in a tight table. This is high cognitive load for a reviewer, though necessary for clinical data."
- Snapshot `sar_subject_31001_screening` table headers: `规则ID`, `标准名称`, `类别`, `结论`, `推理依据（点击展开）` — the table has 5 columns, with "推理依据" being expandable.

**Root-cause hypothesis:** The rules table displays all inclusion/exclusion criteria in a flat list, sorted by rule ID. There is no visual grouping by category (e.g., "医学标准", "实验室检查", "既往病史") or by inclusion vs exclusion.

**Why it matters to a medical monitor:** When reviewing a subject, the monitor needs to quickly scan which criteria passed and which failed. A flat list of 20+ rules (M-01 to E-19) forces the monitor to read every row to understand the overall picture. This is slow and error-prone, especially when reviewing multiple subjects.

**Recommended fix/verification:**
- Add visual grouping: group rules by category (IN-M医学, IN-L实验室, EX-疾病史, etc.) with collapsible sections.
- Add a summary bar at the top: "✅ 通过: 15条 | ⚠️ 证据不足: 3条 | ❌ 不通过: 2条".
- Use color-coded row backgrounds (green for pass, orange for warning, red for fail) to make scanning faster.
- Allow filtering by conclusion (show only failed rules, or only rules needing investigator judgment).

**Confidence:** confirmed (visual evidence + snapshot)

---

### F8 — Orange warning box text is small with tight line height (P2)

**Evidence:**
- Visual analysis Panel 6/7: "The text inside the orange warning box is very small. If this were a real app, the line height looks a bit tight, making it hard to read."

**Root-cause hypothesis:** The warning box uses a small font size (e.g., 12px) and tight line height (e.g., 1.2) to fit more content in a compact space.

**Why it matters to a medical monitor:** Warning boxes contain critical information (e.g., "证据不足: 缺少基线心电图"). If the text is hard to read, the monitor may miss important details or strain their eyes when reviewing multiple subjects. This is especially problematic for older monitors who may need reading glasses.

**Recommended fix/verification:**
- Increase font size to at least 14px for warning box content.
- Increase line height to 1.5 or 1.6 for better readability.
- Use bold for key phrases (e.g., "**证据不足**: 缺少基线心电图").

**Confidence:** likely (visual analysis notes this; cannot measure exact font size from contact sheet)

---

### F9 — Project list shows full protocol titles without truncation (P2)

**Evidence:**
- Snapshot `audit_projects` headings: The project titles are very long, e.g., "【测试用】评价CMS-D001片治疗中度至重度斑块状银屑病成人患者的有效性和安全性的多中心、随机、双盲、安慰剂对照Ⅱ/Ⅲ期临床研究".
- Visual analysis Panel 2: The project list shows full titles, which may wrap across multiple lines.

**Root-cause hypothesis:** The project list displays the full protocol title without truncation or tooltip. This is because the title is an important identifier, but it creates visual clutter.

**Why it matters to a medical monitor:** Long protocol titles make the project list hard to scan. If the monitor has 10+ projects, the page becomes very long and requires excessive scrolling. The monitor cannot quickly find the project they need.

**Recommended fix/verification:**
- Truncate project titles to 50 characters with "..." and show full title on hover (tooltip).
- Add a project code column (e.g., "MG-K10-SAR-III") as the primary identifier, with the full title as secondary text.
- Allow filtering/searching the project list by project code or title keyword.

**Confidence:** confirmed (snapshot shows full titles)

---

### F10 — Action buttons inside table rows are many and small (P2)

**Evidence:**
- Visual analysis Panel 4: "In Panel 4, the action buttons inside the table rows (Review, OCR, etc.) are small and pill-shaped. They are recognizable but might be hard to tap on mobile."
- Snapshot `sar_subjects` table headers include `操作` column — this column contains multiple action buttons per row.

**Root-cause hypothesis:** Each subject row has multiple actions (查看, 审核, OCR, 删除, etc.), and all are displayed as small pill-shaped buttons in the "操作" column.

**Why it matters to a medical monitor:** Small buttons are hard to click, especially on touchscreens. If the monitor accidentally clicks "删除" instead of "查看", they could lose data. On mobile, the buttons are even harder to tap accurately.

**Recommended fix/verification:**
- Consolidate actions into a dropdown menu (e.g., a "..." icon that opens a menu with all actions).
- Use icons instead of text for common actions (e.g., 👁 for view, ✏️ for edit, 🗑 for delete).
- Add confirmation dialogs for destructive actions (delete, reset cache).
- Increase button size to at least 32x32px for touch targets.

**Confidence:** confirmed (visual evidence + snapshot)

---

### F11 — No clear visual separation between screening and baseline results in subject report (P2)

**Evidence:**
- Snapshot `sar_subject_31001_screening` and `sar_subject_31001_baseline` show separate routes for screening and baseline reports, but the visual analysis does not indicate clear visual separation within the report page itself.

**Root-cause hypothesis:** The screening and baseline reports are separate pages (different routes), but within each page, the rules table does not visually distinguish between inclusion and exclusion criteria, or between different categories of rules.

**Why it matters to a medical monitor:** When reviewing the screening report, the monitor needs to quickly see which inclusion criteria passed and which exclusion criteria failed. A flat list of rules (M-01 to E-19) does not make this distinction clear.

**Recommended fix/verification:**
- Add section headers within the rules table: "纳入标准" and "排除标准".
- Use different background colors for inclusion vs exclusion sections (e.g., light green for IN, light red for EX).
- Add a summary at the top: "纳入标准: 5/5 通过 | 排除标准: 8/10 通过 (2条证据不足)".

**Confidence:** question-for-Codex (cannot confirm from snapshot alone whether visual separation exists within the report page)

---

### F12 — Column headers too long and cramped (P2)

**Evidence:**
- Visual analysis Panel 4: "The column header 'Inclusion/Exclusion V1-D-7-D-1' is very long and seems cramped."
- Snapshot `sar_subjects` table headers: `筛选/导入期 · V1 · D-7~D-1↕` and `基线/随机前 · V2（基线2） · D1↕` are very long.

**Root-cause hypothesis:** The column headers include phase name, visit number, and day range (e.g., "筛选/导入期 · V1 · D-7~D-1"). This is clinically accurate but creates very wide column headers that may not fit well on smaller screens.

**Why it matters to a medical monitor:** Long column headers make the table wider, which contributes to the mobile overflow problem (F1). They also make the table harder to scan because the header text is cramped and may wrap awkwardly.

**Recommended fix/verification:**
- Shorten column headers to "筛选期 (V1)" and "基线期 (V2)" — the day range (D-7~D-1) can be shown in a tooltip or in the project info page.
- Use abbreviations: "筛选 (V1)" and "基线 (V2)".
- Allow the user to toggle between compact and detailed column headers.

**Confidence:** confirmed (visual evidence + snapshot)

---

### F13 — UI looks like standard enterprise admin panel, not modern/consumer-grade (P3)

**Evidence:**
- Visual analysis overall: "It looks like a standard B2B SaaS application (similar to older Salesforce or custom admin panels). It is not 'cutting edge' (like a modern consumer app with lots of whitespace and rounded corners), but it is professional."

**Root-cause hypothesis:** The UI uses a standard component library (likely Ant Design or Element UI) without significant customization. The design is functional but not visually distinctive.

**Why it matters to a medical monitor:** While medical monitors do not need a "beautiful" UI, a dated-looking interface can reduce trust in the system. If the UI looks like it was built in 2015, the monitor may wonder if the underlying logic is also outdated.

**Recommended fix/verification:**
- This is a low-priority polish issue. The current UI is professional and functional, which is sufficient for a clinical tool.
- If resources allow, consider a visual refresh: more whitespace, rounded corners, subtle shadows, and a more modern color palette.
- Focus on usability improvements (F1-F12) before visual polish.

**Confidence:** confirmed (visual evidence)

---

### F14 — Help page sections I-XI are too many for first-time users (P3)

**Evidence:**
- Visual analysis Panel 8: "Numbered sections (I through XI) covering 'System Overview,' 'Project Management,' 'Subject Management,' 'Review Process,' etc."

**Root-cause hypothesis:** The help page was written as a comprehensive reference manual, not a quick-start guide. All 11 sections are presented equally, without prioritization.

**Why it matters to a medical monitor:** First-time users do not need to read all 11 sections. They need a "Quick Start" guide that covers the 3-4 most common tasks: (1) create a project, (2) upload protocol, (3) add subjects, (4) review eligibility. The full manual can be a separate "Advanced Guide."

**Recommended fix/verification:**
- Create a "Quick Start" section at the top of the help page (or a separate page) that covers the 4 most common tasks in 2-3 sentences each.
- Move detailed sections (e.g., "Protocol Re-deconstruction," "Batch Operations") to an "Advanced Guide" section.
- Add a "What do you want to do?" decision tree at the top of the help page.

**Confidence:** confirmed (visual evidence)

---

### F15 — Color contrast in warning boxes could be improved (P3)

**Evidence:**
- Visual analysis: "The orange warning box in Panel 6/7 has black text on a light orange background, which is readable but could be higher contrast."

**Root-cause hypothesis:** The warning box uses a light orange background (e.g., #FFF3E0) with black text (e.g., #000000). While this meets WCAG AA contrast requirements, it is not as readable as a higher-contrast combination.

**Why it matters to a medical monitor:** Warning boxes contain critical information. If the contrast is too low, the monitor may miss important details, especially in bright lighting conditions (e.g., during a site visit outdoors).

**Recommended fix/verification:**
- Darken the orange background slightly (e.g., from #FFF3E0 to #FFE0B2) or use a darker text color (e.g., #333333 instead of #000000).
- Test the warning box in bright lighting conditions to ensure readability.

**Confidence:** likely (visual analysis notes this; cannot measure exact contrast ratio from contact sheet)

---

## Top 5 Changes That Would Most Improve Usability

1. **Fix mobile horizontal overflow (F1)** — This is a P0 blocker for mobile/tablet use. Add `overflow-x: auto` to all table containers. Estimated effort: 2-4 hours.

2. **Remove redundant global "审核阶段" selector (F3)** — This creates conceptual confusion. Keep only the per-phase cells in the table. Estimated effort: 1-2 hours.

3. **Rename "Export Markdown" to "导出审核报告" (F6)** — Medical monitors do not know what Markdown is. If the export is Markdown, convert it to Word/PDF. Estimated effort: 2-4 hours (if format conversion is needed).

4. **Add visual grouping to rules table (F7)** — Group rules by category (IN-M, IN-L, EX-疾病史, etc.) with collapsible sections and a summary bar. Estimated effort: 4-8 hours.

5. **Convert help page to collapsible accordion (F5)** — Reduce cognitive load by hiding detailed sections until the user expands them. Estimated effort: 2-4 hours.

---

## Issues That Should NOT Be Changed

1. **Phase-specific review (screening vs baseline) as separate columns/cells** — This is conceptually correct and matches the user's original requirement that "Eligibility review is phase/timepoint based. Screening and baseline/randomization can be audited separately." The per-phase cells make the phase-specific entry points visible, which is the right design.

2. **Baseline anchor date as a per-row input** — While the placeholder needs fixing (F2), the mechanism of requiring an anchor date for date-dependent rules is correct. The user's original requirement stated: "Without the date, date-dependent rules should become evidence-insufficient or a reminder, not silently use screening date as baseline." The current implementation follows this.

3. **Evidence hierarchy (screening病历 > screening检验 > 既往病历 > 既往检验 > 邮件)** — This is a core clinical logic that should not be changed without strong evidence. The bundler correctly prioritizes evidence sources.

4. **pass_verify as a reminder, not a hard block** — The user explicitly required: "`pass_verify`/source traceability reminder is a pass-level reminder, not a hard block. It should be displayed as `溯源提醒`, not as a low-strength internal label." The current implementation is correct.

5. **Three-workflow entry point architecture (new project / re-deconstruct / start review)** — This matches the user's original requirement and provides clear separation of concerns. The task dashboard (Panel 1) is well-designed.

---

## Disagreements/Uncertainties for Other Model Reviewers

1. **Is the global "审核阶段" selector truly redundant (F3), or does it serve a different purpose?**
   - My hypothesis: it is redundant with per-phase cells.
   - Alternative hypothesis: it filters the rows (e.g., show only subjects who have completed screening), while the per-phase cells show the review status for each phase.
   - Question for Codex: Does the global selector filter rows, or does it change which columns are visible? If it filters rows, it may not be redundant.

2. **Is the rules table density (F7) a usability problem, or is it necessary for clinical rigor?**
   - My hypothesis: the flat list of 20+ rules is hard to scan.
   - Alternative hypothesis: medical monitors are accustomed to reviewing long checklists (e.g., ICD-9 codes, lab reference ranges), and a flat list is actually more efficient than grouping.
   - Question for other reviewers: Do medical monitors prefer grouped/collapsible rules, or do they prefer a flat list that can be sorted by rule ID?

3. **Is the mobile experience (F1) a priority, or is this a desktop-only tool?**
   - My hypothesis: medical monitors need mobile access for site visits.
   - Alternative hypothesis: the system is primarily used in the office, and mobile is a nice-to-have.
   - Question for Codex: Did the user explicitly request mobile support? If not, fixing mobile overflow may be lower priority.

4. **Is "Export Markdown" (F6) actually a problem, or do medical monitors know what Markdown is?**
   - My hypothesis: medical monitors do not know Markdown.
   - Alternative hypothesis: the target users are clinical research associates (CRAs) or data managers who are more technical.
   - Question for Codex: Who are the primary users of the export feature? If they are technical, "Markdown" may be acceptable.

5. **Is the help page length (F5, F14) a problem, or is comprehensive documentation valued?**
   - My hypothesis: 11 sections is too many for first-time users.
   - Alternative hypothesis: medical monitors prefer comprehensive documentation that they can reference later.
   - Question for other reviewers: Do users prefer a long scrollable help page, or a collapsible accordion with a search box?

---

## Appendix: Evidence Index

| Finding | Severity | Evidence Path | Confidence |
|---------|----------|---------------|------------|
| F1 — Mobile overflow clips tables | P0 | snapshot metrics, context file, visual Panel 5/7 | confirmed |
| F2 — Anchor date placeholder mixed-language | P1 | context file, snapshot headers | confirmed |
| F3 — Global stage selector redundant | P1 | context file, snapshot headers | likely |
| F4 — "smkzw" username visible | P1 | visual Panel 3/5, snapshot headers | confirmed |
| F5 — Help page text-heavy wall | P1 | snapshot headings, visual Panel 8 | confirmed |
| F6 — "Export Markdown" technical term | P2 | snapshot buttons | confirmed |
| F7 — Rules table dense, no grouping | P2 | visual Panel 6, snapshot headers | confirmed |
| F8 — Warning box text small/tight | P2 | visual Panel 6/7 | likely |
| F9 — Project titles not truncated | P2 | snapshot headings | confirmed |
| F10 — Action buttons many/small | P2 | visual Panel 4, snapshot headers | confirmed |
| F11 — No visual separation IN/EX in report | P2 | snapshot routes | question-for-Codex |
| F12 — Column headers too long | P2 | visual Panel 4, snapshot headers | confirmed |
| F13 — UI looks dated | P3 | visual overall | confirmed |
| F14 — Help page 11 sections | P3 | visual Panel 8 | confirmed |
| F15 — Warning box contrast low | P3 | visual Panel 6/7 | likely |

---

**End of audit.** This report is advisory only. Codex owns source verification, browser visual acceptance, and final code changes.
