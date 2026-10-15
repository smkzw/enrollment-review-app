Same-session fallback continues, source-only. I’ll read the repeat-scheme, rule, and control contracts in full, then inspect the new time helper and DNF wire only as needed.Contracts are in. Next I’ll check DNF wire, identity hashing, and any existing observation-graph/count-scope fields so the recommendation isn’t invented.# Conference Output: r05-retest-source-review-20260915 - evidence_single_object

**Fallback / capability:** Same-session `pi` / `cursor` / `cursor-grok-4.6`. Source-only; no writes, tests, imports, or runtime. Clinical/regulatory acceptance remains Codex-owned.

## Output

### Verdict

Do **not** put `RuleExpression` / control DNF inside `RepeatScheme`. Add a **sibling ancillary expression on the owning component / control**, referenced by id from the scheme. Reuse `AtomicPredicate` / `ControlConditionAtom` plus existing qualification, value, proposition, and judgment paths. Keep IN/EX and control-layer composition blind to that tree. Until that consumer exists, `repeat_relation_unverified` is still the honest outcome — not implemented conditional-retest support.

| Piece | Status |
|---|---|
| `RepeatScheme` as policy (permission / trigger enum / excerpt / count / time / result_use) | exists |
| Evaluable trigger expression, count scope, combine operator | **missing** |
| Third official expression slot / fifth control binding layer | **missing** |
| Observation graph (groups, not raw facts) | source-only helper, **not connected** |
| `evaluate_repeat_time_limit` | definite DateValue contract; **not connected** |

---

### Evidence

**Scheme is provenance, not an expression.** `RepeatScheme.trigger` is `unconditional | source_condition | unresolved`; `source_condition` only requires `trigger_excerpt` ⊆ `source_excerpts` (`repeat_scheme.py:56-57, 72-80`). No atom ids, no comparator, no `count_scope`, no combine operator (`:58-64`).

**Official IN/EX already has exactly two expression trees.** `RuleComponent.expression` and `exception_expression` (`rules.py:427-428`). `evaluate_component` walks **both** and rolls them into `trigger` / `exception` (`expression.py:621-689`). `_evaluate_atomic` still returns `UNKNOWN` / `repeat_relation_unverified` whenever the **owning** predicate has a scheme (`:488-489`). `PredicateBindingRole` is only `"trigger" | "exception"` (`predicate_binding.py:63`). Frozen construction iterates those two trees only (`predicate_binding_input.py:91-93`). Compact wire has `expression` plus optional `exception_expression` (`protocol_deconstructor.py:888-899`).

**Control already has four clinical layers, not a retest slot.** `project_control_atom_identities` walks `applicability | trigger | obligation | exception` (`control_atom_binding_input.py:32-34`). `compose_control_layers` requires `atom_truths` to be exactly those atoms (`control_layer_evaluation.py:81-90`). Nested `evaluation.predicate` cannot carry a second scheme (`control_evaluation_spec.py:73-74`). Control `trigger_expression` means “when this supplementary control applies,” not “when a retest is allowed.”

**Graph already merges acquisitions.** `analyze_observation_relationships` unions `same_acquisition`, then directs `repeat_of` **between group ids**, flags cycle / multiple predecessors / same-pair conflict, and does not authorize replacement (`observation_relation_graph.py:26-64`). Edge-count over facts would double-count merged duplicates; group-count is the unit that matches this helper.

**Time helper is unconnected.** `evaluate_repeat_time_limit` (`repeat_observation_time.py:17-76`) does not resolve `initial_observation` / `preceding_observation` / `episode_anchor` and does not grant permission. It calls `evaluate_time_constraint`, which requires `DateValue.value` / `DateValue.precision` (`expression.py:307-311`; `calendar_dates.py:26-30`). A plain `date` would throw. Dummy `anchor_type=REVIEW_NODE_DATE` when `episode_anchor` is absent (`repeat_observation_time.py:51`) is unused for lookup today, but is a false protocol anchor if any later caller keys on it. Minute/hour vs day/week/month/year split is intentional; no arithmetic crash found on validated `RepeatDuration`.

---

### Inference

**Recursive expressions inside `RepeatScheme` look like reuse and are not.** The scheme already lives on `AtomicPredicate` and on `ControlAtomEvaluationSpec`. Nesting `RuleExpression` there would:

- allow trigger atoms to carry their own `repeat_scheme` (recursive retest policy);
- hide those atoms from frozen identity / candidate jobs unless a special walk is added anyway;
- inflate the owning predicate dump (identity hashes the full predicate, `predicate_binding.py:110`);
- recreate compact `$ref` / schema-size problems inside an already inlined scheme;
- tempt IN/EX evaluation to walk nested predicates.

**`exception_expression` is the wrong spare slot.** Putting “retest if ALT > 2×ULN” there makes it an exclusion/exception to the clause (`evaluate_component` `exception=`). Putting it in the same DNF group ANDs it into the inclusion criterion. Both invent eligibility.

**Control `trigger_expression` is the same trap.** It already drives obligation activation. A retest condition must not waive or activate those branches.

So the existing **expression type** is reusable (`AtomicPredicate` / `ControlConditionAtom` + `determination_mode`). The existing **slot** is not. The missing piece is a **third role / sibling tree**, not a new engine.

---

### Recommendation — one contract, both families

**1. `RepeatScheme` stays policy. Add references and scope, not a nested engine.**

Keep `trigger` + `trigger_excerpt`. Add:

- `trigger_atom_ids: list[str]` — required, non-empty, unique iff `trigger == "source_condition"`; forbidden iff `unconditional`; empty/omitted on historical `repeat-scheme/v1` must mean **unresolved**, never unconditional.
- `count_scope: "per_initial_acquisition" | "per_current_episode" | "unresolved"` — required iff `count_status == "specified"` (with `maximum_repeats`). No default “one” or “unlimited.”
- `result_combine: "sum" | "mean" | "max" | "min" | "unresolved"` — required iff `result_use == "combine"`; still no arithmetic in this increment.

Bump scheme version (or treat new fields as additive with the unresolved fallback above). Do not nest `RuleExpression` here.

**2. Official field ownership**

- `RuleComponent.repeat_trigger_expression: RuleExpression | None`
- Present iff some atom in `expression` / `exception_expression` has `repeat_scheme.trigger == "source_condition"`.
- Same `AtomicExpression` atoms as today (deterministic value, `semantic_proposition`, `requires_professional_judgment`, optional `time_constraint`).
- Validators:
  - those predicates have `repeat_scheme is None` and `observation_policy is None`;
  - `predicate_id` unique across trigger / exception / repeat-trigger trees;
  - scheme `trigger_atom_ids` ⊆ this tree and **must not include the owning predicate_id**;
  - each trigger atom’s `exact_source_clauses` contain the scheme `trigger_excerpt` (or a declared subset excerpt);
  - `validate_repeat_source` still binds scheme spans to the **owning** atom, not to a different rule.
- `PredicateBindingRole` += `"repeat_trigger"`. `FrozenRuleComponent` gets `repeat_trigger_expression` + `repeat_trigger_predicates`. `_frozen_component` adds a third loop. Identity hash already includes `role`, so ids stay distinct.
- Compact wire: optional `repeat_trigger_expression` (same `wire_dnf_group`, `null` allowed), **not** in IN/EX `expression`. Prompt: 复查触发不是入排条件；触发原子 `repeat_scheme` 必须为 `null`. Bump `DNF_WIRE_VERSION` if `dnf-v5` already escaped.

**3. Control field ownership**

- Sibling on `ProtocolReviewControl`: `repeat_trigger_expression: ControlConditionDnf | None` (hydrate like other condition DNFs so atoms get `condition_atom_id`).
- **Do not** put this DNF inside `ControlAtomEvaluationSpec` (no nested identity; `stable_protocol_control_atom_id` / projection do not walk evaluation).
- **Do not** add it to `compose_control_layers` expected atoms.
- `project_control_atom_identities`: extra layer `"repeat_trigger"` for binding/qualification only.
- Ancillary atoms: `evaluation.repeat_scheme is None`. Owning atom’s `repeat_scheme.trigger_atom_ids` point at these ids.

**4. Runtime binding (reuse, no new campaign)**

- Same candidate + qualification jobs over the new role/layer identities. Not n² pair jobs; not a second relation job per trigger atom.
- Observation relation remains **one whole-set job on the owning identity** (the observation being repeated). Trigger atoms bind their own facts; they are not extra relation groups unless they are the same identity.
- Evaluate triggers with existing paths only:
  - deterministic → `evaluate_observed_value` / control `value_comparison`;
  - semantic → existing proposition-evidence result;
  - investigator → existing judgment-content result.
- **Fact scope:** qualified facts of trigger identities that belong to the **prior acquisition group** of the owning observation (graph `prior_group_id`), never “latest,” never the candidate repeat used to prove its own trigger.
- If graph `structural_reasons` is non-empty, or the prior group is unclassified, trigger is `UNKNOWN`. Dual-lane relation agreement is not trigger truth.

**5. Stay out of official IN/EX rollup**

- `evaluate_component` must **not** append `repeat_trigger_expression` to `expressions` (`expression.py:621-623`).
- Component rollup stays `trigger=combine(expression)`, `exception=combine(exception_expression)`.
- Repeat consumer is a later function: relation graph → trigger eval → permission → count/time → `result_use`. Owning atom evaluation stays fail-closed until that function supplies an authorized selection.
- Control obligation activation stays four-layer. Ancillary truths never waive trigger branches.

**6. Count and combine (do not use fact-count or latest/best)**

- Count **repeat acquisition groups** reachable from one initial group when `count_scope=per_initial_acquisition` (`repeat_edges` after `same_acquisition` merge).
- `per_current_episode`: repeat groups for that identity in the episode, excluding initials. Still groups, not locators/facts.
- Ambiguous predecessor / cycle / `repeat_and_same_acquisition_conflict` → count unresolved.
- `combine`: store the operator; apply only after relation + permission; contradictory values inside one acquisition group stay unresolved. No default mean.

**7. Cycles**

- Expression: no scheme on ancillary atoms; no self-id in `trigger_atom_ids`.
- Graph: existing cycle / multi-parent checks.
- Evaluation: trigger uses **prior** group only, so a high repeat value cannot satisfy “retest if high.”

---

### Missing pieces (do not assume they exist)

- No `repeat_trigger_expression` on `RuleComponent` or `ProtocolReviewControl`.
- No `"repeat_trigger"` binding role/layer.
- No `trigger_atom_ids` / `count_scope` / `result_combine` on `RepeatScheme`.
- No consumer that evaluates ancillary atoms or reads the graph.
- Graph and time helper are not on the selection path.
- Putting ids on the scheme without the sibling tree would be dangling references.

---

### Bounded implementation order

1. Scheme fields + validators (`trigger_atom_ids`, `count_scope`, `result_combine`); historical missing ids = unresolved.
2. Official + control sibling trees, uniqueness, no nested scheme; wire/prompt; **do not** change `evaluate_component` / `compose_control_layers`.
3. Frozen identity + existing candidate/qualification over the new role (same jobs).
4. Connect graph to a **read-only** repeat consumer: group count + structural fail-closed; still no adoption.
5. Trigger evaluation on prior-group facts via existing atomic/control evaluators; permission after that.
6. `result_use` last (`use_last_repeat` = last **verified repeat group after proven trigger**, not `observation_policy.selection=latest`). Wire time helper with `DateValue` only.
7. Keep selection `repeat_relation_unverified` until step 5 is real. Do not present blanket UNKNOWN as “conditional retest supported.”

---

### Time helper (definite only)

- **Blocker if connected as-is:** arguments must be `DateValue`, not `date` (`repeat_observation_time.py:25-26` vs `expression.py:307-311`).
- Dummy `REVIEW_NODE_DATE` (`:51`) is safe only while `anchor_type` is ignored; do not persist that constraint as the episode anchor.
- No permission, no reference resolution, no selection — do not treat this as a window implementation.

---

### Objections / decision points

1. Reusing `exception_expression` or control `trigger_expression` is cheaper and wrong: it changes eligibility/activation.
2. Nested scheme expressions would still need identity/binding walks; the sibling tree is the smaller reuse.
3. Counting `repeat_of` **facts** or raw edges is still wrong after `same_acquisition` merge.

**Codex decisions:** (1) bump `repeat-scheme/v1` vs additive unresolved fallback; (2) bump `dnf-v5` if already in flight; (3) control ancillary as control-level DNF (recommended) vs nested under evaluation (not bindable today).

**Safe provisional path:** capture sibling expression + id refs; keep IN/EX and control composition unchanged; keep fail-closed adoption. No tests or clinical acceptance in this pass.
