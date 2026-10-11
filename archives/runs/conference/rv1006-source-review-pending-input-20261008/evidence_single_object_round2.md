Reading the five declared windows (combining the two small ones in the first file, per the stated allowance).

# Conference Output: rv1006-source-review-pending-input-20261008 - evidence_single_object

## Output

### 1. Pass scope, windows, budget

Read-only follow-up pass. Exactly **5 bounded reads** used (within the declared cap); no writes, no tests, no model calls, no scans. All five named windows were covered, with the two small ones in the first file combined into one read as permitted:

- `app/agents/protocol_control_source_interpretation.py:650-860` (covers `650-710` and `825-850`), `1230-1345`, `1470-1630`, `1828-1890`
- `app/services/protocol_control_execution.py:2154-2290`

Verified directly in this pass: `SourceTargetReviewItem` has no conditional aspects constraint (`:660-682`, `unresolved_aspects` is a plain default list); `is_non_action_definition` rejects `statement.unresolved` (`:826-842`, specifically `:833`); `background_context` rejects `statement.unresolved` (`:1557-1575`, specifically `:1562`); the new sibling rejection exists (`:1527-1531`); `validated_source_review_seed` validates each saved item singly through the live validator and requires the full gate at consumption (`:1832-1866`); the deep reuse gate revalidates every saved item through current validators (`protocol_control_execution.py:2253-2282`, especially `:2255` and the invariant at `:2233-2252`). The existing error classification and restricted wrapper were not re-opened, per instruction.

### 2. Decisive remaining defect (one)

**RD1 — `background_context` is the one closure decision whose frozen-unresolved disqualification is not readable to the model, and the host's own permission flag asserts the opposite.**

Evidence:
- The validator rejects `background_context` when `statement.unresolved` is non-empty (`app/agents/protocol_control_source_interpretation.py:1557-1575`; `statement.unresolved` participates in the `:1562` conjunction).
- The prompt's frozen-unresolved prohibitions name only two groups: `covered_by_official`/`covered_by_procedure` (`:1318`) and the three newly blocked decisions (`:1321`). `background_context` is named nowhere in that prohibition context; the nearest text is conditional on the reviewer's own uncertainty ("若只因未找到条款或不确定用途…", `:1304`), not on the frozen `statement.unresolved` list.
- Worse, the host-supplied permission flag is affirmative: `"background_context_allowed": decision_functions == ["background"]` (`:1259-1261`) — it does **not** include `not statement.unresolved`, so a statement classified `["background"]` with a frozen doubt ships `background_context_allowed: true`, while `:1562` will reject the answer.
- Contrast the sibling flag that gets this right: `definition_dependency_allowed` (`:1262`) delegates to `is_non_action_definition`, which encodes `not statement.unresolved` (`:833`). So one closure path is honestly flagged and the other is not, one line apart in the same payload.

Impact: a plausible, host-permitted answer is rejected for an unstated rule — the exact defect class the candidate is otherwise closing. Consequence is bounded: no incorrect adoption; cost is an extra correction round (or an INVALID classification, see CR1) for precisely the statements this candidate targets, and it invites the model to distrust host flags. This is pre-existing, not introduced by the candidate — but the candidate closed three of four siblings and left this one, so consistency argues for closing it in the same repair.

Minimal correction (either is one line, no schema or clinical change):
- **(preferred)** Narrow the flag: `"background_context_allowed": decision_functions == ["background"] and not statement.unresolved`, mirroring `definition_dependency_allowed`. The prompt's existing false-branch text (`:1301-1303`) then routes the model to retain the specific use/dependency doubt, which is exactly the intended outcome.
- **(alternative)** Add one clause to `:1321` naming `background_context` in the prohibition list.

### 3. Disposition of D1 and D2

**D1 — CLOSED for the review-driven paths; my pass-1 digest recommendation is withdrawn.**

- The safety mechanism is unconditional revalidation, not identity: every reuse calls the live validator on each saved item (`protocol_control_execution.py:2253-2257` → `source_interpretation.py:1856-1864`), a semantically invalid item drops its siblings nothing (docstring `:1842`), and final consumption still requires every expected item (`validate_source_target_review:1481-1486`). A rendered-input digest would now add provenance only, not safety. Withdrawn.
- With `:1527-1531` added, the only decisions that survive a statement with non-empty `statement.unresolved` are `unresolved` and `additional_requirement`, and both are already required to carry non-empty `unresolved_aspects` (`:1532-1535`). That is a complete closure at the validator level: no path can both carry a frozen doubt and close it.
- **Self-correction of my pass-1 counterexample.** I claimed a reused `not_current_control` on an unresolved statement would silently exclude the statement from current-node control. That was overstated: `is_post_eligibility_calculation` already requires `not statement.unresolved and not review.unresolved_aspects` (`:685-697`), so the consumer would never have honored that exclusion. The real pass-1 impact was narrower and still R1-relevant — the doubt was closed *at the review layer* (recorded as "无需审核"/"外部资料说明") while the source doubt remained, an audit and policy violation even when the consumer guard holds. The new check makes the review layer agree with the consumer; that consistency is the substantive gain.
- No incorrect-adoption path remains in the windows I could read.

**D2′ — CLOSED, with the RD1 caveat.** The prompt now names the three blocked decisions and the retention path ("只能在现有未完整覆盖路径中保留具体 unresolved_aspects", `:1321-1322`), matching the enforced non-emptiness (`:1532-1535`). The "mandatory field the model cannot read" asymmetry is gone. Per instruction I do **not** require literal text equality between `unresolved_aspects` and the frozen strings; non-emptiness plus the visible instruction is the enforced contract, and semantic anchoring remains the model's responsibility. Residual accepted as a design limit, not a defect.

### 4. Conditional risks (separate from the decisive defect; each needs one fact I could not read)

- **CR1 — classification parity for the new code.** `SOURCE_UNRESOLVED_STILL_EXCLUDED` must map to the same attempt-level family as `SOURCE_UNRESOLVED_STILL_COVERED` (the unresolved family that the restricted wrapper accepts at `protocol_control_restricted_source.py:330-336` and that execution lists at `:3928`), and must be present in the focused/front correction allow-lists (the front path consults `FRONT_REVIEW_CORRECTION_CODES`, used at `protocol_control_execution.py:2211`). Neither mapping is inside my windows. If the new code defaults to INVALID, a review that answers an exclusion on a doubtful statement is classified as a *technical failure* instead of a *reserved doubt* — a category conflation the product rules forbid, and it would bypass the faithful-restriction path for the same input class as its sibling.
- **CR2 — completed-batch adoption.** `_resumable_saved_source_review` revalidates, but the completed-job adoption path (`test_same_identity_deep_source_reuses_validated_batches_without_model_calls`, `tests/v2/services/test_protocol_control_execution.py:5078-5105`) consumes a previously validated batch with zero model calls. If that path does not re-run the current validators, a batch completed under the old validator — which could legitimately contain an exclusion decision on a doubtful statement — can be re-adopted after the change with the doubt still closed. This is the only remaining route by which the pre-change semantics can survive into a post-change result.
- **CR3 — front-stage validator.** `validate_front_review` is a separate imported function (`protocol_control_execution.py:2179-2184`). Confirm it shares `validate_source_target_review`'s new check (or that front-stage reviews cannot carry frozen unresolved), otherwise the two review validators disagree.
- **CR4 — stale doubt has no in-job exit.** The new rejections (plus the pre-existing covered/background/definition ones) mean a statement with non-empty frozen `unresolved` can only be answered `unresolved` or `additional_requirement`; closing it requires an upstream source-interpretation correction. The correction transport code exists (`:3935`), so the exit is contemplated, but its affected-scope semantics are outside my windows. Product decision, not a code defect: confirm a stale frozen doubt can be corrected and re-scoped without a full re-read, or record the limitation.

### 5. Does any consumer still lose pending uncertainty?

Not on the paths I could read: partially-reused seeds cannot be consumed as final (`:1842` plus the scope gate `:1481-1486`); the dropped item's statement keeps its frozen `unresolved` in the interpretation, which is persisted in the diagnostic checkpoint (`protocol_control_execution.py:3996-3999`); surviving decisions are forced to carry aspects (`:1532-1535`); and the exclusion consumer already refuses doubtful statements (`:685-697`). The three places that could still lose it are exactly CR2 (adoption without revalidation), CR1 (misclassified as technical failure, so the doubt is never re-asked as a doubt), and no others found.

### 6. Test decisiveness requirements (not certified — tests unrun and unread)

The synthetic extension is decisive only if it asserts, for each of the three decisions: (a) a full review containing that decision on a statement with non-empty `statement.unresolved` raises `SOURCE_UNRESOLVED_STILL_EXCLUDED` with the correct `statement_index`; (b) `validated_source_review_seed` **refuses** that item (returns the sibling-only review or `None`) and the reuse state is `partially_reused`/`refresh_required`, never `reused`; (c) `is_post_eligibility_calculation` stays False for the `not_current_control` case; (d) genuine preservation — `unresolved` and `additional_requirement` items with non-empty aspects on the same statement are retained. Without (b) the test proves rejection but not seed refusal, which is the D1-closing property.

### 7. Limits

- `SOURCE_TARGET_REVIEW_VALIDATION_VERSION` is not defined or consumed in any window I was allowed to read; I cannot verify its wiring. Safety does not depend on it — the reuse path calls the live validator unconditionally — so it is a provenance improvement, not the gate. Its inclusion in the identity the continuation planner compares remains unverified.
- CR1–CR3 are outside the declared windows by construction; I named the precise definitions rather than scanning.
- I did not re-review the restricted wrapper or error classification (per instruction) except where the new code must integrate.
- No clinical judgment, no adoption, no acceptance. Owner retains final synthesis and acceptance.
