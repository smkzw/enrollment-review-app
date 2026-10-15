全部核对完成。以下为第十四轮审阅报告。

# 会议输出: r05-repeat-binding-review-20260915 - evidence_single_object（第十四轮：目标范围复查条件选择）

## 输出

### 一、实际缺陷（低严重度；未发现高/中）

**AF1（低——外部上下文的审计记录不可区分"未检查"与"不适用"）**
`repeat_condition_selection.py:38-44`：`external_context` 与角色缺失分支的 `audit` 只有 role/reference_group_id=None/considered/outside 四项，不含 `supplied_scope.complete` 或枚举状态标记——审计层面无法区分"范围检查不适用"与"被跳过"。行为本身正确（外部上下文按设计用原始全范围、跳过采集归属类检查），仅审计可读性缺口。最小修复：audit 增加 `"scope_checks": "not_applicable_external_context"` 类显式标记。

**其余重点检查项均核对通过（无缺陷）**，包括分派点名的风险面：
- **"全局清空前重选"的时序**：`build_repeat_condition_selections` 在工厂内 pair 资格（rejection 过滤后的 `by_identity`）之后、全局 identity 选择之前调用（`qualified_binding_selection.py:524-531`），`_select_atom` 在 `allowed` 限定范围内**复用同一套选择器**（`_select_facts_for_identity`/`select_ordered_observation`/`select_semantic_ordered_observation`，`:119-138,:92-99`）——不是绕过选择，而是在目标范围内重做选择；单观察多访视谓词的证据在全局清空前已按目标封存。
- **只排除正向归属他组的候选**：`_evidence_scope:62-70`——归属来自 `qualified_auxiliary_associations` 的 identity 匹配条目；每个候选的归属组集合必须恰一个（多重归属 → `repeat_condition_correspondence_unverified`，AB1 的消费侧处理为 unresolved）；未映射/歧义/争议/任一路辅助 notes 非空均 unresolved（`:59-67`）；`external_context` 用全量事实集（身份维度仍由资格配对限定，`:43-44` + 调用处 :200-205）——**无自动回退**。
- **参照解析**：initial 经祖先闭包且限 initial 角色组、唯一才用（`:20-33`）；preceding 仅显式 `reference_kind` 边、唯一才用（`:16-19`）；结构疑问优先拒绝（`:11-12`）。
- **AND/OR 部分不确定**：outcome 为原子级，reasons 非空即 unresolved+空事实（`:209-215`），DNF 组合沿用三值逻辑；谓词消费把原子未决原因并入 UNKNOWN 结果（`repeat_trigger_calculation.py:65-67`）；控制消费把非本条件的旁置原子置空选择并记 `repeat_condition_outside_target`，防跨条件污染（`control_repeat_trigger_calculation.py:39-46`，与 `_evaluate_control_selection` 的"未核实原因必须对应空选择"校验吻合）。
- **语义内容/日期/专业判断**：语义分支的 relations/gaps/覆盖检查按 row 限定（`:85-113` + `predicate_proposition_calculation.py:22-41`——`condition_selection` 必须逐字节等于封存行，`:24-27`）；日期操作数校验（`:107-112`）；`written_content_verified` 按支持配对传递（`:135-136`）。
- **身份/来源闭环**：图哈希重验（`:165-166`）；封存消费 `iter_scoped` 要求版本/owner/parent/graph/condition 五重身份匹配、目标×条件键集恰好覆盖、outcomes 覆盖条件原子（`:254-278`）；旧 material（无 condition_selections）显式拒绝"须按当前方法重新准备"（`:254-256`）。
- **版本/历史**：consumer v21 双 Literal、v20 可读；授权与 material 的 observation 历史集合已修为 {v17…v21} 连续（`qualified_binding_selection.py:87,:212`——上轮 AB2 修复确认）；evaluator v24（`frozen_review_calculation.py:27`）调用两族辅助计算、结果哈希入 selection_payload（`:309`）并随计算返回（`:321`）——**不授权结果替代**，正式入排对复查谓词仍走既有 UNKNOWN 守卫。
- **归档规则集兼容**：无 `predicate_evidence_roles` 的历史条件 → 角色缺失 → 逐原子 unresolved（`:41-42`），不崩、不猜。

### 二、未完成边界（非缺陷，单独列示）

目标范围触发/许可计算已产出（v24 记录），但**最终复查结果采用仍未接线**：`repeat_condition_calculations` 无 evaluator 消费、`RepeatTriggerCalculation.replacement_authorized` 恒 False；结果选择/数值计算与目标选择的串联（`resolve_repeat_adoption` 一类组装器）及授权 gate 扩展是下一步集成工作。观察任务的新语义方法（consumer v5/辅助关联 v3）在评测与审批记录产生前不得自动采用；用户批准的是"已供已核记录内判断+已知缺口另报"，非全局记录完备声明。全程只读，未运行验证——编译/源码核对不构成运行验收；本报告非临床或产品验收。

### 三、未验证部分

未运行任何代码/构造/测试/模型/浏览器。`_evidence_scope` 归属/枚举分支的行为推演、`iter_scoped` 键集校验对多目标×多条件的覆盖、控制族 `truths[parent_id][atom_id]` 的键域（沿第十二轮已核的 by_control 结构）均为源码推导；`deepcopy` 语义 relations 的不可变性依赖 dataclass/dict 无共享可变状态的既有约定，未实证。
