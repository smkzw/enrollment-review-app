I'll run a read-only independent audit of the v8 bounded-repair isolation. First I'll load the assigned conference context and plan, then check implementation, tests, and the offline recovery evidence.The conference packet is mostly TODOs, so I’ll locate the v8 bounded-repair code, tests, and recovery artifacts from the workspace itself.I'll skip other participants' writeups and go straight to the implementation, focused tests, and v8 attempt 4→5 recovery artifacts.The position-keyed restore path is in view. Next I’ll inspect v8 attempt 4→5 artifacts, how the runner sets indexes, and independently run the focused tests.v8 live attempt 5 failed on `REPAIR_SCOPE_ESCAPE` with p805 in the rejected units. I’ll reconstruct attempt 4→5 offline and run the focused tests independently.# Conference Participant Output: phase5-slice61ak-v8-bounded-repair-audit-20260828 - general_grok46

## Boundary Check

- Role: `general_grok46` / Grok Build `grok-4.6`. Read-only audit. No source edits, no model replay, no control-point publication, no report-path write.
- Initial packet files were placeholders (`Source Of Truth` / `Scope` / `Success Criteria` all `TODO`). Additional workspace reads were required to locate the v8 failure, the post-failure isolation, and the claimed 28 / 988 / A4→A5 evidence.
- Additional reads (justified): `app/agents/protocol_control_deconstructor.py` (`_restore_bounded_wire_repair`, runner index assignment), `app/protocols/protocol_control_repair_errors.py`, `app/protocols/protocol_control_gate.py` (`CONDITIONAL_EXEMPTION_SCOPE_SPLIT`), `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`, `artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/` (raw A4/A5, `runner-result.json`, `clinical-qc.json`, v8 config), v7/v8 replay configs for `max_schema_repairs`.
- Not read: other conference participant outputs as a source of findings. Accidental grep hits on `runs/conference/.../general_pi_antigravity.md` were ignored and not used.
- Tools used: filesystem read/search; `uv run pytest`; `uv run python` offline reconstruction of parsed wires. No live MTPLX, no browser, no production paths.
- Changed files: none.

## Independent Work Product

### Independent audit of the objective

The claimed post-v8 contract is:

1. One source key, several wire positions, only one position authorized → rewrite of a **different-source** candidate is **restored** to the previous round.
2. Unauthorized **same-source** sibling rewrite, candidate-count change, or source-partition change still **rejects**.
3. After that restore, the hydrated set must still be refused by `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`.
4. Do not publish.

That contract is internally consistent as an **engineering isolation** rule. It is **not** sufficient as a path to a clinically acceptable p804/p805 structure. The SCOPE_SPLIT offender on this family is the frozen p804 screening sibling; one-index repair of the waiver sibling cannot clear it. That is the highest-impact contradiction (below).

### Implementation (observation)

Position-keyed restore is the `elif mutable_candidate_indexes:` branch in `_restore_bounded_wire_repair`:

- Count must match previous.
- Frozen same-source siblings (source key is in the authorized set) must **exactly** equal the previous object; otherwise `REPAIR_SCOPE_ESCAPE`「定向修订改动了未获授权的同源候选，或候选对应关系不唯一」.
- Frozen different-source candidates match by source key only; the restored slot is always the previous object (content rewrite is discarded).
- Remaining current drafts must keep the authorized source keys; partition drift rejects.
- JSON/title sort is skipped when indexes are set, so same-source sibling order is previous wire order.

Runner sets `mutable_candidate_indexes` only when the selected source key already has `count > 1`. Unique source keys still use key-based replace.

Live v8 A5 failed in this same branch, with `rejected_structure_unit_ids = [su-3de4633dd1cb5721547f0bb2]` (p805). That is the different-source candidate the new matching rule is meant to restore instead of reject.

### 28 focused tests (observation)

Independent: `uv run pytest tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py -q --tb=no` → **28 passed in 0.05s**.

The file contains exactly 28 `test_*` functions. The isolation cases that match the objective are present:

| Test | Contract |
|---|---|
| `test_same_source_candidate_repair_restores_changed_different_source_candidate` | different-source content rewrite restored |
| `test_same_source_candidate_repair_rejects_modified_sibling` | same-source unauthorized sibling rejected |
| `test_same_source_candidate_repair_rejects_different_source_partition_change` | partition change rejected |
| `test_position_bounded_repair_rejects_candidate_count_change` | count change rejected |
| `test_same_source_position_repair_preserves_wire_order_when_titles_sort_differently` | skip-sort keeps previous order |
| `test_same_source_position_repair_rejects_duplicate_frozen_candidate` | duplicate frozen sibling rejected |
| `test_runner_targets_one_of_two_same_source_candidates_by_wire_position` | runner maps hydrated ID → wire index |

v8 `clinical-qc.json` still says the pre-replay bar was **26 / 986**. The extra two tests are the post-failure isolation; 28/988 is the current tree, not the live v8 start condition.

### 988 protocol-layer regressions (observation)

Independent: `uv run pytest tests/v2/protocols -q --tb=line` → **988 passed, 58 warnings in 130.23s**. Exit 0.

This is a deterministic suite result, not clinical or publication acceptance.

### v8 real A4 → A5 offline restore (observation)

Parsed `artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/execution/raw-responses.json` with product `parse_protocol_control_agent_wire`.

| Slot | Source | A4 | A5 |
|---|---|---|---|
| `[0]` | `su-86389…` (p804) | 补充三项 `complete_or_verify` 无时间窗 | **identical** to A4 |
| `[1]` | `su-86389…` (p804) | 28天 `verify_result_validity` + 「无需再次执行」 | authorized rewrite → 「核对…免除再次检查的适用状态」 |
| `[2]` | `su-3de46…` (p805) | 条件性检测有效窗 + 「无需再次执行条件性检测」 | **unauthorized** rewrite → 「核对免除再次执行…适用状态」 |

Dispositions A4==A5. Count=3. Source keys unchanged.

`_restore_bounded_wire_repair(..., mutable_candidate_indexes={1}, mutable_candidate_source_keys={(su-86389,)}, allow_candidate_repartition=False)`:

- `applied=True`
- `[0]` kept A4 (and A5, already equal)
- `[1]` kept A5 authorized repair
- `[2]` restored to A4 p805 (A5 p805 discarded)

Live A5 `rejected_candidate_ids` match current `_candidate_ids_from_wire(A5)`: `pcc-624367…`, `pcc-68bda6…`, `pcc-77a685…`. The live failure was this restore path on p805, not a later gate.

Reject probes on the same real wires: sibling title tamper, count +1, p805 source-key change → all `REPAIR_SCOPE_ESCAPE`. Matches the stated must-reject set.

### SCOPE_SPLIT after restore (observation + clinical inference)

`_check_conditional_exemption_scope_split` on the restored hydrated candidates raises:

`CONDITIONAL_EXEMPTION_SCOPE_SPLIT [pcc-624367a4829552da203e1c79]: 同源条件豁免不得拆成兄弟候选中的无条件执行义务…`

Same raise on unrestored A4, unrestored A5, and restored A5. Entity is the **p804 screening sibling**, not the authorized waiver slot and not p805.

p804 excerpt matches `_CONDITIONAL_EXEMPTION_SOURCE_RE` (「可接受…无需再次检查」). The screening sibling atom is unconditional `complete_or_verify` / 「完成乙肝表面抗体、乙肝e抗原、乙肝e抗体检查」, which matches `_ROUTINE_ACTION_RE`. The waiver sibling still has timed validity + exemption-modality language. That is the gate’s intended split.

**Inference, not final clinical authority:** p804 is one source sentence: panel (including those extra antigens) + 28-day acceptability + no repeat at screening/baseline. Keeping an unconditional “must complete extra antigens at screening” sibling next to a validity/waiver sibling is a protocol-scope split, not a harmless supplementary split. Restoring p805 does not change that. I do not claim parent clinical QC.

Authorized A5 evidence on the waiver slot is date-window verification only; restored p805 evidence is also date-window verification. SCOPE_SPLIT is not an EXEMPTION_EVIDENCE_OVERSTATED leftover.

### Highest-impact defect / contradiction

**One-index isolation cannot ever clear this family’s SCOPE_SPLIT.**

SCOPE_SPLIT’s offender is `pcc-624367…`, the unauthorized same-source sibling. The new rule **forbids** rewriting that sibling in the same pass. The authorized index only rewrites the waiver/validity candidate. Therefore a later expression-only replay that still targets a single p804 position will restore/keep the screening sibling and fail SCOPE_SPLIT again.

This is not a reason to revert the restore-of-different-source rule. It is a reason not to treat “A4→A5 restore + SCOPE_SPLIT reject” as a complete repair strategy.

**Proposed remediation (engineering, for Codex to choose):**

1. Keep different-source restore and same-source sibling reject as implemented.
2. Do **not** publish; do **not** replay a v9 that only names the waiver candidate.
3. If the clinical goal is one p804 candidate: authorize a **merge/repartition** that is explicitly limited to `su-86389…`, with p805 still frozen/restored — or authorize **both** p804 indexes in one expression-repair pass so the screening sibling can inherit the 28-day/waiver scope.
4. Do not use `CONDITIONAL_EXEMPTION_SCOPE_SPLIT ∈ CANDIDATE_REPARTITION_GATE_CODES` as a silent escape hatch on leftover repair budget. On this v8 config the inherited `max_schema_repairs` is 4 and A5 is the last attempt, so this v8 run would stop after SCOPE_SPLIT. A higher budget would turn SCOPE_SPLIT into a **repartition license**, which contradicts v8’s “固定候选数量与来源键”.

### Second defect (defense in depth)

`_validate_bounded_output_repair` (post-hydration) never receives `mutable_candidate_indexes`. A source key in `mutable_candidate_source_keys` marks **all** siblings mutable. Same-source sibling isolation exists only on the wire restore path. If restore is skipped or indexes are empty, both p804 drafts can change and hydration validation still passes.

**Proposed fix:** pass indexes into `_validate_bounded_output_repair` and freeze non-authorized same-source siblings by payload hash. Add a runner-level test: third different-source candidate rewritten + authorized sibling rewritten, asserting restore note and frozen sibling identity after `ProtocolControlAgentRunner`.

### Test gap (not hit by v8 shape)

Frozen different-source matching requires unique source-key correspondence (`len(matches)==1`). Two frozen candidates that share a **non-mutable** source key would reject even when current==previous. v8 p805 is unique, so A4→A5 is safe. No synthetic test covers that shape.

### Nested live identity (uncertainty)

Live A4 publication rejected `pcc-3909a60154ef77e3bec1cfd7`, which is **A2 raw** waiver identity, not A4 raw `pcc-64a198…`. Nested restore in the live runner means raw A4 is not identical to live hydrated A4. Offline raw A4→A5 still demonstrates the new isolation on the actual A5 drift (p805 content rewrite). Codex should not treat raw-A4 candidate IDs as live attempt-4 IDs.

## Evidence And Assumptions

**Evidence**

- Live A5: `REPAIR_SCOPE_ESCAPE` on p805; `runner-result.json` attempt 5; `gate-results.json` skipped because no hydrated final output; `claims_complete=false`.
- Current restore on raw A4→A5: applied, p805 rolled back, authorized p804 waiver kept, screening sibling kept.
- SCOPE_SPLIT entity `pcc-624367a4829552da203e1c79` on restored hydration via the same helper publication uses.
- Focused tests 28/28; `tests/v2/protocols` 988 passed, 58 warnings.
- v8 notes/config: fixed candidate count/source keys; no overwrite of v5/v6/v7; no control-point publish.
- Inherited repair budget: `representative_group_virology_p803_p805_contract_v3.v1.json` `max_schema_repairs: 4`; live 5 attempts match 1 initial + 4 repairs.

**Assumptions**

- Authorized index for raw A4→A5 is wire `[1]` (the only p804 draft that changed). Live may have mapped `pcc-3909a601` through nested restore; clinically it is still “one of two p804 positions”.
- Calling `_check_conditional_exemption_scope_split` on hydrated candidates is the publication candidate-scope check. Full `check_protocol_control_publication` (catalog/plan/manifest/phase view) was **not** re-run; other publication codes on the restored set are unverified.
- 988 is the current protocol-layer suite, not a frozen SHA of the pre-isolation tree.

**Inference**

- New isolation does what the objective asks on the v8 A4→A5 shape.
- SCOPE_SPLIT after restore is the correct fail-closed clinical/protocol boundary for the p804 split, not a restore bug.
- Isolation plus single-index waiver repair cannot produce a publishable p804/p805 set.

**Recommendation**

- Do not publish. Do not start another MTPLX replay until Codex chooses how both p804 siblings may be rewritten or merged without opening p805.
- Keep different-source restore; add hydration-level index freeze before relying on this in another live loop.
- Treat 28/988 as regression evidence for the isolation patch, not as Phase 5.8d clinical closure.

**Uncertainty**

- Full publication report on restored hydration (MIXED_DECISION, BINDING, catalog ordinals) not executed.
- Nested live A2→A4 baseline wire was not fully replayed through `ProtocolControlAgentRunner` + replay `validate_for_publication`.
- Whether extra p804 antigens (HBsAb/HBeAg/HBeAb) should remain a separate candidate under the 28-day condition is a parent clinical decision, not this participant’s.

## Risks, Gaps, And Verification Needs

1. **Product deadlock:** SCOPE_SPLIT offender is frozen by the new isolation. Risk of another v9 that “only repairs the named waiver candidate” and dies the same way.
2. **Repartition license:** `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` is in `CANDIDATE_REPARTITION_GATE_CODES`. Harmless on this budget; harmful if `max_schema_repairs` increases.
3. **Hydration validator gap:** no index awareness; sibling isolation is single-layer.
4. **ID drift:** live vs raw candidate IDs; any audit that keys off `pcc-3909a601` vs `pcc-64a198` will mis-state attempt 4.
5. **Verification still needed (Codex):** full `check_protocol_control_publication` on restored A5; optional nested-baseline reconstruction; decision on p804 merge vs dual-index authorization. Not visual/browser work.

## Recommended Next Step

Codex should **refuse publication and refuse a same-contract model replay**. Accept the isolation patch as a fail-closed wire behavior that is covered by 28 + 988 and by offline A4→A5 restore, and treat post-restore `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` on `pcc-624367a4829552da203e1c79` as a standing clinical/protocol boundary, not as a restore defect.

**Decision points for Codex**

1. Next p804 repair: (A) authorize both `su-86389` indexes, or (B) authorize a source-closed merge of the two p804 candidates, with p805 still frozen. One-index waiver-only is not a viable path.
2. Should `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` stay in `CANDIDATE_REPARTITION_GATE_CODES`, or become a stop-the-loop / human-check code under a fixed-candidate contract?
3. Is defense-in-depth on `_validate_bounded_output_repair` required before any further live runner use?

**Bounded questions**

1. For this audit, is raw A4→A5 the required previous wire, or must nested live baseline (`pcc-3909a601`) be reconstructed before you treat restore evidence as complete?
2. Confirm: no control catalog write, no v9 MTPLX, no claims_complete flip in this conference.
3. If you want a checked-in guarantee of A4→A5, should a deterministic fixture test load the two raw texts (not a live model) rather than only synthetics?

**Safe provisional path until those answers:** keep the current restore/reject implementation; do not publish; do not replay; do not widen repair budget; record `structured_control_deconstruction_accepted=false`.
