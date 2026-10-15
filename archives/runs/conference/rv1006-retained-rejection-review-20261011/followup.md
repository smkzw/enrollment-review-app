我只核对这三处改动和对应测试，确认先前的范围、窗口和历史门是否已经闭上。# Conference Output: rv1006-retained-rejection-review-20261011 - evidence_single_object

## Output

三处先前结论都已在当前工作区文本里闭上。对计划中的基线单范围产品诊断，没有新的实质性阻断。这不是临床或产品验收。131 项连通结果是本轮说明里的报告，我没有重跑。

### 已解决

关系装配现在把同一次运行历史交给真实校验。`_deep_results` 在待跨章时调用 `validate_source_target_review`，`completed_quote_indexes` 来自 `completed_quote_review_indexes(run_result.source_interpretation, run_result.source_scope_question_history)`（`protocol_control_execution.py` 约 5565–5569 行）。`test_cross_chapter_source_pair_requires_independent_target_result` 的 `completed_scope=True` 插入非当前兄弟，并断言传入范围为 `{0}`。该测试仍替换了 `validate_source_target_review` 和 `_validate_saved_source_review`，只证明参数到达消费方。全文摘录约束仍由生产与保存测试里的真实校验器覆盖，不是持久化临床测试。

补读上界会先定位本单元内、资格判定之后且无 sequence context 的依据，再把落在当前引文末尾与下一引文起点之间的后续依据起点当作上界（`_source_unit_completion_ranges`，约 371–387 行）。句间依据测试要求前一条最大摘录是 `登记筛选检查。补充检查记录。`，后一条从依据之后开始；合法扩写可通过，吞并依据被拒绝。共同依据位于两条动作之前的旧测试仍要求窗口从依据末尾开始，条件 `ranges[index][1] <= bounds[0]` 不会把这条更早的依据误切进上界。

历史恢复结束后、补读和作者调用之前，runner 对 `question_history` 调用同一严格函数（deconstructor 约 7953–7954 行，补读从约 7958 行才开始）。越界索引 `[1]` 在单陈述来源上抛出“记录损坏”，`transport.prompts` 仍为空。提示词后缀改为 `sorted(completed_indexes)`，松散的 `.get("expanded_statement_indexes", [])` 已删除。

### 仍开放，但不阻断这次诊断

固定流程的前置核对仍不传补齐索引。非默认范围的补齐陈述会让 `supports_front_stage_flow` 返回假，因此基线单范围诊断走不到那里。只有诊断明确改走 `RV1001-FLOW` 时，这才重新成为范围问题。

早期历史门只拒绝空、重复、非整数和越界索引。它不从原答重算索引，也不要求索引属于该补读单元。新鲜写入仍按实际引文差异生成索引；这不影响一次新的单范围诊断。

`_FakeTransport.prompts` 只记录 `start` 和 `continue_session`。零提示的证据同时依赖调用顺序：严格检查位于这些调用之前。

### 证据、推断、建议、不确定

证据是上述当前定义和测试。推断是两个已确认缺陷和指定的早期历史问题已经消除。建议按基线单范围继续诊断，不要把跨章模拟或句间依据测试当成临床通过。不确定的是我没有复跑 JUnit，也没有查看 v4 的原始输出。
