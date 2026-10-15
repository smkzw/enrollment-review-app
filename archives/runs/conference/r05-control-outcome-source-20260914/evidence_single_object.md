I'll start from the assigned conference packet and read only the authorized context before reviewing the frozen control-outcome evidence.The packet names the frozen projection and official-predicate files as the source of truth; I’ll read those next and keep extra lookups inside this worktree.The projection files are in; next I’ll read the layer-evaluation contracts and the official predicate path so I can test modality, unknown-vs-missing, and publication boundaries.I’ll now read the official predicate evaluators and the frozen-review consumer, then pull only the adjacent obligation-group definitions needed for attribution.The official empty-selection path and out-of-window FALSE look like the highest-risk misstatements; I’ll confirm identity-outcome statuses, time evaluation, and whether `kind` is dropped at the projection boundary.# Conference Output: r05-control-outcome-source-20260914 - evidence_single_object

## Output

Role: `evidence_single_object` (重要证据审阅). Advisory C03 source review only. Not clinical, regulatory, or publication acceptance.

Read in this pass: conference context; Codex venue plan; design §17.1.1–17.3; plan T5; `app/projections/control_review_outcome.py`; `app/projections/control_calculation_experiment.py`; `app/domain/control_layer_evaluation.py`; `app/domain/contracts/control_evaluation_spec.py`; adjacent slices of `app/domain/contracts/protocol_controls.py` (modality/kind/groups); `app/domain/expression.py` (`evaluate_component`, `_evaluate_atomic`, `_evaluate_logical`, `_merge`, `_evaluate_time`); `app/domain/gates/assessment.py` (`derive_gate_gap_types`, `derive_component_decision`); `app/services/component_review.py`; `app/services/frozen_review_calculation.py`; adjacent exact definitions in `app/projections/control_operand_calculation.py`, `app/projections/control_atom_binding_input.py`, `app/domain/contracts/qualified_binding_selection.py`, `app/services/qualified_binding_selection.py` (`_select_facts_for_identity`, identity outcomes), `app/services/eligibility_review_projection.py` (`_summary_gaps`), and deconstructor contract text on proposition polarity. No tests, imports, product calls, or edits.

---

### Highest-impact defect

Official predicate evaluation still treats **every selected observation outside its time window as the clinical condition being false**. The new control experiment does not. Frozen review then turns that FALSE into an official component decision.

**Evidence**

- `app/domain/expression.py` `_evaluate_atomic` (approx. 494–509): after time filtering, if no in-window fact remains, the atom returns `TruthValue.FALSE` with the time reason codes and `used_fact_ids` of the out-of-window facts. `_evaluate_time` (280–295) always uses `fact.effective_date`; there is no `time_purpose` (`event_membership` vs `interval_condition` vs `source_validity`).
- `app/projections/control_calculation_experiment.py` `_conditional_observation` (74–78): `time_purpose == "event_membership"` and temporal FALSE → `UNKNOWN` + `observation_out_of_window`. Interval conditions may stay TRUE/FALSE. `source_validity` never becomes an atom verdict (71–73).
- Design §17.2: “事件窗口外不能证明临床条件不成立；明确间隔条件可计算真/假.” That sentence is written next to the control experiment, but the same clinical claim is what official IN/EX consume.
- `app/domain/gates/assessment.py` `derive_gate_gap_types` (284–290): time reasons on a FALSE trigger are discarded. `derive_component_decision` (334–365) then emits `INCLUSION_NOT_MET`, `EXCLUSION_NOT_TRIGGERED`, or `REQUIREMENT_NOT_MET` when blocking gaps are empty.
- This is not limited to the leftover explicit-map path. Qualification `usable` requires a non-empty fact list (`qualified_binding_selection.py` 92–94). A single sealed, in-scope fact that is merely out of window still hits `_evaluate_atomic` and can become a definitive official decision.

**Inference**

A valid dated record can be used to **prove a criterion false** instead of remaining unverified. For exclusion, that hides a possible trigger (“not triggered”). For inclusion/required procedure, it reports not met. The control projection was built to prevent exactly this substitution; official predicates were not given the same split.

**Recommendation**

Do not publish or activate frozen official decisions until `_evaluate_atomic` distinguishes event membership from interval conditions the same way `_conditional_observation` does: out-of-window event membership → `UNKNOWN` + a dedicated reason (reuse `observation_out_of_window` or a new official code), never FALSE; only an explicit interval predicate may return FALSE. Keep the supporting fact identity on the UNKNOWN result so the record is not dropped.

**Uncertainty**

I did not run cases. Official `TimeConstraint` on `AtomicPredicate` has no `time_purpose` field, so Codex must decide the default when purpose is absent: fail closed to UNKNOWN, or require a new official spec field. I cannot tell from source alone how many published official predicates are lookback filters vs true interval conditions.

---

### Challenge 1 — unknown vs missing on official empty selections

**Evidence**

- Qualification identity status is only `usable` | `unresolved` (`qualified_binding_selection.py` 81–99). `usable` cannot be empty. There is no “verified absence” status.
- Frozen review copies unresolved official identities into `unverified_predicate_ids` (`frozen_review_calculation.py` 200–220). `evaluate_component` then returns `UNKNOWN` + `observation_unverified` and forbids non-empty selections on those ids (600–608).
- The same function, without that flag, evaluates an explicit empty list as `fact_not_observed` or `professional_judgment_unverified` (487–493).
- `REASON_GAPS` (`assessment.py` 206–218) maps `observation_unverified` → `OBSERVATION_UNVERIFIED` and does **not** list `fact_not_observed`. Unknown trigger with only unmapped reasons becomes `RECORD_INCOMPLETE` (299–308).
- `calculate_frozen_review` still accepts raw `predicate_fact_ids_by_component` when `qualified_binding_selections` is None (88–91, 137–147).

**Inference**

The same empty list means two different clinical claims depending on the caller: “not yet qualified” vs “record not observed / chart incomplete.” Design §17.2 and T5 require that unverified empty choice is not “原件没有记录.” The sealed path honours that; the still-live explicit path does not. Qualification also cannot represent “search closed, absence proved,” which T5 already lists as an open gap (“不能以全部UNKNOWN代替”).

**Recommendation**

1. Reject the raw explicit-map input on `calculate_frozen_review` until it carries a per-predicate tag `{unverified, verified_absent, selected}` with the same hash closure as qualification materials.
2. Map `fact_not_observed` explicitly; do not let it fall through to `RECORD_INCOMPLETE`.
3. Keep detailed qualification `unresolved_reasons` on `predicate_evaluations` (design: “完整逐项原因同时保留”). Today they collapse to one `observation_unverified` code; the detail exists only on `qualification_materials`.

---

### Challenge 2 — official multi-observation hides valid records as source conflict

**Evidence**

- `_evaluate_atomic` (528–540): after time filter, distinct `(value, unit, polarity)` **or** any `conflict_group_id` → `UNKNOWN` + `source_conflict`.
- Design §17.2 (control paragraph): do not default ANY/ALL, do not pick the first, and **do not claim source conflict merely because results differ**.
- Qualification for official predicates rejects `len(fact_ids) > 1` as `multiple_usable_pairs_without_selection_policy` (184–185). Conservative, and it does not invent conflict.
- Official atoms have no `observation_policy`. Explicit maps can still pass two facts and take the conflict branch.

**Inference**

Two legitimate readings become an unusable conflict on the explicit path, which hides both records. The sealed path instead leaves them unresolved — better, but then no official predicate can consume more than one fact at all.

**Recommendation**

Give official predicates the same observation-policy object, or refuse multi-select in `evaluate_component` with `observation_selection_unverified` instead of `source_conflict` unless a real conflict group is attached. Do not treat value disagreement as source conflict.

---

### Challenge 3 — control outcome projection can misstate fulfillment and hide records

**Evidence**

- `project_control_review_outcomes` (80–99): `activation == FALSE` → `not_applicable` regardless of `observation_truth`; else UNKNOWN activation or UNKNOWN truth → `unverified`; else `fulfilled` iff `truth == TRUE`.
- `reason_codes` is `["activation_unverified"]` or `[]`. Observation reasons live only in `ControlReviewOutcome.unresolved_atoms`. `unresolved_atom_identities` is **only the obligation atom itself** if it is UNKNOWN — not the applicability/trigger/exception atoms that made activation UNKNOWN. Comment at 86–88 says this is to avoid sibling misattribution; it also omits **related** prerequisites.
- `ControlObligationOutcome` has `modality` and protocol `source_span_ids` / `source_excerpts`, but **no `kind`**, **no used `fact_id`s**, **no locator ids**. Supporting facts exist on `ControlCalculationExperiment.observations` / `calculations` only.
- Spec contract (`control_evaluation_spec.py` 34–38) and deconstructor text: the predicate already expresses “本原子成立”; kind must not invert. Projection nevertheless labels TRUE as `fulfilled`. Prohibit kinds are not on the outcome. Recommended and mandatory share the same status vocabulary.
- Qualification `any`/`all` always returns unresolved `observation_scope_completeness_unverified` (206–207). The experiment is allowed to aggregate a **supplied** set (`control_calculation_experiment.py` 104–105). Sealed consumption therefore never presents those facts; calculation reasons become `selected_observation_missing` (42–43), which is a different claim.

**Inference**

1. **Polarity:** TRUE→`fulfilled` is safe only if every published prohibit predicate is already “obligation satisfied” (no prohibited event). If a deconstructor emits EXISTS/EQ on the prohibited event itself, a documented violation is labelled fulfilled. Kind is then unavailable to a `control_outcomes` consumer to catch it.
2. **Modality:** `unfulfilled` + `recommended` is not a blocker in design §17.3 (“不把推荐事项提升为排除标准”), but status does not encode intensity. A status-only consumer will promote recommendations.
3. **Hiding records:** `not_applicable` keeps `observation_truth` on the object but drops fact identity. A UI/report that filters on `status` will hide a TRUE prohibit observation that was deactivated by a waived trigger or failed applicability. Activation UNKNOWN also hides which branch is unproved.
4. **any/all:** sealed path hides qualified pairs behind a missing-observation reason.

**Recommendation**

Extend `ControlObligationOutcome` (still non-accepted) with: `kind`; `used_fact_ids`; `observation_reason_codes`; `activation_unresolved_atom_identities` limited to **this group’s** applicability/selected remaining-or-original trigger/exception route (not unrelated sibling groups); keep `modality` as a required consumer field for any later gap/decision mapping. Do not map recommended/best_effort `unfulfilled` to a blocking official-like decision. For `any`/`all`, either pass the supplied set into the experiment and keep `observation_scope_completeness_unverified` as a **parallel** coverage flag (not as empty selection), or keep them unresolved but copy the qualification reason through instead of `selected_observation_missing`.

---

### Challenge 4 — branch attribution in layer composition (mostly sound, two edges)

**Evidence**

- Default obligations use `remaining_trigger_branches` (exception locally waives named branches). Replacement obligations use original triggers + exception route (`control_layer_evaluation.py` 141–164). Exception UNKNOWN does not waive (`_not` of UNKNOWN is UNKNOWN; no-trigger route comment 159–161).
- When triggers exist, default `route` is hard-coded `TRUE` (161); waiver is only via `remaining`. That is consistent if every exception that should kill a branch is listed in `waives_trigger_branch_ids` (publication requires waives when triggers exist).
- Unscoped default obligation (`applies_to_trigger_branch_ids` empty) activates if **any** remaining branch is TRUE. A waived branch plus a still-true sibling keeps the default group active **and** can activate a replacement for the waived branch.
- `obligation_group_truth` is a descriptive AND and is **not** used by the outcome projection. Each atom is scored alone. No control-level eligibility OR/AND is inferred (matches the projection docstring).

**Inference**

Composition is careful about exception-unknown ≠ waived and about not inverting prohibit kinds. The remaining risk is **unscoped default + partial waiver**: both default and replacement groups can be active together. That may be correct, but the outcome list will show two live obligation groups without saying they are alternative routes. A consumer could read both as concurrent mandatory duties.

**Recommendation**

On each outcome, persist `activation_route`: `default_remaining` | `exception_replacement`, plus the trigger-branch ids actually used. Do not add a rolled-up control verdict.

---

### Challenge 5 — source identity and formal publication boundary

**Evidence**

- Control identities hash publication + layer + group/atom index + atom payload (`control_atom_binding_input.py` 28–42). Official codes are forbidden on protocol controls (`protocol_controls.py` 115–118, 263–266). Projection keys by `protocol_control_id`, not IN/EX.
- Outcome `source_span_ids` are **protocol** spans, not subject locators. Naming them `source_*` on a review-outcome object invites confusion with evidence identity.
- `ControlCalculationExperiment.accepted` is `Literal[False]`. `QualifiedBindingSelectionMaterial.accepted` / `authorized_clinical_adoption` / `clinically_qualified` are false. `FrozenReviewCalculation` has **no** such flag, and `FrozenComponentCalculation.result.decision` is a full `ComponentDecision` (`INCLUSION_MET`, `EXCLUSION_TRIGGERED`, …) from `calculate_component_review`.
- Official `evaluate_component` sets `applicable=TRUE` always (`expression.py` 81–82, 620–628). `RuleComponent` has no applicability layer. Population-false therefore becomes inclusion-not-met / exclusion-not-triggered, not `NOT_APPLICABLE`.
- Control experiment `accepted=False` is still attached as `control_outcomes` on the same frozen calculation object that carries official decisions.

**Inference**

The new projection is not a second eligibility engine, and it does not mint IN/EX codes. The publication leak is the **official half** of the same frozen object: it looks like an accepted verdict, while the control half is explicitly non-accepted. Protocol excerpts on the control outcome are not proof of a subject record. Always-TRUE official applicability can misstate “this clause does not apply to this population” as a negative eligibility result.

**Recommendation**

Put `accepted: Literal[False]` on `FrozenReviewCalculation` and on each `FrozenComponentCalculation`. Rename outcome protocol fields (`protocol_span_ids` / `protocol_excerpts`). Do not let any report renderer print `ComponentDecision` or `status=fulfilled` as a signed review. Official applicability needs an explicit layer or a documented encoding inside the trigger; until then, population failure must not be a definitive not-met/not-triggered decision.

---

### What this slice does well (evidence, not praise as acceptance)

- Control empty deterministic selection → `UNKNOWN` + `selected_observation_missing`, not FALSE.
- Semantic/investigator control atoms never take selected facts as proof (`control_calculation_experiment.py` 40–41, 148–158).
- `record_time` is not used as a clinical calendar date (`control_operand_calculation.py` 100–107).
- Conflict groups mark `source_conflict` without treating mere value disagreement as conflict on the control path.
- Frozen review refuses mixed manual + sealed inputs, requires both official and control families when a catalog exists, and requires `review-requirements-scope/v1`.
- Gate logic does not lift UNKNOWN sibling reasons onto a decisive FALSE ALL trigger (284–290). `_merge` still **copies** sibling facts/reasons onto that FALSE result (`expression.py` 106–114) — evidence identity pollution remains even when gaps do not.

---

### Objections to the current plan assumptions

1. Treating “control experiment already implements 17.2 time-purpose” as sufficient for this packet is wrong: frozen review’s **official** decisions still use the old time-FALSE path.
2. “Empty selection + observation_unverified” is only true on the sealed official path. The packet source list still includes a live explicit map that recreates missing-record semantics.
3. `TRUE` = `fulfilled` is not a modality-safe publication label; it is a polarity convention with no structural check and no `kind` on the projected object.
4. Isolating unresolved atoms at control level, without linking the **activating** unknown branch to the suspended obligation, trades sibling misattribution for missing causal attribution.
5. `any`/`all` completeness refusal in qualification plus experiment support for supplied-set aggregation are contradictory consumers of the same policy field.

---

### Proposed remediation order (owner-side; not executed)

1. Official out-of-window event membership → UNKNOWN (H1). Until then, do not attach `ComponentDecision` from time-FALSE atoms to any frozen review object.
2. Close the explicit-map hole or tag missing vs unverified per predicate (H2).
3. Stop labelling value disagreement as `source_conflict` (challenge 2).
4. Add kind, fact ids, activation-route, and related unresolved identities to `ControlObligationOutcome`; keep `accepted=False` on the frozen aggregate (challenges 3 and 5).
5. Decide any/all: supplied-set calculation + separate completeness flag, or unresolved with the real reason copied through.

No source edits were made in this pass.

---

### Decision points for Codex

| ID | Decision | Safe provisional path if unanswered |
|---|---|---|
| D1 | Official `TimeConstraint` without `time_purpose`: fail-closed UNKNOWN, or add an official spec field? | Treat all official time FALSE from empty in-window set as UNKNOWN until purpose exists. |
| D2 | Is the raw `predicate_fact_ids_by_component` path still authorized for frozen review? | Treat it as non-authoritative in review comments; do not use its `fact_not_observed` → `RECORD_INCOMPLETE` decisions as packet evidence of intended semantics. |
| D3 | Prohibit atom polarity: is TRUE always “obligation satisfied”? | Do not accept `status=fulfilled` for `prohibit_*` kinds until kind is on the outcome and a polarity check exists. |
| D4 | May unscoped default and exception-replacement groups be concurrently active? | Surface both; do not roll up; ask publication/hydration if unscoped default must be remaining-only exclusive. |
| D5 | `any`/`all`: compute supplied set, or keep sealed-unresolved? | Keep unresolved, but forbid rewriting the reason to `selected_observation_missing`. |

---

### Bounded questions for Codex

1. For official IN/EX lookback windows (e.g. “28 天内检查”), is the published `TimeConstraint` intended as **event membership** (out of window ≠ condition false) or as **interval condition**? A single default here changes whether H1 is a blocker or a scoped exception.
2. Should `calculate_frozen_review` refuse non-sealed selection maps in this slice, or must historical callers keep the explicit maps?
3. Is there an approved mapping from `ControlObligationOutcome.status` + `modality` + `kind` into gaps/decisions, or is any such mapping still forbidden (T5: 正式发布未接通)?
4. For qualification `no_candidates_in_supplied_input` / `ALL_SUPPLIED_PAGES_SEARCHED_WITHOUT_CANDIDATE`, which status should frozen official evaluation emit: `observation_unverified` (current) or a distinct verified-absence code that still must not become FALSE?

---

### Categories (compact)

| Kind | Item |
|---|---|
| **Evidence** | Line-cited behaviors above; design §17.1.1–17.3; T5 notes that official unverified must not impersonate missing, and that this chain is not accepted. |
| **Inference** | Official time-FALSE and explicit empty→`fact_not_observed` can misstate fulfillment or hide valid records; control TRUE→fulfilled is polarity-unsafe without kind; projection drops fact identity and related unknown branches. |
| **Recommendation** | Align official event-window handling with the control experiment; separate missing vs unverified in the frozen input; do not publish `ComponentDecision` / `fulfilled` from this object; extend the outcome with kind, facts, and activation-route attribution. |
| **Uncertainty** | No runtime cases; unpublished catalog contents unknown; official time-purpose default not specified; concurrent default+replacement activation may be intended. |

Codex retains final synthesis. This pass does not claim the projection is safe to publish or clinically accepted.
