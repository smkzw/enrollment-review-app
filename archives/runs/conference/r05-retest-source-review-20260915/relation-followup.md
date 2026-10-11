Same-session fallback continues. I’ll fill a few remaining line-level gaps, then return the complete source-only report without writing files.The remaining relation files only printed totals. I’ll dump those four files in full for exact line citations.# Conference Output: r05-retest-source-review-20260915 - evidence_single_object

**Fallback / capability:** Same-session continuation as declared `pi` fallback `cursor` / `cursor-grok-4.6`. Source-only: read/search/stat; no writes, tests, imports, DB, model calls, or network. Runtime capture, live two-lane reads, and clinical/regulatory acceptance remain **UNVERIFIED**. Codex remains final authority.

## Output

### Verdict

| Area | Status | Note |
|---|---|---|
| Owner updates: compact schema inline; chronology skipped when scheme present; `result_use.not_specified`; v4 keeps `"repeat_scheme": null` | **PASS** (source) | Provider JSON / live capture still **UNVERIFIED** |
| New increment: one whole-set group per requirement, not n² pair jobs | **PASS** (shape) | One `ObservationRelationContext` per identity that has a scheme |
| Source IDs, excerpt substring, dual-lane receipts, no acceptance flags | **PASS** (source) | Quotes are containment, not 回指 proof |
| Explicit intake + runtime registration | **PASS** | Kind/executor/progress/HTTP exist |
| Automatic parent workflow + authorized consumer | **not implemented** | Do not mark complete |
| Highest-impact source defects | **FAIL** (enqueue exception) + **FAIL** (scheme-in-prompt bias) | See evidence |
| Clinical adoption / trigger / count / `result_use` evaluation | **not implemented** | Fail-closed selection still blocks adoption |

This increment is a **proposed-relationship job** over already-captured candidate sources. Agreement is not permission, replacement, or truth.

---

### Evidence — owner-updated capture / guards

**`result_use` includes `not_specified`.** `repeat_scheme.py:62-64`: `retain_initial | use_single_repeat | use_last_repeat | combine | not_specified | unresolved`. Count/time already had specified / not_specified / unresolved.

**Control v4 keeps explicit null.** `control_evaluation_spec.py:46-47`: omit `repeat_scheme` only when `None` **and** `version != "control-atom-evaluation/v4"`. Older evaluation versions still strip `None`. v4 still forbids stuffing a scheme into older versions (`:52-53`). Official `AtomicPredicate` still pops `None` (`rules.py:235-236`) — historical predicate identity, unchanged.

**Compact RepeatScheme schema is inlined.** `protocol_deconstructor.py:651-669`: `$ref` expanded from `$defs`, `title`/`default` stripped, object `required` forced, field is `anyOf` of inlined object + null. Raw `$defs["RepeatScheme"]` injection is gone (`:1097-1103`). Decimal/`RepeatDuration` JSON shape was not generated here.

**Chronology no longer runs first.** `_select_with_ordering` (`qualified_binding_selection.py:278-280`, `:288-290`) returns empty facts + `repeat_relation_unverified` **before** `select_ordered_observation`. Predicate semantic override runs only when `repeat_scheme is None` (`:522-523`). Control semantic/`_semantic_ordering` likewise (`:612-613`).

Compact prompt still says unstructured limits → `unresolved` (`protocol_deconstructor.py:402`) and does not name `not_specified`. Enum now allows it; prompt/enum alignment is residual, not a consumer.

---

### Evidence — observation-relation increment

**Contract** (`observation_relation.py`):

- Group identity hashes `observation-relation/v1` + scheme + all members (`:42-44`). Members must share identity / job / frozen input / episode / condition / parent context / family (`:27-34`). Same `fact_id` or `locator_id` cannot carry two bodies (`:35-41`).
- Links: `repeat_of` (directed) or `same_acquisition` (undirected via sorted ids) (`:73-75`). Distinct fact ids required (`:69-70`). Duplicate agreement keys rejected (`:88-90`).
- No `accepted` / permission / `result_use` fields on the result.

**Grouping is per requirement, not pair explosion** (`observation_relation_input.py:38-76`):

- Identities with a non-null scheme are collected (predicate `repeat_scheme` or control `evaluation.repeat_scheme`).
- All candidate `BindingQualificationPairContext` rows for that identity become **one** group. Loader is `load_completed_candidate_qualification_input` → `build_qualification_pairs_from_verified` (`binding_qualification_support.py:752-760`): **completed candidate comparison**, not qualification judgments. Intake only requires the candidate job completed (`prepared_review_intake.py:18-34`).
- No members → coverage reason `no_observation_sources_in_candidate_input`; `clinical_scope_complete: False`; no model group.
- `plan_observation_relation_batches` (`:15-25`) emits **one group per batch**. If serialized messages exceed `DEFAULT_PAIR_BATCH_MAX_CHARACTERS` (120_000, `binding_qualification.py:28`), it **raises `ValueError`** rather than splitting or truncating (`observation_relation_input.py:22-23`).

**Prompt** (`llm/observation_relation.py:52-66`): no peer answers; reuses `binding_qualification_prompt_payload` (peer `lane_declarations` omitted, excerpts deduped — `binding_qualification.py:90-133`). States: no link ≠ original / no repeats / complete records; same sample ≠ same analyte; do not pick latest/best; do not compute counts/windows/permission. **`_source_material` still embeds the full `repeat_scheme` dump** (`observation_relation.py:40`).

**Quote gate** (`:86-95`): both ends must be in the group; excerpt must be a substring of that `(fact_id, locator_id)` locator; **at least one quote fact must be one of the two ends**, not both.

**Job / receipts:**

- `ObservationRelationJobExecutor` subclasses `JudgmentContentJobExecutor` with a different `pair_model` (`observation_relation_job.py:14-27`). Runtime filters `item.pair_id in set(batch.pair_ids)` (`judgment_content_job.py:292`). That is a real different context on the existing two-lane product runner (`run_cancellable`, same route/receipt machinery).
- Checkpoints and summary force `accepted=False`, `authorized_clinical_adoption=False`, `clinically_qualified=False` (`judgment_content_job.py:267-271`, `:339-341`; `observation_relation_receipts.py:71-78`). Checkpoint `status` stays `"unverified"`.
- Dual-lane agreement is **set intersection of `agreement_key`s** (`receipts.py:59-65`). `clinical_scope_complete` and `replacement_authorized` stay false.
- Replay: `rebuild_observation_relation_input` requires byte-equal rebuilt payload (`receipts.py:21-27`); `verify_completed_content_job` rebuilds summary from receipts and rejects any true acceptance flag (`content_job_verification.py:19-50`).
- Empty `pairs` still creates a summary-only job (`judgment_content_job.py:111-118`).

**Enqueue exception path:**

- `_enqueue_content_job` does not catch `ValueError` (`judgment_content_job.py:73-88`).
- Product intake is `enqueue_prepared_review` → `app_error_boundary` (`page_review_runtime.py:132-141`). Boundary re-raises untranslated exceptions (`evidence_app_errors.py:873-878`). `ValueError` is not in `translate_storage_error`.
- API `map_exception` else-branch is `_INTERNAL` 500 (`app/api/v2/errors.py:225-227`, `:55-60`). The Chinese oversized/stale text is not the user envelope. `InvalidJobDefinitionError` would be 422 but with a generic “步骤不完整” title (`:177-183`). `ScopeViolationError` would become `AppScopeMismatchError` and keep `str(exc)` (`evidence_app_errors.py:788-789`).

**Runtime / UI, not workflow:**

- Executor registered (`page_review_runtime.py:73-79`); owned type (`review_runtime_ownership.py:13`); intake kind (`prepared_review_intake.py:11-18`, `:67-72`); progress map (`prepared_review_progress.py:17`); HTTP kind (`preparedReviewHttp.ts:4`, `:76`, `:143`); panel label (`PreparedReviewPanel.tsx:19`).
- Parent workflow `_schedule("verification")` still enqueues qualification / judgment_content / proposition_evidence **only** (`prepared_review_workflow.py:321-349`). No `observation_relation` child. Declared gap, not done.

**Shared executor leftovers (not crashes):** cancel checkpoint still says “判断内容核实已取消” (`judgment_content_job.py:355-357`); token-limit error still says “判断内容核实输出额度…” (`:70`). Reconstruct error strings remain 判断内容 unless the injected validator raises first.

---

### Inference (separate)

**Highest-impact defect 1 — oversized/stale refusal becomes a 500.**  
Concrete scenario: one identity with a scheme and many candidate facts/locators; messages > 120_000 characters. Source intent is “refuse to split the set.” User-visible path is `INTERNAL_ERROR` / “发生了未预期的系统错误.” Stale `frozen_review` / family mismatch `ValueError`s (`observation_relation_input.py:33-34`, `:48-49`) take the same enqueue path. This is an actual unsafe **operator** path (failed capture looks like an internal crash), not an adoption path.

**Highest-impact defect 2 — scheme-in-prompt can substitute for trigger/count evaluation.**  
The model is told not to compute counts, windows, or permission (`observation_relation.py:65`), but `_source_material` still sends `permission`, `maximum_repeats`, `trigger`, `result_use`. Scenario: scheme `permission=required`, `count_status=specified`, `maximum_repeats=1`. Dual-lane models may emit exactly one `repeat_of` to match the scheme even when excerpts only share an analyte name. One-end quote + substring can pass (`:90-91`). Summary would store an **agreed proposed relationship**. There is no consumer yet, so this is not adoption today; it **is** poisoned input for the next consumer if agreement is treated as relation proof.

**Grouping (not n², but mixed attributes, pre-qualification).** Pairs keep `fact_id` + `fact_attribute` (`binding_qualification.py:44-65`). Links are **fact_id only**. Distinct date facts vs value facts for the same identity remain separate “observations” and may be linked as `repeat_of` / `same_acquisition` without an attribute check. Same-sample different analytes are prompt-only (`observation_relation.py:58`); validation does not compare subject/attribute. The supplied set is **candidate** pairs, including pairs qualification may later mark inadmissible. That matches “source-backed candidate material,” but it is not an admitted-binding set.

**Quote provenance is structural, not semantic.** One-end quote + substring can pass when the cited line is “ALT 80 U/L” with no back-reference to the other fact. Do not treat quotes as proof of 回指.

**Executor reuse is acceptable, not a crash.** `ObservationRelationContext.pair_id` is what the parent executor filters on. `read_type=ObservationRelationRead` matches dataclass kwargs. Default judgment_content `pair_model` remains `BindingQualificationPairContext`.

**No unsafe adoption path in this increment.** Fail-closed selection still empties facts when a scheme is present. Operand arithmetic still does not consult the scheme. Summary flags are hard-false. Workflow does not auto-run this job. **Do not invent a consumer that adopts agreed links.**

**Omission handling:** identities with a scheme and zero candidate pairs are covered, not silently dropped. Identities without a scheme never enter this job. Missing dual-lane reads fail closed (`receipts.py:46-47`). Same model on both lanes is rejected (`:48-50`). `repeat_of` and `same_acquisition` on the same pair are both allowed (different keys); the next consumer must treat that as contradiction.

---

### Recommendation

**This increment (bounded, no new framework):**

1. Map oversized / stale `ValueError` at `plan_observation_relation_batches` / `load_observation_relation_input` to `ScopeViolationError` (or a dedicated `EvidenceAppError`) **with the existing Chinese refusal text**, raised before `_enqueue_content_job` returns. Do not let `map_exception` turn the declared oversized path into 500.
2. Stop sending `repeat_scheme` into the relation prompt, **or** send only `scope` + source excerpts. Permission, counts, `result_use`, and triggers belong to a later deterministic consumer, not to the relationship model.
3. Keep one-group-per-requirement and the no-split rule.
4. Optionally require quotes to cover **both** ends before a link is structurally valid; still do not treat quotes as semantic accuracy.
5. Do not add this job to `prepared_review_workflow._schedule` until a consumer exists that cannot adopt on agreement alone. Keep intake explicit.

**Next consumer (relation graph → permission / selection) — do not default to latest/best or global fact counts:**

- Build a directed `repeat_of` graph and an undirected `same_acquisition` graph from **agreed** keys only; disputed keys stay unresolved.
- Reject or leave unresolved: cycles (`A repeat_of B` and `B repeat_of A`); two `repeat_of` parents for one left fact; `repeat_of` and `same_acquisition` on the same pair; `same_acquisition` between facts whose candidate `fact_attribute` / analyte / method disagree.
- Within a `same_acquisition` component, contradictory **values** stay unresolved; the link is not a replacement and not a truth vote.
- Trigger: evaluate the scheme’s `trigger_excerpt` / condition against **source-backed facts**, not against the model’s decision to emit a link. No link ≠ trigger false; a link ≠ trigger true.
- Count: count **verified `repeat_of` edges in this requirement’s supplied set** after cycle/duplicate filters, compared to `maximum_repeats` only when `count_status=specified`. Do not count all facts in the chart or all same-day labs. `not_specified` must not become unlimited or “one”.
- Calendar: apply `time_limit` only between a proven initial and its repeat, using the scheme’s reference (`initial_observation` / `preceding_observation` / `episode_anchor`) and calendar month/year rules already on `RepeatDuration`. Dates alone do not create the edge.
- `result_use`: apply only after relation **and** permission; `not_specified` / `unresolved` stay fail-closed. `use_last_repeat` means last **verified repeat after a proven trigger**, not `observation_policy.selection=latest`.
- Investigator discretion remains unproved by dates, signatures, or counts.
- Isolated facts in `facts_without_agreed_relationship` are **unclassified**, not “the original observation.”
- Do not treat agreed links as admitted bindings until qualification (object/attribute/source) has also passed for those facts.

---

### Uncertainty

- Live two-lane runs, prompt size distribution, and provider JSON for inlined RepeatScheme / Decimal: **UNVERIFIED**.
- Whether candidate comparisons usually share one `fact_id` across value and date, or emit separate date facts: inferred from pair construction, not executed.
- Reconstruct/cancel still labels some failures as 判断内容; operators may mis-file relation-job failures.
- Compact prompt vs `result_use.not_specified` wording: residual capture-text gap; enum is present.
- Whether `ScopeViolationError` 409 is the product-preferred envelope for oversized refusal vs a new 422 app error: decision for Codex (source fact is that today’s `ValueError` is 500).

---

### Objections, proposed solutions, decision points, questions

**Objections**

1. “Whole-set relation + fail-closed adoption is enough to start using agreed links.” It is not. Agreement is a proposed edge. Scheme-in-prompt plus one-end quotes can create that edge without a back-reference.
2. “Oversized `ValueError` is an explicit refusal.” In this intake it is a 500 generic internal error.
3. Including the scheme in the prompt contradicts “model opinion is not trigger evaluation.”
4. Running this job on **candidate** pairs (before qualification) is consistent with the stated increment, but a later consumer that skips qualification would adopt unadmitted sources.

**Proposed solutions:** (1) typed enqueue error with the Chinese refusal; (2) strip scheme fields from `_source_material`; (3) both-end quote rule; (4) keep workflow disconnected until the graph consumer above exists; (5) next consumer must require qualification on linked facts.

**Decision points for Codex**

1. Should relation prompts see any scheme fields at all?
2. Must quotes cite both ends before agreement?
3. Is 500-on-oversized a capture blocker for this job, or is a typed 409/422 enough to proceed with runtime trials?
4. Must linked facts also be qualification-admitted before the next consumer reads `agreed_relationships`?

**Bounded questions**

1. For a requirement with `maximum_repeats=1`, if both lanes emit one `repeat_of` whose quotes never mention the other fact’s specimen/order id, should summary still list it under `agreed_relationships`? (Source today: yes.)
2. Should identities with a scheme but only `date_range` / `record_time` pairs be grouped, or only `value` / `assertion_basis` observations?
3. Same-session follow-up resume point if needed: enqueue error mapping + `_source_material` scheme fields; re-read those two sites only.

**Safe provisional path:** treat this as a **source-reviewable relationship proposal job** with explicit intake. Do not wire it into parent workflow, qualified selection, frozen calculation, or UI adoption. Keep `repeat_relation_unverified` as the only selection outcome whenever a scheme is present. Clinical acceptance remains Codex-owned.
