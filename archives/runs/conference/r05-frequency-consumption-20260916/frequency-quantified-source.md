# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮完整读取：`FrequencyHorizon`/`OccurrenceWindow` v4 段（`rules.py:169-237`）、`occurrence_scope.py` v4 全文、`frequency_quantified_periods.py`（124 行全读）、`frequency_quantified_calculation.py`、`frequency_total_resolution.py` v3 wrapper、三个计算器的 `required_period` 注入路径、`qualified_frequency_evidence.py` v6 挂接、双解构器 wire/prompt 段、gate `FREQUENCY_HORIZON_NOT_DECLARED`、presentation、前端新码。仅编译/tsc 级事实。

**先认领两处被拒建议的正确性**：(a) 部分日期的“存在可行安放”是存在性论证——实际日期未知但固定，存在某种安放不证明实际安放满足窗约束，作为滑动窗 TRUE 见证不健全，被拒正确；(b) “每30天”是自纪元的离散固定分段，≠任意连续30天滑动窗——现 prompt 明确“每30天不等于任意连续30天，周期对齐未明不得擅改为滑动窗”（`protocol_deconstructor.py:309`）；(c) duration 的单位即日历单位，未另设 period_unit ✓；(d) boundary_periods 对 any 同样必填 ✓（prompt:306“任一和每一均须核对首尾不完整周期”）。

---

### 1. 核验通过项（evidence，file:line）

- **有限精确地平线**：`unbounded`/`unresolved` → `frequency_horizon_unresolved`（`frequency_quantified_periods.py:46-47`）；explicit_dates/anchor_span 经 `_exact` 仅接受日精度（60-62），月精度→`frequency_horizon_dates_unresolved`——**不猜地平线、不借外层 TimeConstraint**（horizon 的 `relative_window` 是 scope 内独立来源声明，prompt 明令“不从外层时间筛选自动复制”）✓。
- **非迭代纪元边界**：`shift_date(epoch, value*n)` 一次性计算（103）——无逐月月末漂移 ✓。日历期间 duration 必须=1（74，多单位周期未建纪元→unresolved）；周须显式 `calendar_week_start`（79-81）✓。
- **limit 政策正确**：前缀期间保留在 trace（`unresolved` 展开含已算 periods）、`domain_complete=False`；wrapper 只允许 **any-TRUE / every-FALSE** 前缀见证存活（`frequency_total_resolution.py:101-106`），其他域错误拒绝前缀判断（103）——计算上限非临床封顶 ✓。空合格期间集→`frequency_no_eligible_period`→UNKNOWN（107 `results` 非空才走完成分支）——**无空洞真值** ✓。
- **逐期间证据独立复用**：三个计算器注入 `required_period` 单例端点（枚举时已施加 scope 开闭，计算器**不重复** ±1 平移，仅声明侧自行枚举——`frequency_period_qualification.py:91-92` 只作用于 stated 侧）✓；每期间独立求值、无求和 ✓；真相组合经 `evaluate_count_bounds` 区间语义，非硬编码 gte ✓。
- **见证方向**：any→期间 TRUE 即原子 TRUE；every→期间 FALSE 即原子 FALSE（98-99）；完成域且全判定才给反向真值（107-110）✓。
- **合同/版本**：scope v4 新字段版本门控 pop＋旧版拒绝（39-43）、calendar_week_start 仅 calendar_period（44-45）、boundary 仅 any/every（46-47）；`FrequencyHorizon` basis 字段互斥＋摘录包含＋unbounded 禁端点声明（184-208）；horizon 仅 quantifier≠single＋scope v4（rules.py:231-234）；`dnf-v17`、control prompt v2.19、consumer v6、summary/prompt v4 链一致；gate `FREQUENCY_HORIZON_NOT_DECLARED`（2268-2276）；前端新码 9 条全映射（`reviewConditionNotes.ts:25-33`，含 limit 措辞“未据此认定全部满足”）；presentation 逐期间呈现＋未完成域披露 ✓。旧单区间路径零改动回归（quantified None → v2 单路）✓。

---

### 2. 缺陷（按严重度）

- **F1（本轮唯一实质缺陷，不健全正面通道）滑动窗长度随开闭声明漂移**：`frequency_quantified_periods.py:104,107-109`——any_consecutive 的 `following = shift_date(current, duration)`、`raw_end = following`（calendar 才 −1），有效窗长 = duration天数 +1 − 排除端数。仅 (start_inclusive=True, end_inclusive=False)（或反向）给出恰为 duration 的窗长；若解构声明 (true, true)，“任何连续4周”被枚举成 **29 天窗**——一个横跨 29 天的聚类会被当 4 周违反窗 → 期间 TRUE → 原子 TRUE，**相对来源真实的 28 天量词是不健全正面**。现 gate/枚举只要求端点非 null（50-51），不约束组合。**最小补救（择一，建议 a）**：(a) scope 校验器对 any_consecutive 强制 `int(not start_inclusive) + int(not end_inclusive) == 1`（恰一端排除→窗长恰为 duration），否则拒绝——“连续期间长度由时长决定”；(b) 枚举器对 any_consecutive 一律 `raw_end = following − 1天`（长度由构造保证），开闭仅表述边界日归属；(c) 最低限度加 gate issue。未修复前该通道依赖解构器自觉，建议在方法评测前闭合。
- **F2（观察/指引级）anchored_period 量化分段的边界日重叠**：两段均含端时 [a, a+d] 与 [a+d, a+2d] 共享 a+d——边界日事件计入相邻两个期间的下界。语义随声明走、无客观长度错误（与 F1 不同），但若来源惯例是半开周期而声明为双含端，一个事件即可满足相邻两期。最小处置：prompt/gate 指引锚定周期必须声明边界日归属惯例（通常末端排除），或同 F1(a) 式校验；归属保真归方法评测。
- **R（观察）** `full_only` 下被排除的边界期间在 trace 中无痕（仅列入合格期间）——“为何某些期间不在义务域”的审计断点；最小处置：trace 增 `excluded_partial_periods` 计数或列表，便于报告说明。

**非声明**：外层窗口组合、无界/部分地平线、辅助-复查目标频次仍未实现（与声明一致）；全部为编译/tsc 级事实，不构成方法批准、临床接受或完成宣告；最终采信归 Codex/owner。会话保持可续。
