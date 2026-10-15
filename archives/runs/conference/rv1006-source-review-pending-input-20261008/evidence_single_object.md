Trellis SessionStart ✓

I'll start by reading the initial read set (the context file and the plan), then audit the code paths they reference.

Read set received. Reading the frozen source windows now.

Now the tests and the named invariant definition.

One targeted read remains essential for the identity question (the reuse gate named by my mandate). Reading the precise gate function.

# Conference Output: rv1006-source-review-pending-input-20261008 - evidence_single_object

## Output

### A. Pass identity, budget, and evidence trail

- Role: `evidence_single_object` (advisory peer), read-only, serial pass. No source edits, no writes, no tests, no model calls, no browser. I did not touch `runs/conference/.../evidence_single_object.md`.
- Named windows covered in full: `app/agents/protocol_control_source_interpretation.py:1225-1525`; `app/services/protocol_control_restricted_source.py:319-358`, `720-774`; `app/services/protocol_control_execution.py:3890-4015`; `tests/v2/protocols/test_slice58c_control_deconstructor.py:3900-3965`; `tests/v2/services/test_protocol_control_execution.py:370-437` plus the complete `test_invalid_target_review_keeps_technical_failure_and_persists_actual_answer` (`:4900-4945`) and the adjacent reuse-identity tests (`:4986-5105`).
- **Budget disclosure (overshoot, reported per "do not hide tool or evidence failures"):** 11 bounded reads, not 10. The 11th was a single targeted read of `_resumable_saved_source_review` (`app/services/protocol_control_execution.py:2154-2274`) because the assignment explicitly requires me to challenge the identity decision, and that function *is* the identity gate; the alternative was an unsupported objection. Everything else stayed inside the declared set. Also used two targeted symbol greps (one for the named test definition, one to locate the reuse-gate/review-validator symbols in `app/`); no repository-wide scan.
- **Precisely identified but not read** (budget stop, named rather than scanned): `validated_source_review_seed` (the item-level selector called at `:2253`); `SourceTargetReviewItem` / `SourceTargetReview` Pydantic schema and any conditional field validators (the model-visible strict schema); `validate_source_target_review` body after `:1526`; `_restricted_statement_batch_from_review`; `_temporal_restriction_indexes`; `_deep_component_identity` / `protocol_control_agent_prompt_template_sha256`; the consumer of the `partially_reused` state.
- Consequence: findings below that depend on those unread definitions are labeled `[Uncertainty]` and paired with a bounded question. I do not claim clinical acceptance, final acceptance, or authority over any production decision.

---

### B. Direct answers to the four in-scope questions

1. **Does exposing frozen unresolved data prevent a hidden-input contradiction without changing clinical meaning?**
   `[Evidence]` Yes, for the coverage branch. `build_source_target_review_prompt` now ships `"unresolved": interpretation.statements[index].unresolved` (`:1264`) and a hard instruction pair (`:1316-1319`) matching the pre-existing validator refusal at `:1521-1523` (`SOURCE_UNRESOLVED_STILL_COVERED`), and `tests/v2/protocols/test_slice58c_control_deconstructor.py:3938-3950` pins both the payload and the sentence. The change is input-visibility only: no rule text, threshold, unit, or stage semantics move; the prompt explicitly denies the step any authority over the frozen doubts (`:1318` "本步骤无权改写或清空来源解释").
   `[Inference]` Residual: exposure is not retention. The frozen doubt becomes visible and simultaneously becomes *unremovable by this step*, but no read-window check requires the accepted answer to carry that doubt forward (see D2′).
2. **Does early refusal of invalid-review restriction preserve valid R1 results and technical-failure classification?**
   `[Evidence]` Yes, and it is well-guarded in the frozen windows: `restricted_batch_from_review` refuses the faithful-restriction entry set when `SOURCE_TARGET_REVIEW_INVALID` is present (`app/services/protocol_control_restricted_source.py:726-736`, with the explicit comment at `:734-736`), `_whole_unit_restriction` requires *exact set equality* to a single allowed class (`:330-336`), `tests/v2/services/test_protocol_control_execution.py:415-426` proves `None` plus **no mutation** of the frozen result for three error orderings, and `:373-388` proves four distinct invalid/author/transport disguises do not become a restriction. `:4900-4945` proves the technical classification: `failed_final`, `PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_INVALID`, verbatim `raw_output_text` persisted, `partial_wire is None`, and no `restricted_batch` key.
3. **Can any result now be incorrectly adopted?**
   `[Inference]` Yes, conditionally: through *reuse*, not through the validator. See D1. The invalid→restriction paths are closed; the reuse path is not closed with respect to the changed visible input.
4. **Identity treatment for repaired input packets under unchanged validator/policy semantics.**
   `[Recommendation]` The version decision is defensible but the stated justification is incomplete. "The invariant already rejects covered items with `source.unresolved`" proves safety only for `covered_*` decisions. Since the response *shape* is unchanged, keeping `SOURCE_TARGET_REVIEW_VERSION` is acceptable; what must not be claimed is that the version string carries input identity. Recommend recording a separate, non-versioned **input-exposure proof** and gating reuse on it (D1 corrections, H).

---

### C. D1 — Highest-impact defect: the reuse gate proves *coverage* and *current-validator acceptance*, but not *which visible input produced the answer*

**Statement.** The candidate changes the model-visible input while the identity/version of the response contract stays fixed. The reuse gate re-validates a saved review against the *current* validator, so for any decision the current validator does not constrain by `statement.unresolved`, a saved answer produced under the pre-exposure prompt is reused with no identity signal — a silent cross-regime semantic carry-forward.

**Evidence.**
- `_resumable_saved_source_review` (`app/services/protocol_control_execution.py:2154-2274`) proves reuse with exactly: presence of `source_target_review` plus non-empty `source_statement_coverage` (`:2231-2235`), coverage index completeness (`:2245-2250`), `target_review_indexes` + `validated_source_review_seed(batch, interpretation, coverage, review)` acceptance under current validators (`:2251-2257`), then `reused` / `partially_reused` by retained index set (`:2263-2274`).
- The **only** hash comparison on that whole path is `raw_output_sha256` on the *front-stage* branch (`:2193-2196`), and it hashes the saved **answer**, not the **input**. The deep branch (`:2231-2274`) contains no hash comparison at all.
- The docstring defers the remaining proof to "the frozen batch/route/prompt identity checked by the caller" (`:2164-2165`). The only prompt-identity artifacts visible in the frozen diagnostics are `prompt_template_sha256` and `_deep_component_identity` (`app/services/protocol_control_execution.py:3990-3994`) — i.e. a **template** hash computed from the `prompt_template` argument.
- `[Inference]` A builder-code change inside `build_source_target_review_prompt` is not necessarily captured by a template-file hash. If it is captured, my finding collapses for reuse; if not, the identity claim in the packet ("actual message hashes record the changed input") is **recording, not gating** — receipts are stored (`take_call_receipts` `:3893-3894`, saved `:3977`) but no read-window code compares them to the currently rendered message.
- The one `statement.unresolved` consumer visible inside the validator is decision-scoped: `:1521-1523` rejects only `covered_*`. `SOURCE_FUNCTION_UNRESOLVED` (`:1517-1519`) is a different axis (`decision_functions == ["unclassified"]`). Exclusion-class decisions — `not_current_control`, `background_context`, `cited_external_rationale`, `definition_dependency` — have no visible `unresolved` guard.

**Concrete dangerous counterexample.**
Statement S in unit U carries `unresolved = ["给药前时间窗与访视窗口的关系未核清"]`. Under the pre-exposure prompt a run answered `not_current_control` for S with a verbatim prior-sequencing basis, and the batch was persisted in a deep checkpoint that later failed on a *different* item. The candidate ships (exposure added, version unchanged). The user continues that job with `deep_source_job_id=...` — precisely the recovery path the runtime observation exercised. The gate calls `validated_source_review_seed`; the `not_current_control` item passes, because nothing visible constrains `unresolved` for that decision; the item is counted in `kept_indexes`. The batch proceeds with S excluded from current-node control, although the freshly exposed prompt states that a treatment-period heading or adjacent frequency is insufficient to exclude current control (`:1290`) and that "若只因未找到条款或不确定用途，选 unresolved，不得当作背景" (`:1303`) — a fresh answer would have been `unresolved`. Nothing in the reused payload records that it predates the exposure, so the carry-forward is invisible in the audit trail. That is an affected item passing without re-examination, which R1 forbids ("受影响项不假判通过"), reached without any new code path.

**Blast radius / reachability.** `[Inference]` Only reachable across the exposure boundary (continued or adopted deep jobs). This is not theoretical: the observed runtime failure at batch 12 produced exactly the state (`partially_reused`, four-of-five retained) that this gate produces, and continuation is a first-class product flow (`tests/v2/services/test_protocol_control_execution.py:5014-5028`).

**Minimal corrections (cheapest first, no new framework).**
- **(i) Decision-agnostic, preferred.** Persist an input-exposure digest with the review (e.g. `source_review_input_sha256` over the rendered 待核陈述 + 只读来源线索 sections, or over the prompt text). In `_resumable_saved_source_review`, treat a missing or mismatched digest as `refresh_required` with a distinct reason (e.g. `source_review_input_exposure_unproven`). No response-schema change, no clinical semantics, keeps "unchanged contract version" literally true.
- **(ii) If (i) is outside this window's boundary.** For statements with non-empty `unresolved`, refuse reuse of a saved item whose decision is in the *exclusion* class (`not_current_control`, `background_context`, `cited_external_rationale`, `definition_dependency`); force a re-read of only those statements. `partially_reused` already supports this shape (`:2270`), so it is a predicate change, not a new mechanism.
- Both keep normal valid results usable (fresh runs unchanged; only unprovable saved items refresh) and keep genuine faithful R1 restrictions usable (the `unresolved`/temporal whole-unit paths are untouched).

---

### D. D2′ — Second defect class, same family: exposed doubt is not provably retained

**Statement.** The candidate removes the *prompt-side* asymmetry for `covered_*`, but the frozen dimension has no visible retention obligation on the answer for every other decision.

**Evidence.**
- `[Evidence]` No read-window branch requires the accepted item to carry `statement.unresolved` forward. The whole-unit restriction path keys on the model's *own* `unresolved` decisions and on `unresolved_aspects` non-emptiness (`protocol_control_restricted_source.py:346-355`), never on `statement.unresolved`.
- `[Evidence]` The prompt explicitly forbids `unresolved_aspects` content for two decisions ("填 []", `:1313` for `definition_dependency`, `:1374-1375` for `potential_same_requirement`), so a blanket "aspects must be non-empty" rule would be wrong; retention must be decision-aware.
- `[Evidence]` The restriction path silently requires `unresolved_aspects` non-empty for every `unresolved` item (`:354`), while the prompt window I read never states that `decision == "unresolved"` mandates a non-empty list — the closest text is "须保留相关疑问及有源对照线索" (`:1319`). This is the *same defect class the candidate is fixing*: a code-enforced requirement the model cannot read.
- `[Uncertainty]` Both of the above may already be enforced by the `SourceTargetReview`/`SourceTargetReviewItem` Pydantic contract, which is exported to the model as a strict JSON schema (`source_target_review_response_format`, `:1414-1422`). If the schema enforces conditional non-empty `unresolved_aspects`, D2′ collapses. I could not read it within budget.

**Consequence.** Either direction damages R1: (a) the model answers `additional_requirement` for an unresolved statement and drops the doubt from the artifact while the item stays validator-clean; or (b) a legitimate `unresolved` answer with an empty aspect list is refused by the restriction path and surfaces as a *technical failure* — converting a genuine reserved doubt into the wrong category, which the product rules forbid.

**Minimal correction.** One prompt sentence per gap, using Codex's own rationale for not bumping the version ("it clarifies an already-enforced requirement"): for `decision == "unresolved"`, require at least one concrete unverified dimension in `unresolved_aspects`; and require that a statement whose frozen `unresolved` is non-empty either answers `unresolved` or records the preserved doubt in the applicable field. If the Pydantic schema already encodes these, record that as the answer and close the item instead.

---

### E. D3 — Failure-code precedence is positional, not severity-ordered

`[Evidence]` `app/services/protocol_control_execution.py:3939-3941` selects the **first** known failure code in `attempts[-1].error_classes`, and `:3942-3951` derives `retryable` from that single selection. `[Inference]` A mixed set such as `["SOURCE_TARGET_REVIEW_TRANSPORT_FAILED", "SOURCE_TARGET_REVIEW_INVALID"]` yields `retryable=True` and a transport-class error code, even though a deterministic invalid outcome is present. `restricted_batch_from_review` handles the same situation with set semantics (`:728-732`), so the two gates disagree in style.
Severity: low-to-moderate — it cannot adopt anything, but it can mislabel an invalid review as a retryable transport failure and burn repair budget re-asking a deterministic rejection. `[Recommendation]` Rank by severity (INVALID/UNRESOLVED over TRANSPORT) instead of list order. Not a blocker for this window; flag for the same repair if it is one line.

---

### F. D4 — Plan-level naming can be misread as an adoption claim

`[Evidence]` `tests/v2/services/test_protocol_control_execution.py:5024-5028` asserts `decision == "resume_partial"` together with `source_review == "refresh_required"` and reason `verified_unpublished_draft_source_review_refresh_required`. `[Inference]` "resume_partial" describes the *draft*, not the review; the authoritative field is `source_review`. In a product whose rules explicitly forbid collapsing categories, a reviewer or downstream consumer reading only `decision` could treat a refreshed review as partially reused. `[Recommendation]` Keep behavior; ensure the reader of `deep_reuse_plan` consults `source_review` (or rename/document). Only worth doing if it lands in the same repair — not a defect claim.

---

### G. Confirmations — do not "fix" these

- Invalid review → **technical failure, not uncertainty, not researcher judgment**: `:726-736`, `:330-336`, tests `:373-388`, `:415-426`, `:4900-4945`. The refusal is early, before hydration/adoption, and it preserves the actual answer verbatim.
- `[Evidence]` Genuine R1 restrictions remain reachable: whole-unit restriction engages only for exact `{SOURCE_TARGET_REVIEW_UNRESOLVED}` or `{TEMPORAL_SCOPE_UNRESOLVED}` with re-derived coverage and zero candidate errors (`:340-343`), and cannot fire without at least one `unresolved` item (or proven temporal set) carrying aspects (`:353-355`).
- `[Evidence]` The scope gate is intact: `validate_source_target_review` requires exact index-set equality (`:1478-1483`), so a four-of-five review can never be validated as a complete review; partial retention must flow through the seed selector and the `partially_reused` state.
- `[Evidence]` The exposure does not alter clinical meaning: the payload quotes the frozen interpretation field verbatim, adds no rule text, and the response contract is byte-identical (schema name and version at `:1418`).

---

### H. Compatibility of previously valid proofs

| Saved state (produced pre-exposure) | Reuse behavior under this candidate | Verdict |
|---|---|---|
| Valid item, `covered_*`, statement without `unresolved` | Passes current validators; reused | Safe — no regime-dependent semantics |
| Valid item, `covered_*`, statement *with* `unresolved` | Cannot exist (validator already refused it at `:1521`), so nothing to reuse | Safe by construction |
| Valid item, non-covered decision, statement *with* `unresolved` | Passes current validators; reused with no exposure proof | **Unproven — D1** |
| Invalid item inside an otherwise valid review | Dropped by the seed selector → `partially_reused` | Safe in the read windows; see Q2 for whether "dropped-invalid" is distinguishable from "dropped-absent" |
| Any saved state whose input regime is unknown | Input-exposure proof absent on the deep path | **Unproven — D1** |

`[Inference]` The correct identity treatment is therefore: **keep the response-contract version; add an input-exposure proof to reuse.** Version identity answers "can I parse this answer?", exposure identity answers "may I still believe this answer?". The candidate currently answers only the first, and the packet's justification ("actual message hashes record the changed input") describes a *record*, not a *gate* — if the caller's frozen prompt identity does compare rendered-message hashes, Codex should say so explicitly and name the comparison point, because I could not find it in the frozen windows.

---

### I. Decision points for Codex

1. **Reuse gating (blocking).** Accept correction C(i) (input-exposure digest + `refresh_required` on mismatch), or C(ii) (decision-scoped refresh for exclusion-class decisions on `unresolved` statements), or prove that reuse is already gated by a rendered-input hash. *Recommendation: C(i); it is cheap, decision-agnostic, and preserves "unchanged version" literally.*
2. **Retention obligation (D2′).** Decide whether the accepted item must carry the frozen doubt forward beyond the `covered_*` branch, or whether the Pydantic schema already forces it. *Recommendation: answer from the schema first; only add prompt text if the schema is silent — and mirror Codex's existing "clarify an already-enforced rule" argument so no version bump is implied.*
3. **Blast radius of exposure.** A statement whose frozen `unresolved` is non-empty can never be marked covered by this step (`:1317`). Confirm there is a supported, non-new-framework way to correct a *stale* frozen dimension upstream and re-run the affected scope. If not, decide whether the candidate can convert a transient doubt into a permanent blocker inside this window. *Recommendation: accept only if the upstream correction path exists; otherwise record as a bounded, user-visible limit rather than adding recovery.*
4. **D3/D4 scope.** Fix in this repair only if one line each; otherwise record as known, low-severity observations. *Recommendation: fix D3 only if it is literally a precedence list; skip D4 behavior change.*

---

### J. Bounded questions for Codex (each with why it matters and the safe provisional path)

1. **Does any branch of `validate_source_target_review` after `:1526` consult `statement.unresolved` other than the `covered_*` branch at `:1521-1523` — specifically for `definition_dependency`, `potential_same_requirement`, `background_context`, `not_current_control`, `cited_external_rationale`?**
   Why: D1's counterexample and D2′ both stand or fall on this single fact.
   Provisional path: assume **no** (nothing visible enforces them) → treat the version-unchanged statement as safe only for `covered_*`, and apply correction C(i).
2. **Does `validated_source_review_seed` distinguish "item actively rejected by the validator" from "item simply not retained", and can a rejected item ever be silently dropped while the rest are adopted as sufficient?**
   Why: it is the only consumer boundary between `partially_reused` and adoption; the runtime observation ("retains four other review items, not a complete five-item review") lives exactly here.
   Provisional path: assume a dropped item always forces the full gate (per the docstring at `:2163`); require an explicit test only if the answer is ambiguous.
3. **Does `SourceTargetReviewItem` enforce non-empty `unresolved_aspects` when `decision == "unresolved"`, in the strict JSON schema exported to the model at `:1414-1422`?**
   Why: it decides whether D2′'s second half is a real hidden-input asymmetry or already closed.
   Provisional path: assume the schema is silent → add the one clarifying prompt sentence.
4. **Where, if anywhere, is a hash of the *rendered* source-target-review message computed and compared for the deep reuse path (does `_deep_component_identity` or `protocol_control_agent_prompt_template_sha256` capture the builder code, or only a template artifact)?**
   Why: it decides whether the packet's identity claim is a gate or only a record.
   Provisional path: assume record-only → require C(i).

---

### K. Limits, uncertainty, and what would change my conclusions

- `[Uncertainty]` All of D1/D2′ rest on the unread validator tail and the unread schema/seed selector. If the tail enforces `unresolved` across exclusion-class decisions and the schema enforces conditional aspects, D1's counterexample and D2′ collapse to documentation issues and the candidate's identity decision is sound as stated.
- `[Uncertainty]` I could not verify whether `prompt_template_sha256`/`_deep_component_identity` capture builder-code changes; if they do, reuse is already input-gated and D1 reduces to "say it explicitly".
- `[Uncertainty]` D3 severity depends on whether mixed error-class sets occur in production (the test suite constructs them by appending, `:380`, so they are at least representable).
- Nothing here evaluates the actual clinical statement, the correctness of any semantic resolution, or the 11-completed/12th-failed runtime classification beyond what the frozen windows show.

### L. Non-claims and resume point

- No edits, no writes anywhere, no production reads beyond the frozen read set, no tests or model calls. No clinical adoption, no final acceptance, no authority claims — Codex retains final synthesis and acceptance.
- Resume point if Codex wants a same-session follow-up: answer questions J1–J4 (four facts) and, if any answer contradicts my assumption, request a re-pass scoped to the corrected predicate; I can then re-issue C/D conclusions against the real tail, schema, and seed selector without new exploration. The single most important next action is C(i) or an explicit demonstration that reuse is already gated by a rendered-input hash.
