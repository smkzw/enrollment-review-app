Trellis SessionStart 上下文已加载。开始同一来源恢复边界的记录用途字段只读审阅（基线 ec3ba1fb；上限 18 次源码读取；只读、不执行测试、不写文件；不把任务说明当正确性证明）。先建立新增点与消费者地图。

新增点已定位（`_RecordSemanticsRepair` 738-746、响应格式 1828-1831、选择器/合并/提示的 `field` 参数 6531-6653、Runner 抢救 10772-10780/选择 11476/提示 11666/分派 11817、transport `continue_record_semantics` 1770、新组成 `scoped-source-record-semantics-recovery/v1` execution.py:2122、消费者含 history_source_search_input 与 control_evaluation_spec:82）。并行读取契约、选择/合并函数体、模型与 Runner 关键区。

契约、选择器/合并（含 `field` 分支与逐字来源校核）、抢救块（含 atom 竞争位清空与 record 分支）、字段选择与预算已读出。补七处：`observation_repair_field` 全部写入点（陈旧态）、`RECORD_SEMANTICS_REPAIR_INVALID` 停止覆盖、选择+提示区、当前测试、transport 记录方法、两个真实消费者（18/18 用尽）。

Trellis SessionStart 上下文已加载。只读审阅完成（18/18 源码读取用尽；未运行测试、未写文件、未创建 Trellis 任务；不把任务说明当正确性证明）。以下为报告。

## 实际已读范围（18/18）

- `app/domain/contracts/record_semantics.py`：全文（字段 11-14；`validate_source` 16-24：非空、去重、`target_kind != event_history → direction 必须 unresolved`；`RECORD_SEMANTICS_GUIDANCE` 27-38）。
- `app/agents/protocol_control_deconstructor.py`：728-762（`_RecordSemanticsRepairItem` 738-742 仅 layer/group/atom/semantics；`_RecordSemanticsRepair` 745-746）；6490-6779（选择器 6527-6574，`field` 分支 6552-6554/6570-6572；合并载荷 6577-6629，record 逐字来源校核 6608-6611、写回 6623、错误码分支 6627；`_merge_observation_policy_repair` 6632-6647；`_invalid_scoped_observation_payload` 6650-6689，含 6671-6676 逐草案时间属性恢复；观察提示构造 6692-6723）；8420-8485（`observation_repair_field` 初值 8455；循环顶合并 8468-8476 传 `field`）；10720-10829（抢救块 10759-10783：观察分支 10763-10771、record 分支 10772-10783，两分支均清 `atom_repair_path` 10768/10779，record 置 `observation_repair_field` 10780）；11390-11509（预算子句 11406、失败文案 11413-11416、自增 11432-11445、`atom_only` 11446-11462、`observation_only` 含按字段取 reader 可调用性 11472-11479、candidate/复数 11497-11513）；11510-11699（**`scoped_unit_repair` 选择现含 `and not observation_only` 11587-11593**；record 提示分支 11659-11675）。另以 grep 实证：`observation_repair_field` 全部写入点（10580 复位为 observation_policy、10780 置 record）；`RECORD_SEMANTICS_REPAIR_INVALID` 仅 6627 与 11384（停止子句已扩展为 `{"OBSERVATION_REPAIR_INVALID","RECORD_SEMANTICS_REPAIR_INVALID"}`）；dispatch 读点 11817-11818；response format 1828-1831。
- `app/agents/protocol_control_agent_transport.py`：1750-1815（`continue_record_semantics` 1770-1783：会话门 1774-1775 接受 `_scoped_resume_contexts`、响应格式 1776、单条 user 消息 1778、CallError 包裹 1780-1782）。
- 测试：`tests/v2/protocols/test_slice58c_control_deconstructor.py` 11735-11849（`test_scoped_missing_policy_uses_field_reader_and_preserves_actual_proposal` 双参数化全貌）。
- 消费者：`app/services/history_source_search_input.py` 全文（`_eligible` 25-29、目标构造 47-57/74-78、scope 哈希 151-160）；`app/domain/contracts/control_evaluation_spec.py` 30-125（record_semantics 字段 44、证据包含 78-80、investigator_judgment 禁 not_required 81-83、`validate_control_atom_evaluation` 101-122 与明示注释 108）。
- `app/services/protocol_control_execution.py`：2122（新组成 `scoped-source-record-semantics-recovery/v1`，grep）。
- **未读**：deconstructor 10560-10720（抢救块前哨与 10580 上下文）、11360-11390（11384 停止子句全文）、11800-11860（dispatch 分支体）；`history_source_search_calculation.py`、`rules.py:410`、`protocol_deconstructor.py:2592` 等其余消费者（仅 grep 片段）；`_single_requirement_messages` 为早前轮次已读、本轮未重读；服务组成列表机制沿用早前轮次已读。

## 逐挑战结论

**1）错误位置分类是否过宽。** 选择器对 record 字段的判据是"全部错误的 location[7:9] == `("evaluation","record_semantics")`，任一越界即返回 `()`"（6552-6563、6570-6572），即精确到该字段子树；配合 6627-6628 的"唯一无效候选"前置，分类在**授权面上不过宽**（替换值还须过 RecordSemantics 合同 6588 与后续全门禁）。两点边界：其一，pydantic 在外层求值规格校验器上抛出的"记录用途须属于本求值规格逐字原文"与"研究者判断不得声明 not_required_by_source"（control_evaluation_spec.py 78-83）其 loc 落在 `evaluation` 而非 `record_semantics`，**不在此恢复集内**——这类回答会停止而非修复（fail-closed，属覆盖面而非越权）。其二，"不过宽"不等于"字段中立"：见反例 R1。

**2）record_obligation 被修成 not_required_by_source 的后门——可达。** 触发错误只涉及 `(target_kind, proposition_direction)` 规则（record_semantics.py:22-23），但合并载荷对 record 字段**没有既有值保持规则**（对照观察字段的 scope-only 规则 6599-6604 缺失），写回整个 semantics（6623）。因此模型可返回合法组合把与错误无关的 `record_obligation` 改成 `not_required_by_source`，宿主无法区分。下游真实消费者按此取值：`history_source_search_input._eligible`（25-29）以 `event_history + not_required_by_source + direction != unresolved`（且非 professional/future/complex）把条件选入病史来源检索 scope，并把 semantics 冻结进目标与哈希（47-57、151-160）；外层门禁只在 `investigator_judgment` 模式禁止该组合（81-83）。即"Schema 通过 ≠ 记录义务已核实"，且一次与错误无关的降级会改变后续产品行为。最小修复：在合并载荷 record 分支要求 `proposed["record_obligation"] == existing.get("record_obligation")`（该错误类从不牵涉 record_obligation，可确定性冻结；仅一行，不加框架）。

**3）引用/授权范围。** 范围（处置精确等于授权单元、草案来源与 span 限于授权闭包、跨闭包旧候选拒绝、兄弟保留）沿用 6655-6689 的既定检查，充分。引用校核在合并层是"每个 propose 摘录必须是所在**原子** source_excerpts 之一的子串"（6608-6611），而外层合同要求记录用途摘录属于**求值规格** source_excerpts 的子串（control_evaluation_spec.py 78-80）。两层模板不一致会产生可达反例 R2（见下）。合同自身另有 min_length=1、去重、非空（record_semantics.py:14、18-21）——无 span 字段，故"同原子逐字"是引用上限的正确粒度。

**4）索引与兄弟。** 与既有机制一致：唯一无效草案、`index = len(siblings) + 无效序位`（6683），paths 与字段合并用同一 `merged`（6687、8468-8476），兄弟取自 previous 不相交集（6680-6682），恢复期闭包重冻结；测试断言采用内容=实际提案+字段值（11836-11838）、兄弟与处置原样（11839-11842）。未见索引或兄弟问题。

**5）另一 reader 抢先。** 三处都已闭合：原子 reader 曾抢先（首版 6 失败）——抢救成功分支显式 `atom_repair_path = None`（10768、10779），且 `atom_only` 在 observation 前判定（11446-11450）；scoped reader 竞争——`scoped_unit_repair` 选择已加 `and not observation_only`（11589），补救轮不会重入 scoped；观察 vs record——观察抢救用消息判据先行，record 错误不匹配后落入 record 分支（10763-10783），混合错误两分支皆 `()` → 停止。其余通道（time/scope/future/calendar）由当轮错误推导，记录用途错误不命中。

**6）失败/缺能力是否退整候选。** 否，逐类闭合：坏 JSON/混合/越域 → 两分支均 None → `failed_scoped_unit_repair` 保留 → 停止（11406-11416）；缺对应 reader → 分支被可调用性门跳过（10762、10772、11476-11478）→ 同停止；字段回复非法 → 11384 停止子句覆盖双码（含 `RECORD_SEMANTICS_REPAIR_INVALID`）→ 需要核对，不再第三调用；传输故障 → transport_failed 返回；预算沿既有 `repairs` 自增（11445），无清零/无新计数器；第二门拒绝（second_gate）在 `max=2` 下由预算子句停止，即使额度更大也会被候选通道排除（闭包标志）+ transport 无历史拒绝兜底。测试以 `requests` 物理计数与 `_histories=={}`（11821、11823）钉住以上。

**7）消费者真实含义核对。** 已读两个真实消费者：`control_evaluation_spec.py` 的机械核对=包含关系与模式一致性（78-83、101-122），文件自述"Verify source containment only; it does not prove semantic fidelity"（108）；`history_source_search_input.py` 用 semantics 做检索资格与冻结输入（25-29 等）。即现有消费者**不做记录义务的真伪核对**，Schema/门禁通过不能等同于"记录义务已核实"；本次审阅也不主张该点被解决。

## 可达反例与最小修复

- **R1（授权缺口，可达）**：模型返回 `{target_kind:"event_history", record_obligation:"not_required_by_source", proposition_direction:"event_present", source_excerpts⊆本原子}`，仅改动与错误无关的 record_obligation 即通过合并与全门禁；随后该条件可能进入病史检索 scope（消费者 25-29）。修复：record 分支冻结 `record_obligation`（见 2）。
- **R2（模板不一致，可达、fail-closed）**：当草案的求值规格摘录是原子摘录的真子集时，合并按原子层放行某引用（6608-6611），但 78-80 的外层规则会拒绝 → 合并后整线解析失败 → 观察状态未清（解析异常先于 8554 区清理块）→ 以同 paths 再问一轮字段 reader，直至预算停止；不会采用错值，但多一次调用并停在需要核对。修复：合并的引用校核改用求值规格自身的 `source_span_ids/source_excerpts`（或与原子层取交集），一行级改动；并补一条"求值摘录为子集"的测试故障。
- **R3（覆盖面边界，非缺陷）**：仅 RecordSemantics 自身校验器错误（非空/去重/方向规则）可进入本恢复；外层关于该字段的错误（78-83）不进入。建议在文档/回执中显式声明该边界，不建议放宽选择器。
- **旁注（微小）**：6591 的位置不符文案仍用"观察采用说明"字样，record 分支下易误读，可顺手改为按字段措辞（纯文案）。

前一版的 R1（抢救路径缺"复用已核时间属性"）在本基线已修复：6671-6676 在候选校验前对来源匹配草案执行 `_restore_unchanged_time_operands`；`observation_repair_field` 陈旧态亦有每轮异常入口复位（10580；其上下文未在本轮读取窗口内）。

## 反证与局限

可能推翻上述的证据：11384 子句与 10580 复位的完整上下文未读（仅 grep 行）；11800-11860 dispatch 分支体未读（会话一致性检查与响应处理依早前版本+测试断言推断）；`history_source_search_calculation.py`、`rules.py:410`、`protocol_deconstructor.py:2592` 等其余消费者未读，R1 的下游影响描述限于已读消费者；组成串 2122 仅得自 grep。我未运行测试（87pass 为用户报告）；未接触临床原答/原件/env/DB；真实产品尚未实跑本恢复（用户陈述）。跨 Job 区分：服务仍只保存/重载合法 `pending_author_wire`（早前轮次已读 7508-7515、2807-2808、4639-4644），本增量只在同次运行内恢复字段；新 Job 会沿合法入口重新生成一次局部提案——该限制未被本增量解决，也未用伪造会话/回执绕过（transport 门 1774、测试 `_histories=={}` 11821）。本审阅不是模型独立金标、研究者判断或医学批准。

本轮为只读审阅、未创建 Trellis 任务；如需把 R1/R2 登记为任务或进入计划阶段，请告知。
