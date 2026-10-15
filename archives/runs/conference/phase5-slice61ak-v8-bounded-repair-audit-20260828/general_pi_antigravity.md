# Conference Participant Output: phase5-slice61ak-v8-bounded-repair-audit-20260828 - general_pi_antigravity

## Boundary Check

- **Working Directory & Path Confinement**: Audit performed strictly within the authorized repository worktree (`.worktrees/phase5-clinical-facts-profile`). No production or out-of-scope paths were accessed or modified.
- **Read-Only Invariant**: Audit conducted in pure read-only mode. No source files were edited, no live model replays were initiated, and no clinical control points were published.
- **Role Identity & Mode**: `general_pi_antigravity` (Pi / `google-antigravity` / `gemini-3.7-flash`, high thinking effort), operating as participant 1 in serial conference review under Codex chair.
- **Independent Verification Scope**: 
  1. Implementation of bounded wire restoration and isolation in `app/agents/protocol_control_deconstructor.py` (`_restore_bounded_wire_repair`, `_validate_bounded_output_repair`, `ProtocolControlAgentRunner`).
  2. The 28 focused contract and repair isolation tests in `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`.
  3. The 988 full protocol-layer regression tests in `tests/v2/protocols/`.
  4. Offline wire restoration and gate evaluation on real Phase 5.8d v8 Attempt 4 $\to$ Attempt 5 raw outputs (`artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/execution/raw-responses.json`).
  5. The clinical rationale and gate boundary of `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` on the post-repair candidate set.

---

## Independent Work Product

### 1. Implementation Audit: Bounded Repair Isolation (`_restore_bounded_wire_repair`)

In `app/agents/protocol_control_deconstructor.py` (lines 1969–2331), when a repair targets a specific candidate index (`mutable_candidate_indexes`) within a source unit containing multiple sibling candidates (`mutable_candidate_source_keys` with multiple siblings), the isolation mechanism enforces five strict deterministic invariants:

1. **Total Candidate Count Invariant (`lines 2158–2162`)**:
   ```python
   if len(previous.candidate_drafts) != len(current.candidate_drafts):
       raise ProtocolControlAgentWireValidationError(
           "REPAIR_SCOPE_ESCAPE",
           "定向修订不得增删候选；候选拆分或合并必须由对应问题明确授权",
       )
   ```
   Prevents the model from silently dropping or adding candidates under an expression-repair authorization.

2. **Same-Source Unauthorized Sibling Invariant (`lines 2182–2199`)**:
   For any sibling candidate sharing the same source key (`previous_source_key in mutable_source_keys`) whose index is **not** in `mutable_candidate_indexes`, the validator enforces exact deep equality:
   ```python
   matches = [
       candidate
       for candidate in remaining_current
       if (
           candidate == previous_candidate
           if previous_source_key in mutable_source_keys
           else tuple(candidate.source_structure_unit_ids) == previous_source_key
       )
   ]
   if len(matches) != 1:
       raise ProtocolControlAgentWireValidationError(
           "REPAIR_SCOPE_ESCAPE",
           "定向修订改动了未获授权的同源候选，或候选对应关系不唯一",
           structure_unit_ids=list(previous_candidate.source_structure_unit_ids),
       )
   ```
   If the LLM alters an unauthorized same-source sibling, `candidate == previous_candidate` fails, triggering an immediate `REPAIR_SCOPE_ESCAPE` rejection.

3. **Different-Source Candidate Isolation & System-Side Rollback (`lines 2188–2190`, `lines 2235–2243`)**:
   For candidates belonging to unrelated source units (`previous_source_key not in mutable_source_keys`):
   - The match is performed on source key partition identity (`tuple(candidate.source_structure_unit_ids) == previous_source_key`).
   - When building the restored candidate list:
     ```python
     candidates = []
     for index, previous_candidate in enumerate(previous.candidate_drafts):
         if index not in mutable_candidate_indexes:
             candidates.append(previous_candidate)
             continue
         candidates.append(
             replacements_by_source[
                 tuple(previous_candidate.source_structure_unit_ids)
             ].pop(0)
         )
     ```
   - **Key Finding**: If the model made out-of-scope edits to a candidate from a *different* source unit, the system explicitly discards the model's changed draft and substitutes the baseline `previous_candidate` from the previous attempt.

4. **Different-Source Partition Invariant (`lines 2205–2224`)**:
   The set of source unit IDs for all mutable candidates is strictly verified against the previous round (`previous_source_keys != current_source_keys`), blocking attempts to merge or split source units across different sources.

5. **Wire Ordering Stability (`lines 2316–2324`)**:
   ```python
   # skip sort when repair scope is wire-position keyed; title/json
   # sort would swap same-source siblings and break candidate_indexes identity.
   if not mutable_candidate_indexes:
       candidates = sorted(...)
   ```
   Avoids lexical title sorting when position indexing is active, preserving exact index parity between runner validation and model wire responses.

---

### 2. Verification of the 28 Focused Tests

The 28 focused contract tests in `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py` were executed directly against `.venv/bin/pytest`:
- **Result**: `28 passed in 0.06s`
- **Coverage Breakdown**:
  - `test_mixed_decision_stage_control_authorizes_candidate_repartition`
  - `test_mixed_trigger_decision_stages_authorizes_candidate_repartition`
  - `test_unrelated_gate_codes_do_not_authorize_candidate_repartition`
  - `test_candidate_repartition_gate_codes_are_gate_level_not_project_specific`
  - `test_conditional_exemption_binding_allows_bounded_obligation_regrouping`
  - `test_conditional_exemption_binding_uses_fixed_candidate_expression_scope`
  - `test_planning_freezes_exemption_as_required_semantic_action`
  - `test_conditional_exemption_cannot_lose_its_same_source_condition`
  - `test_conditional_exemption_accepts_condition_in_same_obligation_group`
  - `test_conditional_exemption_is_not_mislabeled_as_current_stage_action`
  - `test_exemption_evidence_cannot_require_the_waived_action_not_to_occur`
  - `test_exemption_evidence_may_verify_the_qualifying_condition`
  - `test_exemption_evidence_guard_is_scoped_to_source_waiver`
  - `test_conditional_exemption_scope_split_rejects_unconditional_sibling`
  - `test_conditional_exemption_scope_accepts_one_bound_validity_candidate`
  - `test_combined_routine_action_and_waiver_still_requires_stage_split`
  - `test_synthetic_runner_mixed_decision_repartition_preserves_both_candidates`
  - `test_synthetic_runner_without_repartition_authorization_rejects_split_candidate`
  - `test_repartition_rejects_out_of_scope_candidate_partition`
  - `test_same_source_candidate_repair_uses_bounded_wire_position`
  - `test_same_source_candidate_repair_rejects_modified_sibling`
  - `test_same_source_candidate_repair_restores_changed_different_source_candidate`
  - `test_same_source_candidate_repair_rejects_different_source_partition_change`
  - `test_position_bounded_repair_rejects_candidate_count_change`
  - `test_same_source_position_repair_preserves_wire_order_when_titles_sort_differently`
  - `test_same_source_position_repair_rejects_duplicate_frozen_candidate`
  - `test_same_source_position_repair_rejects_out_of_order_count_change`
  - `test_runner_targets_one_of_two_same_source_candidates_by_wire_position`

---

### 3. Verification of 988 Full Protocol-Layer Regressions

Full protocol regression suite executed across all 51 test modules under `tests/v2/protocols/`:
- **Command**: `MTPLX_API_KEY="" ./.venv/bin/pytest tests/v2/protocols`
- **Result**: `988 passed, 58 warnings in 131.65s (0:02:11)`
- All protocol coverage, catalog, draft revision, schema, gate, and transportation tests passed completely without regressions.

---

### 4. Real v8 Offline Reconstruction (Attempt 4 $\to$ Attempt 5)

Using `artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/execution/raw-responses.json`:
- **Attempt 4 State**:
  - `Candidate 0` (wire index 0): `su-86389bb90acd044a0835089c` (`p804`), title `病毒学检查补充项目：乙肝表面抗体、乙肝e抗原、乙肝e抗体` (screening completion).
  - `Candidate 1` (wire index 1): `su-86389bb90acd044a0835089c` (`p804`), title `病毒学检查结果有效窗及筛选/基线期免予再次检查` (validity window + waiver).
  - `Candidate 2` (wire index 2): `su-3de4633dd1cb5721547f0bb2` (`p805`), title `条件性病毒学检测结果有效窗（首次给药前28天）` (different source unit).
- **Validation Failure in Attempt 4**:
  `OUTPUT_VALIDATION_REJECTED: PUBLICATION_GATE_REJECTED: EXEMPTION_EVIDENCE_OVERSTATED [pcc-3909a60154ef77e3bec1cfd7]`: Evidence overstated non-occurrence for Candidate 1.
- **Repair Authorization**:
  - Targeted unit: `su-86389bb90acd044a0835089c`
  - Targeted candidate ID: `pcc-3909a60154ef77e3bec1cfd7`
  - Targeted wire index: `1`
  - `allow_candidate_repartition`: `False`
- **Attempt 5 LLM Behavior**:
  - `Candidate 0` (`p804` sibling): Left identical to Attempt 4.
  - `Candidate 1` (`p804` target): Corrected evidence modality (fixed overstated evidence).
  - `Candidate 2` (`p805` different source): **LLM touched/rewrote obligation statements** despite no authorization for `su-3de4633dd1cb5721547f0bb2`.
- **System Restoration Outcome**:
  - `_restore_bounded_wire_repair` executed: returned `restored_wire` with `applied=True`.
  - `Candidate 0` preserved identical to previous round.
  - `Candidate 1` adopted repaired content from Attempt 5.
  - `Candidate 2` model drift discarded; restored strictly to Attempt 4 baseline.
  - Candidate count remained 3; wire order remained stable.

---

### 5. Clinical Boundary Audit: Gate Rejection by `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`

Following successful wire restoration and hydration of Attempt 5, candidate-level gates (`_validate_candidate`) passed for all 3 candidates individually. However, batch-level gate validation failed deterministically with:

$$\text{CONDITIONAL\_EXEMPTION\_SCOPE\_SPLIT } [\texttt{pcc-624367a4829552da203e1c79}]$$
$$\text{“同源条件豁免不得拆成兄弟候选中的无条件执行义务；被豁免操作必须与有效期及豁免条件保持同一语义范围”}$$

#### Clinical Root Cause & Boundary Analysis
1. **Source Protocol Text (`body.p804`)**:
   > “将根据标准实验室程序进行包括乙肝表面抗原、乙肝表面抗体、乙肝e抗原、乙肝e抗体、乙肝核心抗体、丙型肝炎病毒抗体、人类免疫缺陷病毒抗体、梅毒特异性抗体检查。可接受在首次给药前28天内的结果，筛选期/基线期无需再次检查。”

2. **Model Deconstruction Defect**:
   The model split paragraph `p804` into two separate candidates sharing source `su-86389bb90acd044a0835089c`:
   - `pcc-624367a4829552da203e1c79`: `COMPLETE_OR_VERIFY` - “完成乙肝表面抗体、乙肝e抗原、乙肝e抗体检查” (pure unconditional screening routine execution obligation).
   - `pcc-68bda6c972207e40b7f213e4`: `VERIFY_RESULT_VALIDITY` (28 days before first dose) + `COMPLETE_OR_VERIFY` (waiver if valid).

3. **Clinical Safety & Regulatory Risk**:
   - If `pcc-624367a4829552da203e1c79` were published as an independent control candidate, clinical study coordinators/investigators at trial sites would receive an unconditional instruction that these viral tests *must* be repeated at screening.
   - For a patient who already has valid historical test results within 28 days prior to first dose, this unconditional sibling would falsely flag a protocol deviation if the test was not repeated at screening, directly violating the protocol's conditional waiver clause.
   - Therefore, the protocol gate's rejection of `pcc-624367a4829552da203e1c79` via `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` is **clinically necessary, protocol-faithful, and logically sound**.

---

## Evidence And Assumptions

### Evidence
1. **Bounded Wire Repair Implementation**: `app/agents/protocol_control_deconstructor.py:1969-2331`, specifically lines 2157–2243 for position-keyed same-source isolation and different-source rollback.
2. **Focused Test Execution**: `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py` (28 tests passed in 0.06s).
3. **Full Protocol Regression Execution**: `tests/v2/protocols/` (988 tests passed in 131.65s).
4. **v8 Replay Logs & Artifacts**:
   - `artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/replay-summary.json`
   - `artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/execution/raw-responses.json`
   - `artifacts/phase5-slice61aj-fixed-candidate-expression-replay-20260828/execution/runner-result.json`
5. **Gate Implementation**: `app/protocols/protocol_control_gate.py:1875-1968` (`_check_conditional_exemption_scope_split`).

### Assumptions Challenged & Verified
- **Assumption 1**: *"When a candidate at index 1 is authorized for repair, changes to unrelated source candidates by the LLM should fail the batch."*
  - **Refutation/Finding**: LLMs frequently introduce subtle formatting or phrasing drift to un-targeted candidates in JSON array responses. The implemented system restoration strictly isolates and rolls back different-source candidates to the baseline without rejecting the turn, while strictly rejecting any drift on same-source unauthorized siblings. This maximizes repair convergence without sacrificing source fidelity.
- **Assumption 2**: *"If all individual candidates pass `_validate_candidate`, the batch is clinically valid."*
  - **Refutation/Finding**: Intra-candidate validation checks only local AST consistency (e.g. valid anchors, valid evidence types). Cross-candidate semantic contradictions (such as splitting a conditional waiver paragraph into an unconditional execution candidate and a conditional waiver candidate) can only be caught at the batch-level scope gate (`_check_conditional_exemption_scope_split`).

---

## Risks, Gaps, And Verification Needs

### Highest-Impact Risks & Gaps

1. **Test Fixture Environment Isolation (`MTPLX_API_KEY`)**:
   - **Observation**: In `tests/v2/protocols/test_protocol_control_agent_transport.py:355`, the test calls `monkeypatch.setattr(transport_module, "MTPLX_API_KEY", "")`, but `_configured_value("MTPLX_API_KEY", ...)` checks `os.getenv("MTPLX_API_KEY")` before falling back to module attributes.
   - **Risk**: When running in an environment where `MTPLX_API_KEY` is exported in the shell (e.g. `MTPLX_API_KEY=mtplx-local`), `test_mtplx_client_disables_proxy_inheritance_and_uses_control_schema` fails with an assertion mismatch (`mtplx-local` vs `local-mtplx`).
   - **Remediation**: In `test_protocol_control_agent_transport.py`, explicitly add `monkeypatch.delenv("MTPLX_API_KEY", raising=False)` (or monkeypatch `os.environ["MTPLX_API_KEY"] = ""`).

2. **Model Deconstruction Prompting for Virology Waiver Paragraphs**:
   - **Observation**: In v8 replay, the model repeatedly split `p804` into two candidates: one for supplementary items and one for validity window/waiver.
   - **Risk**: Since `p804` contains both an enumeration of laboratory procedures and a trailing 28-day waiver sentence, models tend to extract an unanchored routine completion candidate unless explicitly instructed that all tests enumerated in a waiver paragraph inherit the paragraph-level validity/waiver scope.
   - **Remediation**: Ensure prompt guidance in `protocol_control_deconstructor.py` clearly states that when a single paragraph defines both routine procedures and an overriding validity window / waiver condition, the entire set of procedures must remain bound to the validity/waiver scope in a single candidate, rather than split into unconditional routine screening siblings.

---

## Recommended Next Step

1. **Accept the Bounded Revision Isolation Implementation**:
   - The implementation of `_restore_bounded_wire_repair` in `app/agents/protocol_control_deconstructor.py` is fully verified, robust, and correctly covers same-source sibling locking, different-source rollback, count invariance, and partition invariance.
   - All 28 focused tests and 988 full protocol-layer regressions pass.

2. **Acknowledge `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` Clinical Gate Validity**:
   - The rejection of the restored v8 attempt 5 output by `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` is valid and correct.
   - Do not weaken or bypass this gate; the clinical requirement must remain that conditional exemptions cannot be split into unconditional screening siblings.

3. **Handover to Codex Main Venue**:
   - Await Codex chair review and final synthesis. No further edits or model replays required in this pass.
