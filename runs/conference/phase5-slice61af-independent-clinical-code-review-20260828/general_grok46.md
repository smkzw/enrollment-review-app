我将按会议角色做只读独立复核：先读指定上下文和计划，再核对源代码、测试与 v5/v6 工件。会议计划里来源包是空的，我会从仓库里定位 Phase 5.8d、p803-p805、v5/v6 工件和验收摘要。已定位 61aa–61ae 工件与 61ab 代码合同；接下来读父级验收、源代码和 v5/v6 工件。接下来核对门禁实现、定向修订寻址，以及 v6 三个控制点的字段。# Conference Participant Output: phase5-slice61af-independent-clinical-code-review-20260828 - general_grok46

## Boundary Check

- Role `general_grok46` / Grok Build `grok-4.6` / conference mode `parallel`.
- Work stayed inside the runner CWD. No production paths were read or written. No source, test, artifact, or report files were modified. The runner-managed path `runs/conference/phase5-slice61af-independent-clinical-code-review-20260828/general_grok46.md` was not written by tools.
- Other participant outputs were not read. The existing conference review file is an empty Codex stub (`TODO`) and was not used as evidence.
- This is not a visual, browser, PPT, or subject-file pass. No final clinical, regulatory, or publication authority is claimed.
- Initial read set: `context/phase5-slice61af-independent-clinical-code-review-20260828_conference_context.md`, `plans/codex_main_venue_phase5-slice61af-independent-clinical-code-review-20260828.md`. Both still have TODO source packets; additional reads were required to reconstruct the real source of truth.

## Independent Work Product

### Independent audit of the objective

The assignment asks three questions. They are not the same as “did v6 gate-pass”:

1. Does code stop “无需再次检查” from being treated as a mandatory screening action, and does it catch evidence that demands proof the waived action did not occur?
2. After one source unit yields multiple candidates, does wire-position repair avoid out-of-scope rewrite, misalignment, candidate loss, or false release?
3. Are the three v6 control points faithful to `body.p804`/`body.p805`, without recreating 流程第14项 or EX-22?

I treated `parent-clinical-acceptance.json` as a parent claim, not as closure. `clinical-qc.json` still records `parent_clinical_acceptance: pending_codex` and `structured_control_deconstruction_accepted: false`.

### Highest-impact defect

**Stage-split plus per-candidate gates reintroduce a screening “must complete” control for the same p804 panel that the 28-day waiver is supposed to spare.** This is a clinical-logic defect in the accepted v6 artifact, not a test-count issue.

Reproducible path:

1. Source: `body.p804` = 8-item panel, then “可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。”
2. Live v6 attempt 4 (`artifacts/phase5-slice61af-same-source-repair-addressing-20260828/execution/raw-responses.json[3]`) splits that one unit into:
   - Control 3 `pctrl-...-pcc-136f6e944a758e942f4aa33b`：筛选 `decide_at_node`，义务 `complete_or_verify` “完成乙肝表面抗体、乙肝e抗原、乙肝e抗体”，证据 “确认三项新增检查已完成”，`due_stage=screening`。
   - Control 2 `pctrl-...-pcc-59d4b349ce2bfc570ea7156b`：基线 `decide_at_node`，义务把 28 天有效性与“无需再次检查”绑在同一 `verify_result_validity` 原子上。
3. `_check_mixed_decision_stage_control` (`app/protocols/protocol_control_gate.py`) only looks inside one candidate. After the split, Control 3 has an unanchored routine action and no future anchor, so MIXED does not fire. Control 2 has a timed atom, so MIXED does not fire.
4. `_check_exemption_evidence_modality` only inspects evidence on the candidate that still contains 无需. Control 3 has no exemption token, so “确认三项新增检查已完成” is not classified as overstated non-occurrence evidence.

**Effect:** a subject with dated HBsAb/HBeAg/HBeAb inside the first-dose−28d window can satisfy Control 2 and still fail Control 3 at screening. That is the original misread (“无需再次检查” → 必须在筛选执行）relocated to a sibling candidate. Parent check 1 actually endorses this split (“筛选期增量检查…并在筛选节点判定”), which I challenge.

Concrete remediation:

- Add a **same-source cross-candidate invariant**: if unit U has a 28-day / 无需 waiver candidate, any sibling `complete_or_verify` on the waived panel must accept qualifying historical results and must not require a new screening-visit draw as minimum evidence.
- Or stop using MIXED split for “panel execution vs. result-validity waiver of the same panel”; keep one candidate with a timed waiver atom and no unanchored complete for the waived items.
- Until that invariant exists, do not treat v6 as clinically faithful to p804.

### Challenge 1 — “无需再次检查” vs mandatory screening, and overstated non-occurrence evidence

**What the code actually does (evidence):**

| Mechanism | Location | Behavior |
|---|---|---|
| Planning cue | `app/protocols/protocol_control_planning.py` `_REQUIRED_ACTION_PATTERNS` | Isolated sentence “筛选期/基线期无需再次检查” → `preserve_exemption_condition`. |
| MIXED split | `protocol_control_gate.py` `_check_mixed_decision_stage_control` | Unanchored routine (`将/应/须/需…进行/完成/检查`) **and** future-anchor validity in the **same** candidate → `MIXED_DECISION_STAGE_CONTROL`. Exemption token on the **same atom text** suppresses the routine half (`not _EXEMPTION_MODALITY_RE.search(atom_text)`). |
| Conditional bind | `_check_conditional_exemption_binding` | Source must look like `可接受/若/如…，…无需`. Exemption atom spans must overlap a timed atom or trigger in the **same group**. |
| Overstated evidence | `_check_exemption_evidence_modality` | If any obligation atom matches 无需, any evidence matching `未/没有 … 再次/重复 … 检查/检测/执行` → `EXEMPTION_EVIDENCE_OVERSTATED`. |
| Wiring | `_validate_candidate` ~3344 and control validation ~3568 | Both checks run per candidate/control. |

Synthetic coverage in `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`:

- `test_planning_freezes_exemption_as_required_semantic_action`
- `test_conditional_exemption_cannot_lose_its_same_source_condition` / `_accepts_condition_in_same_obligation_group`
- `test_conditional_exemption_is_not_mislabeled_as_current_stage_action` (timed validity + exemption atom; does **not** test a sibling screening complete)
- `test_exemption_evidence_cannot_require_the_waived_action_not_to_occur` only two strings: “确认未重复执行病毒学检查” and “且筛选期/基线期未重复执行病毒学检查”

**v5 failure (evidence):** `artifacts/phase5-slice61ae-.../execution/runner-result.json`

1. schema time-window
2. `MIXED_DECISION_STAGE_CONTROL`
3. `EXEMPTION_EVIDENCE_OVERSTATED`
4–5. `REPAIR_SCOPE_ESCAPE: 定向修订候选发生拆分、合并或对应关系不唯一` then identical-fingerprint stop

That is the old 1:1 source-key repair breaking after a same-source split. v5 is a valid negative control, not a clinical pass.

**Inferences (not evidence):**

- Intra-candidate gates are real and would have caught 61ac’s evidence line “筛选期/基线期访视记录，确认未重复执行病毒学检查” **on the waiver candidate**.
- They do **not** prevent the waived panel from being re-expressed as a screening complete on a sibling (v6 Control 3).
- MIXED is blind if routine + 无需 share one unanchored atom: the exemption regex nullifies `has_unanchored_routine_action`. Binding then depends on a time_constraint still being present in that group.

**Evidence-regex holes (inference, reproducible by inspection):** `_EXEMPTION_NONOCCURRENCE_EVIDENCE_RE` misses “证明筛选期未做病毒学检查”, “确认筛选期没有病毒学检查”, “未再行检查”, because they lack `再次|重复` within 12 characters after `未/没有`.

### Challenge 2 — same-source split and wire-position repair

**What the code actually does (evidence):**

`app/agents/protocol_control_deconstructor.py` `_restore_bounded_wire_repair`:

- MIXED / `allow_candidate_repartition=True`: freeze non-overlapping source keys; accept current drafts whose units ⊆ authorized union; reject crossing or incomplete union.
- Else if `mutable_candidate_indexes`: require equal candidate counts; replace `current.candidate_drafts[index]` only at authorized indexes; reject source-id change at that index.
- Else if source keys: require unique 1:1 key correspondence (this is the v5 killer).
- **After every path, candidates are sorted** by `(source_structure_unit_ids, title, json dump)`.

Runner (`~2457–2547`): on MIXED, indexes are cleared and union expansion is used. On non-repartition errors, `mutable_candidate_indexes` is filled from `_candidate_ids_from_wire` order.

`_validate_bounded_output_repair` **does not receive indexes**. A candidate is mutable if its source-key tuple is in `mutable_candidate_source_keys`. Two same-source siblings therefore both look mutable after hydration.

**v6 live path did not empirically prove position repair (evidence):**

- Attempt 2 MIXED on p805, prompt `候选草稿位置 [1]`.
- Attempt 3 raw still has p804 mixed at `[0]` and p805 validity-only at `[1]` — index `[1]` matched the **pre-sort** model order.
- Restore then **sorts**. `su-3de4633dd1cb5721547f0bb2` (p805) sorts before `su-86389bb90acd044a0835089c` (p804), so the hydrated MIXED on p804 is reported as prompt index `[1]` for attempt 4.
- Attempt 4 uses MIXED **repartition** (p804 union), not the unique-index path. Issue text: “已由系统原样保留定向修订范围外的上一轮内容”. p805 is frozen from attempt 3; p804 is split into two current drafts. That is union restore, not positional identity.

The synthetic tests that actually call `mutable_candidate_indexes={1}` (`test_same_source_candidate_repair_uses_bounded_wire_position`, `test_runner_targets_one_of_two_same_source_candidates_by_wire_position`) keep **identical list order** in the fake transport. There is no swapped-order, insert-in-middle, or title-sort-drift case.

**Defect (inference, high, engineering):** positional restore compares `previous[i]` (already sorted from the last restore) with `current[i]` (provider order). A model that returns `[repaired_B, unrepaired_A]` while previous sorted order is `[A, B]` will write B’s slot from `current[1]` (= A), drop the repair, and can duplicate A. Hydration validation will not catch it if both share source key `("su-02",)`.

False-release risk: sibling rewritten out of scope + same-source key treated as mutable. Candidate-loss risk: count-change is rejected only on the index path; repartition can drop a sibling if it is omitted from current and not frozen (frozen is “previous keys not in mutable keys”; same-source siblings are all mutable under MIXED expansion). That expansion is why attempt 4 could legally introduce a second p804 candidate. It is also why a later **non-MIXED** repair (evidence overstate, as in v5 attempt 3) still needs unique addressing; v6 never re-hit that error class.

**Remediation:**

- Address by `control_candidate_id` / content fingerprint, not post-sort array index.
- Sort both sides with the same key **before** index mapping, or stop sorting until after identity restore.
- Pass `mutable_candidate_indexes` (or IDs) into `_validate_bounded_output_repair` and freeze same-source siblings that were not targeted.
- Add a synthetic case: two same-source drafts, repair index 1, current list swapped; expect sibling frozen and repaired body kept.
- Add a live replay of v5’s EXEMPTION_EVIDENCE_OVERSTATED **after** a same-source split; v6 does not currently demonstrate that.

### Challenge 3 — v6 three control points vs p804/p805, flow 14, EX-22

Authoritative excerpts (frozen in v6 `clinical-qc.json` / `compact-handoff.md`):

- p804: 乙肝表面抗原、表面抗体、e抗原、e抗体、核心抗体、HCVAb、HIVAb、梅毒特异性抗体；首次给药前28天可接受；**筛选期/基线期无需再次检查**。
- p805: HBsAg阴性且HBcAb阳性 → HBV-DNA；HCVAb阳性 → HCV-RNA；梅毒特异性抗体阳性 → 非特异性抗体；首次给药前28天可接受；**无需再次检查**（无“筛选期/基线期”字样）。
- Flow 14 / p328: core 5 tests + the same three reflexives + 研究者判断 past syphilis.
- EX-22 / p685–p689: screening infection exclusion, including HBsAg+ or HBcAb+ **and** HBV-DNA+; HCVAb+ **and** HCV-RNA+; HIVAb+; syphilis specific+ with cured-infection investigator exception.

v6 published controls (`agent-controls.json`):

| # | Title | Source | What it is | Flow14 / EX-22 |
|---|---|---|---|---|
| 1 | 病毒学补充检测结果首次给药前28天有效期 | p805 `su-3de4633dd1cb5721547f0bb2` | Three trigger groups (HBsAg−∧HBcAb+, HCVAb+, syphilis specific+); one shared `verify_result_validity` 28d; evidence dated reports “如适用”; relation `supplementary_requirement` → `pcm-row-2a4db6b98190f7f0c22da3b3` @ `flow-baseline` | Does **not** clone EX-22 positivity/exclusion or investigator cured-syphilis exception. Drops p805 **execution** of HBV-DNA/HCV-RNA/non-specific, claiming flow 14 already owns it. |
| 2 | 病毒学检查结果首次给药前28天有效期及无需再次检查 | p804 | Timed 28d + 无需 in one atom; evidence dated report only; no 未重复执行 | Supplement to flow 14 validity, not a second core-panel execute. |
| 3 | 病毒学检查新增项目（HBsAb/HBeAg/HBeAb） | p804 | Screening complete of the 3 extras; excerpt still quotes the full 8-item sentence | Avoids re-executing the five flow-14 tests **in the statement**, but still **requires screening completion** of extras. |

p803 disposition: `required_procedure` linked to `pcm-row-2a4db6b98190f7f0c22da3b3`, notes “章节标题…完全对应”. That is the correct non-candidate handling of the heading.

**Faithfulness judgment (inference, not clinical sign-off):**

- **Aligned:** 28d window on routine and reflex results; no EX-22 clone; no second official rule number; no “禁止重复检查”; waiver-candidate evidence is dated lab report, not non-occurrence; three p805 triggers preserved as DNF groups.
- **Not aligned / over-split:** Control 3 converts p804’s waived extras into a screening must-complete. Control 2’s evidence text is only “病毒学检查报告及报告日期”, so it is unclear whether extras are in that validity set. Control 1 obligation `applies_to_trigger_branch_indexes` is empty, so one lumped validity statement covers all three reflexes; parent explicitly accepted that, but a single failed HBV-DNA window should not semantically demand HCV-RNA/non-specific evidence except “如适用”.
- **p805 wording gap:** p805 waiver does not say 筛选期/基线期. Control 1 statement still appends “无需再次检查” onto the 28d atom. That is closer to p805 than inventing dual-stage language, but it is still not an explicit stage-scoped waiver.
- Parent file `accepted` vs qc `pending_codex` is an internal contradiction. Tests `975 passed` are not clinical acceptance.

### Draft / output plan (for Codex, not executed)

1. Reject v6 as 5.8d virology closure; keep `claims_complete=false`.
2. Encode a same-source waiver↔execution invariant and an order-independent repair identity test **before** another MTPLX run.
3. Re-run a v5-class evidence-overstate after split, plus a swapped-order position test.
4. Only then consider a v7 replay. Do not publish controls from this artifact.

### Objections to the current plan / parent claim

- Parent check 1 (“筛选期增量检查…筛选节点判定”) conflicts with p804’s 无需再次检查 covering the whole listed panel, including the three extras.
- Parent verification cites focused tests and protocol `975 passed` as if they cover the live v6 clinical split; they cover synthetic MIXED/repartition/exemption strings, not Control 3 vs Control 2.
- “按上一轮 wire 位置定向修订” is only weakly demonstrated in production: v6’s last successful restore was MIXED source-union freeze of p805, not ID-stable positional replace among two p804 drafts.
- Sorting after restore makes the diagnostic index in the repair prompt a function of `su-*` lexicography, not of the model’s array.

## Evidence And Assumptions

### Evidence (directly observed)

- Conference context/plan source packets are TODO; real SoT reconstructed from 61ab/61ac/61ad/61ae/61af artifacts, `app/protocols/protocol_control_gate.py`, `app/protocols/protocol_control_planning.py`, `app/protocols/protocol_control_repair_errors.py`, `app/agents/protocol_control_deconstructor.py`, `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`.
- `CANDIDATE_REPARTITION_GATE_CODES` = `ACTION_TARGET_SCOPE_MISMATCH`, `MIXED_DECISION_STAGE_CONTROL`, `MIXED_TRIGGER_DECISION_STAGES`. `EXEMPTION_EVIDENCE_OVERSTATED` is **not** in that set.
- v5 `d001-ii-virology-p803-p805-contract-v5` / `artifacts/phase5-slice61ae-virology-waiver-stage-contract-20260828`: runner `需要核对`; last issues `REPAIR_SCOPE_ESCAPE` unique correspondence, twice.
- v6 `d001-ii-virology-p803-p805-contract-v6` / `artifacts/phase5-slice61af-same-source-repair-addressing-20260828`: 4 attempts `schema_invalid → publication_invalid → publication_invalid → parsed`; 3 controls; gate issues `[]`; protocol SHA-256 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`.
- v6 attempt-4 restore note present; p804 linked to **two** candidate IDs; p805 to one; p803 `required_procedure`.
- 61ac v3 hydrated evidence still contains “确认未重复执行病毒学检查” (`agent-controls.json` / `hydrated-batch.json`).
- `_restore_bounded_wire_repair` sorts at lines 2246–2253; index replace at 2143–2175; `_validate_bounded_output_repair` has no index parameter (1869–1951).

### Assumptions

- Frozen flow-14 catalog item `pcm-row-2a4db6b98190f7f0c22da3b3` does own screening execution of the core 5 tests and the three p805 reflexives. I did not re-audit the catalog row body beyond v6 notes and p328 attached excerpt.
- Downstream enrollment evaluation would honor `complete_or_verify` + screening `due_stage` as a need to show those tests done at screening, not merely later baseline validity.
- Codex remains the only party that may accept or reject clinically.

### Inference

- Per-candidate exemption gates are necessary but insufficient once MIXED forces a sibling execution candidate.
- v6 “position repair” success is mostly “p805 frozen by disjoint source key under MIXED repartition”.
- Parent `accepted` overstates both clinical fidelity and the repair mechanism that was exercised.

### Uncertainty

- Whether extras (HBsAb/HBeAg/HBeAb) were intentionally excluded from flow 14 and therefore “must appear as a screening control” was a parent product choice. If so, the choice still collides with p804’s waiver sentence.
- Whether empty `applies_to_trigger_branch_indexes` is defined as “all branches” in the evaluator. Artifact notes treat it that way.
- I did not re-execute pytest; I did not open a browser; I did not read subject documents.

## Risks, Gaps, And Verification Needs

| ID | Type | Risk | Repro |
|---|---|---|---|
| R1 | Clinical logic | p804 extras become mandatory screening completion despite 28d/无需 | v6 Control 3 vs Control 2 vs `body.p804` excerpt in `clinical-qc.json` |
| R2 | Engineering | Index restore vs post-restore sort vs unsorted model output → mis-patch / duplicate / drop | `_restore_bounded_wire_repair` 2143–2253; missing swapped-order test |
| R3 | Gate gap | Same-source siblings both mutable in `_validate_bounded_output_repair` | 1916–1922 |
| R4 | Gate gap | Overstated-evidence regex requires 再次/重复 | `protocol_control_gate.py` 281–285 vs 61ab tests 223–226 |
| R5 | Gate gap | Routine+无需 on one unanchored atom suppresses MIXED | `_check_mixed_decision_stage_control` 2032–2035 |
| R6 | Process | Parent acceptance vs qc pending; tests ≠ clinical accept | `parent-clinical-acceptance.json` vs `clinical-qc.json` |
| R7 | Coverage | Live v6 never re-tried `EXEMPTION_EVIDENCE_OVERSTATED` after split (the v5 stopper) | v5 attempts 3–5 vs v6 attempts 2–4 |

Verification Codex still needs (I did not run):

1. New synthetic: swapped current order under `mutable_candidate_indexes={1}`.
2. New gate: same-source waiver candidate present ⇒ sibling screening complete of waived analytes is illegal unless evidence is dated qualifying results (not “已完成”).
3. Adversarial evidence strings without 重复/再次.
4. Confirm flow-14 catalog item text really includes HBV-DNA / HCV-RNA / 梅毒非特异性抗体 execution, so Control 1’s drop of those completes is justified.
5. Do not treat `975 passed` or v6 `gate.accepted=true` as 5.8d closure.

## Recommended Next Step

Codex should **not** close Phase 5.8d virology on this v6 artifact.

Safe provisional path: keep the v5 failure and v6 parse as durable evidence; do not publish the three controls; implement (a) cross-candidate waiver vs execution invariant on the same source unit, (b) identity-stable same-source repair that does not depend on post-sort indexes, (c) a swapped-order regression and a post-split evidence-overstate replay; then decide on a v7 live run.

Bounded questions for Codex:

1. Is Control 3’s screening `complete_or_verify` of HBsAb/HBeAg/HBeAb an intentional product reading of p804, or should those three analytes inherit the same 28d/无需 waiver as the rest of the listed panel?
2. Should MIXED splitting be forbidden when the unanchored action is the panel that the timed atom waives, rather than a true separate screening increment?
3. For same-source positional repair, is the intended identity `candidate_ids` / content fingerprint, with indexes only diagnostic in the prompt (as the v6 repair prompt already says “仅用于诊断”)?
4. After (1)–(3), is the next live replay allowed to reuse v6’s accepted p805 validity candidate, or must the whole p803–p805 packet be regenerated under the new invariant?

If Codex cannot answer (1) in-session: treat Control 3 as **not faithful** to p804 and block publication until an explicit parent override is written that p804’s 无需 **does not** apply to HBsAb/HBeAg/HBeAb. That override is not in the protocol text I read.
