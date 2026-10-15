I'll start with the assigned read set and the four binding-qualification files, then pull the design/source definitions needed for a source-only evidence review.The conference packet is still a skeleton, so I’ll load the four producer files and locate the design/source-of-truth documents next.The four modules are in hand. Next I’ll read design §17.1.1/§17.2, recovery T5, and the live candidate job/receipt contracts so reconstruction can be checked against real checkpoints.I have the design contract. Next I’ll compare live candidate jobs, JobStore checkpoints, comparison payloads, and transport/retry code against this unit’s receipt reconstruction.I'll confirm the unbound names and control evaluation-spec fields with source-only inspection, then draft the conference report.# Conference Output: r05-qualification-source-20260914 - evidence_single_object

## Output

Role `evidence_single_object` / `grok` / `grok-build` / `grok-4.6`. Source-only challenge of the new binding-qualification producer. No runtime import, model call, clinical DB, browser, test, write, or executor-report read. Formal acceptance remains with Codex. Runtime behavior is **UNVERIFIED**, not PASS.

### Scope actually read

- Assigned: `context/r05-qualification-source-20260914_conference_context.md`, `plans/codex_main_venue_r05-qualification-source-20260914.md` (both still TODO skeletons).
- Four new modules: `app/domain/contracts/binding_qualification.py`, `app/llm/binding_qualification.py`, `app/services/binding_qualification.py`, `app/services/binding_qualification_support.py`.
- Design: `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17.1.1 and §17.2.
- Recovery: `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` T5.
- Actual producers/contracts/JobStore/transport: `app/services/predicate_binding_job.py`, `app/services/control_binding_job.py`, `app/services/binding_candidate_comparison.py`, `app/workflow/jobstore.py` (`get_last_checkpoint`), `app/services/job_service.py` (`StepSpec.max_attempts=1`), `app/api/v2/app.py` `default_executors`, `app/llm/predicate_binding_candidates.py`, `app/llm/page_review_harness.py` (`PageCompletion`/`PageReaderRoute`), `app/llm/page_review_transport_options.py`, `app/services/page_review_cancellation.py`, `app/services/page_review_job_service.py` (`route_identity`), plus EvidenceRequirement / ControlEvidenceSourcePolicy / ControlMinimumEvidence / ControlAtomEvaluationSpec / FrozenFactRecord / ReviewEpisode / FrozenLocatorIdentity.

Did **not** read execution worker reports or private reasoning.

---

### Evidence (source facts)

**E1. Stage is constructed and stays unregistered.**  
`BindingQualificationJobExecutor.job_type = "binding_qualification"` / `CONTRACT = "binding-qualification-job/v2"`. `app/api/v2/app.py` `default_executors` has no `binding_qualification`, `predicate_binding_candidates`, or `control_binding_candidates`. No API enqueue of this job. Module docstring: “Not registered.” Clinical flags on pair/summary contracts are `Literal[False]` and validators reject true.

**E2. Summary compose has unbound names.**  
`app/services/binding_qualification.py` imports only `BindingQualificationBatch` and `BindingQualificationPairContext` from the contract module, and only `CONTRACT`, `JOB_TYPE`, `SEMANTIC_DIMENSIONS`, `load_completed_candidate_qualification_input` from support. `compose_qualification_summary` still calls `validate_binding_qualification_structure`, `BindingQualificationPairRecord(...)`, `binding_qualification_summary_hash(...)`, and `BindingQualificationSummary.model_validate(...)`, and writes `BINDING_QUALIFICATION_SUMMARY_VERSION` / `BINDING_QUALIFICATION_PROMPT_VERSION`. AST load-name scan of that file lists those seven names as unbound. `from __future__ import annotations` only delays annotation evaluation; the constructors/constants are runtime loads.

**E3. Candidate receipt reconstruction uses actual checkpoint field names.**  
Completed candidate jobs are required to be `state=="completed"`, `purpose=="isolated_unverified_candidates"`, official contracts `predicate-binding-candidate-job/v7` + prompt `predicate-binding-candidates/v6` / batch `v4`, or `control-binding-candidate-job/v5` + prompt `control-binding-candidates/v1` with `batch_prompt_version is None`.  
Read steps: `read:{lane}` or `read:{index}:{lane}`. Checkpoint fields actually written by `PredicateBindingJobExecutor`: `status`, `candidate_sha256`, `accepted`, `receipt_sha256s`, `lane`, `frozen_input_sha256`, `batch_sha256`. Summary checkpoint: `status`, `accepted`, `frozen_input_sha256`, `reads`, `comparison_sha256`. Comparison artifact: `version=="binding-candidate-comparison/v1"`, `accepted is False`, `batches[].sources[lane]=<full read checkpoint>`, `results` from `compare_candidate_declarations`. Qualification `verify_completed_candidate_comparison` checks those same names, rebuilds comparison, and requires `rebuilt == stored_comparison`.

**E4. Qualification receipts copy that pattern, with gaps against fields this unit itself writes.**  
Qualify checkpoints: `status`, `qualification_sha256` (or `failure` on incomplete), `accepted`, `authorized_clinical_adoption`, `clinically_qualified`, `receipt_sha256s`, `lane`, `batch_sha256`, `frozen_input_sha256`, `comparison_sha256`, `candidate_job_id`.  
Artifact body: `input_sha256`, `batch_sha256`, `messages_sha256`, `payload`, `accepted`, clinical flags, `candidate_job_id`, `comparison_sha256`.  
Summary reconstructs last checkpoint via `JobStore.get_last_checkpoint`, checks `frozen_input_sha256`, `batch_sha256`, `lane`, `accepted is False`, `status=="unverified"`, last `receipt_sha256s` entry, `receipt.job_id/step_id`, `canonical_hash(request.messages)` vs rebuilt messages, `artifact.messages_sha256`, `artifact.batch_sha256`, `request.model`/`reasoning_effort` vs `self.routes[lane]`, `response.finish_reason=="stop"`, and payload-vs-raw-text equality. It does **not** check `artifact.input_sha256`, `artifact.candidate_job_id`, `artifact.comparison_sha256`, artifact clinical flags other than `accepted`, `request.max_tokens`, or `PageCompletion.response_model`. Request dict has no `provider` (same as candidate producer). This pipeline has no round field (same as candidate jobs).

**E5. Pair coverage of comparison items is complete; identity accounting overclaims.**  
`build_qualification_pairs_from_verified` walks every comparison batch/result/comparison item, including `single_lane` and `declaration_disagreement`. Empty comparisons become identity records with `no_candidates_in_supplied_input`. Non-empty `pair_ids` set `status="candidates_qualified"` **at pair-construction time**, before any qualification LLM or structural check, and those records are copied into the summary unchanged. `BindingQualificationSummary` does not require unique `identity_records`.

**E6. Predicate source-policy “present” is guessed from component cardinality.**  
`_source_policies_for_predicate` dumps **all** `component.evidence_requirements` onto every trigger and exception predicate in that component. If `len(policies)==1`, status is `"present"`. Comment in source: “Official components do not publish explicit per-predicate evidence attribution.” `FrozenPredicateIdentity` has no requirement_id. `EvidenceRequirement` binds `rule_component_id` + `fact_type`, not a predicate. Design §17.1: 不得把组件全部 fact_type 复制给触发和所有例外. §17.2: fact_type 相等不是谓词归属证明.

**E7. `_policy_unknown` does not match the predicate policy dict it is given.**  
Predicate policy keys include `control_validity_status`, not `result_validity_status`. `_policy_unknown` tests `policy.get("result_validity_status") == "unknown"`. Official `EvidenceRequirement` validator forbids `None` on the two booleans when `control_origin is None`, so the `is None` branches are also dead for official components. Control policies dumped from `ControlEvidenceSourcePolicy` do have `result_validity_status`; that branch can work for controls.

**E8. Control policy matching uses real atom_refs keys, then still collapses multiples.**  
Key is `(layer, group_index, atom_index)`, matching `ControlEvidenceAtomReference.key`. Empty `atom_refs` are not skipped (`if evidence.atom_refs and key not in refs: continue`), then any empty refs → `"unattributed"` (does not invent a link). Missing `source_policy` or `_policy_unknown` → `"ambiguous"`. `len(matches)==1` → `"present"`; otherwise `"unattributed"`.

**E9. Structural check copies value/unit/date; it does not admit them. Control shape ignores `time_operand_attribute`.**  
`validate_binding_qualification_structure` fails on missing fact/locator/attribute/excerpt, unbound locator, body≠frozen dump, missing identity, `unverifiable_source`. It records `referenced_value`/`referenced_unit`/`referenced_date_precision`/`referenced_record_time` without comparing unit to the predicate, date precision to a time constraint, or locator/document to `required_source_types`. Predicate `candidate_value_shape` pending_checks (`unit_equivalence_unverified`, etc.) are dropped; only `operand_shape` is kept. Control shape is `spec.operand_attribute == pair.fact_attribute` only. `ControlAtomEvaluationSpec` for `value_comparison` with an attached atom time constraint **requires** `time_operand_attribute` in `{date_range, record_time}` while `operand_attribute` is `value` (`control_evaluation_spec.py` lines 78–80, 123–125). A date_range pair on such an atom is labeled `declared_operand_attribute_mismatch` even when it matches `time_operand_attribute`. `structurally_valid` can still be true. `source_policy_status != "present"` does not fail structural validity; it only appends `source_policy_*` to `remaining_unverified`.

**E10. Dual agreement is not gated on policy presence or record_time.**  
`dual_agreement` is equality of `public_agreement_key()` (six structured dimensions, no free text). Compose does not override `source_admissibility=="admissible"` when `source_policy_status` is missing/unattributed/ambiguous, nor `temporal_role=="event_date"` when `fact_attribute=="record_time"`. Prompt text tells the model to keep unresolved / not treat `record_time` as event date; the contract/compose do not enforce it. `authorized_clinical_adoption`/`clinically_qualified`/`accepted` stay false. `remaining_unverified` always includes `clinical_adoption_not_authorized` and `evaluation_activation_absent`.

**E11. Prompt identity.**  
Messages carry `prompt_version=binding-qualification/v2`, `frozen_input_sha256`, `candidate_job_id`, `batch` (including `batch_sha256`), episode/anchors, conditions/facts/locators/documents, per-pair parent context and policies. They omit peer `lane_declarations`, `comparison_sha256`, and candidate-lane explanations. System text forbids filename-only proof and guessed attribution. Batch packing uses payload JSON size, not the later `output_schema` appended to the user message. `plan_qualification_batches` refuses to truncate a single pair.

**E12. Lane/retry/cancel bounds.**  
Enqueue requires `set(routes)==set(LANES)` and `65536<=max_tokens<=131072`. Steps are `qualify:{index}:{lane}` serial per lane, `max_parallel_steps` 1 if both local else 2. `StepSpec.max_attempts` default 1, `retryable` default False. `read_candidate_payload` retries HTTP 429 up to 12×60s and one length-doubling to 131072. Cancel uses `run_cancellable` / `PAGE_REVIEW_CANCEL_REQUESTED` → incomplete checkpoint with `receipt_sha256s`. Failed qualify (`status!="unverified"`) makes summary raise non-retryable `BINDING_QUALIFICATION_RECEIPT_SCOPE_CHANGED`. `_verify_current` rebuilds live frozen hash and receipt-derived pairs/policies; mismatch is non-retryable.

**E13. Formal publisher / consumer wiring is absent.**  
No registration, no enqueue from candidate summary, no `evaluate_bound_component_experiment` consumption of these records. T5 still lists “仍缺经来源资格核实的绑定生产者、跨章临床消费与正式发布命令”.

---

### Inference (not observed at runtime)

**I1. Highest-impact unit defect is not “missing publisher.”** It is that this producer can mark `source_policy_status="present"` and `dual_agreement=True` without a predicate-level source link, and can call a pair `structurally_valid` without admitting unit/date/allowed-source. Clinical flags being false prevents auto-adoption, but `dual_agreement` + `"present"` are the durable structured claims this stage exists to produce. That is a false-ready signal for any later isolated consumer.

**I2. The unbound names in `compose_qualification_summary` make the summary step source-dead.** Qualify steps can be written; durable pair/summary records cannot be composed without a NameError. This is a construction bug in this unit, independent of registration.

**I3. Receipt reconstruction is mostly honest against actual candidate/JobStore names**, not invented fields. The unique reconstruction hole in *this* unit is failing to close artifact fields it writes (`input_sha256`, `candidate_job_id`, `comparison_sha256`) and failing to bind prompt identity to `comparison_sha256`. Last-checkpoint-only receipts are inherited from the candidate producer, not invented here.

**I4. Official single-requirement components will almost always get `"present"`.** That is the same-type/component-wide attribution pattern §17.1 forbids. It is not a blanket-all-unknown workaround, and it is not token matching; it is guessed attribution by `len(policies)==1`. Safer default while no explicit predicate↔requirement link exists: `unattributed`, keep the full policy list, never auto-present.

**I5. Construction remains useful as a disabled isolated producer** after the defects below are repaired. Usefulness does not require activating or registering the stage. T5 asked for a complete but unenabled source-qualification chain; a summary that cannot compose, and a `"present"`/`dual_agreement` that can fire without attributed policy, is not yet that chain.

**I6. Model diversity is not independently verified.** Dual lanes exist as `main-A`/`main-B` with `route_identity` (provider/base_url/model/effort/max_tokens). Caller supplies routes. The requested execution selector was `cursor/default` with no resolved underlying model. This review cannot claim two independent models.

---

### Recommendation (minimum complete repairs in this unit)

Keep the stage unregistered. Do not add a publisher, evaluator hook, or app executor map in this round.

1. **Import/fix compose** in `app/services/binding_qualification.py`: import `BindingQualificationPairRecord`, `BindingQualificationSummary`, `BINDING_QUALIFICATION_SUMMARY_VERSION`, `BINDING_QUALIFICATION_PROMPT_VERSION`, `binding_qualification_summary_hash` from the contract module, and `validate_binding_qualification_structure` from support. Optionally re-export from support instead of duplicating, but the names must resolve.

2. **Stop guessing predicate policy attribution.** Default official predicates to `source_policy_status="unattributed"` whenever there is no explicit predicate-level link (there is none today). Still attach the full `evidence_requirements` list. Do not use `len(policies)==1`, `fact_type` equality, filename, or `required_source_types` string match to promote `"present"`. Fix `_policy_unknown` to the fields actually dumped (`control_validity_status` vs `result_validity_status` per family). Control: keep empty `atom_refs` as unattributed; `"present"` only for a single evidence row whose `atom_refs` explicitly contain this atom and whose `source_policy` is complete and not unknown.

3. **Do not let dual agreement launder missing policy or record_time-as-event.** In compose (and/or judgment validation): if `source_policy_status != "present"`, `source_admissibility` may not be `admissible`; if `fact_attribute=="record_time"`, `temporal_role` may not be `event_date` and `direct_operand_usable` may not be `usable`. Force unresolved/not_usable and `dual_agreement=False` rather than trusting the prompt.

4. **Record, don’t convert, unit/date/allowed-source; don’t drop existing pending checks.** For predicates, persist `candidate_value_shape(...)["pending_checks"]` into `remaining_unverified`. For controls, compare `fact_attribute` to `operand_attribute` **or** `time_operand_attribute` when the latter is set; record `time_purpose`; if `time_purpose=="source_validity"`, add a remaining flag that source-validity is not substituted into an atom conclusion. Do not treat unit string equality as conversion, and do not admit `required_source_types` via fact_type/filename/media_type.

5. **Close receipts against fields this unit writes.** Summary must require `artifact.input_sha256==payload.frozen_input_sha256`, `artifact.candidate_job_id`, `artifact.comparison_sha256`, and artifact clinical flags false. Put `comparison_sha256` (and prompt_version already present) into the prompt payload so message hash links the comparison artifact. Checking `response_model` against `route.model` would be a plus; candidate jobs also skip it — treat as shared residual, not a unique blocker.

6. **Rename identity status.** Replace `candidates_qualified` with a non-authorizing label such as `pairs_constructed` / `candidates_present`, or keep `candidates_compared` from the comparison contract. Status must not say qualified because pairs existed.

7. **Keep `accepted`/`clinically_qualified`/`authorized_clinical_adoption` false** until evaluation + user approval. Missing formal publisher is an integration gap, not a reason to activate.

---

### Uncertainty / UNVERIFIED

- No py_compile, import, JobRunner, model, or SQLite execution was performed. NameError is source-visible, not crash-observed.
- Pydantic `model_json_schema()` stability across versions, JSON round-trip equality of pair bodies vs frozen dumps, and batch size vs actual context (payload-only packing) are unexecuted.
- Whether any real published component has exactly one `EvidenceRequirement` and multiple predicates is not counted from a clinical DB (forbidden). The code path does not require that count to be large to be wrong.
- Dual-lane model inequality: **unknown**. Do not treat `main-A`/`main-B` as proven distinct models.
- `get_last_checkpoint` dropping earlier attempt receipts is inherited; whether T5 wanted this stage to `list_checkpoints` is a Codex product choice.
- Visual/clinical/regulatory/current-web authority: none claimed.

---

### Highest-impact defect

**Predicate policy is marked `present` by “one requirement on the component,” and dual agreement can still accept `admissible` / `event_date` without code gates.** Combined with dropped unit pending-checks and control `time_operand_attribute` blindness, the durable structured success flags (`source_policy_status`, `structurally_valid`, `dual_agreement`) can read as source-qualified when design §17.1.1 step 3 still requires code verification of identity, excerpt, value, unit, date precision, and allowed source, and forbids guessed attribution. Clinical `Literal[False]` only blocks adoption; it does not stop a false qualification record.

Concrete alternative: never emit `"present"` without an explicit predicate/atom evidence link; never emit `dual_agreement` when policy is not present or `record_time` is treated as event date; persist shape/pending flags instead of implying admission.

---

### Objections, decision points, bounded questions for Codex

**Objections**
- Treating `authorized_clinical_adoption=False` as sufficient would hide the dual-agreement/policy hole. This stage’s job is source qualification records, not only a dead clinical bit.
- Copying candidate-job receipt logic is necessary but not sufficient: this unit writes extra artifact fields and then does not reread them.
- `len(policies)==1 → present` is not “conservative”; it is an attribution guess. The conservative value already exists: `unattributed`.
- Control `declared_operand_attribute_mismatch` on a legitimate `time_operand_attribute` will pollute `remaining_unverified` and can mislead later operand selection.

**Decision points (Codex)**
1. Is `"present"` allowed for official predicates before a predicate-level evidence link is added to published contracts? Provisional path: **no**.
2. Is `dual_agreement` a semantic success flag that later isolated consumers may read, or merely informational? Provisional path: treat it as success-shaped; gate it in compose.
3. Does §17.1.1.3 “代码核实…单位、日期精度和允许来源” mean fail `structurally_valid`, or only fill `remaining_unverified` without admitting? Provisional path: do not fail structural on unit conversion; **do** keep pending flags and **do not** set admissible/usable when policy/date role is unresolved.
4. Should identity status be renamed in v2 contracts (breaking this new unused schema) or documented as pair-accounting only? Provisional path: rename now; the contract is not registered.

**Bounded questions**
1. Confirm: no official `EvidenceRequirement`→predicate map is intended in this slice, so `"present"` must not appear for family=`predicate` until a later contract exists?
2. Confirm: `time_operand_attribute` pairs are in-scope for qualification (source/date role of the time operand), not only `operand_attribute==value`?
3. Confirm: do **not** register `binding_qualification` in `default_executors` even after repairs, pending evaluation+approval?

Safe provisional path until those answers: repair 1–6 above; keep job unregistered; do not enqueue from candidate summary; do not consume `dual_agreement` as clinical or even as isolated evaluation input.

---

### Separate non-defect: missing integration

Formal publisher, app executor registration, candidate-job handoff, and `evaluate_bound_component_experiment` consumption are **absent**. T5 already records that gap. That is not a defect inside the four new files’ intended isolation, provided the unit does not claim activation. After repairs, the unit is a disabled producer candidate; before repairs, it is not yet a trustworthy disabled producer.

---

### Quality labels

| Claim | Label |
|---|---|
| Unbound compose names | Evidence (AST + source) |
| Policy `present` via single component requirement | Evidence |
| Dual agreement ungated on policy/record_time | Evidence |
| Receipt field names match candidate JobStore | Evidence |
| Artifact `input_sha256` not rechecked | Evidence |
| Control `time_operand_attribute` ignored | Evidence vs `ControlAtomEvaluationSpec` |
| Summary NameError / JobRunner outcome | Inference / **UNVERIFIED** |
| Two distinct models | **UNVERIFIED**; do not claim |
| Clinical/regulatory acceptance | Not claimed |
| Stage should stay disabled | Recommendation (matches T5 / §17.1.1 isolation) |
