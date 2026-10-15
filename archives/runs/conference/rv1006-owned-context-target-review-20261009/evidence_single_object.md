Trellis SessionStart context loaded. Starting the read-only review now — first scoping the delta at the base commit.

Read and Bash are denied in this non-interactive session; Glob/Grep are permitted, so I'll extract the named functions via targeted pattern reads. Locating the symbols first.

Symbol map acquired. Extracting the first sections (recheck selector + local prompt builder; deep-component identity pair; method-version/hash retention sites).

Line-range extraction via offset isn't working in this tool; switching to anchor + context extraction.

Anchor extraction works. Continuing with the selection gate, local prompt builder, the deconstructor block tail, and the deep-component identity pair.

Core selection/prompt logic and the identity gate are captured. Now the validator, resume-path revalidation, saved-review validation, plus locating the ~9800 consumer.

Now the synthetic-test family, the seed revalidation, the version constant's registry, and a pagination probe for the 9800 consumer.

Review complete. Route/off-peak note acknowledged — no session action needed. Before the findings, two method notes: `Read` and `Bash` are denied in this non-interactive session, so all inspection was done with `Glob`/`Grep` context extraction (no git commands, so I could not verify the `a4cd7dc`→current diff boundary; I reviewed the current state of the named symbols). Hard budget respected: **12 focused sections** read (the four named areas, the validator/seed/prompt in `source_interpretation.py`, the resume and saved-review validation in `execution.py`, and the `owned_context_target` test family), plus locator searches only. No writes, tests, model calls, raw clinical data, or browsing.

## Verdict on the core question

**Adequately bounded as an additive recipe; no distinct "repair identity" artifact is required — with one provenance-label defect that should be fixed (MF‑1).**

- The new method has an explicit version (`source-owned-context-target-recheck/v1`, `protocol_control_source_interpretation.py:43`) and is registered only in the `validator_version` slot of `_deep_component_identity` (`protocol_control_execution.py:2077`), a slot `_same_deep_components_with_current_gate` deliberately ignores while pinning all other identity fields (`execution.py:2102-2113`). Saved artifacts therefore remain reusable across this change; the recipe applies to fresh runs only. This is the same additive pattern as the dozens of prior versioned entries in that list.
- The schema is unchanged: recheck responses are the same `SourceTargetReview`/`SOURCE_TARGET_REVIEW_VERSION`; only the local prompt carries its own method version, recorded per attempt (`deconstructor.py:8936,8938-8940`).
- Reuse is not grandfathering: every kept item is re-proven by *current* validators (`validated_source_review_seed`, `source_interpretation.py:2253-2262`; called from `execution.py:2296`), with `refresh_required` on any rejection (`execution.py:2297-2300`), and the final saved review is fully re-validated at `execution.py:3452-3461`.
- Deliberate trade-off to be aware of: because `validator_version` is excluded from the compatibility gate, adding this recipe does **not** invalidate any saved review; refresh happens only organically via validator rejection. If the owner ever wants to force-refresh pre-recipe saved reviews, the lever is not this version string.

## Must-fix

**MF‑1 — review-basis provenance is misattributed when only the owned-context recheck modified the review** (`deconstructor.py:9068-9079`).
- The recheck success path replaces the item (`8971`) but never adds the index to `repaired_review_indexes` (defined `8213`; the two sibling recovery paths both do add: `8312`, `9029`).
- The recheck call overwrites the shared `review_response` variable (`8942-8944`). Consequently, `review_basis_text` (`9070`) can be the **single-item recheck response**, and `review_proof_origin` (`9072-9077`) is then recorded as **`model_response`** even though the saved review is an assembled, locally modified artifact.
- `review_proof_sha256` (`9079`) still hashes the true assembled review, which limits damage, but the origin/basis pair now misstates which method actually produced the item — exactly the "retaining actual historical prompt identities" property under review.
- Fix: add `repaired_review_indexes.add(item.statement_index)` on recheck success (making origin `assembled_source_target_review` truthful), or introduce an explicit origin value for recheck-modified reviews, and/or record the recheck attempt's `request_prompt_sha256` in the basis detail. Severity depends on downstream consumers of `review_proof_origin` — I did not trace them within budget (see residual uncertainty); worst case is a fail-closed reuse refusal rather than wrong acceptance, but it should not ship silently.

## Supported no-findings (by challenge)

- **Stale proof** — supported. Saved review reuse is gated by per-item current-validator re-proof, coverage-identity checks (`execution.py:2288-2302`), and per-statement reuse identity + coverage-input equality (`deconstructor.py:8260-8281`; `9081-9088`). Exact paragraph equality only selects a *fresh comparison* (`source_interpretation.py:1545`); nothing usable as a proof token is minted from it.
- **False coverage** — supported. Selection triggers only for `additional_requirement` with a known official target (`1546,1553-1554`), a multi-point owned unit (`1557-1558`), and the full owned paragraph verbatim among target excerpts (`1559-1561`). A resulting `covered` item cannot carry gaps (`2196-2197`), must ground exception wording when the interpretation recorded it (`2198-2202`), must survive `_require_resolved_source_target_review` (`deconstructor.py:9770`) and execution-side revalidation. Residual model-judgment exposure is bounded, not zero — see limitations.
- **Exception scope** — supported. Prompt requires checking whether the exception is scoped to this point before judging coverage and forbids borrowing sibling scope/period (`source_interpretation.py:1643-1649,1721-1723,1741-1742`); validator keeps the action inside its own quote (`1909-1910`, with only the narrow ≤32-char same-sentence subject extension `1903-1908`) and blocks coverage with gaps or ungrounded exceptions (`2196-2202`).
- **Foreign index** — supported. Local validation requires the returned index set to equal exactly the requested single index (`1867-1872`); the merge takes `corrected.items[0]` only for the matching index and discards anything else (`8949-8952`); the gate resolves the unit from the statement itself, not a positional index (`1551-1554`); the test's `foreign` family asserts status `需要核对` with the original item intact (`test_slice58c_control_deconstructor.py:13857-13886`).
- **Repeated unchanged failure** — within-run bound verified: one recheck per point per run via the `context_rechecked` set (`8915-8921,8924`) and at most two initiations per run (`8922,8928`); a failure raises immediately (`8970`) so no in-run retry of the same point. Cross-run: no automatic count guard, as you stated; `previous_item_sha256`/`request_prompt_sha256` in attempts (`8938-8939`) give the owner a preflight basis but nothing enforces it. Fine as scoped, provided the notes don't imply a cross-job bound.
- **Transport behavior** — supported. Transport failure yields `raw_output_text=None`, hashed error string, method/prompt/prior hashes retained, `outcome=transport_failed` (`8942-8944,8956-8969`); the boundary consumer records a second attempt and returns `需要核对` with the prior review (`9779-9900`, recovery at `9887-9899`). "Raw response … retained in actual attempts" holds whenever a response existed; there is nothing to retain otherwise.
- **Original review preservation** — supported. `target_review` is reassigned only after both single-item and full-coverage validation pass (`8946-8955,8971`); siblings untouched; the test family asserts frozen `wire`/`inventory`/`review` serializations and sibling equality across all four response kinds, changing the item only in the `covered` success case (`test_...:13853,13876-13886`). One-index-owned context (full unit excerpt + all same-unit `quoted_text`, never sibling decisions) is verified in the builder (`1640-1658`) and asserted by the tests (`13839-13845`), including absence of the block in default mode.

## Limitations

- No git access: "new vs pre-existing" attribution relies on your description, the in-code comments (`8913-8914`), and the new test families. I could not verify byte-identity of the default prompt path vs the base.
- I did not read the response-format builder (`source_interpretation.py:1803-1860`); "schema unchanged" is supported by call sites and tests, not directly inspected.
- `_require_resolved_source_target_review` (`deconstructor.py:6952`), `recovery_target_review` (`8214`), and `_preserved_source_review_proof`/`_unrepaired_source_seed_proof` (`execution.py:2325,2926`) were not read; consumer preservation semantics are inferred from tests.
- No tests executed (per instructions); all behavioral claims are code/test-source readings.

## Residual uncertainty

- **MF‑1 blast radius**: whether any downstream gate keys on `review_proof_origin`/`review_basis_text` (vs `review_proof_sha256` + attempt list). If it does, the mislabel can cause fail-closed reuse refusals or a weaker narrative for the saved proof; if nothing keys on it, it is still an integrity of record issue.
- Gate robustness nits, fail-closed only: `next(...)` without default in `source_target_context_recheck_needed` (`1551-1552`) and at `8929` would surface as an unrelated boundary `需要核对` on impossible input states; not a correctness breach.
- Normalized-equality semantics of `normalize_source_excerpt` for the exact-paragraph precondition were not audited for footnote/whitespace edge cases.

**Closing question (Trellis consent):** no Trellis task was created for this review-only turn. Do you want MF‑1 (recheck provenance origin asymmetry) tracked as a scoped follow-up task, or kept as review notes only?
