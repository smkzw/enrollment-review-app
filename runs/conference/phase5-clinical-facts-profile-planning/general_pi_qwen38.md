I have strong grounding across contracts, storage, Phase 4 authority chain, job runtime, and the frontend Profile surface. Producing the independent review.

# Conference Participant Output: phase5-clinical-facts-profile-planning - general_pi_qwen38

## Boundary Check

- Read-only conference. I made no file modifications and read no paths outside the worktree. Read set: `context/phase5-clinical-facts-profile-planning_context.md`, `prd.md`, `app/domain/contracts/{evidence,normalization,evidence_locator,enums,common}.py`, `app/storage/{models,repositories}.py`, `app/storage/migrations/versions/{0002,0008,0009,0010}.py`, Phase 4 services (`evidence_activation_service`, `evidence_revision_workflow`, `evidence_processing_executor`, `omlx_gate`, `protocol_workbench_service`), `app/workflow/{errors,jobstore}`, and `frontend/src/**` (Profile components, SubjectsPage, viewModels, mappers, api/stubRepository).
- No final clinical/visual/browser acceptance performed; that remains with Codex (P5-AC13 browser trial and 1080P/2K/4K verification).
- No new files created; no Trellis task state touched.

## Independent Work Product

I audited the plan against the actual code. The PRD's authority-chain, silence, conflict, and incremental-recompute goals are directionally right and largely achievable with existing machinery — but the current published contracts and the plan's implied data flow contain a set of concrete, must-fix gaps. Findings below are evidence-first; where I could not resolve a decision from repo context, I ask a bounded question of Codex.

### A. Domain / provenance / identity (highest impact)

**A1 — Published fact/event/exposure/expectation/profile contracts do not bind the complete processing revision. This is the P5-R01/P5-AC01 core and the current contracts fail it.**
- `ClinicalFact` (`evidence.py`) carries only `project_id, subject_id, review_episode_id, evidence_snapshot_id`. It has **no** `complete_processing_revision_id`, no `protocol_version_id`, no `rule_set_revision`, no `episode_revision`.
- `EvidenceNormalizationCandidate` (`normalization.py`) carries `protocol_version_id` but **no** `rule_set_revision` and **no** complete processing revision.
- `PatientProfile`/`PatientProfileEvent` carry only subject + review episode; `ConflictGroup` carries none of the authority chain.
- Phase 4 already models the correct pattern: `EvidenceActivationEvent` freezes `(from_snapshot, from_revision) -> (to_snapshot, to_revision)` pointer pairs plus `expected_revision`/`resulting_episode_revision`, and `FinalAssessmentRecord` binds `protocol_version_id + rule_set_id + rule_set_revision + evidence_snapshot_id + review_run_id + gate_result_id + publication_fingerprint`.
- **Concrete defect:** the same `evidence_snapshot` can yield multiple `complete` processing revisions (a correction over the same snapshot creates a new complete revision). A fact pinned to snapshot only cannot be replayed or verified against the revision that produced it; the P5-R03 gate "校验当前处理修订" is impossible to express. This is the "stale revision publishes a fact" and "later correction silently rewrites an earlier node's profile" family the conference must kill.
- **Remedy (recommended, pending Q1):** introduce **v2 published contracts** mirroring `FinalAssessmentRecord`'s identity surface — `ClinicalFactV2`, `ClinicalEventV2`, `MedicationExposureV2`, `ConflictGroupV2`, `EvidenceExpectationV2`, `EvidenceSpanV2`, `PatientProfileV2` — each carrying `protocol_version_id`, `rule_set_id`+`rule_set_revision`, `evidence_snapshot_id`, `complete_processing_revision_id`, and `episode_revision`. The gate resolves these from the episode's active pointer pair at normalization time and **re-reads the live active pointer at commit time**, rejecting on mismatch (same `expected_revision` semantics Phase 4 candidates already enforce). Do not reuse the Phase 0.5 fixture contracts for publication.

**A2 — There is no published `ClinicalEvent` or `MedicationExposure` contract at all; `MedicationExposureCandidate` is missing required fields.**
- Only `ClinicalEventCandidate` / `MedicationExposureCandidate` and the in-profile `PatientProfileEvent` exist. P5-R06 requires publishing accepted `ClinicalEvent` and `MedicationExposure`.
- `MedicationExposureCandidate` has `dose: str | None` (no `unit`), no `ongoing/end status`, no `source type` — yet P5-R02 requires 剂量、单位、频次、途径、起止日期范围、持续状态、来源类型. `ClinicalEventCandidate` has no `recorded_at`.
- **Remedy:** define v2 published event/exposure contracts carrying full P5-R02 fields, each with fact refs + span refs **provably in the same review episode and same complete revision** (P5-R06: "ClinicalEvent/MedicationExposure 的事实引用和证据引用必须属于同一审核节点与处理修订" — the current candidate contract has no field to assert this; add a gate check that every `evidence_span_ids` resolves into the frozen complete-revision closure).

**A3 — `DateValue` has no explicit deterministic lower/upper bounds.**
- `DateValue` = `value + precision + source_text` only. P5-R04/P5-AC05 requires year / year-month / day precision **and deterministic bounds** for disease duration and exposure windows, and "不猜缺失锚点." Bounds are today only implicit.
- **Remedy:** extend `DateValueV2` (or add a `DateRange`/bounds projection) with deterministic `lower_bound`/`upper_bound` derived from precision + value, plus boundary + property tests. State explicitly that a missing date part widens the bound, never is guessed to a day; and "既往"/"ongoing" never auto-supplies an end date. The existing Phase 4 `evidence_locator` has a `DateValue` type already used by correction/risk structures — reuse that shape rather than inventing a parallel one.

**A4 — Facts lack `source_strength`, and event time vs record time is not separable.**
- `ClinicalFact` has no source-strength field, though P5-R05 defines 5 levels (同期客观 / 既往原始 / 当前研究病历直接记录 / 筛选病历转述 / 无法确认来源) that drive coverage/provenance hints. `PatientProfileEvent` has only `start_date`/`end_date` — no `recorded_at`.
- **Remedy:** add `source_strength` to the v2 fact (deterministically derived from `document_type`/`source_party` + the bound `EvidenceExpectationTemplate.required_source_types`/`allows_screening_record_transcription`, never from model confidence) and a `recorded_at` on events/exposures, displayed separately from event time (P5-R08 "事件发生时间与记录时间分开").

**A5 — Legacy placeholder tables will contaminate reads unless physically quarantined.**
- Migration `0002` defines `clinical_facts`/`evidence_expectations`/`patient_profiles` with FKs to **v1** `evidence_snapshots`; Phase 4 uses `evidence_snapshots_v2`. The v1 FK target ids do not exist in v2, so an in-place remap would violate FKs and legacy rows have no v2 identity.
- **Remedy:** new v2 tables with FKs to `evidence_snapshots_v2` + `evidence_processing_revisions`; quarantine legacy tables (rename to `*_legacy` or exclude in the read path); add an acceptance assertion that the new Profile API returns **zero** rows referencing v1 snapshots (P5-AC01 "legacy 占位事实不混入").

### B. Agent / Gate / Job graph

**B1 — Normalizer must freeze an attempt closure and re-verify the active pointer at commit.**
- Phase 4 already solved the "queued correction silently absorbed" race via `ProcessingCandidateAttemptManifest` (metadata/risk/risk_review/correction/locator/referenced-doc/resolution revision id lists frozen at claim) and `EvidenceProcessingCandidate.candidate_input_sha256`. **Reuse this exact pattern** for the Normalizer job; do not design a new one. The job must also re-check the episode's active `(snapshot, complete_revision, episode_revision)` triple at publication, exactly as Phase 4 re-verifies `expected_revision`.
- **Do not build a new job framework.** `JobRecord`/`JobStepRecord`/`JobCheckpointRecord`/`JobEventRecord`, `IdempotencyRecordRow(scope,key)`, `PageWorkLease` with heartbeat + `commit_guard` + late-arrival rejection, `JobStore` claim/start_step/complete_step/`enter_user_wait`, backoff retries, and `on_cancelled` already cover P5-R09. Phase 5 adds a new job type + idempotency key = hash(snapshot, complete_revision, prompt_version, model_config, frozen input scope). This is the "不过度设计" answer.

**B2 — The "遗漏整页 / 虚构 Span / 空输出 / 跨节点引用" defenses need a deterministic page-coverage gate, not per-fact checks.**
- P5-AC10 lists these as explicit failures. Current `CoverageSummary` (processed/missing/duplicate refs) is a hook but not page-level.
- **Remedy:** at gate time (a) resolve every `evidence_span_ids` into the frozen complete-revision closure (locator/proof path + ocr page binding, which Phase 4's `CompleteEvidenceProcessingRevisionRepository._verify_locator_closure` already enforces); any id not in closure → reject candidate. (b) Require the union of referenced pages (or explicitly excluded pages) to equal the complete revision's page list → "遗漏整页" fails. (c) Verify span `anchor_hash` against the effective-text layer (Phase 4 `LocatorSourceLayer.EFFECTIVE_TEXT`). (d) Verify candidate scope equals frozen scope → cross-node reference fails. (e) Empty output or agent failure → job FAILED, never an empty Profile success (P5-AC10 "不以空 Profile 冒充成功"). (f) Blocking OCR risk unresolved → reject only the affected span scope and publish the rest with explicit rejected scope (P5-R03), never all-or-nothing and never touching the previous active profile.

**B3 — FactRuleLink must be exact-match-only.**
- Reject fuzzy-text similarity (P5-R06 "不能用自由文本模糊相似度把事实串到无关规则"). Link only to published `RuleComponent`/`EvidenceRequirement` by deterministic identity. Build the index as a rebuildable downstream structure; never write back into protocol authority tables.

### C. Clinical / UX for the senior monitor

**C1 — The risk-first first screen is sound but the "关键事件与风险" list can still overflow at 500 facts.** The existing `ProfileFilters` (7 filters) + `isRiskEvent` derivation + lane ordering are a good baseline. **Remedy:** add a hard cap/dedup on the risk list with an explicit "还有 N 项" escalation and per-filter count chips (so a time-poor monitor sees volume and priority without paging); make weak-source ("筛选病历转述") visually distinct with a provenance warning; keep the stale/version banner unmissable; deep-link evidence to the Phase 4 `OriginalEvidenceViewer` (real bbox → red box; `EvidenceLocatorView.bbox` is already `null` for non-bbox → no fake highlight, preserve this honesty).

**C2 — Negation vs silence must be a defined rule with tests.** The frontend already renders the crucial "资料中未见 ≠ 明确否认" note and separates "尚未见到" from "明确否认." The plan must make the backend projector produce, from one negated statement, a NEGATED fact **and** an OBSERVED/covered expectation with `PROVENANCE_FOLLOWUP` (not `ABSENT`); when the bound requirement demands a higher-grade historical source, add the provenance warning without double-reporting insufficiency (P5-AC07). Add tests for each of: 到期 / 未到期 / 较弱来源 / 病历已记载但需溯源 / 明确引用未提供 / 确实未完成检查 — never collapsed into a single "待补证."

**C3 — Contract drift between frontend and backend must be resolved to one source of truth.** The frontend `ProfileEventView` already has `evidenceRelation` ("direct"/"review_basis"/"related_rule"/"unavailable") and `evidenceTargetComponentId` that the backend `PatientProfileEvent` does **not** have. This is exactly the P5-R08 "运行时解码拒绝合同漂移" risk. **Remedy:** the v2 backend contract is authoritative; frontend mappers consume it; the fixture remains only for isolated frontend tests (P5-R08). Add a decode-drift rejection test on the HTTP boundary.

### D. What to reject / defer

- **Reject:** any vector/knowledge-graph DB or generic graph-orchestration framework (PRD already scopes out; SQLite relations + existing JobStore cover Phase 5).
- **Reject:** Fuzzy FactRuleLink; all-or-nothing candidate publication that could block unrelated facts or pollute the prior active profile.
- **Defer to Phase 6:** `ConflictGroup.resolved` as a decision state, ActionRequest creation, per-rule-component judgment. In Phase 5 conflicts stay side-by-side/open; `resolved` is only ever true when a **recorded `CorrectionRecord`** changes source text so one side vanishes — a source change, not a judgment.
- **Defer:** protocol-version display beyond current-node binding; multi-user/security (out of scope per PRD).

## Evidence And Assumptions

- `ClinicalFact` binds snapshot only; `EvidenceNormalizationCandidate` lacks rule_set_revision + complete revision — confirmed in `app/domain/contracts/evidence.py`, `normalization.py`.
- Phase 4 active-pair pattern: `EvidenceActivationEvent`, `EvidenceProcessingCandidate.candidate_input_sha256`, `ProcessingCandidateAttemptManifest`, `expected_revision` — confirmed in `evidence_locator.py`; `EpisodeRecord.active_evidence_snapshot_id`/`active_evidence_processing_revision_id` in `models.py`.
- `FinalAssessmentRecord` already models the full identity chain (protocol + rule_set/revision + snapshot + gate + fingerprint) — confirmed in migration `0002`.
- Job/lease/checkpoint/idempotency machinery exists and is production-used by Phase 4 (`jobstore`, `evidence_processing_executor`, `omlx_gate`, `PageWorkLeaseRepository`, `IdempotencyRecordRow`) — confirmed.
- `EnrollmentRepository.getProfile` is stub-only (`kind:"stub"`, `getDefaultRepository()` throws outside trial mode); no HTTP Profile API — confirmed in `frontend/src/api/stubRepository.ts`, `index.ts`.
- Frontend/backend contract drift on `evidenceRelation`/`evidenceTargetComponentId` — confirmed by comparing `ProfileEventView` (viewModels.ts) with `PatientProfileEvent` (evidence.py).
- Migration `0002` placeholder tables FK to v1 `evidence_snapshots` — confirmed.
- Inference (marked as such): rule_set revision for a node resolves from the episode's bound protocol version (same derivation `final_assessments` uses); I did not re-verify the exact episode→rule-set join but the pattern is established.

## Risks, Gaps, And Verification Needs

- **R1 (stale-revision publication / silent rewrite):** mitigated only by binding facts to the complete revision + episode revision and re-checking the live active pointer at commit. Needs an end-to-end test: activate rev A → normalize → correct → activate rev B → assert no rev-B fact appears under rev-A profile and rev-A replay is byte-stable.
- **R2 (negative-from-silence):** needs the polarity+expectation derivation rule and the five-state projection tests (P5-AC03/AC07).
- **R3 (page omission / hallucinated span):** needs the page-coverage gate and closure-resolution gate tests (P5-AC10).
- **R4 (partial-date bounds):** needs boundary/property tests asserting bounds widen with missing precision and no anchor guessing (P5-AC05).
- **R5 (legacy contamination):** needs the zero-legacy-read acceptance assertion (P5-AC01).
- **Verification need (Codex-owned):** P5-AC09 500-fact Profile at 1080P/2K/4K without horizontal scroll — must be driven in a real browser at all three resolutions with a seeded 500-fact profile; conference cannot accept visually. P5-AC13 browser monitor trial is Codex-owned (tester roles vs conference roles stay separate — plan correctly states this).

## Recommended Next Step

Adopt the dependency-ordered slice plan below, then Codex resolves Q1–Q4 before `design.md` converges.

1. **Slice 5.1 — Contracts + migration:** v2 published contracts/tables with full authority chain; quarantine legacy tables; identity validators + FK + zero-legacy tests.
2. **Slice 5.2 — Normalizer job:** active-closure slicing, attempt-manifest freeze, structured candidate schema (per-span + page coverage + unresolved OCR risk), persistent job on existing JobStore/lease/checkpoint; idempotency + page progress + cancellation + user-wait on blocking corrections; failure/pg-coverage/hallucinated-span/empty-output/cross-node tests.
3. **Slice 5.3 — Deterministic gate + publication:** schema/scope/active-pointer/revision/span-closure/anchor-hash/polarity/unit/date-bounds/source-strength/coverage checks; per-span partial acceptance with explicit rejected scope; transactional publish; mark prior profile stale; never overwrite.
4. **Slice 5.4 — Date/duration/exposure bounds + FactRuleLink index:** bounds engine + boundary/property tests; exact-match index + bidirectional query/reindex.
5. **Slice 5.5 — Expectation projector:** 5-state projection from bound template, due-anchor computation, negation-as-coverage rule, provenance follow-up; P5-AC03/AC07 tests.
6. **Slice 5.6 — Profile projection + HTTP API:** 13-lane v2 profile, risk/emphasis view, real HTTP endpoint with decode-drift rejection, frontend mappers consume v2 (fixture isolated), evidence deep-link to Phase 4 viewer, conflict side-by-side, weak-source warning, per-node stage labels, stale banner.
7. **Slice 5.7 — Incremental recompute + recovery:** span/doc/fact-scoped invalidation, conservative widening, old-node replay, no-forever-pending; P5-AC08/AC11 tests.
8. **Slice 5.8 — Representative check + perf:** D001/MG-K10 isolated copies (per Q2); 500-fact 1080P/2K/4K browser verification (Codex).

**Bounded questions for Codex (each blocks a slice; safe provisional path stated):**
- **Q1 (blocks 5.1):** Confirm new v2 published tables/contracts bound to `evidence_snapshots_v2` + `evidence_processing_revisions` + `episode_revision`, with legacy placeholder tables quarantined — vs in-place rebuild. Recommend new tables (matches Phase 4 pattern, safest for replay). Provisional: proceed with new tables.
- **Q2 (blocks 5.8):** Is P5-AC12 executed inside Phase 5 on **isolated synthetic** structurally-different D001/MG-K10 copies (safe under the no-external-clinical-data boundary), with real-data "与原始资料核对" run only by Codex/user post-conference? Provisional: treat P5-AC12 as isolated-copy verification; real-data clinical reconciliation is outside conference scope.
- **Q3 (blocks 5.2/5.3):** Confirm the Normalizer job freezes an attempt manifest (Phase 4 `ProcessingCandidateAttemptManifest`) and publication re-verifies the live active `(snapshot, complete_revision, episode_revision)` triple at commit. Provisional: reuse Phase 4 pattern.
- **Q4 (blocks 5.4):** Confirm FactRuleLink is exact-match-only against published RuleComponent/EvidenceRequirement (reject fuzzy similarity). Provisional: exact-match only.
