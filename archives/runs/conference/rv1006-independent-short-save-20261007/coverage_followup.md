上一轮整单元回退已按你的收口理解。这一轮只核对相对访视动作的覆盖谓词，看它会不会把来源标签当成已表达或已授权。# Conference Output: rv1006-independent-short-save-20261007 - evidence_single_object

## Output

`relative_visit_action_preserves_time` 只给覆盖状态里的 `time_validity` 增加 `complete_or_verify`。它不选择观察方式，也不采纳事实，更不发布批次。带 `time_validity` 时，关系缺失、错误流程目标、决策节点退回前一阶段、改写义务句，都不会变成 `expressed`。它比编译器宽的地方是：流程摘录可以与动作无关，覆盖仍可能为 `expressed`。

## Evidence

`source_statement_coverage` 在 `protocol_control_deconstructor.py` 4452–4456 行调用新旧两个谓词。任一为真时，只把 `ControlObligationKind.COMPLETE_OR_VERIFY` 放进 `time_validity` 的 kind 集合。`definition`、`threshold`、`calculation_input` 的 kind 集合没有变化。`calculation_input` 仍直接使 `expressed` 为假。

`relative_visit_action_preserves_time` 在 `protocol_control_source_interpretation.py` 2038–2100 行。它要求必做、无例外、无未决、功能集合不超过 `{action, time_validity}`，并且 `source_requires_temporal_resolution` 为假。相对时间词必须出现在原句中，且至少一个以「后」或「之后」结尾。`scope_quote` 必须只匹配一个冻结阶段，决策节点必须严格晚于该阶段，并带有同一阶段的 `supplementary_requirement` 流程关系。义务句与来源摘录必须与 `quoted_text` 相同，spans 必须属于该单元。2090 行在没有匹配流程时返回假。

`source_requires_temporal_resolution` 在 1927 行拒绝数字加天/周/月、`持续/连续/整个`、以及无连字符的 `D7~D14` 这类范围。`D-7~D-1` 含连字符，这个可见正则不命中。`intraday_time_fragments` 本次未读。

编译器的相对路径在 `compile_stage_bound_requirement` 685 行起。712 行要求 `target_action` 出现在流程 `source_excerpts` 中，否则抛出「不能逐项回源」。749 行要求单元只有一个 span。谓词不读流程摘录，也不检查 span 个数。

`test_relative_stage_requirement_preserves_after_stage_without_new_calendar_window` 的参数是 `["action"]` 与 `["action", "time_validity"]`，外加共享时间词。负例 `relation_missing`、`wrong_target`、`wrong_stage`、义务句改为「完成检查」只在含 `time_validity` 时断言为 `candidate_linked`。`wrong_stage` 只把节点改回 `stage:screening:one`。流程摘录被换成与动作无关的文字，不在测试中。

`failed_short_indexes` 在 8491 行之后、对齐之前返回「需要核对」。这不改变谓词本身。

`_deep_component_identity` 的 `compiler_versions` 含 `source-statement-coverage/v6`，位置在 `protocol_control_execution.py` 1898 行。

## Inference

带 `time_validity` 时，省略关系、错误流程编号、决策阶段不晚于前一阶段、伪造义务句，都不能靠这个谓词得到 `expressed`。数字时长和「给药前90分钟」会在进入 kind 扩展前被挡下。额外的 `threshold` 或 `definition` 会使功能集合超出 `{action, time_validity}`，谓词返回假；这两种功能本来也不接受 `complete_or_verify`。

`["action"]` 不走该谓词。它仍可由义务角色匹配变成 `expressed`，所以「只有 action 能通过」是原分支，不是这次扩展。

最小反例只涉及覆盖，不涉及发布。用上述测试编出的候选，保持关系、阶段、原句和 span 不变，只把对应流程的 `source_excerpts` 改成与「再次核查资格」无关的文字。谓词仍为真，`source_statement_coverage` 仍是 `expressed`。同一选择交给 `compile_stage_bound_requirement` 会在 712 行失败。由此覆盖合同宽于编译器合同。

`source_visit_scope_matches` 只用来确定唯一的前一阶段。谓词返回真，不等于临床授权，也不改 `observation_policy` 或 `fact_type`。

## Recommendation

保留这条 `complete_or_verify` 扩展，不要关掉正常相对访视输出。在 2090 行已匹配的流程上补一条与编译器同向的来源约束：该流程至少有一条摘录与原句互相包含。测试里的「再次核查资格」仍满足。同时要求 `len(unit.source_span_ids) == 1`，与编译器 749 行一致。不要改写模型已经给出的阶段或时期。

## Uncertainty

未运行测试，未读 `intraday_time_fragments`、`resolve_ancestor_scope_citation` 和 `procedure_execution_workflow_stage_id`。因此不能确定 `D-7~D-1` 是否被日内规则算作持续期，也不能确定解析函数返回空引用时，空引用与空引用相等是否会放过祖先范围。保存的那份真实流程摘录不在本次读取范围内。

## Objections

现有负例没有锁住「流程编号正确，但摘录与动作无关」。正例通过不能说明覆盖已经等于编译器合同。

若用更严的整句相等去卡流程摘录，可能误伤编译器原本允许的「短目标动作包含在较长流程摘录中」。互相包含是较小的修复；若那份已保存答案两侧都不包含，应单独保留该形状，而不是撤销整个扩展。

## Decision points

覆盖层是否必须重复编译器 712 行的流程摘录约束。建议要。否则 `expressed` 不能被理解成来源合同已经成立。

单元多 span 是否允许在覆盖层通过。编译器不允许。建议覆盖层同样不允许。

## Bounded questions

已保存答案中，冻结流程摘录与原句是否至少一侧包含另一侧？这决定互相包含这条修复会不会误伤那一次已通过整批输出门禁的复验。不会授权发布；受限消费者仍应拒绝剩余共享依赖。
