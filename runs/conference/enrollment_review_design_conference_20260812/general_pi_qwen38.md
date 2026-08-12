Evidence base is sufficient. I verified the current reviewer guards, the test regression set, the three-round user decisions, and the proposed contract. Writing the independent work product now.

---

# Conference Participant Output: enrollment_review_design_conference_20260812 - general_pi_qwen38

Role: `general_pi_qwen38` (effective route `pi/opencode-go/deepseek-v4-flash`, effort max). Independent clinical-workflow and evidence-semantics critic. No other participant outputs read.

## Boundary Check

- Read-only advisory pass; no source/app files modified; no raw clinical material read outside the workspace read set.
- Read: `AGENTS.md`; `context/enrollment_review_design_conference_20260812_conference_context.md`; `plans/codex_main_venue_...md`; `docs/REARCHITECTURE_DISCOVERY_20260812.md` (incl. §§5-17); `app/pipeline/reviewer.py` (prompt, guards, phase timing, verdict recalc); `app/models.py`; `app/markdown_export.py` (labels/ISSUE_VERDICTS); `tests/test_phase_workflow.py` (test inventory + representative bodies); `docs/PROJECT_CONTEXT.md` (top milestone).
- No final acceptance performed; Codex remains final authority. No claim made about any other agent's system prompt.

## Independent Work Product

### 0. Headline finding

**The two-axis model (判断状态 × 缺口原因) is the right spine, but as proposed it has one structural hole: the axes are not orthogonal, there is no stated consistency invariant between them, and two user-confirmed decisions (不自动选边; auto-close) are mutually dangerous unless auto-close is gated by gap type and by the specific component.** The single most likely residual false-certainty path in the current system is **`pass_verify` = "通过（需验证）" rendered and counted as a pass** (`app/markdown_export.py:22,31` — `ISSUE_VERDICTS` excludes `pass_verify`), i.e. a 溯源提醒 that is invisible on project dashboards. The new model must make provenance reminders **open ActionRequests with dashboard counts**, or the "enhanced provenance reminder" improves per-rule honesty while the project view still reads as final.

### 1. Failure-class audit: does the proposed model prevent false certainty?

| # | Case | Proposed design outcome | Verdict & gap | Required remediation |
|---|---|---|---|---|
| C1 | Explicit denial vs silence/omission in screening note | Denial = ClinicalFact(negation=true) with exact excerpt; silence = gap `病历记录不完整` (决策 16.1, 14.3) | Sound in taxonomy. **Gap: neither axis carries the fact-level determinacy.** An Evidence Normalizer LLM can fabricate a "否认" from silence or from an unreadable OCR region, and nothing in the two axes catches it. | Negation facts MUST carry the source excerpt + span confidence; if the polarity-bearing sentence has low OCR confidence or the region is missing, fact determinacy downgrades and the rule conclusion is blocked to `暂不能明确/需人工校对` regardless of LLM text. Polarity flips during single-user 校对 require explicit user confirmation (clinical-data change, not OCR repair) — this is the `需专业判断`-adjacent boundary the design lacks. |
| C2 | Positive historical duration only in later screening narrative | `溯源提醒` (决策 16.1); current system already emits `pass_verify`/病史来源需溯源验证 (`reviewer.py:1189-1219` tests) | Design prevents *rule-level* false certainty but **reintroduces it at dashboard level**: `pass_verify` is excluded from `ISSUE_VERDICTS` (`markdown_export.py:31`) and labeled 通过（需验证）(`:22`). A reminder nobody counts is a silent pass. | Provenance strength is a **display and routing dimension, not a verdict**: `证据强度: 转述-待溯源 | 同期源文件`. The reminder must be an open ActionRequest (`CRC 获取既往源文件`, due=归档/下一节点, blocking=低), counted as `溯源待办 N` on the dashboard, never aggregated into `未发现明确障碍` or plain 通过 counts. |
| C3 | Referenced doc not uploaded vs procedure never performed | Gap taxonomy separates `已知原始资料未上传` vs `必做检查/评分未完成` (14.2) | Taxonomy correct; **no mechanism implements it.** Grep of `reviewer.py` for 见…报告/未上传/reference patterns: zero hits; no test exists. Today an LLM seeing "见外院化验单" with no attachment can (a) cite the note as if it contained the result, or (b) misclassify as 病历记录不完整. | Make `ReferencedDocument` (引用但缺失的文件) a first-class Evidence Normalizer output. Deterministic pre-gate: any rule component whose evidence depends on a referenced-but-missing doc → conclusion `暂不能明确`, gap `已引用文件缺失`, action `CRC 补充上传明确文件`. A reference is never evidence. Acceptance case A3. |
| C4 | Objective fact present, investigator judgment absent | `需专业判断` state; current guards handle EX-20h/EX-11/compound rules well (`reviewer.py:1296-1341,1621-1666` tests) | Sound — this is the cleanest case for the model. **Gap: no auto-close rule for judgment-type gaps.** A judgment can't be machine-verified; if auto-close fires on "new upload", an unrelated file could close it. | Auto-close policy (see §4): judgment gaps close ONLY when a new, dated, attributed, source-linked judgment record exists in a new ReviewRun. Never from a bare upload. `source_and_rule` must point at the judgment text itself. |
| C5 | Partial dates and washout windows | 12.2: dates allow 明确日/年月/年份/相对/未知, compute bounds, risk when bounds change conclusions | Design intent correct; **interval arithmetic is unowned.** Current guards only prevent anchor substitution (`apply_missing_phase_anchor_date_adjustments`, `reviewer.py:1705` area; tests 824-863); they do no bound computation. | Deterministic rule: for duration/washout components, compute [min,max] from partial dates + episode anchor; both inside → 满足/不满足; **straddling the threshold → `暂不能明确` + gap `时间锚点/日期不足`, never auto-pass, never auto-fail**; bounds rendered. Gap type selection (询问型 vs 检查型 vs 文件型) must be driven by `RuleComponent.evidence_requirement`, not by LLM whim — this is what makes C3 and C1 routing deterministic. |
| C6 | Conflicting contemporaneous vs later narrative sources | 决策 16.x/round-2 #4: 并列展示、生成核实行动、不自动选边 | **Direct contradiction with shipped code**: `reviewer.py:120` system prompt instructs "冲突时优先采信既往源文件" (auto-pick). No deterministic conflict detection; no test for conflicts in `test_phase_workflow.py`. | Conflict is a first-class fact state (`ClinicalFact.conflict_group`): same component, ≥2 facts with differing values/negation, neither source-resolved → conclusion hard-blocked to `存在冲突/冲突待核实` (never 明确契合/明确障碍 on the contested component), action `研究者核实 + CRC/CRA 源数据一致性核查`. The prompt line must be removed/aligned. Bounded question Q1. |
| C7 | OCR negation/numeric errors | `text_requires_high_precision_review` + `detect_ocr_hallucination` exist (`app/pipeline/ocr.py`, tests 1771, 2903) | Partial today: prompt-level care + hallucination dedup, but no per-span confidence, no polarity-aware correction path, no re-run scoping. | OCR QC is a **deterministic gate node, not a prompt rule**: low-confidence negation/numeric spans → fact determinacy downgrade → affected rule conclusions to 校对 queue; correction stored as CorrectionRecord (before/after/reason) with affected-fact-and-rule recompute scope. 校对 must never silently flip polarity (see C1). |
| C8 | Current-stage evidence vs future baseline/randomization requirements | `后续节点关注` state + due_stage; phase timing guards exist (`reviewer.py:1719-1800`, tests 572-760) | Sound at single-episode level. **Gap: no escalation trigger.** `后续节点关注` items can accumulate and never re-run when the stage is reached — the "自动升级为必核项" (14.2) has no event. | ReviewEpisode open = deterministic re-evaluation trigger: all rules from the prior episode with state `后续节点关注` MUST re-run on the new episode's anchor date. Escalation is a state-machine transition with the anchor as evidence, not a label refresh. |

### 2. Highest-impact objections (prioritized) and remediations

**P0-1 — Orthogonality hole: the two axes overlap, and no consistency invariant exists.** `需专业判断` and `存在冲突` appear as 判断状态 but are simultaneously gap reasons (12.4 `需专业判断`; 14.2 `需专业判断`/`资料冲突`), and `暂不能明确` has no required gap. Without a validation matrix, an LLM can output 明确契合 with gap=无 on a contested component. **Fix:** define the invariant table as a deterministic validator:

| 判断状态 | required 事实充分性 | allowed 缺口原因 |
|---|---|---|
| 明确契合/明确障碍 | 充分（含确定性达标） | 无（可附溯源提醒，但溯源提醒≠缺口） |
| 暂不能明确 | 不充分 | 必须非空，∈ 12 类 |
| 需专业判断 | 客观事实充分、判断缺失 | 需专业判断 |
| 存在冲突 | 冲突事实 ≥2 未解决 | 资料冲突 |
| 后续节点关注 | 当前节点充分 | 后续节点尚未到期 |

Any row violation = gate failure, not a downgrade vote. This replaces the current regex verdict-reconciliation layer (`reviewer.py:880-884` etc.) with structured validation — the same knowledge, fewer text patches.

**P0-2 — Auto-close + override can silently re-import false certainty.** Decision 16.4 allows auto-close on 新增资料/校对/重跑. Unbounded, this closes gaps on *any* re-run and on *any* correction, including polarity flips (C1) and unrelated uploads. **Fix:** auto-close is a pure function of `(gap_type, missing_component state, new evidence set)`:
- Fires only when the **specific missing RuleComponent/ClinicalFact** transitions to a defined state in a **new ReviewRun** with an evidence-span pointer.
- **Disabled** for gap types `需专业判断`, `资料冲突`, `方案解释冲突` (semantic resolution only — machine can't verify judgment or truth).
- Corrections trigger auto-close only via the re-run they produce; polarity-flip corrections additionally require explicit user confirmation.
- Override = **reopen/reclassify**, never "approve" (§4). Idempotency test: identical re-upload must not flip state (dedup by content hash, already planned).

**P0-3 — "通过（需验证）" and 溯源提醒 visibility.** `pass_verify` labeled 通过（需验证）, excluded from `ISSUE_VERDICTS` (`markdown_export.py:22,31`). The new model keeps `溯源提醒` as a *decision* category (16.1) — if it remains a note rather than an action, dashboards (16.3: 主状态+数量) show zero issues while rules are green-reminder. **Fix:** `溯源提醒` renders as `当前证据：转述（待溯源）` per rule, is an open low-blocking ActionRequest, and is counted in dashboard numbers (`溯源待办 N`), sorted after 资料冲突 per the confirmed order.

**P1-1 — The current conflict prompt violates a confirmed user decision.** `reviewer.py:120` ("优先采信既往源文件") contradicts round-2 #4 (不自动选边). Auto-picking the *prior* source is clinically conservative for EX rules but wrong for IN rules and wrong per decision. See C6/Q1.

**P1-2 — Single `blocking_level` + `due_stage` ordering ambiguity.** 16.3 sorts by type (明确障碍 > 缺口 > 冲突 > 需判断 > 关注 > 无障碍). Type order fights the two axes: a non-blocking 溯源提醒 sits above a blocking 需专业判断. **Fix:** sort by `blocking_level` for the *current episode*, then `due_stage`, then type; `blocking_level` itself is a **computed matrix** (rule type × stage × gap type), not an LLM field: e.g., inclusion gap at screening = blocking; 溯源提醒 at screening = non-blocking; conflict at screening = blocking; judgment gap = blocking for that rule; a blocking action with `due_stage=基线` must not block screening progression.

**P1-3 — `_recalculate_overall_verdict` rank orders `insufficient` above `investigator` (`reviewer.py:1719-1727`); the project dashboard inherits one-verdict collapse.** The new model replaces this with 主状态+数量 — good. But the *stage* 主状态 must be derived from the snapshot's per-rule states via the same computed matrix, not from a re-derived single verdict, or the collapse returns.

**P2 — Agent count.** Normalizer/Assessor/Critic = 3 sequential LLM calls per run on top of ≤8 parallel OCR VLMs — acceptable on M5 Max, but only if: (a) each has a JSON-Schema I/O contract persisted before the next step (crash resumes at last persisted step — this is the entire Graph value; a plain persisted-step state machine achieves the same, so don't lock LangGraph before prototyping both against crash-recovery + incremental-rerun + HITL-pause scenarios); (b) the Critic sees facts+components+excerpts, **not** the Assessor's verdicts, and can only veto/downgrade/request-action; (c) deterministic validators (the P0-1 matrix, unit/window/negation gates) run **after** the Critic as the final gate — the regression suite proves these guards, not the LLM, carry most of the safety (`reviewer.py` guard functions; ~40 guard tests in `test_phase_workflow.py`).

### 3. ActionRequest contract — exact fields (delta from 12.4)

| Field | Type | Notes |
|---|---|---|
| `action_id` | UUID | immutable |
| `rule_component_ref` | FK | **which component**, not which rule (enables affected-scope rerun) |
| `gap_type` | enum(12) | **explicit** — required for routing AND for the auto-close gate (§2 P0-2); currently only implied |
| `target_party` | enum(研究者方, CRC, CRA, 申办方医学/项目组) | decision 16.2; OCR 校对 is **not** a clinical responsibility → model as internal `校对` action owned by the app user, outside the four-party set (flag: 14.2 路由表 currently assigns OCR 校对 to "用户" — resolve the inconsistency) |
| `requested_action` | free text, structured verb list | 补问/补录/补文件/复测/计算/确认/解释 |
| `acceptable_evidence` | enum | 病历原件/检查报告/处方给药记录/研究者判断文字/澄清函… |
| `due_stage` | enum | 预筛/筛选结束/导入期/基线随机/给药前/归档 |
| `blocking_level` | computed | matrix, not LLM (§2 P1-2) |
| `evidence_trigger` | EvidenceSpan FK | the span that created/closed it — **required for audit** |
| `state` | enum | see transitions |
| `transition_log[]` | {from,to,by: system\|user, trigger_evidence, run_id, reason, ts} | immutable append |
| `recompute_scope` | [fact_ids, rule_ids] | the affected-scope rerun set after resolution — **currently unspecified anywhere; without it "仅重跑受影响事实和规则" is not implementable** |

### 4. State machine (auditable, reversible, not an approval workflow)

States: `open → resolved_system | closed_user → reopened → … ; open → superseded` (on episode re-review). Rules:

1. `resolved_system` requires: new ReviewRun + evidence span satisfying the exact `rule_component_ref` + `gap_type` policy (§2 P0-2). Pure function of inputs — re-entrant and idempotent.
2. `closed_user` requires a `reason`; `reopened` likewise. Both are audit rows labeled **人工关闭/人工重开** — the UI must never present them as 批准/复核通过.
3. **No transition may leave a changed rule conclusion without a new ReviewRun.** Closing an action that does not change the component state is a defect (acceptance A9).
4. Stage/evidence-version supersede: new full snapshot or episode re-review supersedes open actions of that episode (recorded), never deletes; old snapshot + old report + old actions immutable.

### 5. Terminology that reads as a final enrollment decision

- `通过（需验证）` / 通过 (markdown_export.py:22): remove "通过" as a renderable stage label; per-rule use `当前证据未发现明确障碍`, with the reminder inline.
- `判定结果` / `判定为` in report headers: rename to `审核结论（工作底稿，非入排决定）`.
- Stage-level `发现明确入排障碍` (round-2 #7): acceptable internally, but the dashboard/report must pair it with "待研究者/CRC 闭环" counts and a persistent disclaimer: 系统为 AI 辅助审核工作底稿，最终入排决定由研究者依方案作出.
- `overall_verdict` naming and `总结论：pass` (`reviewer.py` summary path): replaced by 主状态+数量 per 16.3.

### 6. High-value acceptance cases (concrete, deterministic expectations)

- **A1 沉默≠否认**: screening note omits history question entirely → rule `暂不能明确`, gap `病历记录不完整`, action→研究者方, NOT `明确契合`, no auto-close.
- **A2 否认已有**: note explicitly denies all prohibited classes within window, no conmed table → `明确契合`(或 per-rule pass) + 溯源提醒 open action + dashboard `溯源待办 1`; regression parity with existing test (test 1069) must hold.
- **A3 引用缺失**: note says "见2025-03-01外院化验单", file absent → `暂不能明确`, gap `已引用文件缺失`, action→CRC 补上传; **never** pass on the reference text. (New — currently unhandled.)
- **A4 冲突硬阻断**: prior record 病程6个月 vs screening note 3年, unresolved → `存在冲突`, both facts shown, 核实 action; LLM output of 明确契合 on that component must be **overridden by the deterministic gate** (this is the "not auto-pick" enforcement).
- **A5 OCR 极性**: "否认…" from low-confidence region → fact determinacy downgrade → `校对` action, conclusion withheld; correction of polarity requires explicit confirm + full transition log.
- **A6 部分日期**: 病程 "since 2020" (year only), threshold 6个月 → bounds both inside → pass w/ bounds shown; threshold 5年 → bounds straddle → `暂不能明确` + `时间锚点/日期不足`, never auto-pass.
- **A7 后续节点升级**: screening 随机窗 rule = `后续节点关注`; baseline episode opens → same rule **auto re-runs** with new anchor; still missing → becomes blocking with due=基线.
- **A8 快照不可变**: full upload → new evidence version; old screening snapshot/report/actions intact; new run supersedes; dashboard shows latest + 历史重审 link.
- **A9 无关上传不关闭**: upload of an unrelated lab PDF → action for `需专业判断` remains `open`; action for `已引用文件缺失` closes only when the *referenced* doc arrives and the component re-evaluates.
- **A10 重开可逆**: user override closes → reopens → closes again; full transition_log with triggers, no state divergence after re-run of the same evidence (idempotency).

### 7. Legacy anchor assessment (short)

Read-only anchors + fresh-project rebuild (16.5) is correct and lower-risk than migration. Two requirements to lock: (a) the **golden regression set** (MG-K10-SAR III / D001 typical error cases, the ~40 guard tests in `test_phase_workflow.py`) must run against the *new* structured pipeline in parallel mode and hit parity before write-path switch; (b) the new pipeline must reuse the *clinical knowledge* encoded in the current guards (analyte substitution, syphilis exception, compound-judgment, phase-timing classes) as **structured validators**, not re-derive it from scratch — otherwise the strongest safety asset is silently discarded. "从零创建" refers to project state, not to knowledge.

## Evidence And Assumptions

- Directly observed: `app/pipeline/reviewer.py` prompt (conflict instruction line 120; evidence hierarchy 108-123; guard functions and adjustments 240-1213, 1698-1800); `app/markdown_export.py:20-31` (labels, ISSUE_VERDICTS); `app/models.py` (flat dataclasses, no fact/episode/action entities — confirms 5.1/5.4); `tests/test_phase_workflow.py` full test inventory and representative bodies (washout denials 549/1069/1085; traceability 1189/1204/1219; phase timing 572-760; syphilis 1249-1295; compound judgment 1296-1341; OCR polarity 1771/2903); `docs/REARCHITECTURE_DISCOVERY_20260812.md` §§5,6,7,8,12,13,14,15,16,17; `docs/PROJECT_CONTEXT.md` top milestone (rounds 1-3 decisions); conference context and main-venue plan.
- Inferences (marked): `pass_verify` dashboard invisibility follows from ISSUE_VERDICTS exclusion + project-list stats behavior (test 2948 counts insufficient/investigator only); the auto-close hazards follow from decision 16.4 text with no stated gate; C3 unhandled status follows from zero grep hits for reference-missing patterns in `reviewer.py` and no matching test.
- Assumptions: report output will be rendered in a Chinese/English mixed form; Codex synthesis retains protocol-authoritative versioning and the four-party owner set as confirmed.

## Risks, Gaps, And Verification Needs

- **Open contradiction to resolve first:** shipped prompt 优先采信既往源文件 vs user decision 不自动选边 (Q1) — affects C6 gate design.
- **Unspecified mechanism:** `recompute_scope` / fact-rule dependency graph — without it, "仅重跑受影响事实和规则" (round-2 #2, 14.2 OCR row) and action auto-close scoping are unimplementable; needs an `EligibilityRiskLink`-level bidirectional index (fact ↔ RuleComponent) with versioning.
- **Owner-set inconsistency:** OCR/解析校对 is routed to "用户" (14.2) but the fixed owner set is four clinical parties (16.2) — decide whether 校对 is an internal non-clinical action type.
- **Verification needs (Codex-owned):** confirm A3/A4/A5/A6/A9 acceptance cases against the prototype; parity run of the golden regression set through the new pipeline; browser check that dashboard counts render 溯源待办/冲突/需判断 distinctly at narrow viewport.

## Recommended Next Step

1. Codex answers Q1-Q4 (below); provisional safe path if unanswered: implement C6 as **hard block to 存在冲突** (conservative, matches 不自动选边) and auto-close **disabled for judgment/conflict/interpretation gap types** — both are reversible at prototype stage.
2. Lock the P0-1 invariant matrix and the ActionRequest state machine (§§2-4) as the contract before any data-layer work.
3. Prototype order per 16.6: interactive dashboard + Patient Profile + rule/evidence workbench first, including A1-A10 as clickable scenarios; only then data layer, with LangGraph vs explicit state machine decided on crash-recovery + incremental-rerun + HITL-pause evidence, not on feature lists.

**Bounded questions for Codex:**

- **Q1 (blocks C6):** Round-2 #4 says conflicting sources 并列展示、不自动选边, but `reviewer.py:120` currently instructs 优先采信既往源文件. Should the deterministic gate hard-block a contested component to `存在冲突` regardless of LLM conclusion, with no auto-side-pick? My recommendation: yes; and align/delete the prompt line.
- **Q2 (blocks auto-close design):** Confirm auto-close scope = only the specific `missing_component` state change in a new ReviewRun (unrelated uploads never close), and that gap types 需专业判断 / 资料冲突 / 方案解释冲突 are exempt from auto-close. My recommendation: yes to both.
- **Q3 (blocks C1/A5):** May the single user freely flip negation ("否认"↔"有") during OCR 校对 without an explicit confirmation step, given it is a clinical-data change? My recommendation: no — require explicit confirm; corrections are CorrectionRecords with before/after/reason.
- **Q4 (blocks dashboard spec):** Must 溯源提醒 be an open, countable ActionRequest (`溯源待办 N`) rather than a passive note, per rule conclusion `当前证据：转述（待溯源）`? My recommendation: yes — otherwise the reminder is invisible to the 主状态+数量 dashboard (current `pass_verify` behavior).
