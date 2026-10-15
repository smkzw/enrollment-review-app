补读完成，证据链闭合。以下是第二轮完整输出。

---

# Conference Output: r3-normalizer-latency-source-review-20260909 - evidence_single_object

## Output（第二轮，同会话继续；只读咨询，未写任何文件、未调模型、未触数据库）

### 0. 首轮报告更正（经验事实与推断分层）

**更正 1（我此前的过度陈述）**：首轮称“≥3 个 doomed 引用在预算内**不可能**收敛（数学上不可能）"。这是推断越界。经验事实是：首错即停 + 修复预算 2 **提高失败风险**（每个未报告的同类错误可能消耗一轮），但模型看到一条具体报错后完全可能自行修复未报告的同类引用。运行时证据支持更正：拼接摘录组最终收敛为“1 个保留的登记号 + 17 条显式未解决项（含此前被阻断的 3 条检验发现）"——即修复反馈**可以**收敛，并非不可能。

**更正 2（框架性错误）**：首轮把非逐字摘录框定为“无效拼接摘录”，默认 OCR 文本为真值。这个预设错误。设计书 §3.3（OCR“降级为侧车：只承担存档转录、文本锚定位和廉价预筛，不再是受试者语义判读主路径"）与 §4.2（`page_excerpt`/`page_only` 为合法降级精度；“页面必须显示实际定位精度”）确立：VLM 双读才是语义判读路径。运行时结果（登记号与检验发现全部滞留未解决项、X-ray 印象组接着撞墙、所有者尚未裁定 OCR 与 VLM 谁对）证明把非逐字一律拒为事实来源，会让 OCR 事实上成为语义权威，**永久压制合法视觉发现，尤其手写**。

### 1. 方案 A 的裁定：临时措施，不是终态

拆成两部分裁定：

- **A 的确定性预检/分类引擎：保留并升级**。在冻结输入时对每个已采信观察做与校验器同一口径的逐字预判，仍是消除“三轮 1744s 才发现必然失败”的正确手段；但它只应是**信息引擎**，不应单方面决定处置。
- **A 的处置（非逐字 → 不可引用 → 只能未解决项）：只能作为临时止血，不得为终态**。理由：(i) 设计书明文（上述 §3.3/§4.2）；(ii) 运行时已实证其后果——全部降级、零事实发布、下一组（X-ray 印象）重复同样失败；(iii) 所有者未裁定 OCR/VLM 谁错，系统无权裁决，只能让分歧**可见**。

分类也应从三轮改为四轮：① 同页定位逐字可核对（现状通过）；② 非逐字但为双读采信的视觉观察（手写、影像印象等合法 VLM 发现）；③ 拼接摘录且切段按页序可在页文本中逐字重构（读片确实看到、只是拼接表示）；④ 无重构基础且无双读一致支撑（潜在 OCR/VLM 冲突）。②③ 是桥接对象；④ 是显式冲突/不确定性，绝不静默。

### 2. 现有合同能否承担 R3 桥接——裁定：部分不能，需最小增量

**已具备（evidence）**：
- 候选已持久化 `source_observation_refs`（`app/domain/contracts/facts.py:242`）；page_review 链完整携带 `page_image_sha256`、双模型身份、lane、coverage/reconciliation（`fact_normalization_source_adapter.py:578-630`）——VLM 来源出处**已经**不可变地存在。
- 定位合同已定义 `page_excerpt`/`page_only` 精度 + 可回放 `anchor_hash` + `DEGRADED` 真实性（`evidence_locator.py:188-210, 293-333`）。
- 终局门禁已按精度取文本：`_localized_locator_text` 对 `page_excerpt` 返回定位自带摘录、对 `page_only` 返回 None（`fact_evidence_closure.py:200-231`）；即 `page_excerpt` 定位**已能**作为断言闭合的文本依据，无需 OCR 逐字。

**不能如实表示的三处缺口（需增量）**：
1. `LocatorSourceLayer` 仅 `native_text/raw_ocr/effective_text`（`enums.py:669-679`）。VLM 从页图像读出的摘录没有真实来源层；塞进 `raw_ocr` 即虚假宣称 OCR 来源——正是“不得把模型输出标记为已认证 OCR 坐标”的文字版禁区。
2. 规范化期校验与重放校验硬绑 OCR 逐字：`validate_accepted_candidate_sources`（`page_review_sources.py:55-58`）与 `validate_replayed_sources`（`fact_normalization_replay_sources.py:24-26`）同用该检查，无任何降级通道。
3. 新定位只能进入**新** `CompleteEvidenceProcessingRevision`（修订不可变、`locator_ids` 冻结、`FactAuthority` 绑定修订指针，`facts.py:92-109`）——这本身是设计允许的追加路径（激活事件切换指针），不是缺陷，但意味着桥接必然走“新修订/新权威/新运行”，旧事实、旧修订、原图永不被改写。

### 3. 最小增量桥接（精确实体/字段；不实施）

**3.1 新增枚举成员**：`LocatorSourceLayer.PAGE_IMAGE`（视觉页层；`source_text_sha256` 语义为 `page_image_sha256`）。附加不变量（写入 `EvidenceLocatorArtifact` 校验器）：`page_image` 层只允许 `precision ∈ {page_excerpt, page_only}`，禁止 `bbox/text_range`；`authenticity` 只能 `DEGRADED` 并带 `degradation_reason`；`AUTHENTICATED` 的同源坐标 sidecar 门禁原样不动。

**3.2 确定性物化器**：仅对 `reconciliation.accepted_fact_keys`（双读交叉采信）中的观察，当其摘录未通过 OCR 逐字预检时，生成 `page_excerpt` 定位：`excerpt` = 观察摘录逐字、`source_text_sha256` = 页图像哈希、`anchor_hash` 沿用现有 `locator_anchor_hash`、`locator_algorithm_version` 如 `page-review-accepted-excerpt/v1`；附加出处字段（additive）：`page_review_coverage_id`、`page_review_ids`、`source_observation_refs`、`reconciliation_id`。幂等只建不改；单读、冲突组、NONE 信号永不物化。

**3.3 入修订方式（Codex 决策点 R vs G）**：
- **R（推荐）**：物化定位进入新的完整处理修订（追加候选管线 + 激活事件），门禁体系保持单一定位闭包；`LOCATOR_AND_TEXT_HASH` 只需接受 `page_image` 层；断言闭合零改动（page_excerpt 已支持）。代价：修订管线集成与一次激活切换。
- **G**：修订不动，终局门禁旁路接受 `source_observation_refs` 页级出处。代价：永久双出处体系，且断言闭合仍需为 VLM 摘录开豁免——改动并不更小，审计链更弱。我不推荐 G。

**3.4 规范化期校验四通道**（同改 `validate_accepted_candidate_sources` 与 replay）：①逐字→现状；②双读采信非逐字→允许引用，**强制**生成 `ocr_visual_text_mismatch`（或等价新 code）未解决项，列页、观察 ref、摘录头——文本分歧作为定位不确定性可见，不静默、不判“无来源”；③页序重构成立→可引用并可标注重构依据；④→仅未解决项。

### 4. 与“放松真实性/双读一致”的界限

不放松清单：双读采信标准不变（仍只认 `PageReconciliation` 交叉一致）；模型自报坐标永不成为 `authenticated` bbox；`page_only` 仍不能作肯定/否定断言依据（`fact_evidence_closure.py:273` 不动）；OCR 与 VLM 的文本分歧**不裁决谁对**，只登记为待核对；原图、旧事实、旧修订零改写；`FactAuthority` 陈旧即拒绝发布机制不变。本桥接只是给“双读已采信、OCR 无法逐字核对”的内容一条诚实的降精度出处，不降低任何一致性要求。

### 5. 有界实施顺序

1. **阶段 0（止血，可先行）**：错误聚合（首轮方案 B，独立成立）+ 输入标注四通道状态。停止对 X-ray 组做同反馈重试（否则同墙）。
2. **阶段 1（合同）**：`PAGE_IMAGE` 枚举 + 定位校验器附加不变量 + 物化器 + 出处字段；单元负测试先行。
3. **阶段 2（门禁与重放）**：`validate_accepted_candidate_sources`/`validate_replayed_sources` 四通道；`LOCATOR_AND_TEXT_HASH` 接受 page_image 层；新修订纳入（决策 R）。
4. **阶段 3（发布与前端）**：`FactPublicationService`、检查点重建、Profile 投影透传出处；前端按设计书显示真实精度（页级摘录无高亮坐标）。
5. **阶段 4（兼容验证）**：旧任务/旧修订重放全绿（无 page_image 定位即零行为差）；新任务提示版本 bump；运行中作业隔离不受影响。

### 6. 决定性负测试（摘）

- `page_image` 层 + `bbox/text_range` → 合同拒绝；`page_image` + `AUTHENTICATED` → 拒绝。
- 单读/冲突组/NONE 信号物化 → 拒绝；仅 accepted keys 可物化。
- 物化器对既有定位/修订/图像 UPDATE → 拒绝（只允许 append；旧修订哈希不变）。
- 双读采信非逐字候选发布时缺 `ocr_visual_text_mismatch` 未解决项 → 拒绝（可见性不变量）。
- OCR 校对后新修订使原非逐字观察变逐字 → 分类翻转且旧记录不被改写。
- `page_only` 断言依据仍拒绝；前端对 DEGRADED 定位渲染坐标/高亮 → 拒绝。

### 7. 范围风险

R 路径的修订管线集成量；页级定位保守继承整页 BLOCKING OCR 风险可能过度阻断（建议保留 `ocr_page_id` 继承，先保守）；VLM 支撑事实的来源强度仍按文档元数据派生（是否加显示级“文本核对降级”标记，交 Codex）；②类事实的时间线/Profile 呈现需产品确认。

### 8. 给 Codex 的有界问题

1. R（新修订承载）vs G（门禁旁路）裁定——我推荐 R，理由见 3.3。
2. `ocr_visual_text_mismatch` 的 gap_type 归属：复用 `PROVENANCE_FOLLOWUP` 还是新增枚举（影响期望投影与前端行动文案）。
3. 阶段 0 是否先行落地（聚合报错 + 停止同反馈重试），不等桥接。
4. 3/15 的 X-ray 组在桥接落地前的处置：保持“需要核对”终态等待，还是接受临时降级（我建议保持等待，避免再造一轮 1744s）。
