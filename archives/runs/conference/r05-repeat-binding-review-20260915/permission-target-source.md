全部核对完成。以下为第十九轮审阅报告。

# 会议 Output: r05-repeat-binding-review-20260915 - evidence_single_object（第十九轮：单次复查许可归属）

## 输出

### 一、确定发现

**AN1（低——AK2 维持未修，且本轮沿实际 `fact IDs` 证实其路径成立）**
`repeat_review_presentation.py` 无佐证区分修订（全文件无“佐证”类标记）。实际路径：`repeat_atom_calculation.py:148-149` 在 `fact_result` 内将 `value.used_fact_ids` 设为**单个值事实**；非语义分支的选择清单（`_select_facts_for_identity`）`fact_ids` 只含值事实、时间佐证经 `pair_ids` 扩展不进 `ids`——而图采集组的 `fact_ids` 来自成员配对（含 `date_range` 属性配对）。当组内存在独立日期事实时，它参与时间核验却被 `presentation :42-44` 列为“本次未采用，原件保留”。最小修复（维持第十八轮建议）：对“所在组已采用（`group fact_ids ⊆ selected` 不成立但组结果被采用）且该事实非结果值”的未采用条目，将 `reason` 改为“仅作核对佐证，未作为结果值采用”——按组采用状态区分，不虚增采用、不丢原件。

**其余分派检查项均核对通过，未发现新确定缺陷**：

- **target_observation 语义（经双读辅助对应，非日期邻近）**：`repeat_condition_selection.py:16-17` 参照即目标复查组；`_evidence_scope:62-70` 许可证据须经双路同意的辅助关联且**归属组集合恰等于目标组**才入选，`acquisition_scope_check="verified"` 仅在此路径设置（`:70`）——归属完全来自辅助关联，无任何日期/同值推断。
- **written 判定四重条件**：`repeat_trigger_calculation.py:77-81`（控制族 `:75-78` 同构）＝`requires_professional_judgment` ＋ `written_permission_scoped_to_target`（`repeat_permission_calculation.py:6-12`：同身份证据范围唯一、`role=="target_observation"`、`reference_group_id == repeat_group_id`、`check=="verified"`）＋ outcome usable ＋ `written_content_support` 非空——external_context 原子的 `check=="not_applicable_external_context"` 恒不满足 → **不再充当逐次书面许可凭证** ✓。
- **trigger 不自证**：`repeat_condition_selection.py:211-213`——非许可条件的 target 角色被置 None → `repeat_condition_evidence_role_unverified` → 该原子强制 UNKNOWN ✓。
- **AK1 提取校验已补（核对确认，不重复建议）**：官方 `protocol_deconstructor.py:2557-2569`（investigator_discretion 的许可条件树递归须含 `requires_professional_judgment` 原子，无条件引用亦拒绝）；控制族 `protocol_control_deconstructor.py:737`（wire 校验）＋提示 `:1295-1296`（须 `requires_professional_judgment=true` 且 `determination_mode=investigator_judgment`）；双侧提示明确“不因许可日期接近而推断适用，不把单次许可扩展到其他复查”（官方 `:437-438`）。
- **原布尔逻辑保留**：`written_permission_result` 沿原表达式树递归（`:40-51`）；resolution 的 `operands` 中 `permission`（原条件真值）与 `written_permission` 分列（第十八轮结构未变），许可 FALSE 不被书面核实 TRUE 覆盖。
- **六个关键反例逐一核过**：(1) 首次许可复用于第二次——第二次 row 的归属==第二组要求下首次证据 `source_not_found`/归属不符 → unverified，**不复用**；(2) 两次同值/同日——归属不经值/日期，无影响；(3) 书面否定——`combine` 反转后 witness 保留，written TRUE 而许可 truth FALSE，operands 分列取最严；(4) 数字 OR 真＋研究者分支假——ANY 无 TRUE → FALSE＋witness（仅书面原子）→ 许可 FALSE（不放行）、written 有据；(5) 辅助来源未对应——`len(assignments.get(key,()))!=1` → `repeat_condition_correspondence_unverified`（`:66-67`）；(6) 多归属——同式拒绝 ✓。
- **版本/历史**：资格算法 v24（常量与 Literal/历史集三处含 v23、v24）、官方 `wire-v11`、控制 `wire-v16`/`prompt-v2.13`；v23 历史保留、不补改；无新方法批准、无新增模型任务（许可证据经既有双读观察任务与辅助关联产生）。

### 二、声明的功能待办（不视为缺陷、不声称已支持）

覆盖多次的许可（同一书面同意覆盖 N 次复查）：当前 target_observation 语义按单次归属判定，此类许可对其余次复查保守 UNKNOWN——与分派声明一致；不建议复制许可到每次或手工补临床答案。

### 三、未执行的验证

全程只读，未运行任何代码/测试/构造/服务——以上均为源码推导（含 AK2 的 fact-ID 路径证明）。控制族 written 判定的前置行（`control_repeat_trigger_calculation.py:76`）与 resolution written 校验段沿第十八轮已核结构比对，未逐字重读全文。编译通过不构成运行证据；集中测试按用户决定在完整构建后执行；本报告非运行或临床验收。
