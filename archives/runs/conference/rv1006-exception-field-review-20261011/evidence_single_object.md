我先读会议上下文和主会场计划，只按只读审阅范围核对单条来源例外限定、保存恢复和受影响消费者。上下文把审阅范围收在 `53cdd1bb` 之后的四处源码和合成用例。我先取精确 diff，再读改过的函数和消费者。diff 被截断了。我接着把 `source_function` 的完整改动和调用链读完。单条例外限定补正能冻住其他字段，也能把失败历史存下来，但“有用的有效结果”这一关过宽：任意逐字片段，包括整句原文，都能打开 `fully_expressed`。传输失败还会被记成已尝试，后续不能再读。

# Conference Output: rv1006-exception-field-review-20261011 - evidence_single_object

## Output

审阅范围是工作区相对 `53cdd1bb` 的未提交差异：`protocol_control_source_function.py`、`protocol_control_deconstructor.py`、`protocol_control_execution.py`，以及 `test_slice58c_control_deconstructor.py`。另按指定读了 `validate_candidate_alignment` / `bind_candidate_alignment`、`_saved_source_scope_question_history`、`_validate_saved_source_review`，以及合成用例 `source_exception_field*`、`source_function_field*`、`action_with_source_exception*`。没有改文件，没有跑测试，没有读临床材料，也没有调用产品模型。这不是最终验收。

最高影响的问题在写入口径，不在冻结或存档。`apply_source_function_field_repair` 只要求 `exception_words` 经 `normalize_source_excerpt` 后是 `quoted_text` 的子串。新用例第三组把整句「符合既定条件时可以免于再次提交材料」同时当作原文和例外，并期望 `bind_candidate_alignment` 成功。`validate_candidate_alignment` 在 `exception_expression is None` 时，只要该子串也出现在候选原子文本里，就允许 `fully_expressed`。因此「材料」「除外」或整句动作都能清掉 `SOURCE_EXCEPTION_WITNESS_MISSING`，并被消费成完整表达。这和提示词里的「完整限定」不是同一件事。

建议改成：用已有的 `locate_source_quote_offsets` 要求例外是本条 `quoted_text` 中唯一、连续、且不是整句的片段；对不上就只接受非空的具体 `unresolved`。同一谓词放到本阶段的恢复校验和 `validate_candidate_alignment` 的例外分支，避免只在写入时查一次。第三组合成用例应改为拒绝，不要把整句抄进 `exception_words` 当成有效结果。

## Evidence

- 工作区 HEAD 就是 `53cdd1bb5bd769f3b5c0533f11a40bf002e0759c`。上述四个文件有未提交改动，约 305 行新增。`protocol_control_candidate_alignment.py` 不在这批差异里。
- `missing_source_exception_witness` 只挑选同时含 `action` 和 `exception`、且 `exception_words` 与 `unresolved` 都为空的陈述。它不判断原文里有没有例外从句。
- `apply_source_function_field_repair` 对例外分支只放开 `exception_words` 和 `unresolved`。其余字段用 `model_dump` 对比，必须与原陈述一致。合并时只 `update` 目标陈述的这两个字段，原始 payload 里的兄弟陈述和 `units_without_statement` 不被提案替换。
- 逐字条件是 `normalize_source_excerpt` 之后的 `in` 判断。`normalize_source_excerpt` 会做 NFKC 并去掉全部空白。空串、空白、不在原文中的摘录会被拒绝；`None` 加非空 `unresolved` 会通过。`unresolved: [""]` 也是非空列表，会通过。
- 新用例 `test_source_exception_field_repair_freezes_source_and_requires_semantic_review` 的三组期望是：正当例外「尚未同意者除外」、例外在句首、以及例外等于整句。三组都期望补正后 `bind_candidate_alignment` 成功。夹具把候选的 `exception_expression` 设为 `None`，原子原文等于整句。
- `validate_candidate_alignment` 里，`exception` 与 `action` 同时存在时，没有 `exception_words` 或候选另有 `exception_expression`，不能标 `fully_expressed`。有 `exception_words` 时，只检查它是否出现在所选原子的 statement/proposition 里。`test_action_with_source_exception_is_not_a_pure_definition` 已覆盖纯例外、缺少摘录、无 `exception_words`、以及独立例外层必须拒绝；通过路径用的是「尚未同意者除外」，不是整句。
- `validate_source_interpretation` 核对摘录、范围、时间和归因，不核对 `exception_words` 是否来自本条原文。`_validate_saved_source_review` 也没有这条检查，而且服务只在 `final_output is not None` 时调用它。
- 恢复时，`source_exception_field_repair` 会在发请求前核对阶段、版本、单元、`source_refs`、json path、冻结字段哈希、批次哈希，以及原始答复哈希。`called is True` 的记录进入 `seen_exception_repairs`，之后不再读取。`outcome == "parsed"` 时还要求单条提案与当前陈述相等。标题补核和单元补读把 `transport_failed` 排除在「已尝试」之外；例外补正没有这个排除。
- 调度在调用前把 `called` 设为 `True` 并计入 `source_repairs`。传输异常、坏 JSON、坏摘录都走失败返回，状态是「需要核对」，来源保持补正前的对象。这个返回没有带上已恢复的 `source_target_review`、覆盖账或候选对齐。
- `source_repairs` 与上下文补齐、单元补读、标题补核、用途字段补正共用 `source_repair_limit`。历史里 `called is not False` 的记录在恢复时计入额度。未调用的 `publication_invalid` 且 `raw_output_chars is None` 的例外记录，服务允许没有原答。
- `_alignment_input_identity` 把整条陈述的 `model_dump` 算进来源哈希。`_source_statement_reuse_identity` 包含 `exception_words` 和 `unresolved`。旧证明要在字段变化后继续沿用，必须重新对上这个身份。
- 服务的 `source_review_failure_codes` 含有 `SOURCE_FUNCTION_FIELD_REPAIR_TRANSPORT_FAILED` 和 `SOURCE_FUNCTION_FIELD_REPAIR_INVALID`，没有 `SOURCE_EXCEPTION_FIELD_REPAIR_*`。对不上的失败码会落到 `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID`，传输失败也不会进入可重试集合。

## Inference

- 其他字段和兄弟陈述的冻结在代码上成立。新例外用例没有像用途字段用例那样造第二条原始兄弟陈述，所以这条保证没有被新测试直接封住。
- 整句或短片段被接受，不是恢复逻辑写错，而是写入谓词和消费谓词都把「出现过」当成「例外限定已见证」。语义复读仍可能发生，但确定性门禁已经允许 `fully_expressed`。
- 一次 `TimeoutError` 会被写成 `called: true`。恢复时不再读取。服务又不把这个码标成可重试。这比标题补核和单元补读更死，合成用例还把「传输失败后零次重读」写成了期望。
- 空白 `unresolved` 会记成成功补正，清掉缺失见证，同时挡住 `fully_expressed`，并且因为 `called` 已为真而不能再读一次。这不是可核的具体疑问。
- 失败返回丢掉已有目标核对，在「本条见证仍缺、后续恢复仍会在发请求前返回」时，主要是检查点变瘦，不会单独把旧证明重新用到已改字段上。字段一旦补上，对齐身份会变，旧的 `fully_expressed` 证明对不上。
- 额度用尽但 `called` 仍为 false 的记录不会进入 `seen_exception_repairs`。以后额度恢复时，同一条还会再读。内容失败和传输失败则不会。

## Recommendation

1. 在 `apply_source_function_field_repair` 的例外分支，把 `in` 换成 `locate_source_quote_offsets(quoted_text, exception_words)`。偏移必须存在且唯一，范围不得覆盖整段 `quoted_text`。更紧的口径是：该片段还必须等于按 `，,；;。` 切开的某一整段，且不是整句。对不上时只接受至少一条规范化后非空的 `unresolved`，并拒绝 `[""]`。
2. 恢复 `parsed` 的例外历史、以及 `_validate_saved_source_review` 见到本阶段记录时，重放同一谓词。不要只比较提案与当前陈述相等。
3. `validate_candidate_alignment` 在宣布 `fully_expressed` 前使用同一谓词。`exception_expression is not None` 时维持现有拒绝。
4. 传输失败不要加入 `seen_exception_repairs`，与标题补核一致。把 `SOURCE_EXCEPTION_FIELD_REPAIR_TRANSPORT_FAILED` 放进服务的失败码和可重试集合；把 `SOURCE_EXCEPTION_FIELD_REPAIR_INVALID` 放进失败码但不可重试，并写单独说明，不要落到「深析批次在限定修复次数内未产出合规输出」。
5. 删掉整句即例外的参数组。补上「除外」「材料」、整句、空白疑问必须拒绝的用例；补一条带第二陈述的原始兄弟冻结用例；补一条传输失败后在共享额度内恰好再读一次的恢复用例。

## Uncertainty

- 测试没有执行。以上是静态阅读，不是运行结果。
- 没有把「按标点切句」接到真实方案句式上。含顿号或内嵌逗号的合法例外，可能被第 1 条里更紧的口径误拒。唯一连续子片段已经能否定第三组用例和重复出现的短片段；单次出现的「除外」仍要靠切句或等价规则才能挡住。
- 初始全文解读可以直接写 `exception_words`，不经过这次补正。只收紧 `apply_*` 挡不住那条旧入口。是否同时收紧总校验，会影响已保存陈述，这次差异没有给出存量样本。

## Objections

- 新测试把整句抄入 `exception_words` 并成功绑定，写成了「有效结果」。这正好放过本次补正要补的洞。
- 新测试把传输失败后的永久停读写成期望。同文件里的标题补核和单元补读都允许传输失败后再读。例外限定没有理由更严，否则一次超时就让这条来源永远停在「需要核对」。
- 「提案不等于采用」只在提示词和 issue 文本里。确定性消费侧在候选没有独立例外层时，仍会因任意子串放行 `fully_expressed`。

## Decision points

- 例外见证是否必须是本条原文中的唯一连续真子片段，而不能是任意规范化子串或整句。建议：是。
- 传输失败是否占用唯一补正机会。建议：不占用，与 `source_heading_scope_recheck` 相同；坏摘录和坏 JSON 仍占用。
- 空白 `unresolved` 算成功补正，还是算无效答复。建议：算无效答复，不写入来源。

## Bounded questions

- 已保存的 `SourceStatement.exception_words` 是否允许自由短语，而不是本条原文的连续片段？这决定谓词只加在补正写入和恢复上，还是也加进 `validate_source_interpretation`。在确认前，不要改总校验的存量行为；先改补正、恢复和 `validate_candidate_alignment` 的 `fully_expressed` 分支。
