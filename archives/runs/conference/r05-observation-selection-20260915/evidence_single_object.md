All evidence is gathered. Producing the complete advisory report now.

# Conference Output: r05-observation-selection-20260915 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅，只读设计审阅）。本 pass 未写任何文件、未触网络、未读生产路径、未调用模型；全部结论基于本仓当前 worktree 源码与设计文档。以下按“证据 / 发现 / 最小完整设计 / 实施顺序 / 保留未决项 / 异议 / 有界问题”组织，事实与推断分开标注。

### 1. 审阅范围与证据基线

已读初始读集（conference context、main venue plan）及以下来源（均为本 worktree 当前内容）：

- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17（尤其 292–341 行：绑定链、命题关系、观察选择扩展、控制计算隔离消费）
- `docs/PROJECT_CONTEXT.md` 头部当前状态（第 12 行明确“下一项回到完整观察/最近复查选择”；第 17 行确认“有限枚举与复杂最近/复查…仍继续”）
- `app/domain/contracts/rules.py`（AtomicPredicate 184–244）、`app/domain/contracts/control_evaluation_spec.py`（ControlObservationPolicy 14–30、校验 61–129）
- `app/services/qualified_binding_selection.py`（选择执行器 `_select_facts_for_identity` 211–268、消费主流程 309–622）
- `app/llm/proposition_evidence.py`（关系提示 v4：scope_correspondence / assertion_extent / scope_population）
- `app/domain/expression.py`（`_evaluate_atomic` 475–562、`_evaluate_time` 280–295、部分日期区间算法 235–277）
- `app/projections/control_calculation_experiment.py`（`_conditional_truth` 40–85、`_proposition_observation` 88–114）、`app/projections/control_operand_calculation.py`（59–115）
- `app/services/frozen_review_calculation.py`（计算 v13 消费链）、`app/domain/contracts/qualified_binding_selection.py`（选择 v3 / 消费 v9 合同）、`app/services/qualified_proposition_evidence.py`（关系消费 v3）
- `app/agents/protocol_control_deconstructor.py` 1225–1279（观察政策提示）、`app/agents/protocol_deconstructor.py`（官方 dnf-v1 wire）、`app/domain/contracts/predicate_binding.py`（`predicate_identity_sha256` 93–113、FrozenFactRecord 354–375）
- `app/domain/gates/assessment.py` REASON_GAPS 206–220

### 2. 现状发现（事实，附 file:line）

- **F1 官方谓词完全无观察政策。** `AtomicPredicate`（rules.py:184-244）没有任何选择字段。多观察在两处硬停：选择器 `multiple_usable_pairs_without_selection_policy`（qualified_binding_selection.py:237）与求值器多值 `observation_selection_unverified`（expression.py:533-542）。与 PROJECT_CONTEXT.md:328“控制及多观察仍待完成”一致。
- **F2 控制政策表达不了最近/最早/复查。** `ControlObservationPolicy` 仅 `single/any/all/unresolved`（control_evaluation_spec.py:18）；解构提示明确要求“要求最近一次、复查替代或复杂时点选择尚不能表示时用 unresolved”（protocol_control_deconstructor.py:1239-1240）。即：所有“以最近一次/复查结果为准”的条款今天是**构造性永久 UNKNOWN**——这正是本次目标要消除的“永久 UNKNOWN 当完成”。
- **F3 选择执行器只做基数断言，无排序、无窗口预过滤、无被淘汰观察的留痕。** 控制分支 single 要求 `len(fact_ids)==1`，any/all 全量透传（qualified_binding_selection.py:249-268）；usable-but-not-selected 记录不进 `rejected_pairs`（389-396 只记被拒配对），single 多观察时整体 unresolved 且丢失逐记录原因——与 R3 334 行“不能因一个决定性结果丢失其他记录的未决原因”在选择层存在张力。
- **F4 无时间约束时合同无法声明日期操作数。** `time_operand_attribute` 仅当 `atom.time_constraint` 非空才允许（control_evaluation_spec.py:125-129）；官方侧日期配对同样只在 `time_constraint` 存在时强制（qualified_binding_selection.py:229-235）。“最近一次”条款常无窗口但排序必需事件日期——**合同层面就堵死了**。
- **F5 排序所需日期数据已具备。** FrozenFactRecord 携带 `date_range: PartialDateRange`（predicate_binding.py:372，含精度）；部分日期区间语义已有纯函数（expression.py `_date_bounds`/`_calendar_bound_truth`）。`record_time` 已归一 UTC 且禁止直接用于临床时间（control_operand_calculation.py:101-108），排序必须排除 record_time。候选配对按事实实际存在属性泛化提议（predicate_binding_candidates.py:138），date_range 配对不依赖时间约束存在。
- **F6 频次/未来窗是独立缺口。** 控制侧 `occurrence_window`/prospective 硬停“频次或未来期间仍需独立核实”（control_operand_calculation.py:82-85）；官方求值器同样不消费 `occurrence_window`（rules.py:196 仅合同定义）。频次量词≠最近/复查，不应混入本切片。
- **F7 原因→缺口矩阵与中文文案链路已在。** REASON_GAPS（assessment.py:206-220）、控制 unresolved_atoms、native reason sentences（近期提交）。新增选择原因若不接入此层，闭环不完整。
- **F8 身份哈希稳定机制有既定模式。** `predicate_identity_sha256` 对 `predicate.model_dump` 取哈希（predicate_binding.py:110）；控制规格用 omit-when-None 序列化保持旧身份（control_evaluation_spec.py:54-59）。给 `AtomicPredicate` 加可选字段**必须**复用同款 wrap-serializer，否则全部历史谓词身份/权威链哈希漂移。

### 3. 最小完整通用闭环设计（建议）

核心思路：**选择归选择执行器，求值器零改动**。最近/最早/复查都归约为“从有限集合中选出唯一主导观察”，两个求值器（expression.py 与 control_calculation_experiment.py）收到的仍是 ≤1 个事实，天然被既有消费链（选择 v3→计算 v13→实验 v9→缺口矩阵→中文原因）消费，不产生未消费合同。

**D1 共享政策对象 v2**（扩展现有 `ControlObservationPolicy`，官方谓词复用同一合同类型；建议放中立模块 `app/domain/contracts/observation_selection.py` 供两族引用）：
- 保留 `mode: single|any|all|unresolved`、`scope`、逐字 `source_span_ids/excerpts`。
- 新增可选 `selection` 块（仅 `mode=="single"` 合法）：`criterion: "latest"|"earliest"|"explicit"`、`ordering_attribute: "date_range"`（仅允许事件日期）、可选 `retest: {max_additional_observations: int≥1}`（复查授权次数，来自方案原文）。`explicit` 即现状“恰一项”。
- 校验：latest/earliest 必须有“以最近/最早为准”的逐字方案依据（沿用来源包含校验）；**无政策不得默认取最近**（维持 R3 §17.1:298 禁令）；retest 仅配 `criterion=latest`。

**D2 有限观察集合（可计算定义，不加新合同）**：某身份的有限集合 = 该身份声明操作数属性的全部资格可用配对（官方：value + 同事实已合格 date_range；控制：operand_attribute + 日期配对），若带时间约束则按事件窗口过滤（FALSE 剔除但留痕，UNKNOWN 保留在集合内）。资料供给完整性仍由既有要求级检索完备机制证明，政策不重复证明——此边界须写入设计文档。

**D3 选择执行器扩展**（唯一新增逻辑落点，`_select_facts_for_identity` 两分支对称）：
1. 有限集合内每个 value 事实必须有同事实合格 date_range（缺失→unresolved，复用 `event_date_not_qualified_for_selected_value` 模式）；
2. 有时间约束时先用 `evaluate_time_constraint` + 冻结 anchor 计算窗口归属，FALSE 剔除（留原因）；UNKNOWN 保留；
3. 按日期区间**严格优势**排序：latest 要求其下界 ≥ 其余全部上界（earliest 对称）；部分日期重叠→`observation_order_ambiguous_partial_date`，不造日；
4. 同主导日同值同单位同极性→一致性去重；同主导日异值→`observation_tie_unresolved`，绝不取有利值；
5. retest：窗口内观察总数 ≤ 1+max_additional，超出→`retest_count_exceeds_authorization`；复查落在授权窗外→保守 `retest_outside_authorized_window`（不静默回退初值主导，见 Q2）；
6. 争议组成员先按既有 source_conflict 处理，不得用“取最近”消解冲突。

**D4 选择留痕**：`QualifiedBindingIdentityOutcome` 增可选 `superseded_pair_ids` 及逐条原因（`not_governing_observation` 等）；material v3→v4、消费算法 v9→v10。被淘汰观察的真值/原因保留在 material 并贯穿报告（满足 R3 334 行），求值器版本不动。

**D5 生产端**：控制解构提示 v2.3/wire v7/gate v7——原文明确“最近一次/最早/复查以何为准”时输出 selection 块，歧义仍 unresolved；官方 dnf wire v2 + 提示更新，`AtomicPredicate` 加可选 `observation_policy`（omit-when-None 序列化保身份，F8），缺省走既有单值路径，官方发布 gate 版本随升。

**D6 解释层**：新增原因码接入 REASON_GAPS（均归 OBSERVATION_UNVERIFIED 族）并按既有 native-sentences 模式补中文句；报告展示主导观察与其 locator，同时列出被淘汰观察及原因（来源引用要求）。

### 4. 有界实施顺序

1. 合同：中立政策模块 + 两族挂接 + 序列化/校验（含历史字节稳定性测试）。
2. 执行器：两分支选择逻辑 + 复用 expression.py 纯日期函数（同一 anchor 来源，避免与 operand 计算漂移）。
3. 留痕：outcome/material v4、consumer v10。
4. 生产端：控制 prompt/wire/gate v7；官方 dnf v2/prompt/gate。
5. 原因与展示：REASON_GAPS + 中文句 + 报告/导出。
6. 验证：执行器矩阵单测（latest/earliest/tie/部分日期/复查计数/授权窗外/窗口 UNKNOWN/争议组）+ 旧载荷身份往返测试 + 编译；不跑模型/库/阶段测试（与当前阶段纪律一致），真材评测列为后续。

### 5. 明确保留的未决项（不得静默永久化）

每项需按项目边界登记责任方/下一步：官方谓词 any/all 多观察量词（Phase B，求值器 v14）；频次计数（occurrence_window 两族）；复杂指定时点（Day -1、跨访视基线值选取）与独立复查窗；确定性政策的双路 scope_correspondence 核实（当前仅非确定性有）；真材临床验收与采信授权（Codex/用户）。

### 6. 最重要异议与挑战

- **O1（最高影响）**：只改消费端不改生产端，会把“永久 UNKNOWN”换成“永远无人生产的政策”——反向的未消费合同。最小切片必须同时含 prompt/wire/gate 升级，这会触发发布校验链版本联动，需 Codex 确认一次切片的版本预算。
- **O2**：若 Codex 把“有限观察集合”理解为含官方条款的多观察量词（ANY/ALL），Phase B 必须入本切片（求值器 v14）；我的建议是出切片（目标明确点名最近/最早/复查），合同字段已为其预留。
- **O3**：复查的复杂变体（限期复查、两次取高、均值）不可表示，必须保留 unresolved+原文，不得硬编码临床语义（AGENTS 边界）。
- **O4**：控制侧若不在执行器预过滤窗口而直接“全局取最近”，主导观察可能窗外、窗口内较早观察已被淘汰，净结果静默降为 UNKNOWN——窗口先于排序是正确性要求，不是优化。

### 7. 有界问题（安全暂定路径已给出）

- **Q1**：Phase B（官方观察量词）入不入本切片？暂定：不入。
- **Q2**：复查落在授权窗外的暂定语义：`retest_outside_authorized_window` 保守 unresolved，还是初值主导？暂定：unresolved，待方案原文实证。
- **Q3**：确定性 latest/retest 政策是否要求双路 scope 核实？暂定：不要求（算术排序 + 来源包含即可），语义范围核实仍属非确定性模式。

### 8. 不确定性声明

以上为实现就绪的源码级设计建议，非临床验收；未运行任何模型、数据库、浏览器或阶段测试；对提示改动的实际召回效果（解构器能否可靠识别“最近/复查”表述）只能经真材隔离评测证明，本审阅不将其视为已成立。Codex 保留最终裁决与验收权。
