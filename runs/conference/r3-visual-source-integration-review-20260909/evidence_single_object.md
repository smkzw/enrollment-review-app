# 会议输出: r3-visual-source-integration-review-20260909 - evidence_single_object

## 输出

### 结论（TLDR）

新模块 `app/domain/page_review_evidence_sources.py` 的合同本身是健全的：内容寻址、双主读逐字绑定、摘录哈希真实值校验、OCR 文本哈希与页图哈希严格分立、只物化已采信事实/手写并排除条款信号，40 个测试全部通过（本机实跑，0.22s）。**但它完全没有接线**——除自身测试外无任何消费方，无存储、无 API、无门禁改动。

最重要的发现是一个**接线级死锁（缺陷 D1）**：页审任务在活动修订 R1 下运行，视觉定位在页审之后才产生，而 R1 的定位闭包不可变；发布门禁要求定位属于活动修订闭包；规范化覆盖选择又要求 coverage 绑定当前活动修订。因此视觉事实要正式发布，必须构建并激活包含视觉定位的新完整修订 R2，而 R1 绑定的 coverage 在 R2 下直接 `PageCoverageNotReady`。**若无确定性重推导步骤，正式链路根本无法闭合**——这正是“最小完整接线边界”必须包含的第一块，而不是只放宽第一个校验器。

---

### 一、证据与现状（观察，附 file:line）

**阻塞链（为什么必须接线）**——当前一条图像事实（如手写批注、OCR 漏识区域）即使双主读一致，也无法走完链路：

1. `app/projections/page_review_sources.py:52-70` `validate_accepted_candidate_sources`：事实候选的已采信观察摘录，必须（NFKC+空白规范化后）是某个 OCR 定位 `localized_text` 的**子串**。手写摘录通常不在 OCR 有效文本内 → 解码期直接抛错（`app/agents/evidence_normalizer.py:1547`），回放期同样抛错（`app/services/fact_normalization_replay_sources.py:24`）。
2. `app/domain/gates/fact_evidence_closure.py:377-380`：候选 locator 必须属于当前完整修订的 `locator_ids`（即 `EvidenceLocatorArtifact` 闭包）。
3. `app/storage/fact_authority.py:205-267` `FactAuthorityValidator._validate_locator`：发布前逐定位核对快照成员资格与 `ProcessingRevisionLocatorRecord` 修订成员资格。
4. `app/services/evidence_locator_service.py:114-125`：定位创建只支持 `native_text / raw_ocr / effective_text` 三个来源层，没有视觉层。

**修订/覆盖绑定现状**：

- 页审执行器每步校验 authority 即活动修订（`app/services/page_review_job_executor.py:57-58`），coverage 的 `evidence_processing_revision_id` 在 coverage 步冻结为该修订（同文件 :81）。
- 正式规范化覆盖选择 `app/services/page_review_coverage_selection.py:38-44` 按 `evidence_processing_revision_id == authority.complete_processing_revision_id` 过滤，且 ：96-108 会用当前修订的 association sources **确定性重跑 `reconcile_page_reviews`** 校验既有对账仍成立——这个已存在的重放逻辑是 D1 解法的现成地基。
- 完整修订的 `locator_ids` 在构建时冻结（`app/services/evidence_revision_builder.py:212-244`），不可追加。

**既有视觉旁路（对照，非本次目标）**：`collect_visual_observation_attachments`（`app/services/fact_normalization_source_adapter.py:636-724`）已把选择性视觉观察作为"引用材料"接入，但提示词明确禁止其作为唯一断言依据（`app/agents/evidence_normalizer.py:403-407`）——与"OCR 不做图像事实权威"的边界一致，且不应被本次接线弱化。

### 二、实质缺陷（按影响排序）

**D1（高）接线死锁 / R1→R2 循环失效。** 推理链：页审需活动修订 R1（executor :57-58）→ 视觉定位产生于页审后，R1 闭包不可变 → 发布需活动修订闭包成员资格（fact_evidence_closure :377-380、fact_authority :247-267）→ 必须建 R2 并激活 → coverage 选择要求绑定 R2（coverage_selection :38-44）→ R1-coverage 失效 → `PageCoverageNotReady`，要么全量模型重读（昂贵、且“不改写既有结果”原则下历史堆积），要么放松覆盖绑定校验（**这正是来源验证旁路**，应拒绝）。**建议解法**：确定性重推导——模型输出（`PageReviewRecord`）不可变复用，零模型调用，仅从持久 reviews + R2 的 association sources 重跑 `reconcile_page_reviews`、生成 R2 绑定的 coverage 与视觉来源集合（内容寻址 ID 因绑定字段变化而天然区分，追加写不覆写 R1 记录）。`select_normalizer_coverage` 已内嵌同样的重放校验，证明该重推导是确定性的。Tradeoff 见第五节。

**D2（中）`page_text_sha256` 语义未钉死。** `page_review_evidence_sources.py:336-338,560-561` 只校验“不等于页图哈希”，未声明它是 raw OCR 哈希还是含校对的有效文本投影哈希。两个合法调用方传不同定义的哈希 → 同一页产生分歧的 `source_set_id`，陈旧检测失效。**建议**：钉死为与 `PageAssociationSource.text_sha256` 同一投影（`app/services/page_association_sources.py:18-21` 的 effective-text 投影哈希），并在合同 docstring 冻结该定义；接线时由调用方从修订闭包重算并比对。

**D3（中，接线级）`_compact_locator_inputs` 会吞掉视觉定位。** `app/services/fact_normalization_source_adapter.py:74-106` 在同 `(source_layer, source_text_sha256)` 组内删除“被更完整定位包含”的子串定位。视觉层按页图哈希分组后，同页两条已采信观察的摘录互为子串时（如“白细胞 4.2”⊂“白细胞 4.2 x10^9/L”），较短者的**绑定定位**会被移出可用集合 → 模型无法引用 → 该事实被迫降级为未解决项。这不是优化而是正确性回归。**建议**：视觉层跳过压缩，或分组键加入 `target_id`。

**D4（低）手写代表读道未标记。** 物化器要求代表逐字来自某条主读（:657），但 `VisualHandwritingSource` 不记录是哪条；两读道摘录可合法不同（规范化一致即采信）。下游摘录核对必须接受“任一读道摘录逐字相等”，需在接线规范显式写明，否则实现者可能只对代表读道核对而误拒。

**D5（低）合同级读道 `page_review_id` 去重缺失。** `_validate_reading_pair`（:147-152）只查 lane 与模型身份。伪造合同可用同一 `page_review_id` 配两条 lane 通过校验。物化器路径不受影响（materializer 从双记录构造），但既然合同声称防伪造，应补一行校验。

**D6（记录性）未认证 bbox 参与内容身份。** 测试 `test_raw_observation_keeps_model_bbox_but_locator_is_coordinate_free` 证实 bbox 变化改变 `fact_source_id`。回放必须逐字复用持久观察（当前 `model_dump` 往返满足）。风险已可控，但需在接线文档写死“重推导不得规范化/丢弃 bbox"。

### 三、必须守住的旁路防线（接线时逐条落实）

1. 模型只能引用**绑定到本次 coverage 已采信观察**的视觉定位：`validate_accepted_candidate_sources` 的类型化分支必须核对 locator 的 `target_id`（= fact/handwriting source id）属于已采信集合，且摘录**逐字相等**（替代 OCR 子串包含）——不能只做 locator 存在性检查，否则模型可引用同页冲突/单源观察的定位。
2. R1 绑定的视觉集合不得在 R2 下被引用：修订成员表（`ProcessingRevisionLocatorRecord`）+ 集合的 `evidence_processing_revision_id` 相等校验，双保险。
3. 虚构 locator id：既有成员门禁已覆盖，无需新代码。
4. D3 的压缩吞并。

### 四、最小完整接线边界（文件级顺序，建议）

载体裁决：**Option A——新增 `LocatorSourceLayer.PAGE_REVIEW_VISUAL`，把每条视觉来源桥接为一个 `EvidenceLocatorArtifact`**（`precision=PAGE_EXCERPT`、`authenticity=DEGRADED`+降级原因、`anchor_hash` 含 `target_id`=来源 id、`source_text_sha256`=页图哈希即图像层锚、不设 `ocr_page_id`）。这样候选的 `locator_ids`、修订闭包、发布校验、来源强度派生（按 `source_document_version_id`→元数据）**全部复用既有机器**。Option B（候选加并行 `visual_source_ids` 字段）要在normalizer输入、双门禁、发布校验、Profile API 各造一套平行闭包，面更大、分歧风险更高，不推荐。

顺序：

1. `app/domain/contracts/enums.py`：新增 `LocatorSourceLayer.PAGE_REVIEW_VISUAL`（附加式）。
2. `app/domain/page_review_evidence_sources.py`：钉死 `page_text_sha256` 语义（D2）；补 D5。
3. 存储：`app/storage/page_review_models.py` + 内容寻址幂等仓储（按 `source_set_id` upsert）+ migration。
4. 定位创建：`evidence_locator_service.py` 或专用确定性创建器（不依赖 OCR sidecar 映射路径）。
5. **重推导步骤**（D1 解法）：修订构建/激活编排中，从持久 reviews + 新修订 association sources 确定性重推导 reconciliation → coverage(R2) → 视觉来源集合 → 视觉定位，并入 `evidence_revision_builder.gather_closure`。任务编排顺序固定为：页审 → R2 构建 → 激活 → 规范化。
6. `app/projections/page_review_sources.py`：类型化分支（防线 1）。
7. `app/services/fact_normalization_source_adapter.py`：`_compact_locator_inputs` 视觉层豁免（D3）。
8. `app/agents/evidence_normalizer.py`：提示词为视觉层加一句锚定规则（“有效文本原句”对视觉定位为例外，改为“视觉定位的冻结摘录”）。
9. `fact_evidence_closure.py` / `fact_authority.py` / `fact_publication_service.py` / `fact_normalization_replay_sources.py`：结构性无改动，逐项验证 + 阻断级 OCR 政策测试（见 Q2）。
10. Profile/evidence 读 API：视觉定位按 `page_excerpt` 无坐标精度展示（现有精度渲染应已支持，需实测）。

### 五、R1→R2 Tradeoff 明确评估

- **重推导（推荐）**：每修订多存 coverage/reconciliation/集合行；零模型调用；所有门禁单跳；确定性可回放；复用 `select_normalizer_coverage` 既有重放逻辑，代码增量最小。
- **继承边**（R2 文本未变的页直接引用 R1 集合）：省行数，但每个门禁都要走继承边、集合 ID 内嵌 R1 与所属 R2 矛盾需要在验证器里特判——正是旁路温床。拒绝。

### 六、验收测试清单（合成 only）

1. 手写事实：图像可见、OCR 有效文本无该摘录、双主读一致 → 候选通过解码、双门禁、发布（头号场景）。
2. 伪造视觉 locator id ∉ 修订闭包 → REJECTED。
3. R1 绑定集合在 R2 权威下引用 → REJECTED。
4. 候选引用同页**冲突/单源**观察的视觉定位 → REJECTED（防线 1）。
5. D3 回归：同页两条已采信观察摘录互为子串 → 两条定位都在可用集合、两条候选均可发布。
6. 页文本在 R2 变化 → 该页视觉集合重推导为新 ID，旧 ID 不再被引用。
7. 回放确定性：从持久输入重物化 → 逐字节相同 `source_set_id`（含 bbox，D6）。
8. 既有文本路径回归：无 page_review 的 OCR 子串候选行为完全不变。
9. 纯视觉候选 + 页上未解除阻断级 OCR 风险 → 按 Q2 裁决的行为钉死。
10. 空 sources 页（纯条款信号页）物化空集合并持久化（覆盖闭合证明）。

### 七、保留的解释性不确定性与有界问题（请 Codex 裁决）

- **Q1（D2）**：`page_text_sha256` 钉死为 effective-text 投影哈希（与 association source 同源）是否接受？安全临时路径：接线前该字段一律传 `None`。
- **Q2（政策）**：纯视觉候选（定位不绑 `ocr_page_id`）遇同页未解除 BLOCKING OCR 风险，建议**不阻断**（图像+双读是权威，OCR 只是侧车；当前代码 `ocr_page_id is None → continue` 恰好如此），但需显式测试钉住，避免未来被"保守化"改掉。
- **Q3（触发点）**：物化放在修订构建期（建议，绑定天然一致）还是页审执行器 apply 步（绑 R1，仍需重推导）？
- **Q4（载体）**：Option A（新来源层+定位桥接，建议）vs Option B（并行字段）。

不确定性声明：本角色未做浏览器/UI 验收（Profile 对视觉定位的实际渲染未验证）；只实跑了 50 个相关测试（新模块 40 + 候选来源/适配器 10，全绿），未跑全量套件；R3 任务编排层的具体接序基于 executor 与 coverage_selection 代码推断，未逐行审 job service 全文。以上均不构成临床或最终验收结论。
