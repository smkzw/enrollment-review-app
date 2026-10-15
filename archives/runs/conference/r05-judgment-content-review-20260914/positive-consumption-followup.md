按同一只读角色继续：对照正式路径的实际字段与控制流，核查把书面内容核实并入现有授权/计算是否可行。日期配对耦合和 prompt v3 已看到。接着核对授权字段、缺口门控，以及正式计算如何处理专业判断谓词。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object` follow-up. Fallback `grok-build` / `grok-4.6`. Read-only source review; not runtime or clinical acceptance. No shared-call/quote-floor rerun.

**Verdict on the proposal:** The integration can stay on the existing producer, authorization, consumer, and frozen calculation. It is **not** currently wired. Two existing branches make a positive professional-judgment path **structurally impossible** until they are changed together: the PJ selection hard-stop, and search-gap **overrides that are only additive**. Prompt v3 and the date-window pair coupling are **not** in contradiction.

---

### 1. What the current sources actually do

| Piece | Evidence | Current effect |
|---|---|---|
| Content producer | `judgment_content_input.py:12-56`; `verify_completed_judgment_content` `judgment_content_receipts.py:319-421` | Predicate-only; unique excerpt→value pair; coverage retained; flags false; **not referenced** by command/publication/consumer |
| Content status | `judgment_content_comparison.py:27-34`; five fields `judgment_content.py:14-25` | `content_supported` iff dual-lane `agreement_key` all `supported`. Rejected/disagreement/unresolved are distinct |
| PJ selection | `qualified_binding_selection.py:196-197` | Always `investigator_judgment_not_deterministic_value`. Never selects a value |
| PJ pending | `predicate_binding_candidates.py:98-99`; consumer `80-81` | `professional_judgment_applicability_unverified` is **not** in `resolved_checks` (`61-74`). Even if 196-197 were removed, the pair would still be rejected |
| Search gaps | `_summary_gap_requirements` `eligibility_review_projection.py:445-459` | `CANDIDATES_PRESENT` / incomplete → `OBSERVATION_UNVERIFIED`; not-found → `PROFESSIONAL_JUDGMENT` unless file-observed contradiction |
| Gap application | `derive_gate_gap_types` `assessment.py:274-289, 364-365` | Override is **added**. `blocking_gaps` then force `_decision_for_unknown`. A TRUE value result cannot become IN/EX met while that override remains |
| Missing PJ | `missing_judgment_predicates.py:34-39` | Empty selection + all linked due requirements `PROFESSIONAL_JUDGMENT` |
| Date window | prompt v3 `binding_qualification.py:163-169`; identity gate `qualified_binding_selection.py:203-209` | `date_range` + `event_date` is the window operand. Value stays `not_applicable`. Numeric `date_range` still `time_operand_needs_derivation` (`88-92`, `predicate_binding_candidates.py:101-102`) |
| Auth / eval | `QualificationAdoptionAuthorization` has **no** content fields (`qualified_binding_selection.py:26-54`). Command matches **only** `binding_semantic_correspondence` (`qualified_review_command.py:91-93`). Publication rejects other kinds (`frozen_review_publication.py:83-84`) | Judgment manifest exists (`judgment_method_evaluation.py:11-31`) but cannot authorize binding or content consumption |
| Versions | consumer default **v2** (`qualified_binding_selection.py:23`); prompt default **v3** (`binding_qualification.py:27`, auth Literal `39-40`); evaluator `component-review/v7`; publication `frozen-review-publication/v3` | Binding-only path is v2+v3 prompt. PJ-positive semantics are not versioned yet |

---

### 2. Prompt v3 vs date-window coupling — no contradiction

Prompt v3 (`binding_qualification.py:163-169`) states: `temporal_role` is **field kind**; `date_range` is event vs record; window is computed in code from a **separately verified** event date; value must not impersonate a date; deriving a numeric threshold from a date is not `direct`/`usable`.

Consumer identity selection (`qualified_binding_selection.py:198-209`) only uses **value** records as the observation, and if `time_constraint` is present requires the **same `fact_id`** to have a usable `date_range` pair (`event_date_not_qualified_for_selected_value`). Pair-level `time_operand_needs_derivation` still blocks using `date_range` as a numeric operand.

That matches v3. Do not treat `event_date` as “value derivation.” Pair-level still listing `temporal_applicability_unverified` in `resolved_checks` for values (`74`) is now **explained** as deferred to identity+evaluator (`71-73`); not a v3 conflict. Leave it unless a date-constrained value can become usable without a sibling `event_date` pair (it cannot, `203-207`).

---

### 3. Prioritized findings and minimum corrections

**P0 — Positive path is blocked twice; both must change or PJ stays permanent UNKNOWN.**

1. **Hard-stop** `qualified_binding_selection.py:196-197`.  
   **Fix:** Keep this reason when content scope is absent. When authorization carries a verified content job, **do not** return here. Fall through to the existing value + single-observation + date-coupling logic (`198-212`). Content does not invent a fact; it only licenses an **existing** `value` pair already in `usable_records`.

2. **Pending name** `professional_judgment_applicability_unverified` (`predicate_binding_candidates.py:98-99`).  
   **Fix:** In `pair_direct_selection_rejection_reasons` (`54-120`), add that name to `resolved_checks` **only if** rebuilt content comparison for **this `pair_id`** is `content_supported` (`judgment_content_comparison.py:29-30`). Source-favorable six-key agreement alone must not clear it. `content_rejected` / `disagreement` / `unresolved` / missing pair → keep `pending:professional_judgment_applicability_unverified`. Do not map those to missing judgment.

Without (2), (1) never yields a usable pair. Without (1), (2) never selects.

**P0 — Requirement search override is additive; omitting it is the only in-place “gap removal.”**

`assessment.py:274-277` **adds** `OBSERVATION_UNVERIFIED` / `PROFESSIONAL_JUDGMENT`. `364-365`: any leftover blocking gap prevents IN/EX/requirement-met even if `evaluate_observed_value` returned TRUE (`expression.py` value/time math unchanged).

There is **no** API to “remove a gap type from the component set” except **not putting that requirement in `judgment_gap_by_requirement`**.

**Fix (narrow):** When assembling `judgment_gaps` in `frozen_review_calculation.py:227-245`, **omit** a requirement key only if all of the following hold in the **same** frozen context and due node:

- Every **professional** predicate explicitly in that requirement’s `predicate_ids` (`missing_judgment_predicates.py:34-35` already uses this attribution; do **not** require content on non-PJ siblings or the path dies on mixed requirements).
- Each of those predicates has a usable content-bound **value** selection (P0 pair rule + existing `len(fact_ids)==1`).
- Every `excerpt_coverage` row for that `requirement_id` is accounted: unique+`content_supported` on the selected pair, or retained as blocking (ambiguous / unlinked / `content_rejected` / disagreement). Use coverage rows (`judgment_content_input.py:39-45`, `unresolved_excerpt_coverage` `receipts.py:192-195`) as the found-excerpt ledger. `content_check_ready` only means “sent to model”; gap omission needs **status**, not ready-flag.
- File/other expectation gaps stay: `_summary_gap_requirements` already skips `REFERENCED_FILE_MISSING` (`421-422`); `derive_gate_gap_types` still adds non-PJ/OU `expectation.gap_type` (`284-289`). Do not touch that.

Do **not** delete component-level `OBSERVATION_UNVERIFIED` because **one** predicate calculated. Do **not** convert `content_rejected` into `PROFESSIONAL_JUDGMENT` (`missing_judgment_predicates` needs empty selection **and** search-not-found).

If omission conditions fail, leave the search override. Evaluator then either gets empty PJ selection → `professional_judgment_unverified` (`expression.py` mapping in `REASON_GAPS` `assessment.py:212`) or missing-judgment via the existing empty+not-found path.

**P0 — Authorization has nowhere to hang content; command would drop a judgment digest.**

**Fix:** Optional **all-or-none** fields on `QualificationAdoptionAuthorization` (same object, `extra` is forbid so add explicit optionals, default `None`): `judgment_content_job_id`, `content_summary_logical_sha256`, `content_summary_artifact_sha256`, `approved_content_evaluation_sha256`. If any is set, all required; job type/contract/prompt/summary versions pinned to current content constants (`receipts.py:32-36`).

- Binding digest stays `approved_evaluation_evidence_sha256` (publication `83-84` must remain binding-kind).
- Content digest is the **other** field; publication must require it ∈ approval manifests **and** `evaluation_kind == "written_judgment_content_fidelity"`.
- New small reader beside `require_evaluated_binding_method`: match `EvaluatedJudgmentMethod` family; `source_qualification_method.model_dump()` **equals** the binding method already accepted for that job; `content_contract/prompt/summary/routes` equal `verify_completed_judgment_content` (`CONTRACT`, `PROMPT_VERSION`, `SUMMARY_VERSION`, `routes`). Do not pass a judgment manifest into `require_evaluated_binding_method` (`review_method_evidence.py:10-26` reads top-level qualification fields that `EvaluatedJudgmentMethod` nests).

Identity equality after rebuild (`receipts.py:340`, `152-163`):

`candidate_job_id`, `frozen_input_sha256`, `comparison_sha256` (this is the **candidate** comparison on both sides — `receipts.py:204` vs qualification payload), `review_context_id`, `review_context_sha256` must equal the qualification job and frozen context. Command already checks qualification context (`qualified_review_command.py:83-86`). Qualification payload only copies context if the candidate had it (`binding_qualification.py:92-94`); **require it** before attaching content (otherwise all-or-none cannot bind preparation).

`auth_id` / gate `input_entity_refs` / `output_hash` must include content job + content digest (`qualified_review_command.py:100-120`) or replay will not see them.

**P1 — Freeze positive proof on selection material.**

`QualifiedBindingSelectionMaterial` (`103-126`) has no content refs; `selection_sha256` would not pin the proof. Add frozen: content job id, both summary hashes, content eval digest, `content_supported` pair_ids, per-requirement coverage hashes used for gap omission. Rebuild in `build_receipt_verified_qualified_binding_selections` from authorization + `verify_completed_judgment_content`; mismatch → fail closed. Publication `request_hash` already hashes authorizations (`frozen_review_publication.py:50-51`); new fields ride along once present.

**P1 — Mixed-family search still aborts content input.**

`load_prepared_judgment_links` (`judgment_fact_linkage.py:35-39`) links **every** frozen search against predicate frozen input. Control `requirement_id` → `判断摘录未对应到本次审核唯一的资料要求`. Official PJ integration on a mixed context never starts.

**Fix:** skip searches whose `requirement_id` is not uniquely in this predicate frozen input; record an out-of-family coverage row; do not guess-link. Keep `family != "predicate"` reject (`judgment_content_input.py:17-18`). No new framework.

**P1 — Version only the changed consumer/publication/gap policy; do not force a global evaluator re-eval unless Codex wants it.**

Math in `_evaluate_atomic` / `_evaluate_time` does not change. PJ-positive is **which** `fact_ids` and **which** requirement keys are omitted.

- New consumer tag **v3** when content fields are present; keep **v2** for binding-only (existing evals stay valid).
- Bump `qualification_gap_policy_version` (`frozen_review_calculation.py:262`) when omission rules exist.
- Bump `PUBLICATION_VERSION` so method records must name the content-capable publisher.
- **Do not bump `EVALUATOR_VERSION` (`component-review/v7`)** unless Codex accepts re-issuing **all** binding evaluations. Owner asked to version evaluator; the minimum that preserves a positive path without blocking source-only reviews is: evaluator unchanged, gap-policy + consumer + publication versioned. If a single EvaluatedBindingMethod.evaluator_version must move, every family re-eval is required.

`EvaluatedJudgmentMethod.content_consumer_version` should equal v3. Nested `source_qualification_method.consumer_algorithm_version` should equal the binding method used for that job (v2 or v3 per above).

**P2 — Command/HTTP.**

`publish_review_from_qualified_jobs` has no content job argument (`66-68`). Add optional `content_job_ids` keyed by qualification job or family; bind only onto **predicate** auths. Control jobs: no content (producer refuses). Do not register HTTP (`submit_qualified_review` remains unregistered). No approvals created in these modules.

**P2 — `unresolved_excerpt_coverage` is not a content-status ledger.**

`receipts.py:192-195` treats “ready ∩ selected” as resolved even if comparison is `disagreement`. Gap omission must walk `comparisons[].records[].status` by `pair_id`, then coverage rows.

---

### 4. How the five proposal points should land (after P0/P1)

1. **Optional all-or-none on the existing authorization** — yes; separate content digest field; binding eval still required; judgment manifest must match nested source method + content routes/versions.  
2. **Rebuild content; same candidate/frozen/comparison/context** — yes, fields already exist on both payloads. Clear PJ pending only on pair-level `content_supported`. Rejection ≠ absence; no new encoded fact.  
3. **Official PJ value only on exact pair with source + content; single observation** — reuse `198-212`; remove 196-197 only under content scope. Control/investigator_judgment atoms stay `determination_mode_*` (`219-220`).  
4. **Requirement judgment override omitted only under attributed-PJ completeness + excerpt accounting** — not a blanket `gaps.discard`. Other expectation gaps remain. Freeze refs on selection material.  
5. **Existing calculator for value/polarity/time** — no model truth field. Version consumer/publication/gap-policy; evaluator bump optional (see P1). No HTTP until evaluated approval.

---

### 5. Remaining acceptance obligations (not this review)

- Isolated dual-lane **content** evaluation with gold that scores the five fields, not binding semantic gold.
- User method approval that lists **both** binding and judgment manifests; none created here.
- Real contexts: unique-match recall vs ambiguous/unlinked; mixed official/control searches after the skip fix; PJ with `time_constraint` needing sibling `event_date`.
- Browser/HTTP off until that approval exists.
- Clinical correctness of using encoded `fact.value` after `encoded_value_fidelity=supported` is **unproven**.

**Uncertainty:** whether typical `investigator_assessment` requirements list only PJ `predicate_ids` (if mixed, “every attributed predicate” must mean **professional** ones or omission never fires). Runtime of content reconstruct and JobRunner: not run.

**Not claimed:** clinical PASS, runtime PASS, or Codex final acceptance.
