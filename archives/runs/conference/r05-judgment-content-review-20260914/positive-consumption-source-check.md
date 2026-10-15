按同一只读角色核对现已落地的正向内容路径：先读新的 `qualified_judgment_content` 与授权/选择/缺口相关改动。# Conference Output: r05-judgment-content-review-20260914 - evidence_single_object

## Output

**Session:** same `evidence_single_object` check of the **implemented** path. Fallback `grok-build` / `grok-4.6`. Source review only; not runtime or clinical acceptance.

**Overall:** The nested `JudgmentContentAdoption`, pair-level `content_supported` gate, date coupling, v1 hash pop, consumer v3 / evaluator v8 / publisher v4, and unregistered HTTP adapter are coherent. A **positive PJ path can complete** when one requirement’s found excerpts are all unique-matched, content-supported, source-usable, single-observation, and (if windowed) same-fact `event_date`. Two gaps still matter: requirement resolution does not pin search **status**, and mixed requirements can reject a non-PJ value only because it sat in the content job.

Stale linkage finding **withdrawn** after reread: `judgment_fact_linkage.py:20-21,92-94` records `requirement_outside_binding_scope` instead of raising. Prompt v3 + `event_date_for_time_constraint` (`binding_qualification_support.py:569-571`) is not a numeric-derivation contradiction.

---

### Holds (do not “fix”)

| Check | Evidence |
|---|---|
| Optional nested adoption, all-or-none at use | `QualificationAdoptionAuthorization.judgment_content` `qualified_binding_selection.py:62,66-69`; material `135-137,162-163` |
| Same candidate / frozen / comparison / context | `verify_qualified_content` `qualified_judgment_content.py:28-34`; missing keys fail (`is None`) |
| Content pairs ⊆ qualification pairs | `36-37` |
| Manifest kind + nested source method + routes/versions | `require_content_method` `9-22`; publication membership `frozen_review_publication.py:78-88` |
| PJ pending only with six source keys **and** written content | `qualified_binding_selection.py:67-77` |
| Date-pair PJ pending only via same `(identity, fact_id)` **value** `content_supported` | `316-327` |
| PJ selection falls through existing value / window / single-observation | `206-222` (`written_content_verified` false → old hard-stop) |
| Date operand is window, not threshold | `event_date_for_time_constraint` overwrites `time_operand_needs_derivation` only when `time_constraint` present; pair reject list still blocks the derivation shape (`88-95`) |
| Ambiguous / unreadable / missing-lane search blocks requirement IDs | `qualified_judgment_content.py:59-63` |
| Unlinked / non-unique coverage blocks | `66-68` (`status != unique_source_match` or empty `pair_ids ∩ usable`) |
| Gap suppress is PJ/OU expectation only | `assessment.py:279-294`; missing-file still added; no expectation still `RECORD_INCOMPLETE` if no override **and** not verified |
| Search override omitted only for verified IDs | `frozen_review_calculation.py:236-239` |
| v1 hash excludes new defaults | `qualified_binding_selection.py:157-161`; factory writes v2 (`478-504`) and only accepts consumer v3 (`149-150`) |
| HTTP adapter not mounted | `app/api/v2/app.py:375-392` has no `qualified_review` router |
| No approval created | command only reads manifests / writes adoption **gates** from existing approval id |

---

### P0 — Requirement resolution does not pin `summary.status`

`verified_judgment_requirements` (`qualified_judgment_content.py:59-63`) uses `found_candidates` and the four gap tuples. It never requires `summary.status == CANDIDATES_PRESENT`.

`JudgmentSearchCoverageSummary` only forbids leftover candidates on **not-found** (`judgment_search.py:409-418`). `coverage_incomplete` **may** still carry `found_candidates`. If a future/inconsistent summary had found excerpts and **empty** gap tuples, this function would still emit a verified requirement id, and `frozen_review_calculation.py:239` would drop the search override.

Ambiguous **tentative** excerpts live in `ambiguous_channels`, not `found_candidates` (`judgment_search.py:386-388`). Those **are** gated (`62`). Unlinked **found** excerpts are gated via coverage status (`66-68`). The missing pin is **status**, not the ambiguous channel.

**Smallest fix:** after the gap-tuple checks, `if summary.status != CANDIDATES_PRESENT: continue`. No new gap type.

---

### P1 — Mixed requirement: content-failed non-PJ values become unusable

```329:331:app/services/qualified_binding_selection.py
        if (content is not None and record.fact_attribute == "value"
                and record.pair_id in content_pair_ids and not content_verified):
            rejection = _sorted_unique([*rejection, "written_content_unverified"])
```

Any value pair that entered the content job and is not `content_supported` is rejected, including **non-PJ** predicates that share a requirement’s `predicate_ids` and unique-matched the same excerpt. That is fail-closed for PJ; it can **break** an otherwise source-qualified numeric sibling (positive path for mixed official requirements).

Requirement IDs still need **every** coverage row to intersect `usable_pairs` (`qualified_judgment_content.py:66-68`). A unique-matched excerpt whose only pairs failed content correctly **prevents** gap omission (not false accept). The defect is forcing `written_content_unverified` onto non-PJ identities.

**Smallest fix:** append `written_content_unverified` only when that pair’s predicate `requires_professional_judgment`. Non-PJ stays on the six source keys + date coupling.

`targets = set(requirement.predicate_ids) & set(professional)` (`57-58`) already ignores non-PJ ids for **resolution**. Empty `predicate_ids` → no targets → no ID (no guess). Cross-component ids listed on this requirement but absent from this component’s professional set are also ignored — residual, not a current false-accept if clause-pack ids stay component-local.

---

### P1 — Date-pair pending vs identity `written_content_verified` (no false select)

Date `professional_judgment_applicability_unverified` clears when `(identity, fact_id)` has a **content-supported value pair**, even if that value is later rejected on source keys (`316-327` vs loop order). Identity flag is:

```365:367:app/services/qualified_binding_selection.py
                written_content_verified=bool(usable) and all(
                    item.pair_id in supported for item in usable if item.fact_attribute == "value"),
```

`all([])` is true if `usable` is date-only → PJ hard-stop is skipped, then `value_records` empty → `no_usable_qualified_pair` (`211-212`). **No date-only PJ fact_id.** Acceptable. Optional tighten: `written_content_verified` requires at least one usable **value** in `supported` (`bool(value_records)`), so date-only does not skip the PJ reason string. Behavior of selected facts would not change.

---

### Encoded value vs manufactured clinical truth

`content_supported` requires all five fields, including `encoded_value_fidelity` (`judgment_content_comparison.py:29-30`). That licenses the **already stored** `fact.value` as the observation. `_evaluate_atomic` / `evaluate_observed_value` (`expression.py:456-472`) still do polarity, unit, comparison, then `_evaluate_time` on `effective_date` from `date_range`.

That is **not** a new IE boolean from the content model. `content_supported` is never copied into `TruthValue`.

Preserve UNKNOWN when arithmetic cannot apply: `unit_equivalence_unverified` is still not auto-cleared (`pending_checks` `predicate_binding_candidates.py:109-110`; consumer `83-85`). `non_numeric_value` is **not** in the pair reject shapes (`88-95`), so a CS/NCS string can become `usable` then evaluator `UNKNOWN` (`unit_mismatch` / failed compare). Decision stays indeterminate via `REASON_GAPS` (`assessment.py:207-215,364-365`). **Do not** treat a verified requirement id as “document fulfilled” or skip evaluator UNKNOWN.

Optional smallest harden (only if Codex wants usable ⇒ computable): reject `operand_shape == "non_numeric_value"` for numeric predicates at pair selection, same list as `time_operand_needs_derivation`. Not required to avoid manufactured truth.

Verified IDs only suppress **prior PJ/OU expectation** for that requirement (`assessment.py:288-294`). Missing file / other `gap_type` still apply. Other requirements on the same component unchanged.

---

### Same-context / serialization (no defect found)

- Content vs qualification identity: `qualified_judgment_content.py:28-37`.
- Publication context vs sealed frozen facts/components: `assert_qualified_selections_match_review_context` `516-555`; content search rows loaded from `content["review_context_id"]` (`474-477`) which must match qualification payload hashes.
- Command maps `qualification_job_id → content_job_id` (`81-84,110-124`); control + content refused (`117-118` and auth `66-69`).
- Factory hash includes `judgment_content`, `content_supported_pair_ids`, `verified_judgment_requirement_ids` (`496-504`). v1 read path pops those keys (`157-161`). Factory refuses non-v3 consumer (`149-150`). No migration of old approvals (none claimed).
- `route_identity` keys match `EvaluatedRoute` (`page_review_job_service.py:70-73` vs `review_method_adoption.py:14-21`). Same pattern as binding `qualification_routes`. Not a demonstrated mismatch.

---

### Positive path (when it should succeed)

Official PJ value pair: unique excerpt match → content job subset → dual five-field `content_supported` → six source keys + `not_applicable` → pending PJ cleared → identity one fact → optional same-fact `event_date` if `time_constraint` → `usable` fact_id into existing evaluator. Requirement ID emitted only if every coverage row for that id is unique+usable and search gap tuples are empty. Override dropped only for those ids. Then TRUE/FALSE from **encoded** value/window math can become IN/EX met if no other blocking gaps.

That path is **not** permanently UNKNOWN. Clinical correctness of fidelity remains unevaluated.

---

### Remaining uncertainty / acceptance (not this review)

- Isolated content gold + user approval listing both manifests (none created).
- Whether `investigator_assessment.predicate_ids` are PJ-only in real packs (P1 mixed).
- Runtime reconstruct of nested adoption / hash bytes (not run).
- Evaluator v8 on old frozen contexts: `frozen.evaluator_version != v8` refuses (`frozen_review_calculation.py:157`) — intentional, no migrate.

**Smallest coherent patch set:** (1) require `CANDIDATES_PRESENT`; (2) `written_content_unverified` only on PJ pairs; optional (3) identity flag requires a supported value pair. Do not add a parallel consumer or new fact type.

**Not claimed:** clinical PASS, runtime PASS, or Codex final acceptance.
