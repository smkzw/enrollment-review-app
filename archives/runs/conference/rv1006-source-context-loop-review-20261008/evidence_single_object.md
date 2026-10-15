Trellis SessionStart ✓

I'll audit the frozen source-context loop. First, locating the named definitions in the read set.

Definitions read. Now three targeted greps to confirm the loop mechanics (`MAX_SOURCE_INSERT_REPAIRS`, insert trigger, and whether `observation_policy` participates in coverage checks).

# Conference Output: rv1006-source-context-loop-review-20261008 - evidence_single_object

## Output

### 0. Audit basis and scope

Source-only review of frozen HEAD 4e5edf3c read set; no tests, no shell, no edits, no runtime verification. Owner-supplied runtime facts (deep 1–16 reused zero calls; deep 17 terminated `SOURCE_REQUIREMENT_INSERTION_LIMIT_REACHED` after 12 physical calls; coverage entry `linked_candidate_indexes [0,1]`, `action_candidate_indexes []`, `status candidate_linked`; two delta inserts preserving action but not time words in `atom.statement`) are treated as **evidence I did not independently verify**; the code reading below explains them consistently.

### 1. First cause (evidence, code-level)

The observed duplicate-insert loop is **not** primarily a source-context defect. It is a guard asymmetry inside the deconstructor execute loop:

- `app/agents/protocol_control_deconstructor.py:166` — `MAX_SOURCE_INSERT_REPAIRS = 2`; incremented at `:10238`, enforced at `:9263`. "Two delta inserts" is exactly the budget; the limit error is deterministic exhaustion, not a transient condition.
- Coverage: `action_candidate_indexes` is appended only when `time_scope_preserved` **and** the atom excerpt matches the action (`:4441-4453`). `time_scope_preserved` for non-prohibition statements comes from `_candidate_preserves_source_time_words` (`:4668-4707`), which requires every one of ≥2 `time_words` to appear in the rendered atom statements (or a literal scope citation). A candidate that binds time only via `observation_policy.scope` + `review_node_bindings` fails this test by construction; the `obligation` role is then stripped (`:4489-4490`) and the status becomes `candidate_linked` via `unit_candidates` (`:4566-4573`). This exactly reproduces the owner's `[0,1] / [] / candidate_linked`.
- The duplicate-stop guard (`:9210-9218`) fires only when `entry.status == "candidate_linked" and entry.action_candidate_indexes` — i.e. it requires the very temporal proof whose absence causes the loop. When the unexpressed aspect is temporal, the guard can never fire, so each review cycle re-enters `SOURCE_TARGET_ADDITIONAL_REQUIREMENT` insertion until `MAX_SOURCE_INSERT_REPAIRS` is consumed. The guard's own message — "已有候选引用该原文，但判断语句尚未证明完整表达；停止重复补入，待逐项核对" — describes the observed case precisely; only its condition is incomplete.
- Consequence: a misleading terminal code (`INSERTION_LIMIT_REACHED` suggests retrying with more inserts) instead of the intended `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` / `retry_class=source_semantic_review` route (`:9228-9262`).

**Recommendation — choose C, narrowed.** Extend the guard to also fire when the statement's action is **literally cited** by an existing candidate regardless of temporal preservation. Predicate: for candidates whose `source_structure_unit_ids` include the statement's unit, any atom with source-span intersection where the normalized statement quote is contained in `atom.statement` or in any `atom.source_excerpt` (reuse the same literal rules already used at `:4435-4453` and `:4608-4634`). Derive the diagnostic `candidate_indexes` (`:9224-9227`) from this citation set, not from unit membership.

This is the smallest coherent first change because it:
- kills the redundant second/again insert (observed: "the second nearly duplicate candidate is inserted instead of resolving the first candidate's temporal/footnote problem"),
- emits the honest unresolved terminal (`需要核对`, `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`, statement stays `candidate_linked`, no adoption), satisfying the 1006 rules "preserve gates, no false adoption, do not force an unresolved footnote to zero",
- is code-only: one guard condition + one small evaluation helper in `protocol_control_deconstructor.py`, no prompt, manifest, wire, payload, or model-contract change.

**Deliberately excluded from the necessary scope:** any change to `_candidate_preserves_source_time_words` (that is D; see §3), any reader-packet change (A), any planning-packet change (B), any new coverage field. Optional only if Codex wants it: naming the unexpressed aspect (temporal vs other) in the error detail.

### 2. Sequencing: two causes, not one

Cause 1 — loop non-convergence (above): independent of source context; must be fixed first, because it currently converts any temporal-expression gap into budget exhaustion and a wrong terminal class, and it corrupts the workshop evidence trail for the actual coverage gap.

Cause 2 — source-context gap: the reader packet (`build_source_interpretation_prompt`, `app/agents/protocol_control_source_interpretation.py:2676-2768`) carries only owned units (row + `table_context`) and context units; numbered notes after the table are absent (leading rows only: `_deep_batch_chunks`, `app/protocols/protocol_control_planning.py:976-1004`). The existing frozen procedure target holds note 7's excerpts but for a different operation label, so source/target review correctly refuses coverage. **A and B address this cause and cannot terminate Cause 1**: even with note text supplied, the target review would still refuse the different-operation target, inserts would still be requested, and the same guard gap would still swallow them. Conversely, C does not resolve the row's coverage — after C the item honestly routes to item-by-item review. These must be sequenced (C now; A or B in a later, separate bounded step), not combined: a combined change makes the rerun's causality unreadable and mixes a loop fix with evidence-packet/receipt changes.

### 3. Options evaluated

- **A (reader packet + frozen procedure excerpts):** rejected as first change. Structural risks confirmed: exact row/note identity is not carried (notes are not in the batch; excerpt injection would be an unverifiable association), and the concrete counterexample is already in evidence — feeding the different-operation target's note-7 excerpts would invite taking an unrelated paragraph as this row's evidence, which the reader's own grounding rules (`validate_source_interpretation`, `:2552-2626`) cannot distinguish. Also does not fix the loop.
- **B (note units as read-only context at deep planning):** correct direction for Cause 2, but blocked on parity/reuse mechanics I verified: `_flow_footnote_refs` (`app/protocols/procedure_catalog.py:367-460`) needs `StructureBlock`s, which exist only at extraction; the job payload (`_job_payload`, `app/services/protocol_control_execution.py:942-1005`) carries `extraction_snapshot` (a reference), not blocks; `_preflight_deep_source` (`:2905-2920`) recomputes the plan from the payload without block access, and `_execute_closure` (`:1788-1797`) must produce an identical plan. So B requires either freezing note↔table links into the coverage manifest — which changes `coverage_manifest_sha256` inside `_deep_component_identity` (`:1984-2000`) and would invalidate the deep 1–16 receipts — or a payload contract change. Not this window.
- **C (stop re-inserting when already literally source-linked):** chosen, with the citation-based predicate above rather than the coarse "unit identity" reading, which would wrongly block inserts for an independent requirement that merely shares the unit. The predicate is per-statement/per-quote, so the named C risk is neutralized at the level the evidence allows.
- **D (frozen node + `observation_policy.scope` as temporal proof):** rejected for this window. It is the only option that would make the two existing inserts count, but it converts a model-authored binding into source-side temporal proof; the 1006 rules ("no author-asserted scope becomes source proof", "no phase/day alias guessing") and the named D risks (multidate/relative windows) apply. It is defensible only if Codex can show the wire validator certifies `observation_policy.scope` as source-located and the binding as source-derived (`_invalid_observation_policy_paths`, `:6290`; prompt rules `:6765` suggest scope must cite the atom's source, but I did not read the validator body, so this is unverified), and even then it is an adoption-semantics change outside the window.

### 4. Positive / negative / neighbor variants

- **Positive:** observed deep-17 row (≥2 time words, action literally cited by candidate(s), time only in `observation_policy.scope`/node bindings). With the widened guard, after the first insert exists the next `pending_additional` cycle stops with `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`; no second insert; no `INSERTION_LIMIT_REACHED`; statement stays unresolved.
- **Negative (must not fire):** (i) candidate cites the same unit but a different requirement's quote — citation predicate false, insert budget behavior unchanged; (ii) statement accepted by review (not in `pending_additional`) — path untouched; (iii) existing action_candidate case — fires as today.
- **Neighbor:** two independent requirements in one unit — only the quote actually cited is blocked; the sibling quote still walks the normal insert path. Sibling demotion (`:4602-4645`) and the "keep gate-verified inserts before stopping" early-return (`:9162-9188`) are unaffected. Unresolved note 7 stays unresolved in every variant; nothing maps aliases or zeroes it.

### 5. Consumers and reuse implications (C)

Consumers: only the execute-loop guard and its attempt diagnostic (`source_candidate_alignment`, `coverage`, `partial_wire` shapes unchanged). Reuse: `_deep_component_identity` hashes source/manifest/plan/prompt text, not code — a code-only guard fix therefore does not invalidate deep 1–16 receipts (my reading; Codex should confirm); only batch 17 reruns, and with the guard it terminates in ~2–4 physical calls instead of 12.

### 6. Objections, decision points, bounded questions

- Highest-impact defect found: the guard/adoption asymmetry (§1) — the loop is deterministic and self-inflicted, and I consider it the correct first repair target over A/B.
- Objection to a possible cheap fix: widening the guard to `linked_candidate_indexes` alone would stop inserts for unrelated same-unit requirements; use the citation predicate, or document why unit-level blocking is acceptable.
- Decision points: (1) whether the window endpoint requires this row's coverage resolved (then C alone insufficient and A/B/manual correction must follow, sequenced) or the honest unresolved terminal suffices; (2) confirm the citation predicate definition; (3) confirm code-only change is receipt-neutral.
- Bounded questions for Codex: **Q1** — is the post-C terminal (`需要核对`, `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`, item stays `candidate_linked`) an acceptable window artifact, or must the item be resolved via a sourced correction in this window? **Q2** — approve the literal-citation predicate as the widened guard condition (not `linked_candidate_indexes`)? **Q3** — confirm that deconstructor-only code changes do not invalidate batches 1–16 receipts and that rerunning deep 17 alone is the intended path.
- Remaining uncertainty: I did not read the validator body for `observation_policy` scope grounding, the resume/reuse path `_ResumableSourceReview`, or the runner's terminal classification for the guard result; and the runtime facts are owner-supplied. If Q1 is answered "resolve", the provisional safe path remains C now (bounded, honest stop) with A/B designed as a separate next window — not bundled.
