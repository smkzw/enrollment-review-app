All evidence gathered. Compiling the full conference report.

---

# Expanded Conference Report: Kimi K3

Route: `expanded_pi_kimi_k3` (`kimi-code/k3-256k`, max effort). Lens: product/UX architecture, frontend interaction, source navigation, testable delivery.

## 1. Boundary Check And Sources Read

Boundaries honored:

- Stayed inside the workspace; read only the 27 listed files (documents, code, tests, 8 screenshots).
- Did not read the other participant's prompt, output, or log. Did not open `runs/conference/...` for this conference.
- Edited nothing. No writes to source, design, legacy projects, clinical data, or the runner-managed output path. This report is returned inline for the runner to persist.
- Did not read raw subject/protocol files. Note: `tests/test_phase_workflow.py` contains absolute fixture paths outside the workspace (e.g. `D001_SOURCE_ROOT`); I observed the path strings only, never opened them.
- One bounded external query: PaddleOCR-VL/PP-StructureV3 structured layout output (official/open-source docs only, no clinical content). Used solely to verify bounding-box availability for the provenance design.

Sources actually read (not skimmed by proxy):

- `AGENTS.md`, conference context, final design (all 421 lines), implementation plan, discovery (all 437 lines), `PROJECT_CONTEXT.md` (current milestone + relevant history), Codex conference review, `SYSTEM_REVIEW_REPORT.md`.
- Code: `app/models.py` (full), `app/router/pipeline.py` (structure + SSE lifecycle body), `app/router/projects.py` (structure), `app/router/subjects.py` (structure + upload body), `app/pipeline/ocr.py` (cache + hallucination + page pipeline), `app/pipeline/reviewer.py` (structure + full system prompt + guard inventory), `app/processing_locks.py` (full), `app/markdown_export.py` (structure), `app/llm/client.py` (OCR/review call surfaces), `static/index.html` (CSS block, routing, auth, batch loop, report render), `tests/test_phase_workflow.py` (structure).
- Visual: all six current screenshots and both comparator screenshots, inspected at pixel level.

## 2. Executive Verdict

**The baseline is directionally right and should proceed — but not yet.** The domain model, deterministic-gate spine, conflict hard-block, gap taxonomy, and prototype-first sequencing are correct responses to the audited failure modes. However, as a *buildable product design* it has a systemic weakness: it specifies clinical truth representation far more precisely than it specifies the monitor's working surface. The plan's Phase 1 prototype is exactly the right instinct, yet it is the least specified artifact in the whole packet — no fixture contract, no scripted UAT, no measurable approval gate, no statement of whether the prototype becomes the product shell. Meanwhile the single most load-bearing UX promise — "every fact and judgment clicks back to the exact original location" — rests on an OCR adapter that today returns text with no coordinates (`call_vision_ocr` → `str`), and the plan contains no spike or contract that closes that gap.

Recommendation to Codex: **conditionally approve with revisions.** Keep the architecture; revise the delivery plan around (a) a contract-first prototype that *is* the production shell against a versioned fixture API, (b) an evidence-locator contract with an explicit precision-degradation ladder and an OCR layout-capture spike, (c) an Action-Center-first information architecture, (d) an expected-evidence layer so that *absence* of evidence is as visible as presence, and (e) a model/clinical eval harness with numeric thresholds, added to the testing LOOP. All 14 frozen product decisions are preserved; nothing below contradicts them.

## 3. Defects Or Gaps In The Current Baseline

Severity scale: S1 blocks product correctness, S2 blocks build quality/approval confidence, S3 material polish.

### D1 — Prototype phase has no approval protocol, no fixture contract, no medium decision (S1)

- **Evidence:** Plan Phase 1 lists 7 build items and 5 exit gates ("用户确认信息架构、术语、密度和操作路径…"), but defines no scripted task list, no pass/fail thresholds, no fixture JSON schema deliverable, and no statement whether the prototype is throwaway or the real shell. Product decision 14 makes this prototype the gate for *all* backend spend.
- **User impact:** The monitor approves or rejects an impression, not a tested workflow. Rejection after Phase 1 has no defined remediation path; approval without task-level evidence risks locking a wrong IA into Phase 2-7.
- **Remediation:** Make Phase 1 emit three artifacts: (1) `fixture/v1` JSON schema + example subject (this schema *is* the backend contract for Phase 2); (2) production React shell reading fixtures through a stub API layer (mock service worker), so Phase 2 swaps the stub, not the UI; (3) a scripted UAT (10–14 tasks, e.g. "locate the exact source of the FEV1 fact in ≤3 clicks", "close action X by uploading the referenced report", "find all subjects blocked at baseline by owner") with measured completion rate ≥90%, zero wrong-conclusion errors, and time-to-evidence targets. Approval = UAT sign-off, not a meeting.

### D2 — EvidenceSpan locator precision is promised without a feasible capture path (S1)

- **Evidence:** Design §4.2 defines `bbox / text_range / page_excerpt / page_only` and forbids faked coordinates — good. But `app/llm/client.py:382-421` shows `call_vision_ocr` returns plain text; the adapter even strips `<|LOC_123|>` tokens ("harmless for 1.6"). Native PDF pages yield text only in the current path (PyMuPDF word-level bboxes unused). Official PaddleOCR-VL/PP-StructureV3 docs confirm the *pipeline API* emits layout JSON with `[xmin,ymin,xmax,ymax]` + reading order, but the app consumes the model through an oMLX OpenAI-compatible chat endpoint where no coordinates are returned. Whether oMLX's PaddleOCR-VL-1.6 serving exposes layout output is unverified.
- **User impact:** The monitor's core trust gesture — click a judgment, see the exact sentence highlighted on the original page — silently degrades to "here's the page, find it yourself" on exactly the scanned historical documents where verification matters most.
- **Remediation:** Define the locator contract as an explicit ladder: (1) `bbox` when backend supplies it (native PDF text via PyMuPDF words; VLM pages only if layout capture spike succeeds); (2) `text_range` via normalized fuzzy anchoring (defined algorithm: whitespace/punctuation normalization, longest-common-substring seed, multi-match disambiguation by page section, anchor hash stored); (3) `page_excerpt` with highlighted excerpt panel; (4) `page_only` with visible "precision degraded" badge. Add a Phase 4 spike: evaluate (a) oMLX layout/LOC output, (b) sidecar PaddleOCR pipeline for bbox-only pass, (c) PyMuPDF word boxes for native pages. The UI must render the ladder state per span, never silently.

### D3 — Absence of evidence is invisible in the proposed Patient Profile (S1)

- **Evidence:** Design §4.3 and discovery §12 build the profile from extracted `ClinicalFact/ClinicalEvent/MedicationExposure` — i.e., from what *exists*. Gap types like `record_incomplete` and `required_procedure_not_done` live in the rule layer, not the profile. A timeline/swim-lane visualization structurally cannot show what is missing. The comparator patient summary, notably, does handle this: explicit `未明确提供` rows in its structured summary.
- **User impact:** The monitor's hardest reasoning error is confusing "no abnormality recorded" with "normality established". A fact-driven first screen invites exactly that error, undermining the carefully built silence-vs-denial semantics (frozen decision 9).
- **Remediation:** Add a first-class `EvidenceExpectation` projection derived deterministically from `RuleComponent × WorkflowStage` (what evidence *should* exist at this episode: expected procedures, expected history inquiries, expected documents). Render a coverage matrix lane ("应备证据覆盖") where each expectation shows `observed / observed-weak / referenced-missing / absent`, each cell clickable to rule component and action. Absence becomes a rendered object, not a void.

### D4 — Component state → subject stage status rollup function is unspecified (S1)

- **Evidence:** Design §5.1 defines 7 component states per IN and EX; discovery §13.7 and §15.3 define 6 dashboard primary statuses with a sort order （明确障碍 > 当前节点必需资料/记录缺口 > 冲突 > 专业判断 > 后续关注 > 未发现障碍）. Nowhere is the deterministic mapping defined: precedence across episodes, how `provenance_followup` counts interact with "未发现明确障碍", tie-breaking, and whether `future_stage_not_due` components weight differently at current vs next episode.
- **User impact:** Two subjects with identical rule states could show different dashboard statuses depending on implementation accident — the exact "one `overall_verdict` covers everything" failure the redesign was created to kill, one level up.
- **Remediation:** Specify the rollup as a pure function table: input = component states × gap types × episode; output = primary status + per-category counts + sort key. Unit-test it against the agreed precedence, including pass-with-provenance-followup (`未发现明确障碍（溯源待办 n）`) as its own rendered variant.

### D5 — The daily-work surface is a dashboard, not a queue (S2)

- **Evidence:** Design §8.1 nav: 项目看板 / 方案解构工作台 / 受试者 / 待办中心 / 报告导出 / 系统帮助， with 项目看板 as home. 待办中心's content model is never specified. The comparator's own structure （初筛任务 / 精筛任务 as nav roots) is queue-shaped. A senior monitor's repeated question is not "what's the state of project X" but "what can I unblock today, who owes what by when".
- **User impact:** Every session starts with navigation instead of triage; due-stage urgency (e.g. baseline anchor approaching) is computed nowhere.
- **Remediation:** Home = 今日工作 (work queue): jobs running/awaiting review, actions by `due_stage × target_party`, recently changed subjects, unresolved conflicts. Project dashboard one click away. Action Center gets a defined model: filter/sort by owner/due stage/gap type/blocking, bulk-export per-party action lists (the artifact the monitor actually sends to CRC/CRA), and per-action deep links into the workbench.

### D6 — Testing LOOP lacks a model/clinical eval harness with numeric thresholds (S2)

- **Evidence:** Plan's 统一验证矩阵 lists categories but no metrics: no fact-extraction precision/recall targets, no assessment-agreement targets vs human review, no Critic false-veto budget, no OCR polarity/numeric error budget, no performance budgets (dashboard render with 100 subjects × 56 rules, batch throughput given measured ~94–143s OCR + ~40s review per subject), no visual regression or accessibility layer, no fault-injection matrix ("kill -9 at each job step" → expected recovery state). Existing suite is 131 unittest cases in one 3,006-line file, backend-only.
- **User impact:** "Better" becomes unfalsifiable; model swaps (design names DeepSeek V4 Flash baseline while history used V4 Pro) cannot be compared; regressions surface in clinical use.
- **Remediation:** Add eval layer with golden datasets built from legacy error cases (already planned as fixtures — extend with expected outputs): per-node accuracy thresholds, Critic veto precision ≥ target, polarity/numeric OCR error rate measured per document class, E2E at 3 viewports, axe-core accessibility gate, k6-style local performance budget, and a documented fault-injection checklist per job step. Thresholds are proposed defaults, calibrated in Phase 8 and owned by Codex/user.

### D7 — Single-user ≠ single-writer: human-edit concurrency unspecified (S2)

- **Evidence:** Design covers job-level DB leases, but human artifacts — corrections, rule edits, action overrides — have no optimistic-concurrency contract. One Mac still means two browser tabs, or a browser + a restore-from-backup.
- **User impact:** Silent lost-update on a correction or override is an audit-integrity bug in a system whose value is auditability.
- **Remediation:** Every mutable record carries a `revision` counter; mutations require base revision; conflict → UI shows "record changed since opened" with diff and explicit re-apply. Cheap, testable, and it makes the immutable-transition-log promise real at the API edge.

### D8 — Long-running job UX is specified at the backend, not the screen (S3)

- **Evidence:** Design §9 covers persistence/resume; §8.6 mentions batch and 8-way OCR. Unspecified: per-item job ledger UI (file 12/13 failed — *which facts/rules are now stale?*), retry granularity (page/file/subject/node), cancellation semantics at node boundaries, and pre-run time/cost estimate (historical medians exist: ~2–2.5 min/subject first pass; deconstruction ~240s).
- **User impact:** Partial failure reads as total failure or false success; the monitor cannot answer "is it safe to review subject 31008's report while 31017's OCR failed?"
- **Remediation:** Job detail page: per-item status with affected-scope surfacing (failed file → linked facts/rules/actions marked `stale`), retry at failed granularity only, cancel = cooperative stop at next node boundary with checkpoint, pre-run estimate "≈8 min, ≈¥X, 3 subjects" from rolling medians with confidence band. Failure taxonomy maps each backend failure to a named UI surface (banner / item badge / affected-scope chip).

Two lesser gaps folded into later sections: **D9** — no cross-stage ReviewRun diff view despite stage-isolation decisions (§5, §10); **D10** — no design tokens/density/keyboard/PDF-viewer component decisions for a document-heavy app (§5).

## 4. Target Product And End-To-End User Journeys

Product shape: single-Mac local app, double-click → no login → work queue. AI leads; humans close. Protocol/amendment is the only standard. Every unresolved item is an owned, dated, closable action. Every displayed fact/judgment is one click from its source page.

The monitor's mental model is a pipeline of *questions*, and the IA answers each at the moment it is asked:

**J0 — First run:** "Where do I start?" → Empty-state work queue with one primary action: 新建项目（上传方案）. No login, no ownership. Legacy projects (if present) appear in a collapsed 只读对照 section, visually sealed.

**J1 — Protocol → project:** "Is this one project or several? What standard version am I working under?" → Upload protocol → auto-extracted metadata card (name/ID/version/date, header-sanitized as today) → phase identification: independent II / independent III / non-seamless II/III = separate projects (explicit radio, not inference); seamless/adaptive only on protocol-stated continuous cohort → deconstruction draft → **Protocol Workbench**: three synchronized columns (protocol original / structured rule tree draft / change & gate report) → deterministic gate (parent counts/numbering 100% match, AND/OR/NOT structure, units, time windows, schedule coverage) → user edits/对话-refines → **Publish** creates RuleModelRevision bound to `ProtocolDocumentVersion Vx.x`. Interpretation sources (Q&A/letters/email) attach at this point with authority badges; any conflict with protocol/amendment renders a warning chip that can never be muted into approval.

**J2 — Subject intake + staged evidence:** "What do I have for this subject, at which episode, and what will it change?" → Create subject (ID, center from global roster) → choose episode （预筛/筛选/导入/基线） → explicit choice of **增量上传** vs **全量上传** with mandatory preview *before commit*: incremental preview shows `重复(去重) / 新增 / 受影响事实与规则数`; full preview shows new `EvidenceSnapshot` vs current snapshot relationship (old snapshot retained, never deleted) → commit creates a persisted Job → progress page with per-file ledger (classified → OCR → QC → facts), partial-failure surfacing (D8) → done → toast + affected-scope summary ("3 new facts, 2 rules recomputed, 1 action auto-closed candidate — review").

**J3 — Patient Profile review:** "Who is this patient longitudinally, and what matters for eligibility *right now*?" → Subject header (demographics, target disease status, current episode, anchor dates, snapshot id, open-action count) → risk-filtered swim lanes (§6) → click any event → drawer with linked rule components, risk type, source tier, and the evidence pane scrolled to the highlighted span → corrections happen here (source-preserving; polarity/numeric changes require explicit confirmation and trigger affected-scope rerun) → conflicts render as side-by-side cards, never a winner.

**J4 — Rule review (the workbench):** "For each criterion: what's decided, what's blocked, what unblocks it?" → Rule tree (official numbering) → component card (state, gate trail, facts used, typed gaps) → action card (owner, requested action, acceptable evidence, due stage, blocking) → evidence pane synchronized → professional-judgment items show exactly what wording would close them.

**J5 — Action closure loop:** "Did the new material close the gap?" → Upload (J2) → recompute → **ReviewRun diff** notification: actions `closed_system` with the closing predicate and new span cited; contested/polarity changes flagged for confirmation; user may override/reopen with mandatory reason; everything in the immutable transition log.

**J6 — Stage escalation:** "Screening passed; what changes at baseline?" → Open baseline episode → `future_stage_not_due` components auto-upgrade to due → rerun scoped → baseline ReviewRun produced; screening snapshot untouched and viewable side-by-side; a retrospective review of screening is possible only as an explicit new ReviewRun named as such.

**J7 — Report export:** "What do I hand to whom?" → Subject report (full profile + every rule + evidence + actions), center/project report (issues/actions only, per frozen semantics), HTML primary / Markdown working-copy; every report header states protocol version, RuleModelRevision, episode, snapshot id, generation time. No internal logs or imperative model wording.

**J8 — Recovery:** "I closed the laptop mid-batch / the app died." → Reopen → job banner: "2 jobs running, 1 awaiting review" → click reattaches to live progress (SSE subscribes; browser never owns lifecycle) → after crash, restart resumes from last checkpoint; anything unrecoverable appears as a named failed item with retry, never a silent hole.

## 5. Page And Interaction Architecture

### 5.1 Global shell and navigation

App shell: top bar (product identity, global search `/`, job indicator with live count, help) + left nav rail: **今日工作 · 项目 · 方案工作台 · 行动中心 · 报告 · 任务与系统 · 帮助**. Project context enters via a breadcrumb (项目 ▸ 受试者 ▸ 节点）, never via nested mystery tabs. No login surfaces anywhere.

### 5.2 Page inventory and first-screen hierarchy

| # | Page | First screen (above the fold) | Primary job |
|---|---|---|---|
| P1 | 今日工作 (home) | Jobs running/awaiting review; actions due this stage grouped by owner; unresolved conflicts; recent changes | Triage in <30s |
| P2 | Project dashboard | Subject table: rows = subjects, columns = episodes; cell = primary status + category counts (D4 rollup); per-column filter/sort; urgency sort = blocking now → latest due stage → gap type | Find who needs what |
| P3 | Subject workbench | Compact header (demographics, disease status, episode selector, anchors, snapshot, action count) + tabs: Patient Profile / 入排工作台 / 证据与文件 / 历史与快照 | One-subject deep work |
| P4 | Patient Profile (tab of P3) | Risk-filtered swim lanes + coverage lane (D3); density toggle 风险优先/完整明细 | Longitudinal truth |
| P5 | 入排工作台 (tab of P3) | 3-pane: rule tree / component detail / evidence viewer, synchronized selection | Decide & route every component |
| P6 | Protocol workbench | Metadata card; 3 columns original/tree-diff/gate report; publish bar with gate status | Publish a trustworthy RuleSet |
| P7 | Action Center | Buckets by due_stage; columns owner/requested action/acceptable evidence/blocking; bulk export per party | Close loops |
| P8 | Upload & Jobs | Upload wizard (mode + preview); job cards with per-item ledger, retry/cancel; cost/time estimates | Move evidence safely |
| P9 | Reports | Scope selector (subject/center/project), format, provenance header preview | Hand off |
| P10 | History & snapshots | Snapshot list per subject; ReviewRun list with diff links; action transition log; correction history | Audit & retrospective review |
| P11 | Help & recovery | Task-oriented help; "service restarted" explainer; storage/backup status | Self-service recovery |

Drawers/modals (shared, right-side, 40–48rem desktop, full-screen narrow): evidence drawer (span-level), correction drawer, conflict comparison, override-with-reason modal, referenced-missing-document panel, job detail. All modals trap focus, `Esc` closes, close-with-unsaved-input warns.

### 5.3 P5 workbench — the load-bearing layout

Desktop ≥1280px: CSS Grid `grid-template-columns: minmax(16rem, 22cqw) minmax(24rem, 1fr) minmax(26rem, 42cqw)` inside a `container-type: inline-size` wrapper; gutters draggable; each pane collapsible to a rail. **Panel priority under shrink: rule tree > component detail > evidence viewer** — at <1100px the evidence viewer detaches into an overlay drawer anchored to the selected span (selection state persists); at <820px all three become a tab stack *sharing one selection model* (rule/fact/evidence selection survives tab switches; no full-page horizontal scroll ever). This directly preserves the baseline's narrow-screen decision while making the priority explicit.

Evidence viewer: PDF page image + text layer. Highlight = bbox rect when available, else text-range match highlight, else page badge "仅页级定位". Locator precision is a rendered property (D2). 识别文本/原文 toggle; zoom independent of app zoom; page thumbnails for multi-page docs.

### 5.4 Interaction details

- **Linked selection:** one selection store; clicking a rule selects its facts and scrolls evidence to the primary span; clicking a profile event selects its rule components; hovering a span chip flashes the page region. Comparator's 3-column linked layout validates this pattern; we add explicit *selection state* and precision badges it lacks.
- **Search/filter/sort:** global `/` searches subjects, rules, actions, documents. Tables use TanStack-style per-column filters + multi-sort; saved views per user (single user: saved globally). Dashboard filter chips mirror D4 categories.
- **Keyboard:** `j/k` row navigation; `←/→` collapse/expand tree; `Enter` open; `e` jump to evidence; `c` open correction; `a` open action; `g h/g p/g a` go home/project/actions; `?` shortcut help. All actionable elements focusable, visible focus ring, skip-link to main.
- **Mouse:** click select, double-click open source, `Shift/Ctrl` multi-select for batch ops, drag gutters, right-click context menu only duplicates visible buttons (never sole access).
- **History/recovery entries:** job banner (global), per-subject 历史与快照 tab, action transition log from any action chip, correction history from any corrected fact, "review this run's diff" from any ReviewRun, restore-point list in 任务与系统.
- **Empty/loading/error:** every pane has designed empty states with next action ("尚无筛选期资料 → 上传"); skeletons match final layout to avoid reflow; errors name the failed item and retry path; long-running states show step, ETA, cost-so-far, and cancel.

### 5.5 Responsive and DPI independence

- Layout tokens in `rem`; spacing scale 4/8/12/16/24; type scale with `clamp()` for page titles only, body text fixed 0.875–1rem for clinical density; **no fixed-pixel layout containers** (modals/drawers use `min(90vw, 32rem)` patterns). Current app's fixed `width:500px` modal and `480px` overlay are the anti-pattern to avoid.
- Verified at 100%/125%/150%/200% display zoom and 1280×800, 1440×900, 1920×1080 logical resolutions; 200% zoom must not produce horizontal page scroll or clipped pane content (container queries degrade panes first, text never).
- Density is clinical: table row 2.25rem, 14px base; a 紧凑/舒适 density toggle changes padding tokens only, never font below 13px for data.
- Print/report CSS: subject report prints clean (no nav/panes), spans keep page references in text form.

### 5.6 What the comparator proves and what we refuse

Adopt: fixed left workflow nav; summary-beside-original co-location; rule → recognized-text → original-page three-pane linkage; explicit `未明确提供` absence markers; per-cohort (= per-episode for us) judgment sections; clear batch controls. Refuse: static summary bullets without per-item span links (unverifiable); 批量设为 manual verdict setting without an immutable transition log; cohort-tab model (our episodes are stateful, not tabs); three always-on panes at small widths (the baseline's own discovery already rejects this); action buttons （转发他人/完成审核） implying workflow ownership we deliberately don't have.

## 6. Patient Profile And Provenance Experience

### 6.1 Content model — additions to the baseline

Keep baseline entities; add/refine:

1. **`EvidenceExpectation`** (D3): `{rule_component_id, episode_id, expected_kind (procedure/lab/history_inquiry/document/anchor), required_source_tier, due_stage}` — generated deterministically at RuleSet publish and episode open.
2. **`SourceTier`** on every fact/span: `原始检查报告 / 处方或给药记录 / 同期既往病历 / 筛选病历转述 / 患者自述 / 研究者判断 / 邮件沟通`. Tier drives both evidence-strength chips and conflict rendering; hierarchy per frozen decision 9 (denial = evidence; silence = incompleteness; screening-narrative positive history = usable + non-blocking provenance action unless objective proof required or conflict).
3. **Temporal model:** `event_time` (with precision: day/month/year/relative/unknown + computed bounds) vs `record_time` vs `evidence_freshness` — three separate rendered fields, never conflated; washout/duration thresholds render the *computable interval* and flag when bounds cross the threshold.
4. **`ConflictGroup`** UI contract: side-by-side cards (source tier, date, excerpt, page link), a `blocks_component` flag, and exactly one resolution path: an owned action with a verification-evidence requirement. No auto-winner, no "prior source preferred" logic anywhere (the current reviewer prompt's `优先采信既往源文件` is explicitly retired — verified contradiction in `app/pipeline/reviewer.py` system prompt).
5. **Trend & abnormality projection:** serial labs/scores per analyte; first screen shows eligibility-relevant, abnormal, borderline (within configurable % of threshold), and trend-changing values; all normal values retrievable in 完整明细. Borderline band width is a RuleModelRevision parameter, not hardcoded.

### 6.2 Visual grammar

- **Lanes** (baseline's 13 themes kept, ordered by eligibility salience, collapsible): each event row = time chip (precision-aware: `2024-05` or `≥3年前`) + name + status icons (negation ⊘, uncertain ?, conflict ⚡, OCR risk ◆, weak-source ◌) + source-tier chip + eligibility-link badges (`EX-07b` etc.). Icon count per row ≤4; everything else in the drawer.
- **Coverage lane** (D3): expectation rows rendered as dashed-outline chips: `应做·未上传 肺功能报告` — absence as a first-class visual object.
- **Event drawer:** sections 事实 / 时间（事件·记录·精度） / 关联规则组件 / 证据（span list with precision badge) / 校对记录 / 冲突. Provenance footer always visible: file, page, locator precision, original excerpt.
- **First screen (frozen decision 13):** default 风险优先 filter = eligibility-linked + abnormal + borderline + trending + conflicts + open expectations; counts per lane always visible so hidden normals are discoverable, not forgotten.
- **Provenance reminders** (design §5.4): rendered as countable chips on the relevant fact/rule/dashboard (`溯源待办 2`), opening to a filtered Action Center view — never as fine print next to a green pass. Non-blocking, closeable by evidence or explicit acknowledgment-with-reason; aging (>N days unaddressed at due stage) escalates chip color, deterministically.

### 6.3 Provenance interaction path (the trust loop)

From any summary chip, rule judgment, or action: 1 click → evidence drawer (excerpt + precision badge); 1 more click → full-page viewer at the highlighted location. Correction flow: `c` → drawer shows original OCR (immutable) + corrected text + reason; polarity/numeric changes need an explicit typed confirmation and list the affected facts/rules *before* commit; commit → scoped rerun → ReviewRun diff shows what changed. Conflicting sources: both spans linked from the same conflict card. Missing referenced documents: `referenced_file_missing` expectations render with the citing span ("病历 p4 提及'见外院CT报告'") and an upload drop-zone that auto-links the uploaded file to that expectation. Provenance reminders: 加强溯源 chips deduplicate per rule component (one open reminder per component, updated by new evidence) to prevent alert fatigue.

## 7. Rule, Evidence And Action Workbench

### 7.1 Rule tree

- Sections 入选/排除； official numbering immutable; parent rows aggregate children deterministically (ALL/ANY/NOT badge visible on parent, e.g. `EX-20 · 全部满足才触发`); group/情形组 nodes supported.
- Per-node chip: component state (7-state vocabulary per design §5.1) + open-action count + conflict bolt. Tree filters: 全部 / 阻断 / 未明确 / 冲突 / 需专业判断 / 后续节点 / 已通过（含溯源待办）. Progress bar per episode: `56 组件 · 明确 49 · 待闭环 7`.
- **Screening/baseline coexistence:** episode segmented control above the tree （预筛/筛选/导入/基线）, each bound to its snapshot + ReviewRun; a 对比 mode renders two columns (component states at episode A vs B) with changed rows highlighted — this is also the retrospective-review and escalation surface (D9). History snapshots are read-only and labeled; current snapshot is the only writable view.

### 7.2 Component detail (anti-drowning rules)

Card layout, top to bottom: (1) **Judgment strip**: state badge + one-sentence rationale (≤2 lines) + gate trail ("阈值 1.5×ULN · ALT 42 ULN=40 → 未达阈值" — deterministic render, not LLM prose); (2) **Facts used**: chips with tier/precision, click → evidence; (3) **Gap card** (only when not clear): typed gap, why, and the machine-checkable closing predicate in plain language; (4) **Action card**: owner (4 classes only), requested action, acceptable evidence, due stage, blocking level (computed chip), state + history link; (5) expandable **原文引用** (quotes capped at 2 lines each, "在证据面板打开" for full context). Professional-judgment components show the exact judgment sentence that would close them ("需要研究者针对本条款写明：参与研究不构成不可接受风险（注明日期、签名）"). No component ever shows more than ~1.5 screens at default expansion.

### 7.3 State and action semantics (unchanged from frozen decisions, made operational)

Judgment–gap consistency matrix (design §5.2) enforced at the Gate; UI renders violations as gate-rejected drafts, never as published states. Auto-close only via gap-specific predicates in a new ReviewRun; override/reopen with reason; supersede on snapshot/episode replacement. Blocking level computed deterministically from rule type × episode × gap matrix — LLMs never fill it. Conflict components show ⛔ blocked-until-verified state; no path to "clear" exists without a resolution action.

## 8. Independent Agent And Workflow Architecture

Principle (endorsed from baseline, extended): **semantic reasoning is rented, never trusted.** Agents are stateless typed functions over narrow context slices; all state, counting, logic, dates, thresholds, rollups, transitions, and exports are deterministic. Orchestration = explicit job state machine with checkpoints (no LangGraph day one — endorsed; the interface seam stays).

### 8.1 Node contracts

| Node | Type | Trigger | Input (context slice) | Output (typed) | Deterministic gate | Write authority | Failure path | Stop condition |
|---|---|---|---|---|---|---|---|---|
| N1 Document fingerprint/classify | Deterministic (+ light heuristic) | Upload commit | File bytes, hash, name hints | `SourceDocumentVersion`, dedup verdict, doc-type candidates | Hash re-verify; page-count check | Storage only | Item marked failed; job continues | All files classified or item-failed |
| N2 OCR page node | Deterministic adapter (VLM call) | N1 per file | Page image, OCR model/param version | `OCRPage` text + method + (spike: layout/LOC) | Cache key = content hash+page+model version; page completeness | OCR store (immutable) | Page retry ×3 → item failed with affected scope | All pages cached or failed |
| N3 OCR QC gate | Deterministic | N2 | OCR text | Quality flags: polarity/numeric/date risk, repetition (existing `detect_ocr_hallucination` hardened into *flags*, never silent text mutation) | Risk thresholds per doc class | QC flags only | `ocr_or_parse_risk` expectation + correction task | All pages flagged/passed |
| N4 **Evidence Normalizer** (Agent) | Semantic, bounded | N3 per document | ONE document's pages + doc-type + protocol-neutral schema | Candidate `ClinicalFact/Event/MedicationExposure/ReferencedDocument` with span refs (JSON Schema) | Schema validation; span resolution (every span must resolve via D2 ladder); negation/polarity check; dedup vs existing facts | Proposals only — never direct business truth | Schema/gate reject → 1 retry with error feedback → item failed, document marked `facts_stale` | Document exhausted; zero unresolved spans |
| N5 Fact gate & conflict detector | Deterministic | N4 | Candidate facts + existing fact DB | Accepted facts, `ConflictGroup`s, source-tier assignment | Unit/date/partial-date logic; conflict predicates | Fact DB | Reject candidates with reasons surfaced to user | All candidates adjudicated |
| N6 Coverage projector | Deterministic | RuleSet publish; episode open; N5 | RuleComponents × episode × facts | `EvidenceExpectation` states, coverage matrix | Expectation-state predicates | Projection | Recompute on demand | Projection complete |
| N7 **Eligibility Assessor** (Agent) | Semantic, bounded | Episode review run | ONE RuleComponent + retrieved fact slice + component text + relevant expectations | Typed assessment: state, gap_type, rationale, cited span ids (JSON Schema) | Consistency matrix (state↔gap); logic/threshold/window recomputed independently; every cited span must exist and resolve | Proposals only | Gate reject → 1 retry → component marked `需人工处理` with reason | Every due component assessed or failed |
| N8 Assessment gate & rollup | Deterministic | N7 | Assessments + RuleSet | Component states, stage rollup (D4), ReviewRun record | Rollup function table; stage isolation | Business state | Rollup test failure halts publish of run | Run committed |
| N9 **Safety/Provenance Critic** (Agent, conditional) | Semantic, veto-only | Trigger set only: high-risk rule classes, conflicts, OCR polarity/numeric risk, gate anomalies | Contested component + cited spans + assessment (NOT the whole evidence) | `uphold / veto / downgrade-certainty / open-action` + reason | Critic may not rewrite assessments; output schema enforced | Vetoes/actions only | Critic error → assessment stands with `critic_unavailable` badge, queued for retry; false-veto rate tracked in evals | One verdict per trigger |
| N10 Action synthesizer | Deterministic | N8/N9 | Gaps + matrix + owners | `ActionRequest` + transitions (open/close/reopen/supersede) with idempotency keys | Closing predicates; owner enum; blocking computation | Action store + transition log | Predicate error blocks transition, logged | All gaps have actions |
| N11 **Protocol Deconstructor** (Agent) | Semantic, bounded | Protocol upload/re-deconstruct | Protocol document (+ prior draft + user feedback) | RuleSet draft: rules, components (ALL/ANY/NOT, thresholds, units, windows, exceptions, evidence reqs), workflow stages | Parent counts/official numbering 100% match; phase consistency; schedule coverage; version binding | Draft only — publish is human | Gate fail → annotated failures back to workbench; never auto-publish | User publishes or discards |
| N12 Report/exporter | Deterministic | User request | Committed state + snapshot | HTML/MD with provenance header | No internal logs/imperatives; version binding check | Export artifacts | Regeneration on demand | Artifact written |

### 8.2 Cross-cutting contracts

- **Memory isolation:** agents see only their node's typed input; no shared scratchpad; no agent-to-agent messaging. The Critic's independence requires it never sees N7's prompt or full evidence — only the contested artifact.
- **Gating:** every agent output passes a deterministic gate before touching business state; rejects are data (shown to user with reasons), never regex-repaired into compliance (the current reviewer.py's ~50 post-hoc guards become gate predicates on *structured* output, which is why they get simpler, not bigger).
- **Deterministic-only list (baseline §7.3 endorsed, add):** rollup function (D4), expectation states (D3), blocking levels, dedup/snapshot/stage isolation, transition log, cost ledger.
- **Failure surfacing taxonomy:** each node failure maps to a UI surface — item badge (file/page), component chip (`需人工处理`), job banner, affected-scope chip (`stale` facts/rules), system page. Nothing fails silently; nothing blocks unrelated work.
- **Cost/time:** every AgentCall logged (node, model, prompt version, tokens, latency, cost); per-run and per-batch estimates from rolling medians shown pre-run ("≈8 min · ≈¥3.2 · 3 subjects"); budget guardrails configurable per node; DeepSeek V4 Flash baseline pinned per node with eval-recorded accuracy, swappable per node (not hardcoded).

## 9. Testing And QC LOOP

| Layer | Scope | Representative scenarios | Metrics & thresholds (proposed defaults; Codex/user calibrate in Phase 8) | Iteration mechanics |
|---|---|---|---|---|
| L0 Contract | Fixture schema = API schema | Phase 1 fixtures validate against Phase 2 OpenAPI; breaking change = version bump | 100% fixture/contract conformance in CI | Contract-first PR review; incompatible change fails build |
| L1 Deterministic unit | Gates, rollup, dates, units, logic, transitions | AND/OR/NOT; partial-date bounds crossing threshold; washout; rollup precedence; auto-close predicates; idempotency | 100% pass; mutation testing on gates (≥80% mutants killed) | Every bug → unit test first |
| L2 Component eval (model) | Per-agent golden datasets from legacy error fixtures | GGT≠ALT substitution; syphilis exception; silence-vs-denial; pass_verify semantics; FEV1 vagueness; cross-rule contamination | Normalizer: fact P/R ≥0.95/0.90 per type; Assessor: component-state agreement with adjudicated gold ≥0.90, zero invented spans; Critic: veto precision ≥0.85, false-veto ≤10%; polarity/numeric errors = 0 on seeded set | Eval suite runs on any model/prompt change; regression blocks merge; per-node dashboards |
| L3 Clinical regression | Legacy error classes as fixtures (read-only anchors) | All D001/MG-K10-SAR-III known error categories | 0 recurrence of known error classes | Failure triaged to layer (rule/fact/span/agent/gate), fixed generically — no subject-specific patches |
| L4 OCR quality | Per document class (native/scan/handwriting/photo) | Hallucination repetition; polarity flips; decimal/unit/date errors; locator anchor resolution rate | Polarity/numeric corruption = 0 on golden pages; anchor resolution ≥95% at text_range or better, else visible degradation | OCR adapter changes require L4 rerun |
| L5 Job/recovery fault injection | Orchestrator | kill -9 at each named step; browser close mid-batch; duplicate submit; SSE reconnect; OCR partial failure; DB restore | No permanent `processing`; no duplicate jobs/docs/actions; resume from last checkpoint; partial failure surfaces affected scope | Checklist per job kind; chaos drill per release |
| L6 API integration | FastAPI TestClient | Upload→preview→commit→run→close loop; override/reopen; conflict block; interpretation warning | All pass; audit log complete per mutation | Existing 131 tests ported/split into layers |
| L7 E2E (Playwright) | Critical paths at 3 viewports (1280/1440/1920) × 100%/150%/200% zoom | J1–J8 journeys; 3-pane sync selection; narrow-tab stack persistence; keyboard-only rule review | All pass; no horizontal page scroll; no clipped content at 200% zoom | Per PR on UI changes |
| L8 Visual regression | Screenshot baselines per page/state | Dashboard, profile lanes, workbench panes, conflict card, job page, empty/loading/error | Pixel-diff within threshold; human review on intended changes | Baseline update requires design sign-off |
| L9 Accessibility | axe-core + manual keyboard/screen-reader pass | Focus trap in modals; tree grid roles; color-independent state encoding (icons + text, never color-only) | 0 critical axe violations; all flows keyboard-completable | Per release |
| L10 Performance | Local bench | Dashboard with 100 subjects × 56 rules; profile with 500 facts; PDF viewer first paint | Dashboard interactive <2s; profile <2s; evidence open <1s; batch estimate accuracy within ±30% | Budget regression blocks release |
| L11 Prototype UAT | Phase 1 gate (D1) | 10–14 scripted tasks incl. locate-evidence ≤3 clicks, close action by upload, find owner-due actions, correct OCR polarity | Completion ≥90% unassisted; 0 wrong-conclusion errors; SUS-style score recorded; task-time baselines set | Approval = measured UAT sign-off; failures → IA revision loop before Phase 2 |
| L12 Full-flow UAT | Phase 8 clinical validation | New projects from original protocols; representative screen-fail/success cases; blind human comparison | Every explicit barrier, key gap, and judgment human-verified; profile vs source spot-check pass; time/cost/recovery records complete | Codex clinical acceptance; user sign-off |

Loop discipline: L2–L4 evals are the *steering* loop during Phases 4–6; L5–L10 are the *release* loop; L11–L12 are the *acceptance* loop. Every clinical deviation found in UAT is attributed to a layer and fixed at the most general level; the fix must cite the invariant it restores.

## 10. Revised Implementation Plan

Sequencing principle: **prove the product workflow with a contract-first prototype before any expensive backend commitment** — strengthened so the prototype is the product shell and the approval is measured.

| Phase | Work | Depends on | Prototype/artifacts | Rollback | Exit gate |
|---|---|---|---|---|---|
| **0 Freeze & isolate** | Baseline freeze; legacy write-protection tests; V2 directory spine; dependency/license pin | — | Frozen decision list; protection tests | Delete V2 dirs | Legacy unwritable; 131 tests green |
| **0.5 Contract-first** | `fixture/v1` JSON schema (subject, profile, rule tree, actions, spans with locator ladder, jobs); OpenAPI draft; job/SSE event contract; rollup function spec + unit tests (D4) | 0 | Versioned contract repo artifacts; stub API (mock service worker) | Contract version rollback | Schema validates 3 example subjects; rollup table tests pass |
| **1 Prototype = real shell** | React+TS+Vite shell; all P1–P11 pages against stub API; 3-pane workbench with selection sync; evidence viewer with locator-ladder rendering; 10+ key scenarios incl. all gap types, conflicts, correction, escalation, auto-close, override | 0.5 | Clickable product at 3 viewports × 3 zooms; keyboard map implemented | Branch revert | L7/L9 smoke pass; no fixed-px layout; narrow behavior per §5.5 |
| **1.5 Measured UAT (hard gate)** | Scripted UAT per L11 with the user; IA/term/density iteration loop | 1 | UAT report with metrics; approved IA revision log | Iterate within Phase 1 | L11 thresholds met; explicit user approval recorded — *no backend work before this* |
| **2 Domain + jobs** | SQLAlchemy/Alembic; core tables; WAL; optimistic concurrency (D7); Job/Checkpoint/lease/cancel; SSE subscribe; idempotency; cost ledger | 1.5 | Stub API swapped for real per contract; contract tests in CI | DB backup/restore; migration rollback | L5 fault-injection checklist passes; L0 conformance 100% |
| **3 Protocol workbench** | N11 + N12 gates; metadata header sanitization; phase-boundary decision UI; interpretation sources + conflict warnings; publish flow | 2 | MG-K10-SAR III + D001 rebuilt from original protocols | Discard draft | Parent numbering 100%; phase ≠ episode confusion impossible; RuleSet bound to Vx.x |
| **4 Ingestion & OCR** | N1–N3; content-hash dedup; snapshots; upload previews; **locator spike (D2): oMLX layout/LOC probe, PyMuPDF word boxes, sidecar PaddleOCR option**; correction with polarity confirmation + scoped rerun | 2 | Per-file job ledger UI; precision badges live | Per-adapter rollback; old cache invalidated by key | L4 thresholds; dedup/snapshot semantics; anchor resolution ≥95% or degraded badge shown |
| **5 Facts & profile** | N4–N6; fact DB; coverage lane; trend projection; profile view live on real data | 4 | Profile on representative subjects | Re-projection from facts | L2 normalizer thresholds; silence never becomes denial; conflicts side-by-side; expectations rendered |
| **6 Assessment & actions** | N7–N10; Critic triggers; rollup; escalation on episode open; ReviewRun diff view (D9) | 5 | Workbench live end-to-end | Run-level rollback (runs immutable) | L2 assessor thresholds; consistency matrix enforced; auto-close predicate tests; Critic cannot rewrite |
| **7 Batch, closure, reports** | Batch jobs with estimates; auto-close/override/reopen UI; per-party action export; subject/center/project HTML+MD; help/recovery pages | 6 | Full J2–J8 on real jobs | Feature flags per capability | L7 full journeys; reports carry provenance header; browser-close survival |
| **8 Clinical validation** | Fresh V2 projects; high-risk cases first; blind human comparison; deviation→layer→generic fix | 7 | Validation report; calibrated thresholds | Legacy read-only fallback remains | L12 + L3 zero recurrence; user acceptance |
| **9 Cutover & cleanup** | V2 default; legacy sealed read-only; delete auth/ownership/dead paths with precise manifest; ops/backup docs | 8 | Final regression + visual QC | Re-point entry to legacy (still sealed) | Double-click→workbench; restart recovery; final UAT sign-off |

Observability built from Phase 2: structured job events, cost ledger per node, eval dashboards. Every phase keeps legacy untouched and runnable.

## 11. Prioritized Decisions

**Must change (block approval until in plan):**

1. Phase 1 → contract-first prototype on the real shell + scripted measured UAT as the only approval mechanism (D1).
2. Evidence-locator ladder contract + Phase 4 layout-capture spike; locator precision rendered everywhere (D2).
3. `EvidenceExpectation` + coverage lane so absence is visible (D3).
4. Rollup function spec + tests as a Phase 0.5 deliverable (D4).
5. Model/clinical eval harness with numeric thresholds wired into the LOOP (D6).
6. Optimistic concurrency on all human-editable records (D7).

**Should change (strongly recommended, not blocking):**

7. Home = work queue; Action Center fully specified with per-party export (D5).
8. ReviewRun diff as first-class page powering escalation, closure review, and retrospective review (D9).
9. Job UX: per-item ledger, affected-scope staleness, granular retry, pre-run time/cost estimates (D8).
10. Design tokens/density/keyboard map/PDF-viewer component (pdf.js text layer + highlight overlay) decided in Phase 0.5 (D10).
11. Comparator adoptions: explicit absence markers, per-episode judgment sections; refusals per §5.6.

**Defer (explicitly later, with trigger):**

12. LangGraph — only on demonstrated state-machine maintenance pain (baseline's own trigger; endorsed).
13. Touch-native card layout for phone widths — narrow support is drawer/tab degradation; true mobile is out of the single-Mac scope.
14. Multi-model comparison runs — eval harness supports it; routine use waits for cost data.
15. bbox capture via sidecar PaddleOCR pipeline — only if oMLX layout probe fails *and* text_range resolution <95% in L4.

**Reject (do not do):**

16. Throwaway prototype medium (separate HTML demo) — wastes the approval signal and duplicates work.
17. Any auto-preference among conflicting sources, any LLM-authored blocking/transition/logic/thresholds, any regex-repair of invalid agent output — baseline already rejects; reaffirmed with current-code evidence.
18. Migrating legacy verdicts/reports into V2 truth; free-running agent swarms; always-on Critic; login/ownership revival.
19. Fake precision: rendering bbox-style highlights without backend-supplied or verified anchors.

## 12. Evidence, Inference, Uncertainty And Questions For Codex

**Direct evidence (observed in packet/code/screens):** login gate and localStorage tokens with credentials in SSE query params; single `overall_verdict` in `models.py`; mtime OCR cache (`ocr.py:99-101`); browser-owned batch loop and `cancelProcessing` closing only the EventSource; `request.is_disconnected()` canceling mid-review (so closing the browser *does* kill work); in-process-only locks; reviewer prompt's prior-source preference contradicting the conflict rule; ~50 regex guards keyed to rule-ID/name patterns; `call_vision_ocr` returning plain text with LOC tokens stripped; rule management as one Markdown textarea; dashboard as single-verdict counts (97 subjects: 3/3/5/24/62); comparator's absence markers and 3-pane linkage; PaddleOCR-VL pipeline-level bbox JSON availability per official docs.

**Inference (marked):** [INFERENCE] oMLX's PaddleOCR-VL-1.6 chat serving likely cannot return layout boxes — unverified, hence the spike. [INFERENCE] The stripped `<|LOC_123|>` tokens suggest 1.5-era coordinate emission that *might* be recoverable — flagged as probe item, not counted on. [INFERENCE] Monitor-first IA prioritization is based on the comparator's task-queue structure and general clinical-monitor workflow, not on interviews with the actual user.

**Uncertainty:** (a) Real subject/document volumes per batch (drives L10 budgets). (b) Whether the user reviews on one display or moves windows (drives pane-priority defaults). (c) DeepSeek V4 Flash vs V4 Pro accuracy/cost delta on *our* golden set — unknown until L2 exists; the design's model baseline is a placeholder until measured. (d) Handwriting/photo document share (drives L4 class weights). (e) Whether per-party action export needs a formal "query letter" format or a working list.

**Questions for Codex:**

1. Approve the Phase 0.5/1/1.5 restructure (contract-first + measured UAT hard gate) as a plan amendment?
2. Locator ladder: accept `text_range`-with-confidence as the baseline precision and bbox as spike-dependent upgrade, with visible degradation badges — or is page-level-plus-excerpt unacceptable for your clinical QC?
3. Rollup precedence (D4): confirm the exact ordering including `provenance_followup` rendering as `未发现明确障碍（溯源待办 n）` — I propose it counts toward neither "障碍" nor "缺口" but renders as its own chip; confirm.
4. Work-queue-as-home: does the user want the first screen to be the queue (my recommendation) or the project dashboard (baseline)? This is a taste call only the user can settle — recommend putting both variants in the Phase 1 UAT as an A/B task.
5. Eval thresholds in §9 are proposed defaults — who owns calibration authority at Phase 8 (Codex with user sign-off?), and what agreement level on the adjudicated gold set is acceptable for go-live (I proposed ≥0.90 component-state agreement, zero invented spans)?
6. Critic trigger set: baseline says high-risk rules/conflicts/OCR-risk/gate-anomalies. Should "any `closed_system` transition on a polarity-corrected fact" also force a Critic pass? Cheap and closes the correction-abuse path.

**Statement on the other route:** none — no cross-participant visibility per boundaries.

**Bottom line:** The baseline's clinical-truth architecture is sound and should survive this conference mostly intact. What must change is the delivery of the *working surface*: a measured, contract-first prototype that becomes the shell; a provenance locator design honest about what the OCR stack can actually see; a coverage model that renders absence; a specified rollup; and an eval harness that makes "clinically better" a number instead of a hope. With those amendments, the Phase 0–9 sequence earns its gate discipline; without them, Phase 1 approves a feeling and Phase 4 promises pixels the adapter can't deliver.
