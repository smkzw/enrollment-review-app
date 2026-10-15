I'll start from the assigned conference context and plan, then independently audit the Phase 5.3 Evidence Normalizer and persistence path without editing files.The conference packet is mostly TODOs, so I’ll locate the Phase 5.3 Evidence Normalizer and persistence implementation from the workspace itself.I'll load the slice 5.3 execution packet and inspect uncommitted implementation against the frozen-input and persistence invariants.Frozen-input hashing is in the contracts; next I’ll audit the executor, job/lease path, and locator/empty-output gates for bypasses.# Conference Participant Output: phase5-slice53-independent-check - general_grok46

## Boundary Check

- **Role:** `general_grok46` / Grok Build `grok-4.6`. Advisory participant only. Codex remains final authority.
- **Mode:** read-only independent audit. No source edits. No report-file writes. No conferences started. No internet scan.
- **Workspace:** runner CWD `.` (phase5 worktree). Did not read other participant outputs. Did not read home `AGENTS.md` / `SOUL.md`.
- **Initial read set:** `context/phase5-slice53-independent-check_conference_context.md`, `plans/codex_main_venue_phase5-slice53-independent-check.md`. Both are mostly TODO; additional in-workspace reads were required to audit the uncommitted Slice 5.3 implementation.
- **Not claimed:** clinical/regulatory/visual/current-web acceptance. Test green is not acceptance.

## Independent Work Product

### Audit framing

**Goal:** decide whether the uncommitted Phase 5.3 Evidence Normalizer + persistent run path actually freezes 审核节点 / 资料类型 / 来源方 / 记录时间 / `EvidenceRequirement` into the model input and idempotency hash, and whether activity authority, page closure, locator authenticity, empty output, lease loss, and restart idempotency can be bypassed.

**Highest-impact defect:** finalize records Slice 5.2 locator/page/empty-call rejections but still marks the run `SUCCEEDED`. Locator authenticity is therefore not a run-level hard stop in 5.3. Combined with candidates being persisted before gates, a completed run can contain only rejected locators.

### Frozen input and idempotent hash

| Field | Enters `EvidenceNormalizerInput`? | Enters per-call `input_sha256`? | Enters job idempotency key? |
|---|---|---|---|
| 审核节点 | Yes: `FactAuthority.review_episode_id` + `episode_revision`; `context.current_review_stage` / `workflow_stage_id` from live episode | Yes, via `authority` + `context` in `evidence_normalizer_input_scope_hash` | Yes, `fact_run_idempotency_key` dumps full `authority`; stage/workflow enter only transitively through per-call sha |
| 资料类型 | Yes: `context.document_type` from metadata revision | Yes | Transitive via per-call sha, not as a top-level job field |
| 来源方 | Yes: `context.source_party` | Yes | Same |
| 记录时间 | Placeholder only: `document_record_time=None` always | Yes, as JSON `null` | Same; no actual metadata record-time value exists to freeze |
| `EvidenceRequirement` | Yes: all requirements with `due_stage <= episode.stage`, sorted by `requirement_id`, attached to **every** logical-document call | Yes, full `model_dump` | Transitive via per-call sha |

Evidence: `app/domain/contracts/evidence_normalizer.py` (`EvidenceNormalizerContextInput`, `evidence_normalizer_input_scope_hash`); `app/services/fact_normalization_source_adapter.py` `_load_normalizer_context`; `app/domain/planning/fact_normalization_planning.py` `compute_call_input_hash`; `app/services/fact_normalization_job_service.py` `_compute_input_scope_sha256` + `fact_run_idempotency_key`.

Contract tests prove the per-call hash moves when context or requirements change (`tests/v2/domain/test_evidence_normalizer_contracts.py::test_input_hash_changes_with_document_context_or_requirement`). Persistence tests prove rebuild contains type/party/stage/due requirements (`test_rebuilt_model_input_contains_frozen_document_stage_and_requirements`). That is **not** proof that job-level `Run.input_scope_sha256` equals the planning-layer scope hash.

### Findings by severity

**P1 — Finalize does not fail the run on Slice 5.2 overall rejection (locator authenticity / empty-call / page-coverage gates are non-blocking).**

- File: `app/services/fact_normalization_executor.py` `execute_finalize` (approx. 323–348).
- Observation: after `orchestrate_run_gates(...)`, the executor persists `FactGateResult` rows and always `FactNormalizationRunRepository.set_status(..., SUCCEEDED)`. There is no `if run_result.overall_outcome != ACCEPTED: raise StepFailure`.
- `orchestrate_run_gates` itself treats calls with zero candidates as `failure_reasons` (`app/domain/gates/fact_batch_orchestration.py` ~912–922) and `batch_gate_evidence_closure` can REJECT locators. None of that stops the job.
- All-unresolved runs skip `orchestrate_run_gates` entirely (`else: gate_result_count=0`) and still succeed.
- Inference: locator authenticity is **audited**, not **enforced**, at the 5.3 run boundary. A SUCCEEDED run may contain only rejected candidates.
- Remediation: Codex must pick one contract: (A) finalize `StepFailure(PARTIAL_OUTPUT/GATE_REJECTED)` when `overall_outcome != ACCEPTED`, or (B) keep run=SUCCEEDED meaning “model calls finished” and make 5.4 publish require `overall_outcome==ACCEPTED` plus no rejected locator gates. Until (A) or (B) is explicit, do not treat 5.3 as closed.
- Safe provisional path: assume (B) is the current code meaning; do not publish facts from these runs.

**P1 — Per-page closure is enforced only on the in-memory model payload; unresolved items are not domain-persisted.**

- Files: `app/agents/evidence_normalizer.py` `validate_output_page_closure`; `app/services/fact_normalization_executor.py` `execute_call.apply`; `app/storage/facts_models.py` (no unresolved table); `app/domain/gates/fact_evidence_closure.py` `validate_page_coverage`.
- Observation: decoder/page-closure requires each input page to be covered by a candidate locator **or** `unresolved_items.affected_pages`. Executor empty-output rejects zero candidates **and** zero unresolved. Good at the transport boundary.
- Unresolved items are written only into the Job checkpoint JSON (`unresolved_items` / `unresolved_items_sha256`). Call persist stores status/input/raw sha only.
- Finalize `validate_page_coverage` checks that call page lists equal the complete-revision manifest. It does **not** re-read unresolved items or re-check per-page candidate/unresolved cover.
- Inference: after crash/restart, durability of “逐页闭合” is the checkpoint blob + “step completed”, not a clinical table. 5.4 Expectation projection cannot reconstruct gaps from Run/Call/Candidate.
- Remediation: persist `EvidenceNormalizerUnresolvedItem` rows keyed by `run_id/call_id` in the same `PreparedStepResult.apply` transaction as the call; finalize must reload them and fail if any planned page lacks candidate locator or unresolved cover.

**P1 — Locator authenticity at ingest is ID-membership only; repository create does not call `validate_locators`.**

- Files: `app/agents/evidence_normalizer.py` `parse_evidence_normalizer_output` (unknown locator IDs rejected); `app/storage/fact_repositories.py` `FactNormalizationCandidateRepository.create` (run/call binding only); `app/storage/fact_authority.py` `validate_locators` (unused on this write path).
- Observation: a candidate may cite any ID in `available_locator_ids`. No excerpt, `source_text_sha256`, bbox, or character-range proof at persist. Slice 5.2 text-hash/authenticated-locator checks run later in `batch_gate_evidence_closure`, and per P1 above they do not fail the run.
- Inference: inventing a brand-new locator ID is blocked; borrowing a real locator whose span does not support the assertion is not blocked at 5.3 persist.
- Remediation: either call `FactAuthorityValidator.validate_locators` + reuse `fact_evidence_closure` on persist (fail the step) or accept persist-as-candidate but then do P1 finalize blocking.

**P2 — Two different objects are both named `input_scope_sha256`.**

- Planning: `compute_input_scope_hash` includes authority, revision id, both manifest shas, and per-call shas (`app/domain/planning/fact_normalization_planning.py`).
- Job/Run: `_compute_input_scope_sha256` hashes only `{calls: [{logical_document_id, page_numbers, input_sha256}]}` (`fact_normalization_job_service.py` 93–96). `create_or_reuse_from_source` discards `plan.input_scope_sha256`.
- Inference: clinical fields **do** affect the job key because they are inside each `input_sha256`. An auditor looking only at `FactNormalizationRun.input_scope_sha256` payload will **not** see stage/type/party/requirements listed. Collision risk is low if per-call sha is correct; auditability is weak.
- Remediation: persist `plan.input_scope_sha256` on the run (or a versioned envelope that includes both) and make `create_or_reuse_from_source` the only public creator.

**P2 — `document_record_time` is hard-coded `None`; 记录时间 is not frozen as a source-metadata value.**

- File: `app/services/fact_normalization_source_adapter.py` ~113–121. Metadata contract (`SourceDocumentMetadataRevision`) has type/party only, no record-time field. Prompt tells the model not to fill from upload/screen/ops dates.
- Inference: this is consistent with the current evidence schema, but it does **not** satisfy a reading of the audit question that 记录时间 must be a frozen authoritative input. Candidate `record_time` remains model-extracted and is gated later (`validate_record_time` allows `None`).
- Remediation: if protocol/source docs have an official 报告日期/记录日期 field, add it to metadata revision and hash it; until then document that frozen record time is explicitly absent.

**P2 — `related_requirements` is the full due-stage rule-set, not document-scoped.**

- File: `_load_normalizer_context`. Every call prompt/hash includes ICF, labs, procedures, etc., as long as `due_stage` has arrived.
- Inference: freeze is conservative (requirement text change invalidates all calls). Clinical prompt noise and over-triggering of “should have seen X” is a product risk, not a hash hole.
- Remediation: optionally filter by `required_source_types` ∩ `document_type` **inside** the hashed input, with tests that adding an unrelated requirement does or does not change a lab-report call hash — Codex must choose.

**P2 — `create_or_reuse_job` accepts caller-built call specs without planning page-closure.**

- File: `FactNormalizationJobService.create_or_reuse_job`. `_validate_call_specs` only checks intra-spec continuity and unique `(logical, page)`.
- Execute rebuild via `build_evidence_normalizer_input` fails on hash mismatch; finalize coverage fails on subset pages. Fail-closed for silent success, but it can still spend model calls.
- Remediation: make `create_or_reuse_from_source` the only production entry; keep the spec API test-only or require `plan.input_scope_sha256`.

**P2 — Checkpoint short-circuit skips stale-authority and domain `apply`.**

- Files: `fact_normalization_executor.py` 210–211 and 314–315; `app/workflow/jobstore.py` `_reset_interrupted_steps` 1315–1344.
- Observation: if `last_checkpoint` exists, `execute_call` returns the dict (no `PreparedStepResult.apply`, no `_validate_authority`). Finalize returns any checkpoint. Recovery marks `running` + existing checkpoint as `completed` without re-applying domain writes.
- Inference: with current atomic `acquire → apply → checkpoint` this is hard to hit (checkpoint and completed commit together). It becomes a bypass if anyone later writes checkpoints without completing, or resets a completed step to running without deleting checkpoints.
- Remediation: drop the short-circuit, or re-validate authority and require matching persisted Call/Candidate rows before trusting a checkpoint.

**P2 — Lease-loss fence is fail-closed at `acquire_step_commit`; the 5.3 test does not exercise full `JobRunner` heartbeat discard.**

- Observation: `PreparedStepResult` + `acquire_step_commit` checks owner/generation/expiry/running step; `test_late_reply_lease_lost_is_discarded_and_recoverable` proves expired generation cannot apply candidates. `tests/v2/workflow/test_prepared_step_result.py` proves generation steal skips apply.
- Residual: `JobRunner._run_claimed` has no `except LeaseLostError` around the heartbeat; heartbeat `LeaseLostError` falls into `except Exception` and may call `_commit_step_failure` with a **still-valid** lease if the heartbeat thread join times out (`runner.py` 349–354 then 284–294). That would discard the successful result **and** fatally fail the step (`EXECUTOR_ERROR`, retryable=False). Not a clinical-write bypass; it is a recovery/liveness hole.
- Remediation: catch `LeaseLostError` before `except Exception` and return without `fail_step`; add a 5.3 test that runs `JobRunner.run_job` through heartbeat loss, not only a direct `acquire_step_commit` call.

**P3 — `validate_page_coverage` falls back to `source_document_version_id` as logical id when snapshot-member mapping is empty/errors.**

- File: `app/domain/gates/fact_evidence_closure.py` 96–115. SQLAlchemy errors are swallowed. Production mismatch should fail closed (logical id ≠ version id). Test fixtures that set logical id = version id can hide mapping bugs.
- Residual, not a demonstrated production success bypass.

**P3 — Implement.md Slice 5.3 still requires a real-model minimum closed loop.** Focused tests passing is not that threshold. No live DeepSeek/UAT was in this pass.

### What is working (evidence, not acceptance)

- Per-call freeze includes authority, context (type/party/stage), requirements, both manifest shas, page artifacts, effective-text sha, locator id lists.
- Rebuild path `build_evidence_normalizer_input` refuses hash drift (`expected_input_sha256`).
- Activity authority is checked at job create, before transport, and inside `apply` via `FactAuthorityValidator`. Stale episode revision test leaves no Call row.
- Decoder rejects empty JSON, markdown, forbidden top-level publish fields, page-list mismatch, unknown locator IDs.
- Current executor has **no** dummy `effective_text` fallback (contrary to an earlier worker_03 narrative). Source errors become non-retryable `PARTIAL_OUTPUT`.
- Domain writes for successful calls are intended to sit behind the lease commit fence.

### Draft / output plan for Codex (not executed)

1. Decide finalize blocking policy (P1).
2. Persist unresolved items in-domain; re-check per-page closure at finalize.
3. Unify and store a single input-scope hash that explicitly lists context + requirements.
4. Narrow or document requirement fan-in; decide record-time metadata.
5. Catch `LeaseLostError` in the runner; add a JobRunner-level 5.3 reclaim test.
6. Only then consider a real-model closed loop. Do not use current tests as UAT.

## Evidence And Assumptions

### Evidence (observed)

- Uncommitted new modules: `app/domain/contracts/evidence_normalizer.py`, `app/agents/evidence_normalizer.py`, `app/agents/deepseek_evidence_normalizer_transport.py`, `app/domain/planning/fact_normalization_planning.py`, `app/services/fact_normalization_source_adapter.py`, `app/services/fact_normalization_job_service.py`, `app/services/fact_normalization_executor.py`, plus focused tests under `tests/v2/{domain,agents,services,workflow}/`.
- Uncommitted edits: `app/workflow/jobstore.py` (`acquire_step_commit` / `complete_step_after_commit_fence`), `app/workflow/runner.py` (`PreparedStepResult`), `app/storage/fact_repositories.py` (`set_status`).
- `git status` also shows unrelated Trellis/AGENTS churn; not used as 5.3 evidence.
- Conference packet source-of-truth/scope/success criteria are TODO; execution packet is the real contract: candidate/unresolved-only, reuse Job/Lease, no Profile publish.
- Tests named above were **read**, not re-run in this pass.

### Inference

- Per-call hashing is the real freeze; job-level hashing is a digest of those shas.
- `SUCCEEDED` currently means “steps completed and calls persisted”, not “all gates accepted”.
- Checkpoint/recovery logic assumes checkpoint ⇒ domain apply already committed; true only while apply+checkpoint stay in one transaction.

### Assumptions

- Complete processing revisions only list confirmed metadata revisions (not verified here against the Phase 4 activation writer beyond seeing `is_auto_suggestion` is not checked in `_load_normalizer_context`).
- 5.4 publish will be the first writer of `ClinicalFactV2` and can still refuse rejected candidates.
- No other participant findings were merged.

### Uncertainty

- Whether Codex wants finalize to fail closed on gate REJECTED (product-blocking) vs record-and-continue (candidate warehouse).
- Whether auto-suggestion metadata can appear in `revision.metadata_revision_ids`.
- Whether `JobRunner` heartbeat join-timeout has been seen in this worktree’s workflow tests.
- Live model behavior on per-page unresolved quality (one unresolved listing all pages vs true 逐页 reasons). `validate_output_page_closure` only checks page-number set cover.

## Risks, Gaps, And Verification Needs

- **Do not treat green tests as acceptance.** Persistence tests inject `transport_fn`, use a 2-page seed, and for lease-loss do not run the heartbeat wrapper. Empty-output tests do not persist unresolved. Restart test proves job reuse after `completed`, not mid-step reclaim with dirty candidates.
- **5.4 dependency:** without persisted unresolved items, Expectation/Profile will under-report gaps or re-invent them from checkpoints.
- **Prompt bloat / hash churn:** dumping all due-stage requirements into every document call will invalidate all calls when any requirement text changes.
- **Verification Codex still owns:** (1) focused 5.3 tests independently re-run; (2) a fixture where `batch_gate_evidence_closure` REJECTS locators and assert whether the job/run must fail; (3) crash between model return and `acquire_step_commit` then recover; (4) subset `create_or_reuse_job` vs full revision; (5) metadata `is_auto_suggestion=True` in a complete revision; (6) real-model min loop per implement.md 5.3. No browser/visual work assigned.

## Recommended Next Step

Codex should treat Slice 5.3 as **not closed**. First decision: **does `FactNormalizationRunStatus.SUCCEEDED` require Slice 5.2 `overall_outcome==ACCEPTED`?** If yes, fail finalize on rejected locator/page/empty-call gates and persist unresolved rows in the same lease transaction. If no, write that contract into the design/PRD so 5.4 cannot publish from SUCCEEDED-but-rejected runs.

Do not start 5.4 publish/Profile work until that decision and the unresolved-durability hole are fixed or explicitly deferred with a 5.4 blocker.

### Objections, proposed solutions, decision points, bounded questions

**Objections**

1. “Tests cover empty output / lease loss / restart” — they cover injected transport and a direct fence call, not durable per-page unresolved or runner heartbeat loss.
2. “Gates remain authoritative” — they run at finalize when candidates exist, but they do not control run status.
3. “记录时间已进入冻结输入” — only as `null`. That is a schema fact, not a frozen source timestamp.

**Proposed solutions**

- Finalize: `if run_result.overall_outcome != ACCEPTED: raise StepFailure(retryable=False, error_code=PARTIAL_OUTPUT_CODE, ...)`.
- Add `FactNormalizationUnresolvedRecord` (or equivalent) written in `execute_call.apply`.
- Store `plan.input_scope_sha256` on the run; deprecate the weaker job hash or nest it.
- `except LeaseLostError` in `_run_claimed` before generic `Exception`.

**Decision points for Codex**

1. SUCCEEDED = calls finished, or SUCCEEDED = gates accepted?
2. Requirements in every call vs document-type filtered, hashed either way?
3. Is `create_or_reuse_job` a public API?

**Bounded questions**

1. May a complete processing revision include `is_auto_suggestion=True` metadata? If yes, 5.3 currently freezes suggestion type/party as if confirmed (`_load_normalizer_context` does not check the flag). Why it matters: source-strength and document_type would be unconfirmed yet hashed as authority. Safe path: reject auto-suggestion metadata when building context.
2. Should one unresolved item listing all `affected_pages` count as 逐页闭合, or must each page have its own item/reason? Why it matters: current `validate_output_page_closure` allows the former. Safe path: keep set-cover until Codex tightens; do not advertise 逐页 as proven.
3. For question 1 of SUCCEEDED vs gates: if Codex cannot answer this session, keep runs unpublished and treat `rejected_candidate_count > 0` as a 5.4 blocker.
