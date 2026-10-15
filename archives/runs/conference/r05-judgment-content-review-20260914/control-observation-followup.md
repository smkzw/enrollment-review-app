按同一只读角色审阅控制族消费：先核对当前 operand/time 配对修复，再对照四层求值判断拟议的 any/all 目击规则是否成立。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object`, adjacent **control** consumer. Fallback `grok-build` / `grok-4.6`. Source review only. Not clinical acceptance. No compile/runtime.

**Verdict:** The operand/time pairing fix is the right closed gate. The proposed witness-only any/all step is **valid** for source-declared deterministic policy on all four layers **if and only if** `_conditional_truth` stops returning closed-world TRUE/FALSE. Opening selections without that change is false acceptance. Do not keep the consumer’s permanent any/all reject, and do not accept any/all unconditionally.

---

### 1. Current operand fix (implemented)

```236:247:app/services/qualified_binding_selection.py
    operand_records = [item for item in usable_records if item.fact_attribute == spec.operand_attribute]
    ...
    if spec.time_operand_attribute is not None:
        time_records = [item for item in usable_records if item.fact_attribute == spec.time_operand_attribute]
        ...
        if any(fact_id not in qualified_times for fact_id in fact_ids):
            return [], [], ["declared_time_operand_not_qualified"]
```

- Value comparison no longer adopts `fact.value` from a date-only pair (`declared_operand_not_qualified` if the declared operand is missing).
- Attached `time_operand_attribute` must be a **same-fact** qualified pair. Matches spec: value+time requires a separate date attribute (`control_evaluation_spec.py:123-126`); pure `time_constraint` forbids a second date (`121-122`).
- `event_date_for_time_constraint` (`binding_qualification_support.py:569-571`) is the window operand shape, not a numeric threshold.

`single` still requires `len(fact_ids)==1` (`248-249`). `any`/`all` still die at `250-251`. Compile was not run here.

---

### 2. Witness-only is already half-implemented — the other half overclaims

`_conditional_truth` (`control_calculation_experiment.py:37-62`) on the **supplied** set:

| Policy | Existing decisive branch | Existing complementary (line 62) |
|---|---|---|
| `any` | TRUE in set → TRUE (witness) | all FALSE → **FALSE** |
| `all` | FALSE in set → FALSE (counterexample) | all TRUE → **TRUE** |
| mix UNKNOWN | UNKNOWN (58-61) | — |
| empty | UNKNOWN `selected_observation_missing` (42-43) | not vacuous |

Line 62 is exactly what the proposal forbids: ANY all-FALSE ≠ “no event”; ALL all-TRUE ≠ “every required observation met.” The experiment docstring already says ANY/ALL are only the supplied set (`105-106`); the return value still claims the rest of the population.

Today the qualified consumer never reaches this code for any/all (`250-251` → empty selection → `unverified_atom_reasons` override `168-169`). Hand-built maps could.

**Do not pass multi-observation fact_ids until line 62 is UNKNOWN + `observation_scope_completeness_unverified`.**

---

### 3. Four layers, exception/activation — sound at atom grain

Aggregation is **per atom**, then `compose_control_layers` (`control_layer_evaluation.py:69-165`) uses Kleene `_all`/`_any`/`_not`. Same rule on applicability, trigger, obligation, exception.

After a completeness UNKNOWN (not closed-world FALSE/TRUE):

- Exception UNKNOWN does **not** waive (`_not(UNKNOWN)=UNKNOWN`; comment `159-160`).
- Replacement activation `_all(exception, affected_trigger)` stays UNKNOWN, not on (`141-156`).
- Trigger UNKNOWN → `obligation_group_activation` UNKNOWN → outcome `unverified`, **not** `not_applicable` (`control_review_outcome.py:50-55`, validator `36-39`).

If line 62 stayed as-is and selections were opened:

- ANY trigger all-FALSE → atom FALSE → activation FALSE → `not_applicable` (**hides** incomplete “no trigger”).
- ALL obligation all-TRUE → `fulfilled` (**false completeness**).
- ALL exception all-TRUE → waives remaining trigger.

Witness ANY+TRUE / ALL+FALSE at atom level is the correct decisive grain: one verified event can fire an ANY trigger; one verified miss can refute an ALL obligation. Completeness of `policy.scope` is **not** in code (`ControlObservationPolicy` is source-declared mode+excerpts only, `control_evaluation_spec.py:14-21`). n=1 under `any`/`all` is still a population policy — do **not** coerce it to `single`.

Conflicts: selected conflict → per-observation UNKNOWN `source_conflict` (`156-161`); ANY can still take a non-conflict TRUE witness; ALL can still take a FALSE counterexample; TRUE+UNKNOWN for ALL stays UNKNOWN. Leave that.

---

### 4. Downstream gaps — what to keep vs change

`project_control_review_outcomes` does **not** invent eligibility. UNKNOWN atom → `unverified`; reasons union `unresolved_atoms` into `observation_reason_codes` (`41-44, 75-80`). Completeness will show if `_conditional_truth` puts it in `unresolved` (`171-172`). Default `observation_unverified` only if the dict omits the identity.

Do **not** add completeness onto observations that are already UNKNOWN for `source_validity_policy_unverified`, `observation_out_of_window`, `source_conflict`, etc. (58-61). Those are not “all FALSE / all TRUE closed world.”

Empty any/all stays `declared_operand_not_qualified` at selection (`239-240`) → empty list + unverified reasons. Do not emit usable `[]` as FALSE/TRUE. `selected_observation_missing` remains the experiment backstop.

No change: `single`; `source_validity` (`71-73`); date/`record_time` calendar UNKNOWN (`control_operand_calculation.py:100-106`); semantic / control-PJ (`229-230`); prompts.

---

### 5. Smallest source edit (if adopted)

**A. Consumer** `qualified_binding_selection.py:250-253`  
Delete the any/all reject. After the `single` length check:

```python
if policy.mode not in {"single", "any", "all"}:
    return [], [], [f"observation_policy_mode_{policy.mode}_unsupported"]
return fact_ids, pair_ids, []
```

Keep operand/time pairing and empty → `declared_operand_not_qualified`.

**B. Aggregation** `control_calculation_experiment.py:62`  
Replace the complementary TRUE/FALSE with:

```python
return TruthValue.UNKNOWN, ["observation_scope_completeness_unverified"]
```

Leave 42-61 (empty, single, witness, UNKNOWN mix) unchanged.

**C. Version (unpublished construction)**  
- `ControlCalculationExperiment.version` and inner `selection_payload["version"]`: **v3 → v4** (aggregation semantics).  
- `QUALIFIED_BINDING_CONSUMER_ALGORITHM`: **v3 → v4** (control identities become usable multi-fact). One constant, so predicate methods must name v4 too; owner said nothing real is adopted.  
- Keep `component-review/v8` and `frozen-review-publication/v4`: official value/window math and `compose_control_layers` are unchanged. Do not bump evaluator solely for this.

**Remaining completeness (later, not this step):** exhaustive-side proof that `policy.scope` (population / interval / repeats) was fully observed; semantic and control-PJ modes; source-validity policy consumer. Until then, non-witness any/all stay UNKNOWN with `observation_scope_completeness_unverified`.

**Not claimed:** compile, runtime, or clinical PASS.
