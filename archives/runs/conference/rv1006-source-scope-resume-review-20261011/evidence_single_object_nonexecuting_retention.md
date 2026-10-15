收到同会话定向续审（冻结工作树 delta，四文件 read set）。只读、不委派、不落盘（Explore/Plan 子代理与"不委派"边界冲突；计划文件不写）。先定位 delta 符号。

定位完成。读取核心实现（4 个并行）：全体紧凑受限、时间限制索引、单元引句覆盖/补全、恢复失败与部分恢复分支。

最后 1 次读取：显示分隔/覆盖仲裁函数（决定重复成员文本与重叠区间的行为）。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

定向边界审阅（12 次只读已用满：4 次符号定位＋8 次定义读取）。未改文件、未运行测试、未委派（Explore/Plan 子代理与"不委派"边界冲突，未启；计划文件未写）、未读临床/DB/env/私有目录。未复读历史或此前叙述；以下全部为当前工作树直读。**同产品模型家族、同恢复上下文，模型/上下文独立性折减；非医学批准；临床原件与最终集成由 Owner 负责。**

---

### 事实与内部保护（按问题）

**Q1 无效作者含义/错误方向/依赖候选/不完整来源是否被新伪装为"忠实受限"——未发现决定性缺陷。**

- 入口极化：`restricted_batch_from_review`（`protocol_control_restricted_source.py:893-934`）只放行末次错误类 ⊆ {SCR, STU, TEMPORAL}（`:899-906`），先 `validate_completed_quote_review`（`:910-912`）再语句级、再整单元，且整单元前重验来源/覆盖/目标核对（`:922-930`）；`_whole_unit_restriction` 自身要求末次类**恰为** `{STU}` 或 `{TEMPORAL}`（`:459-465`）、`check_protocol_control_batch_candidates` 与 `_coverage_matches_current_proofs` 通过（`:469-471`）。
- 新扩展的三种非执行处置仅在"受限单元"内被接受（`:500-506、529-533`），并带三个硬闸：**任何候选引用其单元或 span 即拒**（`:511-514`）；每单元必须逐字覆盖（`_unit_statements_cover_source`，`:547`）；被移除候选的冻结单元必须 ⊆ 受限集、保留候选不得与受限 span 相交（`:578-587`），最后再过候选合同门（`:888-889`）。
- 方向/兄弟：`not_current_control` 作为**非受限单元的兄弟**时，要求处置 ∈ {POST_TREATMENT_EXECUTION, NON_ENROLLMENT_EXECUTION} **且** `eligibility_sequence == "after_eligibility_decision"`（`:567-572`）；否则整体 `None`。受限单元内该陈述的 `unresolved_dimensions` 被写成"已核为判定后执行…不作为当前入排条件"（`:620-622`），不改写为资格结果。`unresolved` 项必须带 aspects（`:481-483`）。
- 时间扩展由类型化范围证明，不从 prose 推断：`_temporal_restriction_indexes(whole_unit=True)`（`:156-226`）校验 code/json_path/retry_class/ids 有序/affected_dependents/source_refs，并要求 action、required/prohibited（或"必做单元内的推荐"特例）、`requires_temporal_resolution`；`related_additional` 分支把同单元附加要求一并非执行（保守）。
- **可达反例尝试均被拒**：候选依赖 post-treatment 单元→`:511-514` 返回 None；无 typed after 的 not_current→`:571` 返回 None；共享候选跨出受限集→`:582` 返回 None。**残余为标签粒度**：not_current 陈述的机器 `limitation_kind` 仍记为 `interpretation_unresolved`（`:612-613`），与维度文字（`:620-622`）不完全同义——**建议**（下游按 kind 消费时可能看不出"已确认判定后"），非采用风险。

**Q2 显示覆盖（成员来源/重复文本/真实竖线/重叠）——保护充分，反例均 fail-closed。**

- 重建条件（`source_interpretation.py:329-342`）：须 `table_context`＋`member_texts`＋`member_source_span_ids` 齐备；每个非空成员文本可定位；且**整段 excerpt 必须精确等于成员切片的 " | " 连接**；仅把相邻成员之间的缝隙加入 `extra`。真实竖线只有在被此重建覆盖时才不算遗漏；成员内部的字面竖线留在成员切片内。
- 仲裁 `source_statement_ranges_cover_unit`（`protocol_control_gate.py:5074-5095`）：`end <= start`、`start < cursor`（重叠/逆序/空区间）、`end > len` 一律 False；区间外只允许空白与分隔符（`allow_joining_punctuation` 时含逗号）。文档明示该宽松只服务整单元受限（非可执行）路径，**可执行独立证明用严格默认**。
- 反例：成员文本不匹配/数量错→连接等式失败，无分隔符可加→不完整；**重复成员文本**可能产生逆序 marker，但仲裁 `end <= start` 直接 False（变成补读路径，非误判覆盖）；重叠声明引句由 `source_unit_quotes_cover_source:314-316` 拒绝。**未发现可穿过的布局变体。**

**Q3 时间补读选择——不越损坏诊断/错范围/当前线路/累计预算；cause-local 且旧记录只读。**

- `_resumable_unit_completion_failure`（`protocol_control_execution.py:2784-2832`）：仅接受 workflow_phase=`source_unit_quote_completion`＋code 正确＋`error_classes==["…TRANSPORT_FAILED"]`＋outcome=`transport_failed`＋`called is True`，否则 raise（`:2793-2796`，**无效补读不自动重试**）；要求种子证明 schema/adopted=False 且**语义草稿四项全部为空**（`:2799-2804`，旧候选/复核被丢弃）；detail 的 statement_id/source_refs/affected_dependents/json_path/**precondition_sha256** 必须与实存解释一致（`:2812-2821`，错范围即拒）；历史账必须存在且末条与本次一致（`:2822-2824`，**不重置额度**）；剩余缺口由 `source_unit_quotes_cover_source` 重算（`:2825-2829`）。返回仅含剩余单元的 cause-local 种子（`:2830-2832`），旧 durable 记录不被写。
- 上游：损坏诊断/错批次/线路不符/changed_components→raise 或 None（`:2901-2934`）；`source_repair_limit` 取自源作业冻结限额（`:2872-2880`）并随证明传递（`:2996-3009`）。

**Q4 消费者覆盖与最低附加检查**：正/负消费面（语句级要求 `validate_source_target_review`；整单元要求 typed 类＋逐字覆盖＋候选隔离＋候选合同）在本 delta 内自洽。**上受控真实恢复前的最低附加检查**：① not_current 陈述的投影端到端标签断言（闭合 Q1 残余粒度）；② "重复成员文本"fixture 断言 fail-closed 且**进入补读路径**而非覆盖通过（代码看似闭合，但本轮未读新测试，缺测试证据）；③ 补读种子只重读 typed 缺口单元、其余单元与旧历史不变的断言（测试面同理）。

---

### 结论、反例与建议

- **无决定性缺陷**：四条防线（类型化入口、候选隔离、逐字覆盖、类型化补读）在当前源码上互相闭合；未发现在本 delta 内把失败语义伪装成忠实受限的可达路径。**不主张临床正确性**。
- **建议**：① 给 not_current 陈述以独立 `limitation_kind`（或附加机器字段），避免下游把"已确认判定后执行"当作"解释未决"；② 增加 Q4②/③两个最小断言（合成 fixture 即可，不需新框架）；③ 对 `related_additional` 特例补一条反例（同单元 recommend/required 混排）确认仍只产出非执行结果。
- **限制**：本轮优先审生产边界，**未读**新增测试（`test_protocol_control_execution.py:800-900、1095、1240-1300`）、`full_protocol_coverage.py` 成员构造与 `protocol_controls.py` 成员校验（成员 span 闭合为前包证据）、`locate_source_quote_offsets` 的重复文本语义（仲裁已使其 fail-closed，影响为漏判而非误判）。owner 的连接跑 215/1440/38.27s 未复核，也不作为边界证据。

**同模型家族折减**：本审阅与产品为同族模型、同恢复上下文；以上为源码合同级判断，不构成医学批准或发布依据；实际临床来源核实与最终集成归 Owner。
