# Conference Output: r05-conditional-observations-20260915 - evidence_single_object

## Output

续同会话只读源码审阅（未写/运行测试、未import应用、未访问DB、未调用模型/服务、未改源码、未读workspace外资料；非临床验收，Codex保留最终采信权）。已按五项裁决重新核查并给出修正设计；行号基于当前工作树。

### 一、状态确认（观察）

- 两项 REASON_GAPS 映射已落源码：`app/domain/gates/assessment.py:207-208`；评估器已升 `component-review/v15`：`app/services/frozen_review_calculation.py:27`。同意其定位：这是保护补全，不是功能，更不是临床采信。

### 二、裁决#2修正设计：发生次数（occurrence）

**计数单位改为 ClinicalEventV2 当前链头，不是资格事实行。**

- 事件合同已具备所需身份/世系：`app/domain/contracts/facts.py:439-491` — `fact_ids`（≥1支撑事实，:459）、`referenced_fact_objects`、`stable_identity` 由权威元组+事件类型+引用对象+起止+持续状态推导（:480-490，不含定位，同内容多记录在事件发布层合并）；`source_revision_of` 追加世系（:447）。“多记录描述同一事件”的折叠发生在事件发布，评估器只数事件。
- 冻结链已携带事件，无需新快照管道：`ReviewContextSnapshotV2.events`（`app/domain/contracts/review_context_v2.py:92`），装配时即取链头并排除被更正者（`app/services/review_context_assembly.py:46,51`；`app/services/patient_profile_service.py:338-351` `_chain_heads` by `stable_identity` + superseded 排除）。
- **摘要型频次事实不得当发生数**：`ClinicalFactV2` 可携带 value/unit（如“约每月1次”，facts.py:389-390），它是对频率的陈述而非N次事件。确定性计数只数“逐次事件”；摘要陈述只能走语义命题路径或保持未定，绝不能由代码按“每月1次×N月”乘算展开（那是补造事实）。
- **计数前置资格**：被数事件的 `fact_ids` 必须全部在本谓词身份下有合格 value 配对，且事件日期（start_range）经合格 date_range 配对核实到其支撑事实——沿用既有 `(identity, fact, attribute)` 资格链（`app/domain/contracts/binding_qualification.py:97,253`），不新增资格合同。
- **单调性修正（取代被否决的通用TRUE见证/FALSE不完整）**，对阈值N、滚动窗 duration：
  - `GTE/GT`（"≥N次"）：TRUE=存在一个 duration 窗含 ≥N 个合格链头事件（见证方向）；FALSE=无此窗，须枚举完整→无完整性证明时 UNKNOWN。
  - `LTE/LT`（"≤N次"）：TRUE 须完整性→UNKNOWN；FALSE=存在窗内 >N 事件（见证方向）。
  - `EQ`：TRUE 须完整性；FALSE 仅">N窗"方向可见证，"<N"方向须完整性。
  - 部分日期：事件 start_range 为区间，见证窗必须对所有端点组合成立才判定，否则 UNKNOWN（沿用 `evaluate_time_constraint` 的端点组合纪律，`app/domain/expression.py:235-267`）。
- **三层窗口不得互换**（不发明 OccurrenceWindow 没有的锚点）：
  1. `OccurrenceWindow.duration`（`rules.py:155-159`）= 无锚滚动窗长，判定“是否存在长为 duration 的窗”不需要任何锚；
  2. 记录回溯范围 = 义务侧 `ControlTemporalScopeKind`（calendar_lookback/full_history/official_rule_defined/since_previous_visit，`protocol_controls.py:188-219`）或官方谓词的 `TimeConstraint`，决定“往回查了多远”，是完整性声明的唯一参照系；
  3. 复查方案自己的时限（若方案声明）= 方案对象内独立 TimeConstraint。三者字段不同、来源不同，求值与报告分开呈现。

### 三、裁决#3/#4：条件性复查的关系证书——同作业复用评估结论

**结论（证据）**：两路作业的*基础设施*可完整复用，但*被判定对象*不可——现有三个判定合同全部是“配对内”（pair-local），结构上无法出具事实对事实的复查关系证书：

- 批次载荷已含全部兄弟事实与定位（去重后整批提供）：`app/llm/binding_qualification.py:99-123`——传输层无需改动即可让模型同时看到两份记录；
- 但系统提示明令禁止跨配对取材：“不能借用其他配对的材料”（:157）、“不要假设未列出的资料”（:173）；引用校验也只对单配对 locator 摘录（`app/llm/proposition_evidence.py:108-113`；`app/llm/judgment_content.py:51-53`）；
- 三个判定合同的维度都是事实↔条件：`BindingQualificationJudgment`（contracts/binding_qualification.py:162-202）、`PropositionEvidenceCheck`（contracts/proposition_evidence.py:19-68）、`JudgmentContentCheck`。全库无 retest/repeat/复查关系概念（域合同与LLM层 rg 仅命中无关的 OCR 重复文本枚举）。
- `object_match` 只证“该事实对应本条件的对象”，不证“B 是 A 的复查”——裁决正确，我确认无既有维度可挪用。

**既有“同作业扩展”模式已经存在且应沿袭**：`PropositionEvidenceJobExecutor` 直接子类化通用两路执行器（`app/services/proposition_evidence_job.py:15-21` ← `app/services/judgment_content_job.py:150-165`，可插拔 input/batch/summary/read），生产侧复用 `binding_qualification_prompt_payload`（`llm/proposition_evidence.py:40`）。关系证书照此模式新增一个子任务，即“同一两路作业”的最小诚实实现：

- **合同（新）** `app/domain/contracts/observation_relation.py`（镜像 proposition_evidence.py）：`ObservationRelationCheck`，元组身份=(identity_sha256, 方案哈希， 初查fact+locator, 候选复查fact+locator)；结构化维度：`relation_kind ∈ {same_series_retest, same_cycle_continuation, unrelated_measurement, unresolved}`、双向角色支持、**双 locator 逐字引用**（分别校验属于两条摘录）、unresolved 原因；一致性键只取结构化维度。
- **生产者（新）** `app/llm/observation_relation.py`：复用 `binding_qualification_prompt_payload` + 关系元组清单；系统提示固定：角色只能来自原文可见的关联（复查医嘱引用、标本/序列编号、周期标注），**日期顺序只能佐证已认证关系的一致性，不能单独建立关系**；不新增事实/日期。
- **作业（新）** `app/services/observation_relation_{input,job,comparison,receipts}.py`（镜像 judgment_content/proposition_eposition 四件套）；input planner 只为“声明了复查方案 且 ≥2条合格 value 观察”的身份生成元组——空输入不调模型、存覆盖说明（沿用 proposition_evidence.py:36-37 模式）。
- **工作流**：新增固定版本子任务步骤（沿 §17.2 “工作流v2/v4固定子任务版本”惯例）。
- **验证/消费** `app/services/qualified_binding_selection.py`（消费算法 v11→v12）：`_select_with_ordering` 谓词分支消费证书：角色指派来自双路一致证书；方案次数上限用“已认证复查数”核对，超额观察列 not_selected（新原因 `repeat_count_exceeds_scheme`/`relation_unverified`）；时限用既有 `evaluate_time_constraint` 按方案声明锚点核算；`ordered_observation_selection.py` 增加 declared_repeat 分支——**入参是证书而非日期**，选中事实再走既有单事实数值比较（`expression.py` 现行路径，无需撤任何守卫）。
- **采信授权** `qualification-adoption-authorization/v5`：新增关系子任务回执字段（镜像 judgment_content/proposition_evidence 的采纳位，contracts/qualified_binding_selection.py:67-68 模式）；方法评测登记新 kind（仿 `pair_local_proposition_relation`，`qualified_proposition_evidence.py:10`）。
- **报告**：`QualifiedBindingIdentityOutcome.observation_ordering` 形状不变、原因枚举扩展；可加版本化附加字段引用证书 pair/job，供报告下钻“初查↔复查”链。
- **反“空消费者”验收**：本切片完成的判据是双向的——(a) 有双路证书的复查方案，复查值经既有求值器给出确定比较结果；(b) 无证书的第二条观察（或被认证为 unrelated）产出明确未定原因并进报告，绝不静默择优或回退初查。

**方案声明侧**：`ObservationOrdering`（contracts/observation_selection.py:40-53）增加 `declared_repeat` 方案对象（允许次数、替代或聚合语义、时限、触发引用到同组件兄弟谓词，复用 §17.3 atom_refs 引用模式；逐字原文校验沿 `rules.py:216-220` 既有约束）。触发的“临床意义”成分由被引用兄弟谓词自身的 requires_professional_judgment/judgment_content 链承担，组合即可，无新语义。

### 四、裁决#5：未来期间（prospective）——命题层复用评估（基于实际生产者输入）

- **可复用部分**：`PropositionEvidenceCheck` 的 entails/contradicts/basis/归属维度（contracts/proposition_evidence.py:28-33）足以承载“受试者声明研究期间无怀孕计划”这类意图命题的方向判定；声明记录作为 value/assertion_basis 配对走既有资格链（`llm/proposition_evidence.py:23-25` 已限定这两个属性）。
- **结构性缺口（证据）**：现有时间性维度是*观察范围*（scope_correspondence/assertion_extent/scope_population，:23-27），不是*声明期间覆盖*。生产者输入里 time_constraint/time_purpose 只是上下文，且系统提示把时间核算完全交给代码（`llm/proposition_evidence.py:61-63`）——但未来期间在筛选时点**没有可算的日期**（study_completion 未知），期间覆盖只能作为陈述自身措辞的核实维度。缺它，“目前无怀孕计划”（individual、当下限定）会错误地蕴含“研究期间无怀孕计划”。
- **修正设计**：`PropositionEvidenceCheck` v4→v5 增加 `declared_period_coverage ∈ {supported, partial, unresolved}` + `period_quote`（逐字校验属于该配对摘录）；当条件携带 `prospective_period/prospective_window`（`rules.py:162-182`）时必填；**声明记录的 date_range 资格（temporal_role=event_date）明令不得当作期间覆盖**——两者分列。
- **官方谓词显式模式**：`AtomicPredicate`（`rules.py:185-201`）现仅有 `requires_professional_judgment` 布尔，无来源陈述模式。增加显式 `verification_mode ∈ {numeric_comparison, source_statement}`（解构wire+门校验；source_statement 携带命题文本与结构化期间字段）；`_evaluate_atomic` 的 prospective 守卫（`expression.py:480-481`）对 numeric 路径保持，source_statement 谓词改经密封选择消费命题关系真值（镜像控制分支现行为 `qualified_binding_selection.py:546-573`：single 须 eligible==selected、时间操作数另核）。
- **生产者/方法扩展**：`_spec`（`llm/proposition_evidence.py:15-26`）现拒绝谓词族——放开接受声明了模式的谓词族配对；`require_proposition_method`（`qualified_proposition_evidence.py:9-23`）现仅 control 方法行——需评测并登记谓词族方法；采纳授权合同 v5 允许谓词族 proposition_evidence（现被 contracts/qualified_binding_selection.py:79-82 禁止）。**不扩大 judgment_content（研究者书面判断）语义到受试者陈述**——裁决遵守，意图声明走命题层新维度而非判断链。
- 报告侧：期间声明作为“已核实意图+结构化期间+后续复核义务”呈现，绝不做未来行为的事实判定。

### 五、首个完整实现切片建议（条件性复查端到端）

推荐**条件性复查**为第一切片，理由：Occurrence 的事件级资格前置（逐事件支撑事实全覆盖）与 prospective 的谓词族方法评测面都更重；复查切片最小且能一次贯通“方案声明→两路证书→确定性选择→求值→报告”，验证整条扩展模式。切片=第三节全部条目（合同#1、生产者、作业四件套、消费v12、授权v5、选择器分支、报告下钻），外加方案声明侧（wire/gate）。Occurrence 与 prospective 依同模式后续分片。各新子任务仍受 §17.6 方法评测+用户采信授权边界约束，不因本设计自动生效。

### 六、临床验收敏感决策（与实现选型分开列出）

1. 已声明复查方案下，无证书/被证无关的第二条观察：本设计定为阻断性未定（不回退初查）。若临床侧期望“回退初查值”，这是验收语义变化，须Codex/用户明示。
2. 摘要型频次陈述能否经语义路径替代事件计数满足官方排除条款——建议首片不放开（保持未定）；放开即改变“≥N次”的可接受证据面。
3. Prospective 反向声明（如“计划研究期间怀孕”）经命题层判定为 contradicts 后按普通例外/触发组合消费——是否作为确定排除输入属临床采信决定。
4. 三个新子任务（关系证书、谓词族命题、期间覆盖维度）各自需要独立方法评测与采信授权——既有边界，重申不豁免。

### 七、边界与不确定

- 全部结论为静态审阅；两路模型能否稳定产出关系角色证书、谓词族命题方法评测能否达标，须经真实评测，本会商无权运行。
- 未涉前端、迁移编号、批处理与最终集中验证；均属后续切片/Codex职权。
- 若Codex续问：可就 `ObservationRelationCheck` 字段级草案、wire schema 文案、或 occurrence 事件资格前置的精确判定（支撑事实部分不合格时的事件处置）做同会话补充审阅。
