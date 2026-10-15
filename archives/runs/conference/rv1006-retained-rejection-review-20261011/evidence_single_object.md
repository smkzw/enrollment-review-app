我先读会议上下文和主会场计划，只审 base `05fb1545` 上已落地的源完成与已完成范围补丁。上下文限定审阅 base `05fb1545` 上的五文件补丁。我先核对改动范围，再沿生产、恢复、保存和受限消费调用链追踪。补丁集中在五个文件。我接着读完成范围、核对索引和保存/受限消费的实现。保存与主核对路径已经带上补齐索引。我再用纯计算核对窗口上界，以及跨章消费是否仍用旧范围。# Conference Output: rv1006-retained-rejection-review-20261011 - evidence_single_object

## Output

本轮只审阅工作区相对 `05fb1545` 的未提交五文件补丁。HEAD 就是 `05fb1545`。七份 delivery 文档不在审阅范围内。被拒候选对齐没有实现，不把它当作审查对象。没有改文件，没有跑模型、临床任务、数据库或 `.env`。下面的测试结论来自读代码；我没有重跑那 79 项连通回归。

### 已确认缺陷

**1. 高。跨章消费仍按旧核对范围验收，会否决已经按新范围保存成功的批次。**

- 文件 / 函数：`app/services/protocol_control_execution.py` 的深析关系装配，约 5563–5571 行，调用 `validate_source_target_review`。
- 证据：`target_review_indexes` 只有在传入 `completed_quote_indexes` 时，才把补齐陈述加入待核集合。新测试把处置改成治疗后执行后，默认集合是 `[]`，带上补齐索引才是 `[0]`。生产循环用 `partial` 把同一索引传给规划、提示、校验和恢复种子（`protocol_control_deconstructor.py` 约 9155–9166、9893 行）。`_validate_saved_source_review` 约 3837–3937 行、`_resumable_saved_source_review` 约 2364–2368 行、未决证明约 3239 行、`restricted_batch_from_review` 约 712–714 与 929–933 行，都传了这个索引。关系装配这一处没有传。`SourceTargetReviewValidationError` 继承 `ValueError`，会被收成 `PROTOCOL_CONTROL_SOURCE_RELATION_INVALID`。
- 危险反例：同一批次里，陈述 0 是补齐后的非入组处置，核对结论是 `not_current_control` 且动作摘录等于补齐后的全文；陈述 1 是 `potential_same_requirement`。保存门可以通过。只要存在待合并的跨章项，5565 行的期望集合不含陈述 0，整份核对因多出一项而失败。补齐项本身不是跨章项也会被连带否决。
- 安全常态：只有一条治疗后处置、没有 `potential_same_requirement`。新测试覆盖的就是这条。5565 行的 `if pending` 不会进入。诊断 2 的“保存因漏选补齐项而拒绝”在这条路上已被接上。
- 最小改法：5565 行使用与保存门相同的 `completed_quote_review_indexes(interpretation, history)`。不要先把补齐项从核对里滤掉再校验，否则全文摘录约束会再次被跳过。

**2. 中。新补读上界仍把后一条陈述的先后依据放进前一条的允许原文。**

- 文件 / 函数：`_source_unit_completion_ranges`，`protocol_control_source_interpretation.py` 约 363–382 行；`apply_source_unit_quote_completion` 约 432–445 行随后用覆盖检查拒绝交叠。
- 证据：上界取下一条 `quoted_text` 的起点。只有本条自己在“资格判定之后”且没有 sequence context 时，才把下界抬到本条 `eligibility_sequence_quote` 之后。后一条的依据若落在两条动作之间，就只出现在前一条窗口里。我用与 `locate_source_quote_offsets` 相同的紧凑定位复算了这句：`登记筛选检查。补充血常规。完成资格核对后，记录研究治疗安排。见附表。` 陈述 0 的窗口是 `登记筛选检查。补充血常规。完成资格核对后，`，包含后一条依据。按窗口最大值回填会与依据交叠，`apply` 拒绝。只扩到 `登记筛选检查。补充血常规。` 仍落在窗口内且不交叠。
- 现有测试只把共同依据放在两条动作之前，所以窗口 0 从依据末尾开始，发现不了这个布局。
- 最小改法：把每条上界再截到“落在本条引文末尾与下一条引文起点之间的其他 `eligibility_sequence_quote` 起点”。`maximum_contiguous_excerpt` 必须与这个上界一致。不要只靠事后覆盖失败来表达“不能吞并依据”。

### 关注点（未证实为错误采用）

- 历史恢复对 `source_unit_quote_completion` 只核对单元身份、引用、路径和 64 位 precondition 形状（deconstructor 约 7930–7935 行），不核对 `expanded_statement_indexes`，也不对照原答重算。这个字段现在决定谁必须全文重核。当前成功写入会填合法索引；损坏值不会在“未发送请求”处停下，而会在作者循环内的 `completed_quote_review_indexes` 抛出，再落入约 11123 行的通用 `OUTPUT_INVALID` 修复。建议在既有历史门里、模型调用前拒绝非法索引。
- 约 9266–9275 行还有一套更松的索引收集，缺字段时当空列表。它只在严格函数已经返回后给提示加一句。两套解析以后可能分开。
- 固定流程的 `validate_front_review`、`supports_front_stage_flow`、`prepare_front_stage_flow` 约 100–164、348、380 行，以及 deconstructor 约 8827–8834 行，都不传补齐索引。非默认范围内的补齐陈述会让 `supports_front_stage_flow` 返回假，因此诊断里的治疗后处置进不了这条路径。已经处于默认范围内的补齐陈述仍可能在前置核对中用短摘录通过；主循环 9893 行的带索引校验目前是成功返回前的挡板。
- `source_unit_comparison_as_review` 约 1818 行不传索引。调用方随后对整批做带索引校验，短的核心动作摘录会被拒绝，条目保持未决。这是失败关闭，也使补齐后的跨章同要求无法只凭较短动作摘录成立。
- `protocol_control_source_function.py` 约 208、293 行的背景探针同样不传索引。单条期望集合对不上时返回假，不保存该探针。

### 已核对且未发现洞的接线

补齐成功后，`expanded_statement_indexes` 只记录 `quoted_text` 实际变化的陈述；`apply` 拒绝改动除引文外的字段、拒绝缩短、拒绝越窗。失败提案不会写回 `source_interpretation`。未解析的补齐记录不会进入索引。恢复种子在全文摘录不匹配时丢掉该条，引用身份含 `quoted_text`，旧的短摘录不能因补齐后的原文被复用。共用补读额度在无效补齐时计入 `source_repairs`，同一 precondition 不会因为失败而重置。受限消费和保存门使用同一索引。没有任何模型输出或未解析记录能单独成为采用结论。

### 证据 / 推断 / 建议 / 不确定

- 证据：五文件 diff 是 247 行新增、32 行删除；上述行号和调用点是工作区当前文本。窗口复算是本地纯函数，不是产品作业。
- 推断：补丁修好了“补齐后的一般处置根本不进入核对，于是保存拒绝”这条单陈述路径。它还没有让所有下游消费者使用同一范围。
- 建议：先改 5565 行，并给窗口补上相邻依据上界。两处都补合成测试：一处是“补齐的非入组陈述 + 另一条 `potential_same_requirement`”，保存通过且关系装配仍通过；另一处是依据夹在两条动作之间，前一条的 `maximum_contiguous_excerpt` 不得包含该依据。历史门补对索引的见证。不要为此新做队列或框架。
- 不确定：没有重跑测试，也没有看诊断原文。真实下一轮诊断是否同时含跨章项、依据是否夹在动作之间，代码不能回答。

### 给 Codex 的异议、决定和问题

最重要的异议：不能把“保存和受限消费已传索引”写成“所有消费者范围一致”。关系装配仍会把合法的新范围核对当成范围错误。

决定点：在下一轮单范围产品诊断前，是否把 5565 行与窗口上界一并修正。只跑单条治疗后处置时，5565 行不会被这次诊断打到，但缺陷仍在。

有界问题：下一轮诊断的批次里，除补齐后的一般处置外，是否还可能出现 `potential_same_requirement`？依据是位于全部动作之前，还是位于相邻动作之间？前者决定 5565 会不会在这次诊断里变成关系失败；后者决定新窗口会不会再次邀请模型吞并依据后被拒绝。在得到答案前，安全的临时路径是：诊断可以覆盖当前单陈述测试所代表的路径，不要把含跨章项或句间依据的结果当成这条补丁已经验收的常态。临床和产品是否接受，仍由负责人和用户决定。
