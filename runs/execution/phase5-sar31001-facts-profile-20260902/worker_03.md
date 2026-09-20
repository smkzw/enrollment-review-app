# Execution Output: phase5-sar31001-facts-profile-20260902 - worker_03

## Boundary And Context Check

- Scope executed: independent source verification, node-boundary review, anti-overfit checks, and regression tests for subject `31001`.
- No production writes were performed.
- Fact normalization was not called. No facts, events, exposures, or Patient Profile revisions were published by this worker.
- No runner report file was created or modified.
- No credentials or secret values were accessed or printed.
- The existing API service on port `8910` was reachable. A separate managed start attempt correctly failed because the port was already occupied; the existing process was not stopped.

## Work Performed

### Runtime and source manifest

Verified the isolated runtime and source manifest:

- Source root: `/Users/.../31 河北省中医院/31001`
- Five included PDFs; `.DS_Store` excluded.
- All five local source hashes matched the manifest.
- Runtime reported source immutability verified for both manifest entries.

Source SHA256 values:

```text
2.筛选-基线病历/31001-病历.pdf
0c8e4f54f2cd4ea1f9d6309c9a7ce77e3304f39028c2ebe7efc0fe7f41341d0b

4.筛选-基线检验报告单/31001-基线血常规.pdf
3baf84ced110a071c8c41d3c42088906330c9445f325cb162ce0ac2487cd1d92

4.筛选-基线检验报告单/31001筛选期检查报告单.pdf
13d5eb1104b06f7fee7c58066081060e1f217a48bdea5aa1689e035174029b28

4.筛选-基线检验报告单/乙肝DNA-31001.pdf
b31d4536ac16a0e70bfbfb3180d7ed75cb61f27a3f50735842854caed355d194

5.入组审核过程及结果邮件、中心监查员-医学沟通记录或截图（如有）、Q&A记录（如有）/邮件.pdf
4ccfa3ca66a4d3fc36efa361fc86c0603bf6466c8dcd393a680d45b2e51d3b0c
```

### Official protocol and subject chain

Formal API verification returned:

- Project: `draft-project-09b593a721e7`
- Protocol: `MG-K10-SAR-001`
- Official version: `draft-version-09b593a721e7`
- Official version: `V2.1`, dated `2025-09-19`
- Protocol SHA256: `075c93b45414dcb4bb33ef1cf623d295a9d8f029d7560ca484a0c0267c4fdabd`
- Rule count: 23
- Subject: `31001`
- Subject ID: `0675cabcc979452dbdd5f5c1570c36d8`
- Center: `31 河北省中医院`
- API subject demographic fields remained unset for sex and age; no demographic inference was introduced.

Review episodes:

- Screening: `59b98368e962465ca5d62ff55b4da07d`
- Run-in: `f9548673569b48a499e0f52dfc574f8b`
- Baseline: `746385aba80c421ab83aaf439e084b7f`

The protocol draft contained 124 evidence-requirement drafts. Relevant workflow due counts were:

- Screening: 48 requirements
- Run-in: 29 requirements
- Baseline: 47 requirements

One protocol item remained unresolved: `EX13_CALENDAR_WINDOW_VARIANT`, source reference `da944f6e2a504694bbfbc888fa44d184-snapshot::body.p615`. This is a protocol-level unresolved item, not a basis for an eligibility conclusion.

### Evidence-processing closure

Screening snapshot:

- Snapshot ID: `2685d8e0c0a948ff83a13cb7952eb915`
- Five source files were placed in the screening full snapshot.
- Baseline and run-in latest snapshots remained null.
- Candidate: `cand-0afbef380e5944dbbc296f10a58d1ef5`
- Complete revision: `complete-54ece1166a924583ba76d2d709058d5f`
- Upload job: `d55611301d6147abaefbd40ab59b6077`
- Candidate build job: `514ab32f02544a86b1ae923ac964e541`

Final processing state observed:

- Snapshot status: `ready`
- Candidate status: `ready`
- Complete revision status: `ready`
- Complete revision: `is_current=true`, `is_activatable=true`
- Pages: 24/24 succeeded
- Risk flags: 1,562 total
- Pending risk flags: 0
- Risk reviews: 1,562
- Locators: 1,562
- Corrections: 0
- All scope, page-closure, risk, correction, metadata, referenced, locator, and manifest gates passed.

Risk distribution:

```text
numeric_value       942
decimal_point       363
negation_polarity    94
date                 88
unit                 72
repeated_text         3
```

All 24 pages had complete risk-scan coverage. Every page retained raw OCR as effective text; effective text and hashes exactly matched raw OCR. All locators remained `source_layer=raw_ocr`, with source excerpts matching raw-text slices. Authenticity was `degraded` and bounding boxes were null.

This establishes processing and source-locator closure only. It does not establish fact publication or clinical acceptance.

### Source facts and original positioning

The following were independently checked against raw OCR and page images.

#### Timeline

- Medical record p1: perennial symptoms reportedly began in 2000; diagnosed SAR.
- Medical record p1: symptoms documented on `2025-04-05`.
- Medical record p1: visit on `2025-08-08 09:12`; male, age 51, DOB `1973-08-11`.
- Medical record p2: participant signed ICF on `2025-08-08 09:43`; investigator signed at `09:44`.
- Medical record p8: run-in began `2025-08-08`; mometasone nasal spray and diary instructions documented.
- Medical record p9: next visit planned for `2025-08-15`.
- Baseline CBC and HBV DNA: samples collected `2025-08-15 09:46`.
- Email p1: source assertion that final response was “可随机” on `2025-08-15`; this was preserved as an email assertion, not treated as a system enrollment decision.

Representative raw-text offsets, using the API’s JavaScript/UTF-16 string positions:

```text
Medical record p1:
  自2000年开始出现       78–88
  DOB phrase            148–163
  2025-04-05 symptoms   177–190

Medical record p4:
  2018.09.uk            504–514
  desloratadine dates   540–558
  montelukast dates     580–598

Medical record p8:
  run-in phrase          87–104

Medical record p9:
  next-visit phrase      41–60

HBV DNA p1:
  未检测到靶基因        169–195

Email:
  final 可随机          p1, 988–1005
  deleted 司普奇拜单抗  p2, 13–28
  司普奇拜症状缓解      p4, 11–19
  肝功能不全            p4, 369–374
  8/12 score timing     p4, 402–418
```

#### Medication exposures

Medical record p1/p4/p5 documents:

- 枸地氯雷他定: `8.8 mg QD`, beginning `2025-04-05` in the broad treatment history.
- 孟鲁司特: `10 mg QD`, beginning `2025-04-05` in the broad treatment history.
- Omalizumab: `300 mg SC once`, with historical use from `2018.09.uk`; another dose documented `2025-04-05`.
- 司普奇拜单抗: `600 mg SC once` on `2025-04-09`, `300 mg SC once` on `2025-06-04`.
- Inhaled budesonide: `2025-07-18` through `2025-07-23`.
- Mometasone nasal spray during run-in: each spray `200 µg`, single-nostril dose `100 µg`, daily, preferably morning.
- Concomitant medications for hypertension, hyperlipidemia, chronic gastritis, and herpes zoster were also documented.

The source record broadly states poor treatment effect. Email p2/p4 states that 司普奇拜单抗 relieved symptoms and was removed from the poor-response medication entry. These are conflicting source assertions and were not reconciled into eligibility or response facts.

#### Abnormal, borderline, and related evidence

Baseline CBC, `2025-08-15`:

- NEUT% `39.0`, below `40–75`
- BASO% `1.6`, above `0–1`
- NEUT# `1.58`, below `1.80–6.30`

Screening CBC/urine, `2025-08-08`:

- EOS% `9.1` high
- BASO% `1.3` high
- EOS# `0.55` high
- BASO# `0.08` high
- Urine vitamin C positive
- Urine mucus threads `788`, high

Screening chemistry/immunology, `2025-08-08`:

- ALT `57.8` high
- GGT `146` high
- TBIL `30.5` high
- DBIL `8.7` high
- IB `21.8` high
- 5’-NT `15.1` high

Infectious/HBV evidence:

- HBsAg negative
- HBeAg negative
- Anti-HBe positive
- Anti-HBc positive
- Anti-TP, HIV, and HCV negative
- HBV DNA on `2025-08-15`: “未检测到靶基因”; lower quantification limit and detection-limit explanation were present.

Allergen testing included positive results for ragweed, dust mite, cat, cockroach, dog, mugwort, humulus, and goosefoot. Mold mix was below the stated positivity threshold.

Other screening evidence:

- Nasal endoscopy: congestion, swelling, narrowed passages, sticky secretions, and bilateral inferior turbinate congestion.
- Lung function: physician opinion “肺功能正常”.
- Chest X-ray: no clear abnormality.
- Symptom scores included iTNSS total 12, rTNSS 12, rTOSS 4, and iTOSS 3.

Handwritten sticky-note annotations were visible on original images but absent from OCR. Examples included apparent `CS 与研究疾病相关` on allergen/CBC pages, `NCS` on the baseline CBC and urine areas, and liver-related CS annotations on the chemistry page. These were retained as visual observations only and were not silently converted into structured facts.

#### Conflicting or unresolved evidence

- Broad record: treatment effect “not good”; email: 司普奇拜单抗 provided symptom relief and was deleted from the poor-response entry.
- Medical record denies severe herpes-related history; email documents herpes zoster from `2025-06-24` through `2025-07-25`, reported recovered. Severity and eligibility remain unresolved.
- Medical record lacks prior liver-function history; email says screening showed liver dysfunction and that history/scale information should be added. Chemistry abnormalities support the presence of abnormal liver-related evidence but do not determine eligibility.
- OCR contains inconsistent person-name strings. Center, subject code, and DOB align; names were not normalized.
- Age 51 on `2025-08-08` and age 52 on `2025-08-15` is temporally consistent with DOB `1973-08-11`, not treated as a conflict.
- Email references an enrollment review form, baseline RQLQ, run-in diary, and HBV-related attachment material. Those attachments were not among the five manifest PDFs.

## Artifacts And Evidence

Primary artifacts inspected:

- `context/phase5-sar31001-facts-profile-20260902_execution_context.md`
- `plans/codex_execution_phase5-sar31001-facts-profile-20260902.md`
- `context/phase5-sar31001-facts-profile-20260902_execution_route_manifest.json`
- `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/runtime-identity.json`
- `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/runtime/protocol-semantic-route-preflight.json`
- `artifacts/phase5-acceptance/20260901/manifests/sar-31001.json`
- `artifacts/phase5-acceptance/20260901/live-runs/sar31001-fresh-protocol/service-start.json`
- `artifacts/phase5-acceptance/20260901/SAR_R15_PREPUBLICATION_QC_20260902.md`

Formal API evidence:

- OpenAPI: `http://127.0.0.1:8910/openapi.json`
- Official protocol project/version endpoints
- Subject and review-episode endpoints
- Evidence snapshot, progress, candidate, processing revision, OCR page, image, profile-history, and fact-correction-history endpoints

Source document IDs:

```text
Medical record:
f55350a8cb5726dd2500151b6f3264fd310b1e3efd8c4dd80a893e65c4cd42c5

Baseline CBC:
1adad4efabfb9d5214b94860dc238798073ea864a23e00fff96c2e0ccfd72ba4

Screening report:
7462fdcc295840431f0d9ae270c4a82cf63420bfdbb1d1f52ada3b78972f007a

HBV DNA:
2479b1dd5ef6d0e5881d1d02b40a29b6dc95400e923824ffade741e1153384ba

Email:
6d65ceeedba213bfe06250008cb1e8f0161b8b5195d520e43a898e43dd3c0a50
```

Profile and correction history checks:

- Screening profile history: HTTP 200, `items: []`
- Run-in profile history: HTTP 200, `items: []`
- Baseline profile history: HTTP 200, `items: []`
- Fact-correction histories for all three episodes: HTTP 200, `items: []`

## Commands And Observations

Source hash verification:

```text
sha256sum artifacts/phase5-acceptance/20260901/isolated-inputs/sar/subjects/31001/31001/*/*.pdf
```

Observed output matched all five manifest SHA256 values listed above.

Regression tests:

```text
.venv/bin/pytest -q \
  tests/v2/domain/test_phase5_fact_contracts.py \
  tests/v2/domain/test_fact_candidate_gates.py \
  tests/v2/domain/test_fact_evidence_closure.py \
  tests/v2/domain/test_fact_normalization_planning.py \
  tests/v2/domain/test_patient_profile_contracts.py \
  tests/v2/projections/test_patient_profile_projection.py
```

Result:

```text
200 passed, 5 warnings in 6.48s
```

```text
.venv/bin/pytest -q \
  tests/v2/api/test_fact_normalization_registration.py \
  tests/v2/api/test_fact_normalization.py \
  tests/v2/api/test_patient_profiles.py \
  tests/v2/api/test_fact_corrections.py
```

Result:

```text
39 passed, 5 warnings in 46.37s
```

```text
.venv/bin/pytest -q \
  tests/v2/protocols/test_protocol_control_anti_overfit.py \
  tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py \
  tests/v2/protocols/test_adaptive_batch_budget.py
```

Result:

```text
39 passed, 5 warnings in 0.84s
```

```text
.venv/bin/pytest -q \
  tests/v2/services/test_fact_normalization_source_adapter.py \
  tests/v2/services/test_fact_normalization_executor_profile.py \
  tests/v2/services/test_fact_normalization_persistence.py \
  tests/v2/services/test_fact_normalization_command_service.py \
  tests/v2/services/test_patient_profile_service.py \
  tests/v2/services/test_fact_publication_service.py
```

Result:

```text
79 passed, 5 warnings in 43.32s
```

Warnings were deprecation warnings from Swig-related dependencies; no test failures occurred.

Additional observations:

- All 24 original page image endpoints returned HTTP 200 with `image_available=true`.
- Recomputed raw-text SHA256 values matched all API-reported page hashes.
- Complete-revision page audits found no raw/effective text divergence, selected corrections, unreviewed risks, locator mismatches, or out-of-range excerpts.
- No code or test files were modified.

## Blockers Or Missing Environment

1. **Fact/profile stage is absent.** No published facts, medication exposures, events, or Patient Profile revisions exist for screening, run-in, or baseline. Evidence-processing readiness must not be reported as Phase 5 fact/profile completion.
2. **Node allocation is incomplete or mis-scoped.** All five PDFs are currently in the screening full snapshot; baseline and run-in snapshots are null. This prevents authoritative node-specific normalization.
3. **Referenced source material is missing.** The email references the enrollment review form, baseline RQLQ, run-in diary, and HBV attachment material, but those files are absent from the source manifest.
4. **Metadata requires confirmation.** All five evidence members are auto-suggested with source party `研究中心（待确认）`; HBV DNA and email are typed as `其他资料（待确认）`.
5. **Visual annotations are not OCR facts.** Sticky-note CS/NCS markings require explicit visual review and provenance if they are to affect structured facts.
6. **Clinical/source conflicts remain unresolved.** Treatment response, herpes-zoster history/severity, abnormal liver function, and timing/compliance statements require source-aware adjudication. No eligibility conclusion was made.
7. **Original locators are text-based.** Locator authenticity is `degraded` with null bounding boxes. This is adequate for raw-text closure but not equivalent to pixel-level clinical acceptance.
8. **Protocol ambiguity remains.** `EX13_CALENDAR_WINDOW_VARIANT` is unresolved in the protocol draft.

## Rerun Requests Or Next Step

Codex should:

1. Confirm authoritative screening, run-in, and baseline snapshot allocation before normalization.
2. Import or explicitly account for the missing enrollment review form, baseline RQLQ, run-in diary, and HBV attachments.
3. Confirm evidence member metadata and source-party attribution.
4. Visually verify handwritten annotations and the ambiguous ECG OCR before creating any structured clinical fact.
5. Resolve or explicitly preserve conflicting source assertions; do not collapse them into a single eligibility value.
6. Run official fact normalization separately for the intended active node revisions only after the evidence prerequisites are satisfied.
7. Inspect resulting fact, event, exposure, and Patient Profile records for source-locator linkage and modality fidelity.
8. Keep `claims_complete=false` until all required nodes and authoritative evidence are closed.
9. Re-run the targeted regression suites after publication-path execution.
