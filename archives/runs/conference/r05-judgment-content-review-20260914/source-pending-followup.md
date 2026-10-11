按同一只读角色继续：先读资格选择合同、结构校验与资格提示词，核对 consumer/v2 是否真能解除那两个初始未决项。合同与消费门槛已定位。接下来核对结构校验如何写入那两个 pending，以及资格提示词对时间角色的实际语义。两个 pending 的来源已确认。接着追正式求值如何使用时间窗，并核对评测 kind 过滤器。评测 kind 过滤与时间求值路径已对齐。下面只关闭当前改动里的具体缺陷，不重复上次的架构意见。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object` follow-up. Fallback remains `grok-build` / `grok-4.6`. Read-only; no tests, imports, DB, model calls, web, or writes. No clinical/runtime acceptance.

This pass reviews the **current** consumer/v2 and evaluation-kind sources only. Shared-call architecture and quote-length floors are not reopened.

---

### 1. Direct answer

**`semantic_correspondence_unverified` — prompt/contract can support clearing it.**  
The six structured fields include four correspondence checks the prompt actually asks for: 对象、属性是否直接可用、否认范围、能否作为直接操作数, plus 来源是否可被方案政策接纳 (`app/llm/binding_qualification.py:161-168`). Dual-lane agreement on `object_match=supported`, `attribute_match=direct`, `denial_scope=compatible`, `direct_operand_usable=usable`, `source_admissibility=admissible` is a real answer to the candidate placeholder in `candidate_value_shape` (`app/llm/predicate_binding_candidates.py:95`). That is pair correspondence, not predicate truth.

**`temporal_applicability_unverified` for value records — prompt/contract do not support treating it as answered.**  
`temporal_role` is a **field-kind** enum (`event_date | record_time | not_applicable | uncertain | mismatched`, `binding_qualification.py:38-40`). The prompt mixes two questions in one sentence: “时间角色是事件日期还是记录时间” **and** “使用episode/anchor_dates与条件时间约束判断时间适用性” (`binding_qualification.py:162-164`). There is **no** structured in-window field. Validator only requires reasons for `uncertain`/`mismatched` (`binding_qualification.py:186`), not for window membership.

Consumer/v2 then does this:

```69:73:app/services/qualified_binding_selection.py
                and checked.temporal_role == (
                    "event_date" if record.fact_attribute == "date_range" else "not_applicable")):
            # These are pre-qualification questions answered by the six explicit checks.
            resolved_checks = {"semantic_correspondence_unverified", "temporal_applicability_unverified"}
```

For `fact_attribute=="value"` (and `assertion_basis`), `temporal_role=="not_applicable"` means **this selected field is not a date operand**. It does not mean the observation is inside the condition window. Mapping that onto `temporal_applicability_unverified` is an **overclaim**. The comment at 71–72 is the overclaim in words.

---

### 2. Overclaim and permanent-rejection bugs (exact lines)

**O1. Overclaim — value `not_applicable` clears window pending.**  
- Pending origin: every predicate pair, including `value`, always gets `temporal_applicability_unverified` (`predicate_binding_candidates.py:95`; copied at `binding_qualification_support.py:565-569` and into `remaining_unverified` at `784-785`).  
- Clearance: `qualified_binding_selection.py:66-73`.  
- Same function still copies **all** model `unresolved_reasons` (`74-76`) and keeps unit / professional / source-validity / other `pending_checks` (`79-81`). Those retentions are real; they do not rescue O1.

**O2. Permanent rejection of otherwise dual-agreed value pairs.**  
After the favorable-key block, any non-`date_range` pair whose `temporal_role != "not_applicable"` is rejected:

```109:113:app/services/qualified_binding_selection.py
        if record.fact_attribute == "date_range":
            if judgment.temporal_role != "event_date":
                reasons.append(f"temporal_role_{judgment.temporal_role}")
        elif judgment.temporal_role != "not_applicable":
            reasons.append(f"temporal_role_{judgment.temporal_role}")
```

The prompt never says “value/assertion_basis → `not_applicable`”. It asks the model to classify 时间角色 as 事件日期或记录时间 and to judge 时间适用性. A lane that follows that instruction on a value pair (e.g. `event_date` because `fact.date_range` is the event date, or `uncertain` because the window is unclear) is **schema-legal** (`validate_binding_qualification_payload` only forbids `event_date`/`usable` on `record_time`, `binding_qualification.py:198-201`) and is then **hard-rejected** by 112–113. That is a permanent-rejection bug for the main (value) operand path.

`record_time` pairs remain independently blocked (`84-85` plus compose `788-789`). That block is consistent with the prompt and payload validator. Not a v2 regression.

**O3. Downstream time evaluation does not read `temporal_role`.**  
Selected `fact_id`s go into `evaluate_component` → `_evaluate_atomic` (`expression.py:475-518`). Temporal membership is **code**:

- `_evaluate_time` uses `fact.effective_date` vs `context.anchor_dates` and `expression.time_constraint` (`expression.py:280-294, 494-518`).  
- Adapter sets `effective_date=_phase3_date_value(fact.date_range)` and **does not** use `record_time` (`eligibility_review_projection.py:176-216`).  
- `evaluate_observed_value` is value arithmetic only; callers own temporal **selection** (`expression.py:456-460`), but selection here only chose the value pair. The date used for the window is the same fact’s `date_range`, whether or not a sibling `date_range` pair was dual-agreed `event_date`.

So v2 does **not** certify 时间适用性. It unblocks a fact so the evaluator can apply the window. Missing `date_range` → `date_or_anchor_missing` UNKNOWN, not TRUE (`expression.py:306-315`). A **present** `date_range` that is actually a record/print time still becomes `effective_date` even if a `date_range` pair on that fact was rejected as `record_time`/`mismatched`. That is the residual hole if O1 stays.

**Not an overclaim:** clearing `semantic_correspondence_unverified` under the favorable object/attribute/denial/operand/source key, while leaving `unit_equivalence_unverified`, `professional_judgment_applicability_unverified`, `source_validity_requires_policy_evaluation`, `source_unverifiable`, and model `unresolved_reasons`. Compose still stamps those (`binding_qualification_support.py:784-799`); consumer still emits `pending:{check}` unless in `resolved_checks` (`qualified_binding_selection.py:79-81, 117-118`). PJ predicates still cannot become deterministic values (`194-195`).

**v1/v2 versioning as described:** material/authorization Literals still include `...-consumer/v1` (`qualified_binding_selection.py:45-47, 107-108`). Factory constant is `.../v2` (`23`) and rejects any other authorization version (`139-140`). `require_evaluated_binding_method` binds `consumer_algorithm_version` to that same v2 string (`review_method_evidence.py:21, 24-25`; `qualified_binding_selection.py:286`). Historical v1 typed objects remain parseable; they cannot drive this factory. No runtime proof.

---

### 3. Smallest fix

Do **not** invent a window dimension in this packet. Split the two pending names so they follow actual field semantics.

1. **`candidate_value_shape` (`predicate_binding_candidates.py:95`)**  
   Always emit `semantic_correspondence_unverified`. Emit `temporal_applicability_unverified` **only** when `attribute in {"date_range", "record_time"}`. Value/assertion_basis are not time operands; window stays with `_evaluate_time` on `date_range`.

2. **`pair_direct_selection_rejection_reasons` (`qualified_binding_selection.py:61-73, 109-113`)**  
   - Clear `semantic_correspondence_unverified` from the correspondence+source key; **do not** require `temporal_role` for that clearance.  
   - Clear `temporal_applicability_unverified` only for `date_range` + dual `event_date` (role of **that** field), never from value `not_applicable`.  
   - Keep 109–113 as a **role gate** (value is not a date), but add the matching instruction in the prompt so 112–113 is not a silent trap: `value`/`assertion_basis` → `not_applicable`; `date_range` → `event_date` if it is the clinical event; window doubt → `unresolved_reasons` or `temporal_role=uncertain`, not a fake `event_date` on a value pair.

3. **Comment 71–72** must not say the six checks answered 时间适用性. If value pairs are allowed through, say explicitly: window is deferred to `_evaluate_time`; `temporal_role` is field kind only.

Optional tighter gate (still small, only if Codex wants value selection to respect a rejected sibling date): if any same-`fact_id` `date_range` pair dual-agrees `record_time` or `mismatched`, do not select the value pair. Not required to close O1/O2.

---

### 4. Evaluation-kind isolation (cannot substitute judgment for binding)

`app/services/judgment_method_evaluation.py` is **absent**. The new type is `app/domain/contracts/judgment_method_evaluation.py`.

| Fence | What it does |
|---|---|
| Kind lock | `JudgmentEvaluationManifest.evaluation_kind` is `Literal["written_judgment_content_fidelity"]` (`judgment_method_evaluation.py:31`). Binding kind remains `binding_semantic_correspondence` (`review_method_adoption.py:66`). |
| Approval uniqueness | `(evaluation_kind, candidate_family)` (`review_method_evidence.py:66-69`). Same approval may hold **both** kinds; they are different scopes. |
| Command pick | `qualified_review_command.py:91-93` only matches `evaluation_kind == "binding_semantic_correspondence"` **and** family. A judgment-only approval → `len(matches) != 1` → closed. |
| Publication | `frozen_review_publication.py:83-84`: digest on a binding authorization must not be another kind (`来源核实授权不能引用其他类型的评测记录`). Then `methods[0].publication_version` / `evaluator_version` / `consumer_algorithm_version` are `EvaluatedBindingMethod` fields (`87-89`). |
| Factory read | `build_receipt_verified_...` still uses `read_binding_evaluation` (`qualified_binding_selection.py:285`), which parses **only** `BindingEvaluationManifest` (`review_method_evidence.py:29-31`). A judgment digest fails validation. |
| Method shape | `require_evaluated_binding_method` compares top-level `qualification_contract` / routes / consumer version (`review_method_evidence.py:15-25`). `EvaluatedJudgmentMethod` nests those under `source_qualification_method` (`judgment_method_evaluation.py:13`) and has no top-level qualification fields. `actual.get("qualification_contract")` would be `None`. |

No path in these files **creates** an approval. `ReviewMethodApproval.clinical_case_signoff` stays `False`.

**Residual (not a substitution hole):** `read_review_method_approval` now loads a union (`review_method_evidence.py:38-40`). A mixed approval is allowed. Binding publication ignores judgment digests unless an authorization **points** at them, which command construction does not (`qualified_review_command.py:91-111`). Hand-built pointing is rejected at publication line 83 and at `read_binding_evaluation`.

---

### 5. Remaining uncertainty

- No execution: whether current models emit `not_applicable` or `event_date` on value pairs is unknown; O2 is a source-legal trap, not a measured rate.  
- Whether most official predicates carry `time_constraint` (so O1 matters on almost every value pair) was not counted.  
- Control atoms: `_condition_material` for control dumps `atom` (`binding_qualification_support.py:236-243`) and does not add official `time_constraint` the same way; `source_validity_requires_policy_evaluation` is retained. Control window semantics beyond that were not re-audited.  
- Same-fact value vs `date_range` pair interaction (O3 sibling) has no consumer coupling today.  
- Union decode order if `evaluation_kind` were omitted is untested; both manifests default their kind. Current writers set the field.  
- Clinical correctness of `_evaluate_time` on adapted `date_range` remains unproven (forbidden to run).

**Codex decision (bounded):** adopt the pending-name split in §3 (recommended), or keep clearing `temporal_applicability_unverified` for values but only as an explicit “deferred to evaluator” policy with the prompt role instruction — not as “six checks answered 时间适用性.”

**Not claimed:** runtime PASS, method approval, or final Codex acceptance.
