# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同一角色 `evidence_single_object`，仍以 `zcode`/`GLM-5.3-Flash`（effort max）执行主角色 `codebuddy-cli/deepseek-v4.1-flash` 的 fallback；边界、读集规则、只读约束同前。本轮增读：`occurrence_scope.py`（新）、`rules.py` 改动段、`protocol_deconstructor.py` occurrence 相关 wire/prompt 段、`protocol_control_deconstructor.py`（结构及 schema 生成段）、`protocol_draft_service.py` 相关段、`deconstruction_gate.py` 频次段。git diff 不可用（环境 Xcode 许可报错），版本判断以代码常量与设计文档记录对照，标注为推断。**本增量为声明层施工，不构成频次消费者，更不构成任何临床验收。**

---

### 1. 增量源码审阅：occurrence 声明（evidence，file:line）

**1.1 合同层（新）**
- `app/domain/contracts/occurrence_scope.py`：`OccurrenceScope`＝`version: occurrence-scope/v1` + `kind: anchored_lookback|calendar_period|anchored_period|any_consecutive|unresolved` + `quantifier: single|every|any|unresolved` + `anchor_type`（锚定型必填、其他类型禁止擅加）+ `source_excerpts`（非空、去重、非空白）+ `unresolved_reason`（kind 或 quantifier 为 unresolved 时必填且须非空；已明确时禁止附带）。约束：`anchored_lookback` 只允许 `single`；`any_consecutive` 必须保留 `any|every` 原文量词——**any/every 量化确被合同保留**（回应质询点4，通过）。
- `rules.py:168-180`：`OccurrenceWindow.scope: OccurrenceScope|None`，`preserve_historical_scope` 在 None 时 pop——**旧载荷字节与内容身份不变**；docstring 明确 "absent historical scope is not an inferred rolling window"（无历史默认，通过）。
- `rules.py:280-287`：scope 存在时 (a) 逐字摘录必须含于本条件 `exact_source_clauses`；(b) 与 `repeat_scheme`/`observation_policy` 混用直接拒绝（“频次计数不能与未定义先后关系的复查或观察选择混用”）——第一轮 Q2/Q3 以“scope 存在为条件”的拒绝实现。

**1.2 官方族 wire/prompt（`protocol_deconstructor.py`）**
- Provider schema（727-752）：`occurrence_window` 对象 `additionalProperties:false`、`required:["duration","scope"]`，scope 由 `_wire_occurrence_scope_schema()`（696-698）内联 OccurrenceScope schema、`_inline_required_contract_schema`（701-714）将全部键设为必填（值按模型保留 null）——**新解构的窗口必须带 scope（可为 kind=unresolved+原因），比我在第一轮要求的“仅频次形态必填”更强**。
- Parser `_wire_occurrence_window`（1909-1932）：未知键仍拒绝（现允许 duration/minimum_count/scope 三键）；scope 存在时经 `OccurrenceScope.model_validate` 再 dump。注意 parser 对**缺失** scope 键宽容（1930 `if ... is not None`）——严格性在 provider schema 与 gate 层，parser 层是宽容兜底（见 §3-a 残余）。
- Prompt（288-305）：kind 四分+unresolved 定义、quantifier 按原文、锚点只填锚定型、“不得把‘每月’机械等同日历月”、“任何连续期间”不得固定到筛选日、unresolved+具体原因、摘录逐字含于本条件、**“计数期间与事实筛选的外层时间范围不可互相替代”**、频次与复查/观察选择无结构表达时列入 unresolved_items。语义覆盖完整。
- 版本身份：`DNF_WIRE_VERSION = "dnf-v14"`（132 行）。设计文档上一增量记录为“官方wire13”（2026-09-16 段），v13→v14 与本增量一致——**推断**（git 不可用，未能直接 diff 验证 bump 时点）。

**1.3 控制族（`protocol_control_deconstructor.py`）**
- 共享路径（evidence）：`ProtocolControlAgentWireConditionAtom/ObligationAtom.evaluation: ControlAtomEvaluationSpec`（462-484, 536-561）直接嵌入含 `predicate: AtomicPredicate` 的规格；`protocol_control_agent_json_schema`（1190-1218）由 `ProtocolControlAgentWire.model_json_schema()` 生成 → `AtomicPredicate→OccurrenceWindow→scope` 自动进入控制族 provider schema（`normalize_provider_schema` 将全部键设为 required）。来源链闭合：控制规格要求 predicate 子句 ⊆ spec 原文（`control_evaluation_spec.py:79-83`），scope 摘录 ⊆ predicate 子句（`rules.py:283-285`）→ 传递闭合。**声明到达双族，通过。**
- 版本：`ControlAtomEvaluationSpec` 保持 v4 不升版；scope 以自身 `occurrence-scope/v1` literal 记版本，旧 v4 载荷（无 scope）因 pop 序列化可读。响应格式名 `protocol_control_agent_wire_v1`（1208-1216）为静态名，内容变化依赖消息/schema 哈希冻结捕获——按既有 messages_sha256 冻结惯例可行，但见 §3-f 提示。

**1.4 草稿投影与门禁**
- `protocol_draft_service.py:484-515`：`_time_window_payload` 序列化完整 `occurrence_window`（含 scope），时间语义快照与差异展示携带声明；`_strip_expression`（452-470）逻辑快照照旧剥离窗口字段，不影响。摘录经 pydantic 合同原样通过水合，无字符串改写点（控制族既有的 `_control_quote_normalize` 排版引号恢复属全部摘录检查的共同行为，非本增量新风险）。
- `deconstruction_gate.py`：新增 `FREQUENCY_SCOPE_NOT_DECLARED`（2262-2269）：频次定义+有窗+scope None → issue，repair 动作明确“保留 unresolved……不得默认滚动或日历期间”。`FREQUENCY_WINDOW_NOT_STRUCTURED`/`FREQUENCY_WINDOW_NOT_IN_SOURCE`（2270-2292）不变。`_source_frequency_specs`（1030-1085）仍只认三种形态。

**1.5 消费面（确认未动，符合“有意非成品消费者”）**
`expression.py:505-506`（官方硬 UNKNOWN）、`control_operand_calculation.py:82-85`（控制硬 unresolved）、`proposition_context.py:25`（语义命题路径继续拒绝 occurrence_window，scope 不改变该拒斥）、`assessment.py:207`（缺口同桶）均与本轮前一致——声明只生产、不消费，符合本次指令。

**审阅结论（inference）**：声明层达成目标——双族可达、旧身份可读、摘录逐字贯穿、wire/版本受控、无历史默认、无消费越权。以下为发现的缺陷与残余（均有落点与最小补救），以及一处必须修正的我方先前结论。

---

### 2. 对我第一轮建议的修正（concession + 更正，runner 质询成立）

1. **同次合并只产上界，不产下界——我的第一轮反例 #5 写错了**。我当时写“已见2次 ⇒ TRUE 与完整性无关”，把“2 条记录”当成了“2 次已核实独立发生”。正确语义：`same_acquisition` 是当前关系词汇中唯一的合并关系，已核实合并把 K 组并小；**未核实关系的两两记为可能同次 → 合并后组数 K 是“所供记录中真实不同发生数”的上界，不是下界**。可证下界只来自三类“不同”证明：`repeat_of` 边（检查族语义上即不同次采集——这正是复查计数能成立的原因）、确定性日期不交证明（日精度 `PartialDateRange` 互不重叠）、或显式“不同发生”声明（现词汇表没有，见 §4-A）。因此对 GTE 型频次触发：仅凭 same-merge 机器通常只能得 UNKNOWN，除非下界证明可跨阈值。方向相关判定保留，但两侧界必须分开供给：`TRUE ⇔ 可证不同发生数下界 ≥ 阈值`；`FALSE ⇔ 上界 < 阈值 且 scope_complete`；其余 UNKNOWN。
2. **部分日期单次发生不证明逐日活动**——维持我第一轮的 [1, span] 区间表述，并精确化并集算术：每个部分精度发生贡献“至少1天、至多 span 天”；仅当区间不交性可证（bounds 推理）时才抬高并集下界；日精度确定日计入确定日集合；同日两次独立发生对“发生天数”贡献 1 天。不得把单条月精度记录展开为整月活动。
3. **裸“每月”不蕴含日历月**——prompt 已明令（`protocol_deconstructor.py:296`），但合同 `calendar_period` 没有结构化期间定义字段；期间的真实语义（日历月、月经周期、给药周期）只存在于逐字摘录中。消费端必须先核实期间定义，不得默认公历月（§4-C）。
4. **any_consecutive 的 any/every 量化**——合同已保留（`occurrence_scope.py:41-42`）。补充消费语义：∃ 型（“任何连续4周内≥2次”即存在违规窗即触发）可在单一可证违规窗上早真；∀ 型（“每连续4周不超过1次”）需要全部窗覆盖证明，资料不完整时基本不可证——两型在部分数据下验证性不对称，**不得互相归约**（§4-C）。

---

### 3. 残余缺陷与不安全假设（含最小补救建议）

- **a. 混用禁令以 scope 存在为条件**（`rules.py:282-287`）：无 scope 的窗口仍可与 `repeat_scheme`/`observation_policy` 共存。安全性依赖“新 wire 必填 scope”，但 gate 的 `FREQUENCY_SCOPE_NOT_DECLARED` 只在 `is_frequency_definition`（正则命中）时触发（`deconstruction_gate.py:2262-2263`），而 wire parser 对缺失 scope 宽容（1930）。残余通路：正则未识别的频次原文 + 模型给了窗但漏 scope → 无窗声明、可混用、无 gate issue。**最小补救**：gate 对一切 `occurrence_window.scope is None` 无条件报 issue（gate 只跑新解构草稿，不影响历史）；或 wire parser 强制 scope 键存在。
- **b. 正则识别缺口与误导性修复文案**：`_source_frequency_specs` 仍不认“每…N次”（固定期间+计数）及“每个研究周期”等表述（1030-1085）。未识别形态 + 已声明窗口 → 落入 `FREQUENCY_WINDOW_NOT_IN_SOURCE`（2284-2292），把真频次条件误标“非频率条件添加了发生周期”；未声明窗口 → 退化为纯数值阈值，期间语义静默丢失。**最小补救**：补“每+计数单位”pattern；并新增一条“频次形态未支持”专项 issue，替换误导分支。
- **c. scope 声明与摘录语义无确定性核对**：`kind=calendar_period` 配“近6个月”原文能通过摘录包含校验（摘录即整句）。按家规“来源包含≠语义证明”，语义保真留给未来方法评测是合规的；可选加固：对明显矛盾（anchored_lookback 无“近/内”线索、calendar_period 无“每”类线索）给 gate 提示级 issue——注意防误伤，标记为可选。
- **d. 控制族提示无 occurrence/scope 指引**（`protocol_control_deconstructor.py:1271-1289` 只讲 value_comparison/observation_policy/repeat_scheme 摆放）：合同与 schema 可达，但模型缺指引 → 欠声明或误用风险。**最小补救**：控制 prompt 补一句与官方段（293-298）等价的 scope 摆放与 unresolved 要求。
- **e. `calendar_period` 期间语义只有摘录可依**（见 §2-3）——消费端必须含“期间定义核实”步骤，列为消费者方案的一等步骤而非假设。
- **f. 控制响应格式名静态**（`protocol_control_agent_wire_v1`）：内容 schema 已变而名未变；现行走消息哈希冻结可捕获，但任何按名 pin 的外部工件会漏检。建议 owner 确认无按名 pin 的存量（有界问题 Q1'）。
- **g. 版本判断限制**：dnf-v14 与文档记录的 wire13 衔接为推断；git 在本环境不可用（Xcode 许可），未做 diff 级验证。

---

### 4. 下一手：完整频次消费者接线（source-grounded，修正界语义后）

原则不变：复用 `JudgmentContentJobExecutor` 同族任务、双路对账、逐字来源资格、sealed 求值、`_evaluate_bound_predicates` 映射注入（模板 `repeat_evaluations`，`expression.py:675-690`）；不新队列；频次不入 entails。修正后增量：

- **A. 区分度声明**：频次读取任务（`frequency_evidence/v1` 合同，`StatementKind: aggregate_total|per_occurrence_records|occurrence_days|unresolved`）逐配对双路收集**双向关系**：`same_acquisition | distinct_occurrence | relation_unresolved`，各带逐字引用；另设确定性不交证明通道：日精度 `PartialDateRange` 区间不交 ⇒ 可证不同发生，无需模型。`distinct_occurrence` 是下界（可证不同），`same_acquisition` 合并压上界（合并后组数 K），`relation_unresolved` 两者之间 → 输出区间 `[可证不同数下界, K]`。判定：GTE/GT 触发 `TRUE ⇔ 下界≥阈值`（与 scope_complete 无关）；`FALSE ⇔ 上界<阈值 且 scope_complete`；否则 UNKNOWN。不采用通用 TRUE 见证。
- **B. 发生天数**：按 §2-2 区间并集算术输出 `[确定日∪可证不交部分日的下界, 全部 span 并集上界]`；同次合并同日只计 1 天；无任何逐日展开。
- **C. 窗口应用按 kind 分派**（消费 `occurrence-scope/v1`，缺声明保持 `occurrence_scope_unverified`）：`anchored_lookback`（single）＝[锚点−duration, 锚点] 单区间，复用 `evaluate_time_constraint` 的部分日期歧义语义；`anchored_period`＝锚点起算区间；`calendar_period`＝先双路核实期间定义摘录（“每月”≠自动公历月，月经/给药周期须按原文），再逐期间子求值、按 `every` 合并；`any_consecutive`＝**保留量化词**：`any` 型存在一个可证违规滑窗即 TRUE，`every` 型须全部窗证明否则 UNKNOWN；滑窗最大计数算法与部分日期界可后置，先保留 `sliding_window_unsupported` 类显式 unresolved。
- **D. 汇总声明**：声明 N+期间 P 对窗口 W 转不等式约束（P⊆W ⇒ ≥N；P⊇W ⇒ ≤N；部分重叠按精度转区间或 UNKNOWN），与逐次区间按交集合并（lo=max, hi=min），**永不相加**；声明与已核实明细在同一期间内矛盾 → 显式冲突、双方保留。
- **E. 封存与批准**：`OccurrenceAtomEvaluation`（镜像 `RepeatAtomEvaluation` 三哈希形状，`evaluation_result.py:20-46`）；方法评测 kind（如 `frequency_statement_fidelity`）+ consumer 版本 literal；`require_*_method` 版本匹配克隆；官方侧注入 `_evaluate_bound_predicates` 新映射（与 repeat/proposition 映射互斥校验同款），控制侧替换 `_calculate_operand:82-85` 分支。评测清单必须含：仅上界可得时的 UNKNOWN、下界证明通路、部分日期天数、期间定义误读（月经周期当公历月）、any/every 互混、汇总明细冲突、滚动/固定互换反例。
- **F. 报告**：新原因码独立列（scope 未声明/区分度未核实/期间定义未核实/滑窗未支持/汇总明细冲突），脱离 `OBSERVATION_UNVERIFIED` 同桶；报告区分“声明总数/逐次计数/发生天数”计算方式与参与范围，沿用“未明不默认”。

顺序建议：A–C 为纯函数（可先行隔离评测）；D 并入 A 任务合同；E/F 依赖 A–C 形状。全链完成后按 T4 统一验证。

---

### 5. 有界问题（请 Codex 裁定）

- **Q1'** 控制族响应格式名静态（§3-f）：是否存在按 `protocol_control_agent_wire_v1` 名字 pin 的存量工件/方法批准？若无，维持现状即可；若有，需随 schema 哈希一并更新。
- **Q2'** gate 的 scope 必填检查是否采纳“对一切 occurrence_window 无条件触发”（§3-a，我的建议）？这会影响正则未识别但已声明窗口的草稿——影响面是更严格而非更宽松。
- **Q3'** 控制族 prompt 的 occurrence/scope 指引补句（§3-d）放在本增量内补，还是随消费者增量一起过方法评测？暂定：随消费者增量，避免孤立改提示触发控制族 prompt 版本重冻。

**标注**：§1 为 evidence（file:line）；§1.3 版本衔接、§1 审阅结论及 git 不可用说明为 inference；§3 补救、§4 全部为 recommendation；本增量及本报告均非临床或运行验收，最终采信、评测与批准归 owner/Codex。会话保持可续。
