# Slice61da Package 114 Fertility Definition Evidence Boundary Parent Checklist

## 1. Identity and frozen boundary

- Task: `phase5-slice61da-20260830`
- Group: `d001-ii-package114-fertility-definition-evidence-boundary`
- Frozen plan: `papl-e17d498106b6f71f440ff2be`
- Package 114: `pap-cd76207b0f3d157c2eaa66d6`
- Selected phase: `phase_ii`
- Protocol SHA-256: `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- Frozen plan SHA-256: `92c7d179428216cfd4c9a47f2636bc7d7cfa8311025100d72dcb299e2f977fa4`
- Structure blob SHA-256: `3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d`

Model-free source closure only. No clinical semantic model, no control-point publication, no subject/OCR/Patient Profile/browser/visual stage. Keep `claims_complete=false`. Parent clinical acceptance remains with Codex.

## 2. Owned closure and read-only boundary

Package 114 owns exactly body.p1310-p1321:

1. `body.p1310` — 附录
2. `body.p1311` — 附录1 避孕的规定与方法
3. `body.p1312` — 有生育能力女性的定义
4. `body.p1313` — 女性在月经初潮后至绝经前被认为是有生育能力的。
5. `body.p1314` — 具有以下情况的女性不被视为有生育能力：
6. `body.p1315` — 尚未经历月经初潮
7. `body.p1316` — 满足以下任一项的绝经前女性：
8. `body.p1317` — 子宫切除术史
9. `body.p1318` — 双侧输卵管切除术史
10. `body.p1319` — 双侧卵巢切除术史
11. `body.p1320` — 注：通过参与者病历核查或医学检查或病史询问进行确认。
12. `body.p1321` — 绝经后女性

`attached_source_refs=[body.p1322]`. This is the single minimum read-only attachment needed to complete the p1321 postmenopausal definition. Ownership, disposition, and candidate publication remain Package 115. The other 37 frozen context units stay read-only and are not elevated. Package 113 ends at p1308; blank p1309 stays unowned; p1323-p1333 contraception clauses are outside Package 114 frozen context and must not be absorbed.

## 3. Source-driven semantic layers

### 3.1 Structure headings
- p1310-p1312 are structural-only titles.
- Titles must not invent subject eligibility, contraception method lists, or enrollment conclusions.

### 3.2 Fertility time-window definition
- p1313 defines childbearing potential from menarche to menopause.
- Do not invert menarche/menopause; do not rewrite this alone into contraception duty or exclusion.

### 3.3 Non-childbearing parent/child OR
- p1314 is the parent condition.
- p1315, p1316, and p1321 are parallel OR children of p1314; never flatten to AND.
- p1317, p1318, and p1319 are parallel OR children of p1316; keep bilateral wording on p1318/p1319.
- p1320 lists parallel confirmation methods (chart review OR medical exam OR history). Do not require all three; do not drop any method.

### 3.4 Package 115 read-only boundary
- p1321 postmenopausal branch is incomplete without Package 115 p1322.
- p1322 stays read-only: no attach elevation, no ownership rewrite, no candidate/disposition publish.
- Do not absorb p1323-p1333 contraception start/methods/prohibitions/post-dose duration.

### 3.5 Candidate disposition conclusion
Item-by-item judgment: this package does not form a new independent pre-enrollment action control, but its definitions and evidence modalities are part of the authority needed to apply existing controls.
- structural-only: p1310-p1312
- supporting_or_supplement: p1313-p1321
- known official target: IN-06, because fertility classification determines whether its contraception obligation applies
- known required-procedure target: pregnancy test or FSH, because fertility/postmenopausal/permanent-sterilization classification selects the applicable verification branch
- required_candidate_source_refs=[] and pre_enrollment_source_refs=[]
- all twelve owned refs are forbidden candidates
- zero new candidates is an evidenced anti-duplication conclusion, not a claim that these sources are unrelated to enrollment review

## 4. Config blind checks

Config: `configs/representative_group_package114_fertility_definition_evidence_boundary.v1.json`

- owned exactly p1310-p1321; attached exactly p1322 as read-only context
- required candidates empty; all owned forbidden
- structural-only exactly p1310-p1312
- dispositions supporting_or_supplement for p1313-p1321
- empty workflow/action/visit bindings; known targets include IN-06 and the pregnancy/FSH required procedure
- exception_semantics/clinical_qc preserve parent/child OR, bilateral terms, confirmation OR, Package 113/115 isolation
- owners: p1308=113, p1310-p1321=114, p1322/p1323=115
- excluded_unowned_structure_refs includes p1309
- forbidden_next_package_refs covers p1322-p1333 as ownership/candidate-publication boundaries; p1322 alone may still be attached read-only
- unowned_context_source_refs lists the 26 unowned context refs
- claims_complete must remain false

## 5. Ownership / phase / excerpt regressions

- coverage study_phase=phase_ii and phase_scopes=[unknown] for p1310-p1321
- source orders 32060..32170 step 10
- unit kinds: paragraph for p1310/p1311/p1313/p1314; list_item for p1312/p1315-p1319/p1321; footnote_or_annotation for p1320
- each source_span_ids/member_source_refs is singleton self-ref
- context units disjoint from owned/attached and not used as candidates
- p1308/p1309 and p1322-p1333 must not appear as owned/attached or declared prompt sources

## 6. Model-free dry-run

```bash
.venv/bin/python \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py \
  --config \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/configs/representative_group_package114_fertility_definition_evidence_boundary.v1.json \
  --dry-run
```

Expect owned_count=12, attached_count=1, unit_count=13, claims_complete=false; source_rows contain p1310-p1321 as owned plus p1322 as read-only attached context; batch structural-only for p1310-p1312; pre-enrollment refs remain empty; known targets include IN-06 and pregnancy/FSH; prompt excludes Package113 and p1323-p1333; clinical-qc agent_candidates remain empty with dry-run gate skipped.

## 7. Regression command and stop conditions

```bash
.venv/bin/python -m pytest -q \
  .trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/test_slice61da_package114_fertility_definition_evidence_boundary.py
```

Adjacent-package regressions remain Codex-owned after merge. Stop on SHA/owner/order/phase/excerpt/OR/bilateral/confirmation/Package113-115 isolation failures. Shared-code edits are out of scope for this worker.

## 8. Codex final checks

This checklist proves model-free prepare closure and deterministic regression paths only. It does not prove hydrated clinical acceptance, publication gate pass, subject/OCR/Profile completion, or real-world fertility/contraception verification. Codex remains final authority.

- [x] Parent corrected p1313-p1321 from unrelated execution text to support for existing IN-06 and pregnancy/FSH controls without publishing duplicates.
- [x] p1322 is attached read-only; owner/package remains Package115 and p1323-p1333 stay excluded.
- [x] Parent/child OR, confirmation-method OR, and bilateral surgery terms are covered by deterministic positive and attack regressions.
- [x] Package103-114 combined regression: 300 passed; slice59n shared regression: 39 passed.
- [x] Independent worker_04 acceptance and formal execution audit passed.
- [ ] Hydrated publication, subject review, OCR, Patient Profile, browser and visual acceptance remain outside Package114.
