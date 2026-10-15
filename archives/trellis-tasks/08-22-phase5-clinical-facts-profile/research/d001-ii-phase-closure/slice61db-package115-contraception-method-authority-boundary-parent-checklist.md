# Slice61db Package 115 Contraception Method Authority Boundary Parent Checklist

## 1. Identity and frozen boundary

- Task: `phase5-slice61db-20260830`
- Group: `d001-ii-package115-contraception-method-authority-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 115: `pap-9fb70d121e089bc533c21255`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`
- Package 115 owns exactly `body.p1322-p1333` (12 units); 39 frozen context units; 64 frozen source span ids.

Model-free source closure only. No clinical semantic model, no control-point publication, no subject/OCR/Patient Profile/browser/visual stage. Keep `claims_complete=false`. Parent clinical acceptance remains with Codex.

## 2. Owned closure and read-only boundary

Package 115 owns exactly body.p1322-p1333:

1. `body.p1322` — 女性连续停经12个月，并排除妊娠及其他可能导致闭经的医疗原因后，即可临床诊断为绝经。
2. `body.p1323` — 2.有生育能力女性参与者的避孕规定与方法 (heading)
3. `body.p1324` — 在筛选时血妊娠试验阴性后，必须开始采取适当的避孕措施。
4. `body.p1325` — 从签署知情同意书之日开始至研究药物末次给药后3个月为止……（禁止使用激素类避孕）……讨论/选择/知晓。
5. `body.p1326` — 在研究流程中计划的访视点……病历中记录对话和同意……停用或已知/怀疑怀孕需立即打电话。
6. `body.p1327` — 高效的避孕方法是指持续和正确地使用时，年失败率低于1%的避孕方法。包括：
7. `body.p1328` — 正确放置含铜的宫内节育器（Intrauterine-device，IUD）
8. `body.p1329` — 男性伴侣绝育
9. `body.p1330` — 双侧输卵管结扎/双侧输卵管切除术/双侧输卵管闭塞术
10. `body.p1331` — 禁欲。禁欲定义为完全和持续地避免所有的异性性交。禁欲的可靠性需要根据研究的持续时间以及参与者的首选和平常的生活方式进行评估
11. `body.p1332` — 可接受的避孕方法：含杀精剂的男用避孕套或女用避孕套……不能同时使用……建议/强烈建议妊娠检查。
12. `body.p1333` — 不可接受的避孕方法：定期禁欲……无杀精剂避孕套……杀精海绵……性交中断。

`attached_source_refs=[]`. `body.p1321` (Package114) and `body.p1334` (Package116) are frozen context only: read-only, never attached, never disposed, never published. The other 37 context units stay read-only and are not elevated. Package114 ends at p1321 (no write-back); Package116 starts at p1334 (no absorption).

## 3. Source-driven semantic layers

### 3.1 Structure heading
- p1323 is the structural-only section heading.

### 3.2 Menopause clinical diagnosis definition
- p1322 defines menopause: 12 months continuous amenorrhea, excluding pregnancy and other medical causes of amenorrhea.
- This closes Package114's p1321 "绝经后女性" branch and supports the pregnancy/FSH control's postmenopausal (FSH>40 IU/L) applicability.
- Ownership stays Package115; do not rewrite the 12-month term, drop exclusions, or turn it into an exclusion/pregnancy-duty.

### 3.3 Distinct time anchors (must never merge)
- p1324: screening-negative blood pregnancy test → must start appropriate contraception (`screening` anchor).
- p1325 / IN-06: ICF date start → last dose + 3 months (`icf_date` + `last_dose_date/after/3 months` anchors).
- Pregnancy/FSH control: screening / baseline / first-dose-pre-dose detection anchors.
- Do not merge p1324's screening-negative trigger with the ICF-date start; do not attach the post-dose tail duration to the ICF date.

### 3.4 Modality and method-group preservation
- p1324 "必须开始" and p1325 "必须同意" are mandatory; do not downgrade to recommendations.
- p1327's high-efficiency list p1328/p1329/p1330 are parallel OR choices; never flatten to AND; p1330 keeps 双侧 (bilateral) and its three surgical approaches are OR.
- p1331 abstinence is defined as complete and continuous avoidance of all heterosexual intercourse; reliability is a professional assessment tied to study duration and usual lifestyle. Periodic abstinence or withdrawal is NOT equivalent.
- p1332 acceptable methods: male or female condom with spermicide are OR but cannot be used simultaneously (friction failure risk); post-dose pregnancy check every menstrual cycle is a recommendation, strongly recommended for delayed menses — never upgraded to a mandatory procedure; spermicide condition must not be dropped.
- p1333 unacceptable methods (periodic abstinence, condoms without spermicide, spermicidal sponge, withdrawal) must not be mixed with acceptable conditions.
- p1325 hormonal contraception prohibition (禁止使用激素类避孕) is mandatory.

### 3.5 Reuse of accepted p1325/p1326 semantics
- slice60m accepted group `d001-ii-contraception-documentation` (checkpoint 2026-08-28 + `parent-clinical-acceptance.json`) already published the p1325/p1326 increments: hormonal prohibition, method discussion/selection/knowledge, ICF→last-dose+3mo interval, planned-visit counselling + medical-record recording + participant agreement, conditional immediate contact on stopped method or known/suspected pregnancy.
- These are reused, not re-published: `forbidden_candidate_source_refs=[body.p1325, body.p1326]`.

### 3.6 Candidate disposition conclusion
- `required_candidate_source_refs=[]`, `pre_enrollment_source_refs=[]`, `candidate_required_markers_by_source_ref={}` — candidate count is not predeclared and no candidate is forced.
- p1322 and p1324-p1333 are explicitly disposed as `supporting_or_supplement`; p1323 remains structural-only. This prevents a false closure where the prose preserves semantics but the machine-readable disposition map is empty.
- All owned refs are forbidden candidates. p1325/p1326 reuse the accepted slice60m controls; p1322/p1324/p1327-p1333 remain source-linked definitions, trigger clarification, method taxonomy, modality, and evidence guidance for IN-06 and pregnancy/FSH rather than duplicate controls.
- IN-06-covered continuous contraception duty must not be re-published as a new candidate (covered-branch markers).
- Deterministic gates reject any candidate emitted from an already disposed source and separately reject the listed semantic attacks (anchor merging, OR-flattening, modality upgrade, condom co-use, category cross-over). Preservation of directly sourced components is carried by the explicit disposition map, `clinical_qc_checks_by_source_ref`, `exception_semantics_by_source_ref`, and Codex clinical acceptance.

## 4. Config blind checks

Config: `configs/representative_group_package115_contraception_method_authority_boundary.v1.json`

- owned exactly p1322-p1333; attached empty; required candidates empty; forbidden candidates exactly all twelve owned refs
- structural-only exactly p1323; the other eleven owned refs are `supporting_or_supplement`; visit/family/action/target maps and required-marker map remain empty (no candidate forced)
- known targets include IN-06 (`pcm-row-0555ca044760e4df3ef7e3c3`) and the pregnancy/FSH required procedure (`pcm-row-18127a0dc9921364671ebb8c`)
- workflow stages: flow-screening / flow-baseline / flow-d1-pre-dose
- exception_semantics/clinical_qc preserve: menopause definition, screening-vs-ICF anchors, method OR, condom mutual exclusion, recommendation modality, abstinence reliability, Package114/116 isolation, p1325/p1326 anti-duplication
- owners: p1307/p1308=113, p1321=114, p1322-p1333=115, p1334/p1335=116, p515/p516/p567=45, p575/p581/p583=46, p584=47, p594=48, p618/p623=50, p838=75
- forbidden_next_package_refs covers p1334-p1341/p1343-p1346 (Package116 owned)
- unowned_context_source_refs lists the 26 unowned context refs
- claims_complete must remain false

## 5. Ownership / phase / excerpt regressions

- coverage study_phase=phase_ii and phase_scopes=[unknown] for p1322-p1333
- source orders 32180..32290 step 10
- unit kinds: list_item for p1322/p1328-p1331; paragraph for p1323-p1327/p1332/p1333
- each source_span_ids/member_source_refs is singleton self-ref
- 39 context units disjoint from owned; p1321 (owner 114) and p1334 (owner 116) present in context only
- p1334 must not appear as owned/attached, in forbidden/required candidates, or as declared prompt source

## 6. Model-free dry-run

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package115_contraception_method_authority_boundary.v1.json \
  --dry-run
```

Expect owned_count=12, attached_count=0, unit_count=12, claims_complete=false; source_rows contain p1322-p1333 as owned via frozen_plan_owned; batch structural-only for p1323; context_structure_unit_ids empty; known targets include IN-06 and pregnancy/FSH; prompt includes all twelve refs and the required semantic markers; prompt excludes p1321/p1334 and Package116 refs; clinical-qc agent_candidates empty with dry-run gate skipped.

## 7. Regression command and stop conditions

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61db_package115_contraception_method_authority_boundary.py
```

Adjacent-package regressions remain Codex-owned after merge. Stop on SHA/owner/order/phase/excerpt/anchor-merger/OR-flatten/modality-upgrade/abstinence-reliability-loss/Package114-116 isolation failures. Shared-code edits are out of scope for this worker.

## 8. Codex final checks

This checklist proves model-free prepare closure and deterministic regression paths only. It does not prove hydrated clinical acceptance, publication gate pass, subject/OCR/Profile completion, or real-world contraception verification. Codex remains final authority.

- [x] Parent confirms p1322-p1333 ownership and p1323 structural-only.
- [x] Parent confirms p1324 screening-negative anchor stays distinct from p1325/IN-06 ICF anchor.
- [x] Parent confirms method OR (p1327-p1330), condom mutual exclusion (p1332), unacceptable list (p1333), and abstinence reliability assessment (p1331) are preserved by gates.
- [x] Parent confirms p1325/p1326 accepted slice60m semantics are reused and not re-published; IN-06 covered branches are not duplicated.
- [x] Parent confirms Package114 (p1321) read-only and Package116 (p1334+) isolation, claims_complete=false.
- [x] Hydrated publication, subject review, OCR, Patient Profile, browser and visual acceptance remain outside Package115.
