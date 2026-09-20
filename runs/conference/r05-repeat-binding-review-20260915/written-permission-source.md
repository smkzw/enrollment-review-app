全部核对完成。以下为第十八轮审阅报告。

# 会议输出: r05-repeat-binding-review-20260915 - evidence_single_object（第十八轮：书面许可实际消费与相邻报告）

## 输出

### 一、确定发现

**AK1（低——书面许可的语义覆盖边界：语义化许可文字不产生书面证人）**
`repeat_trigger_calculation.py:77-78` 与 `control_repeat_trigger_calculation.py:77` 的 `written_atom_ids` 判定仅认 `requires_professional_judgment` 原子。谓词族合同互斥（`rules.py:303-306`——语义命题不得与专业判断混用）：若方案中“研究者书面同意复查”的许可文字被解构为**语义命题**（无专业判断标记），该原子永不进 `written_atom_ids` → investigator_discretion 的 `written_permission` 恒 `repeat_written_permission_unverified`。方向保守（不会产出错误 TRUE——语义原子的 assertion_basis 配对不在 judgment_content 的 supported 内，`written_content_support` 交集恒空，`repeat_condition_selection.py:254-257`），但功能上系统性无法确认此类书面许可。最小修复（择一）：(a) 维持现状并在任务记录/设计文档声明该限制（解构层应把 investigator_discretion 的许可条件原子标记 `requires_professional_judgment`）；(b) 控制族判定扩展 `determination_mode == "investigator_judgment"`（该族两标记并存）。不建议对谓词语义原子直接扩展（会依赖不存在的内容核实通道）。

**AK2（低——报告把仅作时间佐证的日期事实列为“未采用”）**
`repeat_review_presentation.py:20-21,:42-44`：单组非数值采用时 `used_fact_ids` 只含值事实（`repeat_atom_calculation.py:148`），同组参与时间核验的 date_range 配对被列入 unselected 并标注“本次未采用，原件保留”——事实参与了核验却被呈现为未采用，措辞误导但不丢原文、不重算、不虚增采用。最小修复：unselected 的 reason 对“所在组已被采用、但该事实非结果值”的情形改为“仅作核对佐证，未作为结果值采用”（按组 adopted 状态区分）。

**其余重点挑战均核对通过**（file:line 证据）：
- **两族统一、不误解除保护**：`qualified_binding_selection.py:472-477,:489-494` 的 `written_content_verified_pair_ids` 构造已去除 predicate 族限定，命题与观察资格消费对控制族同样按 supported 解除 `professional_judgment_applicability_unverified`；解除**只**针对该项 pending——来源/时间/操作数失败仍由 `pair_direct_selection_rejection_reasons` 其余维度阻断（`qualified_observation_relation.py` 资格判定不变）；`professional_identities` 扩至控制族（`:495-499`）。supported 来自两族 judgment_content 的五项内容/归属/对象/节点/值忠实核实（`verify_qualified_content` 链），节点与对象核实经 `unique_source_match` 继承，无新增模型任务。
- **决定性分支追踪**（`repeat_permission_calculation.py`）：OR 仅收集 TRUE 分支 witness（`:21-22`）——数值独自满足的分支 witness 为空 → `usable=False` → UNKNOWN（`:43-46`）；AND 全真收集全部子 witness（每个子为必要条件，非“无关背书”，`:25`）；NOT 透传已知原子 witness、UNKNOWN 原子不产 witness（`:15-18,:28-29`）——不从缺记录制造许可；“明确书面否定”场景：`combine` 对 FALSE 的 witness 仍可非空（书面否定原子）→ written TRUE 而许可条件 truth FALSE——resolution 侧 `operands` 中 `permission`（原条件真值，`repeat_result_resolution.py:107-119`）与 `written_permission`（`:122-127`，取自已校验 `used/span ⊆ 许可条件计算` 的封存结果，缺省 UNKNOWN）**分列**，status 聚合取最严——原条件真值不被取代 ✓。
- **贯通与版本**：`written_permission` 字段在两族计算 dataclass（`repeat_trigger_calculation.py:25`/`control_repeat_trigger_calculation.py:26`），`asdict`→resolution `model_validate` 往返一致；resolution 校验 `condition.condition_id == scheme.permission_condition_id` 且书面结果的 facts/locators ⊆ 同一许可条件的实际采用原文；资格 v23（双 Literal 含 v23，授权历史集含 v22）、命题消费 v7、冻结计算 v27、发布 v9、观察消费沿用 v6——旧 v22 材料可读、无新方法批准（无真实调用路径），需新评测记录才可启用（fail-closed 不变）。辅助条件每个 target 范围继续复用已核实来源（`_evidence_scope` 未变）。
- **报告投影**：`repeat_review_presentation.py` 只读已保存的 `RepeatAtomEvaluation.resolution/numeric_result`，不重算；范围声明（`:10`）、数值明示“计算结果，不是新增的原始检查记录……未作四舍五入”（`:60-61`）、有理数以分子/分母呈现（`:54-57`）；`review_history.py:448-449,:588-590` 复用 notes/unselected 入口，未采用原件携带 locator_ids 保留。

### 二、待核风险（源码推导，未运行）

`review_history.py` 传入 presentation 的 `facts` 视图是否完备含 `date_range.lower_bound/source_text`、`polarity.value`、`locator_ids`（`:30-43` 逐字段依赖）——视图构造段本轮未逐行核对，若字段缺失将是运行时 KeyError（确定性错误，属源码可查范围，未及验证）。

### 三、保留的未完成/未知边界（与声明一致，未绕过）

观察排序与复查组合（`policy.selection` 保守拒绝不变）、无复查回退语义（missing→UNKNOWN）、书面许可内容对**语义命题化**许可文字的覆盖（AK1）、报告 API/UI 之外的新字段呈现广度——均未在本轮宣称完成。已知缺口仍单列报告（`:10`）。

### 四、结论

仅源码复核：两处低严重度确定发现（AK1 覆盖边界、AK2 措辞），核心链路（两族统一解除、决定性书面追踪、字段/哈希/版本贯通、只读报告）与声明一致，未发现错误解除控制族保护、空值变肯定或丢弃有效证据的路径。未运行任何验证；编译/推导不构成运行证据，集中测试按用户决定在完整构建后执行；本报告非临床或产品验收。
