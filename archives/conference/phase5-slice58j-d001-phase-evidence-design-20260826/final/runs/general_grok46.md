Trellis SessionStart ✓ — Independent challenge of the D001 II phase-evidence closure design. Reading the assigned context packet and plan first.Next I’ll pull the closure matrix stats, phase contracts, and checkpoints—focusing on the 152 cited units and the shared/unknown upgrade path.Shell was blocked in Ask mode; switching to direct file reads and targeted searches.I have enough to challenge the design: the highest-impact defect is treating “共同章节结构 / 未限定” as positive shared evidence, plus matrix rows that claim shared while citing II-only sources. Drafting the full schema report.

---

# Conference Report: `general_grok46`
**Task:** `phase5-slice58j-d001-phase-evidence-design-20260826`  
**Role:** Cursor CLI / auto — participant 2 (data contract, representative packs, deterministic gates, double-count, acceptance matrix)  
**Mode:** read-only advisory; **not** clinical final acceptance; **no** file writes

## Executive verdict

Current state correctly separates **source closure** (155→152 units, accepted) from **phase closure** (`phase_closure.accepted=false`, 136 issues, `claims_complete=false`). The dangerous gap is not missing tooling — it is **three layers that can be silently collapsed**: (1) structural `phase_scopes`, (2) matrix provisional `phase_disposition`, (3) Agent/Codex clinical shared evidence. The highest-impact defect is that **“共同章节结构 / 未限定某期” remains a licensed upgrade path to `cross_phase_shared` in the Agent contract**, while package 69 already proved that path fails clinically for mixed container chapters under 研究治疗.

---

## ISSUES_ONLY

### I1 — Highest impact: “共同章节结构” is an underspecified positive-shared predicate (unknown→shared upgrade)

- **Failed requirement:** Shared must require positive dual-phase applicability of the *same* requirement; absence of phase limit is insufficient (`CHECKPOINT_20260826_PHASE_PACKING…`; Agent prompt in `app/agents/phase_applicability.py`).
- **Defect:** Prompt still lists “目标处于覆盖两期的共同章节结构中” as a sufficient positive example, without distinguishing:
  - **Shared leaf:** same obligation applies to II and III; vs
  - **Mixed container:** parent heading (e.g. 研究治疗) holds phase-specific children (补救治疗 II≠III) while the leaf is `unknown`.
- **Evidence:** Package 69 first pass used exactly that upgrade (“覆盖两期的共同章节结构” + 未限定); repair2 correctly forced all 11 targets to `unresolved` (`slice58h-v2-plan/merged-package69-probe/post-fix2-result.json`).
- **Why it matters:** Lexical gate `_SHARED_PHASE_TERMS` does **not** include “共同章节”, but the *semantic contract text* still teaches the model that container co-location counts. Any future soft-gate change, or rationale that also says “两期均/共同适用”, reopens the path.

### I2 — Matrix provisional `cross_phase_shared` on explicit II-only sources (false shared / wrong cross-phase share)

- **Concrete counterexample:** `pcm-row-c6eb8bbf8636dc83110216e6` (“筛选基线合并与D1前基线窗口”)
  - `phase_disposition`: `cross_phase_shared`
  - Source heading: `研究评估和程序 > 访视安排 > Ⅱ期临床研究阶段 > 筛选期`
  - Closure report: `phase_scopes=["phase_ii"]` + `PHASE_SHARED_SOURCE_MISSING`
- **Meaning:** Human matrix claims shared while frozen unit is structurally II-only. Accepting matrix disposition as authority would invent cross-phase sharing.

### I3 — `_phase_audit` treats structural `shared` as sufficient to clear shared disposition (pseudo-complete)

In `map_matrix_source_closure.py` `_phase_audit`:

```text
cross_phase_shared && "shared" not in row_scopes → PHASE_SHARED_SOURCE_MISSING
selected_phase_applicable && !(selected|shared in scopes) → PHASE_SELECTED_SOURCE_MISSING
```

- **Defect:** Any cited unit with structural `PhaseScope.SHARED` clears `PHASE_SHARED_SOURCE_MISSING` without checking that the *same obligation* is shared.
- **Coupled defect:** `_structurally_explicit_disposition` maps sole `SHARED` → `CROSS_PHASE_SHARED` with no Agent evidence (`app/protocols/phase_applicability.py`). Table headings naming both II+III flow/schedule (`phase_detection._table_heading_scopes`) can mint structural SHARED.
- **Upgrade path to wrong shared:** weak dual-phase table title → structural SHARED → audit silence → publishable shared without clinical positive evidence.

### I4 — Post-treatment / whole-study window pollution into pre-enrollment controls

- Package 69 owned excerpt: “自签署ICF开始至研究结束…” under 合并用药/治疗 (`su-256df82ad8f103fea4136561`).
- Matrix review already flags diary/post-dose as “不并入入排” and III 补救 as phase boundary only (`d001-ii-control-matrix-review.md`).
- **Missing gate:** No deterministic check that source time window / visit column (治疗后、随访、研究结束) cannot satisfy a row whose `review_nodes.review_stage ∈ {screening, baseline}` or `due_workflow_stage_id` is pre-dose.
- **Pollution path:** Shared/unknown treatment-section unit reused as positive evidence for IE/screening controls → treats on-treatment recording obligations as enrollment closure.

### I5 — Double-count / pseudo-completeness metrics

- Source closure: 155 anchors → 152 unique units (accepted).
- Phase issues: 136 ≈ mostly paired `PHASE_UNRESOLVED` + `PHASE_SHARED_SOURCE_MISSING` on the same rows → **counting issue_count as “work remaining” double-counts rows**.
- 60 matrix `cross_phase_shared` / 22 `selected_phase_applicable` are **hypotheses**, not truth; `claims_complete=false` must stay.
- Running all 137 packages and counting “gate-passed unresolved” as closure would **fake completeness**.

### I6 — Multi-anchor rows: OR-aggregation of scopes hides per-unit polarity

- Example selected rows with `phase_scopes=["phase_ii","unknown"]` still emit `PHASE_UNRESOLVED` (conservative — good).
- But evidence view / Agent package still risks **one disposition for a row while units disagree** (II flow cell + unknown narrative). Unit-level view is mandatory; row disposition must be derived, not primary.

### I7 — Acceptance criteria omission in conference success criteria

Success criteria ask for unknown→shared and post-treatment pollution blockers (good), but omit:
- **II-only source + shared disposition** (I2) as a required blocker;
- **Structural SHARED ≠ clinical shared** (I3);
- **Matrix disposition must never auto-write unit disposition**.

---

## EVIDENCE_LOCATORS

| Claim | Locator |
|---|---|
| Source closed, phase not | `d001-ii-control-matrix-closure-report.json`: `source_closure.accepted=true`, `unique_frozen_unit_count=152`, `phase_closure.accepted=false`, `issue_count=136`, `claims_complete_*=false` |
| 82 rows / SHA | same report + closed matrix header `protocol_document_sha256=36244313…dd98` |
| Unknown→shared probe failure→safe unresolved | `CHECKPOINT_20260826_PHASE_PACKING_AND_RATIONALE_ACCEPTED.md`; `slice58h-v2-plan/merged-package69-probe/post-fix2-result.json` (`final_disposition=unresolved` for 合并用药/治疗 titles) |
| II-only + shared disposition | closed matrix `pcm-row-c6eb8bbf8636dc83110216e6`; report issue at `phase_scopes:["phase_ii"]` + `PHASE_SHARED_SOURCE_MISSING` |
| Audit rule | `map_matrix_source_closure.py` `_phase_audit` ~L271–323 |
| Structural SHARED auto-disposition | `app/protocols/phase_applicability.py` `_structurally_explicit_disposition` ~L145–159 |
| Dual-phase table → SHARED | `app/protocols/phase_detection.py` `_table_heading_scopes` ~L405–406 |
| Agent shared positive-evidence wording | `app/agents/phase_applicability.py` prompt strings ~L1390–1393, L1424–1426; `_SHARED_PHASE_TERMS` ~L349–367 |
| 137 pending, no forged results | `slice58i-v2-plan/summary.json` `batch_count=137`, all pending |
| Heterogeneous control inventory | `research/d001-ii-control-matrix-review.md` §2 (表5, 有效期/复测, 结核, 妊娠, 补救边界) |
| Next safe action | `CHECKPOINT_20260826_D001_MATRIX_SOURCE_CLOSURE_ACCEPTED.md` |

---

## NO_ISSUE_SCOPE

These are **not** alleged broken in this pass:

- Source identity remapping / verbatim span binding for the 155 anchors (source closure accepted).
- Keeping `claims_complete=false` / `manual_clinical_acceptance_required=true` in closure reports.
- Four publish dispositions contract (`selected` / `opposite` / `shared` / `unresolved`) and index-only Agent drafts.
- Package 69 repair2 outcome remaining unresolved rather than upgrading to shared.
- Decision not to run full 137 until matrix-grounded reference dispositions exist.
- Relation closure for 82-row matrix (`external_relation_target_count=0`).

---

## Design answer (challenger, not implementer)

### A. 152-unit selected/opposite/shared/unresolved evidence view

Build a **unit-primary** projection `unit_id → evidence_card`, indexed only from closed matrix `source_anchors[].structure_unit_id` (152), not 1,840:

For each unit:

1. **Frozen facts (deterministic):** `structure_unit_id`, `source_ref`, `heading_path`, `table_context`, `phase_scopes`, verbatim excerpt, span ids, SHA/manifest id.
2. **Matrix hypotheses (non-authority):** citing `matrix_row_id`s, their provisional `phase_disposition`, review stages, time anchors.
3. **Polarity buckets (must be filled before publish):**
   - `supports_selected` / `supports_opposite` / `supports_shared` / `unresolved`
   - Each evidence atom: one unit + its own spans + excerpt + rationale relation phrase
4. **Derived unit disposition:** only from polarity + structural explicitness rules; matrix disposition is input hypothesis / conflict signal.
5. **Row roll-up:** row may publish only if all cited units’ dispositions are compatible; else row stays blocked (`PHASE_UNIT_DISAGREEMENT`).

Do **not** count 1,840 dispositions for this slice; non-cited units stay out of “matrix phase evidence closure.”

### B. Heterogeneous structure classes (must not share one evidence rule)

| Class | Signal | Allowed positive shared? | Default if weak |
|---|---|---|---|
| True shared leaf | Explicit “II与III均适用/标准相同” in unit text | Yes | — |
| Untagged leaf under mixed container | `unknown` + parent has phase-split children | **No** | `unresolved` |
| Opposite-phase citation | III text under II project used as boundary/trigger | Not shared; may be `opposite` or context-only | Do not project as II enrollment obligation |
| II-only flow table | e.g. 表1 Ⅱ期流程表 cells | No; `selected` if II project | — |
| Mixed table (表5) | row/cell may inherit title; old III mis-tag fixed to unknown | Only with positive dual-phase proof of that row | Prefer per-row Agent + Codex |
| Validity / retest | time half-life, not phase name | Shared ≠ automatic | Codex on clinical window |
| TB / pregnancy | multi-trigger + exceptions + visit columns including on-treatment | Split enrollment gate vs on-study follow-up | Separate cards |
| Post-treatment / EOT–EOS | visit after first dose / 研究结束 | Never support pre-enroll `decide_at_node` | Hard reject |

### C. Deterministic vs semantic vs Codex

| Deterministic OK | Semantic Agent required | Codex clinical only |
|---|---|---|
| Identity/span/excerpt recovery | Interpreting unknown leaf under mixed container | Whether 研究治疗 leaf is truly shared for II project |
| Sole explicit `phase_ii`/`phase_iii`/`shared` *from local explicit markers* → structural candidate (not publish) | Distinguishing opposite-phase mention vs shared | TB preventive-therapy exceptions, pregnancy week-12 vs D1 gates |
| Block: unknown→shared; II-only→shared; post-treat→screen | Table5 row applicability | Final accept/reject of matrix hypothesis |
| Block: claims_complete without zero phase blockers | Packaging rationale quality | Closing 5.8d |

**Challenge:** Do **not** auto-publish structural SHARED via `_structurally_explicit_disposition` until a second check proves local explicit shared language (not merely II+III in a schedule title). Treat structural SHARED as `candidate_shared_structural`, still needing polarity evidence or Codex.

### D. Minimal representative pack (not 137)

Risk strata (1 package or focused probe each), selected from `slice58i-v2-plan` by owned unit intersection with the 152 set:

1. **Already run:** package69 合并用药/治疗 unknown leafs (mixed container) — keep as regression gold.
2. **II-only flow:** package owning 表1 Ⅱ期流程表 cells cited by selected matrix rows (e.g. ICF X column).
3. **False-shared matrix row:** package containing `su-14cbbde23a2e420ac91ec1ca` (II 筛选期 baseline window).
4. **表5 full table packet:** all t10 header+12 rows together (no row orphaned from title).
5. **TB + validity/retest cluster:** p807–p813 / related matrix rows.
6. **Pregnancy / FSH:** enrollment EX-29 vs on-study 7.3.7 follow-up (must split).
7. **Opposite/boundary:** 补救治疗 II/III paragraphs — must not project III post-treatment into II enrollment.
8. **Optional:** one dual-phase schedule heading that detector marks SHARED — prove whether structural SHARED over-fires.

**Pass rule for “closure design proven”:** every stratum’s gate outcomes match expected class (including forced unresolved / blocked publish); **not** “N random packages green.”

---

## RECOMMENDED_REPAIR

1. **Rewrite shared positive-evidence contract:** remove bare “共同章节结构” as sufficient; require one of: (a) local explicit dual-phase sameness sentence, (b) Codex-accepted shared authority heading that *does not* contain phase-split siblings for the same obligation family, (c) reliable cross-ref tying the *same* obligation to both phases.
2. **Add deterministic blockers (testable):**
   - `UNKNOWN_TO_SHARED_FORBIDDEN`
   - `SELECTED_OR_OPPOSITE_SCOPE_CANNOT_SUPPORT_SHARED_DISPOSITION` (covers I2)
   - `POST_TREATMENT_SOURCE_FOR_PRE_ENROLL_REVIEW_FORBIDDEN` (source visit/time vs review_stage)
   - `MATRIX_DISPOSITION_NOT_UNIT_AUTHORITY`
3. **Split structural SHARED from publish SHARED;** do not clear `_phase_audit` solely because `"shared" in row_scopes`.
4. **Ship unit evidence view for 152** before any further Agent mass run; align package69’s 11 units to matrix reference cards first.
5. **Acceptance metric:** unique `(row_id)` or `(unit_id)` with open phase blockers — never raw `issue_count`; never “137 packages completed.”
6. Keep `claims_complete=false` until Codex accepts the representative strata + all 82 row×unit conflicts cleared or explicitly waived with override records.

---

## QUESTIONS_FOR_CODEX

1. For 研究治疗 / 合并用药 unknown leafs: is the **authority decision** “shared for II project by design” or “remain unresolved until protocol amendment language exists”? Package69 cannot decide this; it only blocked the bad upgrade.
2. Should structural `SHARED` from dual-phase **流程表标题** auto-publish, or always require Agent/Codex confirmation (recommended: no auto-publish)?
3. For `pcm-row-c6eb8bbf…` (II-only source, shared disposition): is the intended repair `selected_phase_applicable` for this II matrix, or was the source wrong?
4. Does “matrix phase evidence closure” mean (A) only 152 cited units, or (B) 152 plus all units needed to *justify* shared/opposite for those 152 (context units)? Affects representative pack scope.
5. May diary / AE concomitant meds under “研究期间” ever appear as supporting evidence for screening IE rows, or is hard exclusion required?

**Safe provisional path if unanswered:** treat all matrix `cross_phase_shared` over `unknown`/`phase_ii`-only as **blocked hypotheses**; run only strata 1–3 + 表5 probe; do not start 137; do not set `claims_complete`.

---

## RESIDUAL_RISK

- Clinical truth of shared treatment chapters remains open; technical unresolved ≠ clinical shared or non-shared.
- Table5 / TB / pregnancy packs not yet run under repaired shared contract → heterogeneity may still surprise.
- Prompt vs lexical gate mismatch can recur after “helpful” prompt edits.
- 1,298 Agent units outside the 152 can still poison context if retrieval pulls post-treatment / III-only material into owned evidence.
- Conference participant has not re-read all 1,840 units or source DOCX; locators are from frozen closure artifacts and cited probes only.

---

## Objections / decision points for chair

| # | Objection | Decision needed |
|---|---|---|
| 1 | Matrix 60× shared is not a prior; it is the main contamination source | Discard matrix disposition as authority for unit view |
| 2 | “共同章节” in Agent prompt conflicts with package69 clinical safety | Edit contract before more live Agent |
| 3 | Structural SHARED auto-disposition is a silent publish path | Demote to candidate-only |
| 4 | 136 issue_count is a bad KPI | Switch to unique row/unit blockers |
| 5 | Full 137 run would prove scale, not closure | Chair must forbid until strata pass |

---

## Verification needs (for Codex, not claimed done here)

- [ ] Unit evidence cards for all 152 with conflict flags vs matrix disposition  
- [ ] Automated tests for I1–I4 blocker codes  
- [ ] Representative strata 2–7 live or replay  
- [ ] Confirm no path sets `claims_complete=true` while any blocker remains  
- [ ] Explicit non-claim: medical acceptance of D001 II phase applicability

---

**Status:** Complete independent pass for `general_grok46`. No files modified. No final medical acceptance claimed. Runner should persist this body to `runs/conference/phase5-slice58j-d001-phase-evidence-design-20260826/general_grok46.md`.
