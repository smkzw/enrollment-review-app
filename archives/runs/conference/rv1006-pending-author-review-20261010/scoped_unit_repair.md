同批准角色只读增量审阅（来源闭包局部修订）。先定位新符号在三源码与三测试中的落点。

定位完成：merge 与 restore 在 deconstructor 5059/5089，parse 在 5729，runner 选择在 11590-11630，transport 新方法 1498。先读四段核心实现。

继续读 runner 授权范围与调用、merge 消费现场、restore 闭包分支与服务端身份。

继续核对：时间保留函数、预算计数点、两个新测试。

继续核对：已核时间保留函数、预算计数点、身份列表与待核提案恢复入口。

关键核对：scoped 解析失败后的状态清理与修复选择链尾部。

核对失败转"需要核对"的兜底条件，判断 stale 状态是否真实可达。

最后一项可达性核对：`repair_baseline_wire` 是否在失败路径被清空（决定 stale 闭包 ID 是否会被再次消费）。

# Conference Output: rv1006-pending-author-review-20261010 - evidence_single_object

## Output

### A. 已读范围（20 项聚焦读取，全部只读；无写入/测试/网络）

- deconstructor：`_merge_scoped_unit_repair` 全函数（5059-5086）；`_restore_bounded_wire_repair` 的来源补入/义务原子/闭包重分区/定向候选分支（5089-5484）；`_parse_repartition_with_checked_time`（5729-5749）；`_restore_unchanged_time_operands`（5687-5726）；runner scoped 选择与调用（11460-11688，含 local batch/wire、prompt、`continue_scoped_unit_repair` 调用、兜底 `continue_session`）；merge 消费现场与预算（8440-8535）；失败兜底与 `repairs += 1`（11270-11320）。
- transport：`continue_scoped_unit_repair`（1498-1515）、`continue_session`（1517-1549）、`restore_scoped_session`/`restore_history`（1870-1909）。
- execution：`_pending_author_resume`（2794-2815）与组成身份 validator 串（2098-2125）。
- 测试：slice58c `test_scoped_unit_repair_preserves_siblings_and_rejects_scope_escape`（11490-11520）、`test_scoped_unit_repair_runs_through_current_consumer_without_full_history`（11523-11556）；transport `test_scoped_snapshot_resume_enables_only_self_contained_requests`（1550-1574）、`test_scoped_unit_repair_uses_frozen_local_schema_and_does_not_invent_history`（1577-1599）。

### B. 已核事实（读证，非采信结论）

1. **授权域不扩**：`_merge_scoped_unit_repair` 强制 `patch.dispositions` 集合恰等于授权集、候选来源 ⊆ 授权集，并对"跨界原候选"直接 `REPAIR_SCOPE_ESCAPE`（5065-5079）；授权集 = 既有 `mutable_candidate_source_union`（11460-11464、11598），即原传递闭包，未被本路径放大。
2. **宿主保留兄弟**：合并用 `previous.model_copy`，授权外处置与候选按原对象保留（5081-5086）；restore 闭包分支再验 `current_union ⊆ 授权 union`、拒绝跨界候选，未覆盖单元必须被候选覆盖或为治疗后处置（5303-5360）。测试断言 `merged.dispositions[1] == original.dispositions[1]`、`partial_wire.dispositions[1]` 保留（11518、11555）。
3. **已核时间不覆盖**：`_restore_unchanged_time_operands` 仅在"探测原子（强制旧属性后）与旧原子整体规范化相等且唯一匹配"时回填 `evaluation.time_operand_attribute`，不触碰时间约束/来源定位（5687-5726；入口条件 5742-5748 要求来源 ⊆ 恰一个原候选）。
4. **support 无候选删除被拒**：`dropped_units` 检查；测试证明即使 `allow_post_enrollment_reclassification=True`，非 `post_treatment_execution`（无 notes 匹配）的处置仍 raise（11504-11516）。
5. **局部上下文无重复**：owned=闭包，context=原 context+闭包外 owned，两者按 batch 构造不相交（11600-11603）；prompt 附局部未核提案与"尚未采用"（11615-11621；测试 11537-11539 断言 su-01 owned / su-02 context）。
6. **transport 权限边界**：scoped 方法仅当 session 有真实 history 或已核 scoped 绑定方可（1504-1505）；只发单条 user 消息、不入 `_histories`（1507-1515）；`continue_session` 仍要求真实历史并落全轮（1517-1549）；`restore_scoped_session` 拒绝空/非法摘要与不同上下文覆盖（1870-1883）。测试 1567-1573、1588-1599 逐条覆盖。
7. **预算与会话**：scoped 调用前通用分支 `repairs += 1`（11316-11320）、`repair_used=True`（11596），预算按既有共享账扣除；session_id 不变，无重置/伪历史。
8. **身份**：`source-closure-scoped-unit-repair/v1` 仅进 `validator_version` 连接串（2118），compiler/source/route 未变；`_pending_author_resume`（2794-2815）与上轮读证一致（排除集、双 hash、used 校验、state=absent）。

### C. 按严重度发现

**F1 · 低-中（本增量新引入，可达；fail-closed 但有真实损耗）· scoped 回复 schema-invalid 后 `scoped_unit_repair_ids` 未清理**
- 证据：标识符全文件仅出现于 8307（初始化）/8471-8472（消费）/8483（清理）/11598（设置）——**清理点只有 8483**，而它在解析链表达式（8471）之后；合并/重解析一旦抛错即跳过清理；异常处理器的逐模式复位块（10494 起）不含该变量；`repair_baseline_wire` 从无 `= None` 赋值（仅 10781/10860/10892 赋 `wire`），故 8472 的 `scoped_unit_repair_ids and repair_baseline_wire is not None` 在后续轮次持续成立。
- 可达序列：scoped 尝试获授权（`allow_candidate_repartition`）→ 模型回复不是可解析 wire（WIRE_SCHEMA_INVALID/OUTPUT_INVALID，不含 11280 的 `REPAIR_SCOPE_ESCAPE` 兜底码）→ 处理器继续（`repairs` 本例 1<2，11319-11320 再 +1）→ 走通用兜底 `continue_session`（11685-11688）→ 其回复在下一轮被**强制**送进 `_merge_scoped_unit_repair` → 集合不等 → `REPAIR_SCOPE_ESCAPE` → 11280 立即转"需要核对"。净效果：兜底修复的合法回复永不可被消费、多一次白付调用、错误码误挂到系统自己请求的全包回复上。
- 不受影响路径：回复可解析但越域 → `REPAIR_SCOPE_ESCAPE` → 11280 立即兜底结束，无 stale 复用（干净）。若 stale 轮回复恰为授权集内的合法 scoped patch，则合并通过并再走完整 hydrate/gate，语义仍在原授权域内，不构成采用绕过。
- 最小修复（约一行）：在异常处理器复位块（10494 附近）加 `scoped_unit_repair_ids = set()`，或在解析链用 `try/finally` 保证清理；补一个回归测试：scoped 回复 `"{}"` → 断言后续不再以 scoped 解析（要么显式兜底、要么一次干净回退）。

**F2 · 低（微边界，仅记录）**：`patch` 中 `source_structure_unit_ids` 为空的候选可通过 5067-5068 的"⊆授权集"检查（空集恒真），随后在 restore 闭包分支因"必须与授权 union 相交"（5320-5324）被静默丢弃——无注入、无单元丢失（单元仍须被其他候选覆盖，否则 raise）。若 wire Schema 允许空来源，则表现为静默忽略一条候选；后续 hydrate/gate 兜底。无需修，除非希望 merge 层显式拒绝空来源候选。

**F3 · 低（提示性，非缺陷）**：merge 层不校验 `source_span_ids` 与授权单元的一致性，仅后续 hydrate/完整来源门兜底（8497-8530 之后的既有门链）；这是分层设计的既有约定，若未来新增绕过 hydrate 的消费者需重新审视。

### D. 风险清单逐项裁决（对应提问）

- 借同来源扩越授权：否。写入域=既有误差闭包，且 merge/restore 双层强制 ⊆ 授权集（B1）。
- 外部候选/空处置/候选来源跨域注入：拒绝（extra/missing/cross 均 raise，测试 11498-11509）；空处置不可达（授权非空+集合相等）。
- 同源兄弟/已核时间被覆盖：否（B2、B3）。
- 无候选的非法 support 通过：否（B4，测试含 `allow_post_enrollment_reclassification=True` 反例）。
- 局部上下文不全/重复：否（B5）。
- 新 method 提供全包历史/丢预算/重置会话：全包历史否（B6）；预算按 11320 扣除；会话不变。**唯一残留为 F1 的状态清理**。
- 局部 Schema 与接受域一致：请求 response_format 由 `local_batch` 生成（transport 1506），接受域由 merge 强制=同一授权集；未逐字核对 `protocol_control_batch_response_format` 是否以 `owned_units` 为域（边界），但即便偏宽，merge 拒绝兜底、偏窄则失败即转"需要核对"，均 fail-closed。
- 有源未决/来源对应被改或伪造：否。merge 只替换授权单元处置与闭包内候选（B1/B2），其余对象原样，随后原 restore/hydrate/full source/gate/reviewer。

### E. 可否有界使用

可以。授权域未扩、破坏性删除有测试钉死、时间与兄弟保留经读证与测试、transport 不伪造历史；唯一建议随下次增量附带：F1 一行清理 + 1 个 schema-invalid 回归测试。不需要重构，也不需要更多模型/全量重跑。

### F. 未证边界与证据限制

- 无 diff，不能归因"某行本次新增"；但 `_merge_scoped_unit_repair`/`_restore_unchanged_time_operands`/`continue_scoped_unit_repair` 三者在既读面中仅本增量出现。
- 未读：`protocol_control_batch_response_format` 本体（schema 域）；`parse_protocol_control_agent_wire` 必填字段集；异常处理器 10494 复位块的完整列表（仅由标识符穷尽 grep 证明未含 scoped ids）；11595→11692 的 try 内其它分支调用点未逐行细读。
- 测试为合成输入（owner 声明），未运行；"前置首窗 8 失败为夹具/断言修正"未独立复核；真实后续 Job 未跑，故 F1 仅代码级可达，未实证。
- 同家族程序/上下文隔离审阅，非独立模型金标或临床批准；未输出临床原文。
