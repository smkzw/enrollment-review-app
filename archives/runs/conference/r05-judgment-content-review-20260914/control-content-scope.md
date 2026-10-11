I’ll inspect the content-job, linkage, and control-policy sources only, then return the smallest complete extension points without proposing extra inference.# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Fallback:** `grok-build`/`grok-4.6`. Source only. No clinical adoption. Runtime tests deferred (listed, not requested).

**Current split (proven):** Five checks (`judgment_content.py:12-18`) are fidelity of existing writing to an encoded **value** fact, not proposition truth. Prompt already says `encoded_value_fidelity` ≠ meeting a standard (`llm/judgment_content.py:27-36`). Control atoms already carry `determination_mode` + `proposition` with **no** operation/predicate (`control_evaluation_spec.py:43-46,63-82`); consumer refuses `semantic`/`investigator_judgment` (`qualified_binding_selection.py:231-232`); operand calc skips non-deterministic (`control_operand_calculation.py:78-79`); layer compose keeps UNKNOWN (`control_calculation_experiment.py:37-41,164-177`). Search already has `judgment_search_target/control-v1` (`judgment_search_source.py:343-381`). Evaluation schema already allows `candidate_family: control` (`judgment_method_evaluation.py:12`). **Blockers** are input/consumer/authorization/workflow, not the method-eval type.

**Do not build:** a 6th “proposition_true” check; `content_supported` → atom TRUE/FALSE; polarity invert; disease examples; extra confirmation; new queue/job_type; auto method adoption.

---

### A. Provenance/content reuse (same job/receipt protocol; version pins keep old receipts)

Missing **meaning**, not missing machinery: control pairs already have `atom_identity_sha256`, `condition.{layer,group_index,atom_index,atom_id}`, and `source_policies[].atom_refs` (`binding_qualification_support.py:165-213,234-243`). Predicate linkage uses **requirement-local `predicate_ids`** (`judgment_fact_linkage.py:88-89`; `judgment_content_input.py:25-36`). Control policies have **no `requirement_id`/`predicate_ids`**. `load_prepared_judgment_links` rebuilds **only** `PredicateBindingFrozenInput` (`linkage.py:31-39`), so control search rows become `requirement_outside_binding_scope`. Input then hard-rejects `family != predicate` (`input.py:17-18`). Authorization forbids content on control (`qualified_binding_selection.py:66-68`). Command refuses control content (`qualified_review_command.py:117`). Workflow enqueues **one** content job on the predicate candidate (`prepared_review_workflow.py:233-286`); ready-step origin maps any non-`control_qualification` child to `"predicate"` (`248-251`) — a second content job would mis-bind without an explicit name.

**Ordered units (one protocol, two jobs):**

1. **`judgment-fact-linkage/v2`** — same locator exact-match; add `family` + `atom_refs` (empty refs stay unattributed shells, never infer a singleton). Resolve control `summary.requirement_id` via `project_control_evidence_requirements` / `ControlEvidenceOrigin.requirement_identity()` (`control_evidence_requirements.py:25-96`), not predicate `predicate_ids`. Keep v1 predicate path.

2. **`judgment-content-input/v2`** — drop family reject; select control **value** pairs iff `unique_source_match` and pair `(layer,group_index,atom_index)` ∈ link `atom_refs` **and** policy `evidence_key`/`protocol_control_id` matches that requirement. Unlinked excerpts stay in `excerpt_coverage` with `content_check_ready=false`. Empty `pairs` already enqueue summary-only (`judgment_content_job.py:99-107`) — **missing writing stays reportable coverage, job completes, no extra prompt.**

3. **Same `JOB_TYPE`/`PURPOSE`** — bump `input_version` / optional prompt pin (`JUDGMENT_CONTENT_VERSION`) only if system text must say “五项不裁定命题”. Do not add fields to `JudgmentContentCheck`. Old jobs keep `judgment-content/v1` receipts.

4. **Workflow, no new queue** — if `includes_controls`, enqueue `control_judgment_content` on `candidates["control"]` (same `enqueue_judgment_content`). `CHILD_TYPES` same `judgment_content`. Expected ready set adds that key. Origin map: `control_judgment_content` → `"control"`. Empty control pairs still `completed`.

5. **Authorization/consumer v-next (accounting only)** — allow `JudgmentContentAdoption` for `candidate_family=control` (new authorization version; keep v2 predicate-only). `verify_qualified_content`: require `source["candidate_family"]==payload family`, shared `candidate_job_id`/context hashes, pair ⊆ source pairs. Attach `content_supported_pair_ids`. **Do not** clear `determination_mode_investigator_judgment_not_direct_arithmetic`. Optional `verified_control_evidence_keys` analog of `verified_judgment_requirements` (`qualified_judgment_content.py:46-75`) for **coverage accounting only** — never feed `_conditional_truth`.

6. **Publication map** — `{control_qualification: control_judgment_content}` beside the predicate map. `require_content_method` already matches family (`qualified_judgment_content.py:13`). Method gate stays independently evaluated; no auto-adoption.

7. **`CONTENT_CONSUMER_VERSION` → v2** so control methods cannot silently reuse v1 predicate-only consumer identity.

### B. Non-deterministic proposition evaluation — **new result contract, not this extension**

`proposition` + `investigator_judgment` has no arithmetic operand (`control_evaluation_spec.py:63-64`). Five checks never bind that string. Calculating atom TRUE from writing would be a **new** payload (proposition correspondence ≠ encoded-value fidelity) and a new consumer/calculation version. Today UNKNOWN is already reportable (`control_review_outcome.py:52-53` `unverified`; reasons from consumer/calc). **Leave it.**

**Contradictions / overengineering:** `EvaluatedJudgmentMethod` already has `control` while runtime forbids it — fill the runtime, don’t add a third family enum. `semantic` is a different refused mode (`231-232`); do not bundle. One shared content call for predicate+control would mix frozen inputs and break `candidate_job_id` pairing (`verify_qualified_content.py:29-31`). Do not invent default `atom_refs`. Do not treat `semantic_evidence_unverified` (`control_calculation_experiment.py:40-41`) as failure.

**Deferred checks (do not run now):** v1 predicate receipt still verifies; control empty-pairs workflow completes; unique `atom_refs` selects only those value pairs; empty `atom_refs` never auto-links; `content_supported` does not change investigator_judgment atom truth or obligation polarity; missing writing → UNKNOWN + coverage row, no blocking, no extra confirmation; publication maps both jobs; env method gate still required.
