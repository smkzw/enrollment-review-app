证据链已闭合。现在整理并返回完整会议报告。

# Conference Participant Output: r3-observation-alignment-review-20260906 - general_single_object

## Boundary Check

本参与者在 `off_peak` 期以 `zcode/zcode/GLM-5.3-Flash`（thought=max）执行。全程只读：仅读取指定源码、直接引用的域合同、页判读 harness（`app/llm/page_review_harness.py`，作为观察生成上游的必要补充证据）与聚焦 rg 检索的测试；未读写 runner 报告路径，未读 `.env`、凭据、临床原始文件、artifacts；未调用产品模型、未联网、未执行测试（仅两次本地纯计算度量 prompt 常量长度）。未看其他参与者输出。以下不构成临床、法规或最终验收结论。

## Independent Work Product

先纠正一个症状定性：**"两组归一化只返回 unresolved-only"是合同正确行为，不是 Normalizer 故障**。系统提示明确规定候选只能来自 `accepted_observations`，pending 仅供说明（`app/agents/evidence_normalizer.py` 约556-560行；`_model_input_payload`，同文件723-837行）。该页对账产生 **0 个 accepted key**，模型正确拒绝虚构候选，输出 unresolved-only 是唯一合规结果。缺陷在上游接受逻辑与投影膨胀，分三问作答。

**一、展示/上下文/哈希身份是否过度约束一致 —— 是，且存在同一库内两种"同一观察"定义的自相矛盾**

1. 采信主路径用完整 `normalization_key` 精确相等（`app/domain/page_reconciliation.py:67-85`）。该键含 `observation_context_key(context)`（`app/domain/page_normalization.py:101-123`），而 context 哈希**包含 `location_text`**（合同验证器用全量 `context.model_dump()` 重算，`app/domain/contracts/page_review.py:69-90`）。`location_text` 是"表格行列标题或位置原文"的展示性抄录（harness 指令，`app/llm/page_review_harness.py:361-366`），两个不同模型（GLM low vs MiniMax high）对同一行头抄录差一个字符即哈希不同 → 永不采信。而 `source_aligned_fact_keys` 计算"同源对齐键"时**显式排除 `location_text`**（`app/domain/page_source_association.py:60`）——设计者已知它是展示字段，但主对账路径没用这个定义。测试 `tests/v2/domain/test_page_source_association.py:31-34` 更直接锁定了"位置不同不应阻断一致"的意图。
2. 对齐救援路径自身过严：两道摘录必须经 `_positioned_text` 定位到**完全相同的 (start,end) 窗口**且在页文本中唯一出现（`page_source_association.py:54-58`）；A/B 摘录边界差一个字、或报告重复行导致摘录非唯一，即被跳过。
3. 单道内同身份重复（化验单重复行常见）会把该身份**两道全部**键踢出采信（`page_reconciliation.py:88-93` ambiguous_keys）。"重复行不得静默合并"应指不合并成一条事实，现状是连跨道一致的也全部不接受——过度保守，但这符合"宁缺勿错"方向，属可接受的设计取舍（决策点见后）。
4. 冲突分组键是**未归一化的原始 `field_name`**（`page_reconciliation.py:79,95`），两道对字段名抄录差异会把一组不一致拆成多条冲突；且组内只要有一个键未采信，冲突就**列出全部键，含已采信键**（`page_reconciliation.py:95-98`）。61 条冲突的膨胀机制在此。
5. `context=None` 的事实永久不可采信（`page_reconciliation.py:73-74`），按 harness 指令应为少数，但每条都永久滞留 pending。

**二、冲突投影是否在复制无语义价值的身份字段 —— 是**

`fact_conflicts` 原样 dump（`evidence_normalizer.py:810-813`）：每键形如 `field|value|unit|context:<64位hex>`（`normalization_key` 约百字符），对模型纯噪声；且冲突内容与 pending 项**语义重复**——每道观察的完整内容已在 `pending_observations` 中（含 `review_status` 三分类），冲突块的增量信息只剩"未成双源一致"这一句 reason。实测 61 条约 16k 字符即由此而来。

**三、无损投影能否缩输入 —— 能，且不动任何冻结合同与引用**

以下切除全部满足：存储合同（`PageReviewRecord`/`PageReconciliation`/`input_sha256`）不变；`source_observation_ref` 由 `review_id+kind+index` 派生（`page_review_sources.py:25-27`）不变；仅改 `_model_input_payload` 投影并升 `_PROMPT_LAYOUT_VERSION`（v18→v19，`evidence_normalizer.py:374`）。
- **同一段摘录出现两次**：`text_anchor.excerpt` 恒等于 `observation.region.excerpt`（`page_review_pending.py:36-41` 用同一字符串查找），模型侧删 anchor 内重复，保留 `text_start/end+sha` 供对照 sidecar——纯无损。
- **页级身份逐项重复**：`page_artifact_id`/`source_document_version_id`/`page_number`/`use:"unresolved_only"` 每项重复 93 次（`page_review_pending.py:61-73`），提升到页级一次。
- **模型侧删 `normalization_key` 与 `source_text_sha256`（64 hex）**：模型无任何指令使用它们，审计投影（API 展示用同一函数）保持不变——需将模型投影与展示投影拆为两个函数。
- **accepted 侧双份**：`accepted_facts` 与 `accepted_observations(kind=facts)` 携带同一全量 dump 两次（`evidence_normalizer.py:786-797`），合并为一份。
- **`fact_conflicts`/`signal_conflicts`/`handwriting_conflicts` 模型侧替换为一句"见 pending 项 review_status"**（signal_conflicts 除外，pending 不覆盖条款信号，保留）。
- **`json.dumps` 用紧凑分隔符**（`evidence_normalizer.py:874`，现为默认 `", "/": "`，实测约省 10-17%）。
- `same_source_passage.meaning` 固定句重复（`page_review_pending.py:84-88`）提为一次性说明。
按观察值（93 项≈83k、冲突≈16k）估算，仅上述无损项可减约 45-60% 模型侧输入；不动 `_MAX_PROMPT_CHARS` 对 R3 的豁免（符合约束）。

**修复最小集（除投影外）**：在 `reconcile_page_reviews` 增加第二层确定性采信——对未过精确键的观察，按 `observation_context_key(context 去掉 location_text)`+归一化字段名分组；当且仅当两道各恰有一条、且 `normalized_value,normalized_unit` 相等时采信（`polarity/target_text/time_text` 仍在身份内）。同时把 `_fact_review_status` 与 `ambiguous_keys` 的身份改为同一去 location 定义；`facts_by_field` 改用 `normalize_field_name` 分组且冲突只列未采信键。**拒绝的反例**：不同日期（time_text 异组）、不同对象（target_text 异组）、同值不同极性（polarity 异组）、单位不同（值/单位相等判据失败）、单道重复行（每道恰一条守卫失败）——全部保持 pending，无误合并。不改 `fact_normalization_key` 本身（存储观察的合同验证器依赖它，`page_review.py:69-90`），只改对账期派生身份。

**原始失败证据缺口**：(a) 传输失败时 `raw_output_sha256=对错误字符串求哈希`（`evidence_normalizer.py:1943,2053`），与成功输出哈希同字段存放，事后审计易误读；(b) `_complete` 在 `finish_reason=length` 时**静默加倍 max_tokens 重发一次**（`deepseek_evidence_normalizer_transport.py:242-246`），这次更长调用不记入 attempts——观察到的"长时间运行后超时"很可能发生在这次未记录的重发上；(c) GLM 传输 600s 超时、max_retries=0（同文件192-194行），超时异常只剩通用 httpx 文案，无请求耗时、finish_reason、provider 错误体持久化；(d) `continue_session` 全量重放历史（首 prompt+首输出+修复 prompt+8.6k Schema 再内嵌，Schema 实测 8,583 字符、系统合同 6,700 字符），修复轮输入只增不减，是大页超时的直接放大器。

## Evidence And Assumptions

上述每条均标注了文件与行为来源，属观察+源码推断。**假设一（未证实）**：该真实页 0 采信的主因无法从代码唯一确定——location 漂移、context=None、单道重复行、对齐窗口失配四种机制都存在，主因分布需对存储记录做机械分类才能确认（我不被授权读临床记录）。**假设二**：手写为主的页（约束C）在"无模糊匹配"约束下几乎必然大面积 pending——手写身份键是 `kind|规范文字|context哈希`（`page_normalization.py:126-131`），两道手写转写逐字一致概率低；若这是"留人工核对"的既定设计，则手写页的正确修复只有投影瘦身，不是放宽采信。**假设三**：`association_source` 在 job 路径已冻结接线（`app/services/page_review_job_executor.py:156-159`），排除"未传对齐源"这一解释。`pending_page_observations` 存在 O(n²) 规范化重算（`page_review_pending.py:23-33`），仅 CPU 开销，非超时主因。

## Risks, Gaps, And Verification Needs

1. **最高风险（对本报告自身的反驳）**：若该页主因是 context=None 或手写转写漂移，去 location_text 的第二层采信几乎不改善采信率，只是正确但不解决症状——因此实施前必须先做第 6 节的机械分类，避免修错靶。
2. 去 location 采信会改变既有 reconcile 输出与 `reconciliation_id`（身份含结果字段，`page_reconciliation.py:198-205`），需版本升 `r3-v9→r3-v10`；已冻结真实运行的 reconciliation 引用在重跑时改变。开发阶段可接受与否是 Codex 决策。
3. `tests/v2/domain/test_page_review_pending.py:35-45` 锁定 pending 全量 dump 形状、`:77-97` 锁定不同日期/不同值永不采信——第二层采信实现必须逐条通过这些反例测试；模型投影瘦身需拆分展示/模型双投影并补投影回归测试。
4. `test_page_review_contracts.py` 中可能有对采信行为的更多锁定断言，实施前需全量跑相关测试（本参与者未运行测试，按边界）。
5. 静默 length-retry 若保留，至少要作为独立 attempt 记录（attempt、max_tokens、耗时），否则超时证据链永远缺失。

## Recommended Next Step

给 Codex 的决策点与有界问题：

**Q1（最关键，先于写码）**：是否授权对已存储的该真实页 `page_review_records`/`reconciliation` 做一次**离线机械分类**（用现有归一化函数，把每个未采信事实归入：unassociated / 单道重复 / 值不一致 / context哈希失配-含location / 对齐窗口跳过，不产生任何临床结论）？没有这个分布，任何修复都是赌一把；这是授权读取范围问题，只有你能开。
**Q2**：是否接受 `RECONCILIATION_VERSION` 升版与采信身份变更（去 location_text 第二层）在当前阶段的冻结引用影响？
**Q3**：手写页"大面积 pending 留人工"是否为既定产品语义？若是，手写页只做投影瘦身。
**Q4**：模型侧投影瘦身（保留展示投影不变、`_PROMPT_LAYOUT_VERSION` v18→v19）是否批准？此项无合同风险、收益确定，即使 Q1 未决也可先行。

安全暂定路径：Q4+失败证据修复（length-retry 记录、失败哈希分字段）先行，Q1 分类结果出来后再定 Q2/Q3 的采信变更范围；全过程不加模糊匹配、不加人工字符上限、不换模型、不加语义读段。
