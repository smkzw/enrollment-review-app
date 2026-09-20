The previous conference pass already returned the report. I’ll check whether anything new was requested or remains open, then stop if the assignment is complete.The runner still has a pending placeholder, so the advisory report was not persisted. I’ll re-read the assigned sources and return the complete schema in this response.The runner file is still a pending placeholder, so this response is the complete `evidence_single_object` pass for persistence. No source writes.

# Conference Output: r05-retest-design-20260915 - evidence_single_object

## Output

**Role / fallback:** `evidence_single_object`（重要证据审阅）。Assigned primary `grok` / `grok-build` / `grok-4.6` was unavailable before a resumable session existed; this pass is the declared `pi` fallback `cursor` / `cursor-grok-4.6`. Advisory only. Codex remains final authority. No production writes, no tests/imports/runtime, no clinical/regulatory/visual acceptance, no source clinical-file reads, no network.

**Boundary observed:** Read-only inside the runner-bound worktree. Initial packet plus named source-of-truth files. Adjacent definitions opened only to verify reuse (`r05-conditional-observations-20260915` follow-up, `proposition_observations.py`, `expression.py`, `assessment.py`, `judgment_content_job.py`, `control_operand_calculation.py`). The prior conference is a proposal to challenge, not an adopted design. This turn re-grounds that advisory because `runs/conference/r05-retest-design-20260915/evidence_single_object.md` is still the Codex pending placeholder.

---

### 1. Evidence (sourced fact)

**E1. User / design authority (packet + §17.2 + T3)**

- Protocol, not chronology, determines permitted retest triggers, count, permission, time limit, and whether the retest replaces the initial result or combines with it. Dates may only evaluate an already-proven relation. (`context/r05-retest-design-20260915_conference_context.md`; `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17.2 lines 330–332)
- Existing `latest`/`earliest` and `single`/`any`/`all` do not express conditional retest. Owner already rejected “retest count proves authorization” and “same-day ≥ proves unique dominance.” (§17.2 lines 326, 332; T3 `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` lines 81–89)
- Models: source meaning. Code: numbers, dates, logic. Independent dual product VLM, versioned outputs and receipts, no new automatic adoption. Preserve raw evidence and initial review histories. No disease/drug/protocol-specific rules. No staged tests until the whole system is built.
- Conditional retest remains explicitly open; protective `UNKNOWN` is not feature-complete. (§17.2 lines 320, 332; T3 line 87: 复查先核原文关系而非日期顺序)
- Packet scope also requires: same-day, repeated attempt, bad initial sample vs true abnormal result, discretionary investigator permission, unrelated simultaneous tests, missing date/source, additional repeat after max, missing permitted repeat; do not assume absence of a repeat violates OPTIONAL permission.

**E2. ObservationPolicy as it exists today**

```63:87:app/domain/contracts/observation_selection.py
class ObservationPolicy(ContractModel):
    mode: Literal["single", "any", "all", "unresolved"]
    scope: str
    source_span_ids: list[str]
    source_excerpts: list[str]
    selection: ObservationOrdering | None = None
    # selection.criterion is only latest|earliest; ordering_attribute is only date_range
    # selection is forbidden unless mode == "single"
```

- `OrderedObservationExclusion.reason` is only `not_governing_observation` | `observation_out_of_window`.
- Date-dominant unique pick is `select_ordered_observation` (`app/services/ordered_observation_selection.py:44-112`): same-day / partial-date ties stay unresolved; `within_window` vs `before_window_check`; never a favorable value.
- Semantic path reuses that selector (`semantic_observation_selection.py:99-171`). It does not assign initial/retest roles.

**E3. Dual evidence today is pair-local (fact ↔ condition), not fact ↔ fact**

- `PropositionEvidenceCheck.scope` is literally `pair_local`; quotes must come from that pair’s locator; “不能借用其他配对原文” (`app/llm/proposition_evidence.py:63-108`, `app/domain/contracts/proposition_evidence.py:51-54`).
- Binding qualification is also per `(identity, fact, attribute)` (`qualified_binding_selection.py` pair rejection / usable-record path).
- Job reuse pattern already exists: `PropositionEvidenceJobExecutor` subclasses `JudgmentContentJobExecutor` (`proposition_evidence_job.py:15-30`); empty selected pairs save coverage and do not call a model.
- Adoption remains sealed: `QualificationAdoptionAuthorization` v5 must name judgment_content / proposition_evidence jobs (`qualified_binding_selection.py` contract: `QUALIFICATION_ADOPTION_AUTHORIZATION_VERSION = "qualification-adoption-authorization/v5"`, `QUALIFIED_BINDING_CONSUMER_ALGORITHM = "qualified-binding-selection-consumer/v14"`). Dual agreement of reject/unresolved never becomes usable truth.

**E4. Consumption already selects, then calculates**

- Deterministic: `_select_with_ordering` → `select_ordered_observation` or `any`/`all` (`qualified_binding_selection.py:274-327`). File is 847 lines.
- Semantic: relations first, then `_semantic_ordering` if `policy.selection` is set (same file ~518-539).
- Official value arithmetic is caller-owned: `evaluate_observed_value` “Value arithmetic only” (`expression.py:466-470`). `_evaluate_atomic` fail-closes on `semantic_proposition` / `occurrence_window` / `prospective_*` / unresolved policy (`expression.py:488-496`). **There is no analogous guard for retest.** Multiple distinct values without a unique policy become `observation_selection_unverified` (`expression.py:567-571`), which is a safety net, not retest semantics.
- Control operands likewise fail-close only on frequency/prospective (`control_operand_calculation.py:82-87`), not retest.
- `combine_observations` implements `single`/`any`/`all` only (`app/domain/proposition_observations.py`).
- Gaps: `REASON_GAPS` maps those selection/proposition codes to `OBSERVATION_UNVERIFIED` (`assessment.py:206-233`); new retest reasons are absent.

**E5. Four-layer control algebra vs nested predicate policy**

- Controls already have separate DNF layers: applicability / trigger / obligation / exception (`control_evaluation_spec.py:125-133`).
- `ControlAtomEvaluationSpec` forbids copying `observation_policy` onto the nested `AtomicPredicate` (“补充要求的观察政策只能由所在求值规格声明，不得在比较条件内重复”, `control_evaluation_spec.py:63-65`). That is an existing anti-duplication rule.
- `ObservationPolicy` lives in `observation_selection.py` and is imported by `rules.py` (`rules.py:11`). `TimeConstraint` lives in `rules.py` (`rules.py:45-71`). Putting a `TimeConstraint` inside `ObservationPolicy` would create the circular `ObservationPolicy → rules` dependency the packet forbids.
- Official `AtomicPredicate` already carries `observation_policy`, `occurrence_window`, `prospective_*`, `semantic_proposition` as optional omitted-when-null fields (`rules.py:208-233`). Historical serialization stays stable if new optional fields follow the same omit pattern.

**E6. Adjacent prior proposal (not adopted)**

`runs/conference/r05-conditional-observations-20260915/followup.md` proposed hanging `declared_repeat` on `ObservationOrdering`, then a new tuple-local dual job. That file is adjacent evidence of a previous advisory, not current product behavior.

---

### 2. Highest-impact defect

**Hanging a retest scheme on `ObservationOrdering` (or using `latest`/`earliest` as a stand-in) is the wrong integration point.** It would:

1. Force retest through `mode == "single"` and date dominance (`observation_selection.py:85-86`, `ordered_observation_selection.py:54-55`), which is exactly “infer initial/retest from chronology.”
2. Make optional permission unrepresentable: missing retest would look like “no unique latest” or “scope incomplete,” violating “absence of an OPTIONAL repeat is not a violation.”
3. Import interval/`TimeConstraint` into `observation_selection.py` and recreate the `ObservationPolicy → rules` cycle that `ControlAtomEvaluationSpec` already refuses.
4. Leave `_evaluate_atomic` / control operands without a fail-closed `repeat_relation_unverified` guard, so a published scheme could still be consumed as ordinary `any`/`all`/`single` on mixed initial + unauthorized extras.

**Remediation:** treat retest as a **sibling source-declared scheme + tuple-local dual proof + deterministic graph consumer**, not as another ordering criterion. Details in §4.

---

### 3. Inference (not evidence)

- Protocol-level “must retest if X” as a **procedure obligation** can already live in control trigger/obligation layers. That answers “was the retest procedure due/done.” It does **not** answer “which lab value governs this IE predicate.” Collapsing permission into a second full predicate algebra would duplicate `AtomicPredicate` and circularly feed ObservationPolicy.
- Investigator discretion is already a determination mode (`investigator_judgment` + `judgment_content`). A retest permission of that kind should **reference** that chain, not invent a third PJ semantics.
- Pair-local proposition/qualification cannot certify “B is an authorized retest of A.” A new tuple identity is required. The **job machinery** should be subclassed, not forked into a new queue.
- Candidate grouping must not pre-label initial vs retest by date. Present unordered accounted facts for one identity; the model may say `unrelated` or `repeated_attempt_same_draw`. Code builds a graph only from dual-agreed structured fields.

---

### 4. Recommendation (advisory; smallest complete change)

#### 4.1 Supported generic forms (bound; do not simplify the rest)

| Form | Meaning | Outside this bound |
|---|---|---|
| Optional repeat, replace | 0 retests → use initial under existing policy; 1 authorized retest → that value governs; initial retained as not-selected | Infer required from optional wording |
| Optional/required repeat, combine | Authorized initial+repeats then existing `any`/`all` | `single` + `combine` without a further unique rule → unresolved |
| Required repeat missing | `permitted_repeat_missing` UNKNOWN, not “record incomplete,” not optional-fail | Treat like optional |
| Source-stated trigger | invalid sample / abnormal result / investigator discretion, each with verbatim excerpts | Disease/lab nomogram, “use the better value,” repeat-until-normal |
| Same-day | Relation only from source meaning (复查医嘱, specimen/order ids) | Same calendar day ⇒ retest |
| Unrelated simultaneous tests | `unrelated`; each remains an ordinary observation under existing policy | Merge into one series |
| Same-draw repeated attempt | `repeated_attempt_same_draw`; does **not** consume authorized-repeat quota | Count as a protocol retest |
| Extra after max | not-selected `repeat_count_exceeds_scheme` | Silently keep latest |
| Missing date/source | relation may still be proven from text; interval stays unverified | Invent dates |

Unsupported source is stored as `repeat_scheme.permission=unresolved` (and/or `result_disposition=unresolved`) with excerpts. Do not coerce to `latest`/`any`/`all`.

#### 4.2 Field shape (minimal, with counterexamples)

**A. `RepeatScheme` — sibling of `ObservationPolicy`, not inside it**

Place on `AtomicPredicate` (official) and `ControlAtomEvaluationSpec` (control). Optional; omit when null (same serializer pattern as `semantic_proposition`).

**Do not define this class in `observation_selection.py`.** `rules.py` already imports `ObservationPolicy` and owns `TimeConstraint`. Smallest cycle-free placement: `class RepeatScheme` in `rules.py` after `TimeConstraint`, then optional field on `AtomicPredicate`. `control_evaluation_spec.py` already imports `AtomicPredicate` from `rules.py`, so it can import `RepeatScheme` the same way. A new `repeat_scheme.py` that imports `TimeConstraint` from `rules.py` while `rules.py` imports that module would recreate a cycle.

- `source_span_ids` / `source_excerpts` (required if present; must be contained in the owning atom/predicate excerpts — reuse `rules.py:241-245` / `control_evaluation_spec.py:103-107`)
- `permission`: `required` \| `optional` \| `investigator_discretion` \| `unresolved`
- `max_authorized_repeats`: `int ≥ 0` \| omit=unresolved
- `interval`: `TimeConstraint` \| omit. Official event windows stay on `AtomicExpression.time_constraint`; this field is only the **repeat-to-initial** limit.
- `result_disposition`: `replace` \| `combine` \| `unresolved`
- `trigger`:
  - `kind`: `none` \| `invalid_sample` \| `abnormal_result` \| `investigator_discretion` \| `sibling_identity` \| `unresolved`
  - `enforcement`: `must_satisfy_declared_trigger` \| `may_repeat_without_trigger` \| `unresolved`
  - `sibling_ref`: string identity only (`predicate_id` / `atom_ref` path), **not** an embedded `AtomicPredicate`
  - trigger excerpts
- Counterexample: “可复查一次，以复查为准” → `permission=optional`, `max=1`, `disposition=replace`, `enforcement=may_repeat_without_trigger` or source-stated trigger. Missing retest ≠ fail.
- Counterexample: “异常时可于7日内复查，以复查为准” → trigger=`abnormal_result`, interval=7 days, replace. Chronology does not pick the pair.
- Counterexample: hemolyzed / clotted / “标本不合格复查” → `invalid_sample`, distinct from `abnormal_result`. Do not merge those kinds.

Do **not** put this on `ObservationOrdering`. `any`/`all` + combine is a valid scheme with `selection is None`.

**B. Tuple-local dual proof — `ObservationRelationCheck`**

New contract module `app/domain/contracts/observation_relation.py` (mirror `proposition_evidence.py`, do not extend `PropositionEvidenceCheck.scope` beyond `pair_local`).

Identity: `(identity_sha256, scheme_hash, fact_a, locator_a, fact_b, locator_b)` with canonical unordered pair key so (A,B)==(B,A).

Structured fields (code consumes only these):

- `relation`: `authorized_retest` \| `repeated_attempt_same_draw` \| `unrelated` \| `unresolved`
- `initial_fact_id` / `repeat_fact_id` required iff `authorized_retest` (model assigns roles; prompt forbids date-only basis)
- `quote_a`, `quote_b` each must be substrings of the respective locators (two-locator analogue of proposition quote validators)
- `trigger_support`: `supported` \| `rejected` \| `unresolved` (source meaning of the **repeat** record vs declared trigger excerpts)
- `basis`: `explicit_source_link` \| `insufficient` — validator: `authorized_retest` + `insufficient` is illegal

Prompt rule (code-enforced by quotes, not trust): 日期顺序只能核对已认证关系，不能单独建立关系.

Empty planner: identity has `<2` qualified value facts, or scheme absent/unresolved → no model call, persist coverage (`empty_selected_pairs` pattern).

**C. Deterministic consumer — new shared submodule**

`app/services/authorized_repeat_selection.py` (do not add hundreds of lines to `qualified_binding_selection.py`).

Inputs: receipt-verified qualification accounting, dual-agreed relation rows, `RepeatScheme`, qualified dates. Uses existing `evaluate_time_constraint` and `observation_scope_reasons`. Does **not** call `select_ordered_observation` to assign roles.

Algorithm:

1. Graph from dual-agreed `authorized_retest` edges; `unrelated` leaves nodes as independent initials; `repeated_attempt_same_draw` collapses to one observation before quota.
2. Leftover qualified facts with `unresolved` relation among a declared scheme → identity unresolved (`repeat_relation_unverified`), do not drop silently.
3. Count **authorized** repeats only; extras → not-selected `repeat_count_exceeds_scheme`.
4. Interval: only on proven pairs with qualified dates; missing date → `repeat_interval_unverified`, not a fabricated bound.
5. Trigger enforcement: if `must_satisfy_declared_trigger` and `trigger_support!=supported` (or sibling/PJ not usable), that edge is not authorized (not-selected `repeat_trigger_unmet`). If `may_repeat_without_trigger`, skip this gate.
6. Permission:
   - `optional` + zero authorized repeats → governing set = initials; **do not** emit `permitted_repeat_missing`
   - `required` + zero → unresolved `permitted_repeat_missing`
   - `investigator_discretion` + no usable PJ on the trigger ref → unresolved, do not auto-adopt
7. Disposition:
   - `replace` → governing = last authorized repeat (or the single authorized one); initial and superseded repeats in `not_selected` as `superseded_by_authorized_retest`; **histories and raw evidence stay**
   - `combine` → governing = initials ∪ authorized repeats, then existing `ObservationPolicy`
8. Then existing latest/earliest/`any`/`all` run **only on the governing set**.

Fail-closed guards (feature, not tests): if `repeat_scheme` is present, `_evaluate_atomic` and `control_operand_calculation` must UNKNOWN with `repeat_relation_unverified` unless the sealed consumer already reduced `fact_ids`. Map new codes in `REASON_GAPS` to `OBSERVATION_UNVERIFIED`, never `RECORD_INCOMPLETE`.

#### 4.3 Exact integration files / classes

| Stage | Files / symbols | Existing vs missing |
|---|---|---|
| Protocol capture | `RepeatScheme` in `rules.py` (or cycle-free new module); `AtomicPredicate` optional field; `control_evaluation_spec.py` `ControlAtomEvaluationSpec` optional field + validator (excerpts ⊂ atom; nested predicate still must not carry a second policy); `app/agents/protocol_deconstructor.py`; `app/agents/protocol_control_deconstructor.py`; `app/protocols/deconstruction_gate.py`; wire/prompt version bump following control v3 / official omit-null pattern | Policy capture exists; scheme capture **missing** |
| Source closure | Existing candidate job + `binding_qualification_support.verify_completed_binding_qualification`; accounted facts already per identity | Reuse |
| Fact candidate grouping | `app/services/observation_relation_input.py` **new** (mirror `proposition_evidence_input.py`): unordered pairs from **this identity’s qualified value facts**, not chronology; batch via existing `plan_judgment_content_batches` | Grouping **missing**; packing reusable |
| Dual relationship proof | `app/domain/contracts/observation_relation.py`; `app/llm/observation_relation.py`; `app/services/observation_relation_{input,job,comparison,receipts}.py`; `ObservationRelationJobExecutor(JudgmentContentJobExecutor)` | Pair-local jobs exist; tuple-local **missing**. No new queue |
| Workflow | Same formal workflow that already inserts a version-pinned `proposition_evidence` step when `semantic_proposition` is present (`qualified_binding_selection.py:518-539` pattern): add step when `repeat_scheme` present; zero pairs still persist a completed check | Step **missing** |
| Deterministic trigger/permission/time | `app/services/authorized_repeat_selection.py` **new**; `evaluate_time_constraint` (`expression.py`); sibling/PJ reuse of `judgment_content` via existing `authorization.judgment_content` | Logic **missing**; primitives exist |
| Result selection | `qualified_binding_selection.py` `_select_with_ordering` / semantic branch: call the new submodule **before** `select_ordered_observation` / `_semantic_ordering`; consumer algorithm v14→v15; authorization v5→v6 with `observation_relation: JudgmentContentAdoption` sibling (do not overload `proposition_evidence`) | Hook exists; call **missing** |
| Combine after governing set | `predicate_proposition_calculation.py`; `app/domain/proposition_observations.py`; control four-layer combiner / operand calc | Reuse on reduced set |
| Frozen report / action | `OrderedObservationAudit` + extend exclusion reasons; `QualifiedBindingIdentityOutcome.observation_ordering` already requires selected ∩ not_selected = ∅ (`contracts/qualified_binding_selection.py:131-138`); frozen review / control review outcome; `assessment.py` `REASON_GAPS`; keep initial locators on the report, not in `used_fact_ids` | Split exists; retest reasons **missing** |
| Method gate | `app/services/review_method_evidence.py` new purpose `tuple_local_observation_relation`; no auto adoption | Pattern exists |

Prefer the new submodule + 4-file job mirror over growing `qualified_binding_selection.py` (already 847 lines) or `ordered_observation_selection.py`.

#### 4.4 Four-layer control: use, don’t duplicate

- **Use** applicability/trigger/obligation/exception when the protocol states a **procedure control** (“异常必须复查”). That is obligation satisfaction, reported separately from IE value consumption.
- **Do not** encode IE “may retest once, use retest” as a second trigger/exception predicate tree. That duplicates algebra and would require ObservationPolicy to point at rules.
- Permission on `RepeatScheme` is a **consumption policy**, not a truth-value of a sibling atom. `investigator_discretion` may *reference* an existing PJ atom by string identity.

---

### 5. Uncertainty

- Dual-VLM stability on unordered pairs (role swap A↔B, same-day unrelated vs 复查) is unevaluated. This pass did not call product models.
- Whether `replace` means the last authorized repeat only, or any authorized repeat chosen by a further source rule, is not evidenced beyond the user sentence “whether replaces initial or combines.” Default in §4 is last authorized; Codex/user may tighten.
- Historical published rules have no `repeat_scheme`; they must remain readable with the field omitted. New official/control wire versions are required before capture. This pass did not inventory current wire enum values line-by-line in `deconstruction_gate.py`.
- `DateValue` still lacks clock time (T3/§17.2 line 324). Same-day interval of “within 24 hours” cannot be computed; keep `repeat_interval_unverified` rather than treating calendar-day equality as proof.
- No runtime or staged tests were run, per packet.

---

### 6. Objections, decision points, questions for Codex

**Objections**

1. Do not implement the adjacent conference’s `declared_repeat` on `ObservationOrdering`. It contradicts the chronology ban, optional-permission rule, and the no-cycle constraint.
2. Do not extend `PropositionEvidenceCheck` with a second fact id. `scope=pair_local` and quote validators are load-bearing; mixing tuple proof into that schema will silently break official/control proposition consumption.
3. Do not skip the fail-closed official/control guards. Without them, publishing `RepeatScheme` while consumer v14 still runs would combine unauthorized extras under `any`/`all`.
4. Do not treat control trigger/exception as a complete substitute for IE retest consumption.
5. Do not put `RepeatScheme` in `observation_selection.py` in order to “keep observation fields together.” That file cannot own `TimeConstraint` without a circular import.

**Decision points (Codex / user)**

1. `replace` + multiple authorized repeats: last-only vs unresolved-until-source-picks-one.
2. `trigger.enforcement` default when the protocol says only “可复查” with no abnormal/hemolysis clause: `may_repeat_without_trigger` vs `unresolved`.
3. Same-draw instrument rerun: collapse before quota (recommended) vs leave as two observations.
4. Unresolved leftover facts under a declared scheme: fail the whole identity (recommended) vs quarantine only those facts and still consume the proven subgraph.

**Bounded questions (block a full implementation spec, not this advisory)**

1. For optional `replace`, if a dual-agreed retest exists but declared trigger `abnormal_result` is not supported on that record, is the retest unused (keep initial) or still replacing? This is `must_satisfy_declared_trigger` vs `may_repeat_without_trigger`. It changes governing `used_fact_ids`.
2. Confirm authorization shape: new v6 field `observation_relation` parallel to `proposition_evidence`, rather than reusing the proposition adoption slot. Reuse would let a proposition receipt authorize a relation job.

**Safe provisional path if those stay unanswered:** implement capture + tuple job + consumer with `enforcement=unresolved` and `replace`+`>1` authorized → `repeat_result_disposition_unverified`; optional+zero retests still uses initial; no auto adoption; no staged tests.

---

### 7. Fallback / capability record

- Primary route `grok/grok-build/grok-4.6:high` unavailable; executed `pi/cursor/cursor-grok-4.6:high`.
- Tools: Read/Glob/Grep on the authorized worktree. No writes (including no write to the runner-managed report path), no tests, no imports, no DB, no browser, no network, no Trellis task creation, no recursive delegation.
- Runner state at this pass: `runs/conference/r05-retest-design-20260915/evidence_single_object.md` is still the pending placeholder. This response is the complete schema for runner persistence.
- This is one complete bounded advisory pass. Not Codex acceptance.
