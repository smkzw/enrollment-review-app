I'll start from the assigned conference context and Codex plan, then independently audit the Phase 5 sources before writing findings.I'll now audit the architecture, PRD, contracts, and Phase 4/Profile code against the four review questions.The PRD and design are loaded. Next I’ll inspect contracts, storage identity, Phase 4 runtime, and the Profile frontend for identity-chain and provenance defects.The identity-chain mismatch is confirmed. I'll inspect Phase 4 processing revisions, ClinicalFact field gaps, jobs, and the Profile frontend next.I have enough contract and identity-chain evidence. Next I’ll check one repository write path so the highest-impact defect is sourced, then return the full conference report.# Conference Participant Output: phase5-clinical-facts-profile-planning - general_grok46

## Boundary Check

- Role: `general_grok46` / Grok Build `grok-4.6`. Conference mode: `parallel`. One bounded pass.
- Working directory only. No production paths. No file writes. No sibling outputs. Report is returned here for the runner to persist.
- Did not read home `AGENTS.md` / `SOUL.md`. Did not read other participant outputs. Did not read raw clinical material outside this worktree.
- Tools used for evidence, not for edits. No browser/visual/PPT acceptance attempted; Codex remains final authority.
- Additional reads beyond the initial packet were limited to the named source-of-truth files and in-tree contracts/storage/frontend needed to audit identity, Gate/Job graph, and Profile UX.

## Independent Work Product

### Independent audit of the assignment

**Goal:** Stop Phase 5 at a source-linked, replayable, incrementally recomputable fact base plus Chinese Patient Profile. Do not emit eligibility decisions, ActionRequests, or washout conclusions.

**Highest-impact defect (must-fix before any Agent prompt or Profile write path):** the current Phase 5 placeholder stack cannot bind to Phase 4 authority. If implementation proceeds on existing contracts/tables, the system can publish facts from a stale Phase 2 snapshot, ignore complete processing revisions/corrections, and attach locators that Phase 4 already replaced.

This is not a naming cleanup. It is the exact failure mode in the success criteria: *publish facts from a stale evidence revision* and *lose source location authenticity*.

### Findings by severity

#### S0 — Identity chain is still Phase 2; writing it would publish stale facts

**Evidence**

- Review episode current authority is the paired pointer `active_evidence_snapshot_id` + `active_evidence_processing_revision_id` to `evidence_snapshots_v2` and `evidence_processing_revisions` (`app/storage/models.py` ReviewEpisodeRecord, constraint `ck_review_episodes_active_pointers_paired`).
- Phase 4 locators live in `EvidenceLocatorArtifact` / `processing_revision_locators`, with authenticity, sidecar, effective-text hash, and processing revision (`app/domain/contracts/evidence_locator.py`).
- Phase 5 placeholder write path still FKs to old tables:
  - `ClinicalFactRecord.evidence_snapshot_id` → `evidence_snapshots`
  - `EvidenceSpanRecord.source_document_version_id` → `source_document_versions`
  - `EvidenceNormalizationCandidateRecord.evidence_snapshot_id` → `evidence_snapshots`
  - `AgentCallRecord.evidence_snapshot_id` → `evidence_snapshots`
  - `ReviewRunRecord.evidence_snapshot_id` → `evidence_snapshots`
- `ClinicalFact`, `EvidenceNormalizationCandidate`, and `PatientProfile` contracts have **no** `complete_processing_revision_id`. `PatientProfile` has no snapshot id at all.
- `EvidenceNormalizationCandidate.validate_evidence_scope` only compares four Phase 2 ids on facts; it does not check events, exposures, spans, conflicts, or processing revision.
- NODE_CONTRACTS §4.1 still authorizes “raw OCRPage + existing EvidenceSpan or text to locate”, not “Phase 4 effective text + authenticated locator_ids of the active complete revision”.

**Inference**

A Normalizer/Gate that accepts these contracts can emit “accepted” facts whose snapshot is not the episode’s active v2 snapshot, whose spans are not in the complete revision locator set, and whose text is pre-correction OCR. Later Phase 4 correction would not naturally stale those facts.

**Recommendation**

Create a Phase 5 write namespace (`clinical_facts_v2`, `clinical_events_v2`, `medication_exposures_v2`, `conflict_groups_v2`, `evidence_expectations_v2`, `patient_profiles_v2`, `fact_rule_links_v2`) whose mandatory identity is:

`project / subject / review_episode / protocol_version / rule_set_revision / evidence_snapshot_v2 / complete_processing_revision`

Freeze Phase 2 `clinical_facts` / `evidence_spans` / `patient_profiles` as read-only regression anchors. Do not migrate or mix them into a live Profile. Gate publication **must** prove:

1. Snapshot status is the episode’s current **active** v2 snapshot.
2. Processing revision is that episode’s current **active complete** revision (`revision_kind=complete`, `READY`, `is_activatable`, matching page manifest).
3. Every cited locator_id is in that revision’s `locator_ids` and `source_text_sha256` / excerpt matches effective text.
4. Candidate/failed/non-active revisions cannot publish.

**Reject:** any design that “repoints” existing Phase 2 FKs in place, or treats `evidence_snapshot_id` as sufficient without the complete processing revision.

#### S0 — Candidate type is the published fact type; Agent can write the truth object

**Evidence**

- `EvidenceNormalizationCandidate.clinical_fact_candidates: list[ClinicalFact]` (`normalization.py`).
- `ClinicalFact` is the same class stored by `CLINICAL_FACT_CONFIG` (`repositories.py`).
- PRD P5-R02: Agent may write only candidates and unresolved items, never accepted facts, conflict rulings, expectation finals, or eligibility conclusions.
- Design §7.0: Evidence Normalizer write scope is **candidate only**.
- `ClinicalFact.certainty: float` exists on the publishable object. Project instructions forbid substituting model confidence for evidence or Gate.

**Inference**

If Gate “accepts” the Agent object by identity, publication is a trust-the-model copy. Certainty can become a silent filter. Conflicts can be pre-grouped by the Agent. This is how silence becomes a negated fact and how contradictions get a winner.

**Recommendation**

Split types:

| Agent writes | Gate/publish writes |
|---|---|
| `ClinicalFactCandidate` | `ClinicalFact` (new id, gate_result_id, input hash, processing revision) |
| `ClinicalEventCandidate` | `ClinicalEvent` |
| `MedicationExposureCandidate` | `MedicationExposure` |
| `ReferencedDocumentCandidate` | `ReferencedDocument` |
| unresolved items, coverage, uncertainty codes | `GateResult`, rejected-candidate log, `EvidenceExpectation` |

Gate **copies allowed fields after proof**, never promotes the candidate row. `certainty` stays on the candidate as a quality audit field and **must not** be a publication or first-screen threshold.

Also missing as first-class published entities: `ClinicalEvent` and `MedicationExposure`. They exist only as candidate stubs and as `PatientProfileEvent` projection. If Profile events are the only store, Phase 6 cannot cite events independently, and incremental recompute has no grain.

#### S0 — Locator duality: Agent-invented `EvidenceSpan` vs Phase 4 authenticated locators

**Evidence**

- Phase 0.5 `EvidenceSpan` allows Agent-proposed bbox/text_range/page_excerpt/page_only (`evidence.py`).
- Phase 4 `EvidenceLocatorArtifact` forbids bbox unless authenticity + sidecar + occurrence character range pass; text-only routes cannot carry bbox.
- PRD P5-AC02 / P5-AC10: no fake red box; fabricated span is a hard failure, not an empty successful Profile.
- Frontend `ProfileEventRow` deep-links to `/workbench?episode&component&evidence` (eligibility workbench), not to the Phase 4 source viewer.

**Inference**

If Phase 5 lets the Normalizer emit new spans, it reopens the fabrication path Phase 4 closed. If Profile opens workbench rather than the authenticated page image, the medical monitor cannot actually replay source in ≤3 clicks on the live evidence stack.

**Recommendation**

Normalizer input is the complete revision’s **effective text + existing locator_ids**. Primary citation is `locator_id`. New span proposals are allowed only as a residual, and `EvidenceSpanLocatorGate` must prove them against Phase 4 sidecar/effective text; otherwise reject the candidate and record `unresolved_item`, do not publish. Profile evidence click opens the Phase 4 file/page/locator surface. Workbench linkage is Phase 6.

#### S1 — Silence can still become a negative fact; polarity is not proven from excerpt

**Evidence**

- Polarity gate on `ClinicalFact` only: unknown cannot carry value; affirmed/negated must carry a typed value (`evidence.py`).
- NODE_CONTRACTS §4.2 says “完全未提及” may not produce a negated fact, but there is no excerpt-negation proof, no assertion-basis field, and no distinction between “既往史无特殊” (documented negation) and a blank history section (silence).
- `EvidenceExpectation` correctly separates `absent` vs `observed` vs `observed_weak` vs `referenced_missing` vs `not_due`, but subject-level expectation rows are still the Phase 2 table with no processing revision.
- PRD P5-AC03: seed-set polarity errors must be 0.

**Recommendation**

Add `assertion_basis`: `explicit_statement | source_stated_flag | not_mentioned`. Publish `negated` only when the bound locator’s effective text contains an explicit negation of the asserted object (not of a neighboring clause). `not_mentioned` and coverage holes create `EvidenceExpectation` only. Blank templates, unchecked boxes without a recorded “无”, and missing pages are gaps, never `polarity=negated` of “disease absent” or “lab normal”.

Gate test seed (deterministic, no clinical corpus required):

1. Excerpt “否认肝炎病史” → affirmed object “肝炎病史” with `polarity=negated`, basis=explicit.
2. History section present but silent on hepatitis → no hepatitis fact; expectation `absent` or `description_insufficient`.
3. Missing lab page in manifest → expectation `referenced_missing` or `required_procedure_not_done`, never “正常”.

#### S1 — DateValue cannot carry the PRD’s bounds / time kinds; candidate dates are raw strings

**Evidence**

- `DateValue` is `{value, precision, source_text}`. Known precision **requires** a canonical `date` (`common.py`). Year precision therefore stores some calendar day.
- Bounds exist only in Phase 6 evaluator `_date_bounds()` and only when `allow_partial=True` (`expression.py`). They are not stored on the fact.
- `ClinicalFact` has a single `effective_date`. No event time, interval start/end, record time, upload time, or episode anchor.
- `ClinicalEventCandidate` uses `event_date_lower/upper: str | None`. `MedicationExposureCandidate` uses `start_date_lower` / `end_date_upper: str | None`, no duration status, no unit, no source type, no original-name vs class split.
- PRD P5-R04 / P5-AC05: do not substitute screening/operation date for a missing date; do not infer stop date from “既往”.

**Inference**

UI and later time-window code can treat `2023-01-01 (精度：年)` as an exact day. Exposure “ongoing” can be stored as an invented end date. Washout “decidable range” then becomes a false exact interval.

**Recommendation**

Persist, do not just compute later:

- `DateInstant { source_text, precision, lower, upper }` with `lower/upper` derived deterministically from precision (year → Jan 1–Dec 31 of that year; month → first–last day; day → equal bounds; unknown → null bounds and no invented value).
- On facts/events/exposures: `event_start`, `event_end`, `record_time`, `upload_time`, `episode_anchor_id` as separate fields.
- Duration status enum: `ongoing | ended | intermittent | single | unknown`. “既往” ≠ ended.
- Phase 5 may compute **decidable interval for later washout**, and must not emit `washout_met`.

Implementation-plan item 6 is acceptable only as interval publication, not as elution judgment.

#### S1 — ConflictGroup cannot exist without rules; duplicate identity is unspecified; `resolved` is writable

**Evidence**

- `ConflictGroup.fact_ids` min 2, `affected_rule_component_ids` **min 1**, `resolved: bool = False`, resolution spans optional (`evidence.py`).
- No `FactRuleLink` contract or table exists (only named in design §4.3).
- Duplicate merge is prose only (“稳定内容身份”).
- Frontend first-screen conflict filter requires risk label `"来源冲突"` (`ProfileFilters.tsx`). Unlabelled conflicts disappear from the default view.
- PRD: do not auto-pick a winner; keep all locators; unresolved unless a recorded correction changes the source.

**Recommendation**

- Conflict is a fact-layer object. `affected_rule_component_ids` must be **optional / derived from FactRuleLink after indexing**, not a create-time requirement.
- `resolved` may be true only when a Phase 4 correction or recorded fact amendment changed a source; Gate sets it, Agent cannot.
- Duplicate key (deterministic): `subject + episode + processing_revision + fact_type + polarity + canonical(value, unit) + date_bounds`. **Exclude** span ids. Merge union of locator_ids. If polarity/value/date-bounds/duration disagree → `ConflictGroup`, never merge.
- First-screen conflict set is projection-owned (`highlighted_event_ids` / conflict lane), not a client label heuristic.

#### S1 — Source strength does not exist in the fact model; weak transcription can be published as peer truth

**Evidence**

- No `SourceStrength` enum. `required_source_types` exists on requirements/templates, not on facts.
- PRD P5-R05 / P5-AC04: screening-record transcription of long-term positive history is a **weaker current fact** plus strengthened provenance reminder; contemporaneous original history sits beside it; do not overwrite.
- Expectation matrix already allows `OBSERVED` + `PROVENANCE_FOLLOWUP` and `OBSERVED_WEAK` + provenance/OCR/historical-source gaps (`evidence.py`). That is the right dual-status, but nothing maps source strength into it.

**Recommendation**

Enum, Gate-assigned from document_type/source_party metadata (Phase 4 metadata revision), **not** from Agent:

`contemporaneous_objective | historical_original | current_study_record | screening_transcription | unverified`

Strength never mutates the value. It drives coverage (`observed` vs `observed_weak`) and the reminder. Same semantic object from transcription + original → conflict or dual sources in one group, original does not delete transcription.

Do not mark coverage `absent` when a weaker source already supports a current fact the rule also wants a higher-grade source for. That is the “同时误报证据不足” case in P5-R07.

#### S1 — AgentCall/Job graph currently requires ReviewRun and old snapshot; whole-subject Agent is the likely slice

**Evidence**

- Subject AgentCall validator requires `review_run_id` + `evidence_snapshot_id` (`agents.py`). Those FKs point at Phase 2/6 tables.
- NODE_CONTRACTS idempotency string includes `review_run_id`.
- Phase 4 already has persistent jobs, checkpoints, leases, idempotency (`job_service`, `workflow/runner`, `EVIDENCE_PROCESSING_JOB_TYPE`).
- NODE_CONTRACTS §4.1 allows “a declared file/page range” but does not force per-document coverage against the complete revision manifest.
- P5-AC10: empty output, missed whole page, fabricated span, cross-episode cite = explicit failure, not a successful empty Profile.

**Inference**

Creating a Phase 6 `ReviewRun` just to call the Normalizer contaminates assessment history and rebinds old snapshots. One subject-level LLM call will drop pages or invent spans.

**Recommendation — job graph (dependency order)**

1. **Activation lock:** read episode active `(snapshot_v2, complete_revision)`; refuse if unpaired or not complete.
2. **Slice:** one Normalizer AgentCall per **logical document** (not whole subject, not isolated line). Input = that document’s ordered pages of effective text + locator_ids + metadata + due `EvidenceExpectationTemplate` fact_types (as index hints only).
3. **Coverage Gate:** `coverage.processed_refs` must equal the slice’s page manifest; missing page without `unresolved_item` fails the call.
4. **Span Gate:** every citation ∈ complete revision locators; excerpt hash = effective text; OCR-risk pages block **affected** candidates only (not the whole document).
5. **Field Gate:** polarity basis, units, date bounds, source strength, no invented anchors.
6. **Cross-document merge Gate:** duplicates/conflicts; Agent does not merge across documents.
7. **Publish** immutable facts/events/exposures/conflicts with `gate_result_id` + input hash.
8. **FactRuleLink** deterministic exact `fact_type` ↔ published `EvidenceRequirement` / `RuleComponent`. No fuzzy text.
9. **Expectation projection** from templates + published facts.
10. **Profile projection** new revision; mark previous Profile stale; never overwrite.

Idempotency key must include `complete_processing_revision_id + prompt_version + model_config + document_slice_hash`. Do **not** require `review_run_id`. Introduce `FactNormalizationRun` (or reuse Job + ProjectionRevision) as the Phase 5 run identity.

Reuse the Phase 4 job runner. Reject new orchestrators, vector DBs, and graph DBs.

OCR risk: unreviewed critical OCR on a decimal/negation/unit blocks **those** candidates; other pages in the same document may still publish. Failed candidates must not replace the last good Profile.

#### S2 — First-screen Profile will drown a time-poor monitor; several Phase 6/7 leaks are already in the shell

**Evidence**

- Design §8.4: click shows related rules, **risk, actions**, and source. Actions are Phase 7. Eligibility main status is Phase 6.
- `SubjectsPage` header renders `MainStatusBadge` (episode eligibility rollup) and stale copy “当前审核结果需要重新核对”.
- Default first screen = client `isRiskEvent`: any `relatedRuleComponentIds` counts as “入排相关” (`ProfileFilters.tsx`). A complete FactRuleLink index would put almost every fact on the first screen.
- `highlighted_event_ids` is mapped then unused; the client recomputes the set.
- Filters have no “弱来源”. Weak transcription therefore hides unless also labelled enrollment/abnormal.
- `is_abnormal` / `is_critical` / `has_trend_change` are booleans on `PatientProfileEvent` with no owner. If Agent sets them, first screen becomes a hidden judgment. If protocol thresholds set them, Phase 6 leaks into Phase 5.
- Evidence click → `/workbench`. Catalog/evidence already have HTTP repositories; Profile still `getDefaultRepository()` stub (`frontend/src/api/index.ts`).
- Prototype banner still says 合成示例数据.
- 13 lanes exist and are ordered correctly. ExpectationCoverage already distinguishes the five statuses and states that unseen ≠ denied. Keep that.

**Recommendation — information hierarchy**

Server-projected `highlighted_event_ids` is the first screen. Client filters only narrow that set. Definition of highlight, **not** “has any rule link”:

1. Unresolved conflicts.
2. Currently due expectation gaps (`absent`, `referenced_missing`, due `observed_weak`).
3. Weak-source current positive long-term history + provenance reminder.
4. Source-stated abnormal/critical flags or value vs **that report’s own reference range** (not protocol 3×ULN).
5. Serial same-analyte trend that crosses the source reference range.
6. OCR/parse-risk rejected or down-ranked candidates in current scope.

“全部历时信息” shows all 13 lanes, empty lanes included (“本主题当前资料未见记录”, never “正常”). Header shows demographics, disease/course, episode, anchors, **snapshot + complete revision identity**, Profile generated-at, pending-check count. Do **not** show eligibility main status, Action counts, Agent/schema/pipeline words.

Abnormal/critical/trend are **deterministic projection flags** from source-stated fields or serial values. They are not eligibility verdicts.

500-fact 1080P/2K/4K: lane virtualization, no page-level horizontal scroll, desktop-only. Visual proof is a tester/Codex job, not this conference.

#### S2 — Implementation-plan and design text smuggle Phase 6/7 into Phase 5

**Evidence**

- Implementation plan Phase 5 work item 5: “与规则和 **Action** 双向链接”.
- Design §8.4 event click includes **行动**.
- NODE_CONTRACTS §4.3 “不形成明确临床判断” is correct, but §2.2 idempotency still assumes `review_run_id` for all subject nodes.

**Recommendation for the chair**

Must-revise those sentences: Phase 5 links facts ↔ requirements/components and stores structured gaps. It does **not** create, close, or display ActionRequests. Washout/threshold/AND-OR stay in Phase 6.

### Must revise / defer / reject (for chair synthesis)

**Must revise in `prd.md` / forthcoming `design.md` / `implement.md`**

1. Identity: active `evidence_snapshots_v2` + complete processing revision on every published object and every AgentCall.
2. New v2 tables; old fact/span/profile tables remain untouched regression anchors.
3. Split candidate vs published types; first-class Event/Exposure tables; FactRuleLink table.
4. Cite Phase 4 `locator_id`; do not let Agent bbox become the authenticity source.
5. Assertion basis + excerpt proof for negation; silence → expectation only.
6. Persist date bounds and time kinds; duration status; no invented end/anchor.
7. SourceStrength enum; transcription remains weaker, never overwrites original.
8. Conflict without mandatory rule ids; no Agent resolve; duplicate key specified.
9. Job graph: per-document Normalizer → coverage/span/field/merge gates → publish → index → expectation → profile revision. `FactNormalizationRun`, not `ReviewRun`.
10. First screen = server highlight set defined above; Profile evidence opens Phase 4 viewer; no eligibility badge on Phase 5 Profile.
11. Strike Action bidirectional links and washout conclusions from Phase 5 plan text.
12. OCR-risk blocks affected candidates only; failed run must not clobber last good Profile.

**Defer (explicitly out of this phase, keep hooks only)**

- Eligibility Assessor, Critic, component status, ActionRequest, report export, bulk review.
- Protocol-relative lab thresholds (3×ULN etc.) as Profile “abnormal”.
- Unit conversion beyond exact-label match; new facts from a versioned unit step later.
- Fuzzy fact-to-rule linking.
- Large-scale D001 / MG-K10-SAR medical accuracy (Phase 8). Phase 5 representative check on **isolated copies** only, by testers, not this conference.
- 1080P/2K/4K visual UAT and real-browser monitor trial (P5-AC13 tester route).
- Manual fact amendment UI beyond the data model (reason, scope, new revision); if in Phase 5, keep it after publish-path exists.

**Reject**

- Vector DB, knowledge graph, generic Agent framework.
- Promoting Agent `ClinicalFact` rows to truth.
- Auto-resolve conflicts or “latest document wins”.
- Fabricating negatives from silence / missing pages / unmentioned items.
- Fake bbox from model-reported coordinates.
- Mixing Phase 2 placeholder facts into live Profile.
- Using `certainty` as a clinical or publication threshold.
- Creating Phase 6 ReviewRuns solely to satisfy Normalizer AgentCall.
- Mobile/narrow layouts; login/multi-user; legacy project writeback; project-specific hardcoded clinical fixes.
- Empty Profile returned as success after Agent failure.

### Dependency-ordered slice plan (implementable, still inside Phase 5)

| Slice | Outcome | Exit proof (non-visual) |
|---|---|---|
| 5.0 Identity freeze | v2 tables + FK to snapshot_v2 + complete revision; old tables read-only; write-path tests refuse unpaired/non-active/legacy ids | Contract + migration tests |
| 5.1 Candidate schema | Split candidate/published; DateInstant; SourceStrength; assertion_basis; Event/Exposure published types | Schema tests; Agent cannot insert published tables |
| 5.2 Locator Gate | Citations must be complete-revision locator_ids; excerpt hash; no fake bbox; cross-episode fail | Fixture locators, no raw clinical files |
| 5.3 Polarity/silence Gate | Seeded negation vs silence vs missing page | P5-AC03 seed, polarity errors = 0 |
| 5.4 Duplicate/conflict Gate | Specified merge key; unresolved group; all locators kept | P5-AC06 |
| 5.5 Per-document Job | Persistent job, checkpoint, idempotency including processing revision, coverage vs manifest, OCR-risk scoped reject, last Profile preserved | P5-AC10/11 |
| 5.6 Publish + FactRuleLink | Exact fact_type match only; bidirectional query; rebuildable | Index rebuild test |
| 5.7 Expectation projection | Five statuses not collapsed; weak + provenance dual-status | P5-AC07 |
| 5.8 Profile projection + HTTP | Runtime decode; stub fixtures remain test-only; first-screen server set; 13 lanes; event vs record time; conflict side-by-side; evidence → Phase 4 viewer | API contract tests; frontend mapper tests |
| 5.9 Incremental stale | Correction/upload/amendment → affected recompute, new Profile revision, old episode replayable | P5-AC08 |
| 5.10 Isolated representative check | Tester/Codex on isolated copies; conference does not substitute | P5-AC12/13 evidence-chain split |

Do not start 5.5 Agent prompts before 5.0–5.4 gates exist. An Agent without those gates will generate un-auditable facts.

### Required tests (chair should put into design/implement)

- Activation: non-complete, candidate snapshot, unpaired pointer, wrong episode → no publish.
- Locator: fabricated span, wrong page, bbox without sidecar, excerpt mismatch, cross-episode id → fail call, no Profile success.
- Polarity seeds above; “未提及” ≠ negated.
- Year/month bounds stored and displayed as ranges; screening date not copied into missing MH date; “既往” not ended.
- Duplicate same value different pages → one fact, two locators. Different values → conflict, `resolved=false`.
- Transcription + original → both visible; coverage `observed_weak` + provenance, not `absent`.
- Idempotent rerun same revision/prompt/model/slice → same facts. New correction revision → new facts + stale old Profile.
- Kill browser mid-job → resume from checkpoint; no duplicate facts.
- Runtime JSON with extra fields / missing processing revision → HTTP decode reject.
- Frontend: fixture repository still used only in isolated tests after HTTP lands.

## Evidence And Assumptions

### Evidence (observed in-tree)

1. Conference context and Codex plan: Phase 5 in-scope; Phase 6/7 out; four review questions; identity mismatch already flagged.
2. PRD P5-R01–R09 and AC01–AC13: authority chain, silence≠negation, source strength, date kinds, conflicts, expectations, Profile, jobs, isolated copies, conference≠tester.
3. Design §4.3 / §7.0–7.2 / §8.4: Normalizer candidate-only; deterministic date/unit/duplicate/conflict gates; Profile lanes and first-screen intent; event vs record time.
4. Implementation plan Phase 5: includes Action linking and washout range — the former is a phase leak.
5. `ReviewEpisodeRecord` paired v2 pointers vs fact/span/candidate/profile/agent_call FKs to Phase 2 `evidence_snapshots` / `source_document_versions`.
6. `ClinicalFact` lacks processing revision, source strength, record time, assertion basis; uses `list[ClinicalFact]` as Agent output.
7. No published `ClinicalEvent` / `MedicationExposure` / `FactRuleLink` contracts or tables.
8. `DateValue` canonical date + precision only; bounds live in `expression.py` for eligibility, not on facts.
9. `ConflictGroup.affected_rule_component_ids` min_length=1; `resolved` unconstrained.
10. Phase 4 `CompleteEvidenceProcessingRevision` + `EvidenceLocatorArtifact` already implement authentic locators.
11. Frontend Profile is stub/fixture; `getDefaultRepository()`; first screen from client heuristics; evidence → workbench; header shows eligibility main status.
12. Evidence/catalog already have HTTP repositories; Profile does not.
13. Phase 4 job runner/idempotency/checkpoints exist and should be reused.

### Assumptions (provisional; Codex may override)

- A1. Per-document Normalizer slice is the default. Whole-subject calls are rejected unless a measured context budget proves otherwise.
- A2. Lab “abnormal/critical” on first screen is source-stated or vs the report’s own reference range, never protocol exclusion thresholds.
- A3. `FactNormalizationRun` can be a new small identity; we should not overload `ReviewRun`.
- A4. Isolated D001 / MG-K10-SAR copies for AC12 are an implementation/tester concern; this pass does not inspect those files.
- A5. `schema_version = fixture/v1` remains until Phase 5 publish contracts version; runtime decode still rejects drift.

### Inference

If 5.0–5.4 are skipped, later slices cannot satisfy AC01/AC02/AC03/AC10. The PRD’s product intent is mostly right; the **placeholder contracts and plan text are not**. The dangerous designs are: same-type candidate promotion, Phase 2 FKs, Agent-invented spans, first-screen = any rule link, and Action/ReviewRun leakage.

### Uncertainty (does not block the must-fix list)

- Exact document-slice token budget for the chosen model.
- Whether manual fact amendment UI is in 5.9 or a thin 5.x follow-on.
- Whether year-precision `DateValue.value` is currently always day=1 in fixtures (bounds should be stored regardless).
- Real-browser 500-fact layout behavior — unverified here by assignment.

## Risks, Gaps, And Verification Needs

| Risk | Why it matters | Verification (not this conference) |
|---|---|---|
| Stale-revision publication | Facts detach from corrections/effective text | Gate tests on active complete revision only |
| Silence → negated/normal | False eligibility inputs in Phase 6 | Polarity seed set AC03 |
| Hidden conflicts | Monitor sees one value | Conflict group + first-screen projection tests |
| Lost/fake location | Fake red box, failed replay | Locator authenticity vs Phase 4 sidecar |
| First screen = entire Profile | Time-poor monitor cannot work | Highlight-set unit tests; later 1080/2K/4K by testers |
| ReviewRun/Action leak | Phase 5 becomes a backdoor Phase 6 | Schema forbids Action write; AgentCall without review_run |
| Agent empty success | False “no findings” Profile | AC10: fail the job, keep prior Profile |
| Incremental miss | Conservative widen not specified | If affected scope unproven, recompute whole episode, still new revision |
| Representative check using live legacy projects | Violates read-only legacy rule | Isolated new-architecture copies only |

**Do not claim:** clinical accuracy on real subjects, regulatory adequacy, or visual acceptance. Those remain Codex/tester.

## Recommended Next Step

Chair should treat **S0 identity + candidate/published split + Phase 4 locator citation** as blocking revisions to `prd.md` and as the first sections of `design.md`. Do not authorize implementation slice 5.5 (live Normalizer) until 5.0–5.4 tests exist.

Safe provisional path if the questions below are not answered in-session: implement 5.0–5.4 and the job skeleton with a fake structured candidate fixture (no model). Keep old tables frozen. Keep Profile HTTP behind decode of the new identity. Do not generate Agent prompts against Phase 2 `ClinicalFact`.

### Most important objections

1. Current contracts would publish Phase 2-shaped facts and Agent-owned spans — this violates AC01/AC02/AC10 even if the PRD prose is correct.
2. First-screen “入排相关 = any FactRuleLink” plus eligibility badges/actions will not serve a senior monitor and pulls Phase 6/7 into Phase 5.
3. Implementation-plan “Action 双向链接” and design “点击显示行动” must be struck, not “implemented lightly”.

### Proposed solutions

- New v2 fact/event/exposure/conflict/expectation/profile/link tables keyed by active complete processing revision.
- Candidate ≠ published; Gate copies after proof.
- Cite Phase 4 locator_ids; per-document job; coverage vs manifest.
- Server-owned first-screen highlight set; Profile evidence opens Phase 4 viewer.
- Structured gaps only; no ActionRequest, no washout verdict, no ReviewRun.

### Decision points for Codex

1. **Normalizer run identity:** new `FactNormalizationRun` bound to complete processing revision, **not** `ReviewRun`? (Provisional: yes.)
2. **Agent slice:** per logical document vs per page vs whole subject? (Provisional: per document.)
3. **First-screen “异常”:** source-stated / report reference range only, vs any protocol-relative flag? (Provisional: source-stated only.)
4. **Manual fact amendment:** in Phase 5 after 5.9, or data model only? (Provisional: model + Gate in 5.9, UI can be thin.)
5. **Profile header:** drop `MainStatusBadge` for Phase 5, or keep as a later-bound empty slot? (Provisional: drop until Phase 6.)

### Bounded questions for Codex

1. Confirm that `AgentCallContract` for `evidence_normalizer` will be revised to require `complete_processing_revision_id` and to drop mandatory `review_run_id`. This decides whether Phase 5 can reuse `agents.py` as-is (it cannot, if the answer is no).
2. Confirm duplicate-merge key may ignore span ids and must not include Agent `certainty`. Needed to write the conflict Gate without re-litigating merge semantics mid-implementation.
3. Confirm testers, not this conference, own AC12 isolated-copy walkthrough and AC13 browser trial, and that design.md should list the seed polarity/date/conflict fixtures rather than real protocol pages as the Phase 5 Gate acceptance set.

End of participant pass. No files modified. No final acceptance claimed.
