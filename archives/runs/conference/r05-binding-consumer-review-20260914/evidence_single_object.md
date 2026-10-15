I'll start with the assigned context files and stay inside this workspace for a read-only evidence review.I'll audit the design, T5 plan, and the binding/selection modules next so the review is grounded in the actual sources.The selection consumer is in view; next I’ll read reconstruction, frozen-review consumption, and how hashes and authorization actually persist.The hash split and dual-family merge look like the high-risk spots; I’ll read those reconstruction and consumer paths next.I’ve got a likely dual-family hash crash and mixed hash semantics; next I’ll confirm authorization persistence, frozen-fact equivalence, and how empty selections are consumed.Authorization looks read-only with no issuer; I’ll confirm GateResult persistence and whether empty selections evaluate as unverified or as false.I have enough source evidence for the dual-family path, hash kinds, and authorization gate. The report below is advisory only.

# Conference Output: r05-binding-consumer-review-20260914 - evidence_single_object

## Output

Read-only source review of receipt-derived frozen calculation selections. No tests, model calls, DB, runtime imports, or production writes. Codex retains final acceptance. This pass does not claim clinical/regulatory/visual/current-web authority, and does not claim the default-disabled complete path is activated.

---

### 1. Highest-impact defect

**Official + control sealed integration is inverted: the documented dual-family path hard-fails; the mixed path proceeds with unverified control maps.**

This is the highest-impact defect I can prove from source.

**Evidence**

- `calculate_frozen_review` accepts either one `ReceiptVerifiedQualifiedBindingSelections` or a `Sequence` of them (`app/services/frozen_review_calculation.py` 137–143, 86–103). The Sequence branch is the only way to feed both families as sealed objects: it recursively resolves each family, rejects duplicate families, and prefers predicate first (97–103).
- After that resolve succeeds, the same function still treats the original argument as a single sealed object when writing the calculation identity (234–240):

```234:240:app/services/frozen_review_calculation.py
    if qualified_binding_selections is not None:
        selection_payload["qualified_binding_selection_sha256"] = (
            qualified_binding_selections.material.selection_sha256
        )
        selection_payload["qualified_binding_family"] = (
            qualified_binding_selections.candidate_family
        )
```

- `qualification_materials` already knows the Sequence case (245–250). The hash payload does not.
- A review with `clause_pack.control_publication` requires both a control frozen input and a complete atom map (`46–53`). A lone sealed control object still demands a caller-supplied official map (`132–133`). A lone sealed predicate object returns caller `control_input` / `control_selections` unchanged (`113–119`).

**Counterexample (fail closed, intended API)**

1. Build sealed predicate selections and sealed control selections from two authorized qualification jobs.
2. Call `calculate_frozen_review(..., qualified_binding_selections=(predicate_sel, control_sel))`.
3. `_resolve_selection_inputs` can succeed and `_calculate_controls` can run.
4. Line 236 then does `list.material` / `tuple.material` → `AttributeError`.
5. No `FrozenReviewCalculation` is produced. Official and control therefore cannot both enter frozen calculation as receipt-verified inputs.

**Counterexample (fail open, mixed API)**

1. Same review has a published control catalog.
2. Call `calculate_frozen_review(..., qualified_binding_selections=predicate_sel, control_input=manual, control_selections=manual)`.
3. Predicate branch returns the hand-built control maps (119).
4. Control arithmetic runs on maps that never passed `build_receipt_verified_qualified_binding_selections` or `_validate_authorization`.
5. `selection_payload` records only the predicate `selection_sha256` / family; `qualification_materials` contains only the predicate material; `controls.selections_sha256` still hashes the unverified control map.

**Inference**

The Sequence API is the claimed dual-family integration. It is unfinished at the identity-seal step. The leftover explicit-map API is the path that actually runs, and it lets authorized official selections carry unauthorized control selections (or the reverse, if someone passes sealed control plus raw official maps). That is not “both official and control selection integration.” It is one sealed family plus a side channel.

**Recommendation**

- If any argument is sealed, require every family present in the frozen review to be sealed. Reject leftover `predicate_fact_ids_by_component` / `control_input` / `control_selections` when a sealed object is present.
- If the review has `control_publication`, require a two-item Sequence `{predicate, control}` and fail with a contract error, not `AttributeError`.
- Hash all sealed materials, e.g. sorted `(family, selection_sha256)` plus both `frozen_input_sha256` values. Do not keep singular `qualified_binding_family`.
- Until that is fixed, do not issue `binding-adoption-authorization` and do not treat mixed maps as receipt-verified.

**Uncertainty**

I did not execute the call. The `AttributeError` is from ordinary attribute access on a Sequence; the mix path is from the predicate `return` that forwards caller control maps. Whether a current caller already uses the mix path is unverified (no runtime).

---

### 2. Artifact hash vs logical hash

**Evidence**

`read_by_sha` is content-addressed over raw bytes and re-hashes those bytes (`app/evidence/artifacts.py` 91–113). Executor `_put` writes `json.dumps(..., ensure_ascii=False, sort_keys=True)` with default separators `", "` / `": "` (`binding_qualification.py` 142–146). `canonical_hash` uses compact separators `","` / `":"` (`app/domain/publication.py` 10–18).

Qualification summary therefore has two different digests for one object:

| Kind | Where | What it hashes |
|---|---|---|
| Artifact | checkpoint `summary_sha256` = `_put(summary.model_dump())` (`binding_qualification.py` 365) | exact JSON bytes in `raw_response` |
| Logical | object field `summary_sha256` = `binding_qualification_summary_hash` excluding itself (`binding_qualification.py` compose via support 823; contract 379–382) | canonical compact JSON without the hash field |

`verify_completed_binding_qualification` documents this and returns both (`binding_qualification_support.py` 1015–1029):

- `summary_sha256` = logical (`rebuilt_dump["summary_sha256"]`)
- `summary_artifact_sha256` = checkpoint / `read_by_sha` key

Candidate comparison has **only** an artifact digest: `verify_completed_candidate_comparison` returns `comparison_sha256: summary[1]["comparison_sha256"]` after `read_by_sha` (`350–351`, `462`). There is no inner logical comparison hash. Frozen input hashes are logical contract hashes (`PredicateBindingFrozenInput` / `ControlBindingFrozenInput` validators).

Authorization and selection material both have a single field name `summary_sha256` (`qualified_binding_selection.py` contract 49–51, 113–115). `_validate_authorization` compares `authorization.summary_sha256` to `verified["summary_sha256"]` (logical, 131) and `authorization.comparison_sha256` to `verified["comparison_sha256"]` (artifact, 130).

**Counterexample**

Issuer copies the three hashes from job checkpoints, which is the uniform persisted pattern:

- `frozen_input_sha256` from payload → logical → matches
- `comparison_sha256` from candidate summary checkpoint → artifact → matches
- `summary_sha256` from qualification summary checkpoint → **artifact A**
- consumer compares A to logical L → `InvalidJobDefinitionError("采信授权与回执重建的资格任务身份不一致")`

If the issuer instead copies `verify_completed_binding_qualification()["summary_sha256"]` (L) and the checkpoint comparison digest (A), authorization can pass. The contract does not say which to use. `QualificationAdoptionAuthorization` cannot even carry `summary_artifact_sha256`.

**Inference**

Hash kinds are mixed under one field name. Reconstruction itself is careful; the authorization/selection contracts throw that distinction away. An owning service that follows checkpoint naming will be fail-closed for the wrong reason. An owning service that follows the verify dict will work, but later `read_by_sha("raw_response", authorization.summary_sha256)` would miss, because L is not a store key.

**Recommendation**

Split the authorization contract, for example:

- `frozen_input_logical_sha256`
- `comparison_artifact_sha256` (and add a logical comparison hash if comparison should be identity-stable across JSON spacing)
- `summary_logical_sha256`
- `summary_artifact_sha256`

Validate each against the corresponding verify field. Reject any digest that cannot be opened with `read_by_sha` when the field is declared as artifact. Do not reuse checkpoint key names for logical hashes.

**Uncertainty**

No issuer exists in this workspace (see §3), so I cannot observe which digest a real writer would pick. That is why this is currently a contract defect, not a live mis-issuance.

---

### 3. Actual persisted authorization

**Evidence**

- Consumer loads `AppendRepository(session, GATE_RESULT_CONFIG).get(authorization.authorization_id)` and requires `gate_name == "binding-adoption-authorization"`, `result == ACCEPTED`, `output_hash == canonical_hash(authorization.model_dump(mode="json"))`, evidence hash ∈ `input_entity_refs`, job id ∈ `accepted_entity_refs` (`qualified_binding_selection.py` 106–117).
- `GATE_RESULT_CONFIG` mirrors only `gate_result_id`, `gate_name`, `code_version`, `result`, `input_scope_hash`, `idempotency_key`, `output_hash` (`repositories.py` 1432–1453). `input_entity_refs` / `accepted_entity_refs` live in `payload_json` and **are** restored by `decode_contract` (`350–373`). Persistence of those lists is structurally possible.
- Workspace grep of `binding-adoption-authorization` and `QualificationAdoptionAuthorization` construction hits only the consumer/contract files. No owning service `save()`s this gate.
- `approved_evaluation_evidence_sha256` is never passed to `read_by_sha`. It is only a string membership test on the gate payload.
- `authorization_id` is used as `gate_result_id`. The authorization object itself is not stored; only its canonical hash is `output_hash`. Replay needs the caller to resupply the full object.
- Missing gate raises `NotFoundError` from `AppendRepository.get` (357–358), not `InvalidJobDefinitionError`. Wrong gate becomes the Chinese contract error.
- Consumer does not check `input_scope_hash`, `affected_scope`, `recompute_scope`, or `authorizing_service` against any persisted service identity.
- Receipt reconstruction checks request `model` and `reasoning_effort` only (`binding_qualification_support.py` 897–904). Authorization binds `provider`, `base_url`, `model`, `reasoning_effort`, `max_tokens` (contract 62–64). `base_url` / `provider` / `max_tokens` are not proven by stored request bytes.

**Inference**

The read-side gate is real and fail-closed if no row exists. It is not an implemented adoption authority. Anyone who can `AppendRepository.save` a `GateResult` with this `gate_name` and a matching `output_hash` would unlock evaluation activation (`_AUTHORIZATION_WAIVED_REASONS` strips `evaluation_activation_absent` and `clinical_adoption_not_authorized`, `qualified_binding_selection.py` 43–46, 100–102). That is a future writer risk, not current activation.

`accepted: Literal[False]` on selection material is enforced (contract 121–129). Authorization does not flip clinical adoption flags. Distinguishing “calculation input unlocked” from “clinically adopted” is preserved on the object, not on the mixed control maps in §1.

**Recommendation**

- Keep the gate unsatisfiable until an owning service exists that: stores the authorization object or both hash kinds; `read_by_sha`s the evaluation evidence; binds `input_scope_hash` to job + evidence + routes; wraps missing gates as the same contract error.
- Do not treat a generic `GateResult` row as semantic proof.

**Uncertainty**

I did not inspect DB rows. Source shows no writer. A row created outside this tree would not be visible here.

---

### 4. Semantic rejection and population scope

**Evidence — rejection**

`pair_direct_selection_rejection_reasons` (53–103) rejects, among other things:

- any lane `unresolved_reasons`
- structural invalid / pending checks / non-present source policy
- `record_time` as clinical event date
- bad operand shapes
- missing second lane or `dual_agreement is False`
- non-admissible source, non-supported object, non-direct attribute (including `derivation_operand` / `context_only`)
- incompatible denial scope
- `date_range` unless `temporal_role == "event_date"`
- non-usable direct operand
- remaining unverified except the two authorization-waived codes

Dual agreement uses `public_agreement_key()` on structured fields only (`binding_qualification.py` contract 193–202). Dual **rejected** agreement still fails the field checks (`object_match_rejected`, etc.). Dual rejected/unresolved does not become usable fact truth. That part matches the contract docstring.

**Evidence — stamping vs checking**

`compose_qualification_summary` sets `semantic_dimensions_rechecked = list(SEMANTIC_DIMENSIONS)` whenever both lanes are present (803), not after checking each dimension. The consumer’s `semantic_dimensions_incomplete` test (82–83) therefore never fires on a complete dual payload. Individual field checks still run. This is false accounting, not a bypass.

**Evidence — population / subset**

- Official expected set = every trigger + exception identity on frozen components (`139–151`). Extra qualification identities become `identity_outside_current_frozen_expected_set` (396–405). Missing qualification rows become `identity_absent_from_qualification` (304–305, 356–357). No-candidate rows keep their reasons and clear facts (306–315, 358–367).
- Official usable path allows only one fact; more than one → `multiple_usable_pairs_without_selection_policy` (177–178). Professional judgment → `investigator_judgment_not_deterministic_value` (171–172).
- Control expected set = all four layers from `project_control_atom_identities` (`control_atom_binding_input.py` 7–44; consumer 154–157). `any` / `all` always return empty facts + `observation_scope_completeness_unverified` (199–200), even when qualification produced a complete candidate subset. `single` requires exactly one fact (197–198).
- Empty official lists are still keyed into `predicate_fact_ids_by_component` (339). `evaluate_component` with `fact_ids=[]` does **not** use type-bucket fallback (`expression.py` 481–493); it returns `UNKNOWN` / `fact_not_observed` or `professional_judgment_unverified`. Empty control lists become `UNKNOWN` / `selected_observation_missing` (`control_calculation_experiment.py` 42–43). Truth value is unverified, not false.
- Specific consumer reasons (dual disagreement, attribute match, scope completeness) are **not** passed into `calculate_component_review`. They remain only on `identity_outcomes` / `rejected_pairs` inside `qualification_materials`.

**Evidence — identity collapse**

Qualification is keyed by `predicate_identity_sha256` (role + component + predicate + time constraint). The calculation map is keyed by `predicate_id` (339). Two frozen identities that share `predicate_id` last-write the map. `evaluate_component` then requires `len(unique predicate_ids) == len(atoms)` (587–589) and will raise, or if IDs are unique across atoms it silently drops the first identity’s facts.

**Inference**

Semantic rejection of dual-rejected/unresolved pairs is structurally closed. Population coverage of frozen expected identities is fail-closed. Control `any`/`all` is stricter than `evaluate_control_layers_experiment`, which would compute over a supplied subset while disclaiming completeness (`control_calculation_experiment.py` 104–106). Reason codes are lost at the evaluator boundary. `predicate_id` collapse is a real identity bug if duplicate IDs exist in one component.

This is structural closure, not clinical effectiveness. Dual-lane `attribute_match == "direct"` plus authorization still does not prove object/time/source semantics for enrollment.

**Recommendation**

- Keep dual-rejected → unresolved.
- Pass identity unresolved reasons into the calculation result, or stop claiming frozen calculation preserves them.
- Key official maps by `predicate_identity_sha256` or fail at selection build if two identities share `predicate_id` in one component.
- Decide whether control `any`/`all` should remain unconditionally unresolved (matches “do not claim population completeness”) or may supply the qualified subset with an explicit incompleteness reason (matches the experiment layer). Do not do both.

**Uncertainty**

Whether live RuleSets actually duplicate `predicate_id` inside one component was not executed. `any`/`all` frequency in published catalogs was not counted.

---

### 5. Immutable source equivalence

**Evidence**

`assert_qualified_selections_match_review_context` compares:

- Official: `authority`, `episode`, `_frozen_fact` dumps of review facts vs frozen facts, component-id set vs clause pack, full frozen component dumps vs `rule_set` (`440–479`).
- Control: publication object equality, authority/episode, same `_frozen_fact` dump hash (`481–501`). Control does **not** compare component ids or atom-identity completeness; the factory fills every projected atom, and `_SEAL` blocks forged sealed objects.

`_frozen_fact` drops `inherited_from_fact_id`, `run_id`, `gate_id`, `source_candidate_ids`, `gate_ids`, `authority`, `supported_requirement_ids`, `created_at` (`predicate_binding_input.py` 153–169). Kept: clinical value fields, locators, `assertion_basis`, `stable_identity`, `revision`.

Pair reconstruction still requires pair bodies to equal frozen condition/fact/locator/document/policy material (`binding_qualification_support.py` 530–545) before a pair can be structurally valid.

`read_by_sha` integrity is byte equality to the digest (artifacts 107–112). Verify requires `rebuilt_dump == stored_summary` after JSON parse (1013–1014), so logical object equality is checked in addition to artifact bytes.

**Inference**

Fact equivalence for consumer-to-review binding is the frozen projection, not the full `ClinicalFactV2`. Two review facts that differ only in `supported_requirement_ids` / run / gates would still match. That matches the frozen-fact contract text and is **not** locator or excerpt equivalence. Nested `assertion_basis` is included; process metadata is not.

Clause-pack expressions are not dumped against frozen component expressions in `assert_*`. Mismatch would fail later in `evaluate_component` key checks (fail closed), not at the selection-binding gate.

**Recommendation**

If Codex wants immutable source equivalence to include requirement-index or gate lineage, compare those fields separately; do not fold them into `_frozen_fact`. If the frozen projection is the intended clinical identity, document that `supported_requirement_ids` drift is out of scope for this consumer.

**Uncertainty**

Whether `assertion_basis` or `ScalarValue` can carry extra nested mutable fields beyond the frozen model was not exhaustively field-walked beyond the published contracts.

---

### 6. Official and control selection integration (beyond §1)

**Evidence**

- Two families cannot live on one `QualifiedBindingSelectionMaterial` (contract 133–138). Dual integration must be two sealed objects or mixed maps.
- Control calculation requires complete atom-key coverage (`control_calculation_experiment.py` 111–113). The consumer builds that complete map, with `[]` for unresolved atoms (391).
- Official calculation requires complete component keys (`frozen_review_calculation.py` 181–185) and complete per-component `predicate_id` keys (`expression.py` 586–589). Empty lists are allowed and mean “no category fallback.”
- Executor after extraction still inlines lane reconstruction (`binding_qualification.py` 242–356) instead of calling `_reconstruct_qualification_lane_state`. Compose is shared (`349–356` vs support 1004–1011). Current checks are parallel (same hashes, `accepted is False`, last receipt, message hash, model, effort). Drift remains possible.

**Inference**

Per-family maps can be structurally complete, including empties. Joint sealed integration is not. Shared compose preserves prior summary behavior; duplicated reconstruction is the residual extraction risk.

**Recommendation**

Delete the inlined executor reconstruction or make it a single call into the support function. Do not claim extraction preserved behavior while two copies exist.

---

### 7. Default-disabled / non-activation

**Evidence**

- Qualification job `purpose` is `isolated_source_qualification`; summaries and artifacts require `accepted is False`, `authorized_clinical_adoption is False`, `clinically_qualified is False` (executor 259–286, 357–361; verify 973–994).
- Selection material locks those three flags to `False` (contract 121–129).
- `BindingQualificationJobExecutor` is not referenced from `app/workflow/`. Module docstring: “Not registered.”
- Design §17.1.1 and T5 both say this chain is not T5 close-out and not automatic adoption.

**Inference**

Source agrees the complete path is not activated. The defects above are in the unfinished consumer, not proof of silent production use.

---

### 8. What is actually closed vs what is not

| Claim | Status from source |
|---|---|
| Dual-rejected/unresolved agreement cannot become usable facts | Closed in `pair_direct_selection_rejection_reasons` |
| Empty official/control selections do not fall back to fact_type buckets | Closed in `evaluate_component` / control experiment |
| Frozen expected identities are enumerated; extras rejected | Closed |
| Receipt reconstruction of completed qualification vs stored summary | Closed, with explicit artifact vs logical split in verify |
| Persisted adoption authorization as an owning-service product | Not implemented (read-only gate, no writer) |
| Artifact vs logical hashes on authorization/selection contracts | Not closed; mixed kinds |
| Both official and control as sealed calculation inputs | Not closed; Sequence crashes; mix path is unverified control |
| Unresolved reasons survive into component/control truth reasons | Not closed |
| `predicate_id` vs `predicate_identity_sha256` accounting | Not closed if duplicate ids exist |
| Clinical effectiveness of dual-lane “direct” matches | Not proven; must not be claimed |

---

### 9. Objections to the current plan’s assumptions

1. “Sealed selections are an alternative input for frozen calculation of both families” is only true for one family at a time. Dual-family Sequence is a crash; mixed maps are a provenance hole.
2. “Persisted authorization gate linkage” is a read of a `GateResult` shape that nothing in this tree writes, and it binds mixed hash kinds.
3. “Immutable source equivalence” here is `_frozen_fact` equality plus publication/authority/episode, not excerpt-level or requirement-index equivalence.
4. Stamping `semantic_dimensions_rechecked` is not a recheck.
5. Conservative `any`/`all` emptying is not the same as the experiment layer’s “compute over supplied subset.” Pick one contract.

---

### 10. Proposed remediation (bounded)

1. Fail closed: if any sealed selection is passed, all families required by the frozen review must be sealed; reject raw sibling maps.
2. Fix Sequence hashing: record every `(family, selection_sha256, frozen_input_sha256)`; never read `.material` on a Sequence.
3. Split artifact vs logical hashes on `QualificationAdoptionAuthorization` and `QualifiedBindingSelectionMaterial`; validate both against `verify_completed_binding_qualification`.
4. Reconstruct `approved_evaluation_evidence_sha256` with `read_by_sha` or stop calling it persisted evidence.
5. Wrap `NotFoundError` in `_validate_authorization`.
6. Reject duplicate `predicate_id` inside one component at selection build.
7. Either thread unresolved reasons into calculation outputs or document that frozen calculation reason codes are evaluator-generic.
8. Deduplicate executor reconstruction onto the support function.
9. Do not create a `binding-adoption-authorization` writer until 1–5 are done.

---

### 11. Decision points for Codex

1. Is mixed “sealed official + explicit control maps” a temporary adapter or a defect? This review treats it as a defect.
2. Should `authorization.summary_sha256` be logical L (current consumer) or artifact A (current checkpoint name)?
3. Should control `any`/`all` stay unconditionally unresolved, or supply the qualified subset with an incompleteness flag?
4. Is `_frozen_fact` the approved equivalence surface, including dropping `supported_requirement_ids`?

---

### 12. Bounded questions for Codex

1. **Hash kind:** When an owning service later issues `QualificationAdoptionAuthorization`, must `summary_sha256` equal `verify[...]["summary_sha256"]` (logical) or `verify[...]["summary_artifact_sha256"]` (store key)? This controls whether a checkpoint-faithful issuer can ever pass `_validate_authorization`.
2. **Dual-family API:** Should `calculate_frozen_review` accept only a Sequence of sealed objects whenever `control_publication` is present, and reject `control_input`/`control_selections` kwargs in that mode? If Codex wants the mix path kept, that is an explicit provenance exception and should be labeled non-receipt-verified on `FrozenReviewCalculation`.
3. **Evaluation evidence:** What bytes is `approved_evaluation_evidence_sha256` supposed to name (isolated eval artifact, comparison, something else)? The consumer never opens it, so I cannot verify closure.

**Safe provisional path (until Codex answers):** do not issue authorization; do not call `calculate_frozen_review` with a Sequence of both families; do not treat mixed maps as qualified; keep `accepted=false`; treat current consumer as structurally incomplete, not clinically usable.

---

### Categories recap

- **Evidence:** file/line observations above; `read_by_sha` byte check; no writer for `binding-adoption-authorization`; Sequence `.material` access; predicate return that forwards control maps; empty-list evaluator behavior; mixed logical/artifact hashes in verify vs authorization.
- **Inference:** dual sealed path cannot complete; mix path can complete with unverified control; authorization is currently unsatisfiable from in-tree services and would be easy to mis-issue on hash kind; rejection of dual-rejected pairs holds; empty selections stay UNKNOWN; this is not clinical proof.
- **Recommendation:** fail-closed dual-family API, split hashes, no issuer yet, keep default-disabled.
- **Uncertainty:** no runtime/DB; no live RuleSet duplicate-`predicate_id` proof; no actual GateResult rows; evaluation-evidence artifact identity unknown.

Resume point if Codex continues this session: answer questions 1–3, then I can re-audit only the chosen hash/API contract against the same files.
