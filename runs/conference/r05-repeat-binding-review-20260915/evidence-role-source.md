全部核对完成。以下为第十一轮审阅报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第十一轮：逐原子复查证据角色的实现审阅）

## Output

### 一、实际缺陷（均为低严重度；未发现中/高）

**Y1（低——持久层不重申角色完整性）**
wire 层强制每原子一条（官方 `protocol_deconstructor.py:2538-2541` 与控制 `protocol_control_deconstructor.py:699-706` 均 `require_complete=True`），但持久合同只校验键域：`rules.py:440`（`validate_repeat_evidence_roles(roles, identifiers)` 无 require_complete）与 `protocol_controls.py:1247-1252`/`:1226-1232` 同。经解构 wire 进入的材料恒完整，故现路径无实际缺口；手工/异常构造的部分映射可在合同层通过。最小修复：`RepeatTriggerCondition.validate_nonrecursive_condition` 与 `ControlRepeatTrigger.validate_role_identities` 增加 `require_complete=True` 复核（或由发布 gate 复查）。

**Y2（极低——多所有者闭包的正确性依赖来源交集非空）**
`rules.py:464-468`：同一条件被多个所有者 scheme 引用时，角色摘录须逐字属于**每个**所有者的 `source_excerpts`——语义严格正确，但若两个所有者来源片段不重叠，解构会在组件校验时拒绝（fail-closed 而非数据错误）。行为可接受，标注供所有者知悉。

### 二、已核对项（file:line 证据）

- **角色合同**（`repeat_scheme.py`）：`RepeatEvidenceRole`（`:11-21`——非 unresolved 必须带逐字 `source_excerpts`，"不能由期限参照推断"，即不从 `time_limit.reference` 默认）；`validate_repeat_evidence_roles`（`:24-31`——键 ⊆ 条件谓词防未知引用 + 摘录闭包）；`RepeatEvidenceRoleReference`（`:34-37` 位置引用）；`resolve_repeat_evidence_roles`（`:40-52`——越界拒绝、同原子重复引用拒绝、`require_complete` 强制每原子一条含显式 unresolved）。
- **官方侧**（`rules.py`/`protocol_deconstructor.py`）：`RepeatTriggerCondition.predicate_evidence_roles`（`:427`）空省略序列化（`:432-433`，历史字节保持）；组件级闭包对**每个所属 RepeatScheme** 复核（`:459-468`）；wire 键形态严格（`protocol_deconstructor.py:2525`）、`require_complete=True`（`:2540`）；schema 内联全字段 required（`_inline_required_contract_schema:691-692`——unresolved 也须显式空 `source_excerpts` 数组）；提示明确 existence/scalar/set 原子顺序（`:432-433`）、四角色与逐字来源（`:433-434`）、"初查值、前次复查值与外部用药/许可背景须分开标明，不把整棵混合条件树套同一范围""未明使用unresolved，不以本次复查结果证明自身触发"（`:435-437`）——无整树过滤、无 target 角色、无 unresolved 自动回退；**水合谓词 ID 重映射同步重映射角色键**（`:2990-2993`，时序在条件表达式重映射循环之后，remap 表全覆盖）。
- **控制侧**（`protocol_controls.py`）：草稿 `evidence_roles` 位置引用（`:1217`，空省略 `:1222-1223`）以 "i:j" 矩阵校验（`:1228-1231`）；水合 `predicate_evidence_roles` 按 `condition_atom_id`（`:1238,:1247-1252`）；**水合映射经 `resolve_repeat_evidence_roles` 用水合表达式的原子矩阵解析（`:3170-3172`），`condition_dnf` 按原序枚举组/原子（`:2895-2921`）——索引一致、无重排无丢失**；所有者闭包双形态分支（`:1283-1288`）。对称性成立。
- **版本**：官方 `dnf-v10`（`protocol_deconstructor.py:132`）、控制 wire15/prompt2.11（`:116,:118`）、解构 gate `protocol-deconstruction-gate/2026-09-15.9`（`deconstruction_gate.py:64`）、控制 gate15（`protocol_control_gate.py:58`）、控制执行13（`protocol_control_execution.py:115`）——旧响应不能冒充新方法。
- **冻结/资格投影**：`_repeat_condition_material` 将非空角色映射排序入组件身份哈希、空时省略（`predicate_binding.py:217-221,:183-184`）——旧记录哈希与序列化字节不变；资格父上下文以 `condition.model_dump` 携带映射（谓词 `binding_qualification_support.py:318`、控制 `:357-358`）——**无额外模型阶段**（观察/资格/判断任务提示与轮次未变）。

### 三、未完成边界（如实陈述，非缺陷）

- **角色尚未过滤任何求值**：`repeat_trigger_calculation.py` 与 `control_repeat_trigger_calculation.py` 未消费 `predicate_evidence_roles`（全库 rg 无计算器命中）；目标范围辅助计算与最终复查采用仍待接线；`expression.py:488-489` 的 `repeat_relation_unverified` 守卫原样保留。
- 供给范围批准不推断临床完整性（`clinical_scope_complete: False` 恒定未变）；上游 formal-consumer-scope 的运行时身份失败仍未被接受（本轮未重审该运行项）。

### 四、未验证部分

全程只读：未运行代码/构造/测试/模型/浏览器。Y1 的"现路径无缺口"基于解构 wire 强制完整的源码链推演；水合索引一致性为顺序枚举的逐行核对，未构造数据实证。本报告非临床或产品验收；运行验证按用户决定推迟。
