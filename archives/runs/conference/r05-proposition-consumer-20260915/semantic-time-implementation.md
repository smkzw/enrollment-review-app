# Conference Output: r05-proposition-consumer-20260915 - evidence_single_object

## Output

同会话第 5 轮只读源码复审（未编辑/导入/运行）。结论：**语义-时间路径成立：同事实独立合格日期强制、无绕过准入的计算路径、确定性行为不变、v1 兼容双闸；未发现不安全推断。1 个一致性小瑕疵（F-A），另答极性边界问题。** ≤60 行。

### 发现
- **F-A（低，一致性瑕疵，非不安全）** 豁免旗标口径不一致：关系选择按**身份**成员豁免 `pending:source_validity_requires_policy_evaluation`（`app/services/qualified_proposition_evidence.py:63`），而拒绝核算路径按身份**且** fact_attribute 过滤（`app/services/qualified_binding_selection.py:371-374`）。v2 语义 source_validity 规格 `operand_attribute=None` 时两口径分歧。无证据绕过：实验端独立强制该政策（single 必需 `app/projections/control_calculation_experiment.py:84-86`；过期→UNKNOWN `:87-88`；日期须合格且已计算）。最小修复：把属性过滤传入 `:63`，仅为口径对齐。
- **极性/否定边界答复** 声明式拆分在本限定内充分，依据三条结构闸：(a) wire6 仅 CALENDAR_LOOKBACK 可附 time_constraint，非日历范围禁止附窗（`app/agents/protocol_control_deconstructor.py:556-560`）；(b) prompt3 明令“未被 time_constraint 明确表示的时间限定仍属原文理解，不得删改”（`app/llm/proposition_evidence.py` 提示新增行）；(c) v2+时间结构上必须声明 date_range 操作数（contract `:125-127`）且准入前须有合格同事实日期与已计算窗口，否则 UNKNOWN。残留歧义（窗口同时留在命题内=双重表示）不可结构消除，但其失败方向安全：日期 UNKNOWN → UNKNOWN（`control_calculation_experiment.py:82-83`）阻断仅凭关系下 FALSE；日期 FALSE+contradicts → FALSE 与计算结果一致。拆解保真度归 pending 评测/审批（F2），不构成临床接受。

### 已核实正确（证据）
1. 同事实合格日期：选择端 `qualified_binding_selection.py:487-495` 仅用 usable（严格通过）日期配对、要求 v2+date_range+`set(fact_ids) ⊆ 日期事实`，否则 `declared_time_operand_not_qualified`；日期 pair_id 并入 usable_pair_ids 可见。计算端用该事实 `fact.date_range`（`app/projections/control_operand_calculation.py:96-108`）；合格日期配对蕴含 date_range 非空（结构 `fact_attribute_missing` 拒绝）；record_time → UNKNOWN（`:101-108`）；锚点仅取冻结 episode（`:67,109-112`）。
2. 合取语义：entails+interval-false→FALSE（失败合取 `:96-97`）；contradicts+time-true→FALSE；event_membership false→UNKNOWN 不推无他事件（`:89-90`）；source_validity 须 single 且 false→UNKNOWN（`:84-88`）；date UNKNOWN→UNKNOWN（`:82-83`）；reader 只见约束不计算（prompt3 注入 `time_constraint/time_purpose`，提示“日期由代码另行核算，不能仅因未算日期否定内容”）。
3. 确定性不变：`_conditional_observation` `:111-142` 与 v7 逐行一致；`_calculate_operand` 确定性分支未动（`:78-80` 仅 v2 非确定性放行）。
4. v1 兼容：v1 语义+时间双闸拒绝（选择 `:489` 版本不符 + 计算 `:78-80` unresolved→`_proposition_observation:79` UNKNOWN）；v1 语义无时间仍可准入（与 v7 行为一致）。实验 Literal 保留 v3-v8（`:26`）。
5. 版本绑定：consumer v8 双 Literal（contract `:56,:136`）；evaluator v11（`frozen_review_calculation.py:27`，命令/发布经常量导入钉住）；experiment v8 Literal+payload（`:26,:259`）；proposition consumer v2/prompt v3/wire6/prompt2.2/gate v6——冻结 v2 提示的在途 v4 工作流将在推进/重试/发布/挂接四处显式 fail-closed，不静默续跑。
6. source_validity 豁免扩展：validity_specs 纳入 v2 非确定性 single+date_range 规格（`qualified_binding_selection.py:346-357`），下游实验强制政策。
7. 多事实 any/all：逐事实观察=内容∧各自窗口——ANY-TRUE 见证须窗口内 entails；ALL-FALSE 可来自 interval 失败或 contradicts；反向/穷尽仍 UNKNOWN（`:63-69`）。D1 修复确认：pair-id 比较（`:483-486`）。
8. 未来/频次：predicate occurrence/prospective 窗与 atom.prospective_period → unresolved→UNKNOWN（operand `:82-87`）。

### 未决（非源码缺陷）
审批 gate 数据仍未签（须覆盖 consumer8/evaluator v11/prompt3/wire6）；拆解保真与临床效果归 pending 评测；无运行/测试证据（编译通过为 owner 声明）。
