我只复核当前豁免窗口辅助函数和新测试，看上次的反例是否已被拦住，以及有没有新的放行缺口。# Conference Output: rv1006-waiver-window-review-20261011 - evidence_single_object

## Output

Checked source: base `83d8ee59` plus the current two-file patch. This pass read only `_exemption_validity_is_bound_in_group` (`app/protocols/protocol_control_gate.py` lines 2881–2932) and `test_result_validity_exemption_keeps_independent_action_or_window` (lines 292–306). Tests were not run. `window48pass` is software evidence only. No medical approval.

**Decision:** the counterexamples from the last pass are closed. One new release blocker remains, so the repair is not closed.

### Evidence

The skip now requires `single_window_exemption` on both the joined excerpts and the statement (line 2920). That helper requires exactly one `_TEMPORAL_CUE_RE` hit, every cued clause to be an exemption, no `并|且|或|另|还|以及` in any clause, and every `_ROUTINE_ACTION_RE` hit to start inside an `_EXEMPTION_MODALITY_RE` match (lines 2901–2918). The peer match is unchanged.

By inspection, these now fail closed with `TIME_ANCHOR_MISSING`, and the new test encodes them for both the shared quote and a statement-only addition:

- `，并须在随机前完成另一项检查。`
- `，并必须完成另一项检查。`
- `或随机前的另一项检查。`
- `并记录另一项检查。`

The three original one-window sentences still have one cue and none of those coordinator characters. `无需重复检查` is forgiven because the routine match starts at `需` inside `无需`. Two `N天内` cues make the count not equal to 1, so that shape still cannot skip.

### Inference

The 48-character bridge reopens a mandatory action. `_ROUTINE_ACTION_RE` can start at `需` inside `无需` or `不需要` and its `.{0,48}` consumes a later verb. `finditer` then sees one match, and the start-position excuse forgives all of it.

Concrete sentence: `重新筛选时无需12天内复查但必须完成妊娠检查。`

One cue, `但` is not in the coordinator set, and the only routine match runs from `需` through `检查`, covering `必须完成`. The skip returns true. A same-group validity atom with `upper_bound_days=12` still has one suffix bound. No second window is created, and the pregnancy-test action is dropped. `可豁免` does not do this: it creates no `_EXEMPTION_MODALITY_RE` span, so a detected `必须` still fails.

### Recommendation

Keep the new veto. Narrow the excuse so a match that starts inside `无需` or `不需要` does not cover a later `必须` in that clause. The suffix after the exemption token in `14天内的检查结果无需重复检查` does not itself match `_ROUTINE_ACTION_RE`, so the three existing sentences can stay on the skip. Do not infer a window for the blocked sentence.

### Uncertainty

These remain limits, not a second blocker: `合并` or `并发症` contains `并` and will fail closed; `筛选后12天内` is two cues and will fail closed; `和` or `但` plus a bare `记录` or `完成` still misses both the coordinator list and `_ROUTINE_ACTION_RE`. The projection can still mark the waiver atom `fulfilled` when validity is false or unknown. Consumers, the shared exemption regex, schemas, and the author path were not re-read and are unchanged.
