# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**Fallback 声明**：主角色 `codebuddy/codebuddy-cli/deepseek-v4.1-flash` 在存在可续会话前不可用，本会话按 runner 裁决以 `zcode`/`zcode`/`GLM-5.3-Flash`（effort max）执行同一 `evidence_single_object` 角色，保持同一读集、边界、质量门与串行协议。能力限制：无写入、无应用导入、无测试/数据库/浏览器/模型调用，符合任务边界本身；本角色不产出也不自称最终临床、视觉或产品验收，均归 Codex。读集内的 18 个指定源文件全部完整读完，另按具体依赖扩展读取 6 个相邻定义（repeat_scheme、observation_selection、observation_relation_graph、repeat_series_constraints、repeat_result_selection、evaluation_result、repeat_observation_count、deconstruction_gate 频次段），未读 raw 病例/凭据/历史日志。所有建议为设计建议，owner 整合。

---

### 0. 结论摘要（TL;DR）

1. **频次消费当前在四个层面全部硬阻断**：官方求值 `expression.py:505-506` 返回 `occurrence_scope_unverified`；控制操作数 `control_operand_calculation.py:82-85` 返回“频次或未来期间仍需独立核实”；命题路径 `proposition_context.py:25-26` 直接拒绝含 `occurrence_window` 的条件；缺口侧 `assessment.py:207` 把该原因折叠进 `OBSERVATION_UNVERIFIED`。不存在任何一条频次生产→消费通路，接线是纯增量。
2. **合同能表达“有窗”，不能表达“是什么窗”**：`OccurrenceWindow`（`rules.py:167-171`）只有 `duration + minimum_count`，无滚动/固定声明、无锚点依据、无逐字来源绑定；而解构门 `_source_frequency_specs`（`deconstruction_gate.py:1043-1084`）已经在解析“X内…N次”“X内≥N天”“每…≥N天”三种原文形态——“每…”（固定期间）信息在合同层被丢弃。
3. **最小接线不新起队列**：完整复用既有四段式（`JudgmentContentJobExecutor` 双路任务 → `qualified_*` 版本化消费者 → sealed 求值合同 → `_evaluate_bound_predicates` 映射注入）。`repeat_evaluations`（`expression.py:675-690`）就是频次映射的现成模板；`RepeatAtomEvaluation`（`evaluation_result.py:20-46`）就是封存求值的现成形状；`evaluate_repeat_count`（`repeat_observation_count.py`）就是“已知下界按比较方向决定结果”的现成先例。
4. **逐次计数只需 `same_acquisition` 合并**：对计数而言，初查/复查排序无关紧要，只有 same_acquisition 合并影响组数；`analyze_observation_relationships` 的 acquisition-group 原语可直接复用，不必把复查链语义搬进频次。
5. **最高影响缺陷（对 owner 取舍的主动异议）**：频次谓词上 `occurrence_window` 与 `repeat_scheme`、与 `observation_policy` 的共存语义在合同层均未定义；且“任何连续X周内”这类滑动窗与“近X月内”这类回溯锚定窗在 `duration` 字段上完全同形——若不先在声明层区分，逐次计数的算法选择就没有合法输入。建议第一增量在合同层显式拒绝/保留 unresolved，而不是让消费端猜。

---

### 1. 证据：现状全景（evidence，均带 file:line）

**1.1 生产侧（方案解构已结构化频次）**

- `OccurrenceWindow`（`app/domain/contracts/rules.py:167-171`）：`duration: TimeQuantity` + `minimum_count: int|None`，docstring 写"Rolling duration used by frequency definitions"——滚动是**散文暗示**，不是合同字段。
- 配套校验（`rules.py:271-283`）：`occurrence_window` 必须与三者之一配对——数值谓词 unit=`次`（汇总次数）、数值谓词 unit∈{天,日,day,days}（发生天数）、或 `minimum_count` 非空（括号定义最小次数）。三类形态在合同层已预留。
- `semantic_proposition` 与 `occurrence_window` 互斥（`rules.py:307-310`）；与 prospective 字段亦不可混用（`protocol_deconstructor.py:2142-2145`）。
- 解构提示与 wire 校验只接受 duration/minimum_count 两字段（`protocol_deconstructor.py:1895-1914`，未知字段拒绝）；草稿投影透传（`protocol_draft_service.py:465,499,509`）。
- 解构门（`app/protocols/deconstruction_gate.py`）：`history_pattern`（X 天/周/月/年内…发生/发作 N 次＝**滚动+汇总次数**）、`occurrence_day_pattern`（X 内≥N 天＝**滚动+发生天数**）、`every_period_day_pattern`（每 周/月/年…≥N 天＝**固定期间+发生天数**）（1043-1084）；`_predicate_preserves_frequency` 强制频次结构绑定在含频次原文的子句上（1099-1139）；`FREQUENCY_WINDOW_NOT_STRUCTURED`/`FREQUENCY_WINDOW_NOT_IN_SOURCE` 双向把关（2262-2285）；无锚点“内”字回溯在**非频次**条件上报 issue（2174-2185）——频次条件的锚点未决被静默豁免。

**1.2 消费侧（四处全部阻断）**

- 官方：`_evaluate_atomic`（`app/domain/expression.py:505-506`）`occurrence_window is not None → UNKNOWN/occurrence_scope_unverified`，先于 observation_policy 处理。绑定路径 `_evaluate_bound_predicates`（621-708）对 `repeat_evaluations`/`proposition_evaluations` 有完整的映射注入先例：键⊆对应原子集、与其它映射不相交、context_sha256 绑定、source_fact_ids⊆accepted、used_fact_ids==selections、未核实原子强制 UNKNOWN（691-705 分派链）。
- 控制：`_calculate_operand`（`app/projections/control_operand_calculation.py:82-85`）对含 `occurrence_window/prospective_*` 的谓词整体返回 unresolved。注意 `ControlAtomEvaluationSpec` 本身**允许** deterministic+value_comparison+携带 occurrence_window 的谓词（`control_evaluation_spec.py:55-58` 只要求 operation↔predicate 配对），阻断仅在操作数计算一处——控制族增量是局部的。
- 命题：`proposition_context.py:25-26` 显式拒绝 `occurrence_window`（"混入需要另行核实的数值、频次”）；`_evaluate_atomic:503-504` 对 semantic_proposition 同样 UNKNOWN。数值频次伪装成 entails 的通道在合同、上下文、求值三层都已被堵死——**这条边界已是既成事实，新接线不得重新打开**。
- 缺口报告：`app/domain/gates/assessment.py:207` `occurrence_scope_unverified → GapType.OBSERVATION_UNVERIFIED`，与普通观察未核实同桶，无频次专属原因。

**1.3 事实/事件侧（为什么“数行数/数身份”在两个方向都错）**

- `clinical_event_stable_identity`（`app/domain/contracts/facts.py:651-675`）= hash(authority, event_type, referenced_fact_objects, start_range, end_range, duration_status)。两条临床独立发作若类型、引用对象、日期范围、持续状态全同（如同日两次、同月精度两次），**稳定身份相同**。
- `_publish_events`（`app/services/fact_publication_service.py:489-585`）按该身份分组，同组候选折叠为一行发布（revision 链除外）。推论（inference，机制必然）：发布事件行数既可**低估**（同范围独立发作合并）也可**高估**（同一发作跨 run/更正链多行）——行数既不是下界也不是上界。设计文末边界“频次不能直接 count 事件、事实或定位条数”由机制证实。
- `PartialDateRange`（facts.py:122-171）月/年/未知精度是常态：发生天数的“不同自然日”计数在部分日期下只能得到区间界；未知精度事件不得借任何日期。
- 极性：`NEGATED` 事实不得计入发生；`UNKNOWN` 极性不得携带值（facts.py:204-224）。

**1.4 可复用机器（现有双路任务与确定性计算先例）**

- 观察关系族：`observation_relation_input.py`（输入选择**仅限 `repeat_scheme is not None` 的身份**，40-62 行）、`observation_relation_receipts.py`（JOB_TYPE=`observation_relation`，双路 main-A/B、agreement_key 求交集、争议保留、`accepted=False`）、`qualified_observation_relation.py`（`OBSERVATION_CONSUMER_VERSION=v8`，方法评测 kind=`observation_relationship_fidelity`，逐引用来源资格、`supplied_scope` 完备标志+原因码、`episode_memberships`）。
- 关系图：`analyze_observation_relationships`（`app/domain/observation_relation_graph.py`）——union-find 把 `same_acquisition` 边折成 acquisition group（group_id=内容哈希），`repeat_of` 有向边仅用于链检查；未连边记录成为单例组并入 `unclassified_fact_ids`。**对计数：单例=保守独立（可能同次未证明），合并仅凭双路一致+来源资格。**
- 计数先例：`repeat_series_constraints.calculate_repeat_series_constraints`（`app/domain/repeat_series_constraints.py`）——按 acquisition group 计数（非行数）；`per_current_episode` 需逐组成员资格证明+episode_sha256；`per_initial_acquisition` 需唯一初查且所有复查可溯祖。`evaluate_repeat_count`（`repeat_observation_count.py:34-44`）的方向逻辑：部分集可证“超上限→FALSE"；未超+范围不完整→`repeat_count_coverage_incomplete/UNKNOWN`。这正是“已知下界能否决定结果取决于原比较方向”的已实现形态。
- 声明合同模板：`RepeatScheme`（`repeat_scheme.py:94-191`）的 `count_status specified/not_specified/unresolved` + `maximum_repeats` + `count_scope`，状态/值成对校验（“明确次数须同时保留计数范围”）；`ObservationPolicy`（`observation_selection.py:63-99`）的 scope+逐字来源+`window_order`（within_window/before_window_check/not_applicable）。
- 封存求值形状：`RepeatAtomEvaluation`（`evaluation_result.py:20-46`）：context_sha256/atom_sha256/resolution_sha256/source_fact_ids/result/resolution。
- 方法批准：`require_proposition_method`（`qualified_proposition_evidence.py:11-25`，kind=`pair_local_proposition_relation`）与 `require_observation_method`（`qualified_observation_relation.py:15-26`）——逐字段匹配 binding_method/content_contract/prompt/summary/routes/consumer_version。
- 任务执行器模板：`ObservationRelationJobExecutor(JudgmentContentJobExecutor)`（`observation_relation_job.py:10-27`）——8 个 staticmethod 钩子即可派生同族任务，无新队列。

---

### 2. 四类区分的逐一核对（evidence + inference）

| 区分 | 原文形态 | 生产侧现状 | 消费侧现状 |
|---|---|---|---|
| 汇总次数 | “5年内发作3次”；或裸总数“既往共发作3次” | unit=`次` 数值谓词+window.duration（gate 已解析“内”形态） | 谓词比较可直接复用 `evaluate_observed_value`；**缺失的是“声明总数+覆盖期间”的核实工件**——命题路径按构造拒绝频次谓词，`entails` 无法承载总数与期间 |
| 逐次事件 | 逐条发作记录，需核同次/异次/未明 | 关系任务仅服务 `repeat_scheme`（`observation_relation_input.py:40-62`），频次谓词的关系无处声明 | acquisition-group 图+计数先例可复用；缺频次侧的资格选择与计数调用 |
| 发生天数 | “6个月内≥N天”“每月≥N天” | unit 天/日 已预留；`every_period_day_pattern` 已解析“每…" | 无任何按“不同自然日”去重计数的确定性代码；部分日期区间传播缺失 |
| 滚动 vs 固定 | “近/过去X内”（回溯锚定）vs“每X"（日历期间）vs“任何连续X周"（滑动） | 三种原文形态 gate 都能**看见**，但 `OccurrenceWindow` **存不下**种类与锚点；`is_unanchored_lookback` 对频次豁免（gate:2180） | 求值无窗口应用代码；锚定回溯/滑动/固定期间的算法互不可换（设计文末明令） |

**关键推断（inference）**：滑动窗（"任何连续4周内≥2次”）与锚定回溯（“筛选前6个月内≥2次"）在现合同中**同形**（都是 `duration=4周/6月`），但算法截然不同（后者=单区间计数；前者=暴露期内任意滑窗的最大计数，部分日期下界复杂）。若合同不先声明量词，消费端任何选择都是机械默认——正撞 owner“不用机械默认补齐”的红线。

---

### 3. 缺口清单（每项含证据与建议落点）

- **G1 范围/量词声明缺失**（rules.py:167-171；gate:1043-1084）：`OccurrenceWindow` 需要显式 `window_quantifier` 类声明（回溯锚定/固定期间/滑动连续/unresolved）+ 逐字来源绑定。落点：`app/domain/contracts/rules.py`（新版本 literal，历史序列化按 house 风格 pop 保留）、同步 `protocol_deconstructor.py` wire 校验（1895-1914）与提示、`deconstruction_gate.py` 门禁、`protocol_draft_service.py` 投影。
- **G2 解析器不对称**：`every_period_day_pattern` 只认“每…≥N天”，不认“每…N次”（如“每月发作≥4次”这一常见固定期间计数形态，gate:1053-1057 无对应 pattern）。按 owner 取舍，缺形态应显式保留 unresolved/补声明，不得默认按滚动处理。
- **G3 汇总核实工件缺失**：无任何合同承载“原文声明总数 N+声明期间 P+P 与谓词窗口 W 的覆盖关系”。命题族的 `relation=entails/contradicts` 结构性不可用；需要频次专用读取合同（见 §4 步骤2）。
- **G4 关系任务范围**：观察关系输入按 `repeat_scheme` 选择身份（observation_relation_input.py:40-43,60-62），频次谓词进不去；且该任务提示词深绑初查/复查词汇，直接扩选集会改变已批准复查方法的提示身份（版本绑定→复查族需重新评测批准）。
- **G5 发生天数计算器缺失**：需要独立的“不同自然日并集”确定性计算（区别于组计数），处理部分日期区间界与窗口成员歧义传播。
- **G6 共存语义未定义**：`occurrence_window × repeat_scheme`（`_evaluate_atomic` 先判 repeat，expression.py:501-502；合同未禁同存）、`occurrence_window × observation_policy`（single/any/all 表达的是选取，不是计数聚合）均无约束。
- **G7 计数端不确定性传播**：`evaluate_time_constraint` 已有 partial-date 区间与 `ambiguous_time_window` 语义（expression.py:312-476），但计数侧无等价物；月/年精度组的窗口成员歧义须转为计数区间加宽而非 TRUE/FALSE。
- **G8 报告侧同桶折叠**：`occurrence_scope_unverified→OBSERVATION_UNVERIFIED`（assessment.py:207）；频次落地后报告须区分“原文声明总数/逐次代码计数/发生天数”三种计算方式与参与范围，沿用 2026-09-15 复查来源补充的“合并结果必须明确参与范围及计算方式；未明不默认”模式。
- **G9 控制族规格**：`ControlAtomEvaluationSpec` 无需新增 operation（value_comparison 已可携带频次谓词，control_evaluation_spec.py:55-58），增量集中在 `_calculate_operand:82-85` 分支与控制族资格消费者。

---

### 4. 最小完整接线建议（recommendation；只给落点与设计选择，不给代码补丁）

总原则：复用 `JobRunner/JudgmentContentJobExecutor` 同族任务（不新增队列）；复用双路对账与逐字来源资格；复用 acquisition-group 图与方向相关计数先例；sealed 求值+版本化方法批准；汇总与逐次永不相加；不数行数、不数身份、不虚构事件；prospective/future-statement 消费已存在（命题链 ProspectiveEvidenceCheck），**不在本接线范围内重复施工**，频次谓词若带 prospective_* 仍走既有阻断。

**步骤0 — 合同声明（一切的前置）**
`OccurrenceWindow` 增加：范围量词声明（建议单字段 `window_quantifier: within_lookback | per_period | any_consecutive | unresolved`，一并回答滚动/固定与锚定/滑动）、固定期间的期间单位（per_period 时必填）、逐字 `source_span_ids/source_excerpts`（镜像 ObservationPolicy/RepeatScheme 的来源合同）；新版本 literal，旧载荷原样可读（空字段 pop 序列化）。同步 wire/提示/门/草稿投影四处（G1 落点）。同时定死共存语义（建议第一增量：与 `repeat_scheme` 同存、与 `observation_policy` 非 unresolved 模式同存，均在合同层拒绝——语义未定义前不得静默择一，见问题 Q2/Q3）。

**步骤1 — 频次声明读取任务（生产，同族新任务）**
新建 `FrequencyEvidenceJobExecutor(JudgmentContentJobExecutor)`（落点建议 `app/services/frequency_evidence_job.py` + receipts，合同 `app/domain/contracts/frequency_evidence.py`，提示 `app/llm/frequency_evidence.py`）。逐配对双路输出（**结构化字段，不是 entails/contradicts**——这是“不把数值频次伪装成普通语义 entails”的具体形态）：`statement_kind: aggregate_total | per_occurrence_records | occurrence_days | unresolved`；总数逐字引用+精确值；声明期间逐字引用；逐次集内两两 `same_acquisition` 声明（同次才合并，**未声明≠异次，异次不需要证明**——未合并按独立计是保守上界方向）；显式 unresolved 原因。双路按 agreement_key 求一致，争议逐配对保留（沿用 observation_relation_receipts 的 compose 模式）。分批复用 `plan_judgment_content_batches`。方法评测注册新 kind（如 `frequency_statement_fidelity`），隔离运行 `accepted=false`。

**步骤2 — 确定性计算（纯函数，落点 `app/domain/occurrence_constraints.py`，镜像 repeat_series_constraints/v2 形状）**
输入：窗口声明 sha、合格配对与图、事实日期、锚点（经冻结 episode）。语义：
- 汇总：声明 N+期间 P 与窗口 W 的覆盖关系转不等式约束——P⊆W ⇒ count(W)≥N（下界）；P⊇W ⇒ count(W)≤N（上界）；部分重叠⇒按日期精度转区间或 UNKNOWN+原因。**约束与逐次计数按区间交集合并（lo=max, hi=min），绝不相加**；声明总数与已核实逐次数在同一期间内矛盾（如声明3次但已核实4次不同发生）→ 显式来源冲突，UNKNOWN，双方保留。
- 逐次：acquisition group 数=已核实合并后的不同发生数；方向相关判定（先例 `evaluate_repeat_count`）：观测下界已越阈值（如已见≥N次且谓词为 GTE）⇒ TRUE 与范围完整性无关；未越+范围不完整 ⇒ UNKNOWN；未越+范围完整 ⇒ FALSE。**"未提供记录≠未发生”由此机制保证**，无通用 TRUE 见证。
- 发生天数：不同自然日并集大小；日精度贡献确定日，月/年精度贡献区间，未知精度只加范围疑问；同日两次独立发生=1天（天数与次数分开报告）。
- 窗口应用：within_lookback 用谓词外层 time_constraint 锚点（复用 `evaluate_time_constraint` 的区间/歧义语义于“计数窗口”）；per_period 按声明期间逐段求值后按“每”语义合并（ALL 型）；any_consecutive 第一增量保留 `occurrence_window_sliding_unsupported` 类 unresolved（合同已声明量词，不算静默降级）。
- 输出：`occurrence-constraints/v1`：计数区间 [lo,hi]、分段结果、scope_complete、全部 sha256 绑定、`replacement_authorized=false`。

**步骤3 — 封存求值+方法批准**
`OccurrenceAtomEvaluation`（镜像 `RepeatAtomEvaluation`：context/atom/resolution 三 sha256+source_fact_ids+result+resolution）；方法 kind 与 consumer 版本 literal（如 `qualified-occurrence-evidence/v1`）；`require_*_method` 克隆逐字段版本匹配。隔离评测清单须覆盖：声明总数期间覆盖/部分覆盖、逐次同次/异次一致与争议、部分日期天数区间、滚动/固定互混反例、方向相关界、汇总与明细冲突、拒绝虚构展开。采纳走既有三层批准（§17.6），不自动。

**步骤4 — 消费接线（两个对称入口）**
- 官方：`_evaluate_bound_predicates` 增加 `occurrence_evaluations` 映射，校验完全镜像 `repeat_evaluations`（expression.py:675-690：键⊆含 occurrence_window 原子、与 repeat/proposition 映射两两不相交、context_sha256、source⊆accepted、used_fact_ids==selections）；分派链（691-705）在 repeat/proposition 之后、`_evaluate_atomic` 之前消费；未供结果的频次原子保持 `occurrence_scope_unverified`，不静默回退。
- 控制：`_calculate_operand:82-85` 的频次分支改为消费合格 occurrence-constraints 结果；操作数仍出自冻结输入与已选事实，`accepted=false` 边界不动。

**步骤5 — 报告与解释**
计数/声明值、覆盖期间、计算方式（声明总数/逐次计数/发生天数分列）、资料范围说明、逐源引用进入审计与报告；`assessment.py` 缺口映射为频次专属原因码扩列（区分“声明期间未核实/计数范围不完整/滑动窗未支持/汇总明细冲突”），不与普通观察未核实同桶。

**实施顺序**：0→1→2 可并行推进（合同先行阻塞后两者）；3→4→5 依赖 2 的形状；全链完成后按 T4 统一集中验证，不新增阶段性测试轮次。

---

### 5. 反例集（scope 要求；每条可直接成为评测用例）

1. **数行数**：同日两次发作（同类型/对象/日精度范围）发布为 1 个事件行 → 行计数 1 < 真值 2；同一发作跨两次运行 → 行计数 2 > 真值 1。
2. **数身份**：两条同语义独立事实 stable_identity 相同 → 合并低估；同身份多 revision → 高估。
3. **汇总+明细相加**：声明“共4次”+已核实2条逐次记录=6 次是虚构；正确为区间约束交（≥4 且 ≥2 ⇒ lo=4；上界不受逐次加宽）。
4. **滚动/固定互换**：“近3个月≥2次”按“任一日历月≥2次”或“每3个月≥2次”求值均错；“每月≥15天”按滚动30日滑窗求值错。
5. **方向盲判定**：已见1次、阈值≥2、范围不完整 ⇒ 必须 UNKNOWN（非 TRUE 亦非 FALSE）；已见2次 ⇒ TRUE 与完整性无关。
6. **虚构展开**：由“病史记载发作3次”合成3个 ClinicalEventV2 —— 禁止；汇总保持声明态。
7. **部分日期天数**：“2023年3月发作”对“≥5天”不能贡献确定天数，只能贡献 [1,31] 型区间界。
8. **minimum_count 伪装**：括号定义最小次数（“频繁发作（每月≥2次）"）不得当作谓词自身 value 直接比较；声明量词与被比阈值须各自对应原文。

---

### 6. 对 owner 取舍的主动异议与修正建议（active-peer challenges）

1. **异议（最高影响）**：取舍说“先支持原文直接记载的总次数/发生天数并核期间”——方向正确，但**“核期间”需要窗口量词声明先行**：没有 within_lookback/per_period 的声明，"P 与 W 的覆盖关系”无从计算，汇总核实会退化为只比对数字。建议把步骤0（合同声明）定义为汇总支持的前置而非并行项。
2. **异议**：“裸总数无期间”的形态（“既往共发作3次”）：现 gate 的 history_pattern 必含“X内"，裸总数不会产生 occurrence_window → 走普通数值谓词路径即可，无需频次机器（**推断**：`validate_comparator_value:271-283` 允许 direct_count 不带窗口）。建议 owner 明确这一读法（问题 Q5），避免为它强造 duration。
3. **修正**：逐次关系不必复用整个观察关系任务——计数只需 `same_acquisition` 合并（初查/复查排序与计数无关，`repeat_of` 链仅用于链检查）。把 same/different 声明并入频次读取任务、复用图分析器与计数器，是改动面最小且不触碰已批准复查方法身份的路径（与 Q1 的取舍联动）。
4. **提醒**：`every_period_day_pattern` 不认“每…N次”（G2）——固定期间+计数的常见形态现在会**静默无结构**。不补默认，但至少要让解构门在见到“每…N次”时显式报“频次形态未支持”而非沉默。

---

### 7. 有界决策问题（请 Codex 裁定；均附安全暂行走向）

- **Q1 频次逐次关系任务形态**：新建同族 sibling 任务（我的建议：不动复查方法批准身份）vs 扩展 observation_relation v5→v6 纳入频次 owner（单任务，但 OBSERVATION_RELATION_VERSION 升版触发复查族重评测）。暂行：sibling。
- **Q2 `occurrence_window × repeat_scheme` 同存**：合同层拒绝（我的建议：语义未定义）vs 定义求值优先级。暂行：拒绝并要求解构期拆分或保留 unresolved。
- **Q3 `occurrence_window × observation_policy`**：single/any/all 表达选取而非计数聚合，是否同样拒绝非 unresolved 共存？暂行：拒绝。
- **Q4 滑动连续窗（any_consecutive）**：合同声明但第一增量求值保留 unresolved，是否可接受？暂行：是（声明在、不静默）。
- **Q5 裸总数（无期间声明）**：按普通数值谓词走既有路径、仅在存在窗口时核期间覆盖，是否符合“汇总次数并核期间”的本意？暂行：是。
- **Q6 控制族**：是否同意第一增量不扩展 `ControlAtomEvaluationSpec`（现有 value_comparison 已可携带），只扩 `_calculate_operand` 消费分支？暂行：是。

---

### 8. 不确定性与未验证范围（honesty 边界）

- 本审阅为纯静态源码阅读；未运行任何代码、未构造对象、未访问数据库——`occurrence_scope_unverified` 的实际线上触发频率、真实方案语料中“每…N次”等形态的分布，均未实测，仅为机制推断。
- `app/llm/observation_relation.py`（提示正文）与 workflow 编排细节（父工作流子任务挂接的具名函数）不在指定读集内，步骤1/4 的挂接点描述基于 `observation_relation_job.py` 执行器与 receipts 契约推断；接线实施前需 owner 核对父工作流 v6 的子任务注册面。
- 方法评测清单（§7 步骤3）为建议覆盖面，正式金标/留出划分与评分版本归既有评测规程，不由本角色定义。
- 判定标注：§1 全部为 evidence（带 file:line）；§2 表格“消费侧现状”列与 §3 的机制推论为 inference；§4/§5/§6 为 recommendation；§7 为待决问题。

会话保持可续：Codex 可就 Q1–Q6 或任意证据点在本会话发起定向 follow-up。
