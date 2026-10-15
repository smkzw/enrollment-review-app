全部证据就位（期限计算器 `repeat_observation_time.py:19` 已存在且前提外部化）。以下为第七轮审阅报告。

# 会议输出: r05-repeat-binding-review-20260915 - evidence_single_object（第七轮：复查数值结果 + 最小完整集成路径）

## 输出

### 一、A 部分：`repeat_numeric_result.py` 与其选择输入的缺陷

**U1（低-中——选择结果与图的身份绑定缺失）**
`app/domain/repeat_result_selection.py:8-13` 的 `RepeatResultSelection` 不携带其来源图的 `graph_sha256`；`repeat_numeric_result.py:33-40` 只校验传入图自身哈希与 `selected ⊆ groups`，**不校验 selection 产自同一图**。调用者可用图 A 的 selection 配图 B（两图各自哈希自洽且组 id 恰有交集）而静默使用图 B 的事实集。最小修订：`RepeatResultSelection` 增加 `graph_sha256: str | None = None`（默认保持兼容），`calculate_repeat_numeric_result` 在非 None 时强制相等；或由组装层统一传入期望哈希。

**U2（低——合格值集的规则绑定完全外部化）**
`repeat_numeric_result.py:27`（docstring）与 `:56`：`qualified_value_fact_ids` 是否属于**该 repeat_scheme 所有者身份**函数不可检测。集成时必须从该谓词的 `identity_outcomes` usable `fact_ids` 派生（`qualified_binding_selection.py:536-543` 一带已有的产出），不得用全量合格集——否则跨规则借用不可见。集成约束，非函数缺陷。

**核对通过的算术/来源/完整性语义**（file:line）：
- 精确有理数：`Fraction(Decimal(str(value)))`（`:67,:72`），float 经十进制字符串精确化，sum 从 `Fraction(0)`（`:81`）、mean 为精确除法（`:82-83`）、min/max 比较（`:84-87`）——无舍入路径，docstring `:29-30` 明示避免跨阈值舍入。
- **所选采集组的全部合格记录必须一致**：组内 `(Fraction, unit)` 集合唯一否则 `repeat_same_acquisition_value_conflict`（`:59-74`）；跨组单位一致（`:78-79`）；极性必须 AFFIRMED（`:63-64`）；bool 先于数值检查（`:65`）；非有限值拒绝（`:68-69`）。
- 结构性守卫：图哈希重算先行（`:33-36`）；selection 原因或结构疑问直接 unresolved（`:46-47`）；`all/any` 拒绝并指向命题求值器（`:51-52`）；operation None 限单组（`:53-54`）；输出为纯 dataclass，非 ClinicalFact、无采用字段（`:12-18`，对比 `RepeatTriggerCalculation` 的 `replacement_authorized=False` 模式）。
- 无方案/疾病/模型硬编码；`select_repeat_result_groups` 与本函数均**无产品调用者**（rg 全库）。

### 二、B 部分：四问证据能力判定与最小集成路径

**(a) 采集观察成员资格 = 已有证据；供给来源覆盖 = 真缺失语义。**
成员资格：`same_acquisition` 双路同意链接 + 每端逐字 quotes + 位置级资格化（`qualified_observation_relation.py:62-88,:93-100`）→ 图 `acquisition_groups`（`observation_relation_graph.py:36-40`）——完整。覆盖：`clinical_scope_complete` 恒 False（`observation_relation_receipts.py:84`、`qualified_observation_relation.py:119`）；判断搜索覆盖（`JudgmentSearchCoverageSummary`）是页面级判断搜索覆盖，`candidate_fact_accounting` 只证明“每条供给事实被考虑”——**都不能证明“该检查项目的全部报告已供给”**，且分派禁止从全部供给事实推断。→ 最小合同新增：`ObservationCoverageStatement`（version `observation-coverage/v1`）：scheme 身份 + 检索范围声明（来源类型/访视窗）+ 证据引用（判断搜索 summary、到期要求清单）+ `covered_group_ids`；版本化消费者为 `select_repeat_result_groups(scope_complete=)` 与 `evaluate_repeat_count(scope_complete=)`（两处现有参数即插座）。

**(b) 触发范围 = 计算器齐备、缺“防自证”绑定（未接线+一小块缺失语义）。**
`calculate_repeat_trigger_conditions`（谓词，`repeat_trigger_calculation.py:23-79`）/`calculate_control_repeat_triggers` 与期限计算器 `evaluate_repeat_time_limit`（`repeat_observation_time.py:19-81`，调用者提供 reference_date、无 initial→preceding 回退）都已存在。缺失：触发条件的合格事实选择（`identity_outcomes.fact_ids`）与观察图组角色**无交叉约束**——复查结果自身的值可满足其触发条件（分派明令禁止）。→ 最小新增：纯函数 `partition_facts_by_observation_role(graph, fact_ids)`（initial/repeat/unclassified 三集）+ 包装器 `calculate_scoped_repeat_triggers`：按 `time_limit.reference` 允许角色过滤后再调既有 `evaluate_bound_expression`；目标复查组事实一律排除。

**(c) 研究者许可 = 真缺失语义。**
judgment_content 链证明“书面判断内容与对象一致”（`verified_judgment_requirements`、`content_supported_pair_ids`），不承载“批准复查”命题；无许可消费者。→ 最小合同新增：`RepeatPermissionRecord`（version `repeat-permission/v1`）：scheme 身份 + 对象 + judgment_content job/pair 引用 + 许可命题映射。缺失书面判断 → unresolved 原因 `investigator_permission_unverified`（报告缺口，非 satisfied、非强制交互中断）。

**(d) 结果采用 = 代码就绪、未接线；终态消费需版本化 evaluator 输入。**
`select_repeat_result_groups` + `calculate_repeat_numeric_result` 就绪。终态消费者（不发明审批）：`_evaluate_bound_predicates` 增加 `repeat_adoption_evaluations: Mapping[predicate_id, EvaluationResult]` 可选入参（模式同 `proposition_evaluations`，`expression.py:650-660` 的范围校验可复制）；仅由 owning service 在授权 gate 后构造；`_evaluate_atomic` 的 `repeat_relation_unverified` 守卫（`:488-489`）保留为兜底。版本化：EVALUATOR_VERSION v24、consumer v18（两处 Literal）、publication v8、`QualificationAdoptionAuthorization` 加可选 `repeat_adoption`（省略保持序列化，模式同 `observation_relation`，`qualified_binding_selection.py:73,:78-79`）。

**有序实现计划（函数边界，全部复用既有证据轮次、无新模型轮）**：
1. 修 U1（selection 携带 graph_sha256）。
2. `app/domain/repeat_scope_partition.py`：`partition_facts_by_observation_role`。
3. `app/services/repeat_trigger_scoped.py`：`calculate_scoped_repeat_triggers`（输出含被排除事实与 `trigger_scope_verified`）。
4. `app/domain/contracts/observation_coverage.py` + 组装服务（消费判断搜索与到期清单，产出 scope_complete）。
5. `app/domain/contracts/repeat_permission.py`（judgment_content 挂接）。
6. `app/services/repeat_adoption_resolution.py`：`resolve_repeat_adoption(...)`——组合封存 material 内 `observation_relations` 图 + scoped triggers + `evaluate_repeat_count` + `evaluate_repeat_time_limit`（reference 由图角色与 episode anchors 解析）+ `select_repeat_result_groups` + `calculate_repeat_numeric_result`；输出 `RepeatAdoptionRecord`（组件哈希绑定，`replacement_authorized=False` 待 gate）。
7. evaluator/合同版本化消费（上段 (d)）。
8. `qualified_review_command`/`prepared_review_publication` 接受 repeat adoption gate 引用；`prepared_review_workflow` v7 仅增步骤编排，不加模型任务。

**高后果歧义（需所有者决策）**：
- 触发证据角色的**缺省**：方案未声明参照时，unclassified 组是否可参与触发？建议保守排除（仅角色明确组），代价是纯 unclassified 资料下触发恒 UNKNOWN。
- 许可时间性：v1 不断言许可早于复查日期，日期不明保留 unresolved。
- 覆盖声明的证明边界：到期要求清单 + 判断搜索的联合何时足以声明 `scope_complete=True`——这是 (a) 的唯一真实证据缺口，声明过宽会制造不安全肯定。

### 三、未验证部分

全程只读，未运行任何代码/构造/测试/模型/浏览器。U1 的错位场景为源码推演；`evaluate_repeat_time_limit` 的分支语义（日历 vs 流逝分钟、开界）为逐行阅读结论，未数值实证。本报告为工程/源码审阅，不构成临床或整产品验收；运行测试按用户决定推迟至完整构建后，本轮不建议亦不执行。
