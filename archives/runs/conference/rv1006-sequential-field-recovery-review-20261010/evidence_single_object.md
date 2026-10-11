Trellis SessionStart ✓

I'll start by reading the assigned files and the specific regions called out.

I've completed the assigned review within the read budget (initial read set fully, plus 7 targeted reads; 2 operations left unused rather than overrunning). Report follows.

# Conference Output: rv1006-sequential-field-recovery-review-20261010 - evidence_single_object

## Output

### 0. 审阅范围与证据状态

**实际读取（全部只读）：**

| # | 目标 | 结果 |
|---|---|---|
| 1 | `app/domain/contracts/control_evaluation_spec.py`（全 179 行） | 完整读取 |
| 2 | `app/agents/protocol_control_deconstructor.py` 6440-6579 | 完整读取 |
| 3 | 同上 6700-6859（`_invalid_time_operand_paths`、`_build_time_operand_repair_prompt`、`_merge_time_operand_repair_payload`、`_merge_time_operand_repair`） | 完整读取 |
| 4 | 同上 10790-11069（多候选聚焦修订分支全貌） | 完整读取 |
| 5 | 同上 718-767（`_TimeOperandRepair`/`_ObservationPolicyRepair` 模型） | 完整读取 |
| 6 | 同上 1205-1264（`_normalize_absent_time_bound_flags`、`_preserve_unstated_observation_selection`） | 完整读取 |
| 7-8 | `app/agents/protocol_control_agent_transport.py` 1700-1799（`continue_observation_policies` / `continue_time_operands` 真实适配器） | 完整读取 |
| 9-10 | `tests/.../test_slice58c_control_deconstructor.py` 10105-10292、10680-10759 | 完整读取 |
| 11 | 模块内 grep：`_invalid_observation_policy_paths` 定义位置 6420、`_max_schema_repairs` 约 13 个调用点、`ProtocolControlAgentWireObligationAtom` 在 642、`time_purpose` 线格式在 1066 | 命中清单 |

**明确未取证、需在连接测试/产品恢复中验证的项：**
- 未运行任何测试（本角色不要求）。
- 未读取 `_WireModel` 的 `extra` 策略全文（仅确认 `_TimeOperandRepairItem` 仅声明 3 字段；冗余键是否被拒未直接取证）。
- 未读取 `ProtocolControlAgentWireObligationAtom` 642-720 全文，因此"日期修订提示中原子是否携带 `evaluation.time_purpose`"只做了签名级（1066 行）判断，未做序列化实证。
- 未核对 HEAD `fb1872…` 与工作区当前补丁的 diff；本文按**当前工作区实际源码**评估（题目要求）。
- 本审阅与产品同为 DeepSeek 家族，不构成独立模型族复核。

---

### 1. 该补丁的机制声明与静态符合性

**声明：** 在既有 ≥2 无效候选分支中，先只改入授权观察政策；候选单独校验暴露被遮蔽的缺失日期操作数后，用**既有**有界日期工具补一个枚举属性；两处共用同一 `repairs` 计数、同一 `session_id`、既有合并器；随后校验候选与整线；不得新增接口、不得改预算、不得放宽发布。

**静态符合性：逐步核对结果**

| 约束 | 代码位 | 判定 |
|---|---|---|
| 只入授权政策 | `_merge_observation_policy_repair_payload` 6480-6507：位置集合必须与 `paths` 全等（6478）；已有 policy 仅允许改 `scope`（6486-6491）；来源必须属于本原子直引（6492-6505） | **成立** |
| 日期路径同源同会话 | 10880 `date_reader = transport.continue_time_operands`；10898-10901 显式传 `session_id=session_id`；10902-10903 响应会话必须相同 | **成立** |
| 共用同一计数器 | 10896 `repairs += 1`（政策侧 10851 已 +1）；无任何重置语句在 10830-11042 内 | **成立** |
| 共用既有日期合并器 | 10904 复用 `_merge_time_operand_repair_payload`（6791-6822），无新函数、无新参数 | **成立** |
| 预算耗尽不得再调模型 | 10891-10895：日期预门禁在 `date_reader(...)` 之前，超限即抛 `REPAIR_BUDGET_EXHAUSTED`（10893）且置 `focused_response=None`；政策侧 10846-10850 同理 | **成立** |
| 整线仍过原发布门禁 | 11003 `parse_protocol_control_agent_wire` + 外层 `output_validator`；10907-10909 与 10991-10993 仅做候选级结构校验，不做接受 | **成立**（测试 10251-10263 证实 `输出验证器` 恰消费 1 次） |

---

### 2. 被质疑面逐项裁定

#### ① 禁用错误能否进入日期路径 —— **不成立（有硬证据）**
`_invalid_time_operand_paths`（6728-6762）为**全量否决**选择器：任一 error 的 `type != "control_time_operand_missing"` 即整体返回 `()`（6743-6753），最后 6755-6761 再回基线复核 `time_constraint` 非空且 `time_operand_attribute` 为空，否则清零。测试 `test_candidate_relative_policy_selector_rejects_other_errors`（10279-10292）以 `title=""` 混合错误实证空选择。10881-10882 在空选择或无 reader 时抛回原 `candidate_error`，**不降级为猜测、不退回整候选**。

#### ② 触发前置性：政策错误是否必然先于日期错误 —— **成立（关键承重点，已静态证明）**
`validate_control_atom_evaluation` 在 `control_evaluation_spec.py` 的执行顺序为：政策存在性（132-134，抛"求值规格须说明观察选择规则"）→ 政策来源归属（135-139）→ `control_time_operand_missing`（155-160）。同一原子同时缺政策与日期属性时，**政策错误确定性先报**。这证明 10841-10843 的 `policy_paths` 在测试场景下非空，且补丁的前提（"先补政策、后暴露日期"）与生产错误顺序一致，而非仅测试环境巧合。

#### ③ 兄弟/来源/阈值/时间政策能否被改动 —— **成立但有一处需披露的既有副作用**
日期合并器逐项复核 `time_constraint is not None` 且 `time_operand_attribute is None`（6809-6811），只写 `evaluation["time_operand_attribute"]`（6812）；`_TimeOperandRepairItem` 仅 3 字段（750-753），`_ObservationPolicyRepair` 只写 policy（6506）。**阈值、方向、锚点、期限、来源均无写路径。**

**需披露点（既有代码、非本补丁新增）：** 6813 `_normalize_absent_time_bound_flags(candidate)` 的作用域是**整候选**（1213-1229 递归所有 dict），并非目标原子。对已通过校验的兄弟原子，`both bound is None → bound_inclusive=True` 是语义空操作，且"先前有效"保证只有语义无效组合才可能被改写；测试 10264 的 `partial_wire == expected` 全等断言会暴露任何非预期改动。但严格说，"仅授权字段可动"在实现口径上靠的是**空操作论证**，不是作用域收窄。**最小补救（可选）：** 把 6813 的调用参数从 `candidate` 改为目标 `atom`，或将归一化循环限定在 `paths` 内；不新框架、不改语义。

#### ④ 上一次响应是否被误记到失败日期调用名下 —— **不成立（有硬证据）**
三条记账路径分离清晰：
- 政策响应先以 `schema_invalid` + 自身 sha256/chars/全文入账（10883-10890），且 `issues` 携带政策后候选校验的真实错误；
- 失败前显式 `focused_response = None`（10897），日期调用前再次置空（10883 分支内 10892 亦置空），因此 11004 的异常处理器（11008-11027）在日期通道失败时只能拿到**日期响应**或 `None`；
- 测试断言 `attempts[1].raw_output_text is not None`（10266）与 transport 失败时 `attempts[-1].raw_output_text is None` 而 `attempts[1]` 非空（10274-10276）。

**诚实标注一句**：政策被 `schema_invalid` 记账而其后**被接受**（10867 合并成功）是设计选择——`attempts[1].outcome == "schema_invalid"` 在成功路径同样成立（10265）。这是"字段级响应在整候选未过前不视为已接受"的一致口径，不是错记；但对流水读者存在误读空间，建议在 `issues` 文案上保持现有"仅补入授权字段，整批仍须通过原发布门禁"（10916）即可，无需改动。

#### ⑤ 未决日期能否被接受 —— **不成立**
6801-6804：任一 `attribute == "unresolved"` 即抛 `TIME_OPERAND_UNRESOLVED`。测试 `failure="unresolved"` 断言 `需要核对`、`final_output is None`、`consumers == []`（10268-10270）。位置错位（`atom_index=1`）同理被 6799 全等集合校验拒绝。

#### ⑥ 预算耗尽仍能调模型 —— **不成立**
两处前置门禁（10846、10891）都在对应 reader 调用之前；`failure="budget"`（`max_schema_repairs=1`）断言 `date_calls == 0`、末次 `error_classes == ["REPAIR_BUDGET_EXHAUSTED"]`（10271-10273）。另外，115 行未在预算耗尽后残留 `focused_response`（10892 先置 `None`），避免把未获批的响应文本挂到预算错误上。

---

### 3. 最高影响项：我能找到的最强残余缺陷与不确定点

按影响排序，全部标注证据等级。

#### D1（已证实的可达分支，影响中等）— 政策修订成功后候选的另一非日期错误会**吞掉该候选本轮的全部字段级修复**，但不产生错误接受
路径：10852 `if policy_paths:` → 政策合并成功（10867）→ 候选校验（10871）暴露非日期类错误 → `date_paths` 为空（6743 全量否决）→ 10882 `raise candidate_error from cause` → 外层 11004 捕获 → **立即返回"需要核对"（11028-11036），不再尝试该分支内的任何其他修复**。
判定：这是**失败关闭**，不违反任何硬边界（不猜测、不放宽、不越权），但会让"政策已补好"的这一轮成果连同后续候选全部停在 partial_wire。与"最小必要修复"目标一致吗？一致——但请在连接的恢复实测中确认：真实恢复场景中，政策补全后最常见的"次生错误"是否恰好是日期缺失（本题场景），若是，则此分支基本不被触发；若不是，则此路径会把多候选串行修复的成功率压回 10845 那条老路。**无需代码改动；需要一条可观测性证据。** 建议在 `issues` 中保留 `candidate_error` 原文（已由 10876 `_validation_error_summary(cause)` 提供），足够定位。

#### D2（未证实的顾虑，我明确标为 unproved）— 10845 `raise ValueError("候选已有效，不能再次请求修订")` 在补丁后仍保留
在"候选单独有效、整线因跨候选规则失败"的场景，该分支会落到既有整候选重写（10919-11002）。该路径**不在本补丁授权范围内**，但它与我刚审的字段级路径共享同一 `repairs` 预算；我未能静态排除"它在本轮次里先于字段级路径消耗预算"的排列（需要运行才能构造）。**安全临时路径：** 保持现状不动；在连接测试里增加一条"政策+日期候选与另一跨候选无效候选混合"的用例，观察是否出现预算被整候选重写抢占。这属于"未证明的关切"，不建议在无实证前改动。

#### D3（未证实的顾虑）— 日期提示的原子可见性问题（只做了签名级判断）
`_build_time_operand_repair_prompt`（6765-6788）把 `candidate["obligation_expression"]…atoms[i]` 整对象内联。我确认线格式存在独立 `time_purpose: Literal["not_applicable","unresolved"] | None`（1066），但**未实证**该字段是否出现在原子的内联 JSON 中。若出现，模型会看到原子的 `time_purpose == "unresolved"` 而 `time_operand_attribute` 存在——两者语义不冲突（前者是"约束用途未定"，后者是"操作数属性"），但可能诱导模型输出 `record_time` 而不是 `date_range`。**若值确为 "unresolved" 被展示且真实恢复中出现错误属性选择**，最小补救是把提示中该键剔除或改写为中性文案（不改校验、不改工具）。请 owner 在连接测试里用一次真实/合成日期调用 dump 一次提示原文即可定论。这是我能找到的、对**输出正确性**影响最直接的开放点。

#### D4（设计告知项，非缺陷）— 政策响应被记账为 `schema_invalid` 后其内容被接受
见 §2④。测试（10265）显式断言该行为，属有意口径。仅提示：若下游对 `attempts` 做"schema_invalid ⇒ 该输出未被采纳"的推断，会出现不一致解读。建议保持现状但留意流水消费方。

---

### 4. 我认为补丁是对的、且值得计入回归锚的点

1. **选择器全量否决语义**（6743 首错即空、6755 基线复核）——这是"禁用错误不能进日期路径"的硬保证，比"收集所有匹配路径"更安全。
2. **政策→日期两次 `repairs += 1`**（10851、10896）与两道预算前置门禁（10846、10891）——共享计数的实现与文档口径（7138-7143："总额度共享"）一致。
3. **响应归因链**（10883→10897→10898→11004）——`focused_response` 在每个模型调用前被置空，使 11004 的 `raw_output_*` 归因天然只能指向"当前失败调用"，无需额外状态。
4. **测试 `test_multi_candidate_policy_then_date_repair_keeps_frozen_scope_and_budget`** 的 7 个参数（含 `budget`/`missing_reader`/`session`/`position`/`unresolved`/`transport`）覆盖了"不得扩大调用、不得换会话、不得错位、不得接受未决、不得越预算"五条边界；`assert initial == snapshot` 与 `partial_wire == expected` 同时冻结了输入与输出。

---

### 5. 对 Codex 的决策点与有界问题

**决策点 1（需你裁定）：** 是否要求本补丁附带 D1 的**一条**可观测性断言——"政策补全后出现非日期次生错误时，结果必须是 `需要核对` 且 `attempts` 保留该次生错误原文"，而不新增重试。我倾向**要求**：它零成本、只加断言、把 D1 从"推理"升级为"回归锚"。

**决策点 2：** D3 是否允许在 owner 的连接测试中先 dump 一次真实日期提示（只读、不产出临床结论），以便在**不**修改源码的前提下关闭该不确定性。我建议允许——这是唯一能证明"提示不含误导字段"的方法，成本一次调用。

**有界问题（若答案改变结论请回交）：**
- Q1：`_WireModel` 是否 `extra="forbid"`？若否，`_TimeOperandRepair` 能容忍冗余键，D2 的"位置全等"仍是防线，但我对"多余字段被静默忽略"的判定需修正。**为什么重要**：影响 6799 是否为充分防线。**无答案时的安全临时路径**：按 forbid 处理，因为在位置全等之上还有 6809-6811 的逐项复核，即使容错也不会放宽语义。
- Q2：D3 的提示实证结果。**安全临时路径**：若无法立即取证，本次窗口按现状使用，但在 `implement.md` 记录该开放点，不声称"提示完整"。

**关于角色边界的诚实声明：** 我未运行测试、未接触产品/临床数据、未做浏览器或发布门禁验证；以上 `成立/不成立` 均为静态源码证据级判断。临床接受、真实恢复与最终发布门禁仍由你所有。

**最高影响的单一反对意见（总结）：** 补丁的**日期路径本身**是安全的（选择器全量否决 + 逐项复核 + 预算前置），真正的风险不在"能修坏"，而在"修不动"——D1 表明政策成功后一旦暴露非日期次生错误，多候选分支会整轮放弃（失败关闭但零推进）。请勿为此扩大重试或新增通用框架；正确的响应是**一条断言 + 一条提示取证**，其余交给 owner 的连接恢复实测。
