# Conference Output: rv1006-whole-temporal-restriction-review-20261008 - evidence_single_object

## Output

**Role pass:** `evidence_single_object` — codebuddy/codebuddy-cli/deepseek-v4.1-flash, effort max, serial, tools-on, read-only. No shell/test/diff/network, no edits, no clinical/DB/env sources, and I did not write the runner-managed report path. I make no acceptance claim; the owner has not accepted the patch and its connected regressions are still failing. No clinical judgment is offered or implied; nothing here authorizes rule activation, fact adoption, or signing.

**Evidence basis (no re-reads in this pass).** The four declared files plus two small windows slightly outside the declared bounds for auditability: `app/protocols/protocol_control_gate.py:4999-5100` (`_statement_scope_proof_issues`) and `app/services/protocol_control_execution.py:2676-2750` (preflight defaults). 16/16 reads+searches consumed; the two greps were (a) the two restriction-version constants across `*.py`, (b) `preserve_unresolved` across `*.py`. Because no shell was permitted I could not diff `base1796417d` against the working tree, so **every statement below describes the current working-tree state, not "what the patch added."** I do not attribute any line to the patch and treat no part of it as already reviewed.

---

## Findings

### F1 (highest impact) — the typed temporal failure can never take the existing zero-reread route, and the artifacts it would need are destroyed before any proof can see them

This is the direct answer to "how to revalidate saved actual source/review/wire without repeatedly regenerating authors after a consumer-only change?"

Call order, with locations:

1. `app/services/protocol_control_execution.py:2554-2596` (`_validated_deep_partial_source`). When the component identity changed (`changed_components`, computed at 2554 through `_same_deep_components_with_current_gate`), the saved `partial_wire` is merely *parsed* for damage (2564-2566, comment: "A damaged wire hard-fails; outdated semantics are discarded, not reused") and then discarded together with `source_target_review`, `source_statement_coverage` and `session_id` (2590-2592). The function returns a **source-only seed**.
2. `2578-2579`: if `_revalidated_source_seed_proof` also fails, the checkpoint is non-resumable; the preflight then leaves the batch at its loop default `decision="refresh_required", reason="new_or_incomplete_batch"` (2742-2743; the failed_final branch at 2852-2877 never refines the reason).
3. `_preserved_unresolved_review_proof` is class-pinned: `last.get("error_classes") != ["SOURCE_TARGET_REVIEW_UNRESOLVED"]` → `None` (2635-2639). The temporal class cannot construct this proof at all.
4. The preflight offers the preserve decision only when `continue_after_final_failure == _INDEPENDENT_DEEP_READ_POLICY` **and** `partial[2].source_seed_proof is None` (2872-2877) — i.e. only while the identity is unchanged. On a consumer-only change `source_seed_proof` is non-`None` by construction, so this branch is dead.
5. JobRunner side, `3599-3629`: on `decision == "resume_partial"` with `resume_wire is None`, the partial is re-fetched and is still the degraded seed, so `resume_wire` stays `None` and the author regenerates from the source seed — new model calls for a change that touched only a restriction **consumer**.
6. Meanwhile the machinery that would make this unnecessary already exists and is class-agnostic: `3532-3580` builds `prior_result` from the saved diagnostic (3550-3554), re-derives the restricted batch with *current* code (`restricted = restricted_batch_from_review(batch, prior_result)`, 3555), returns `_restricted_deep_checkpoint(...)` with `revalidated_restricted_from`, `new_model_calls: 0`, `adopted: False` (3561-3572), and otherwise fails closed with the original typed error code (3573-3580). The equality check against the enqueued proof is at 3545. And `restricted_batch_from_review` already handles the temporal class: `app/services/protocol_control_restricted_source.py:332-334` accepts `{"TEMPORAL_SCOPE_UNRESOLVED"}` with `whole_unit=True`.

So the derivation is class-complete; the **route** is missing, and it is missing for three independently fixable reasons — the proof predicate (2636), the preflight guard (2874), and the early destruction of the raw artifacts (2554-2596). The last is the real blocker: by the time the preserve branch runs, `partial[1]` has `partial_wire=None, source_target_review=None, source_statement_coverage=[]`, so a temporal proof computed there cannot revalidate anything. Any fix that only widens the error-class predicate produces a proof over empty artifacts — that is the first trap to flag to the owner.

Context so the owner does not over-build: for an **unchanged** identity the temporal case already recovers without re-reading — a fully saved review yields `transport.review_calls == 0` (`tests/v2/services/test_protocol_control_execution.py:611-615`), and the in-run derivation at 3688-3695 saves the restricted checkpoint. The gap is specific to identity change (and to any case where the wire was never persisted).

### F2 — whole-unit temporal preservation is non-executable by construction; the independence sibling claim is a separate, proof-bearing path

The distinction the review must hold, stated once and precisely:

- **Non-executable whole-unit preservation** (`protocol_control_restricted_source.py:318-492`) is safe because nothing from the unit can execute. Its obligations are: every statement of the unit is recorded exactly (`:444-459`), spans are the unit's own (`:447`), no retained candidate may touch those spans or units (`:421-430`), the excerpt must be fully accounted for by statement ranges plus separately-sourced scope ranges (`:370-397`), the unit becomes `RESTRICTED_SOURCE` (`:464-467`), and the result must still pass candidate checks (`:472`). Its failure mode is **refusal**, not leakage.
- **An independence/executable-sibling claim** (path 1, `:495-707` plus `_coexisting_statement_proofs` `:214-315`) must be *positively proven*, twice: in the derivation and again in the gate (`protocol_control_gate.py:5014-5098` plus the coverage check `:5197-5207`). The four bindings are literal locability, qualifiers inside the statement's *own* quote (`:4921-4927`), unit-wide pairwise disjointness (build `:269-276`; gate `:5073-5080`), two-way candidate↔quote citation (`:4960-4996`, `:5061-5066`, `:5081-5097`), and full-excerpt coverage under the **strict** separator set in the gate.
- `allow_joining_punctuation=True` exists only for the non-executable whole-unit path (`:4936-4957` docstring explicitly says joining punctuation never proves independence), and the tests assert exactly that boundary (`:391-412`).

The correct audit criterion is therefore: executable content survives only where `independent_scope_proof is not None` **and** the gate coverage check holds; every other unit must be `RESTRICTED_SOURCE` with `proof is None` and zero candidates on its spans. Three verifiable invariants: **(a)** `RESTRICTED_SOURCE` unit ⇒ no candidate binds it or its spans; **(b)** a unit that keeps a candidate ⇒ all its restricted statements carry proofs; **(c)** `ranges_by_index` covers the excerpt under strict separators. (a) and (c) are derivation-enforced; only (b)+(c) are re-asserted by the gate — see F6.

### F3 — exact local heading coverage: conservative in both paths, with one asymmetry worth recording

- In the whole-unit path, a statement's `scope_quote` must be exactly locatable inside the frozen excerpt (`:379-385`); ranges that lie outside the statement ranges and do not overlap them become `extra_scope_ranges`, and the unit excerpt must then be fully covered (`:386-397`). A scope quote that exists only in `heading_path` (not in the excerpt) makes `locate_source_quote_offsets` return `None` → the whole path refuses. That is the conservative direction.
- The gate grounds qualifiers against `[excerpt, *heading_path]` plus table headers (`protocol_control_gate.py:5146-5181`). So a heading-only qualifier is admissible for a **non-executable** restricted statement, which is acceptable, but it can never support an executable sibling claim: `source_statement_context_is_self_contained` reads the statement's own text (`:4921-4927`), and a shared heading forces the whole-unit path — asserted by `:677-700` (`shared_scope` → whole unit, 2 restricted, 0 candidates).
- Residual asymmetry to record, not to "fix" blindly: the two paths disagree on which strings must be claimed in the excerpt (`scope_quote` only vs. all qualifiers), and the joining-punctuation allowance means `，`/`,` inside a unit may remain unclaimed in the non-executable case. Neither can leak executable semantics, because the same path removes every candidate from those units.
- **F3b, the least-checked branch:** the single-statement fallback at `:590-597` requires only `len(indexes)==1`, membership in unresolved/temporal, and (temporal ⇒ `quoted_text == excerpt`). It does *not* require the statement's quote or `scope_quote` to be locatable in the frozen excerpt, unlike every other branch (`:171-172`, `:245-250`, `:370-385`). A single-statement *unresolved* unit can therefore emit a restricted record whose `source_quote` is not in the unit excerpt, if `validate_source_interpretation` permits it (unverified; see Uncertainty). Cheapest consistent fix: add `locate_source_quote_offsets(unit.excerpt, statement.quoted_text) is not None` to that fallback — the helper is already imported and used there.

### F4 — the current preflight's silence about *why* a failed batch is re-authored

`2742-2743` sets `decision="refresh_required", reason="new_or_incomplete_batch"` for every batch before the loop body, and the failed_final branch (2852-2877) never refines it when `partial is None`. A batch with a complete saved diagnostic is therefore reported as "new or incomplete". This matters because it is exactly the case the owner is looking at: the operator cannot distinguish "nothing was saved" from "saved, but revalidation under current components refused". Minimal fix: assign an explicit decision/reason in that branch. No identity change.

### F5 — silent demotion to `refresh_required` in three shapes the real batch may or may not hit

All are fail-closed, but each converts preservation into author regeneration, invisibly:

1. `protocol_control_restricted_source.py:425` — a candidate intersecting a restricted unit but also spanning any non-restricted unit → the whole call returns `None`. The owner's case worked only because all four candidates were fully inside the two restricted units ("zero surviving candidates").
2. `:472` — the derived output must pass `check_protocol_control_batch_candidates`, which validates candidates with `candidate_ids=candidate_id_set` and runs `_check_conditional_exemption_scope_split` (`protocol_control_gate.py:5247-5271`). A retained candidate that references a **removed** candidate's id therefore makes the whole derivation bail instead of restricting the unit.
3. `:81-85` — `additional != indexes` returns `None`; path 1 additionally bails at `:538-541` for any `additional_requirement` review item outside `temporal_indexes`. If the saved review carries a second, non-failing `additional_requirement` point, the patch never engages. The synthetic fixtures only ever contain one (`:321-346`).

Related asymmetry, worth an explicit decision: the clock-capability class cannot preserve a sibling at all — a restricted unit with more than one statement bails (`:166-167`), and every `TIME_PRECISION_UNSUPPORTED` issue must map to a distinct single-unit failed candidate (`:134-145`) — while the temporal class can. Two classes share the `consumer_unavailable` label but behave differently on the same source shape.

### F6 — labeling and defense-in-depth gaps (record now, bundle later)

- **Labeling:** `:433-453` sets `temporal_only` per unit and stamps **every** statement of that unit with `limitation_kind="consumer_unavailable"` plus the unit-level first dimension. In the owner's case that marks four non-temporal statements as a capability gap when their true reason is "independence not proven". The prose is right ("同一原文单元的持续期或跨节点要求尚未完成核对，未证明各要求可独立采用；本单元整体保留待核"); the machine-readable enum is not, and it is the same enum used at `:183` for a genuinely different reason ("当前系统尚不支持原文所需的小时或分钟精度计算"). A consumer keyed on the enum cannot tell "build the clock engine" from "finish the correspondence review", which conflicts with the project rule to separate gap reason from rule judgment.
- **Groundedness:** `protocol_control_gate.py:5101-5209` grounds qualifiers for proof-less restricted statements but never requires `statement.source_quote` itself to be present in `unit.excerpt`. The proof-bearing branch does check it (`:5040-5045`). Every derivation path happens to enforce locability, so this is tamper/legacy hardening; the live defenses are replay re-derivation equality (`tests...:1129-1133`) and catalog/batch equality (`:5322-5330`).
- **Coexistence:** nothing in `check_protocol_control_batch_candidates` (`:5222-5272`) asserts "`RESTRICTED_SOURCE` ⇒ no candidate binds that unit or its spans"; only the derivation guarantees it. Invariant (a) of F2 is derivation-only.
- **Quote reuse through a foreign span** (the one leak-shaped case I could construct): a retained candidate whose atom cites the restricted statement's text but binds a span owned by a preserved unit. The removal check (`restricted_source.py:429`) is span-level only, and for a proof-less restricted unit the gate never runs `candidate_cites_unit_quote` against the restricted quote. Reachability requires a mis-authored span binding that source-interpretation/coverage checks may already reject (unverified).
- Each of these is a gate/identity change → another author-regeneration wave. Do not bump identity for them alone.

### F7 — what is genuinely well-built (state it so it is not "fixed" away)

No frozen-version whitelist exists: `TEMPORAL_RESTRICTION_VERSION` / `WHOLE_UNIT_RESTRICTION_VERSION` (`restricted_source.py:46-47`) are referenced **only** as entries in `_deep_component_identity`'s `compiler_versions` (`execution.py:2000-2001`, import at `:111-112`); the grep over `*.py` found no other consumer. Keep it that way. `preserve_unresolved` is a closed route — preflight (`:2877`, `:2882`), JobRunner (`:3527`, `:3532`), plus tests at `:4405`, `:4479` (not read). Restricted statements are canonically ordered by `(unit, index)` (`:206-208`, `:468-470`), so digests and reuse decisions are order-stable.

---

## Recommendation: extend the preflight with a scoped derived-restriction proof — do not keep the limitation as-is

Keeping the conservative limitation costs a full author regeneration on the exact scenario this consumer change exists for, and it costs it *silently* (F4). Extending is smaller than it looks because the JobRunner branch and the temporal derivation already exist; the only genuinely new piece is a proof that binds the saved artifacts to a current-code derivation.

**R1 (the answer to the reuse question) — four edits, no new stores:**

- (a) Add `_preserved_temporal_restriction_proof(batch, saved)` beside `execution.py:2625-2673`, the same shape as the unresolved proof (diagnostic digest 2667-2669, `statement_ids`, `source_refs`, `adopted: False`; `error_code="PROTOCOL_CONTROL_TEMPORAL_SCOPE_UNRESOLVED"`), reusing the unresolved proof's validations verbatim (2640-2649: `validate_source_interpretation`, `_validate_deep_batch_output(hydrate(wire))`, coverage equality, `validate_source_target_review`) and additionally requiring `restricted_batch_from_review(batch, reconstructed_result) is not None`.
- (b) Evaluate it on the **raw** `saved` mapping at a point where the wire still exists — immediately after the checkpoint read at 2524-2527 and before the `changed_components` branch at 2554, or by exposing the raw checkpoint to the preflight branch. This is mandatory: computed after 2554-2596 it validates nothing.
- (c) In preflight 2872-2877, allow a new decision string under the same frozen `_INDEPENDENT_DEEP_READ_POLICY` guard and record the proof next to 2883/2892.
- (d) Add the string to the JobRunner allowlist at 3527 and select the proof builder by typed class in 3532-3580; the rest of that block (3550-3580) needs no change.

**What a consumer must revalidate before reuse is admitted** (all four, none optional): the real saved source interpretation and the real saved review (validated against the batch, with recomputed coverage equality), the raw wire provenance (hydrated and re-validated by the whole current gate — not a parse-only check), the typed failure witness (exact error-class list, `statement_ids`, `source_refs`, `affected_dependents`, `retry_class`), and the current-code derivation of the restricted batch. Then the diagnostic digest equality check at 3545 ties the enqueued plan to the on-disk artifact. Record `adopted: False`, `new_model_calls: 0`, `revalidated_restricted_from`.

**Explicitly barred** (and none of it is needed): a client- or author-supplied verified flag, any version whitelist, an approved-source-job list, silently copying an old success checkpoint, a new cache or queue, or re-running the author "to confirm". The admission basis is re-derivation under current consumers, not provenance matching.

**Keep the conservative limitation — i.e. do not extend — when any of these hold:** the derivation returns `None` (shared candidate at `:425`; dangling candidate reference at `:472`; `additional != indexes` at `:81-85`/`:538-541`; unproven excerpt coverage); the definition-consumer attempts are absent or inconsistent (`:330-331`, 477-491); or the artifacts fail any single revalidation above. In those cases the honest outcome is the typed failure preserved as-is with a *refined reason* (F4), not a fabricated restriction.

**Mandatory negative checks (acceptance for R1):**

1. Tampered `source_quote` inside the saved restricted statements → the proof is not constructible and the JobRunner equality at 3545 refuses. (NC-replay)
2. Second `additional_requirement` review item → no restriction derived; fall back to `refresh_required` with an explicit reason (NC-additional).
3. Candidate spanning a restricted unit and a preserved unit → no restriction derived (NC-shared).
4. Retained candidate referencing a removed candidate id → no restriction derived (NC-dangling).
5. `partial_wire` absent or damaged in the saved diagnostic → refuse; never substitute the degraded seed (NC-seed).
6. Missing/altered definition-consumer raw answer (chars/sha256 mismatch, duplicate, `None` list) → refuse (mirrors `:477-491`).
7. Coverage equality recomputation mismatch between saved coverage and current `source_statement_coverage` → refuse.
8. Unit excerpt tampered (extra prefix / changed qualifier) → derivation refuses; nothing is adopted (mirrors `:465-484`).
9. Replay the new decision twice with the same checkpoint → byte-identical result, zero transport calls (idempotence).
10. `protocol_control_gate.py` must still reject a proof-less restricted statement in a unit that keeps a candidate (`RESTRICTED_SOURCE_SCOPE_UNPROVEN`, `:5131-5141`) after the route change — the new route must not touch that predicate.

**R0 (no code, do first):** refine the failed-batch reuse `reason`/`decision` (F4) and adopt the three-invariant audit checklist (F2). Optionally harden F3b's single-statement fallback and F6's `RESTRICTED_SOURCE`/no-candidate assertion — but only bundled with a planned identity bump, since each forces another regeneration wave.

---

## Counterexamples (decisive negative cases)

- **NC-additional.** Unit as in the owner's case plus one non-failing `additional_requirement` point: expected `restricted_batch_from_review(...) is None` today (`:81-85`, `:538-541`). Ask the owner whether the real receipt contains such a point; if it does, this patch does not engage on the data it was written for.
- **NC-shared.** Restricted unit A + preserved unit B + one candidate with `frozen_structure_unit_ids=[A,B]`: expected `None` (`:425`) → author regenerated. Correct behavior is bail; do not "fix" it with dependency expansion.
- **NC-overlap.** A restricted statement whose quote covers the whole excerpt (`:753-763`) → `None`; the executable/restricted point cannot coexist. Already covered; keep.
- **NC-shared-scope.** A shared qualifier outside both quotes (`:677-700`) → whole unit, zero candidates, no proofs. Already covered; keep.
- **NC-unreported.** Unclaimed prefix or unread exception (`:465-484`, `:636-702`) → refuse. Already covered; keep.
- **NC-canonical.** Statement order perturbed in a saved batch → digests and output identical (sorted at `:206-208`, `:468-470`). Positive case; no action.

---

## Remaining uncertainty (explicit; nothing invented)

- **No shell/test/diff.** I cannot attribute lines to the patch, cannot confirm the base revision, and ran no regression. The owner's failing connected regressions remain open; I claim no green.
- **Read but not fully verified:** `_same_deep_components_with_current_gate` (`execution.py:2033-2040` is all I saw; body unread). My claim that `compiler_versions` participates in identity by exact list equality — and therefore that a consumer-only change forces a global re-author wave — is an **assumption**, not a verified fact. It is also the premise that gives R1 its value; if the comparator is lenient, R1 becomes a nice-to-have rather than the fix for "repeatedly regenerating authors".
- **Not read at all** (any conclusion touching them is inference): `ProtocolControlAgentRunner` (how the typed `error_detail` is constructed), `validate_source_interpretation`, `validate_restricted_definition_consumers`, `validate_source_target_review`, `requires_temporal_resolution` (the class predicate — the single most consequential unread item, since it decides whether a "temporal" restriction really is a consumer limitation), `intraday_time_fragments`, `_revalidated_source_seed_proof`, `_restricted_deep_checkpoint`, `_deep_results`, the `RestrictedProtocolControlStatement` contract, and the projection consumer of `limitation_kind`.
- **Unverified assumptions:** (1) `compiler_versions` is identity-bearing by exact equality; (2) `hydrate_protocol_control_agent_output` plus the candidate checks guarantee `dispositions` covers every unit that has statements — otherwise `:364-368` can raise an uncaught `KeyError` past the `except ValueError` at `:3690-3696`, turning a controlled refusal into an uncontrolled error (cheap hardening: `if unit_id not in dispositions: return None`); (3) no out-of-set consumer keys behavior on `limitation_kind` or on the two restriction-version strings beyond `_deep_component_identity`.
- **Bounds report:** no clinical files, no database, no environment, no edits, no tests, no network; no clinical or regulatory conclusion, and no final acceptance, which remains Codex's.
