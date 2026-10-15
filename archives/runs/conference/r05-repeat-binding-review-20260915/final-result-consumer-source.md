全部核对完成。以下为第十六轮审阅报告。

# 会议输出： r05-repeat-binding-review-20260915 - evidence_single_object（第十六轮：复查单原子求值与持久化实现审阅）

## 输出

### 一、确定缺陷

**D-1（高优先——retain_initial 仍被复查侧疑问整体清空；上轮 R1 未兑现且与实现注释矛盾）**
证据链：`qualified_observation_relation.py:159-171` 的 `supplied_scope.reason_codes` 仍混合复查侧原因（`repeat_correspondence_disagreement`、auxiliary notes、复查链接未决）；`repeat_result_resolution.py:132-136` 以 `scope["complete"]` 调用选择器；`repeat_result_selection.py:56-57` 的范围检查位于 `retain_initial` 分支（`:74-75`）之前 → 复查链接争议时 selection 拒绝（`repeat_result_scope_incomplete`）→ resolution `reasons` 非空 → `chosen=[]`（`:148`）→ `repeat_atom_calculation.py:174-175` 输出 unknown——**已核实的初查事实被复查执行疑问抹去**。这与 `repeat_result_resolution.py:137-139` 注释"repeat execution issues remain in checks but are not themselves the initial measurement truth"直接矛盾，违反本轮标准"初查、复查疑问、采用结果分离"。
最小修复：在 `qualified_observation_relation.py` 构造 `supplied_scope` 时并列输出 `initial_reason_codes`（仅初查组相关：初查组 origin 未决、初查组事实值/日期资格缺失、accounting 对初查组事实的枚举缺口）；`repeat_result_resolution.py:132-135` 对 `retain_initial` 改用初查侧完备（或 `select_repeat_result_groups` 增加 `initial_scope_complete` 参数并在 retain_initial 分支使用）；旧 material（无新键）按既有 fail-closed 模式显式要求重备（与 `:254-256` 的"须按当前方法重新准备"先例一致）。

**D-2（低——语义原子组内 UNKNOWN 混合被误标为值冲突）**
`repeat_atom_calculation.py:165-166`：组内结果 truth 集合 >1 一律 `repeat_same_acquisition_value_conflict`——语义原子"一 TRUE 一 UNKNOWN（未核）"被标成冲突而非保留未核原因。最小修复：truth 集含 UNKNOWN 时输出未核原因码（合并成员 reason_codes），仅 TRUE/FALSE 并存才记冲突。

### 二、核对通过项（不构成缺陷）

- **身份/来源闭环**：resolution 按 (owner, target, condition_id) 精确连接条件计算并五重校验（selection/frozen/parent/condition_sha/scope_sha，`repeat_result_resolution.py:36-60`）；`result_sources` 在清空前于工厂内构造（`repeat_condition_selection.py:173-190`——qualified_pairs 携带 `written_content_verified`、source_content_pairs、限定 owner 的命题关系与疑问）；atom 计算要求 `source_observation_sha256` 与封存观察一致（`repeat_atom_calculation.py:60-62`）、来源配对去重、命题关系双路/状态/owner 校验（`:71-84`）。
- **书面判断不绕过**：professional 原子逐事实要求 `written_content_verified`（`:118-121`）；investigator_discretion 的许可条件结果单列且 `written_permission` 恒 UNKNOWN（`repeat_result_resolution.py:110-121`）——条件 TRUE 不当书面许可。
- **不造 ClinicalFact/不挑有利值**：`evaluate_calculated_numeric_value`（`expression.py:170-186`）Fraction 精确比较、不把合成值放进源字段（仅 observed_unit）；数值材料经 `as_material` 分子/分母字符串（`repeat_numeric_result.py:25-38`）；不合规复查保留为证据不剔除（resolution docstring `:19-21` 与 checks 保留）。
- **原组合不改**：谓词侧 `repeat_evaluations` 仅覆盖 repeat_scheme 谓词、与命题通道互斥、context/atom 哈希与选择清单逐项比对（`expression.py:676-691`），`:488-489` 守卫保留为兜底（`:701-703`）；控制侧 owner 原子经 `chosen`/`repeat_evaluations` override（`control_calculation_experiment.py:192-205,:320-321`），四层组合不变。
- **历史兼容**：v22 三处 Literal 齐、授权/材料历史集 {v17…v22}（`qualified_binding_selection.py:61,:87,:165`）；experiment v11/outcome v4 的 `repeat_evaluations` 空省略、非当前版本拒绝（`:48-58`/`:76-88`）；`PredicateObservation.repeat_evaluation` 可选且 truth/fact_ids 一致性校验（`review.py:202-224,:240`），发布侧在有采用结果时不重复命题疑问（`frozen_review_publication.py:167,:171`）。
- **运行可达性**：`unit_required` 参数已存在于数值签名（`repeat_numeric_result.py:44`）；`compare_values`/`calculate_predicate_proposition_fact` 均在（`expression.py:145`/`predicate_proposition_calculation.py:17`）；`FrozenReviewCalculation.repeat_atom_evaluations` 字段在（`frozen_review_calculation.py:50,:247`）；导入链无环（各新服务仅单向依赖，frozen_review 局部导入 `:242,:248`）。
- **已知边界未被绕过/扩大**：报告 API/UI 未呈现（合同字段已备，呈现层待接——与声明一致）；研究者自主许可保守 UNKNOWN；`policy.selection` 非空的观察排序组合保守拒绝（`repeat_atom_calculation.py:122-123`）；无复查不推断回退（missing→UNKNOWN）。

### 三、待核风险（本轮未能完全排除）

- `repeat_atom_calculation.py:104` 控制族 `control_operands` 对全部 `source_ids` 计算（含非语义场景）——对大组有一次冗余计算，无正确性影响；运行时规模影响未测（用户推迟集中测试）。
- 语义控制原子经 `_proposition_observation`/`_conditional_observation` 的全分支行为沿第十二轮已核定义推演，本轮未逐分支重验。

### 四、结论（仅源码范围）

**FAIL 一项（D-1）**：retain_initial 的初查/复查分离未实现且与代码注释矛盾，会误伤已核实初查事实。其余接线（身份、来源、书面判断、历史兼容、参数/版本一致性、无循环导入）**PASS**。D-2 为低优先原因码修正。本审阅未运行任何代码——编译或源码推导不构成运行证据；不声称运行或临床通过；集中测试按用户决定在完整构建后执行。
