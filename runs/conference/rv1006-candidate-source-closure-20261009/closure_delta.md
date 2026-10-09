上一轮关于“忽略所有伴随义务组”的建议不采用。我只复核收窄后的合取覆盖和 exception 层：OR 组仍须各有本条义务，独立例外层仍应拒绝。# Conference Output: rv1006-candidate-source-closure-20261009 - evidence_single_object

## Output

The narrowed repair still lets one obligation group’s selected atoms stand in for every OR alternative. The exception-layer refusal matches the narrower rule. No clinical or composite acceptance is claimed. Tests were not re-run here.

### Evidence

The conjunction witness is at `app/agents/protocol_control_candidate_alignment.py` 621–628. After the unchanged “every group has a selected atom” check (614–616), coverage is:

```python
if not any(_split_obligations_cover_source(source, scope,
           [atom for atom in group.atoms if atom in obligation_selected])
           for group in candidate.obligation_expression.groups):
    raise ValueError("候选义务摘录未按原文保留完整合取内容")
```

`_split_obligations_cover_source` (131–164) returns true only when the atoms it is given tile the quote, with only `且` / `并且` / `同时` or punctuation left over. An empty atom list returns false.

`test_split_conjunction_checks_this_statement_without_erasing_or_alternative` (150–185) passes one AND group whose selected atoms are `领取材料` and `回收材料` while `记录电话` is unselected. The OR case moves `记录电话` into a second group and does not quote it, then expects `另一义务分支`. That second atom is not a fragment of `领取材料，回收材料`, so it never becomes selected.

The exception gate is 633–634: `action` plus `exception` with `exception_expression is not None` raises `独立例外层不能仅凭动作文字对应宣布完整`. Words are still required only when `exception_words` is non-empty (652–653). The success fixture uses `exception_expression is None` and words inside the obligation atom (79–116). `different_exception_layer` expects any `ValueError`.

The reported 64-pass window and the statement-1 / statement-0 replay were not re-executed in this pass. Statement 0’s inputs are not in these two files.

### Findings

Mandatory conjunction regression. `any(...)` accepts the item when one group’s selected subset tiles the quote, even if another OR group does not. Line 614–616 only requires some selected atom in that other group, and a fragment of this quote is enough to be selected. Previously a witness group had to be fully selected. A companion atom in the covering group now qualifies that group as a witness, which is what the three-obligation AND case needs, and it also licenses a weaker second alternative.

Counterexample, one candidate, quote `领取材料，回收材料`:

- Group 0: `领取材料`, `回收材料`, plus unselected `记录电话`. The selected pair tiles the quote.
- Group 1: only `领取材料`, and that atom is quoted.

`另一义务分支` passes. Group 0 makes `any(...)` true. `fully_expressed` passes. Group 1 alone satisfies the candidate without `回收材料`. The new OR test does not catch this, because its second group is unquoted and not groundable on this quote.

This is not a request to ignore OR groups. Keep 614–616. Change the split witness from `any` to `all`: every group’s selected atoms must tile this quote. One AND group with an unselected companion still passes. The existing OR test still fails at 614–616. A weaker quoted alternative then fails `完整合取内容`.

Exception change. No second mandatory edit. A non-empty `exception_expression` is refused for every `action` plus `exception` item, including a layer that literally matches this sentence. That is the conservative rule you locked, and the different-layer fixture reaches that refusal. Pure `exception`, `definition`, `calculation_input`, and `unclassified` still fail at 630–632.

### Remaining limits

A selected excerpt that already contains the whole quote skips the split block entirely (621–624). Another OR group is then not tiled. That short-circuit predates this delta. It does not affect the split path used by the three-atom AND case.

`action` plus `exception` with `exception_words is None` and `exception_expression is None` never reaches 652–653, so the label adds no exception text. The new success fixture always sets words. Worth a one-line refusal if that shape can be produced; it is not the reported composite failure.

A shared candidate-level exception layer blocks every `action` plus `exception` statement on that candidate, even when this sentence’s words already sit in the obligation atom. That is the accepted cost of not matching exception phrases across atoms.

Statement 0 staying rejected for incomplete literal coverage is consistent with this gate. Nothing here says that rejection should be removed. The whole composite is not accepted. Proof reuse and per-statement sibling disposition were not reopened.
