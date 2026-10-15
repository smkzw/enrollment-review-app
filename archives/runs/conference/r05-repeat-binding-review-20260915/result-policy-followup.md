全部核对完成。以下为第六轮审阅报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第六轮：复查结果处理——population 合同、结果组选择器、观察资格书面判断接线）

## Output

### 一、发现（按严重度）

**S1（中——专业判断类复查所有者的观察资格仍系统性依赖书面判断授权；口径一致化后的操作前提，非新矛盾）**
`app/services/qualified_binding_selection.py:484-487` 现按与主选择路径（:497-501）**完全同口径**构造 `written_content_verified_pair_ids`（`supported` 或 date_range+`content_sources`，限谓词族），传入 `qualified_observation_relation.py:77` 消解 `professional_judgment_applicability_unverified`。但两者都只在 `authorization.judgment_content` 在场时非空（:412-420）：谓词族授权未附书面判断任务时，`requires_professional_judgment` 的复查所有者位置在观察图中全部进 `source_unresolved`。上一轮 P1 的口径偏差已消除（同进退），转为接线前提：此类方案的正式发布须同时提供判断任务，否则观察证据系统性缺失。缺失书面判断的行为是**保留 unresolved 原因**（`qualified_observation_relation.py:86-87`），不是 satisfied，也不是强制交互中断——符合分派要求。

**S2（低——`retain_initial` 同样被 `scope_complete` 拦截）**
`app/domain/repeat_result_selection.py:38-39` 的范围完整性检查位于所有 `result_use` 分派之前，"保留初查结果"在供给范围不完整时也拒绝。语义上可辩护（初查角色本身依赖范围完整——未供给的更早记录可能推翻 initial 归属），方向保守、无不安全肯定；标注为有意口径供所有者确认。

**S3（备注——组合运算前提未在本层校验）**
`:67-74` combine 分支返回 `combination=scheme.result_combine` 但不校验组内值可加性（sum/mean 需数值、极性/单位一致）。与 docstring "without inventing values"（:1）一致——纯选择器前提，属未来消费者职责，非缺陷。

**确认非缺陷的点**（源码逐项核过）：
- **历史序列化保持**：`repeat_scheme.py:70-78` 非 v3 pop `result_population`、v1 继续 pop 三字段——v1/v2 字节与哈希域不变；非 v3 带值构造拒绝（:85-86）。
- **显式合并总体与操作**：v3 合同 `(result_use=="combine") != (result_population is not None)` 双向拒绝（:87-89）；combine+三层 unresolved 可保存（:97 只约束 combine↔result_combine），选择器对 population/combine 的 unresolved 给出区分原因码（:68-71）——合同允许保存未核实、选择器保守拒绝，分层一致。提示双侧补齐：谓词（`protocol_deconstructor.py:429-432`）、控制（`protocol_control_deconstructor.py:1272-1275`，含"非combine填null，不默认纳入初查或漏掉初查"）。
- **不猜日期**：选择器的 initial/repeat 归属来自双路同意的原文 origins（:35-37），"最后"由图回指闭包判定（:63-66），全程无日期推断；分叉/并列"最后"→ `repeat_last_observation_unverified`，不挑（:64-66）。
- **不挑有利结果**：`use_single_repeat` 恰一组才选（:60-62）；combine 只按原文声明操作与总体（:67-74）；其余 result_use → `repeat_result_use_unverified`（:75）。
- **不重复计数采集**：输入域是 acquisition 组 id（同次采集已在图内合并），`repeat_group_ids` 去重/包含校验（:29-32），初查不得混入复查集（:30）。
- **防篡改/错配**：图哈希重算先于一切读取（:25-27），缺键/缺 graph_sha256 均落 ValueError；祖先闭包限定 scope 且必含初查（:53-55）。
- **纯选择器 vs 采用**：`replacement_authorized` 恒 False（:13，init=False）；docstring :20-24 列 caller 前提（scope、来源资格、许可、触发、时间窗）。**无产品调用者**（rg 全库仅定义文件自身）。
- **版本绑定**：wire schema const `repeat-scheme/v3`（谓词 :665、控制 :1178）+ wire 校验拒绝旧版（谓词 :2148"不能沿用旧规格"；控制 :473-475/:551-553）；控制链版本升级为执行 v11（`protocol_control_execution.py:115`）、wire v13、prompt 2.9、gate v13——旧响应不能冒充新方法。

### 二、剩余集成需求（已声明的待办，本轮不扩围实现）

1. `select_repeat_result_groups` 尚无调用者——结果组选择未接入任何采用链；`RepeatResultSelection.selected_group_ids/combination` 的消费者（数值组合执行器：单位、极性、sum/mean 语义、`all/any` 布尔化）不存在。
2. 完整复查判定链未串联：许可（permission/investigator_discretion 的书面判断）、触发条件计算（`RepeatTriggerCalculation`/`ControlRepeatTriggerCalculation`）、次数（`evaluate_repeat_count`）、期限（`time_limit` 的 reference 选锚）、结果采用（本选择器）五段各自独立，无一消费者把它们组合成正式结论。
3. 结果采用路径的方法评测与授权（类比 `observation_relationship_fidelity`）不存在。
4. `use_last_repeat` 的结构序与时间序一致性依赖 `scope_complete` 与图的回指完备——这两项前提的运行时证明方式（判断搜索/覆盖）尚未与选择器对接。
5. S1 的操作前提：含专业判断类复查所有者的方案，正式发布需同时提供书面判断任务，否则观察证据将整体保留 unresolved。

### 三、未验证部分

- 全程只读，未运行代码/构造/测试/模型/浏览器；全部结论为源码推导。
- `select_repeat_result_groups` 的祖先闭包与 use_last 判定的行为推演（含环、分叉）为图方向语义论证，未构造数据实证；环图已被 `structural_reasons` 前置拦截（:33-34）。
- 谓词 wire `DNF_WIRE_VERSION = "dnf-v8"` 的历史升级序列未追溯（本轮只需确认 const v3 强制在位）。
- 最终入排对带复查方案条件保持 UNKNOWN（`repeat_relation_unverified` 链无变化）；本报告为有界增量源码审阅，无临床或整产品验收声明；测试实现按用户决定推迟，不在本轮建议。
