全部核对完成。以下为第十二轮审阅报告。

# 会议 Output: r05-repeat-binding-review-20260915 - evidence_single_object（第十二轮：复查次数/期限计算接线 + 观察任务归属局限确认）

## Output

### 一、核对结论与实际缺陷

**`repeat_series_constraints.py` 及其调用（`qualified_observation_relation.py:169-175`）：未发现算术、图、身份或序列化缺陷。** 逐项源码证据：图哈希 + `supplied_scope` 三重绑定（graph_sha256/scope 值/fact_ids 恰等于全组事实/complete 严格 bool，`:18-28`）；per-initial 计数要求**恰一已知初查 + 全部复查祖先链回指**（`:50-51`），`per_current_episode` 一律 `repeat_count_scope_unverified`——不从共享上传范围假设（`:53-56`）；计数按**采集组**（`:60-63`，复用 `evaluate_repeat_count`）；期限对照三分支——`episode_anchor` 用精确声明锚（`:91-93`，str 枚举键与 dump 后 dict 查找兼容：`enums.py:4` `StableEnum(str, Enum)`、`:51` 值 `"first_dose_date"`）、`initial_observation` 用祖先链交集（`:95`）、`preceding_observation` 用**显式 preceding 边**且候选唯一（`:96-101`）；组日期要求**全部记录具备资格日期配对**（调用处 `:172-173` 仅 `fact_attribute=="date_range"` 的 identity-local 配对）且**日期+精度一致**（`:66-76`，排除 source_text 比较实际值）——无记录/上传日期回退、无日期排序回退（日期来自 `_phase3_date_value(item.date_range)`，`:171`，保精度的既有适配）；`replacement_authorized: False`（`:120`）+ docstring `:13`；输出携带 scheme/graph/supplied_scope 三哈希（`:114-115`）。

**Z1（低——结构疑问与范围共用原因码）**：`:57-58` 结构疑问时计数返回 `repeat_count_scope_unverified`——与"范围未核"同码，实际结构原因在 `graph.structural_reasons` 可查。轻微误导调试；最小修复：区分 `repeat_count_structure_unverified`。

**Z2（真实集成缺陷——所有者指认的观察任务归属局限，源码核实成立）**：`observation_relation_input.py:39-48` 的 schemes 只收**所有者身份**（trigger/exception 谓词或四层控制原子）的 repeat_scheme；`:51-57` 组成员只收 `pair.identity_sha256` 为该所有者身份的资格配对。因此观察图只覆盖**所有者同一测量的记录**；当 `predicate_evidence_roles` 中 `initial_observation`/`preceding_observation` 角色谓词是**另一测量身份**（如"实验室 X 超标时复查血压"的 X）时，其资格事实不在任何 owner 图内——未来按角色过滤条件证据将无图可依，缺失匹配只能保持 unresolved。第十轮建议的"图交集证明采集"在跨测量场景**不成立**，所有者更正正确。

### 二、最小扩展现有观察任务（未来集成设计，非新模型阶段、非临床启发式）

对 `observation_relation_input.py` 的组构造增加 **auxiliary source references**：对每个 owner scheme 的 ancillary 条件，取角色为 `initial_observation`/`preceding_observation` 的**条件谓词身份**的资格配对（来自同一资格任务的 identity_outcomes——已存在，无需新轮次），随组作为辅助来源输入；观察任务的既有 link/origin 提示与校验扩展一类对象（`validate_observation_relation_payload` 的两端集合检查放宽到"成员 ∪ 辅助引用"，origins 覆盖并集），输出辅助事实→组的归属声明，与 owner 图同闭包校验。**防混分析物的结构保证**：owner 结果值与辅助事实分列——`qualified_operand_pairs` 维持 identity-local（`qualified_observation_relation.py:158-168` 现状已保证），`calculate_repeat_numeric_result` 的 `qualified_value_fact_ids` 只收 owner 身份 value 配对，辅助事实只产出"归属组"声明、**永不进入** `acquisition_groups` 的组值集合——数值聚合无法混入异测量。`external_context` 角色不需要归属（不过滤）；无匹配 → unresolved（**无自动回退**）。

### 三、版本与历史兼容

qualification consumer v19：两处 Literal 含 v19（`qualified_binding_selection.py:61,:165`），历史约束集保留 v17/v18（`:87,:212,:231`）；observation consumer v4（`qualified_observation_relation.py:12`）——旧 v3 评测被 `:24-25` 拒绝（需新评测记录，方法评测/审批未跳过）；`series_constraints` 新键仅出现在新产出 material 中（dict 字段，旧 v18 material 读兼容）。

### 四、未完成边界（非缺陷）

通过 count/time 不授权替代（模块恒 False）；最终复查采用消费者未接线，`repeat_relation_unverified` 守卫原样；`supplied_scope` 用户策略只覆盖已供记录，已知缺口另行报告；辅助来源扩展为设计建议，尚无源码。全程只读，未运行任何验证；本报告非临床或产品验收。
