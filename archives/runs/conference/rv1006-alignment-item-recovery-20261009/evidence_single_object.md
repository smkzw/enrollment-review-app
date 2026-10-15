只读审阅这次对齐项恢复。先核对相对冻结 HEAD 的差异和指定控制流，再按四条验收路径找可复现反例。# Conference Output: rv1006-alignment-item-recovery-20261009 - evidence_single_object

## Output

当前工作区 HEAD 是 `43928e2779dc52b1560c3378298df9dc4f66d785`。相对该 HEAD，本次功能差集只有 `app/agents/protocol_control_candidate_alignment.py`、`app/agents/protocol_control_deconstructor.py` 和两个指定测试文件。另外 7 个 delivery 文档的既有脏文件不在本审阅结论内。下面是只读审阅，不是临床批准，也不是合并结论。

### 证据

- `bind_partial_candidate_alignment` 会整份拒绝这些回答：与原 JSON 不一致、自带 `proofs`、版本不对、条目重复、配对不等于预期、陈述或候选越界、结构单元或原文摘录对不上。逐项 `validate_candidate_alignment` 抛出的 `ValueError` 只丢掉该条，其余条保留，并给每条证明写上同一份完整 `response_text`。全部失败时返回 `None`，不造空 `proofs`。对应测试把坏摘录的兄弟留在失败明细里，作业状态仍是「需要核对」，`final_output` 为空。
- 通过条的复用同时核对来源哈希、完整候选哈希、原答哈希，以及原答里该配对的逐字条目。候选标题一改，复用结果为空。
- 有非空 `applies_to_trigger_branch_indexes` 且不等于全部分支时，`_conditioned_obligations_cover_source` 直接失败。显式绑满全部分支时，每个触发分支都要有一条已选原子，其 `statement` 与条件前缀逐字相等，再由该义务组覆盖后果。契约写明空列表是 control-level / unscoped，不是「全部触发分支」。
- `_common_trigger_preserves_visit_time` 只用 `statement.startswith(时间词)`，再用 `source_visit_scope_matches` 对冻结阶段 `display_name` 做子串或「期内」词干匹配。通过后，`time_validity` 的锚点方向核对被跳过。新正例的触发句是「基线期已完成核查者」，时间词是「基线期」。
- 数值修订只在同时满足这些条件时调用既有 `continue_atom`：失败 `reason == numeric_predicate_missing`、`atom_paths` 长度为 1、`statement_ids` 与 `cited_unexpressed` 相同、预算未用完、该三元路径未走过。合并器冻结 kind、statement、modality、temporal_scope、来源、判断标记、prospective_period、continuing_obligation 和兄弟原子。合并异常时退回调用前的 `wire`。
- 合并成功后把整份新 wire 写入 `raw_text` 并 `continue`。后续「需要核对」返回使用当前 `wire`，没有回到修订前草稿。`validate_control_atom_evaluation` 只核对求值原文包含在原子摘录内，并写明不证明语义保真。对齐侧的数值门只比较比较符、一个数字、单位和整句条款，不比较 `proposition`、`observation_policy.mode`、`repeat_scheme`、`record_semantics`。
- 多数字来源在「没有任何已选原子带 predicate」时先抛 `CandidateNumericAlignmentError`，此时尚未执行 `len(numbers) != 1`。路径只要有一个摘录同时含数字和比较词，就会进入 `continue_atom`。
- 同一轮复用 `reusable_proven_alignment_items` 默认只要 `fully_expressed`。`incomplete` 即使带有合格证明，也不会进入 `resumed_alignment_items`。执行层发布门在新增要求未全部 `fully_expressed` 时拒绝（`protocol_control_execution.py` 约 3495–3502 行）。`test_publication_scope_never_guesses_unknown_or_structural_ownership` 仍要求未知、跨候选、越出来源或结构归属时修不了范围。
- `continue_atom` 不把修订轮写入会话历史；`restore_scoped_session` 只绑定上下文哈希，不重建对话。

### 推论

1. 空 `applies_to_trigger_branch_indexes` 会被当成「可以核对」而不是「未绑定」。反例：原文「已完成核查者，领取材料，回收材料」；两个触发分支各有一句逐字「已完成核查者」；义务组摘录覆盖「领取材料」「回收材料」；`applies_to_trigger_branch_indexes == []`。函数不会在分支绑定处返回，随后可以给出 `fully_expressed`。同一形状若只写成 `[0]`，现有测试要求失败。空绑定比半绑定更宽，和契约里的 unscoped 相反。
2. 访视时间词只要是触发句开头，阶段显示名又能子串套上，未来或范围被改掉的句子仍能关掉时间锚点。反例：时间词「筛选期」，冻结阶段显示名「筛选期」且 `review_stage` 一致、来源非空；触发原子句为「筛选期外已完成核查者」。`startswith` 为真，`source_has_single_visit_anchor` 对无数字、单时间词为真。把时间词改成「筛选期内」、阶段名仍是「筛选期」时，「期内」词干规则同样为真。新正例没有分隔「基线期」和后面的「已完成核查者」，所以锁住了这一种前缀。
3. 求值修订在重核失败后仍留在草稿里。反例：唯一缺口原子的原文是「年龄至少18岁」；模型只改 `evaluation`，predicate 写成 21，或把 `observation_policy.mode` 改成 `any` 同时留下合法的 ≥18 predicate，statement 和来源不动。合并器接受。predicate 为 21 时，第二轮对齐会失败，但返回的 `partial_wire` 已是改后的 wire。mode 改成 `any` 且数字正确时，现有数值门挡不住，单条作业可以走到 `final_output` 非空。多数字原文「收缩压≥140且舒张压≥90」落在同一个无 predicate 原子上时，也会先调用这一次修订。
4. 合法的 `incomplete` 条会在数值修订后的再次对齐失败时从结果项里消失。反例：同答第 0 条是已通过校验的 `incomplete` 并带证明，第 1 条是唯一数值缺口。修订合并成功后再次对齐，第 0 条因不是 `fully_expressed` 不进入续用集。新回答身份不合法时，异常分支只回填续用集，结果对齐不再包含第 0 条。原答全文仍可能留在第 0 条旧证明或尝试记录里，但保存下来的 items 不再有这一条。全部新增要求都未 `fully_expressed` 时，执行层消费门仍会拒绝共同发布。这一条是记录丢失，不是放行发布。

### 建议

按这个顺序改，仍用现有合并器和 `continue_atom`，不新增投票、阈值或第二套修订框架。

1. `_conditioned_obligations_cover_source`：触发表达式存在时，只有 `set(applies_to_trigger_branch_indexes) == set(range(len(branches)))` 才允许走共同前缀。空列表直接失败。
2. `_common_trigger_preserves_visit_time`：时间词必须是触发原子里的独立片段，拒绝「期外」「期内」借前缀或词干换成阶段。阶段窗口代码与来源时间词不一致时不得跳过锚点核对。正例应改成能看出分隔的句子，而不是靠「基线期已完成核查者」。
3. 数值路径在调用前确认来源只有一个数字、一个比较方向，且这条路径上的原子就是唯一缺 predicate 的已选义务原子。合并后的 wire 只有在完整门和来源对应都重新通过后才作为 `partial_wire` 留下。任一重核失败，恢复调用前 wire 和当时的逐条证明，不重签旧证明。
4. 再次对齐前，把本轮已经证明、且候选哈希未变的 `incomplete` 条放进失败回填，避免续用过滤器把它们清掉。

### 异议、决定点、问题

- 异议：新测试覆盖了坏摘录保留、显式半分支拒绝、带数字的「基线前7天」、以及合并期改 statement 的失败。它们没有覆盖空分支绑定、无数字的「期外/期内」、只改 predicate 或观察选择、以及 `incomplete` 兄弟遇上数值修订后再对齐失败。不能用这些测试数量说明包已经收住。
- 决定点：空 `applies_to` 是未绑定，应拒绝。重核失败的求值拼接应回滚到原草稿。访视前缀应按独立时间词判断，正例需要改。
- 问题：真实作业那一次结构失败的 `reason` 是不是 `numeric_predicate_missing`，且 `atom_paths` 是否正好一条？本次没有读作业载荷。若当时只是普通 `ValueError`，新代码只会留下通过的条目，不会调用 `continue_atom`。在 Codex 确认该失败明细之前，安全的临时结论是：逐条保留已经接上 `ValueError`；数值局部修订只覆盖「无 predicate、路径唯一」这一支，而且失败草稿目前还会留下模型改过的求值。

### 不确定性

未运行测试，未读 `.env`、数据库、原始病例和其他用户目录，未把整个 `protocol_control_deconstructor.py` 从头读完。定义消费者内部的共同发布只核对到执行层「新增要求必须全部 fully_expressed」这道门，以及 runner 在仍有 `pending_additional` 时不走「已解析」返回。`continue_atom` 不写会话历史；恢复后草稿以保存的 `partial_wire` 为准，这一点未做一次真实恢复演练。
