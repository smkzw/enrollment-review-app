所有证据已收集完毕（五个文件全文 + 相邻依赖：原入口三处调用方、`observation_selection.py` 合同、`evaluate_time_constraint` 签名、`repeat_review_presentation.py`、版本标记）。以下为完整会议输出。

# 会议输出：r05-no-repeat-source-20260916 - evidence_single_object（第二轮：复查与日期选择相容性）

## 输出

### 0. 角色与限制声明

继续同一有界只读角色（回退 `zcode`/`GLM-5.3-Flash`，effort max）：本轮只读审阅，未修改任何文件、未运行测试/导入/对象构造/模型/服务/DB/浏览器。**新代码仅经静态阅读核验，未运行验收**；全部结论为仅源码级。

### 1. 上轮决议落实核验（仅源码证据）

- **F1 已修，核验通过**：`repeat_result_selection.py:61-63` 现在凡将选中初查组（`result_use=="retain_initial"` 或零复查）一律要求 `roles.get(initial_group_id)=="initial"` 且 `initial_scope_complete is not True` 即阻断——False 与缺失（None，resolution:146 的 `.get` 链）都进入 `repeat_initial_scope_unverified`，fail-open 已消除。零复查路径保留全图检查：structural（:67）、roles（:69）、scope（:71）、祖先闭包（:86），与“零复查保留全 scope 和图检查”一致。两条直接可达场景（含上轮 (a) `result_use=use_last_repeat`+零复查+initial_scope_complete=False）均被 ：62 阻断。
- **F2 已落实**：`repeat_result_required_not_supplied`（selection:59）单列 `no_result` 政策。
- **F4 驳回，接受**：核实 `frozen_review_calculation.py:27`（`component-review/v29`）与 ：169 的版本门、`frozen_review_publication.py:31`（`frozen-review-publication/v11`）与 ：99-100 的双版本门——正式计算/发布确有独立版本隔离，旧产出在进入结果链前已被版本门拦截。我上轮“仅凭同为 resolution/v1 推断旧错误已存在”确实过度推断，收回该风险等级。

### 2. 本轮新增代码逐项核验（对照指定审重点）

**(1) 直接可达异常**：逐行追踪未发现。关键风险点均安全——reconcile:19 的 `policy_selection["combination"]` 索引由短路条件保护（`len(selected_group_ids)!=1` 先行返回；selected 非空时 `policy_selection` 必非 None，resolution:160-171）；`representatives.values()` 均属已在 ：24 核过 `set(ids)<=set(facts)` 的组；`select_qualified_observation_dates:98` 的 `facts[fact_id]` 由调用侧同源字典构造保证；`evaluate_time_constraint`（expression.py:312-329）对缺失 anchor/日期返回 UNKNOWN 而非抛错；atom calc:187 的 `*(a + b or c)` 优先级正确且 `unknown()` 内 `sorted(set())` 去重，避免 resolution 与 ordering 理由重复堆叠。

**(2) 时间/来源保护无遗漏**：窗口顺序一致性双重校验（合同 observation_selection.py:98-99 + select:85-87）；`within_window` 仅排除 FALSE、UNKNOWN 留在候选内，若其胜出则 ：129-133 以 `observation_window_membership_unverified` 阻断；`before_window_check` 先选后核，选中者 FALSE/UNKNOWN 分别以 out_of_window / membership_unverified 阻断；缺日期界 → `ordering_date_missing`（:99-100）；并列/区间重叠 → `observation_tie_unresolved`/`observation_order_ambiguous_partial_date`，**无按 fact ID 破平局**（:124-127），杜绝有利替代；ordering 严格区间支配（latest 要求 `lower > other_upper`，:119-123）。reconcile 未向 select 传 `conflicting_fact_ids`（:42-46 缺省 ()），但代表值是组内成员、全组已在 ：31-32 做过冲突交集检查，保护等价。

**(3) 同次多记录不当多次 / 只取一值**：未发现。同一采集组先要求日期哈希全等（reconcile:33-37），`min(ids)` 仅为日期排序代表（:40，注释明示）；组内**全部**成员仍在 group_results 中逐条计算（atom calc:163-183），真值为组内 ALL 合取、数值冲突/语义矛盾仍阻断（:173-176），`observed_value` 仅在组内值全等时透传（:181-183）。代表值不参与结果值选取——最终值来自 `group_results[chosen]`（:189），与“不选其结果值，组内所有结果仍计算”一致。

**(4) 排序失败仍采信**：未发现。ordering 理由与 resolution 理由合并进 UNKNOWN（atom calc:186-187）；`agrees_with_repeat_selection` 不等 → `repeat_ordering_policy_disagreement`（reconcile:52-53），不得换有利组；审计字典无条件嵌入 `resolution_sha256`（atom calc:215-224），防篡改。ordering 仅在“已选唯一组且 combination 为 None”时运行（reconcile:19）；combine/any+ordering 显式返回 `repeat_ordering_combination_unverified` → UNKNOWN，与“多组聚合与排序未实现、不声称完整”一致；无 selection 政策时 reconcile 返回 `((), None)`（:11-12）且 `fact_result` 相应放行（atom calc:132-133 移除 blanket UNKNOWN），这些方案与改动前**逐字节同哈希**（audit 不加键），无行为漂移。

**(5) 原入口重构行为变化**：无。三处原调用方（repeat_condition_selection:130、semantic_observation_selection:161、qualified_binding_selection:322）仍调用原入口 `select_ordered_observation`；入口保留全部前置检查（ordered_observation_selection.py:54-64）并透传全部实参（含 `conflicting_fact_ids`:69）；抽取函数复述的前缀策略检查（:82-87）幂等。审计产出形状与 `OrderedObservationExclusion` 的 Literal 理由集一致（:113/:132/:134 vs observation_selection.py:11）。

**(6) date_range 与 effective_date 无错用**：已核对。排序链一致使用来源侧 `originals`（ClinicalFactV2 `.date_range`，atom calc:108 → reconcile:33-34/:98）；组内日期一致性用计算侧 context facts（`.effective_date`，:169-170）；`effective_date` 是 `date_range` 的确定性投影（:41 `_phase3_date_value`），两套哈希从不跨用比对。

**(7) 冲突集合来源**：`conflicting_fact_ids` 由计算 context facts 的 `conflict_group_id` 构建（atom calc:113），与 `fact_result:126` 同源；reconcile 用其对全部组员做交集（:31-32）。一致。

**(8) 排序审计只读**：`repeat_review_presentation.py:11-18` 仅 `resolution.get("observation_ordering")` 读取 criterion/agreement 呈现，键位在 reconcile:13-16 恒存在，`.get` 对旧存档（无该键）安全跳过；无重算。版本标记 `component-review/v29`、`frozen-review-publication/v11` 与声明一致。

### 3. 缺陷结论

**本轮未发现确证缺陷**——无直接可达异常、无被绕过的时间/来源守卫、无同次多记当多次或单值摘取、无排序失败仍采信、无入口行为漂移。按“不发明缺陷”约束，如实报告零确证缺陷，并附三条诚实标注的**非缺陷观察**：

- O1（既有行为，非本轮引入）：窗口成员资格仅用 `date_range.lower_bound` 作事件日期（select:107），宽区间记录可能偏宽纳入窗口；原入口与复查排序共用同一约定（`effective_date` 同源），语义一致，属全库既有口径，如需收紧应另行立项。
- O2（命名）：`observation_order_ambiguous_partial_date`（select:126）实际覆盖“区间重叠”歧义，含非部分日期情形；失败关闭方向正确，仅命名欠准。
- O3（设计说明，非缺陷）：ordering 候选集为整个对应关系图分组，隐含“图范围=政策 scope 范围”的既有解释（与入口路径对 operand 候选的解释一致）；若方案文本 scope 与图范围不符，表现为 disagreement→UNKNOWN，失败关闭而非误采。

### 4. 未验证项声明

未运行任何代码：上述全部为静态阅读结论；ordering 与 selection 在真实数据上的联合行为（尤其 use_last_repeat 拓扑序与日期序不一致场景）未有用例执行证实；`observation_relation_graph.py`/`repeat_numeric_result.py` 等更深依赖未在本轮读取集内展开；三条观察项（O1-O3）未验证其临床出现频率。多组聚合与排序、条件性缺席（trigger FALSE）均未实现且本轮代码未声称完成——与声明一致。
