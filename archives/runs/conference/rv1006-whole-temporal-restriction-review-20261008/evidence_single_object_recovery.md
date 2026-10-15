Bounded follow-up acknowledged: 8 targeted reads, read-only, no edits/tests/shell. Starting with the decisive definitions.

# Conference Output: rv1006-whole-temporal-restriction-review-20261008 - evidence_single_object

## Output

**Role pass:** `evidence_single_object`, same session, codebuddy/codebuddy-cli/deepseek-v4.1-flash, max, read-only. 8/8 targeted reads consumed this pass (`execution.py:2033-2110, 2486-2750, 3435-3515, 3625-3715`; `restricted_source.py:300-492, 698-731`; tests `490-558, 4490-4680`). No shell/tests/edits/network/clinical/env. I did not write the runner-managed report. **I claim no green, no publication, no global dependency closure.** The owner's real-call evidence is owner-observed; I only verified the code path that can produce it.

**Answers to the five priority questions, with evidence:**

| # | Question | Answer |
|---|---|---|
| 1 | Does any new route admit changed source or executable semantics? | **No** (see F5). |
| 2 | Does a coverage/witness mismatch fail closed rather than masquerade as a cache miss? | **Mostly yes, with one non-uniform hole (F1/F2): mismatch cannot be silently reused, but through path 1 it can produce an uncontrolled exception and a mislabeled proof.** |
| 3 | Is declaration skipped or budget rebound/reset? | Declaration is skipped when consumers already exist and runs fresh otherwise; the preserved branch binds the budget exactly once before the call; `new_model_calls` is receipt-derived. Budget *reset* semantics unverified (Limits). |
| 4 | Are global scope doubts retained? | Every artifact sets `adopted: false`; the saved review is preserved in the checkpoint (test 4657). The `scope_complete`/`unresolved_reasons` consumer records were not re-read this pass (Limits). |
| 5 | Is the proof over an actual failed artifact, not a user-controlled flag? | **Yes**: proof is computed from the store-read diagnostic, carries `diagnostic_sha256` + `restricted_batch_sha256`, is recomputed at execution from the store, and a client-modified plan proof is rejected (test 4590 → `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`). No whitelist, no approval flag. |

---

## Findings

### F1 (highest impact). `_preserved_temporal_restriction_proof` re-indexes the raw failure witness without a guard → uncontrolled `TypeError`/`KeyError` where a controlled refusal is required

**Location:** `app/services/protocol_control_execution.py:2725-2726`

```python
"statement_ids": result.attempts[-1].error_detail["statement_ids"],
"source_refs": result.attempts[-1].error_detail["source_refs"],
```

Everything before this line can succeed *without* `error_detail` ever having been validated as a mapping: `restricted_batch_from_review` (2709) returns through **path 1** (`_restricted_statement_batch_from_review`) whenever that path succeeds, and `_whole_unit_restriction` — the only place that proves the typed detail via `_temporal_restriction_indexes` — is merely the fallback. Path 1 accepts `TEMPORAL_SCOPE_UNRESOLVED` in its class intersection (this list was read in the prior pass at `restricted_source.py:512-519`; **not re-verified this pass**, see Limits) and does not require the detail mapping.

**Counterexample (concrete, all inputs legal):** a saved diagnostic with
- `attempts[-1].error_classes == ["TEMPORAL_SCOPE_UNRESOLVED"]`,
- `attempts[-1].error_detail is None` (or a mapping lacking `statement_ids`),
- `partial_wire = None`,
- a review whose items are all decision `unresolved`, covering every statement index, and statements with empty `unresolved`,

then path 1's no-wire sub-branch produces a **candidate-free, proof-free, non-empty** restricted batch (candidates `[]` because `has_wire` is false; `proofs` stays `{}`, `restricted_source.py:566-597, 702`). That satisfies every admission check at 2710-2714 and `_validate_deep_batch_output` at 2715, and the function then does `error_detail["statement_ids"]` on a `None` → `TypeError`.

**Blast radius:** in `_validated_deep_partial_source` the proof is evaluated inside a plain boolean chain (`:2576`), so the exception escapes preflight; in the preserve branch it is inside `try: … except ValueError` (`:3652-3664`), and `TypeError`/`KeyError` are **not** `ValueError` → the mismatch surfaces as an uncontrolled executor error instead of `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID`. That is exactly the failure mode change 4 claims to have removed; the conversion covers source-validation `ValueError`s, not the proof builder's own indexing.

**Honest reachability:** I found no evidence that a natural runner-produced temporal diagnostic has a missing detail (the runner emits class and detail together), so the shape is reachable from legacy/foreign or manually composed checkpoints, and from any path-1 admission with a damaged detail. Cost of the guard is one line; the failure mode without it is a crash class the owner is explicitly trying to eliminate.

**Smallest correct fix (also fixes F2):** stop re-deriving the witness from the raw attempt. Require the typed derivation *inside the proof* and take the fields from it:

```python
proven = _temporal_restriction_indexes(batch, result, whole_unit=True)
if proven is None: return None
...
"statement_ids": sorted(proven),
"source_refs": sorted({span for i in proven
                       for span in units[statements[i].structure_unit_id].source_span_ids}),
```

Alternatively guard `isinstance(detail, Mapping)` and return `None`. Do **not** widen the `except` to bare `Exception` — that would mask real bugs.

### F2. The "temporal" proof label can be attached to a restriction actually caused by unresolved review items

**Location:** `execution.py:2695-2728` + `restricted_source.py:710-731`

The builder only checks the *class list* of the last attempt; the restriction itself may come from path 1's `unresolved` logic, in which case `_temporal_restriction_indexes` never ran, `temporal_indexes` is empty, and the restricted statements carry `limitation_kind="interpretation_unresolved"` (`restricted_source.py:448-452`) — while the proof is stamped `preserved-temporal-restriction-proof/v1` and the eventual failure falls back to `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID` (2727). The audit then says "typed temporal consumer gap, wholly non-executable" about a batch whose real reason is target-correspondence non-closure. The derived restricted statements themselves stay honest; only the proof/diagnostic layer misattributes. Fixing F1 as above (requiring `_temporal_restriction_indexes(..., whole_unit=True)` inside the builder) removes this by construction.

### F3. Temporal-class fallback reuses unresolved-class code, text, and provenance key

**Locations:** `execution.py:2727` (`error_code: "PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID"`), `:3697-3704` (fallback `StepFailure` + `preserved_unresolved_from`).

For the temporal class the fallback raises the generic `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID` with the unresolved-class wording ("原文对应关系仍未核清") and stores provenance under `preserved_unresolved_from`. The frozen continuation policy is itself keyed by error code (`[:4502-4505]` lists `PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNRESOLVED`), so a temporal attempt that cannot be re-derived becomes unclassifiable by policy and mislabeled for the operator. Cheap fix: branch code/text/key on `proof["schema_version"]` (use a typed `PROTOCOL_CONTROL_TEMPORAL_SCOPE_UNRESOLVED`). Test coverage: the negative family at 4643-4649 exercises only `changed_proof` / `source_clear` / `restriction_error` for the unresolved class; no temporal fallback code is asserted.

### F4. Definition-consumer evidence is not rehydrated before revalidation (fail-closed but misattributing)

**Locations:** `execution.py:2704-2708` (rebuild by filtering the diagnostic mapping) vs `restricted_source.py:479-487` (raw-answer rehash).

The proof rebuilds the run result from `saved` alone. Attempt raw text is not part of `run_result` (test-asserted at `[:526]` in the prior pass — `"raw_output_text" not in checkpoint["run_result"][...]`; not re-verified this pass), it lives in `attempt_raw_outputs`. So a diagnostic that **already carries** `source_definition_consumers` will fail `len(raw) != attempt.raw_output_chars` / sha mismatch at `restricted_source.py:480-483` and raise `ValueError("受限定义登记原答与实际回执不一致")`, which the preserve branch maps to "已保存的未决来源未通过当前逐项重核" — a message that misattributes a rehydration gap to the source review. Outcome is fail-closed; only the diagnosis is wrong. Fix: rebuild via the existing checkpoint rehydration pattern (checkpoint + `attempt_raw_outputs`, the same shape used by `_saved_deep_run_result` in the consumer-reuse tests), or explicitly refuse consumer-carrying diagnostics with a distinct message. The owner's real batch has `source_definition_consumers is None` and takes the fresh-declaration path (change 3), so this does not affect the observed case.

### F5. What is verified correct (state it so it is not "fixed" away)

- **No changed source, no restored executables.** The changed-compiler guard requires all identity keys except `compiler_versions`/`validator_version` to be exactly equal (`:2574-2575`), the transport receipt route to match the frozen route (`:2536-2541`), the prompt and batch material to be current (`:2522, 2544`), the repair contract to be current and no source-correction pending (`:2565-2566, 2557-2561`), and then *both* a constructible proof (`:2576`) and `state == "reused"` (`:2579`). Any failure falls through to the wire-parse/source-seed path and, with the identity changed, to author re-derivation — refusal, not admission.
- **The proof forces wholly non-executable output**: `restricted.candidates` empty, statements non-empty, **no** `independent_scope_proof` (`:2710-2714`) — asserted by the `executable_sibling` negative case (`tests:496, 545`). This is *stricter* than the unchanged-identity unresolved route, which may still carry a candidate (test `:4660`), and that asymmetry is the principled part: executable semantics are never restored across a compiler change.
- **Delegation is real, not parse-only**: the derivation recomputes coverage and demands equality (`restricted_source.py:340-341`), requires the original hydrate to pass `check_protocol_control_batch_candidates` (`:339`) and the output to pass it again (`:472`), re-hashes the definition raw answers (`:479-487`), and the proof then runs the **full** gate `_validate_deep_batch_output` on the derived batch (`:2715`). Negative family confirms: `source`, `prompt`, `schema`, `repair`, `missing_wire`, `boolean_ids`, `coverage`, `unread_source`, `executable_sibling` all refuse, `bad_wire` raises, and the saved diagnostic is byte-unchanged (`tests:492-551`).
- **Whole-unit temporal preservation + exact local heading coverage unchanged** (`restricted_source.py:347-397`): the typed range must be proven (`_temporal_restriction_indexes(..., whole_unit=True)`), every restricted unit's statements must be disjoint and locatable, a `scope_quote` must be exactly locatable in the excerpt, non-overlapping extra scope ranges are admitted, overlapping ones are refused, and the whole excerpt must be covered (`allow_joining_punctuation=True` — punctuation only, never a semantic claim). Local headings therefore cover *source text* only; they do not establish independence, matching the comment at `:377-378`.
- **Change 3 verified structurally**: declaration runs only when definitions exist and consumers are absent (`:3470-3471`); the preserved branch binds the budget immediately before that call (`:3473-3477`, called with `bind_budget=True` at `:3687`) while the normal branch passes the default `False`; receipts are extended from the transport (`:3488-3489`) and `new_model_calls = len(checkpoint["model_call_receipts"])` (`:3695`), asserted by test `:4652-4656`.
- **Proof vs plan cannot be self-asserted**: execution recomputes the proof from the store (`:3654-3659`) and requires equality with the enqueued entry (`:3665`); a modified plan proof fails with `DEEP_SOURCE_INVALID` (test `:4590, 4646`). `adopted: false` is set on both the success-artifact and the failure-diagnostic returns (`:3695, 3703`) and in both proofs (`:2691, 2727`).

---

## Recommendations (ordered, smallest first)

- **R1.** Fix F1 by deriving `statement_ids`/`source_refs` from `_temporal_restriction_indexes(..., whole_unit=True)` (or guard the mapping and return `None`). This also removes F2. One function, no new machinery.
- **R2.** Branch the temporal fallback code/text/provenance key (F3) on `proof["schema_version"]`; keep the unresolved-class behaviour untouched.
- **R3.** Either rehydrate `attempt_raw_outputs` when rebuilding the run result (F4) or refuse consumer-carrying diagnostics explicitly; do not leave the misleading "source review failed" message for a rehydration gap.
- **R4.** Add the negative checks below; the current family covers identity drift but not witness-shape drift through path 1.
- **R5 (do not).** No version whitelist or approval flag (none exists today — verified: the two restriction constants appear only as `compiler_versions` entries, `execution.py:2000-2001`, prior-pass grep); no new cache/queue/framework; do not widen the zero-candidate requirement to the unresolved route or the sibling-preservation path to keep parity — the current asymmetry is correct.

## Mandatory negative checks

1. Temporal class + `error_detail = None` + all-`unresolved` review → `partial is None`, **no exception**, and the JobRunner path yields a controlled code.
2. Temporal class + detail lacking `statement_ids` / non-int ids / wrong `source_refs` (existing `boolean_ids` case extended to path 1 shapes) → refusal, not crash.
3. Proof inequality (modified plan proof) → `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID` (exists at test `:4590`; keep for the temporal schema too).
4. Derivation raises during preserved reconstruction → `PROTOCOL_CONTROL_RESTRICTED_SOURCE_INVALID`, never `EXECUTOR_ERROR` (exists at `:4628-4631` for the unresolved/temporal cases; verify the gate-error branch, which is a different exception family — see Limits).
5. Diagnostic carrying `source_definition_consumers` with stripped raw text → explicit refusal with a non-misattributing message (F4).
6. Coverage list emptied (`tests:521`) and excerpt extended (`tests:523`) → refusal (exists).
7. `partial_wire` damaged → raise/controlled refusal, saved diagnostic byte-unchanged (exists at `tests:517, 541-551`).
8. Replay the preserved temporal decision twice → identical checkpoint, zero model calls, no writes to the old job (`tests:4640-4642` pattern applied to the temporal schema).

## Remaining uncertainty / limits (nothing invented)

- **Not re-read this pass (prior-pass or unread):** path 1's class-intersection and review-admission block (`restricted_source.py:495-597`), `_temporal_restriction_indexes` (`:50-96`), the preflight writer that emits the temporal proof/`unresolved_review_proof` entry (current numbering ≈`execution.py:2752-3000`; only the execution reader at `:3641-3665` was verified), `_bind_control_request_budget` (does it cap or reset?), `take_call_receipts` accumulation semantics, `_resumable_saved_source_review` internals, and tests `1100-1320`. F1/F2 are conditional on path 1 still accepting the temporal class as it did in the prior revision.
- **Top bounded question for Codex:** is `ProtocolControlGateError` (and `ProtocolControlAgentWireValidationError`) a `ValueError` subclass? If not, then `_validate_deep_batch_output` at `:2715` raising inside the preserve branch escapes the `except ValueError` at `:3660` as an uncontrolled error — the same defect class as F1, in the one place change 4 claims to have fixed it. The prior-pass observation that these exceptions are caught *separately* from `ValueError` suggests they are not subclasses, but I did not verify the class definitions.
- Second question: with a real (non-fake) transport, does `take_call_receipts()` return only the new declaration receipt or the whole job's accumulated receipts? `new_model_calls` correctness (change 3) depends on this; the test only exercises a one-receipt fake (`:4618, 4655`).
- Third question: the owner's real-call evidence reports `state=reused` with `source_seed_proof` absent. That is consistent with the guard at `:2565-2580`, but it implies `_resumable_saved_source_review(...).state == "reused"` held under the **current** review validator. I could not re-verify that validator this pass; if it is stricter than the saved review, the route would have refused instead of reusing.
