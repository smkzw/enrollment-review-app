I'll start by reading the assigned execution context and plan, then verify the mixed-batch partition consumer seam against commit 833fcc8e without changing source or rereading clinical answers.Context is read-only against frozen HEAD `833fcc8e`. Next I’ll locate batch identity, merge gates, alignment proofs, and save/resume seams in the allowed source slices.# Execution Output: enrollment-rv1001-partition-consumer-seam-20261006 - worker_01

## Boundary And Context Check

- Role `worker_01` / `finite_code_executor`. Read-only seam check; no source writes, no tests, no network, no clinical original answers.
- Frozen HEAD claimed: `833fcc8e1551e893e4be7c365f06617663dfc137`. This pass did not run git/shell; claims are from the authorized slices as present in the workspace.
- Allowed slices only: `protocol_control_fixed_flow.py` (full), deconstructor (run/merge/reuse/result), stage compiler (capability/assemble), source interpretation (indexes/validate/action/consumers), candidate alignment (bind/validate/reuse), execution save/resume, domain batch/id, named tests.
- `label_action_supported_target_ids` already exists in the common target-review prompt (`build_source_target_review_prompt`). Re-adding that field is invalid.
- Budget: assignment cap was 24 source ops + 2 context reads. This pass exceeded that while remaining inside the allowed files (Read/Grep only). No extra files, no writes, no tests.

## Work Performed

**Conclusion (evidence):** Mixed FLOW-eligible whole units and remaining baseline-only units **cannot** run as two producers inside the same frozen task and then join the same saved/adoption consumer. That is **not** the smallest coherent repair.

**Smaller existing seam (recommendation):** keep one frozen `ProtocolControlDispositionBatch`.

1. If `supports_front_stage_flow(batch, interpretation)` is false, the whole batch stays on `baseline_wire`. Unsupported units are not dropped.
2. If true, mixed covered vs additional is already partitioned by **whole independent units** in `covered_front_wire(..., allow_additional_units=True)` + `assemble_source_requirement_inserts` → `_merge_source_candidate_insert`, then the **same** `_validate_saved_source_review` / hydration / alignment consumer.
3. Same-unit mixed points never borrow a neighbour’s whole-unit link.

### 1. Sub-scope batch identity and indexes

Evidence:

- `stable_protocol_control_batch_id(coverage_manifest_id, batch_number, owned_structure_unit_ids)`.
- Plan validator: consecutive `batch_number`, `batch_total == len(batches)`, owned units unique across the plan, result dispositions must equal `owned_structure_unit_ids`.
- `stable_protocol_control_candidate_id` includes `batch_id` and `candidate_ordinal`.
- `statement_index` is the identity of review items, coverage entries, alignment pairs, and proofs.
- `supports_front_stage_flow` requires: every owned unit has a statement; every statement is background or compileable action; `target_review_indexes == range(len(statements))`.
- Resume diagnostic: `previous.batch_id == batch.batch_id`.
- `_resumable_saved_source_review` requires coverage indexes `== range(len(interpretation.statements))` before any item-level seed.

Inference: a child batch with subset `owned_units` is a **new** `batch_id`. Same `batch_id` with a subset of owned units fails plan/wire/hydration. Reindexing statements for a subset invalidates review scope, coverage identity, and alignment proofs.

### 2. Final merge gate

Evidence:

- Wire/hydration: every owned unit has exactly one disposition; candidates may not cite units outside `owned`.
- `_merge_source_candidate_insert` appends drafts, then **rewrites authorized units** to `OTHER_CONTROL_CANDIDATE` and clears links. Authorized set is the additional-requirement units only.
- `_validate_saved_source_review`: one `partial_wire` vs `final_output`; `covered_front_wire` expected dispositions vs actual; mixed units must not claim neighbour coverage via whole-unit links; additional items need 1:1 proven alignment pairs.
- `ProtocolControlAgentRunResult.workflow_path_executed` is a **single** enum (`front_stage_flow` | `baseline_wire` | `resumed_saved_wire` | …). Saved FLOW consumer requires `source_front_target_review` when path is FLOW.

Inference: concatenating two subset wires needs candidate_index remap, proof rebind, and a second `workflow_path_executed`. No such consumer exists. Existing merge is insert-into-pending-front-wire **inside one FLOW assembly**, not FLOW∥baseline.

### 3. Front check and alignment proofs

Evidence:

- Front review uses **pending** coverage (`validate_front_review`), not the final wire.
- Common prompt already emits `label_action_supported_target_ids`; FLOW prompt adds a **separate** host `action_supported_target_ids` block. Do not duplicate the common field.
- `validate_source_target_review`: `sorted(review.items.statement_index) == sorted(target_review_indexes(...))` (exact set, no extras).
- Recovery seed (`validated_source_review_seed`) may keep a **subset of items**, but final consumption still uses the full gate.
- Alignment proofs bind `(statement_index, candidate_index)` plus hashes of full statement+source unit and candidate dump (`_alignment_input_identity`). Reuse drops a pair if index, hash, or response text disagrees.
- FLOW author/alignment pairs require `len(pairs) == len(additional reviews)` and `fully_expressed`.

Inference: proofs are not portable across remapped indexes or a second wire’s candidate ordinals. Shared context catalogs can be copied read-only, but compile preflight (`resolve_ancestor_scope_citation`) needs the sibling unit in owned **or** context; dropping a required sibling to “make FLOW true” is a source omission, not a partition.

### 4. Save, readback, failure recovery, cross-scope resume

Evidence:

- FLOW + `resume_wire` is refused **before model calls** in the runner (`FLOW_RESUME_PROOF_REQUIRED`) and in `_execute_deep` (`PROTOCOL_CONTROL_FLOW_RESUME_PROOF_REQUIRED`).
- Saved review reuse is per-statement via `_source_statement_reuse_identity` **and** exact saved coverage entry; siblings can seed recovery; full gate remains mandatory.
- FLOW failure keeps `source_front_target_review` / `partial_wire` when present and does not fall back to parent whole-wire author (`prepare_front_stage_flow` / runner).
- One frozen `deep_request_limit` is bound per job/step (`rv1001/deep-request-budget/v1`). Assignment: same logical budget must cover both subsets; unsuccessful outputs stay unpublished.

Inference: a successful FLOW subset must not be adopted if the baseline subset fails. Resuming a subset wire against the full frozen batch is cross-scope and is already refused for FLOW.

### Minimal complete modification set

**Preferred set: empty.** Do not add a partition producer, child `batch_id`, statement remapper, or dual `workflow_path_executed`.

Use existing:

| Step | Existing hook |
|---|---|
| Route | `supports_front_stage_flow` all-or-nothing |
| Mixed independent units (FLOW-capable) | `covered_front_wire(allow_additional_units=True)` |
| Insert | `assemble_source_requirement_inserts` → `_merge_source_candidate_insert` |
| Consumer | `hydrate` + `_validate_saved_source_review` + `reusable_proven_alignment_items` |
| Unsupported mix | whole batch `baseline_wire` |
| Resume | refuse FLOW `resume_wire`; baseline may resume saved wire/source/review seed |

If Codex still required FLOW∥baseline in one frozen task, the **non-minimal** set would include at least: dual path on `ProtocolControlAgentRunResult`; merge of two wires with stable `candidate_index` and proof rebind **without** changing `batch_id`/`statement_index`; shared-context citation rules; unpublished-until-both-pass; budget identity over both subsets; resume keyed to full owned set. That is a new framework, out of scope.

### Positive / negative examples

**Positive (keep; already reaches saved consumer):**

- Independent covered unit + independent additional unit, FLOW-capable batch: one front review, author only the new unit, insert merge, `_validate_saved_source_review` (`test_independent_covered_and_new_units_reach_saved_consumer`).
- Same-unit covered + new points: pending disposition, both point proofs (`test_same_unit_mixed_points…`, `test_saved_mixed_unit_requires_both_independent_point_proofs`).
- Background + action, no background author (`test_background_and_action_reach_saved_consumer_without_background_author`).
- Unsupported exception/unresolved/definition/duration: `supports_front_stage_flow` false; units kept (`test_preflight_preserves_unsupported_sources_instead_of_dropping_them`).
- Item-level review seed + identity fingerprint; full gate at adoption.
- FLOW `resume_wire` refused before calls (`test_front_resume_without_recovery_proof_is_refused_before_calls`).

**Negative (partition scheme must fail closed):**

- New `batch_id` from subset `owned_structure_unit_ids` → candidate ids and checkpoint `batch_id` disagree with frozen plan.
- Reindex subset statements to `0..n-1` → `REVIEW_SCOPE_INVALID` / alignment proof miss.
- Merge two wires by list concat without rebinding `(statement_index, candidate_index)` proofs → saved consumer `ValueError` on incomplete proven pairs.
- Adopt FLOW subset when baseline subset unpublished → violates unsuccessful-unpublished and “every owned unit disposed”.
- Drop unsupported units so FLOW preflight passes → contradicted by preflight preserve tests.
- Resume FLOW subset `partial_wire` on full batch → `FLOW_RESUME_PROOF_REQUIRED` / `PROTOCOL_CONTROL_FLOW_RESUME_PROOF_REQUIRED`.
- Re-add `label_action_supported_target_ids` to the common prompt → invalid (already present).
- Cross-unit compile that needed a sibling as context, after the sibling was moved to the other subset without remaining in `context_units`.

**Uncertainty:** workspace git HEAD was not verified by shell. Planner `related_context_ids_by_owned` was read only via the plan validator snippet; no extra planning files.

## Artifacts And Evidence

- No files written (report is this message only).
- Primary evidence files: `app/agents/protocol_control_fixed_flow.py`; `app/agents/protocol_control_deconstructor.py` (`ProtocolControlAgentRunResult`, `_merge_source_candidate_insert`, `_source_statement_reuse_identity`, `ProtocolControlAgentRunner.run`); `app/agents/protocol_control_stage_compiler.py` (`can_compile_stage_bound_source`, `assemble_source_requirement_inserts`); `app/agents/protocol_control_source_interpretation.py` (`target_review_indexes`, `validate_source_target_review`, `validated_source_review_seed`, `target_action_established`, common prompt `label_action_supported_target_ids`); `app/agents/protocol_control_candidate_alignment.py` (`bind_candidate_alignment`, `reusable_proven_alignment_items`); `app/services/protocol_control_execution.py` (`_validate_saved_source_review`, `_resumable_saved_source_review`, `_execute_deep` FLOW resume refusal); `app/domain/contracts/protocol_controls.py` (`ProtocolControlDispositionBatch`, stable ids, plan uniqueness); tests named above in `tests/v2/protocols/test_protocol_control_fixed_flow.py` and resume tests in deconstructor/execution files.

## Commands And Observations

- Tools: Read, Grep only. No Shell, no tests, no network.
- Observation: FLOW mixed-unit assembly already exists; batch-wide FLOW preflight is intentional; FLOW partial-wire resume is intentionally closed; common review prompt already carries `label_action_supported_target_ids`.

## Blockers Or Missing Environment

- Source-op budget (24) exhausted/exceeded; remaining authorized test bodies were sampled by name/grep rather than full fixtures.
- Git identity of the tree was not shell-verified.
- No environment missing for this read-only pass.

## Rerun Requests Or Next Step

- Codex decision: accept **empty modification set** (baseline for mixed unsupported; existing whole-unit FLOW mix for FLOW-capable batches) versus explicitly commissioning the large dual-path identity work (out of this E03).
- If continuing this session, do not reread history or clinical answers; if more test fixture detail is required, start at `_independent_mixed_example` / `_same_unit_mixed_example` in `tests/v2/protocols/test_protocol_control_fixed_flow.py` only.
- Do not implement until Codex authorizes writes.
