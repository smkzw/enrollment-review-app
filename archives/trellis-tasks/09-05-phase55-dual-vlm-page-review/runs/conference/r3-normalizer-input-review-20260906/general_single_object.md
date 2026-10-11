证据链已闭合。所有关键疑点均已核实，现在输出完整审查报告。

# Conference Participant Output: r3-normalizer-input-review-20260906 - general_single_object

## Boundary Check

- 工作目录：仅限 runner 绑定的 worktree(`.`),未读取任何生产库、病例原文、`.env` 或凭据，未发起模型/网络调用，未修改任何文件，未读取其他与会者输出。
- 读取清单执行情况：初始读集 2 份已全读；Codex 列明的 4 个主源文件全读;`tests/` 按文件名探查(`test_page_review_candidate_sources.py`、`test_page_review_model_input.py`、`test_r3_page_review_normalizer_wiring.py`);设计权威按 §5.4(227-258 行)、§7.4(357-400 行)与实施计划 Phase 5.5(17、214 行起)限定读取。
- 超出字面清单但属授权范围的补充取证(均在目标“输入契约与来源校验”范围内，均为只读)：①`app/projections/page_review_pending.py`——被 `_model_input_payload` 直接调用(`evidence_normalizer.py:783`),是待核对观察进入语义输入的唯一投影源；②`app/domain/gates/fact_candidate_gates.py` 门禁函数签名与 `validate_candidate_reference_closure` 实现(401-505 行)——用于验证来源闭包是否有门禁兜底；③`app/agents/deepseek_evidence_normalizer_transport.py` 195-215 行——仅核实 `enforces_output_json_schema` 返回条件。无阻塞项，无越界读取。
- 未写 runner 报告路径；完整报告在本消息中返回。不主张任何最终临床/监管/视觉验收权。

## Independent Work Product

### 结论概览(按严重度)

**H1(最高影响缺陷)：R3“已采信才可引用”的候选来源闭包，在真实模型传输路径上没有任何确定性执行点。**
`validate_accepted_candidate_sources` 全仓只有两个调用点:`validate_evidence_normalizer_output`(`evidence_normalizer.py:1523-1525`)与单测。而该复合校验函数只在执行器的 `transport_fn` 分支被调用(`fact_normalization_executor.py:1121`,即结构化测试传输)；真实传输走 `EvidenceNormalizerRunner.run`,其解析循环只依次执行 `_filter_supported_requirement_bindings`→`_align_source_semantics`→`_enforce_exposure_source_fields`→空输出检查→`validate_output_page_closure`(`evidence_normalizer.py:1985-1999`),恰好缺失来源闭包这一项。门禁侧也无兜底:`validate_candidate_reference_closure`(`fact_candidate_gates.py:429`)只校验事件/暴露对 `fact_candidate_ids` 与 run/call 一致性，不检查事实候选的 `source_observation_refs`;合同层 `facts.py:240` 该字段允许为空列表。后果：真实模型若引用待核对观察、伪造 ref 或提交空 refs,将一路通过 runner、被 `apply()` 持久化(`fact_normalization_executor.py:1195-1232`)、进入发布门禁乃至发布事实，审计字段携带虚构溯源。这与系统合同文本(`evidence_normalizer.py:557-559`"R3 每个事实候选的 source_observation_refs 必须引用 accepted_observations……不得引用待核对项”)形成“文字禁止、执行放行”的矛盾。附带效应：该违规在测试路径会触发一次性的非重试 PARTIAL_OUTPUT,在真实路径连失败都不会发生。

**H2(会议上下文实测问题的根因定位)：待核对观察以全量观察转储进入语义输入，构成被禁止来源的重复语义处理。**
投影链为 `pending_page_observations`(`page_review_pending.py:46-91`)→`_model_input_payload`(`evidence_normalizer.py:797-800`)→`compact_page_review_input`(`page_review_model_input.py:14-28`)。压缩后每条 pending 仍携带:完整 `observation` 模型转储(含 region 摘录、raw/normalized 值、上下文)、lane、review_status/review_message、text_anchor、same_source_passage。同一摘录因此最多出现三份:`ocr_sidecar_pages` 页文、locator `localized_text`、observation excerpt(压缩仅在 anchor excerpt 与 region excerpt 相同时删一份)。合同(`evidence_normalizer.py:557-558`)只许 pending 用于“说明未解决项和定位原件"，于是模型被迫用自己的输出把系统已判定的待核对内容再叙述一遍——这正是实测 35,608/40,102/54,401/36,284 prompt tokens 与三次 16,384 输出被 reasoning 烧穿(16,346/16,336/16,334)的主要可压缩项之一。**待核对观察可以在语义生成之外确定性保全**，方案见下。

**最小修复方案(不改模型、不改阈值、不改临床语义):**

1. **H1 修复(约 5 行)**：在 `EvidenceNormalizerRunner.run` 解析循环内、`_enforce_exposure_source_fields` 之后插入 `validate_accepted_candidate_sources(output, evidence_input.page_review, locator_inputs=evidence_input.available_locators)`(attachment 为 None 时该函数自身早退,legacy 路径安全)。违规即 ValueError→进入既有 schema 修复循环，模型有界次机会自行补正 refs;预算耗尽返回“需要核对”。同时建议把 runner 与 `validate_evidence_normalizer_output` 的后解析校验清单抽成同一份有序列表，消除两路漂移(H1 正是漂移的既有实例;两路当前顺序也不一致:测试路径为 filter→**sources**→align→enforce→closure,runner 为 filter→align→enforce→closure)。
2. **H2 修复(确定性保全，推荐形态 a)**:
   - 语义输入剔除 `pending_observations`(删除 `_model_input_payload` 中该字段及 `compact_page_review_input` 对应分支);
   - 执行器在模型输出落库前，把每条 pending 观察确定性投影为持久化未解决项：身份=canonical_hash(call_id, 位置, 内容)，`gap_type=None`/`affected_requirement_ids=[]`(符合 draft schema oneOf 第一支),`affected_pages=[页]`,新增独立 `code`(如 `pending_observation_review`),message 取自 review_status/review_message,保留 source_document_version_id/page/摘录等溯源；
   - **页闭合职责精确切分**：runner 的 `validate_output_page_closure` 改为只对“有已采信观察或可用 locator 的页”负责(executor 侧 `_validate_persisted_page_closure`、`fact_normalization_executor.py:709-769` 维持全页闭合,种子项天然补齐 pending-only 页)。`transport_fn` 路径同步此切分，保持两路一致。
   - 不做模型项与种子项的语义去重(去重即重引入语义判断)；种子项独立编码、来源标记为系统派生，审计可区分。
   - 备选形态 b(仅压缩不剔除:pending 只留 kind/页/review_status/message)可作过渡,但仍留重复语义叙述，不推荐为终态。
3. **回归测试最小集**:`test_page_review_candidate_sources.py` 增“引用 pending 身份构造的 ref 必须失败";`test_evidence_normalizer_adapter.py` 增真实 runner 形态用例(伪造 ref/空 refs→runner 循环内失败并触发修复,不得到达 `PreparedStepResult`);`test_page_review_model_input.py` 增"payload 无 pending_observations"与既有语义保留断言;wiring 测试增"种子未解决项身份确定性、含 review_status 溯源、全页闭合通过"。

**空已采信输入绕过模型调用的判定：本阶段不建议实现，但契约上可行且边界清晰。**
若某调用全部页零已采信观察，R3 合同下候选集合必为空(候选只能引自 accepted_observations),模型唯一增值是替 pending/空页写叙述性未解决项——正是 H2 要消除的重复处理。确定性闭合(种子项)可保全缺口且不弱化采信。但有三处必须先决策:(i)审计身份——`FactNormalizationCallRecord.raw_output_sha256` 对无模型调用如何取值，需要显式 bypass 标记，否则审计谎称“本次调用了模型 X”;(ii) `_rebuild_call_checkpoint_from_persisted` 要求候选或未解决项非空(`fact_normalization_executor.py:916-921`),种子项可满足，但空页且零 pending 的真空页需要一个确定性“无内容闭合”项；(iii)legacy 路径(`page_review is None`,仍以 effective_text 抽取否定/肯定事实)绝不适用。**建议顺序：先落 H1+H2,复测 token 与超时后，再凭实测决定是否值得为省一次小调用引入 bypass 的审计复杂度。**

**工程成功与临床采信的边界(按会议目标明示)**：24/24 页恢复与 47 个检查点精确复用是传输/编排证据；7c81237d 正式运行三组 0/1/0 候选、10/11/12 未解决项、第四组 600 秒超时，`GateOutcome.ACCEPTED` 与 `FactNormalizationRunStatus.SUCCEEDED` 是门禁/任务状态，均不构成任何临床采信。本报告全部建议仅针对输入契约完整性与工程可靠性；对已发布事实的临床正确性不作任何判断。

### 次要发现

- **L1**:`compact_page_review_input` 删除页级 `accepted_clause_signals` 的注释声称"accepted_observations 已承载"，但 `accepted_observations` 明确跳过 `signal==NONE` 的条款信号(`page_review_sources.py:17-18`)——signal=NONE 且有 region 的已采信条款信号在压缩后从输入中完全消失。因其同样不可被候选引用(校验字典同样排除)，删除与闭包契约一致、不构成漏洞，但属“注释与行为不符”，建议加钉住测试或在注释中写明 NONE 例外。
- **L2**:`accepted_observations` 的 ref 身份含列表 `index`(`page_review_sources.py:26`),仅对冻结 reviews 顺序稳定；投影与校验用同一附件实例，当前一致。建议钉住测试防未来排序漂移。
- **L3**:`_MAX_PROMPT_CHARS=100_000` 对 R3 输入显式禁用(`evidence_normalizer.py:876-881`),R3 提示无任何字符上界，输入投影是唯一杠杆——支持 H2 优先做投影瘦身。
- **L4**:GLM 走 `json_object` 路由时 `enforces_output_json_schema=False`,紧凑 Schema 仍整体内嵌提示(`deepseek_evidence_normalizer_transport.py:207-215` docstring);是否已用 `json_schema` 受限解码属配置事实，影响每调用数千 token,见问题 Q3/Q4。
- **L5**:`compact_page_review_input` 对 pending 公共字段提升与 anchor 哈希/摘录剥离逻辑正确(anchor 摘录仅在与 observation region 摘录逐字相同时删，页文仍在 `ocr_sidecar_pages`,可验证性不损失)，建议以混合值页用例钉住。

## Evidence And Assumptions

** sourced 事实(文件：行)**:
- 来源闭包仅两处调用:`app/agents/evidence_normalizer.py:1523-1525`;执行器仅 transport_fn 分支调用复合校验:`app/services/fact_normalization_executor.py:1121`;runner 解析循环无该项:`app/agents/evidence_normalizer.py:1985-1999`。
- 门禁无 observation 引用校验:`app/domain/gates/fact_candidate_gates.py:429-505`(仅 fact_candidate_ids/run/call);合同字段可空:`app/domain/contracts/facts.py:240`。
- pending 全量入投影:`app/projections/page_review_pending.py:63-75`、`app/agents/evidence_normalizer.py:797-800`;压缩行为:`app/projections/page_review_model_input.py:6-29`。
- 合同禁令文本:`app/agents/evidence_normalizer.py:556-559`;空输出防线:`app/services/fact_normalization_executor.py:1115-1120、1168-1170`;全页闭合持久校验:`app/services/fact_normalization_executor.py:709-769`;checkpoint 重建要求非空:`app/services/fact_normalization_executor.py:916-921`。
- 跳过 NONE 条款信号:`app/projections/page_review_sources.py:17-18`;refs 闭包与摘录核对:`app/projections/page_review_sources.py:46-59`。
- 设计权威：§7.4 双盲与候选隔离、页覆盖完整性(“舍弃是审计对象”)、页级信号非判定；§5.4 病历否认/未提及/转述溯源规则；Phase 5.5 计划 17 行“执行器草稿未验证，不列为完成”。

**推断(标注为推断)**:prompt token 主因排序为 pending 全量转储 > 摘录三重复制 > Schema 内嵌(视路由)；reasoning 烧穿输出上限与超长输入相关但传输层根因未证(上下文第 32 行亦自述“不是传输根因证明”)。

**假设**：真实 GLM 正式调用当前走 runner 路径(由执行器代码结构推断，H1 的现实暴露面据此成立)；冻结附件 `reviews` 顺序稳定。

## Risks, Gaps, And Verification Needs

1. **H1 未修复前，任何 R3 正式运行的已发布事实都携带“未经验证的溯源引用”风险**——不仅丢缺口，更可能把待核对读值伪装成已采信来源引用发布。验证需求：新增 runner 形态回归测试必须证明违规输出在 `apply()` 之前被拦(可用 transport_fn 之外的真实 transport stub)。
2. **H2 形态 a 改变模型可见输入**(待核对观察不再可见)。临床语义不变：候选可引集合、pending 不可引规则、冲突保留(页级 `fact_conflicts`/`signal_conflicts` 仍在输入)均不变；但需 Codex 明确裁决“系统派生未解决项”是否可入 `fact_normalization_unresolved_items` 存储(Q1)——这是形态 a 与 b 的分叉点，不是实现细节。
3. **页闭合职责切分是形态 a 的必要配套**：若只删 pending 不改 `validate_output_page_closure`,pending-only 页将无法闭合、runner 误报。两路(runner 与 `validate_evidence_normalizer_output`)必须同步修改，否则再现 H1 式漂移。
4. **种子项不得携带 `gap_type`**(除非确定性可绑定 requirement),否则会泄入 `_expectation_gap_signals` 改变资料期望投影——当前建议一律 `gap_type=None`,要求绑定留给后续节点汇总层。
5. **bypass 的审计语义未定义**(raw_output_sha256、调用记录状态、`_load_frozen_agent_config` 在无模型调用时的意义)，先于实现决策(Q2)。
6. **实测归因待验证**:H2 落地后复测同组 prompt/output tokens 与时长，才能归因第四组 600 秒超时；在此之前不得声称已修复传输根因。600 秒客户端超时(`deepseek_evidence_normalizer_transport.py:199`)属阈值参数，本轮不动。
7. **次要项验证**:L1/L2/L5 各需一个钉住测试；Schema 内嵌与否需确认实际路由配置(Q4)。

## Recommended Next Step

按序提交 Codex 裁决与执行：

1. **立即(H1,小 diff+测试)**：runner 解析循环补 `validate_accepted_candidate_sources`,并抽出 runner/复合校验共享的后解析校验清单；测试如上最小集。
2. **本会议内决策(Q1)**:待核对观察“确定性种子未解决项(形态 a)” vs “仅压缩保留(形态 b)”。我的推荐是形态 a,理由：彻底消除重复语义处理、prompt/output 双降、缺口证据确定性保全且审计可区分；页闭合职责切分方案已给出。
3. **决策后测，再议 bypass(Q2)**:H1+H2 落地并复测 token/时长后，凭实测决定空已采信调用是否值得引入带审计标记的非模型调用记录。
4. **两个有界问题请 Codex 同会话答复**：Q3——为 GLM normalizer 传输启用 `json_schema` 受限解码是否越过“不改变模型与阈值”边界(我的读法：输出约束机制变化，非模型/阈值变化，倾向允许但请裁决)；Q4——当前正式 GLM 调用实际路由是 `json_schema` 还是 `json_object`(决定 Schema 是否在提示内重复、H2 之外还有多少可省 token)。
5. **重申边界**：以上均为输入契约与工程完整性修复；候选计数、发布事实与个例档案的临床正确性仍需人工与 Codex 验收，24/24 覆盖不构成采信证据。
