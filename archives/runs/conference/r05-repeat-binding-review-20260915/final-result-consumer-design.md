当前实现已重读核实（选择器/数值/条件选择/两族计算器/求值器/发布链与设计文档增量段一致）。以下为最终设计核查报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第十五轮：最终复查结果消费设计核查）

## Output

### 一、对拟实施方案的挑战结论（高/中风险优先）

**R1（高——retain_initial 会被复查侧疑问整体清空，违反“分别保留”）**
`repeat_result_selection.py:56-57`：`scope_complete` 检查位于 `retain_initial` 分支（`:74-75`）之前，而 `supplied_scope.reason_codes`（`qualified_observation_relation.py:159-171`）混入了纯复查侧原因（`repeat_correspondence_disagreement`、`auxiliary notes`、复查链接未决）。某次复查链接争议会令 retain_initial 拒绝——已核实的初查事实被复查执行疑问抹去。最小修订：在 `qualified_observation_relation.py` 构造 `supplied_scope` 时将 reason 二分为 initial-critical（`observation_scope_reasons` 结果、初查组 origin 未决、初查组值/日期资格缺失）与 repeat-side（correspondence/disagreement/notes）；`select_repeat_result_groups` 增加 `initial_scope_complete` 参数（或把 retain_initial 分支的角色检查后移至 initial 侧判定），retain_initial 仅被 initial-critical 阻断。初查本身的来源、归属、书面判断（`_evidence_scope` 经 `written_content_verified_pair_ids` 已核）与有效期（`source_validity_specs`）保持原通道不变。

**R2（中——研究者许可无书面判断绑定合同）**
`repeat_scheme.py:136-137` 仅强制 investigator_discretion 声明许可条件；condition_selection 的 outcomes（`repeat_condition_selection.py:211-215`）不含“许可命题=书面批准”的内容映射（第九轮判定未变）。许可条件 DNF TRUE ≠ 许可成立。最小实现：采用组装器对该 permission 目标输出 `investigator_permission_unverified` 并阻断采用（UNKNOWN+缺口报告，不中断、不要求用户确认缺失）；若需闭环，补版本化 `RepeatPermissionRecord`（绑定 scheme/对象/judgment_content pair）——非本轮必须。

**R3（中——“不合规复查”的结果处理无原文合同，必须保留未知）**
触发不成立、超 `maximum_repeats`、期限外的**已发生**复查：方案未规定其结果能否采用，RepeatScheme 无对应字段。可由现有合同确定的只有：无复查+use_* → `repeat_result_missing`（`:76-77`）UNKNOWN、不回退初查、不选有利值（`:78-92` 全部显式声明路径）。不合规复查处理必须输出 `repeat_execution_nonconforming` 类 UNKNOWN 并单列缺口；**不得编造**“违规复查仍采用/一律废弃”的临床政策——原文语义补充留给 scheme 未来版本。

**R4（中——Fraction 不得进 ScalarValue 域）**
`expression.py:73-79` `EvaluationResult.observed_value: ScalarValue`。采用结果走 truth-only + `RepeatNumericResult.as_material`（`repeat_numeric_result.py:25-38`，分子/分母字符串）材料并行（第九轮 B 选项）；阈值判定在组装器内用 `evaluate_observed_value`（`:466-482`）以 Fraction 直接比较（Python 原生 Fraction/Decimal 比较支持）。

**R5（中——控制族 owner 原子无采用覆盖通道）**
`_evaluate_control_selection` 的 atom_truths 由 chosen 计算推导，无 override 入口。最小修订：增加可选 `atom_truth_overrides: Mapping[atom_identity, TruthValue]`（校验键 ⊆ repeat_scheme owner 原子、值为三值），与谓词侧新参数对称。

### 二、最小完整源码接线（依赖有序；无新模型任务）

1. **R1 修订**（上述）。
2. **谓词侧单原子通道**：`_evaluate_bound_predicates`（`expression.py:608-676`）增加 `repeat_adoption_evaluations: Mapping[predicate_id, EvaluationResult]`，校验复制 `:656-660` 模式（键 ⊆ repeat_scheme 谓词、`used_fact_ids` ⊆ 该谓词选择、未核实谓词强制 UNKNOWN）；分支链插在 `_evaluate_atomic` 兜底之前；`evaluate_component` 透传；**原最终组合不变**——adoption 只覆盖 repeat_scheme 谓词，`:488-489` 守卫保留为无输入兜底；EVALUATOR_VERSION v25。
3. **组装器** `app/services/repeat_adoption_resolution.py`（消费者=v25，非孤立 helper）：纯函数，输入 sealed selections + frozen_review 的 EvaluationContext；逐 owner 经 `iter_scoped_repeat_conditions`（`repeat_condition_selection.py:237-284`，五重身份已校验）取**按目标**的触发/许可条件结果（owner_references 区分角色，`repeat_trigger_calculation.py:75-77`），结合 `series_constraints`（`qualified_observation_relation.py:203-209` 调用，按 target 的 time_checks + count）、`result_policy_selection` 与 `calculate_repeat_numeric_result`（scheme 必填哈希校验，`repeat_numeric_result.py:59-60`）；all/any 组合复用 `calculate_predicate_propositions(condition_selection=row)` 逐组结果 + `_evaluate_logical`，不新写组合器。输出 `RepeatAdoptionRecord`：每 owner 谓词的 EvaluationResult + `as_material` 材料引用 + 五哈希（scheme/资料/图/条件范围/方法——方法身份经授权 id）。布尔/数值结果只描述“该 owner 谓词采用值判定”，**不进最终条款 AND 之外的任何通道**（方案 1 约束成立：触发 TRUE 仅是采用前置，不是入排真值）。
4. **控制侧**：组装器产出 owner 原子三值（数值经同族 operand 通道、语义经现有 `_evaluate_control_selection(repeat_triggers_only=True)` 的 chosen=row 选择），经 R5 的 `atom_truth_overrides` 注入——`compose_control_layers` 的四层组合不变。
5. **授权与版本**：`QualificationAdoptionAuthorization` 增可选 `repeat_adoption`（省略保持序列化，模式同 `observation_relation`，`qualified_binding_selection.py:73,:78-79`）；gate input_entity_refs 含组装依据哈希；consumer v22、publication v8；评测/审批记录产生前不得启用（用户未授权自动采用新方法）。
6. **报告层**：复用 `reviewEvidenceScopeNote`（`frozenReviewExport.ts:7`）既有范围声明；报告投影增加四分字段（初查发现 / 复查可用性 / 实际采用结果 / 资料范围），未采用原件经 `not_selected`/`unverifiedEvidence` 既有通道保留（`frozenReviewExport.ts:43-50`）。

**过度工程检查**：无需重开观察/资格轮次（全部材料已封存于 material v21 与 v24 计算结果）；不需要独立“采用模型任务”；组装器是必要消费者而非再设计。比拟方案更短的一点：控制族**不需要**新表达式通道——现有 chosen/unverified 输入加一个 override 映射即闭合。

### 三、无复查/不合规复查策略（明确边界）

由现有合同可定：retain_initial（修订 R1 后仅依赖初查侧完备）；use_single/use_last/combine 无复查 → UNKNOWN（missing）；角色/范围/唯一性不满足 → 各自 UNKNOWN 原因码（`:51-89`）。必须保留未知：不合规复查处理（R3）、许可无书面判断（R2）、`result_use=unresolved/not_specified`（`:93`）。禁止：无依据回退初查、跨政策选有利值、把 condition TRUE 当入排 TRUE。

### 四、未验证部分

全程只读，未运行任何验证；本轮为设计核查与源码接线建议，不构成运行/临床验收，不宣称测试通过（用户已决定完整构建后集中测试）。历史封存不受影响：所有新输入版本化（v25/v22/v8），旧快照走既有守卫保持 UNKNOWN；原文引用经 condition/graph/selection/scheme 哈希闭环，无原始事实改写。
