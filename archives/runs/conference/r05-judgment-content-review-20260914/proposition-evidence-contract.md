I’ll inspect the new proposition-evidence contract and prompt against the control spec and existing source/content split, then list only the gaps that must close before a job/consumer.# C03: proposition-evidence contract (reader only)

**Verdict:** usable **candidate** for a pair-local source-relation reader. It is **not** a consumer, not atom truth, not product-complete. `accepted` is absent (good). Do not implement the job until the items below are in the **result + prompt material**.

Aligned already: non-deterministic modes only (`proposition_evidence.py:18-21`); no IE/arithmetic in the prompt (`36-41`); polarity not inverted (`39`); investigator decisive answers require `explicit_investigator_judgment` (`65-67`); quote ⊆ that pair’s `locator.excerpt` (`62-64`); empty pairs do not call a model (`26-27`); `read_candidate_payload` reused. Spec `proposition` is the published string (`control_evaluation_spec.py:44`), distinct from atom `statement`.

---

**P0 — Pin what was checked; do not reuse the qualification blob**

Result is only `pair_id` + relation/basis. Receipts cannot prove *which* `proposition` / mode / atom. `binding_qualification_prompt_payload` dumps full `condition.atom` (kind, modality, `time_constraint`, `observation_policy`, values) (`binding_qualification.py:101-107`). The model is told not to calculate while being given the calculator’s inputs.

Add to each check (and hash them): `identity_sha256`, `proposition` (exact spec string), `determination_mode`, `spec.version`. Prompt material: proposition + pair locator/object/episode node + spec `source_excerpts` only. Strip `operation`/`predicate`/time operands/obligation kind. Combiner stays `evaluate_control_layers_experiment`.

**P0 — Source / target / node must gate decisive relations**

Five-way content checks are structured (`judgment_content.py:14-18`). Here they are prose only (`42-43`). `entails`/`contradicts` can issue with no machine-checked object, node, or investigator attribution.

Add three `supported|rejected|undetermined` fields (same vocabulary as content, not new IE truth): investigator attribution (required supported for investigator-mode decisive), target, node. Decisive relation allowed only if all three are `supported` (investigator mode: basis must remain `explicit_investigator_judgment`). Otherwise force `undetermined`.

**P0 — Partial scope + absence ≠ negation, in the schema**

One pair ≠ `observation_policy` `any`/`all`/`single` (`control_evaluation_spec.py:18`). Contract has no pair-local marker, so a later consumer can treat one `entails` as atom TRUE.

- Literal `scope: pair_local` (only legal value in v1).
- Closed `unresolved_reasons` including `proposition_not_mentioned`, `negation_not_of_this_proposition`, `pair_does_not_cover_observation_policy`.
- `undetermined` ⇒ `basis == "insufficient"` (today `undetermined` + `explicit_statement` is legal, `proposition_evidence.py:24-28`).
- `contradicts` only for an explicit opposite of **this** proposition, never missing mention.

**P1 — Locator/quote tightness**

No `assertion_basis.locator_id == pair.locator_id` (content requires it, `judgment_content.py:18-21`). Date/`record_time` excerpts can “entail” a clinical proposition. Substring quote can be an unrelated clause of a long excerpt.

Require a bound assertion locator; reject non-text attributes. Keep quote-in-excerpt; do not add disease/model lists.

**P1 — Mode × basis**

Investigator is constrained; `semantic` may still use `explicit_investigator_judgment`. Pin: `semantic` decisive ⇒ `explicit_statement` only; `investigator_judgment` decisive ⇒ `explicit_investigator_judgment` only.

---

**Do not add before job:** dual-lane job type, method adoption, mapping `entails`→`TruthValue.TRUE`, observation-policy aggregation, date/value evaluation. Dual-lane `agreement_key` can wait for the job. Combiner remains deterministic/UNKNOWN for non-deterministic atoms until an **approved** consumer exists.

**Deferred (not requested now):** runtime import, model call, receipt replay.
