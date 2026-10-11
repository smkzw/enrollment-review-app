# Conference Output: r3-normalizer-scope-review-20260909 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅）。静态源码审阅，未运行代码、未读临床数据（按 Source Of Truth 约束）。审阅范围：verified-observations-only normalizer scope + deterministic pending retention 的拟议最小改动（未实施），判定临床/来源损失与最小安全集成要求。

### 一、总裁决（建议）

**有条件接受（accept with conditions）。** 拟议方向正确且有代码与实测支撑，但按当前表述直接实施会出现一个高优先级集成缺陷（见 Objection 1，页闭合失败）和一个静默损失（Objection 2，条款信号冲突无确定性保留家）。满足下述 8 项最小集成条件后，提议范围可以安全落地；其中条件 1（保留 OCR sidecar 与 locators）直接回答了 Objective 中"Should OCR sidecar/other locators remain"的问题：**必须保留**。

设计文档本身已把举证责任写明（`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md:228`）："更大幅裁剪待核对模型上下文尚未实施，须证明资料要求关联和关键缺口不会损失。" 本报告逐项核对了这两个举证点，结论：在满足条件后两者均不损失（详见第三节维度 1、4）。

### 二、主要异议与补救（按影响排序）

**Objection 1（最高影响，集成缺陷）：页闭合校验先于保留项追加，拟议改动按字面实施会导致混合调用硬失败。**
证据：`app/agents/evidence_normalizer.py:2025` 中 runner 在解析后立即调用 `_validate_normalizer_semantics` → `validate_output_page_closure`（`evidence_normalizer.py:1834-1864`），要求每页被候选或未解决项覆盖；而 `pending_retention_items` 是执行器在模型输出**之后**追加（`app/services/fact_normalization_executor.py:1196-1203`）。当前 v23 下模型能看见 pending 原文所以能自行逐页闭合；v3 只给计数后，若提示词同时告诉模型“待核对细节已由代码保留、不要复述”，则混合调用（同调用内既有已采信页又有纯待核对页）中纯待核对页无人闭合 → runner 页闭合失败 → schema 修复循环 → `PARTIAL_OUTPUT` 作业失败。
补救（二选一，推荐前者）：
- (a) 最小安全：提示词保留一条机械义务——“没有可用已核实观察的每页，输出一条仅引用计数的未解决项（如 code=`page_pending_observations`），不得复述原文”。与保留项重复无害（code 不同、身份不同），不改 runner 签名。
- (b) 后续优化：`validate_output_page_closure` 增加 `precovered_pages` 参数，由执行器从 `pending_retention_items(evidence_input)` 预计算纯待核对页。更干净但改 runner 链路，建议 v3 稳定后再做。

**Objection 2（静默损失）：移除 `signal_conflicts` 后，条款证据信号分歧在产品输出层无任何确定性保留。**
证据：`pending_page_observations` 只迭代 `("facts", "handwriting")` 两类（`app/projections/page_review_pending.py:53-55`），条款信号从不进入保留项；R3 视觉策略下 `accepted_observations(include_clause_signals=False)`（`app/agents/evidence_normalizer.py:818-819`），`accepted_clause_signals` 又已被 `compact_page_review_input` 剥离——即当前 v23 模型视图中条款信号的唯一残余就是 `signal_conflicts` 摘要；下游无其他消费者（rg 确认仅 normalizer 输入路径引用）。两主读对同一条款的 evidence_for/against 分歧（`app/domain/page_reconciliation.py:126-141`，reason="语义条款证据信号未形成双主读一致"）是真实的临床相关分歧信号，v3 按提议删除后只剩持久化对账记录（审计可查但用户不可见），违反“no hidden silent loss”边界。
补救（推荐）：在每页 pending 摘要中加 signal_conflict 计数与涉及 clause 的 `field_name` 列表，并在 `pending_observations_report` 中为有 signal_conflicts 的页追加一行确定性保留（固定 reason，不新增事实、不加模型负担）。替代方案（需 Codex 明确决策）：接受 audit-only 并在覆盖报告中给用户可见指针；无指针则拒绝该项删除。

**Objection 3（兼容性）：任何系统合同文本变更都会使旧冻结作业恢复失败，须按既定规则显式排程。**
证据：`_load_frozen_agent_config` 用当前代码哈希对比 DB 冻结行（`fact_normalization_executor.py:542-549`），哈希覆盖 `_PROMPT_LAYOUT_VERSION + 模板 + _SYSTEM_CONTRACT + 修复合同 + schema`（`evidence_normalizer.py:605-617`）。v3 必然改合同文本（描述计数与保留标记），升级后在飞的 None/v1/v2 作业 resume 时 fail-closed（`PARTIAL_OUTPUT`"冻结提示词内容与当前证据规范化模板不一致"）。设计文档已接受“新提示不续跑旧版本失败任务”（doc:230），v22→v23 同模式。这不是阻断项，但属于"old policy compatibility"检查点的必答内容：要么部署前排空在飞作业，要么采用按 policy 变体的合同与变体感知哈希（旧作业逐字节稳定，代码量略增）。推荐前者（先例一致、更简单），条件是不存在不可放弃的在飞生产作业——见 bounded Q1。

### 三、逐维度核查（任务指定的检查点）

1. **研究者书面判断缺口（investigator written judgment）— 不损失。** 判断缺失信号完全由确定性代码产生：`_expectation_gap_signals`（`fact_normalization_executor.py:223-253`）对到期且无覆盖模板发 `PROFESSIONAL_JUDGMENT`；投影层（`app/projections/evidence_expectations.py:253-275`）对 `investigator_assessment`-only 模板即使有弱覆盖也在无完整来源时落 `ABSENT/PROFESSIONAL_JUDGMENT`。pending 中的未核实书面判断本就不许成为事实（正确），其原文由保留项逐字保存，期望层正确报告"无法判定"（符合用户确认的§16：报告而不阻断）。措辞细节：gap_detail 说“未见研究者书面判断”，即使存在待核实记载——保守方向正确，可作后续措辞优化，不属本次必改。
2. **冲突值/否定/时间 — 不损失。** 两读道的全部未采信观察由 `pending_retention_items` 逐字保留（field_name/raw_value/raw_text/excerpt/context/手写类别），且携带 `review_status` 消息（如“同一对象的原文读值不一致，请核对原件”，`page_review_pending.py:30-35`）。`fact_conflicts`/`handwriting_conflicts` 摘要不含保留项没有的临床内容，删除安全。跨读道否定/时间误读在值比较无法判定时落 `association_pending`，两侧原文仍都在——保守保留，无静默丢失。
3. **unknown vs not-done — 不受影响且更精确。** 极性/缺口规则不变；模型看不到待核对原文后更不可能把未核实内容误标为未执行。到期未覆盖需求由确定性 `RECORD_INCOMPLETE` 兜底。
4. **需求绑定（requirement binding）— 对已采信内容不损失；对 pending 内容有意放弃，需实测举证。** `related_requirements` 保留在输入中（提议明确），已采信候选的 `supported_requirement_ids` 与未解决项绑定仍对冻结集合闭包校验（`evidence_normalizer.py:1563-1594`）。放弃的是"模型把待核对内容绑定到需求"——这本就是可选行为且不可靠；设计文档要求的举证（“资料要求关联不会损失”）由条件 8 的对照实测满足：v2/v3 同冻结输入的 gap signals 与期望投影确定性部分必须逐位一致。
5. **漏报 pending（missing pending reports）— 有一处真实缺口即 Objection 2；其余为有意且正确的取舍。** 模型不再对待核对内容做语义观察（如“该摘录疑似数值单位不符”）是正确取舍：语义核实职责属于独立的最多两轮双模型冲突复核（scope 明确 normalizer 不得重做），保留项保证"模型漏写不导致其消失"（doc:228 已验证的 v2 性质）。弃置页（`DISCARDED_NO_ELIGIBILITY_VALUE`）观察不保留是有意设计（弃置理由在 `page_dispositions` 可见），可接受，建议在实现说明中写明。
6. **旧策略兼容 — 见 Objection 3。** 策略经作业载荷+幂等 scope 哈希版本化（`fact_normalization_job_service.py:434-439,473-475,553-555`），v3 只需新常量并在这三处一致替换（当前三处硬编码 v2 常量，漏一处即 scope 漂移）；执行器允许集元组扩展（`fact_normalization_executor.py:1127-1130`）。旧 None/v1/v2 语义本身不受影响。
7. **来源交叉绑定（source cross-binding）— 不受影响。** `source_observation_refs ⊆ 已采信引用`、定位页=观察页、视觉定位绑定 cited 观察，全部确定性校验（`page_review_sources.py:35-98`）；来源语义由冻结元数据确定性再对齐（`_align_source_semantics`）。前提是条件 1 成立（sidecar+locators 保留），否则模型选不出能通过校验的定位。

### 四、最小安全集成要求（条件清单）

1. **保留**：`context`、`related_requirements`、`ocr_sidecar_pages`（整页有效文本）、`locators`（含 localized_text 与 page_review_visual 标记）、`accepted_observations`（facts+handwriting 全量观察）、`page_dispositions`。理由：来源语义判定（document_type/source_party 约束）、日期/事件归属核对（合同明文要求在所引原文中核对日期关系，`context.time_text` 不是证明）、摘录锚定（模型须先看见定位原文才能产出通过 `validate_accepted_candidate_sources` 的候选）、纯条款信号页的页闭合兜底，全依赖整页文本与定位。
2. **仅从模型视图移除**：`pending_observation_groups` 明细、`fact_conflicts`、`handwriting_conflicts`（两侧观察已逐字确定性保留）。
3. **新增每页 pending 摘要**：按 kind 与 review_status 的计数 + 冻结策略标记（如 `"pending_retention": "code-retained/v1"`），明确告知模型细节已由代码保留、禁止复述。
4. **signal_conflicts 不得静默丢**（Objection 2 补救，推荐确定性保留行）。
5. **页闭合义务**按 Objection 1(a) 保留模型侧一行机械闭合项。
6. **新策略常量 `preserve-pending/v3`**：job service 三处一致写入；执行器允许集扩展；保留项追加对 v3 同样生效。
7. **提示版本**：`_PROMPT_LAYOUT_VERSION` v23→v24 + 注册新 PromptVersion；部署排程按 Objection 3 决策。
8. **上线前对照实测门（doc 要求的举证）**：冻结 runtime-03 两页样本，v2 vs v3 对比 (a) 带 `affected_requirement_ids` 的 gap signals、(b) `ABSENT/PROFESSIONAL_JUDGMENT` 期望状态集合、(c) 每条 pending 观察 id 均出现在某保留项 reason 中（覆盖完整性），以及 prompt/completion tokens 与时长。通过前 v3 不进正式入口（与 doc:230 小样流程一致）。

### 五、具体最小编辑与测试

编辑（按第四节条件）：
- `app/projections/page_review_pending_normalization.py`：加 `PENDING_NORMALIZATION_POLICY_V3`。
- `app/projections/page_review_model_input.py`：v3 投影函数——pending 摘要替换 groups、删三类 conflicts 载荷、加 signal_conflict 摘要；policy 经参数显式传入（`_model_input_payload` 目前只从 `evidence_input` 构建，需把 policy 穿透 `build_evidence_normalizer_prompt`）。
- `app/agents/evidence_normalizer.py`：合同增量（计数语义+保留标记+一行闭合义务），bump 布局版本；如选变体方案则哈希函数感知变体。
- `app/services/fact_normalization_executor.py`：策略元组加 v3；保留项追加条件覆盖 v3；prompt 构建传 policy。
- `app/services/fending_normalization_job_service.py`：三处常量替换。
- `app/projections/pending_observations_report.py`：（条件 4 采纳时）signal_conflict 保留行。

测试（沿用现有模式）：
- `tests/v2/services/test_page_review_model_input.py`：v3 投影不含 pending 原文与三类 conflicts、含计数与标记、accepted_observations 不变。
- `tests/v2/services/test_r3_page_review_normalizer_wiring.py` 增参数化：v3 下模型 prompt 不含 pending `raw_value`；保留项仍持久化且计数一致；全 pending 调用 `model_called=False`；混合调用经一行闭合项通过 runner 页闭合；v2/None 载荷行为与提示逐字节不变（若选全局 bump 则改为断言旧哈希失效 fail-closed）。
- `tests/v2/projections/test_pending_observations_report.py`：signal_conflict 保留行（如采纳）；计数摘要与 `pending_page_observations` 输出一致性。
- 确定性等价测试：同冻结输入 v2/v3 的 gap signals 与期望投影输出相等（保留项 gap_type 均为 None，不进信号）。

### 六、对现有 pending 辅助模块的独立缺陷标记（按要求独立于提议）

- **D1**：`pending_observations_report` 每页单条 `reason` 串接全部条目；144 条 pending 观测（owner 实测）会生成超长单条目。持久化安全、下游不扩散（gap_type=None 不进期望信号），但单卡片 UI 不可用。本次不改（YAGNI），登记备查；若要做，仅“前 N 条+余量计数”。
- **D2**：`_fact_review_status` 要求 `observation.context` 非空且对侧唯一身份匹配才判值分歧；无 context 的待核对项一律 `association_pending`。保守不误报，但分歧检出率偏低——两侧原文仍都保留，非正确性问题。
- **D3**：`_unique_text_anchor` 要求摘录在页文本中唯一；重复摘录（检验表常见）无锚，`same_source_passage` 对 >2 条同段落也不标记。仅影响 v23 模型视图联动，保留项不受影响；v3 计数化后此路径对模型视图基本失效，属可接受衰减。
- **D4**：`pending_only_output` 对调用内全部页（含弃置页）发"暂无已核实内容”；措辞对弃置页偏钝但准确，弃置理由另有展示。外观问题。

### 七、Codex 决策点与有界问题

- **Q1（部署形态）**：升级时是否存在不可放弃的在飞 v2/None 作业？无 → 推荐全局 v24 bump + 排空；有 → 变体门控合同与哈希。安全临时路径：先 v3 仅写新作业、旧作业排空后再 bump。
- **Q2（Objection 2 取舍）**：signal_conflicts 走确定性保留行（推荐）还是 audit-only + 用户可见指针？后者无指针则应拒绝该项删除。
- **Q3（闭合机制）**：先模型侧一行计数闭合项（推荐），验证后再做 validator `precovered_pages` 松弛？
- **Q4（实测门归属）**：条件 8 的冻结样本对照由 owner 执行并留档后，v3 常量才切正式入口——确认此顺序？

### 八、证据/推断/建议/不确定性分列

- **证据（源码直接核实）**：模型视图构成与剥离点（`evidence_normalizer.py:742-860`、`page_review_model_input.py`）；v2 保留项追加时序与再校验（`fact_normalization_executor.py:1196-1203`）；runner 先验页闭合（`evidence_normalizer.py:2000-2025`）；条款信号不进保留（`page_review_pending.py:53-55`）且下游无消费者（rg）；期望信号确定性与投影短路逻辑（`evidence_expectations.py:238-356`）；策略幂等接线（job service 434-475、553-555）；设计文档举证义务与不续跑规则（doc:226-230、§16）。
- **推断**：v3 计数化将降低 prompt 与 reasoning 开销（依据 owner 的 v22→v23 实测方向：分组减 prompt 但增 completion/耗时；推断而非证明）；signal_conflicts 临床价值为中等（条款方向分歧可见性）。
- **建议**：有条件接受 + 第四节 8 条 + 第五节编辑/测试。
- **不确定性**：静态审阅未运行测试；v22/v23 token/耗时为 owner 提供的测量值非金标；未核验 PromptVersion 注册的迁移细节（预期无 schema 变更）；混合调用中模型对“一行闭合项”指令的遵循度需实测确认（失败模式已由 fail-closed 兜住，不会静默）。

报告完毕，未写入任何运行器管理路径；请 Codex 汇总裁量。
