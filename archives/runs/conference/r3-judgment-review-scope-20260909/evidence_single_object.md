I'll start from the conference context and the assigned source list, then independently check the judgment-review evidence contract without writing files or expanding into raw clinical material.Conference context is mostly a placeholder, so I’ll audit the assigned design section and source files independently rather than treating the packet notes as settled.The design already separates “verified absence of investigator judgment” from unverified reads; next I’ll check whether the code actually keeps that distinction.I’ll now check the page-review contracts, handwriting comparison, and the tests that claim to separate verified absence from unverified reads.# Conference Output: r3-judgment-review-scope-20260909 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅）。只读、不改源码、不跑模型/服务、不访问网络/库/病例。会议上下文与主场计划几乎全是 TODO，本报告以指定源码与设计 §16 为准，不把拟案当既定结论。未做最终临床/监管/视觉验收。

### 审阅边界

**已读（授权集）：**  
`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §11/§15 冲突复核段/§16；`app/domain/targeted_page_review.py`；`app/domain/contracts/page_review_focus.py`；`app/services/targeted_page_review_jobs.py`；`app/services/targeted_page_review_executor.py`；`app/services/targeted_review_candidates.py`；`app/services/fact_normalization_executor.py` 的 `_expectation_gap_signals` 及 pending 追加处；`app/services/evidence_expectation_projection_service.py` 的 `_observations`；`app/projections/evidence_expectations.py`；`app/projections/pending_observations_report.py`；`app/llm/page_review_repair_preservation.py` 与其测试；直接导入的 `page_review.py` / `targeted_review_outcome.py` / `evidence_expectations_v2.py` / `evidence_normalizer.py`（UnresolvedItem）/ `enums.py`（GapType）/ `evidence.py`（Template）；相邻 `page_reconciliation.py`、`page_review_pending.py`、`page_review_harness.py` 针对性提示、`page_review_format_repair.py`；`tests/v2` 中 targeted / expectation / pending / format_repair / handwriting 相关测试。

**未读（按合同）：** 数据库、env、病例、其他运行目录、网络。检索曾扫到 `artifacts/` 路径名，未把那些副本当证据。

**需要扩大才可闭合、本轮未扩：** `app/pipeline/reviewer.py` 里旧 CS/NCS 散文正则（仅检索命中，不作产品读道）；规则原子 `requires_professional_judgment` 如何投影成 `required_source_types`；正式 HTTP/UI 是否把 `professional_judgment` 直接显示成“确无书面判断”。

---

### 对四条拟案的独立核实

#### 1. 两轮链目前只吃“同对象/时间键的结构化数值事实”——**已证实**。把待核对手写做成类型化复核——**方向对，但不可并进现有 `compare_targeted_reads`。**

**证据**

- `explicit_conflict_fields` 只索引 `record.facts`，且要求 `context.target_text` 非空、两侧同一 `(field, context_key)`、各恰好一条、`_structured_value`（纯数值/比较符或日期）且 `_value` 不等。手写、自由文本、对象键不一致都进不了。
- `enqueue_targeted_review` / `targeted_review_candidates` 的唯一入口就是上述函数；无目标则 `TargetedReviewNotReady`：“该页没有明确的数值、日期或标记分歧；文字表述与对应关系需另行核对”。
- 测试 `test_text_summary_difference_does_not_start_value_reread` 已钉死：文字摘要分歧不得启动数值复核。
- 手写分歧在 `reconcile_page_reviews` 里另记，`field_name` 恒为 `"handwriting"`，从不进入辅助作业。
- 现有两轮机制本身已具备拟案要的外壳：首轮 `PageReviewFocus` 禁止 `candidate_excerpts`；次轮才注入上一轮摘录；`candidate_auto_accept` 恒为 `False`；辅助记录不进正式事实/覆盖。但次轮摘录只从 `record.facts` 按字段名收集，不含 handwriting。

**推断**

拟案“只读当前原页、不强配检验、盲读/次轮只展示上一轮原文、一致仍只作未采信候选”与已接线辅助链的**作业外壳**兼容，与**比较函数**不兼容。若把 `"handwriting"` 或 CS/NCS 原文塞进现有 `targets: tuple[str, ...]`，`compare_targeted_reads` 会按事实字段名查找，手写永远 `pending`，次轮 `cue_kind` 仍可能是 `blind`。

**建议（最小）**

- 保留现有数值/日期链不动。
- 新增与 `explicit_conflict_fields` 并列的手写目标函数，身份用已有字段：`kind` + `context.target_text` + `region.excerpt`（及必要时 `time_text`），不要用冲突记录里那个总名 `"handwriting"`。
- 比较用全文结构（kind/raw_text/context/excerpt），不要走 `_structured_value`。
- `PageReviewFocus` 加判别（`structured_fact` | `handwriting`），并 bump `TARGETED_REVIEW_VERSION`；次轮摘录按目标类型取 facts 或 handwriting。
- 入队条件收窄：两侧都有同类且 `target_text` 非空、原文或所指不一致。单侧有、无对象、对象对不上 → 仍待核对，不启动两轮、不升级为缺失。
- 一致也不得发布为 `investigator_assessment` 事实。

**反例**

- 同页 WBC 数值双读一致，旁注 “NCS” 一侧读到、一侧未读到：当前两轮不启动（对）；若为“有手写就复核”而强配到该检验，则违反“不强配”。
- 两侧都写 CS/NCS，但 `target_text` 分别为“白细胞”与空：对账已是 handwriting conflict；若当数值目标入队，比较函数无法对齐。
- 两侧 `raw_text` 同为 “NCS” 且对象同为“白细胞”：现有对账可双源接受手写；辅助链不应再采信为条款结论。

**过度设计：** 新作业类型、第三读道、第三模型、用文件类别/同页/同权威当手写目标。

---

#### 2. `_expectation_gap_signals` 把“当前无已核实判断”做成 `professional_judgment`，待核对手写因未绑 requirement 被跳过——**已证实，且是本轮最高影响缺陷。** 这不是“可能”误标，而是结构性误标。

**证据**

1. `pending_retention_items` 产出 `code=page_observation_unverified`，**不设** `gap_type`、**不设** `affected_requirement_ids`。合同还规定：绑 requirement 必须同时有 `gap_type`，且 **不允许** `PROFESSIONAL_JUDGMENT`。
2. `_expectation_gap_signals` 对 `gap_type is None` 的未解决项直接 `continue`。待核对手写因此对期望投影隐形。
3. 随后对每个到期、尚无“具体缺口”的模板：只要 `required_source_types` 含 `investigator_assessment`，就**自动**追加 `GapType.PROFESSIONAL_JUDGMENT`，文案为“当前尚无已核实的研究者书面判断……”。否则追加 `RECORD_INCOMPLETE`。
4. 该填充**不检查**双主读是否都成功、范围是否一致、是否漏页、是否存在 `page_observation_unverified`、手写冲突或单源手写。
5. 投影器在无覆盖且无信号时会拒绝通用回退；上述自动填充把“禁止的通用回退”挪到了上游，再喂给投影器。
6. 设计 §16 前提：“相应资料已完成有效读取和范围核对；模型失败、漏页、仅一页未见或两路范围不一致，不得冒称已经核实缺少研究者判断。” 自动填充直接违反该前提。
7. 设计 2026-09-06：辅助复核“不能作为研究者判断缺失的条款报告依据”；“条款级书面判断缺失报告仍按 §16 单独实现”。

**推断**

现有三态被压成两态：`OBSERVED`（实际对书面判断几乎不可达，见第 3 点）与 `ABSENT + professional_judgment`。真正的“读取/归属待核对”被跳过。`page_observation_unverified` 只留在规范化未解决项里，期望层把它当成“没有判断”。

**建议（最小、通用、可测）**

用**三个互斥证据合同**，不要靠文件类别、同页、同权威或再调一次模型：

| 状态 | 何时成立 | 用什么现有字段 | 缺口 |
|---|---|---|---|
| 已核实适用判断 | 双主读接受的手写/事实：`context.target_text` 非空，摘录在，且 **显式** `supported_requirement_ids` 含该 `requirement_id`，节点=当前 `workflow_stage_id` | `accepted_handwriting` / 已发布事实的 `fact_type`+`locator`+`supported_requirement_ids` | 无（`OBSERVED`） |
| 读取或归属待核对 | 存在 `page_observation_unverified`，或单源、对象空、两路范围不一致、读失败、漏页 | `pending_retention_items` 的 code/原文；`review_status` | **禁止** `professional_judgment`。投影要么带已有 `OCR_OR_PARSE_RISK`（仅当已有解析/门禁拒绝），要么**闭包失败** `EVIDENCE_EXPECTATION_INPUT_INCOMPLETE`，要么引入/放开一个“未核实”缺口；流程继续，claims_complete 仍 false |
| 明确且完整范围内未见 | **仅当** 适用资料已双主读成功、范围一致、无该条款对象的待核对手写/事实，才报缺失 | 条款/节点/原件定位 + 设计示例文案 | 这时才 `professional_judgment`，且不阻断作业 |

**不要做：** 把未绑 requirement 的手写自动挂到所有 `investigator_assessment` 模板（同页传播）。未绑就保持未核实；没有可证缺失就**不伪造**缺失。投影器已会在无信号时拒绝——应保留该拒绝，而不是在 executor 里补一个判断缺口。

**反例**

- 检验页一侧 “NCS / 白细胞”，另一侧空手写：pending 保留原文，但期望仍可能对所有书面判断要求报 `professional_judgment`。
- 一页读失败、其余页无判断：§16 禁止称已核实缺失；当前仍会填 `professional_judgment`。
- 到期模板尚无任何页覆盖完成：同样被填成确无记录。

**过度设计：** 新期望状态机、用文件类型猜适用页、为每个 pending 条目调模型去绑条款。

---

#### 3. 正向书面判断必须是原摘录 + 所指对象/节点；同页批注不能覆盖所有要求。CS/NCS 不得用项目正则变结论。——**拟案正确。当前正向覆盖路径实际上是断的。**

**证据**

- 设计 §11：无阈值异常仅报告单批注或对应节点病历分析才算书面判断；箭头/圈画不算；CS/NCS 必须针对何项目，不能从一项传到整张报告。
- `ObservationContext.target_text` + `HandwritingKind.CS_NCS_JUDGMENT` + `region.excerpt` 已能表达“这段字、指哪个对象”。`handwriting_normalization_key` 把 kind、原文、context 编进键，**没有**把 NCS 映射成入排结论。测试 `test_handwriting_targets_and_polarity_are_part_of_association` 证明对象不同则键不同。
- `_observations` 注释正确（“文件类别不能证明含书面判断”），但实现是：`document_type == "investigator_assessment"` 时**不写入** `source_types`；其它类型才写入。结果是该服务路径下 `source_types` **永远不含** `investigator_assessment`。
- `_coverage_verdict`：模板若要求 `investigator_assessment`，则 `source_type_matches` 必须看到该字面量 → 在上述路径上恒假 → 完好覆盖不可达。
- 投影器在“无 complete + 有 judgment_gap + 要求书面判断”时，把本可弱覆盖的检验事实打成 `ABSENT + professional_judgment`。再叠加第 2 点的自动 `judgment_gap`，书面判断要求被锁死为缺失。
- `_matching_observations` **未**按模板 `fact_type` 过滤，尽管模块注释写“精确 fact_type”。`test_lab_result_does_not_replace_required_written_judgment` 靠的是来源类型否决，不是 fact_type。
- `AtomicPredicate.requires_professional_judgment` 已存在，但是规则层，不是页观察覆盖键。

**可复用、不必新增的字段**

- 观察：`excerpt`、`raw_text`、`kind`、`context.target_text/time_text/location_text/polarity`
- 范围：`requirement_id`、`workflow_stage_id`、`review_episode_id`、`page_image_sha256`、双读 `page_review_id`
- 结果：`candidate_auto_accept=False`、`clinical_findings_allowed=False`、pending code `page_observation_unverified`
- 覆盖：已发布事实的 `fact_type`、`supported_requirement_ids`、`locator_ids`（正向判断应走 **fact_type + 对象 + 摘录 + 显式条款绑定**，不是文件类别）

**真正必须新增的（尽量少）**

1. 辅助复核目标的类型判别（事实 vs 手写），见第 1 点。  
2. “未核实读取”在期望层的显式表示：优先复用未解决项 code，**停止伪造** `professional_judgment`；仅当 Codex 坚持期望行必须有 `gap_type` 时，才考虑把已有 `GapType.SOURCE_CONFLICT` 纳入信号集，或加一个窄的 `observation_unverified`。**不要**新造第五种期望状态。  
3. 正向覆盖：让 `fact_type == "investigator_assessment"`（或已接受手写投影成该类事实）且 `target_text` 绑定该 `requirement_id` 时可以 `OBSERVED`。这是接线，不是新临床字段。

**不要新增：** CS/NCS 枚举结论、项目特异正则、同页“有批注⇒所有异常已判断”、把 Codex 手读答案写入产品、用 `document_type=investigator_assessment` 当覆盖。

**反例**

- 同一张检验单：WBC 旁 “NCS”，RBC 无字。不得让 WBC 手写覆盖红细胞条款。
- 箭头↑不是判断；即便双读一致也不构成 `investigator_assessment`。
- 页顶“异常均无临床意义”而无对象：可作未核实/描述不足，不能自动满足所有 `requires_professional_judgment` 原子。
- 文件名为“研究者评估表”但页上无针对该节点该项目的摘录：`_observations` 排除文件类别是对的；缺的是事实/手写正向路径，不是把文件类别加回去。

**过度设计：** 手写→条款的通用语义匹配器；为 CS/NCS 单独事实类型再加一层“临床意义布尔值”。

---

#### 4. 格式保真模块：逐条独立合法 facts/handwriting、全结构+数量、非法条目未验证、未启用。——**基本属实。** 存在错误通过/错误保护窗口。接线不得热改共享 harness。

**证据**

- `REPAIR_PRESERVATION_VERSION = "page-repair-preservation/v1"`；`check_repair_preservation` 未接入 `read_page`。线上仍是：格式错 → 同提示同图一次纠正 → 只验收新答。
- 签名 = 除 `observation_id` 外的 `model_dump`；`Counter` 保数量；非法条目 `uncheckable`；顶层 JSON 都抽不出则 `original_parseable=False` 且全 0。
- 测试覆盖：改值/字段/摘录/原文/对象、同键不同摘录与重复条数、手写消失、非法条目、外层坏 JSON、新增条目不算本检查通过项。未测：`clause_signals`、仅新增不删除、整场 `facts` 非 list、`has_eligibility_value` 矛盾被单条包装绕过。

**错误保护（把未保住的当成保住）**

- `protected_observations` = 旧答里独立合法条数，**不是**新答里仍在的条数。消失记在 `missing_or_changed`。若接线只判断 `protected > 0` 会假通过。`test_pending_handwritten_judgment_cannot_disappear...` 已要求 `missing==1`。
- 单条包装时强制 `has_eligibility_value=True`，会把“无价值页却带 facts”拆成可保护观察（测试有意如此）。接线若把 `original_parseable=True` 当成整份旧答合法，会假保护。
- `facts`/`handwriting` 不是 list 时 `uncheckable += 1`，`originals` 为空，缺失为 0：整场观察被丢掉也不报 `missing`。

**错误通过（内容已变仍像格式-only）**

- **新增**观察：`missing==0`（测试写明本检查不验收新增）。纠正若删了非法条、加了另一条检验值，本函数通过。
- **不比** `clause_signals`。针对性复核要求该数组为空；主读纠正可改条款方向。注释自称范围外，接线若当唯一门闩会漏。
- 非法条消失只进 `uncheckable`，不进 `missing`：多一个未建模字段的真实手写可被纠正删掉且不失败。
- `extract_json_object` 成功即 `original_parseable=True`，即使周围还有散文。

**建议（接线失败语义 + 版本边界）**

- 保持离线，直到单独版本闸。**不要**改 `evaluate_page_review_response`、一次纠正预算、或横评 harness。
- 若接入：独立于 `PAGE_REVIEW_FORMAT_REPAIR_VERSION`。`missing_or_changed > 0` → 纠正失败，保留原格式失败，不接受新答。`uncheckable > 0` → 不得称已保全；失败闭合或显式未验证。`original_parseable=False` → 本检查不适用，沿用现有一次纠正，不得写 `protected`。新增条数必须另计，本函数不管。
- 不做医学真伪判断；通过 ≠ 可采信。
- 横评任务冻结旧行为：任何接入走新 prompt/job 版本，旧作业不重放新闸。

**反例**

- 旧答 1 条合法 ALT + 1 条多字段手写；纠正只留 ALT 并加一句“均 NCS”：`protected=1, uncheckable=1, missing=0` → 假通过。
- 旧答 JSON 可抽但 `has_eligibility_value=false` 且带 facts；纠正改成 true 并改数值：合法旧条 `missing=1` 应失败；若只看 `original_parseable` 会假过。

---

### 按严重度

| 严重度 | 位置 | 机制 | 已证实 / 设计建议 | 最小建议 |
|---|---|---|---|---|
| **P0** | `fact_normalization_executor._expectation_gap_signals` | 无已核实判断 ⇒ 伪造 `professional_judgment`；pending 手写因无 `gap_type` 被跳过 | **已证实** | 有 `page_observation_unverified`、读失败、单源或范围不一致时禁止该填充；无资格信号则让投影闭包失败，不伪造缺失 |
| **P0** | `_observations` + `_coverage_verdict` + 自动 judgment_gap | 书面判断完好覆盖不可达，弱检验事实被改写成确无判断 | **已证实** | 正向覆盖用 `fact_type`+`target_text`+摘录+`supported_requirement_ids`；不要把文件类别加回 `investigator_assessment` |
| **P1** | `explicit_conflict_fields` / `compare_targeted_reads` / enqueue | 手写与对象不一致进不了两轮；硬塞进现有 targets 会次轮仍盲读 | **已证实**（限制）；扩展为**建议** | 并列手写目标+全结构比较；版本 bump；一致仍不采信 |
| **P1** | `pending_retention_items` ↔ 期望 | 未核实与确无记录在期望层坍缩 | **已证实** | 三态合同；未绑 requirement 的手写保持未核实 |
| **P2** | `page_review_repair_preservation` | 未接线；`protected` 名不副实；不拦新增/条款信号/整场非 list | **已证实**（窗口）；接线为**建议** | 独立版本闸；以 `missing_or_changed` 失败闭合；不热改 harness |
| **P2** | `ReconciliationConflict.field_name="handwriting"` | 一页所有手写冲突共用一名 | **已证实** | 目标身份用 kind+对象+摘录，不要复用该字段名 |
| **P3** | 旧 `pipeline/reviewer.py` CS/NCS 正则 | 项目外散文启发式 | **未核读全文** | 新链禁止复用；列入扩读 |

---

### 对拟案的主要异议

1. **不要把 §16 缺失报告焊进辅助事实复核。** 设计已拆开。手写两轮只解决“页上已有字但没读清”；确无判断是另一条，且前提是范围已核实。混用会把未读完写成“未见判断”。
2. **“当前无已核实判断” ≠ “完整范围内未见”。** 前者是未核实，后者才是 §16 发现。现码把前者当后者。
3. **复用 `compare_targeted_reads` 是错的最小改动。** 最小是并列函数 + 同一 Job 外壳。
4. **不要为未绑条款的手写补 `affected_requirement_ids`。** 那会把同页批注传到所有书面判断要求。
5. **正向覆盖断了。** 只停自动缺口而不修 `fact_type`/对象绑定，书面判断将永久 `ABSENT` 或投影失败。
6. **保真模块的 `protected` 不能当通过条件。**

---

### 给 Codex 的决策点

1. 未核实在期望层：A) 有 pending/读失败则不投影该模板并 `INPUT_INCOMPLETE`（流程仍继续）；B) 允许 `CoverageGapSignal` 使用已有 `SOURCE_CONFLICT`/`OCR_OR_PARSE_RISK` 但文案不得称“未见判断”；C) 新增窄 `GapType`。**建议先 A+停伪造，C 仅在期望行必须有 gap 时再加。**
2. 手写两轮入队：仅“同类 + 非空同一 `target_text` + 原文不一致”，还是所有 pending 手写？**建议前者。**
3. 已接受手写如何成为覆盖：经 Normalizer 变成 `fact_type=investigator_assessment` 且显式绑 `requirement_id`，还是期望层直接读 `accepted_handwriting`？**建议前者，避免第二条覆盖管线。**
4. 保真检查：本阶段保持离线，还是只在新版本纠正闸失败闭合？**建议离线**，直到横评任务版本边界写清。

---

### 向 Codex 的有界问题（卡住处）

1. `EvidenceExpectationTemplate.required_source_types=["investigator_assessment"]` 与规则原子 `requires_professional_judgment` 是否一一对应？若模板过宽，停用自动填充后可能大面积 `INPUT_INCOMPLETE`。这决定是先修模板投影还是先修缺口填充。  
2. 产品是否允许期望行在“未核实”时没有 `professional_judgment`、也没有 `ABSENT`？§16 允许报告未决且不 `claims_complete`；现投影器对到期无信号会抛错。需要 Codex 在“闭包失败”与“新增未核实缺口”里定一条。  
3. 辅助手写复核是否允许进入当前 `targeted-page-review-job/v1` 幂等键（同一 `reconciliation_id`）？若允许，旧数值复核任务会挡住新手写范围。应否新 job 版本/新幂等维度？

**未决时的安全临时路径：** 不实施自动采信；不把手写塞进数值 `targets`；不把 pending 手写绑到全部书面判断模板；停掉无覆盖前置的 `professional_judgment` 填充；保真模块保持离线。流程继续出报告，未决项保持无法判定，不冒称确无研究者书面判断。

---

### 类别对照

- **证据：** 上文函数行为、合同字段、测试钉、设计 §11/§16/辅助复核段。  
- **推断：** 自动填充在真实“待核对手写 + 到期书面判断模板”下会误标；书面判断 `OBSERVED` 在现行 `_observations` 路径上不可达。未用病例运行证明发生率。  
- **建议：** 三态证据合同；手写并列复核；正向覆盖走 fact_type+对象+摘录+条款绑定；保真独立版本闸。  
- **不确定：** 模板如何从 `requires_professional_judgment` 生成；UI 是否已把该缺口显示为确无记录；旧 reviewer 正则是否仍在任何活动路径。  

本角色一次完整顾问通过结束。不声称 Codex 终裁。
