# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮读取：`qualified_frequency_evidence.py`（116 行）、`occurrence_evidence_bounds.py`（101 行）、当前 `frequency_evidence.py`（162 行，与本轮起点一致，期间仍只有 `period_excerpt` 单字段）、`occurrence_scope.py` 校验段、既有日期/锚点定义（`PartialDateRange`、`DateValue`、`evaluate_time_constraint`、`calendar_dates`、episode `anchor_dates` 可达性——`qualified_observation_relation.py:275` 同路径）。只回答有界问题：声明期间→合格期间 vs 要求窗口的桥。

---

### 1. 现状缺口的确切形状（evidence）

- `bound_stated_total`（`occurrence_evidence_bounds.py:80-101`）要求**两侧已是精确 date 区间**，且 docstring 明令本函数不做期间文本解析、不猜锚点、不展开部分日期、部分重叠→None（数学正确：部分重叠时窗外未知量使任何一侧界都不可用，反例：声明[1–6月]=N、要求[3–4月]，count(要求)≤N 不成立）。
- 因此缺口是**两个区间生产者**，都不存在：
  1. **声明期间**（`FrequencyStatement.period_excerpt` 目前只是原文串）→ `stated_start/stated_end`；
  2. **要求窗口**（`OccurrenceScope`）→ `required_start/required_end`。后者卡在：未命名回溯锚点（“近5年内”）现只能声明 `kind=unresolved`（`anchored_lookback` 强制 `anchor_type`，`occurrence_scope.py:34-36`）——方向与时长已知但机器不可用，用户政策（未命名回溯锚点分别适用于当前筛选/基线，不得默写为方案命名锚点）因此**无处落地**。
- 附带缺口：`bound_distinct_occurrences(enumeration_complete=...)` 的布尔无来源依据——`select_qualified_frequency_sources` 输出恒 `enumeration_complete: False`（`qualified_frequency_evidence.py:113`），逐次路径的“上界可用”条件永远不满足。

---

### 2. 最小通用桥设计（recommendation；复用既有读步，无新模型阶段、无专用正则）

**2.1 声明期间结构化——加在既有频次读步（合同 v2，可选字段、pop 序列化，v1 身份不变）**

`FrequencyStatement` 增嵌套 `period: FrequencyStatementPeriod | None`（`period_excerpt` 保留为原始逐字串，继续承担包含校验与 agreement_key 扩展）：

```
basis:            "explicit_dates" | "anchor_relative" | "unresolved"
start/end 组件:    explicit_dates 时必填——模型只观察原文日期的原始分量
                  （年/月/日各 as-stated + precision），逐字 start_quote/end_quote；
                  规范区间由代码经既有 PartialDateRange 校验/界推导生成（设计§7：模型
                  不产生规范化值），部分精度→确定性上下界，unknown→无界
duration_value/unit + duration_quote:
                  anchor_relative 时必填（时长与单位，逐字）
anchor_named: bool + anchor_quote:
                  anchor_named=true ⇒ anchor_quote 逐字给出方案命名锚点短语，
                  代码仅在短语对应冻结 episode.anchor_dates 的 AnchorType 词汇时解析；
                  false ⇒ 不得携带任何 anchor_type（不造锚点）
```

校验规则沿用本合同风格：basis 与字段成对必填/互斥、全部 quote 非空且属本 source_pair、跨路 agreement_key 扩展 period 字段。方法评测（`frequency_statement_fidelity` 下一轮）须覆盖期间抽取保真：命名 vs 未命名锚点、显式日期、多期间、锚点词与方案词汇不符。

**2.2 要求窗口侧——`OccurrenceScope` 增 `relative_unanchored` kind（v2 增量 literal）**

新 kind 语义＝“原文明示相对时长与方向、未命名锚点”：无 `anchor_type`、quantifier 仅 `single`、`unresolved_reason` 必须为空（这不是未决，是明确声明）。旧 v1 载荷不受影响（新增 literal 向后兼容读取）。这样“近5年内”获得机器可处理的声明，而**方案命名权不被伪造**——与 `anchored_lookback`（命名锚）在合同层显式分型。其余 kind 不动；`calendar_period`/`any_consecutive` 的期间资格仍不在此桥内（保留 unresolved，见 §4 边界）。

**2.3 纯函数桥——`qualify_statement_period`（落点 `app/domain/frequency_period_qualification.py`）**

输入：已资格化的 statement period + group 的 `OccurrenceWindow`/scope + 冻结 `members[0].episode["anchor_dates"]` + 当前节点身份。输出 `QualifiedPeriodRelation`：
- **关系分类**：subset / superset / equal / partial / undecidable——对部分精度的两侧端点做**全端点组合一致**判定（现成 house 模式：`_calendar_bound_truth`，`expression.py:249-281`）；只有全组合一致的关系才输出，否则 undecidable＋原因码。等价实现约束：只有两侧端点均日精度时才调 `bound_stated_total` 四日期入参；部分精度一律经组合一致通道，绝不在本层“展开”。
- **锚点解析**：`anchored_lookback/anchored_period` → `scope.anchor_type` 必须存在于冻结 episode.anchor_dates，缺失 → `frequency_anchor_missing`（不猜）；`relative_unanchored` → **应用政策锚**：按当前节点取筛选/基线锚分别求解，并在输出中携带 provenance `{anchor_source: "application_policy", policy_identity, applied_node, anchor_bounds}`。
- **Provenance 去处**：政策锚只进入未来 `OccurrenceAtomEvaluation.resolution` 与报告说明（“按当前筛选/基线节点分别适用——应用政策，非方案命名锚点”），**从不写回任何来源合同或 scope 字段**——来源措辞保持逐字原文，满足“保存推导依据而非伪造来源表述”（设计§5 规则的频次版）。
- 方向/日历算术复用 `app.domain.calendar_dates.shift_date/date_bounds` 与月/年日历语义（`expression.py` 既有实现），本模块零新解析器。

**2.4 逐次路径的列举旗标**：`FrequencyEvidenceResult` 增 group 级 `enumeration_status: "complete"|"partial"|"unresolved"`＋逐字 quote（双路一致）——`complete` 仅当原文以完整列举方式呈现（如“先后两次”）；消费者据此向 `bound_distinct_occurrences` 传 `enumeration_complete`，否则维持无上界＋`occurrence_enumeration_incomplete`。

**2.5 消费连接**：`select_qualified_frequency_sources`（现有）扩展 `quote_reasons` 到新 quote 字段；关系/声明资格逻辑不变；数值消费按既定计划：关系分类 → `bound_stated_total` → `intersect_count_bounds`（None → `occurrence_count_bounds_conflict` 显式保留）→ `evaluate_count_bounds(comparator, predicate.value)`。

---

### 3. 三条区分与两不等的落实（按要求逐条）

- **事件时间 vs 计数期间**：桥只消费 statement 的 period 字段（计数期间）；单次发生的时间属事实层，走既有谓词外层 `time_constraint`/`evaluate_time_constraint` 逐事实路径。**禁止**把任何 `fact.date_range` 指派为汇总期间（无字段、无代码路径）。
- **部分精度 vs 时长**：精度→端点不确定性界（全组合一致判定）；时长是另一语义类型，仍不建模（逐次天数跨度维持 `occurrence_day_extent_unmodeled` unresolved，前轮 D3 不变）。
- **声明总数 vs 逐次发生**：期间桥仅作用于 `stated_total`；`individual_occurrence` 无计数期间字段（合同现形状已保证，v2 亦不添加）。
- **引文一致＋双路一致 ≠ 临床核实**：引文资格（quote containment＋既有 `pair_direct_selection_rejection_reasons`）证明出处；方法评测证明抽取保真；代码日历算术证明区间关系——三者各证其事，合格期间的真值仍只是“来源支持的计数期间与窗口的集合关系”，不是临床结论。

### 4. 明确不做（边界）

不给 `calendar_period`/`any_consecutive` 做期间资格（先保留 `frequency_period_kind_unsupported` 类 unresolved，待其期间定义核实设计）；不建第二任务队列（期间字段在既有读步内，v2 增量）；不做研究专用期间解析；不改历史 v1 身份。

**有界问题**：Q1'' `relative_unanchored` 是否采纳为 scope v2 kind（替代方案：保持 kind=unresolved＋在桥层以 duration 推断方向——我反对，那是把声明降级为猜测）；Q2'' 政策锚 provenance 的 policy_identity 形态（引用现有用户裁决记录 vs 新版本化政策对象）——暂定引用既有裁决、不新增对象。

**标注**：§1 为 evidence（file:line）；§2/§3 为 recommendation；无运行、无导入、无验收声明；最终采信归 Codex/owner。会话保持可续。
