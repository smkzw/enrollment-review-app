我按只读边界审这三件事：候选来源是否被正确补进提示、证明复用是否绑住输入变化、action+exception 是否仍受既有精确校验约束。先看相对 HEAD `469288f4` 的两文件 diff 和相关定义。产品 diff 只落在候选对齐模块和它的测试上。接下来核对闭包如何进提示、如何进证明身份，以及保存/读取端是否会沿用旧的正向证明。# Conference Output: rv1006-candidate-source-closure-20261009 - evidence_single_object

## Output

The closure prompt does not by itself authorize sibling auto-completion, and multi-unit proof reuse is bound to the cited units. Two holes remain. A separate obligation group still blocks `fully_expressed` for the statement under review, and `action` plus `exception` still does not constrain `exception_expression`.

No clinical, regulatory, visual, or current-patient acceptance is claimed. Tests were not run in this pass. The reported 50-pass module result is prior evidence, not this review.

### Evidence

The product diff against `469288f4` is only `app/agents/protocol_control_candidate_alignment.py` and `tests/v2/agents/test_protocol_control_candidate_alignment.py`. Other paths in the worktree were not read.

`_candidate_source_closure` (`protocol_control_candidate_alignment.py` 265–271) keeps owned units whose ids are in `candidate.source_structure_unit_ids`, in `batch.owned_units` order, and raises `候选核对来源闭包越出本批授权原文` for any other id. The prompt always attaches that list (288) and says completeness proves only `statement_index`, siblings are not completed by co-citation, and unrelated neighbor limits must not be lent to this statement (332–337).

The caller accepts a fresh alignment only when its pairs equal the requested pairs (`protocol_control_deconstructor.py` 9386–9388). Coverage becomes `semantically_aligned` only for indexes whose own item is `fully_expressed` (9407–9425). A failed fresh read keeps only items that `reusable_proven_alignment_items` still accepts (9441–9465).

`fully_expressed` still requires every obligation group to contain a selected atom (614–616). Selected atoms must intersect the current statement unit’s spans and excerpts (591–599). Groups are stored as DNF and hydrated group by group (`protocol_control_deconstructor.py` 3848–3876).

The source hash adds `candidate-source-closure-context/v1` and the closure dump only when `len(source_structure_unit_ids) > 1` (388–390). One-unit inputs still hash the statement plus that unit’s full `model_dump`. `bind_candidate_alignment` (409–426) runs only on a new response at the deconstructor call sites (7144–7146, 9389–9392) and in fixed flow (456–458). Resume and save both call `reusable_proven_alignment_items` and do not bind stored `response_text` (`protocol_control_execution.py` 2152–2197, 3448–3508; deconstructor 9356–9370). Hash mismatch drops the item (460–462). `ValueError` from an out-of-batch closure is also dropped (470–472). A dropped proof fails the completed-batch gate with `候选对应证明未绑定当前完整来源与候选` (3507–3508).

The function gate (629–632) rejects `definition`, `calculation_input`, and `unclassified` even when `action` is present, and rejects `exception` only when `action` is absent. Exact excerpt, obligation grounding, time, number, and `_validate_evidence_policy_checks` (556) still run for every `fully_expressed` item. `evidence_policy_alignment_pairs` still selects any statement that contains `action` (70–74). The exception checks are unchanged: an `exception_expression` is rejected only when `exception_words` is empty (639–640); otherwise the words only need to occur in the rendered statements or propositions of selected atoms (650–651). The new success fixture leaves `exception_expression` as `None` and puts `尚未同意者除外` inside the obligation atom (`test_protocol_control_candidate_alignment.py` 79–116; fixture policy at `test_slice58c_control_deconstructor.py` 289–297 and 6951). That policy is not explicit, so the new test does not exercise evidence-policy checks.

### Inference

Question 1. The payload is limited to units the candidate already cites and this batch owns. Uncited owned units stay out. Extra alignment items cannot mark a sibling complete. That does not make a shared-parent composite comparable as one whole requirement. If a companion sits in another obligation group and is grounded only on its own unit, it is not selectable for this statement, and 614–616 rejects `fully_expressed`. The new instruction asks the model to stop calling that companion “added”; the gate then treats the same companion as an uncovered branch of this statement. If both atoms share one group, 614–616 passes as soon as one atom is selected, and a companion excerpt that already contains this sentence skips the split-conjunction check (621–628). Nothing then tests shared heading, parent, or scope. “Not added” is only prompt text.

Question 2. A previous positive proof is not retained or re-signed when a cited extra unit changes. Reuse compares the stored hashes with the current identity and drops the mismatch. The save and resume consumers do not call `bind` on the stored answer. A one-unit proof stays reusable because that unit is already fully hashed; the new closure field is the same unit. `validate_candidate_alignment` does not read sibling text, so a later fresh response that repeats the old JSON can be signed for the new closure. That is a new read, not retention of the old proof. No current consumer replays stored `response_text` into `bind`.

Question 3. `action` plus `exception` still passes through the exact-source, obligation, time, number, and evidence-policy gates. Pure `exception`, and any set containing `definition`, `calculation_input`, or `unclassified`, still cannot be `fully_expressed`. `exception` plus `threshold` without `action` remains rejected; that matches the stated rule and is not a new rejection. The exception layer itself is not bound. Once `exception_words` is non-empty, a different `exception_expression` is ignored unless its atom happens to be selected and the source words are already present on another selected atom.

### Recommendation

Mandatory:

1. At `protocol_control_candidate_alignment.py` 614–616, apply “另一义务分支” only to groups with at least one atom grounded on the current statement unit. A group grounded only on other closure units must not block this `statement_index` and must not satisfy it. Do not mark any other statement complete. Counterexample: group 0 is `材料分发及回收` on unit A; group 1 is `另外记录操作日期` on unit B; both ids are on the candidate; the item for statement A is `fully_expressed` and quotes only group 0. Today this raises `候选存在未覆盖本条要求的另一义务分支`. The same candidate in one group does not raise, with no parent check.
2. For `fully_expressed`, if `exception_expression` is not `None`, require `exception_words` and require every exception-atom statement to contain that normalized text. Keep the existing success case where the expression is `None` and the words are in the obligation atom. Counterexample: obligation statement `材料分发及回收，尚未同意者除外`, `exception_words` the same, functions `["action","exception"]`, and an unquoted exception atom `已签署同意者也除外`. `fully_expressed` now passes.

Optional:

- Assert that an owned unit absent from `source_structure_unit_ids` is omitted, and add the two counterexamples above. The current tests use one unit and `exception_expression is None`.
- Do not put one-unit closure into the hash. That would discard the intended one-unit reuse.
- Later instruction-only edits need a version bump. `CANDIDATE_SOURCE_CLOSURE_CONTEXT_VERSION` covers the multi-unit payload, not a future wording change.

### Uncertainty

The failed composite’s group shape was not in the generic diff. Finding 1 is a live blocker if companions are separate groups, and only a missing relationship check if they share one group. This pass did not re-run the module tests.

### Objections, decision, and question

The prompt-only closure change does not implement the shared-parent correspondence fix. It can move a structurally accepted negative decision into a structurally rejected positive one. The new `action` plus `exception` permission is wider than the exception check it relies on.

Provisional path until Codex answers: make the two mandatory edits above. Do not add a framework, do not hash one-unit proofs again, and do not treat the 50-pass run as acceptance.

Decision needed: in the failed shared-parent candidate, are the companion requirements separate `obligation_expression.groups` or atoms of one group? That chooses whether 614–616 must change before another model read. The safe code change is the same either way.
