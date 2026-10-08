我先按会议指定的只读范围核对草稿与主会场计划，确认剩余来源疑问能否单条续核，以及旧核对资格和修复预算边界。会议上下文把证据限定在五条源码路径。我按这些路径核对剩余来源疑问、旧核对资格和修复预算，不读病例、不改源、不跑模型。关键门在 `not resuming_partial`。我接着读复用身份、来源疑问重核，以及草稿恢复时的预算与校验消费者。只读核对结论：按已保存的修复账，剩余那条来源疑问现在不能安全地单条续核。只删掉 `not resuming_partial` 会重新放开整段疑问循环，并在失败时丢掉已过门禁的草稿。

# Conference Output: rv1006-source-question-partial-resume-review-20261008 - evidence_single_object

## Output

### 结论

不能。在旧核对资格和共享修复额度仍有效的前提下，现有「来源疑问 + 已审阅草稿」路径不能安全地只补最后一条来源疑问。

最小提案（删掉 `protocol_control_deconstructor.py` 约 7414 行的 `not resuming_partial`）不够，而且会破坏失败保留。恢复运行时 `source_repairs` 从 0 重新计数，不会读取上一份诊断里已经用掉的 4 次范围提案。疑问循环仍按陈述下标顺序选择所有仍符合 `can_recheck_source_scope_question` 的条目。失败返回又不带上已经恢复的 `partial_wire`，诊断写入会把已过门禁的草稿记成空。

在 Codex 明确批准「在已用完的额度之外再给 1 次、且只针对尚未见证的那一条」之前，应维持现状：草稿保留，最后一条疑问保持未核，不把这次失败改写成来源种子证明。

### 证据

只读了会议允许的五条路径，未读病例，未改源，未跑测试或产品模型。冻结行为以当前工作区这些行内实现为准；会议上下文称冻结 HEAD 为 `f205bf54`，本次未再核 git。

- 恢复时 `resuming_partial = resume_wire is not None`，`repair_used` 立刻为真，但 `source_repairs = 0` 无条件重置（`protocol_control_deconstructor.py` 7062–7090）。疑问块的准入是 `source_interpretation is not None and not resuming_partial and callable(source_reader)`（7414–7417）。额度用尽时 `continue`，不会为被跳过的最后一条留下见证。
- 生产恢复在调用 `run()` 之前要求 `start_source_interpretation` 可调用（`protocol_control_execution.py` 4016–4046）。因此生产路径上，挡住续核的是 `not resuming_partial`，不是缺少读取器。`run()` 不接收旧 `attempts`，调用方虽然持有 `previous` / 来源作业诊断，但没有把已花费次数传进去。
- 单条提案的冻结范围已经在 `apply_source_scope_question_recheck`（`protocol_control_source_interpretation.py` 416–441）。原生列只允许改 `unresolved`、`scope_quote`、`affected_stage`、`time_words`；原文、逻辑、力量、例外和其余字段必须与原陈述一致。原生列会走现有 `apply_source_scope_correction`。混合标记列在 `test_native_column_question_uses_real_headers_not_an_unrelated_action_target` 中以「共享范围」拒绝。这次没有重读抛出该句的校验函数本体。
- `can_recheck_source_scope_question`（368–383）在 `unresolved` 非空、`affected_stage is None`，且具备两个原文时间词或全部标记列原生范围时为真。成功提案若清空疑问或写上阶段，该条就不再入选；若保留真实疑问且阶段仍为空，该条继续入选。测试 `test_real_uncertainty_is_retained_and_single_time_is_not_selected` 固定了「保留疑问」这条合法结果。
- 无草稿的来源恢复会发疑问调用，并与 `max_schema_repairs` 共用计数（`test_source_time_question_recheck.py` 162–191）。带 `resume_wire` 的 slice58c 夹具会保留原草稿和已证明的兄弟核对；本次读到的夹具没有一条断言「有读取器时恢复不得再发来源疑问」。
- 疑问失败的返回只交 `source_interpretation`，不交 `partial_wire`（7457–7460）。同作业失败诊断原样保存 `result.partial_wire`（`protocol_control_execution.py` 4137–4189）。新的 `attempts` 从本次 `run()` 重新编号，第一条是草稿 JSON，不是原来的来源原答。
- `_revalidated_source_seed_proof`（2341–2544）只重放来源原答及范围内的范围/摘录/疑问校正；疑问与校正合计不得超过 `max_source_corrections`。证明结果明确丢弃 `partial_wire`、目标核对、覆盖账、对齐和会话。`_unrepaired_source_seed_proof` 在已有 `partial_wire` 时直接返回 `None`（2291–2292）。这是来源清单重放，不是「组件未变的已保存草稿」证明。
- 组件与修复合同都未变时，`_validated_deep_partial_source`（2626–2701）保留草稿并走 `_resumable_saved_source_review`，不重放疑问额度。组件、待校正或修复合同变化时，种子证明失败则整份草稿返回 `None`，不保留线稿。
- `_source_statement_reuse_identity`（6815–6836）包含引用、范围、阶段、时间词、`unresolved`、力量、例外、顺序和权威。运行器只在 7938–7946 用它过滤 `resumed_review_indexes`。`previous_covered`（7947–7954）对 `covered_by_official`、`covered_by_procedure`、`background_context`、`definition_dependency` 不要求该指纹。指纹不符时，`reuse_inputs_unchanged`（7966–7975）只比较状态、处置和链接。完整校验在 8544 行对组装后的整份核对执行。
- 仍有 `unresolved` 的陈述不能被校验成完整覆盖或排除性决定（1618–1625）。因此会议所述「目标核对留下最后一条疑问」这一形态，不会把该条旧决定当成覆盖结果复用。`validated_source_review_seed`（1926–1960）会丢掉单条校验失败的项目，但只要还有任意一条种子通过，`latest_source_target_review` 仍指向整份旧核对对象（7598–7600）。

会议给出的已消毒观察与上述控制流一致：六条冻结表陈述中，四条较早陈述和最后一条缺少原生列范围；共享额度 4 被四条提案用完；作者仍运行；目标核对留下最后一条疑问并使该组失败；四条提案留在已保存来源中。这不是模型不可用，也不是校验器已经证明的临床歧义。十五个已完成组零调用复用、其后独立组完成，说明失败被限制在这一组，没有把范围重置扩展到兄弟组。

### 推论

最后一条会在首次运行被跳过，是因为同一 `run()` 内 `source_repairs` 已到上限，不是因为恢复消费者拒绝它。下一次恢复是一次新的 `run()`。只删守卫之后，选择器看不到「这四条已经见证过」，只会重新扫描当前仍可核的陈述。四条提案若仍留着疑问且阶段为空，它们会再次排在最后一条前面，把新额度再次用完。四条若已不再可核，选择上会只打到最后一条，但这笔调用记在新作业的满额额度上，不记在来源作业已经用完的账上。

失败时诊断会失去线稿。下一次同一作业的 `last_checkpoint` 若成为这条新诊断，种子重放无法把草稿 JSON 解析成来源清单；组件或修复合同稍后一对不上，`_validated_deep_partial_source` 会丢掉整份草稿，包括原本已经过门禁的线稿。跨作业 `resume_partial` 仍读来源作业的最后检查点；只有新失败覆盖了该作业的最后检查点时，旧见证链才会从恢复入口消失。`JobStore` 是否另存历史检查点，这次没有读。

旧的未决决定不会被当成最后一条的覆盖证明。兄弟陈述在指纹和覆盖账都未变时可以不重读。这个保护不够覆盖「提案改了范围或时间、覆盖状态却没变」的条目，因为覆盖类和背景类决定可以绕过指纹。8544 行的整批校验能挡住时间冲突和「仍有疑问却宣称覆盖」，但它是整份核对失败，不是只作废被改的那一条后继续。`scope_quote` / `affected_stage` 的变化是否总能被该校验拒绝，取决于旧决定类型；这次没有把每种决定都走完。

`_revalidated_source_seed_proof` 不能用来证明这次恢复后的线稿。它的成功结果就是丢弃线稿。用它代替线稿恢复，会违反「无关内容保持原草稿」。

### 建议

现在不要改产品源码。已保存草稿继续按门禁有效的局部草稿保留；最后一条原生列疑问保持未核；不要为换目录或新的 `deep_max_schema_repairs` 清零已花费的 4 次。

若 Codex 不批准额外名额：问题的答案就是不能续核。不要删除 `not resuming_partial`。

若 Codex 批准在来源作业原额度之外仅再给 1 次，最小改动应同时满足下面四条，而不是只删守卫：

1. 调用方从已保存 `attempts` 按 `_revalidated_source_seed_proof` 2492–2521 行的同一见证规则算出已花费次数和已见证下标，传入 `run()`。`source_repairs` 从该次数起步，上限取来源作业额度，不取新目录额度。已见证且前提哈希仍匹配的下标不得再选。
2. 只有一条未见证且 `can_recheck_source_scope_question` 为真的陈述时，才调用现有 `build_source_scope_question_prompt` 和 `apply_source_scope_question_recheck`。提案前后原文、力量、例外、来源身份和兄弟陈述保持同一对象内容。
3. 该调用失败时，返回突变前的 `source_interpretation`，并显式返回原 `partial_wire`。诊断不得写成 `partial_wire: null`。
4. `previous_covered` 与 `resumed_review_indexes` 使用同一指纹。指纹已变的条目不得因状态和链接未变而复用。随后仍走现有完整来源、覆盖、目标和终局校验。宿主不得自动改线稿、清空 `unresolved`，也不得新增受试者要求。

建议的定向消费者检查，本次未执行：

- 正面：已花费 4 次、四条不再可核、一条仍可核、不批准新名额时期望零次疑问调用，线稿与兄弟核对不变。
- 正面：批准 1 次且只有未见证下标可核时期望恰好一次 `start_source_interpretation`，只改允许的原生字段，`partial_wire` 字节不变，被改下标不在复用核对中，兄弟不被重读。
- 负面：疑问传输或模式失败仍返回原线稿和突变前的来源；新诊断的 `attempts[0]` 不被种子证明当成来源原答。
- 负面：指纹已变但 `target_inputs` 相同的覆盖决定不得进入 `previous_covered`。
- 负面：改写 `quoted_text`、力量或例外的提案被现有 apply 拒绝，且不替换线稿；混合标记列仍走现有共享范围拒绝。
- 负面：新的 `max_schema_repairs` 或新目录不得把已见证的 4 次清零。

### 不确定性

未读 `source_statement_coverage` 的函数体。兄弟覆盖是否会因单条时间或范围变化而改变，只根据「指纹相符时必须整条覆盖账相等，否则重新核对」推断。未读 `protocol_control_agent_repair_contract_sha256` 的组成，也未确认检查点存储是追加还是只留最后一条。未把 8544 行之后的每个失败分支都读完。以上不足改变「现在不能只删守卫」这一判断；它们影响的是批准额外名额后，线稿与新来源一起失败时的精确诊断形状。

### 异议、替代、决定与问题

最重要的异议有三条。第一，删除守卫续的不是「剩余一条」，而是一次预算从 0 开始的全量疑问循环。第二，失败返回与 4137–4139 行的诊断写入会把已过门禁的线稿丢掉，种子证明又补不回来。第三，`_source_statement_reuse_identity` 还没有管住 `previous_covered` 的覆盖类和背景类决定；「改后来源后仍信任旧的完整目标核对」这个口子还在。

替代做法是维持现有失败，或者在调用方传入已花费账本和未见证下标之后，只做上面第 1–4 条。不要升级全局提示、编译器或版本白名单，也不要把线稿恢复改写成来源种子重放。

需要 Codex 决定的只有一件事：来源作业共享额度已经用掉 4 次之后，是否明确批准再花 1 次，且仅用于尚未见证的那一条原生列疑问。未批准时，安全的临时路径是不改代码、不重读模型、不把该组失败推广到已零调用复用的十五个组。

请 Codex 回答：这一次额外调用是否被批准，并且是否仍受来源作业原来的 `deep_max_schema_repairs` 约束，而不是受新目录限额约束？该答案决定能否进入编辑轮；不决定则本角色维持「不能续核」。
