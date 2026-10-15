# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮完整读取：`RepeatScheme` v4 段（`repeat_scheme.py:95-170`）、`repeat_multi_initial_selection.py`（46 行全读）、`repeat_result_resolution.py` 多初查分支（172-239）、`repeat_atom_calculation.py` 嵌套求值段（180-254）、`repeat_observation_ordering.py`（55 行全读）、`repeat_condition_selection._condition_targets`（164-177）、presentation 量化/多链段、前端新码。仅编译/tsc 级事实。

---

### 结论：未发现可行动缺陷

**逐项核验（evidence，file:line）**：

1. **合同与版本**：`RepeatScheme` v4＋`multi_initial_result`（mode per_initial_then_all/any/unresolved＋逐字摘录，`repeat_scheme.py:94-99`）；非 v4 拒绝填充＋pop 序列化（135-137, 147-151）——旧工件身份不变 ✓。consumer31/evaluator35/publication17/dnf-v18/control prompt v2.20 全部与声明一致。
2. **链选择前提**：`select_multi_initial_results` 要求政策已声明（None/unresolved→`repeat_multi_initial_policy_unverified`）、链分解干净、**全供给域完备**（roles+links，注释明示非历史完整性主张）——任一不满足即 unknown ✓。缺失来源政策保持 unknown ✓。
3. **每链独立施用**：逐链调用既有 `select_repeat_result_groups`（单初查语义复用，`scope_complete=True/initial_scope_complete=True` 由函数级全域门保证）；链内违规 repeat → 链原因码→`selected_group_ids=[]`→链结果 unknown——**无效复查保持未知采用，不判临床 false、不删记录** ✓；链内 `result_use != retain_initial` 的执行检查逐 repeat 并入链原因（与单路径同款）✓。
4. **any/all 与来源政策一致性门**：`repeat_atom_calculation.py:222-223`——`policy.mode != multi.operation`（含 policy None/single/unresolved）→`repeat_multi_initial_policy_disagreement`→UNKNOWN，**不静默改写任一语义** ✓；链内数值（sum/mean/min/max）仍走链内 `calculate_repeat_numeric_result`（202-210），**跨链无数值聚合、无人工 ClinicalFact**（`evaluate_calculated_numeric_value` 输出计算值非事实）✓；链组合经 `_evaluate_logical`（231-234）✓。
5. **排序×多链**：`repeat_observation_ordering.py:19-21`——multi 存在/policy_selection 缺失/选定数≠1/combination 非空 → `repeat_ordering_combination_unverified`——全局排序与多链政策并存即 unknown，日期不建链 ✓。
6. **未重复初查的条件触发**：`_condition_targets`（170-177）在 multi 政策已声明且链分解干净时，为**每条无复查的初查链**补 `initial_without_repeat` 目标——即使其他链有复查也逐链计算 ✓；`select_multi_initial_results` 按链传入 `absence_triggers`（unconditional 触发合同性禁配该政策，无悬空）✓。
7. **接口假设**：“唯一 policy_selection”假设已解除——multi 路径 `policy_selection=None`＋独立 `multi_initial_selection` 键（resolution:234-235）；原子计算先分派 multi（218-221）；排序函数显式退出（19-21）；呈现层 numeric 块在 multi 下不可达（原子级 `numeric_result` 恒 None，247-250）→无 KeyError 通路 ✓。条件/计数身份联接键不变（owner, repeat_group_id, condition_id）；count_scope 字典携链明细（229-231）✓。
8. **证据/报告保留**：链结果与链内 numeric 入 `audit["multi_initial_results"]`（240-241）；absence/frequency/numeric 嵌套来源均保留并呈现（presentation:19-21, 125-129）；原子级 `evidence_fact_ids` 覆盖链内事实（链事实 ⊆ 全图 source_fact_ids）✓。前端两新码已映射（53-54，措辞“暂不自行选择结果”与实现一致）✓。
9. **UI vs 计算**：呈现全部由存储 resolution 生成；多链说明（“不同组不混合计算数值”）与实现语义一致；无采用性宣称（`replacement_authorized=False` 不变）✓。

**明确不支持（非 bug，如实呈现为 unknown）**：governing-initial 日期选链、跨链数值聚合、排序×多链、政策与观察量词不一致的混合语义、政策未声明。

**覆盖限制**：(a) 双解构器 v4 提示全文未逐字重读（wire schema 由 `model_json_schema` 自动携带新字段、版本常量已核）；(b) `repeat_numeric_result.py` 未列变更、未重读；(c) 多链呈现的浏览器视觉核验归 Codex。

**非声明**：仅编译/tsc 级事实；不构成方法批准、临床接受或完成宣告。会话保持可续。
