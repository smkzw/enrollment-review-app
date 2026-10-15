# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本设计基于本会话已完整读过的 `OccurrenceScope` v3、`TimeConstraint`、`evaluate_time_constraint`、`required_frequency_period`、`bound_stated_total`/`bound_distinct_occurrences`/`qualify_individual_days` 及整条频次管线；刚复核 `ProtocolPeriod` 枚举与现行量化路由（`frequency_period_qualification.py:38-39` 一切非 single → `frequency_period_kind_unsupported`）。以下是**设计建议**，owner 决定取舍。

---

### 1. 缺口的精确形状

现有单区间路径能表达“一个计数期间”，缺四件事：**计数地平线**（哪些期间实例进入量化——现 scope 无 horizon 字段；外层 `TimeConstraint` 可能暗示但语义是筛选/成员归属，**不得挪用**，现行 `frequency_outer_window_combination_unresolved` 阻断保持）、**日历期间对齐**（calendar_period 有 kind 无 period_unit——现字段装不下“每月/每周”）、**边界期间政策**（首尾不完整月/周是否计入）、**any/every 组合语义**（∃违反窗 vs ∀期间合规的可判定方向完全不同）。滑动窗时长已由 `window.duration` 携带，不缺。

### 2. 合同最小增量（OccurrenceScope v4，additive；v1–v3 读旧不变、旧版本非 null 新字段拒绝——沿用 v3 先例）

- **`horizon: ScopeHorizon | None`**——计数地平线，仅来源支持四种 basis：`explicit_dates`（start/end 用与 `FrequencySourceDate` 同构的年/月/日分量＋逐字摘录）、`anchor_span`（start_anchor/end_anchor 两个 `AnchorType`——**阶段必须绑定到方案命名锚点对并留逐字依据，不做“治疗期”→锚点的隐式映射**，冻结 episode 无该锚即 unresolved；不建议引入裸 `ProtocolPeriod` 枚举绑定）、`unspecified_lifetime`（来源明确“任何/不限期间”的**正向声明**，带逐字摘录；缺失不默认）、`unresolved`。
- **`period_unit: Literal["week","month","year"] | None`**——仅 `calendar_period` 必填（日历对齐期间），其余 kind 禁止；固定天数周期（“每30天”）归 `any_consecutive`＋`every`，时长用既有 `window.duration`，不加字段。
- **`boundary_periods: Literal["full_only","include_partial","unresolved"] | None`**——仅量化 every＋有限地平线必填；any 语义不需要（∃不枚举全部期间）。
- 校验：`quantifier=single` 禁带以上三字段（单区间路径不动）；`any_consecutive` 禁 `period_unit`。

**频次读取步零改动**——量化归因全部是 occurrence_date/总数期间 vs 枚举期间的代码算术；scope 属解构侧，同步双族 wire（schema 自动内联）＋prompt＋gate，版本按惯例 bump（dnf-v17/control22/prompt2.19）。

### 3. 算法与接口（新纯函数模块 `app/domain/frequency_quantified_periods.py`）

- **`enumerate_calendar_periods(horizon, period_unit, boundary_periods, episode)`**：地平线解析为端点可能性（复用 `_anchor_bounds`/`_source_date_bounds`/`_endpoint_possibilities`），按日历边界切出期间实例（复用 `shift_date`/`date_bounds` 月/年日历语义）；每个期间产出 `(start_possibilities, end_possibilities, boundary: full|partial)`＋`boundary_periods=full_only` 时 partial 期间**整段跳过并记录**（既不算 TRUE 也不算 FALSE——不是未知期间，是不在义务域内）；`include_partial` 时按其覆盖跨度作为独立期间求值，**禁止按比例折算**。地平线 unresolved→整组 `frequency_horizon_unresolved`。
- **逐期间计数**：复用既有件——individual_day 贪心 stabbing（逐期间）、individual_occurrence 组的全世界 inside 分类（逐期间端点）、stated_total 经既有 `bound_stated_total` 期间关系分类匹配到单一期间实例（总数与逐次在期间内仍只交不加以及**跨期间绝不求和**——每期间结果独立，只按量词组合）。每期间产出 `EvaluationResult`：TRUE 需该期间下界≥阈值（stabbing/异次团）；FALSE 需该期间上界<阈值（仅当 `enumeration_complete` 且该期间记录日精度完备——期间级完备是逐期间判定的，不继承全局）；否则 UNKNOWN。
- **量词组合 `combine_quantified_truth(per_period_results, quantifier)`**：every→任一 FALSE 即 FALSE、任一 UNKNOWN 即 UNKNOWN、全 TRUE 才 TRUE；any→任一 TRUE 即 TRUE、全 FALSE 才 FALSE、否则 UNKNOWN。与 `evaluate_count_bounds` 现行“区间内全同真值才给真值”同构。
- **滑动 any/every `sliding_quantifier_truth(inside_groups, duration, threshold, comparator, quantifier, horizon)`**：
  - **精确 TRUE 见证（何时可用，非通用）**：quantifier=any 且谓词为下限方向（gte/gt）时，∃ ≥阈值条**显式 distinct** 发生、其日期区间存在一处 ≤duration 的跨度安放（逐次日期为区间时做“存在逐区间取一天使跨度≤duration”的可行性判定，小 n 确定性可解），且该跨度窗口在地平线域内（`unspecified_lifetime` 恒在域内；有限域需跨度在域界的全可能世界中都入选）——三者齐备才 TRUE；任一不齐保持 UNKNOWN。
  - **精确 FALSE**：quantifier=any 的 FALSE＝全域无违反窗，需**有限地平线＋enumeration_complete＋域内发生全部日精度**（部分日期使跨窗归属有歧义）→ 排序后最大 duration-簇 <阈值才 FALSE；否则 UNKNOWN。quantifier=every（“每连续X周不超过X次”型）方向镜像：TRUE 需全域完备枚举（通常 UNKNOWN），FALSE 只需一个可证违反窗（与 any-TRUE 同一条见证）。
  - `unspecified_lifetime` 下 any 的 FALSE 永远不可得（域无限）——保留 UNKNOWN，不假装枚举。
- **外层 TimeConstraint**：维持现 `frequency_outer_window_combination_unresolved` 阻断不变；量化期间的地平线只来自 scope 自身 horizon 字段，**不得**从外层约束推断或合并——组合设计另行立项。
- **汇总额外约束**：地平线级声明总数（既有 stated_total 通道，期间=整个地平线）按既有交集并入；**每期间结果之间、期间与事件之间一律不求和**（跨期间下界求和虽是逻辑推论，按 owner 红线 v1 不做，留作后续明确分离的可选项）。

### 4. 实施顺序与集成点

1. `occurrence_scope.py` v4 三字段＋校验（先行，阻塞后续）。
2. 双解构器 wire/prompt/gate 同步＋版本 bump；gate 对 `calendar_period` 缺 `period_unit`、every 缺 `boundary_periods` 增提示级 issue（沿用 `FREQUENCY_SCOPE_NOT_DECLARED` 风格）。
3. `frequency_quantified_periods.py`：`enumerate_calendar_periods` → 逐期间计数（复用件）→ `combine_quantified_truth`/`sliding_quantifier_truth`。
4. `frequency_period_qualification` 按 kind/quantifier 路由（single 走原路；calendar/every、any_consecutive/any-every 走新函数；仍不支持的组合保留 `frequency_period_kind_unsupported`——如 calendar_period＋quantifier=any 可作第二小步，仅是逐期间 TRUE 的 ∃组合）。
5. resolution/presentation：resolution 携带逐期间结果与枚举 sha；呈现逐期间列出“某期间未能判定/不满足”＋原文摘录；`individual_calculation`/`day_calculation` 接口不变。
6. 方法评测清单增补：地平线声明保真（阶段→锚点对、unspecified_lifetime 的措辞依据）、边界期间政策、any/every 方向、见证/反驳的正反例。

**有界问题**：Q1 `unspecified_lifetime` 是否要求来源措辞逐字支持才可声明（我的建议：是——它是唯一让 any-TRUE 免地平线的通道，必须防泛化）；Q2 `calendar_period＋any` 是否进第一增量（建议：随后即加，成本低）；Q3 辅助-目标评估仅要求本设计不预占其语义（逐期间计数以 scope 为准，不依赖谓词目标），确认即可。

**标注**：本回复全部为 recommendation/设计建议，owner 决定；无写入、无导入、无运行、无临床访问；不构成方法批准。会话保持可续。
