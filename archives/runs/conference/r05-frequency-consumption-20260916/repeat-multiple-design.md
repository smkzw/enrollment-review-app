# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮读取：`FrequencyRelativeHorizon`/`FrequencyHorizon`（`rules.py:169-218`）、`_relative_bounds`、`domain/repeat_result_selection.py` 全文、`services/repeat_atom_calculation.py`（228 行全读）、`repeat_result_resolution.py` 相关段、`RepeatScheme`/`ObservationPolicy`（本会话早前全文在案）。仅报告建议，owner 决定。

---

### 1. 地平线精炼核验（evidence，通过）

`FrequencyRelativeHorizon`（`rules.py:169-177`）仅保留 anchor_type/direction/上下界 TimeQuantity＋**可空**开闭——不含半衰期、洗脱、combined_window_selection 等无关 schema；`_relative_bounds` 开闭未知即返回 None→`frequency_horizon_dates_unresolved`（`frequency_quantified_periods.py:18, 60`）；既有 `TimeConstraint` 一字未动。**核验通过，无新问题。**

### 2. 多初查现状（evidence）

现有链路已 honest-unresolved：`repeat_initial_scope_not_unique`（多初查时，`qualified_observation_relation` 侧）；`select_repeat_result_groups` 只接受单一 `initial_group_id` 且要求所有 repeat 可溯祖至该初查（`repeat_result_selection.py:92-93`→`repeat_initial_correspondence_unverified`）；`repeat_predecessor_ambiguous` 拦截双前驱；`repeat_atom_calculation.py:184-187` 对 selected 为空/有 reason 即整体 UNKNOWN。**无扁平化、无日期排序捏造对应**——现状即正确默认。

### 3. 现有字段是否足够？——不足，需显式链级声明（inference + recommendation）

三个缺口证明不能只靠既有字段：
1. `ObservationPolicy.mode`（any/all）语义是**原子供给观察集**上的组合，不是“每条链先施用复查政策、再跨链组合”——复用它会静默改写既有语义；
2. 无任何字段声明“多初查时哪条链作准”（governing）或链间合取/析取；
3. `count_scope=per_initial_acquisition`（每初查上限）与 `per_current_episode`（当前节点上限）已分立，但只覆盖计数，不覆盖**结果采用政策在链间的施用方式**。
因此“因存在多条初查记录就按初查分别施用再 any/all”是**不被支持的来源解读**，须显式声明；不能要求用户裁决语义——声明由解构模型按方案原文供给，原文不明→unresolved。

### 4. 最小合同建议（RepeatScheme v4，additive；v3 pop 读旧＋`require_current_extraction` 要求当前版——沿用 no_repeat_result_use 先例）

```
multi_initial: Literal["per_initial_apply_owner_policy", "governing_initial",
                       "unresolved"] | None
governing:     Literal["latest_initial", "earliest_initial", "unresolved"] | None
```
- 仅当图确认多初查时消费；单初查存在即忽略（向后等价）。
- `per_initial_apply_owner_policy`：按链分割（初查组＋其 repeat 后代，祖先关系已在图内；一条 repeat 溯及两条初查已被 `repeat_predecessor_ambiguous` 拦截）→ **每链独立调用既有 `select_repeat_result_groups`**（链内初查+该链 repeats）→ 链间组合沿用原子既有 `observation_policy`（any→任一链满足即触发；all→全部链满足；policy 单值/未决→unresolved，不新造语义）。
- `governing_initial`：按声明的 latest/earliest **初查日期**选链（日期序在此是来源明示的选择准则，合法；对应关系仍只来自已声明关系），其余链进 not_selected 审计。
- 来源不明→`multi_initial=unresolved`→维持现状 unresolved 原因码，不发明。

### 5. 明确不支持（honest 边界）

跨链数值聚合（两初查系列的值相加/取均值——`result_combine` 仅限单链内，跨链聚合须另立声明）；按日期顺序**推断**记录归属哪条链；每初查上限与当前节点上限互相折算；部分链 unknown 时以有利链代答（组合沿既有 UNKNOWN 传播）。全部保持 unresolved 并给出原因码。

### 6. 实施顺序（最小连贯）

1. `RepeatScheme` v4 两字段＋校验（governing 仅 governing_initial 必填；unresolved 须原因）＋双解构器 prompt/gate 同步＋版本 bump。
2. 图链分解纯函数（按初查祖先关系分链，置于 `repeat_result_selection.py` 旁），多初查时逐链调既有 selection。
3. `repeat_result_resolution`/`repeat_atom_calculation` 消费：policy 未声明→现状原因码不变；声明后按 §4 组合，ordering 审计记录每链 selected/not_selected。
4. 呈现：按链列出结论与未选链；前端补多初查原因码。
5. 方法评测清单增补：链归属错误（一条 repeat 挂两初查）、governing 选错方向、跨链聚合未声明即用、单链 vs 全局上限混用。

**有界问题**：Q1 `per_initial_apply_owner_policy` 的跨链组合是否限定复用原子 `observation_policy`（我的建议：是，避免第二套量词），还是允许 RepeatScheme 另带链间 any/all（我反对——两处量词易冲突）；Q2 `governing_initial` 的“最近”在初查日期部分精度时的处理（建议：无法唯一排序→unresolved，不取有利）。

**标注**：§1-2 evidence；§3-6 为 recommendation/design，owner 决定；无写入/导入/运行/临床访问；不构成方法批准。会话保持可续。
