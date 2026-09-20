I'll start with the assigned conference context and plan, then independently audit EvidenceRequirement attribution, frozen qualification, and guessed-source acceptance.Context is loaded. Next I’ll read the contract definitions, deconstructor/gate/qualification path, and the original T5/R3 requirements.I'll read the role prompt, linked execution packet, design §17, and the contract/source files next.Next I’ll inspect the live contract fields and how predicate refs flow through hydration, assembly, freeze, and qualification.I’ll now read the six live modules in full relevant sections rather than relying on the worker report.Remap and qualification look like the main risk. I’ll inspect the gate, prompt version, projections, and the exact diff next.# Conference Output: r05-policy-links-review-20260914 - evidence_single_object

## Output

Role `evidence_single_object` / `grok` / `grok-build` / `grok-4.6`. Source-only review of official `EvidenceRequirement` predicate attribution through semantic wire → hydration → assembly → freeze → qualification. No app import, tests, DB, model, browser, or production write. Formal acceptance remains with Codex. Runtime behavior is **UNVERIFIED**.

This pass independently audited the objective, source list, constraints, edge cases, and likely objections before drafting. Worker reports were not treated as proof.

---

### Scope actually read

- Assigned: `context/r05-policy-links-review-20260914_conference_context.md`, `plans/codex_main_venue_r05-policy-links-review-20260914.md` (plan still TODO).
- Design: `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17.1, §17.1.1, §17.2, §17.3.
- Recovery: `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` T5 (2026-09-14 notes).
- Linked execution context (for the assigned change, not as proof): `context/r05-policy-predicate-links-20260914_execution_context.md`.
- Current source: `app/domain/contracts/rules.py`, `agent_io.py`, `predicate_binding.py`, `binding_qualification.py`; `app/agents/protocol_deconstructor.py`; `app/protocols/deconstruction_gate.py`; `app/services/binding_qualification_support.py`, `binding_qualification.py`, `predicate_binding_input.py`, `protocol_deconstruction_executor.py`; `app/storage/codecs.py`, `repositories.py` (`_save_requirement_row` / `get_evidence_requirement`); `app/projections/control_evidence_requirements.py`; `app/llm/binding_qualification.py`; `app/agents/protocol_semantic_transport.py`.
- Git observation: dirty tree; `rules.py` / `agent_io.py` / `protocol_deconstructor.py` / `deconstruction_gate.py` modified; `predicate_binding.py` and `binding_qualification_support.py` untracked in this worktree. Reviewed current files, not a reset HEAD.

Did not run `py_compile`, tests, or job replay. Did not treat `runs/execution/r05-policy-predicate-links-20260914/worker_01.md` as evidence of correctness.

---

### Evidence (source facts)

**E1. Official optional `predicate_ids` exist and omit when empty.**  
`EvidenceRequirement.predicate_ids` is `list[str]` default `[]`. Serializer pops the key when empty (`rules.py` 296–307). Validator rejects blank strings, duplicates, and any nonempty list on procedure or control origin (316–322). `SemanticEvidenceRequirement` mirrors omit-when-empty ( `agent_io.py` 121–137). Storage encodes the full contract via `model_dump` (`codecs.py` 29–38; `repositories.py` 1619–1634), so a historical payload without the key loads as `[]` and re-dumps without the key.

**E2. Membership is the union of trigger and exception IDs, not a stored role.**  
`RuleComponent` (348–365), `SemanticRuleComponent` (149–170), `FrozenRuleComponent` (290–303), and the gate (2942–2976) all check `predicate_id in {atoms from expression ∪ exception_expression}`. After wire resolve, only `predicate_ids` remain; `role` is discarded. A requirement may name a mix of trigger and exception atoms.

**E3. Semantic uniqueness is conditional; published uniqueness is not.**  
`SemanticRuleComponent` rejects duplicate atom IDs in the component **only if** any requirement has `predicate_ids` (157–159). `RuleComponent` does not check intra-component uniqueness. `RuleSet` requires globally unique predicate IDs (418–421). `FrozenRuleComponent` always rejects duplicate trigger/exception IDs (274–278).

**E4. Compact wire uses positional `predicate_refs`; system IDs are generated, then remapped.**  
Wire schema (`protocol_deconstructor.py` 731–746): optional array, `minItems: 1`, `{role, group_index, atom_index}`, `additionalProperties: false`. `_resolve_wire_predicate_refs` (2171–2216) rejects empty array, unknown keys, invalid role, non-int/bool indexes, duplicate `(role, group, atom)`, missing exception DNF, out-of-range group/atom. It never invents a link for omitted refs. Atom order is existence → scalar → set (`2095–2100`, `2159–2161`). `_system_predicate_id` hashes `dnf-v1` + prefix + group_key + atom_key (2025–2041). Hydration copies resolved IDs only when nonempty (2340–2341). Assembly remap (`2664–2726`) builds `predicate_id_remap[original] = current` per component while `used_predicate_ids` is RuleSet-global; requirement IDs are rewritten through that dict. `semantic_candidate_from_draft` copies the remapped IDs (2961).

**E5. Wire version, gate version, and qualification contract versions were not bumped.**  
Compact schema still `wire_version: {const: "dnf-v1"}` (892, 939). `_COMPACT_WIRE_COMPONENT_CONTRACT` still says providers must not emit node refs or formal predicate identity (406–407) and does not mention `predicate_refs`. `_SYSTEM_CONTRACT` does mention `predicate_refs` (337). `protocol_prompt_template_sha256` hashes prefix + `_SYSTEM_CONTRACT` + interpretation + formal-id + compact-wire contracts (414–426), so the instruction change **does** change the computed template hash. Executor still stamps `prompt_version_id="protocol-deconstructor/v1"` and `schema_version_id="protocol-deconstruction-draft/v1"` (executor 1032–1036). `DECONSTRUCTION_GATE_VERSION` remains `protocol-deconstruction-gate/2026-09-02.2` (gate 64) despite a new blocking issue `EVIDENCE_PREDICATE_REF_INVALID` (2970–2975). Integrity reuse keys only that version string (executor 1161–1171). Qualification remains `binding-qualification-job/v2`, pair/summary/prompt `v2` (`binding_qualification.py` 25–27; support 53).

**E6. Qualification `present` is explicit-ref coverage of retained rows, not source verification.**  
`_source_policies_for_predicate` (support 118–162): empty refs are kept as shells; nonempty refs that omit this predicate are skipped; if any retained row lacks `predicate_ids` → `"unattributed"`; if none retained → `"missing"`; if every retained row names this ID → `"present"`. Comment: do not infer from singleton/`fact_type`. Multiple retained explicit rows stay in the list; `required_source_types` is still `sorted(set(...))` across those rows (154). Official path never calls `_policy_unknown` and never returns `"ambiguous"`. Control path still can (`206–210`). Compose (`binding_qualification.py` 178–179) only appends `source_policy_{status}` when status ≠ `"present"`. `structurally_valid` does not require `"present"`. Dual agreement is not gated on it. Clinical flags remain `Literal[False]` on the qualification contracts.

**E7. Frozen inputs carry the published requirement objects, including `predicate_ids` when present.**  
`_frozen_component` copies `list(component.evidence_requirements)` (predicate_binding_input.py 133). Component identity hash dumps those objects via `model_dump(mode="json")` (predicate_binding.py 191–196). Empty `predicate_ids` are omitted, so legacy frozen bytes without the key stay stable. Nonempty refs change `component_identity_sha256` / `frozen_input_sha256`. Frozen validator rejects unknown refs (294–303). Pair `pair_id` hashes frozen_input_sha256 and identities, **not** `source_policy_status` (binding_qualification.py 44–65).

**E8. Procedure/control consumers do not get official `predicate_ids`.**  
Procedure assembly constructs `EvidenceRequirement` without the field (deconstructor 2820–2826). `shared_control_requirements` never sets it (control_evidence_requirements.py 104–124). Domain validator would reject if they did (rules.py 321–322).

**E9. Compact wire still defaults omitted official source-policy booleans.**  
Hydration (`2328–2333`): `allows_screening_record_transcription` defaults `True`, `requires_contemporaneous_objective_source` defaults `False` when the model omits them. Official contract still uses those same defaults and forbids `None` on non-control rows (rules.py 287–288, 328–334). Control projection refuses missing `source_policy` (control_evidence_requirements.py 65–66).

**E10. Gate issue is redundant with contract construction for pydantic drafts.**  
`EvidenceRequirement` already rejects duplicate IDs in one list; `RuleComponent` already rejects unknown IDs. A `ProtocolDeconstructionDraft` that validates `proposed_rules` cannot carry the condition `EVIDENCE_PREDICATE_REF_INVALID` tests. The issue is still default level `"阻止发布"`.

**E11. Product compact transport is live; non-compact remains a second schema.**  
`ProtocolSemanticTransport.uses_compact_wire_contract` is true for local structured backends (protocol_semantic_transport.py 383–385). `_uses_compact_wire_contract` defaults **False** if the attribute is missing (deconstructor 3681–3682). Non-compact prompt appends `ProtocolSemanticDeconstructionCandidate.model_json_schema()`, which exposes `predicate_ids`, not `predicate_refs` (429–435, 1309).

**E12. T5 still treats official per-predicate policy attribution as an open gap, and forbids calling accepted=false summaries a closure.**  
Recovery plan T5 (2026-09-14): next material gap is official per-predicate policy attribution, evaluated semantic proof, control clinical consumption, and batch formal publish. Qualification is unregistered construction.

---

### Inference (not observed at runtime)

**I1. Highest-impact defect: `present` is still not 17.1.1 source qualification, and the visible-shell rule likely makes it unreachable on real official components.**  
Design §17.1.1 step 3 requires code checks of identity, excerpt, value, unit, date precision, and allowed source, and forbids guessed attribution. Current `"present"` only means “every *retained* requirement row explicitly names this predicate.” It does not admit a source.  
Worse for the stated goal: a component with one explicitly attributed lab requirement **and** one unattributed “病史/病历” shell keeps **every** predicate `"unattributed"` (E6). That is the common official shape. The new field then cannot turn T5’s 官方逐谓词政策归属 into qualification `"present"` unless every sibling requirement is also fully attributed. That is not singleton-guessing (the previous failure mode), but it is a coverage bar that the execution prompt did not state, and it will look like the feature “landed” while consumers still never see `"present"`.

**I2. Historical qualification identity is now ambiguous under the same v2 names.**  
Previous construction (still the same job/pair/summary version strings) treated a single component-level requirement as `"present"`. Current code treats that same legacy object as `"unattributed"`. Frozen dump does not change (empty `predicate_ids` omitted), so `pair_id` and `frozen_input_sha256` stay the same. Replaying an old v2 summary that recorded `"present"` against current `expected_pair_frozen_bodies` would diverge on `source_policy_status` without any version bump. That is a request-identity break, not a serialization-byte break.

**I3. Remap last-wins is a latent identity bug, currently fenced for attributed wire output.**  
`predicate_id_remap[original] = current` overwrites if the same original ID appears twice in one component (deconstructor 2686). Counterexample: trigger atom `P` keeps `P`; exception (or later trigger) atom also originally `P` remaps to `P:component:02`; a requirement listing `["P"]` follows the **second** atom. Wire-generated IDs plus Semantic uniqueness-when-refs-exist make this unreachable on the compact path. It is reachable if uniqueness is later relaxed, or if a non-compact model reuses IDs and somehow bypasses the semantic check. Assembly should remap by atom instance, not by original-id dict.

**I4. Positional refs cannot detect medically wrong but in-range indexes.**  
`group_index`/`atom_index` are structural. Empty `existence_atoms` makes `atom_index=0` the first scalar. A model that counts per-array indexes, or counts NOT-wrapped tree nodes, emits a legal ref to the wrong atom. Code will hydrate, freeze, and may mark `"present"`. That is attribution, not semantic truth. Compact contract’s “do not emit node refs / formal predicate identity” also fights `_SYSTEM_CONTRACT`’s `predicate_refs` instruction; likely effect is omission (safe unattributed), not guess.

**E/I boundary on guessed source policy.**  
Omitted official wire booleans still become True/False (E9). That is guessed **source-policy content**, distinct from guessed **predicate attribution**. Control already refuses that guess. Official still does not. This is current source, not shown as introduced solely by `predicate_refs`, but it is in scope for “no guessed source acceptance.”

**I5. Gate version and wire_version conservatism are inconsistent with the control atom_refs precedent.**  
§17.3 bumped control wire/prompt/gate when adding `atom_refs`, while keeping historical omission. Official DNF kept `dnf-v1` and gate `2026-09-02.2`. Old responses without `predicate_refs` still parse (additive). New prompt hash changes, so *new* deconstruction jobs will not silently reuse an old template hash. Gate cache keyed on an unchanged version could reuse an old `evidence_coverage` pass; for historical drafts without `predicate_ids` the new check would not fire anyway (E10). The miss is process/identity, not a live false-publish of invalid refs.

**I6. `present` plus dual_agreement can still look source-qualified to a later isolated consumer.**  
Compose always keeps `clinical_adoption_not_authorized` and `evaluation_activation_absent`. That blocks auto-adoption. It does not stop `"present"` + `dual_agreement=True` + `structurally_valid=True` from being the durable flags this stage exists to emit. Flattened `required_source_types` is a set-union across retained policies; the prompt also sends the full `source_policies` list. A consumer that only reads the union can treat two mandatory sources as OR, which the support comment claims not to invent.

**I7. Construction is still an unregistered producer.**  
No finding here that the field is wired into `evaluate_bound_component_experiment`, formal publish, or live executors. T5 already records that gap. Usefulness of the field is limited to future qualification inputs after republish with links.

---

### Recommendation

Treat the current change as **construction of an optional attribution channel**, not as closed official per-predicate source policy, and not as T5 progress beyond “the field exists.”

Concrete remediations, in order:

1. **Split attribution status from source-policy status.** Keep `"unattributed"` / `"missing"` / explicit-link-present as an *attribution* enum. Do not reuse `"present"` for 17.1.1 step 3. Official `"present"` must not mean excerpt/unit/date/allowed-source verified. Until those checks exist, remaining_unverified should still carry a source-verification pending reason even when links are explicit.
2. **Decide the shell rule explicitly (Codex).**  
   - If mixed attributed + unattributed siblings must stay `"unattributed"`, document that `"present"` requires *complete* per-requirement refs on the component, and do not advertise per-predicate policy as available on typical IN/EX components.  
   - If an explicit subset should be recognizable, return the attributed rows as attributed and keep unattributed shells in a separate list/status, never OR them and never drop them.
3. **Bump identity versions that changed meaning:** `binding-qualification-job` / pair / summary (at least), and explain that v2 `"present"` on official predicates is not the same predicate as current `"present"`. Do not replay old v2 summaries.
4. **Fix remap to instance identity:** map `(expression_root, atom_order) → new_id`, or remap requirement IDs after uniqueness rename by walking atoms in the same order used to assign IDs. Reject duplicate original IDs in a component whenever any ref exists (already true semantically; do it on `RuleComponent` too).
5. **Fail closed on omitted official source-policy booleans in *new* semantic output**, or persist explicit unknown; do not keep `.get(..., True/False)` as clinical policy. Legacy published rows without new keys stay as they are.
6. **Align compact prompt with the schema:** mention `predicate_refs` in `_COMPACT_WIRE_COMPONENT_CONTRACT`, or the field will be omitted in practice.
7. **Bump `DECONSTRUCTION_GATE_VERSION` if the new issue code is considered part of gate semantics;** otherwise delete the dead check and keep the version. Do not cache “pass” across a real issue-set change.
8. **Do not enable adoption, registration, or formal consume.** Keep the stage disabled. Attribution ≠ semantic proof.

---

### Uncertainty

- Runtime: whether compact transports actually emit `predicate_refs`; whether PromptVersion rows in the product DB match the new template hash; whether any stored qualification v2 summaries exist with singleton `"present"`. Not verified (no DB/job replay).
- Whether Codex *intended* the control-style visible-shell bar for official components. Execution text says never infer from singleton/`fact_type` and preserve all applicable policies; it does not say `"present"` requires total component attribution.
- Non-compact live use: transport defaults compact=False if the flag is missing. Frequency in product routes unverified.
- Historical `EvidenceRequirement` payload hashes after the dirty `control_origin` serializer: read path hash-checks stored bytes, so old rows still load; a rewrite would omit new empty keys. No DB sample hashed here.
- Model independence of the linked executor (`pi/cursor/default`) is unverified, as the conference context already notes.

---

### Objections, decision points, bounded questions for Codex

**Objections**
- The plan’s success path (“explicit refs → qualification may recognize attributed published policies”) is only true when *every* retained sibling is also explicit. That is not how official components are written.
- Keeping `wire_version='dnf-v1'` and qualification `v2` because the field is optional ignores that **`present`’s meaning changed**. Optional-field parse compatibility ≠ identity compatibility.
- Worker claim that “prompt template hash will change for new PromptVersion registration” is only half right: `protocol_prompt_template_sha256` does change, but `prompt_version_id` stays `protocol-deconstructor/v1`. Consumers keying on the id will collapse instruction revisions.
- `EVIDENCE_PREDICATE_REF_INVALID` is not independent evidence of production safety; pydantic construction already refuses those drafts.

**Decision points (Codex, not this role)**
| Decision | Safe provisional path until answered |
|---|---|
| Shell rule: complete-component refs vs attributed-subset + listed shells | Keep `"unattributed"` for mixed components; do not treat current `"present"` as available in product |
| Whether to bump qualification v2 after `present` semantics changed | Do not replay or compare old v2 official `"present"` records |
| Whether omitted official source-policy booleans may default | Do not call those defaults “no guessed source”; they remain guessed content |
| Gate version bump vs delete dead check | Do not cache old gate passes across a real issue-set change; current new check is redundant |

**Bounded questions**
1. For an official component with `R1.predicate_ids=[P_trigger]` and `R2.predicate_ids=[]`, should `P_trigger` be `"present"` with `R2` listed as an unattributed extra policy, or `"unattributed"` as now? This decides whether T5’s 官方逐谓词政策归属 can ever fire without forcing models to attribute every sibling.
2. Must `binding-qualification-pair/v2` (and job/summary) increment because official `"present"` no longer means “exactly one component requirement”? If no, how should old singleton-`"present"` summaries be distinguished?
3. For *new* official semantic output, should omitted `allows_screening_record_transcription` / `requires_contemporaneous_objective_source` fail closed instead of True/False? Control already fails closed on missing policy.

Until those are answered: keep the field, keep omit-when-empty serialization, keep membership checks, do not enable qualification consumption, and do not describe legacy one-requirement components or mixed-attribution components as source-qualified.
