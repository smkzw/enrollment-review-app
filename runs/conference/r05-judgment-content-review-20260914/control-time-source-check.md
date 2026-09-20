按同一只读角色核对已落地的 `control_time_bindings` 与 `source_validity` 改动，只找具体源缺陷。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object` source check of implemented control-time bindings + `source_validity`. Fallback `grok-build` / `grok-4.6`. No runtime.

**No blocking source defect found** against the stated contract (no implicit inheritance; empty bindings omitted; global-without-bindings parses, publication/composition fail; single `date_range` source_validity only). Remaining items are integration/verification limits, not redesign.

---

### What the source actually does

- Bindings: `ControlTimeBinding` is layer + atom id + excerpts only (`control_time_binding.py:9-13`). Purpose is **not** re-declared; `validate_control_time_bindings` requires the target atom to already have the **same** `time_constraint` as the global one (`58-59`), `time_purpose` in `{event_membership, interval_condition, source_validity}` (`61-64`), and binding excerpts ⊆ that atom’s excerpts (`65-68`). No copy into the atom body.
- Hash: `control_time_bindings` default `[]`, serializer pops when empty (`protocol_controls.py:1610, 1620-1625`). Parse of old JSON without the key stays `[]`.
- History vs publish: model validator calls `validate_control_time_bindings(self)` **without** `require_explicit` (`1645`). `validate_control_evaluations` and `compose_control_layers` use `require_explicit=True` (`control_evaluation_spec.py:130-132`, `control_layer_evaluation.py:80`). Global + empty bindings: parse OK, gate/compose raise (`control_time_binding.py:35-36`).
- Arithmetic identity unchanged: operand calc still uses `atom.time_constraint` only.
- `source_validity` pending: cleared only inside six-dimensional favorable agreement (`qualified_binding_selection.py:67-79`) and only if the atom is deterministic, `time_purpose==source_validity`, has `time_constraint`, policy `single`, and declared date field is `date_range` (`335-340`). Cleared attributes are `{operand_attribute, time_operand_attribute}` (`355-357`) so **value** (clinical operand) and **date_range** (time operand) can both enter `by_identity`. Identity still requires same-fact qualified time pair (`243-247`). `record_time` never enters `validity_specs`.
- Observation: non-single still UNKNOWN `source_validity_policy_unverified` (`control_calculation_experiment.py:73-75`). Value compare + FALSE time → UNKNOWN `source_outside_validity_window` (`80-81`), not threshold FALSE. Time-only `time_constraint` still returns `temporal.truth` (`87-90`). Experiment default **v5** (`26`).

Pending **does not** block a valid declared `date_range` once six-dim `event_date` + `usable` hold: control date pairs get `declared_time_operand_attribute` / `event_date_for_time_constraint`, not the rejected `time_operand_needs_derivation` list (`90-95`). Value+validity without a same-fact qualified date still fails `declared_time_operand_not_qualified`, not a silent value-only accept.

---

### Remaining integration / verification limits (not defects in this contract)

- No compile/runtime of serializer round-trip vs stored `control_sha256`. Empty-list omit is source-correct; not proven against a live catalog blob.
- Product candidate producer still does not emit global time; the binding path is unpublished. Historical global-without-bindings remain uncomposable by design, not reinterpreted.
- Binding excerpts need only be **contained** in the atom; they need not be the calendar-bearing sentences. Atom-level gate still checks `atom.time_constraint` vs atom text (`protocol_control_gate.py:2737-2761`).
- `any`/`all` + `source_validity` never clear the pending marker (intentional). Experiment’s non-single branch is unused on the factory path.
- `record_time` stays non-calendar (`control_operand_calculation.py:100-106`). Freshness uses `date_range` + `event_date` only.
- Evaluated adoption / isolated gold still required before product use. No clinical PASS.
