按同一只读角色继续：先核对全局 `control_time_constraint` 硬拦截、原子 `source_validity` 恒未知，以及现有时间求值能否在不发明用途的前提下被消费。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object`. Fallback `grok-build` / `grok-4.6`. Source only; not clinical acceptance.

**Answers:** (1) Global `control_time_constraint` **cannot** be executed without an explicit, source-backed atom mapping. (2) For **single** deterministic observations already qualified on `date_range`, `source_validity` can use the existing `time_result` as **admissibility**, not as a false clinical compare. Both are interpretation holes, not missing arithmetic.

---

### 1. Global control time — do not consume blindly

`ProtocolReviewControl.control_time_constraint` is optional (`protocol_controls.py:1608`). Gate only checks it is a well-formed `TimeConstraint` and folds its **anchor** into decide-at-node alignment (`protocol_control_gate.py:2661-2674, 3270-3278`). It does **not** name atoms, purpose, or date field. Per-atom calendar text is checked only against `atom.time_constraint` (`2737-2761`).

Composition then **refuses** any non-null global window (`control_layer_evaluation.py:79-80`). That is “cannot ignore,” not evaluation.

Atom contracts already require **purpose + operand** before time is executable (`control_evaluation_spec.py:9-11, 67-71, 115-126`):

| `time_purpose` | FALSE `time_result` today |
|---|---|
| `event_membership` | UNKNOWN `observation_out_of_window` (`control_calculation_experiment.py:79-80`) — not a failed lab |
| `interval_condition` | FALSE via `90-91` — **is** the time proposition |
| `source_validity` | discarded; always UNKNOWN `source_validity_policy_unverified` (`73-75`) |
| `record_time` operand | UNKNOWN `source_calendar_date_unverified` (`control_operand_calculation.py:100-106`) |

Applying one global window to every atom would mix membership, interval, and freshness, and would use the wrong of `date_range` vs `record_time`. Disease/title inference is out of contract.

**Minimal mapping (old dumps unchanged):** optional list on `ProtocolReviewControl`, **pop when empty/None** (same serializer pattern as `evaluation` / `observation_policy`). Do not add required spec fields (`control-atom-evaluation/v1` stays). Do not copy the window onto unlisted atoms in stored JSON.

Each row, source-contained:

- `layer` + atom id (`condition_atom_id` / `obligation_id`)
- `time_purpose` ∈ `{event_membership, interval_condition, source_validity}`
- `source_span_ids` / `source_excerpts` ⊆ **that atom’s** excerpts (not control-wide reuse — `protocol_controls.py:868-871`)
- If the atom already has `time_constraint`, it must **equal** the global constraint; if it has none, calculation uses the global constraint **only for that atom**

**Sequence:** (1) `validate_control_evaluations` / gate: global set ⇒ mapping non-empty, ids exist, purpose matches that atom’s spec; relax `115-116` only for mapped atoms (purpose allowed when atom window is missing **and** binding supplies the global one). Unmapped atoms unchanged. Controls with global and **no** mapping still fail compose (same as today). (2) `control_operand_calculation._calculate_operand`: effective constraint = `atom.time_constraint or mapped_global`. Do not pass `record_time` as calendar event. (3) Replace compose raise with: global set ⇒ every mapped atom was evaluated with that constraint (presence of `time_result` / matching purpose); **unmapped atoms are not timed**. (4) Experiment version **v5** if v4 is already the default in-tree (`control_calculation_experiment.py:26`); consumer bump only if mapping changes which pairs are usable.

No silent default “all atoms,” no model-filled purpose.

---

### 2. `source_validity` — blanket UNKNOWN is redundant; missing proof is interpretation

Arithmetic already runs: `_calculate_operand` writes `time_result` from `atom.time_constraint` + `date_range` (`91-111`) for any purpose except `unresolved`. `control_source_validity` (`source_validity.py:49-72`) is the same `evaluate_time_constraint`; do **not** add a second calculator.

What is missing is **using** that result:

- Consumer pending `source_validity_requires_policy_evaluation` (`binding_qualification_support.py:591-592`) is never cleared ⇒ **no usable pair** via the factory. That is blanket rejection, not extra evidence.
- `_conditional_observation` 73-75 drops `time_result` entirely.

**Smallest observation rule (single policy only; any/all stay completeness):**

- `time_purpose == source_validity` and `operation == value_comparison`: FALSE/UNKNOWN time → UNKNOWN `source_outside_validity_window` (or keep temporal reasons); **do not** take `90-91` FALSE as ALT/threshold failure. TRUE time → existing value path (`85-92`).
- `operation == time_constraint` and purpose `source_validity`: the atom **is** the freshness proposition; `time_result` **is** the atom truth (`81-84` already). Do not hide FALSE as UNKNOWN here.
- `record_time`: keep `source_calendar_date_unverified`; do not treat UTC clock as event/validity calendar.
- Clear the pending **only** when `observation_policy.mode == "single"` and the qualified pair is the declared date operand (`date_range`). Leave `source_validity` on `any`/`all` until scope completeness exists.

That is the event_membership pattern applied to **admissibility**, not a new policy engine. Qualified single `date_range` + declared `source_validity` is enough to **admit or withhold** the observation; it is not clinical approval and not “source policy” in the evidence-requirement `source_validity_window` sense (different contract, `source_validity.py:27-47`).

---

### 3. Exact edits (no new framework)

| File | Change |
|---|---|
| `protocol_controls.py` | Optional mapping list + pop-empty serializer |
| `control_evaluation_spec.py` | Gate: global ⇒ bindings; 115-116 exception only for mapped atoms |
| `protocol_control_gate.py` | Call the same check after `validate_control_evaluations`; do not regex-assign purpose |
| `control_operand_calculation.py` | Effective constraint for mapped atoms; still no `record_time` calendar |
| `control_layer_evaluation.py` | Replace 79-80 raise with “mapped atoms timed” check |
| `control_calculation_experiment.py` | `source_validity` branch as §2; bump experiment version if v4 already frozen |
| `binding_qualification_support.py` / `qualified_binding_selection.py` | Clear `source_validity_requires_policy_evaluation` only for single + qualified `date_range` |

Do not change `compose_control_layers` Kleene logic, prompts, or invent adoption.

---

### Remaining uncertainty

- Whether any published catalog rows already have `control_time_constraint` (compose already refuses them; mapping is a **republish**).
- `half_life_multiplier` on control windows: operand calc does not pass `half_life_days` into `evaluate_time_constraint` (`108-111`). Unmapped half-life stays incomplete.
- Official requirement `source_validity_window` is **not** this control path; do not merge them.

**Not claimed:** compile, runtime, or clinical PASS.
