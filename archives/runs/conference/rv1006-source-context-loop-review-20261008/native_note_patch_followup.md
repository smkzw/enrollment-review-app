Continuing the same bounded review. Locating the patched definitions first.

Now reading the eight patched definitions.

Reading the remaining four definitions plus two targeted context greps for the patched guard block and bridge tail.

Two final targeted greps to close the exact guard construction and the source-link refresh predicate.

# Conference Output: rv1006-source-context-loop-review-20261008 - native_note_patch_followup

## Output

### 0. Basis

Read-only source review of the frozen working patch. Eight targeted reads completed (table_footnote_context_links / _flow_footnote_refs, batch + bridge validators, deep planning, _prepare_source_in_session + _job_payload, _execute_closure + component/material identity, _preflight_deep_source + _source_interpretation_requires_refresh, reader prompt, _literally_cited_action_candidates + citation-stop site). No tests run, no originals inspected; the 1135-passed suite, the fixture plan-hash equality, and the 15/75 preflight are owner-supplied and treated as unverified claims throughout.

### 1. Citation stop (C) — as implemented, no must-fix; one residual false-positive class

Implementation: `_literally_cited_action_candidates` (`app/agents/protocol_control_deconstructor.py:4411-4434`) returns candidates whose `source_structure_unit_ids` contain the statement's unit and whose obligation-group atom has span intersection with the unit and `quote in normalize(text)` for `text ∈ [atom.statement, *atom.source_excerpts]`. The stop site (`:9236-9250`) builds `cited_candidates` as `action_candidate_indexes ∪ literally_cited…` for entries with `status == "candidate_linked"`, intersects with the target-review `additional` list, and returns `需要核对` (`:9251-9292`) with class `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` and `retry_class=source_semantic_review`. This is exactly the previously recommended shape: it is per-statement and per-quote, not per-unit, so the "same unit, different requirement" objection is neutralized for distinct quotes.

Counterexample class that remains: strict containment `quote ⊆ atom text` can credit a different statement's candidate when one sibling quote is a substring of another sibling's text (e.g., unit statements S1="第1天给药", S2="第1天给药后4小时采血"; S2's candidate atom.statement contains S1's quote → S1's insert is suppressed). Effect is bounded and honest — item stays `candidate_linked`, batch terminates 需要核对, nothing is adopted — so I classify it as a residual limitation, not a must-fix. Optional later hardening would be equality-style or quote-region matching; I do not recommend adding it inside this window (it risks under-matching legitimate citations).

### 2. Note-context repair (B) — mapping, scope, closure, parity

Mapping (`app/protocols/procedure_catalog.py:463-500`): per-unit `^n` numbers from member-ref block texts, notes via the existing `_flow_footnote_refs`, keyed by referring unit, values are manifest note unit ids; per number it is all-or-nothing (drops the link if any note paragraph ref lacks a manifest unit). Chain: producer computes it on verified snapshot blocks (`app/services/protocol_control_execution.py:725, :800`), payload freezes it conditionally (`:967-968`), closure and preflight pass the same payload key (`:1801`, `:2910-2926`). Contract closure: `validate_batch` (`app/domain/contracts/protocol_controls.py:2624-2637`) confines keys to owned units, requires linked note units to be in batch owned/context, unique, no self-link, and no table rows; `validate_bridge` (`:2953-3003`) enforces note ids ⊆ manifest, folds them into `expected_context_ids`, exempts them from the non_control-context prohibition, and enforces exact closure `actual == expected ∪ (actual ∩ table-context rows)`. Planning (`app/protocols/protocol_control_planning.py:1273-1284, :1336-1339`) raises `table_note_source_unknown` for out-of-manifest refs, merges note ids into context before chunking so the note units become real `context_units` of the owning chunk, and attaches the batch field only for owned markers. Reader path (`app/agents/protocol_control_source_interpretation.py:2684-2685, :2770-2775`): note number → unit-id map on the owned entry, note text visible through the ordinary context list, plus explicit instruction that the relation proves location only, that note content must not be copied as the row's requirement, and that the note is handled by its own batch.

Read-only property holds in code: quoted_text must ground in owned heading/excerpt (`:2544-2551`), scope and time words cannot ground in note context (only heading/own table headers/prior same-clause), the statement `structure_unit_id` enum is owned-only (`:2788-2791`), and context units appearing as statements raise `SOURCE_COVERAGE_INVALID`. So no, a discovery `non_control`/context note is not being turned into a patient requirement or clinical proof; it can only inform the reader's judgment while every citable field remains owned-grounded. Residual: that influence is prose-level, not link-auditable.

Parity: producer, closure and preflight all derive the plan from the same frozen payload key with the same function; the legacy path is exactly `None ≡ {}`; the note key is deliberately absent from `_DEEP_SOURCE_IDENTITY_FIELDS` (`app/services/protocol_control_execution.py:1953-1958`), so old source jobs remain compatible and note changes are caught per batch by `_same_deep_batch_material` (`:2082-2092`). No parity or scope defect found in code.

Residual limitations I could substantiate:
1. Header-carried markers silently do nothing: links are keyed to the unit carrying `^n`; if the marker sits on a leading header row (always context, never owned) or any non-deep unit, planning's owned filter drops it, and the data-row reader sees neither the note nor the marker — a silent no-op subclass (the observed row carried the marker itself, so the fix lands there). Fixing this needs column-conditional propagation; explicitly out of window.
2. Split logical tables: `_flow_footnote_refs` stops at the next table block (`procedure_catalog.py:419-422`); only the fragment followed by the numbered list gets notes.
3. All-or-nothing per number with no diagnostic (silent reproduction of the old gap for that number).
4. Prompt sentence "该脚注由其自身所属批次处理" presumes the note unit is deep-owned; if discovery classified note 7's paragraphs `non_control`, no batch owns them and the sentence is inaccurate for note-local requirements.

### 3. Reuse identity — the 15/75 rationale from code

- The new field is `exclude_if` empty (`protocol_controls.py:2561-2563`), so batches without note links are byte-identical between pre-patch saved batches (re-parsed with the new model → empty, excluded) and the current plan; `_same_deep_batch_material` therefore returns True for completed batches 1-15 and False for the batch owning the marker row (context units + links changed) → `planning_material_changed`, the single justified reread among completed batches.
- The 75 refresh-required are structurally explained before any note logic: the default decision for any batch without a completed step is `refresh_required / new_or_incomplete_batch` (`protocol_control_execution.py:2950-2951`); the note field is not the cause. Your caution is correct: the optional payload field does not justify rereading old successes.
- The one hinge I cannot verify from source: `_deep_component_identity` (`:1989-2062`) keeps `schema_version` v3 and does not include the note key, but does include `compiler_versions` and `wire_schema_sha256`, and `_same_deep_components_with_current_gate` (`:2065-2079`) tolerates drift only in `validator_version`. If the C/B patch added or changed any `compiler_versions` entry (the current list contains `source-insert-cited-statement-stop/v1`, `:2022`) or the wire schema since the source job ran, batches 1-15 would report `component_material_changed` and the 15/75 claim would be wrong. The claim is consistent with code only if those identities pre-date the source job's checkpoints. Verification: dump the preflight reason histogram — 15 × `same_material_and_current_gate` (or restricted variant), 1 × `planning_material_changed`, 75 × pre-existing reasons, zero `component_material_changed` / `prompt_material_changed`.

### 4. Classification

- Must-fix: none proven from source for either C or B. C matches the recommended minimal shape; B keeps gates, context-only semantics, exact closure, and per-batch reuse scoping.
- Residual limitations: the four in §2 (header markers, split tables, all-or-nothing drop, note-ownership sentence), plus the §1 substring suppression and the prose-only auditability of note influence.
- Optional redesign: none recommended; do not widen into column/note propagation or discovery reclassification in this window.

### 5. Owner decision questions and remaining uncertainty

1. Confirm the frozen discovery disposition of note 7's paragraphs. If any is `non_control`, either soften the reader sentence "该脚注由其自身所属批次处理" to not assert an owner, or explicitly record that note-local requirements are outside deep ownership. If they are candidate/uncertain, the sentence is accurate and I withdraw the concern.
2. Provide the preflight reason histogram (§3) to close the reuse hinge; and state whether the patch changed `compiler_versions` or the wire schema relative to the source job. If it did, 15/75 must be re-derived.
3. For the deep-17 rerun under the patch: expected terminal is the citation stop (`SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`, status 需要核对, first or second insert retained in partial wire) rather than `INSERTION_LIMIT_REACHED`; please confirm the observed terminal class and that the stop fired before a further insert.
4. Measure batch 16's reader-prompt size: note context is not bounded by `_MAX_SCHEDULE_ROW_CONTEXT_CHARS` (that bounds same-row context only), so long note lists are an unmeasured prompt-budget risk.
5. Remaining uncertainty (mine): the owner's runtime facts, the connected-module pass, the fixture hash equality, and the real 15/75 run were not verified by me; the material-change path and the citation-stop path were derived from source only.
