# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮读取：`repeat_frequency_scope.py`（全文）、`repeat_condition_selection.py` 频次分支与 `iter_scoped_repeat_conditions`（292-341）、`frequency_atom_calculation.py` scoped 路径（38-90）、`repeat_trigger_calculation.py` 调用段、`repeat_result_resolution.py` 嵌套保留段、`evaluation_result.py` 验证器、`repeat_review_presentation.py`、`frozen_review_calculation.py`/`control_calculation_experiment.py` 接线段。仅报告新发现；不构成临床接受。

---

### 1. 声明逐条核验（evidence，全部通过）

- **封存行验证**：`iter_scoped_repeat_conditions`（`repeat_condition_selection.py:292-341`）——selections `require_unchanged`；owner 身份取自冻结输入期望集；每个复查目标×辅助条件的行完整对应（318-320 不多不少）；行级校验 version（v2/v3 读保留、v3 强制于频次路径 `frequency_atom_calculation.py:79-80`）＋owner_hash＋target_kind＋parent_id＋graph_sha256＋condition_sha256（321-327）；逐身份 outcome 完备（338-340）。任何不一致 raise 关闭。
- **主/辅分离与意外启用防护**：scoped 调用跳过主身份与非 scoped 身份（`frequency_atom_calculation.py:61-62`）；无 scoped_outcomes 的常规调用跳过辅助身份（59-60）——**辅助频次在无封存行时留在旧 unknown 路径**，不会被静默启用 ✓。outcome 非 usable → `source_unresolved` 追加（`repeat_frequency_scope.py:24-25`）→ 下游 `_resolve_single_frequency:34-36` 一律 `frequency_sources_unresolved` 关闭数值消费 ✓。
- **来源配对限制**：pairs 限定 `usable_pair_ids` ∩ `outcome.fact_ids`（10-12），statements 再限定于 pairs（13-14）；跨 scope 关系**不丢弃**——单端在 scope 的链接进 `crossed` 并以 `frequency_relation_crosses_repeat_scope` 追加 unresolved（16-23），桥接矛盾证据保留 ✓；全局 disputed/unresolved_notes 原样携带（21）✓。
- **哈希绑定**：`repeat_scope_sha256 = canonical_hash(row)`＋`unscoped_frequency_sha256 = canonical_hash(qualified)`（29-30）——scoped 计算同时绑定封存行与原始资格材料，无变更/无混用 ✓。
- **重算而非沿用父数**：individual/day/total/quantified 全部从 scoped statements 重算（31-38）✓；per-period 量化亦按 scoped 集合 ✓。
- **评测器一致性**：`chosen` 用频次 used_fact_ids 替换所选 ID（`repeat_trigger_calculation.py:66-67`），注入 `_evaluate_bound_predicates` 时与既有 used==selections 校验自洽 ✓。
- **数值分支不可供给书面许可**：`written_permission` 仅来自书面内容支持的研究者原子（82-89），频次数值结果无法置位 ✓。
- **嵌套保留与报告**：`RepeatAtomEvaluation.evidence_fact_ids` 纳入嵌套 `condition_frequency_evaluations` 来源（`evaluation_result.py:63-65`）；resolution 保留并输出 `condition_frequency_evaluations`（`repeat_result_resolution.py:62-70,185-187`）；呈现按复查组渲染逐条件频次说明＋“不作为检查结果值采用”（`repeat_review_presentation.py:83-91`）✓。
- **版本**：evaluator `component-review/v34`、publication `frozen-review-publication/v16`、consumer `qualified-binding-selection-consumer/v30`、control experiment v13（frequency 门限 v12+、repeat v11+）✓ 与声明一致。
- **无新模型步**：`scope_repeat_frequency` 是对已资格化 dump 的纯重算；来源限定器/模型读取未动 ✓。**目标相对事件锚**：未添加支持——occurrence_date 仍须来源自述，未命名事件不借复查日期，保持 unresolved ✓。

### 2. 发现

无健全性缺陷。三条观察（无需改动）：(a) 跨 scope 判定中“两端都在 scope 外”的链接既不入 links 也不入 crossed——正确（与 scoped 证据无关），且原始全量链接经 `unscoped_frequency_sha256` 与父级材料哈希保留，无丢失；(b) scoped 副本继承父级 `source_unresolved`，下游保守方向正确；(c) “context=None 旧路径保持 unknown”子声明——我核实了 `repeat_trigger_calculation.py:42-55` 与 `frequency_atom_calculation.py` 的 context/authority/事实等同校验及频次路径无合成日期构造，但未在本轮限定范围内逐行定位控制族该分支，标记为**未完全核验**而非断言。

**非声明**：目标相对事件锚、外层窗口组合、无界/部分地平线仍未实现；全部为编译级事实，无运行/写入/临床访问；不构成方法批准、临床接受或完成宣告。会话保持可续。
