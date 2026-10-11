# Conference Output: r3-normalizer-prompt-cost-review-20260909 - evidence_single_object

## Output

独立审阅完成。我在只读边界内重建了失败作业 `e5c3b71c53894aa7b37a85a0570644f8` 的全部 14 个冻结输入（复用 `scripts/audit_normalizer_input.py` 的 `_build_input`→`_model_input_payload` 路径，直接查询 runtime-03 副本库，mode=ro，无模型调用），并对每个 prompt 分量做了逐字段归因和反事实压缩仿真。以下按证据/推断/建议/不确定性分层给出结论、最小降本方案、实现边界、验收测试与对 Codex 的决策点。

### 1. 结论概览

**最小降本方案 = 纯模型侧投影压缩（不动的冻结输入、不改输出合同、不改存储、不影响回放），核心是把待核对观察从"逐条全量记录"降为"分组语义摘要"，同时移除四类已被证实模型不可用的审计元数据。** 对四个已成功调用实测 prompt token 下降 24%–53%（估算），待核对观察占比最高的调用（2 条已核实观察、144 条待核对）从 56,606 token 降至估算 ~26,000。全程不降低 effort、不裁剪 max_tokens、不替换模型，原始证据（`effective_text`、`localized_text`、摘录）、缺口绑定语义、冲突值、阶段判断全部保留。完整的待核对记录应通过新的确定性报告投影进入最终报告，而不是继续依赖模型转述——这同时是本审阅发现的最高影响缺陷的修复。

### 2. 已核实事实（全部来自本次只读实测，可复现）

**2.1 分量占比（14 个调用合计约 1.02M 输入字符）**
- `page_review` 约 571k（56%）：其中待核对观察 367k、冲突记录 152k、已采信观察仅 52k。
- `related_requirements` 每调用恒定 16,343 字符，14 次重复 ≈ 229k（22%）。
- `locators` 合计 145k（14%）：`localized_text` 仅 32k，其余 113k 为 ID/枚举/溯源元数据。
- 固定头（模板+系统合同+内嵌 Schema）每调用 15,661 字符（Schema 8,675 + 系统合同 6,955），且 zhipu-coding-plan 路由用 `json_object`（`deepseek_evidence_normalizer_transport.py:566`），`enforces_output_json_schema=False`，Schema 全量进提示。

**2.2 待核对观察逐字段归因（最差调用 call_c49df4，144 条，page_review 107k 字符）**
| 字段 | 字符 | 模型可用性 |
|---|---|---|
| page_review_id / observation_id | 14,520 | 不可用：输出合同无任何观察引用字段（`evidence_normalizer.py:399-449` 仅 code/message/pages/locator_ids/requirement_ids/gap_type/reason） |
| review_status + review_message | 9,648 | 仅 4–5 个不同值，可整组提升 |
| text_anchor（offsets/source_layer） | 5,155 | 不可用：无输出字段承载偏移 |
| lane/kind 重复标签 | ~4,600 | 2 个值，可提升 |
| 真实语义（field/value/raw_text/excerpt/context 四项） | ~46,000 | 必须保留（摘要化） |

**2.3 冲突记录（556 条，152k 字符）**：`normalization_keys` 84k + `page_review_ids` 44k 为审计身份；`reason` 是通用模板（如"原件异常标记的判读不一致，需核对原件"），**具体冲突读值只存在于 normalization_keys 内**（格式 `field|value|unit[|context:hash]`，`page_normalization.py:141-143`）。安全压缩（保留 field、reason、去 context 哈希后的去重键）实测 152,326→44,997 字符，**省 70% 且不丢任何冲突值**。

**2.4 需求块归因（58 条，15,618 字符）**：`description` 仅 1,481 字符（中位长 22）；大头是 `requirement_id` 3,074（前缀 `requirement:component:` 22 字符×58 可无损剥离）、两个布尔字段名 5,500、`required_source_types` 空列表 2,814。**降本空间在结构开销而非描述文本。**

**2.5 视觉定位溯源**：每个视觉 locator 携带 5 个 ID+sha ≈ 250 字符，job 合计 47k（locator 分量的 33%）；候选校验用的是冻结输入（`page_review_sources.py:50-82`），提示中的这些哈希对模型完全惰性。

**2.6 运行时事实核对**：5 个零已采信观察的调用已经走了 `pending_only_output` 快路径（~6.5s，无模型调用，`fact_normalization_executor.py:1124-1131`）；四个实测成功的模型调用 prompt token/耗时为 38,441/621s、56,606/429s、27,570/519s、46,780/461s。**耗时与 prompt token 不相关**（推理深度主导）；chars/token 校准值一致地 ≈2.8。

**2.7 反事实仿真**（分组摘要待核对 + 安全压缩冲突，保留 field/value/raw_text/excerpt/polarity/time/location）：
- call_c49df4（2 采信/144 待核对）：输入 134,282→58,047（-57%），token 56,606→估算 26,324。
- call_c6270fe（8/91）：-48%，token -20,823；call_5ed18db（30/37）：-23%，token -9,348；call_9f0c98（12/31）：-27%，token -6,374。
- 待核对主导的调用普遍 -48%~-57% 输入字符。

### 3. 最高影响缺陷与主动异议

**D1（缺陷，必须修）：完整的待核对观察今天只能通过模型转述进入未解决项，没有任何确定性旁路。** `pending_page_observations` 的唯一消费者是 `_model_input_payload`（rg 全仓核实）。若模型漏报，这些待核对内容在 Profile/报告中消失。降本方案把模型侧降为摘要后，此缺陷会被放大——因此**必须同时**新增确定性待核对报告投影（见 §4-L1b）。这与任务范围里"where complete pending records should enter final report"的问句直接对应：答案是"从存储的对账记录确定性投影，而非模型转述"。

**D2（缺陷）：R3 输入无 prompt 上限。** `_MAX_PROMPT_CHARS=100_000` 仅对 `page_review is None` 的旧输入生效（`evidence_normalizer.py:897`）；R3 输入实测达 157k 字符提示无任何预算门。建议加 R3 输入预算断言（诊断性质，超限告警而非静默）。

**D3（异议，纠正任务前提）：** "已核实事实少但待核对观察多"的输入中，**零已采信的一半已经免费**（快路径存在且已生效）；真正的成本痛点是 2–30 条已采信 + 37–144 条待核对的混合调用（9 个模型调用）。方案应对准混合调用，不要在零采信调用上重复投入。

**D4（异议，纠正降本直觉）：** 需求块的冗余不在 description 长文，而在结构字段；任何"截断描述"方案既低效又引入语义损失风险。同样，**不建议 locator_id 别名化**：locator_id 是模型输出字段，别名需要双向映射侵入解码路径（`_normalize_locator_aliases` 已经在修一类 ID 漂移，再叠加别名会扩大漂移面），收益（38k）低于待核对/冲突/溯源三项合计（~190k），风险却更高。

**D5（推断，需验收确认）：** 耗时不随 prompt 线性下降（2.8 校准下 621s/38k vs 429s/56k）。token/费用节省是可靠的；墙钟时间与 `incomplete_chunked_read`（第 10 组 480s 断流）风险的改善是合理假设但未测。

### 4. 最小降本方案（分层，全部可逆）

**L0 保持现状**：`pending_only_output` 零采信快路径；effort/max_tokens/模型身份不动。

**L1 模型输入投影压缩（本轮主体，改动集中在 2.5 个文件）**

a. 新模块 `app/projections/page_review_pending_digest.py`：`pending_observation_digest(pending_page_observations(...)) -> {"groups":[{"lane","kind","status","note","same_passage","items":[{"f","v","t","x","p","time","loc"}]}]}`。逐条保留字段名、原值、原文转写、定位摘录、极性、关联时间/位置；提升可重复的 lane/kind/status/message；丢弃模型不可用的 observation_id/page_review_id/text_anchor 偏移；`same_source_passage` 保留为组级标志（防止模型把"同原文范围"误读为"事实一致"）。待核对条目**仍留在模型上下文中**——它们承担两个语义职责：把明显对应到期要求的待核对内容绑入 `affected_requirement_ids`（`_expectation_gap_signals` 的兜底只会给出泛化"未见记录"，读值分歧级别的缺口只有模型能绑定），以及写出指向具体对象的核对理由。

b. 新模块 `app/projections/pending_observations_report.py`：从存储的 `PageReviewRecord`+`PageReconciliation` 确定性投影完整待核对记录（含原文摘录、双读状态、文本锚点）到 Profile/问题清单数据源。这是 D1 的修复，也是"摘要进模型、全量进报告"的安全底座。

c. `compact_page_review_input` 扩展：冲突压缩（去 `|context:` 哈希尾、去 `page_review_ids`，保留全部去重键值对）；已采信观察去 `normalized_value/normalized_unit/bbox`（模型自行从原文产规范值；此条见决策点 Q1）。

d. `_model_input_payload`：locator 的 `page_review_visual` 溯源对象 → `"visual":true` 标记（提示中只需告知"此定位文字来自绑定摘录、可直接引用"，合同语义已在系统合同中）；`precision`+`page_number` 按页分组提升；需求块剥公共前缀、布尔字段省缺声明化（默认值一行声明，偏离才列出）、空 `required_source_types` 省略。

e. `_SYSTEM_CONTRACT` 增补一句声明摘要形状与"完整待核对记录由系统从冻结对账确定性保留并进入报告"；`_PROMPT_LAYOUT_VERSION` v22→v23，重新冻结提示哈希。**旧运行回放不受影响**：检查点复用路径（executor 1029-1079）只对冻结输入与持久候选复验，从不重建模型提示。

**不建议本轮做**：zhipu `response_format=json_schema` 实验（传输已支持该机制，`deepseek_evidence_normalizer_transport.py:537-544`，若端点支持可再省每调用 8,675 字符+每次修复轮重复；但 MTPLX 上受限解码关闭 MTP 的性能回退有案可查，需一次真端点实验+回退，交 Codex 决策）；locator_id 别名（D4）；描述截断（D4）。

**L2（后续轮）**：端点 Schema 实验与 L1 效果实测后再议。

### 5. 验收测试（具体判据）

1. **投影确定性/无损单测**：同一冻结输入两次投影字节一致；摘要 `items` 条数 == `pending_page_observations` 条数，且每条 `(field_name, raw_value, excerpt)` 三元组逐字保留；`effective_text`/`localized_text`/需求 description 文本字节不变；冲突压缩后每个 `normalization_keys` 去重集合在投影中仍可区分（值对无损）。
2. **冻结不变量**：重跑 `scripts/audit_normalizer_input.py`（新投影）对同一副本库，`input_scope_sha256` 不变、数据库哈希不变（复刻 runner.py 的只读隔离约定）。
3. **字符预算门（新断言）**：最差调用输入 ≤65k 字符；`pending+conflict` 合计 ≤35k；R3 提示超 100k 字符时显式告警（D2）。
4. **语义无损验收（决定性）**：在**新建隔离 runtime**（design §14，不改写历史）重放四个已成功调用的冻结输入：已发布事实的 `(asserted_object, polarity, value, unit, locator_ids, supported_requirement_ids)` 关键字段集合不低于基线；页闭合门禁全过；finalize 后 gap 信号数 ≥ 基线；确定性待核对报告投影条数 == 存储待核对条数（D1 闭合）。
5. **性能记录（§13 口径）**：每调用 prompt/completion/reasoning token、P50/P95 墙钟、修复轮数；接受线：待核对主导调用 prompt token ≤ 基线×0.75，修复轮 ≤2 不变。
6. **回归**：`tests/v2/services/test_page_review_model_input.py`、`test_page_review_pending.py`、`test_evidence_normalizer_adapter.py` 全量；V2 全量回归一次。

### 6. 决策点与有界问题（请 Codex 裁决）

- **Q1** 已采信观察的 `normalized_value/normalized_unit` 是否保留？（我倾向移除——模型应从原文自行规范；但它们可能引导模型输出确定性值格式、减少修复轮。影响小，需一次实测。）
- **Q2** b 项确定性待核对报告投影是否纳入本轮切片？（我主张纳入：它是摘要化模型输入的安全性前提，且独立可测。）
- **Q3** 是否授权对 zhipu-coding-plan 端点做一次 `json_schema` response_format 探测调用？（超出本角色只读边界，需 Codex 授权与凭据。）
- **Q4** 提示布局 v23 冻结时间点：随 L1 同步，还是等 Q1/Q3 结论一并冻结（避免两次版本翻转）？我建议后者。

### 7. 不确定性与恢复点

- token 节省按 2.8 chars/token 校准；压缩后中文占比升高，实际节省可能低 10–20%（已在 §2.7 标注为估算）。completion/reasoning 收缩（27–35k→更低）为假设，待验收 4 实测。
- 第 10 组断流调用在压缩输入下能否成功未验证；验收 4 的隔离重放即为恢复点。
- 本审阅无阻塞项；所有测量脚本以 stdin heredoc 运行，未写入任何文件，副本库只读（`mode=ro`）。最终临床/产品验收权归 Codex。
