# Slice 4.4 详细可实施合同独立细化

日期：2026-08-19

角色：独立细化规划者，只读审查，不实施产品代码

范围：Slice 4.4「定位、风险、校对、完整处理修订、活动版本、资料中提及但未提供」

结论：可按本文拆分实施；任何工作包不得越过本文停止点进入 Slice 4.5/Phase 5。

## 1. 审查范围与当前事实

### 1.1 已读取的权威来源

- 项目边界：`AGENTS.md`。
- 活动任务：`prd.md`、`design.md`、`implement.md`、`reviews/final-planning-review.md`。
- 总体设计：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`、`docs/PROJECT_CONTEXT.md` 的 Phase 4 检查点。
- 已验收 Slice 4.1-4.3：三份 `reviews/codex_execution_phase4-evidence-ocr-v2-slice4*_review.md`，以及当前未提交的实际代码和测试。
- 后端规范：`.trellis/spec/backend/database-guidelines.md`、`quality-guidelines.md`、`persistent-jobs.md`、`error-handling.md`、`directory-structure.md`。
- 前端规范：`.trellis/spec/frontend/state-management.md`、`type-safety.md`、`quality-guidelines.md`、`component-guidelines.md`、`directory-structure.md`。
- 现行实现重点：`app/domain/contracts/{evidence,evidence_ingestion,evidence_processing,ocr,review,enums}.py`、`app/evidence/{locator,risk}.py`、`app/storage/{models,evidence_repositories,ocr_models,ocr_repositories}.py`、`app/services/evidence_*`、`app/api/v2/{subjects,evidence*}.py`、`frontend/src/{pages/EvidencePage.tsx,api/evidence,components/evidence-workspace}` 及对应 `tests/v2`/Vitest/Playwright。

未读取工作区外临床原始资料，未使用 legacy 项目数据推导合同。

### 1.2 4.1-4.3 已接受且不得回写的基线

1. `0008`/`0008a` 已建立不可变原文件、逻辑资料版本、元数据修订、候选快照、上传预览和确认；候选可供同集合 no-op 收敛，但不是活动基准。
2. `0009` 已建立不可变 `PageArtifact`、`OCRProfile`、`OCRPage`、原始请求/响应、运行/尝试、页租约，以及明确不可激活的基础 `EvidenceProcessingRevision`。
3. 4.3 正式 OCR 页的 `risk_items` 为空，且 `OCRPage`/canonical payload 不可变；4.4 不得回填或改写它。
4. 扫描/照片正式路线当前只有 text-only OCR。无机器坐标时不得画框；合成布局度量不是正式坐标能力。
5. 当前 `EvidenceSnapshotRepository.latest_effective_for_scope()` 仍从 `ACTIVE` 状态集合按创建顺序取末项，前端也从列表状态/时间派生“当前资料版本”。这是 4.2 的临时脚手架，4.4 必须彻底移除其活动权威地位。
6. 当前真正被 `EpisodeRepository`、API 和既有审核链使用的是 `app.domain.contracts.review.ReviewEpisode`，其物理表仍有 legacy `evidence_snapshot_id`；`evidence_ingestion.py` 中另有带成对活动指针的同名合同。4.4 必须收敛为一个活动版本事实源，不能继续维护两套同名真相。

## 2. 第一性原理与不可跨越边界

### 2.1 Slice 4.4 只回答六个问题

1. 一段待核对文字真实来自哪一个不可变页和哪一层文本？
2. 系统能诚实定位到 bbox、字符范围、页内摘录还是仅页码？
3. 原 OCR 中哪些片段属于识别核对风险，是否已由用户明确处理？
4. 用户的校对如何在不覆盖原 OCR 的前提下形成可回放的有效文本层？
5. 哪一组页产物、OCR、定位、风险核对、校对、元数据和引用资料关系构成一个可激活的完整处理修订？
6. 审核节点当前使用的快照/处理修订是哪一对，如何激活和回滚？

它不回答临床事实是什么、是否满足入排标准、AND/OR 条件如何判定、行动应由谁关闭。以上属于 Phase 5/6。

### 2.2 六条硬不变量

- **原始层不变：** SourceBlob、PageArtifact、原生文本/坐标、OCRPage.raw_text、原始请求/响应以及 4.3 基础处理修订永不 UPDATE。
- **扫描只观察：** 风险扫描输出结构化提示，不输出修正文，不写 ClinicalFact、RuleExpression、Assessment、Gap 或 ReviewRun。
- **校对是覆盖层：** 校对记录锚定原 OCR 哈希和原始字符范围；“有效文本”是确定性投影，不替换 OCRPage.raw_text。
- **定位必须可证：** bbox 必须由与来源文本同源的字符/词坐标逐字符映射得到；页尺寸或模型自报坐标本身不构成真实性。
- **活动版本显式：** 当前版本只来自 `ReviewEpisode.active_evidence_snapshot_id + active_evidence_processing_revision_id`，不得从时间、列表顺序、最大 ID、状态数量或 legacy 字段推断。
- **候选隔离：** 候选失败、取消、待核对或冲突不能改变活动指针、旧 ReviewRun、旧投影或“已有更新版本”状态；只有成功的 ActivationEvent 可以产生版本更新事实。

## 3. 术语与分层真相

| 名称 | 定义 | 是否可变 |
|---|---|---|
| 原始 OCR | `OCRPage.raw_text + raw_text_sha256` | 否 |
| 风险扫描工件 | 对某一原始 OCR 哈希、规则版本运行后的完整风险集合 | 否 |
| 风险核对记录 | 用户对单个风险的确认、校对或“不适用”处理 | 追加写 |
| 校对记录 | 对原始 OCR 固定范围的替代层及理由/确认 | 追加写 |
| 有效文本 | 原 OCR 加当前处理修订所选校对记录的确定性投影 | 可重建，不是事实表 |
| 定位工件 | 对一个稳定目标范围和固定来源文本生成的四级定位结果 | 否 |
| 基础处理修订 | 4.3 产物；只冻结页、PageArtifact、OCRPage | 否，永不可激活 |
| 完整处理修订 | 新建修订；冻结基础页清单及全部 4.4 关联 | 否，通过门禁后可激活 |
| 活动版本 | ReviewEpisode 明确指向的 `(snapshot_id, complete_revision_id)` | 仅经 ActivationEvent 原子切换 |
| 被提及资料 | 原文明确提及但当前完整处理修订中未由资料满足的记录 | 通过不可变修订/满足关系演进 |

## 4. 领域合同冻结

### 4.1 避免回写 4.3 的持久化策略

`0010_evidence_locator_corrections` 采用“现有处理修订根 + 新增旁路工件/关联”的追加设计：

1. 现有 `evidence_processing_revisions` 保留，新增 `revision_kind = base|complete`、可空 `base_processing_revision_id` 和 `completion_manifest_sha256` 投影列。
2. 迁移前的 4.3 行投影为 `base`；其 canonical payload、payload hash、页清单和 `is_activatable=False` 不改写。
3. 新完整修订是新的 root row，不是在旧基础行上补字段；它复制并冻结同一有序页清单，另通过子表固定 locator、risk scan/review、correction、metadata revision、referenced-document revision/resolution 的 ID 集合。
4. 仓储按 `revision_kind` 分派到 `BaseEvidenceProcessingRevision` 或 `CompleteEvidenceProcessingRevision` 合同。旧 base decoder 继续逐字回放旧 payload。
5. 完整修订的 `completion_manifest_sha256` 对所有有序引用及其 canonical payload hash 计算；任一子表缺行、多行、换绑或顺序漂移都拒绝读取/激活。
6. `base_processing_revision_id` 必须属于同一 snapshot/scope，且其页清单逐项等于完整修订页清单。完整修订不能借机换页、换 OCR 或隐藏失败页。

建议新增表按职责拆分，而不是把大数组只塞进 JSON：

- `evidence_locator_artifacts`
- `ocr_risk_scans`、`ocr_risk_flags`
- `ocr_risk_reviews`
- `correction_records`
- `processing_revision_locators`
- `processing_revision_risk_scans`、`processing_revision_risk_reviews`
- `processing_revision_corrections`
- `processing_revision_metadata_revisions`
- `referenced_document_revisions`、`referenced_document_resolution_revisions`
- `processing_revision_referenced_documents`
- `evidence_activation_events`
- 可恢复构建需要时：`evidence_processing_candidates`、`evidence_processing_candidate_events`

所有不可变表保存 canonical payload/hash、UTC 时间和必要镜像列；列表读取也必须执行镜像闭包校验，不能先用漂移列过滤后隐藏坏行。

### 4.2 定位请求与定位工件

定位请求必须包含：

- `page_artifact_id`、可选 `ocr_page_id`；
- `source_layer = native_text|raw_ocr|effective_text`；
- `source_text_sha256`；
- 稳定目标 `target_id`；
- 优先使用原始 `target_text_start/target_text_end`，其次才是摘录文本；
- locator/coordinate transform/sidecar 版本；
- effective_text 时同时带 `processing_revision_id` 和 effective text hash。

定位结果必须另外冻结：`source_document_version_id`、页码、页图哈希、坐标 sidecar 哈希、目标范围/摘录哈希、消歧证据和真实性门禁结果。`locator_id` 身份至少包含页工件、来源层、来源文本哈希、目标范围或上下文锚点、算法版本；当前仅按“页 + 规范化目标文本”生成 ID 的方式不能用于重复文本正式持久化。

精度门禁：

1. `bbox`：仅当目标原始范围可一一映射到同源坐标字符/词，坐标 sidecar 的文本哈希与 source hash 一致，区域在当前页内，变换版本匹配且覆盖目标文本时允许。当前 text-only 扫描/OCR 路线一律不得输出 bbox。
2. `text_range`：范围必须直接指向绑定来源文本且内容一致；不能用在另一层文本上的偏移。
3. `page_excerpt`：目标可在页内证明存在但没有稳定唯一范围，或重复文本无充分 occurrence anchor 时使用；必须说明降级原因。
4. `page_only`：目标未找到或只知道页时使用；不得携带摘录、范围或坐标。

重复文本规则：有可信原始 range 且 range 与同源坐标可映射时，可定位该 occurrence；只有目标字符串、多个命中或上下文锚点不唯一时必须降级。禁止“取第一处”“取最近一处”“按阅读顺序猜测”。

### 4.3 风险扫描工件

`OCRRiskScan` 绑定 `ocr_page_id + raw_text_sha256 + scanner_rule_version`，保存完整 flag 集合哈希、运行时间和覆盖状态。同一三元组幂等复用；规则版本变化新建扫描，不覆盖旧扫描。

`OCRRiskFlag` 保持极性、数值、小数点、单位、日期为 blocking，重复文本/低置信为 informational，并增加所属 scan/ocr page/raw hash 镜像。所有范围必须逐字回验原始 OCR。

扫描器的输出类型只能是 `list[OCRRiskFlag]`/`OCRRiskScan`。以下调用和副作用在模块边界测试中应被禁止：

- 返回修改后的字符串、规范化临床值或布尔表达式；
- 写 `OCRPage`、`CorrectionRecord`、`ClinicalFact`、`RuleComponent/RuleExpression`、`Assessment`、`ReviewRun`；
- 把 OCR 风险映射成“符合/不符合/证据不足”等临床判断；
- 因识别到数值/单位而重排、合并或改写“且/或/以及/任一/全部”等并列条件。

冻结的复合反例文本至少包括：

`ALT > 3×ULN 且 AST > 3×ULN，或总胆红素 > 2×ULN。`

扫描前后原始文本哈希必须相同；扫描可标出数值/单位，但不能生成新的文本，不能把 `且` 改成 `或`，不能产生或更新任何规则表达式。

### 4.4 风险核对与校对

`OCRRiskReview` 是追加写用户动作，包含：risk ID、决议 `confirmed_as_read|corrected|not_applicable`、理由、actor、UTC 时间、base complete/base processing revision、expected revision。blocking risk 只有在完整处理修订明确选中有效 review 后才视为已核对；仅打开页面或保存草稿不算核对。

`CorrectionRecord` 必须包含：

- `ocr_page_id`、`raw_text_sha256`、原始 start/end、原始文本；
- corrected text；可选结构化 old/new 值及单位/日期精度；
- reason、actor、created_at；
- `supersedes_correction_id`；
- `base_processing_revision_id` 和受影响页/原始范围；
- 确定性变化类别；
- 是否需要二次确认、确认人/时间/确认动作。

变化类别至少覆盖 `polarity|numeric|decimal|unit|date|semantic_connector|other_text`。前五类沿用 PRD blocking 规则；`semantic_connector` 不是风险扫描器的自动“修正”，但用户若确实把 `且/或/以及/任一/全部` 等连接词改成另一逻辑含义，必须二次确认并保留前后文本。Phase 4 只保存来源校对，不据此更新 RuleExpression。

有效文本投影规则：

1. 所有 correction 都锚定同一不可变 raw OCR，而不是锚定前一版 effective text，避免字符偏移逐版漂移。
2. 一个完整修订对同一原始范围最多选择一个有效 correction；后继必须显式 supersede 前项。
3. 两个有效 correction 范围重叠但无显式替代时拒绝构建完整修订。
4. 投影按原始 offset 确定性应用并计算 effective text hash；读取时重新计算核对。
5. 新校对创建新的完整处理修订候选；旧完整修订仍投影旧 correction 集合，精确回放不变。
6. 影响范围只记录受影响 OCRPage/PageArtifact/字符范围和后续可消费的 scope token；4.4 不启动全项目临床重算，也不自动关闭行动。

### 4.5 “资料中提及但未提供”

使用两层追加合同，不能保留一个可变 `provided` 布尔值：

- `ReferencedDocumentRevision`：稳定 referenced-document ID、scope、描述、document type/source party（可未知）、触发 locator ID、来源方式 `manual|deterministic_candidate`、pattern version、状态 `proposed|confirmed|dismissed`、supersedes revision。
- `ReferencedDocumentResolutionRevision`：状态 `unresolved|provided`；provided 时必须引用同一 scope、且属于该完整处理修订 snapshot 成员的 `source_document_version_id`；解除关联产生新的 unresolved revision，不删除旧满足关系。

规则：

1. 确定性模式只能生成 proposed，不能自动 confirmed/provided。
2. 每条 confirmed 记录必须有可回放触发 locator；无法提供 trigger 时不能伪装成“原文提及”。
3. 后续上传文件只有在新的完整处理修订中显式建立 resolution 后才算已提供；旧处理修订仍回放 unresolved。
4. dismissed 只表示用户解除该候选，不删除候选、触发原文和历史。
5. 本功能不创建 ClinicalFact、EvidenceExpectation 结论、规则影响、入排判断或 ActionRequest。

### 4.6 完整处理修订的闭包门禁

一个 `complete` 修订只有同时满足下列条件才可标记 `is_activatable=True`：

1. 快照及全部文档属于同一 project/subject/review episode/study phase。
2. 页清单与绑定 base revision 完全一致且覆盖 snapshot 每个成员的实际页清单；无缺页、失败页、重复页、换页或非终态 OCR。
3. 每页固定真实 PageArtifact、实际 OCRPage（原生路线允许明确无 OCR 的受控合同）、metadata revision。
4. 每个 locator 的来源层、哈希、页、坐标 sidecar 和目标归属闭合；任何伪 bbox 或跨页引用阻断。
5. 每页固定一个风险 scan 版本；所有 blocking flag 均有本修订选中的有效 review/correction；informational 可保留未处理。
6. correction 集合无重叠冲突、关键变化均完成二次确认，effective text hash 可重建。
7. referenced-document revision/resolution 集合完整且所有 trigger/提供文件属于本修订闭包。
8. completion manifest hash 与所有子表/子 payload 一致。

门禁失败只能产生不可激活的处理候选状态/事件，不得创建“半完整但可激活”的 revision。

## 5. 活动指针、激活与回滚事务

### 5.1 ReviewEpisode 单一权威

1. 以现有 `app.domain.contracts.review.ReviewEpisode` 和 `EpisodeRepository` 为唯一运行合同，新增可空成对字段 `active_evidence_snapshot_id`、`active_evidence_processing_revision_id`。
2. `evidence_ingestion.py` 的同名合同应收敛为导入/兼容别名或删除重复定义；不得让 API、服务和仓储各选一套。
3. legacy 非空 `evidence_snapshot_id` 保留其 Phase 2/旧 fixture 语义，本 Slice 不重指向 `evidence_snapshots_v2`，也不得作为 Phase 4 当前版本 fallback。
4. `0010` 对活动指针增加 FK 和“同时为空或同时非空”的 CHECK；跨 scope/修订属于目标快照的约束由同事务仓储再次验证。
5. 迁移不按时间回填活动指针。升级时没有完整可激活 revision，因此指针保持 null；即使发现一个或多个历史 `ACTIVE` snapshot，也不得猜测。测试/开发数据通过正式激活命令建立指针。

### 5.2 成功激活的单事务顺序

输入：target snapshot、target complete revision、expected episode revision、actor、reason、job/idempotency key。

同一数据库事务内：

1. 重读并校验 expected episode revision 和当前成对指针。
2. 完整执行 4.6 闭包门禁；base revision 永远拒绝。
3. 目标 snapshot 首次发布时验证 `READY` 并追加 `ready -> active` 状态事件；同一已激活 snapshot 的新处理修订不重复转换 snapshot 终态。
4. 追加唯一连续的 `EvidenceActivationEvent`，记录 from/to 两对指针、event kind `activate|rollback`、reason、actor、job、expected revision、时间。
5. 以乐观锁原子更新 ReviewEpisode 两个活动指针并递增 revision。
6. 提交后才产生“当前版本已更新”的投影事件；不修改旧快照、旧处理修订、旧 ReviewRun 或旧报告。

任一步失败则 ActivationEvent、snapshot 状态事件和 episode 更新全部回滚。不得出现“事件成功但指针未变”或“指针已变但事件缺失”。

### 5.3 回滚

- 回滚目标必须是历史 ActivationEvent 中出现过、且当前仍能通过完整回放校验的一对 snapshot/complete revision。
- 回滚不重开旧 snapshot 候选，不改写其状态；追加 `rollback` ActivationEvent 并按 expected episode revision 切换成对指针。
- 回滚后的“当前”仍只由新事件/指针决定，不取创建时间最大值。

### 5.4 候选失败隔离

- `retryable_failure|terminal_failure|cancelled|needs_attention|revision_conflict` 均不得写 ReviewEpisode、ActivationEvent 或任何旧结果 stale/update-available 标记。
- 双标签页同时激活时，只允许一个 expected revision 成功。失败者记录候选冲突事件，但不能追加成功 ActivationEvent。
- 只有成功激活后，基于旧活动 pair 的当前投影可显示“已有更新版本”；历史投影仍按其绑定 pair 回放。

### 5.5 所有读取路径必须改用指针

- `latest_effective_for_scope()` 改为读取 episode pointer 后按 ID 获取并校验，不排序猜测。
- 上传预览的 incremental prior/full comparison base 只取 pointer 指向 snapshot。
- Subject/Episode API 返回两个活动 ID；snapshot list DTO 明确返回 `is_current`（由 pointer 投影），不能让前端从 `status=active` 猜。
- `EvidencePage.currentSnapshotVersionLabel()` 使用服务端 current ID/显式序号；禁止按 createdAt 计算活动身份。展示序号可以是服务端稳定 activation sequence，但活动选择不能依赖它。
- 重启、列表顺序变化、相同时间戳和多个历史 ACTIVE 状态下结果必须一致。

## 6. 处理候选状态与持久任务

为避免“不可变完整修订”和“需要等待用户核对的可变过程”混为一体，4.4 应新增 `EvidenceProcessingCandidate`（或等价明确命名的构建实体）：

`staged -> processing -> needs_attention|retryable_failure|terminal_failure|cancelled|ready|revision_conflict`

- candidate 绑定 snapshot、base processing revision、expected episode revision、Job 和幂等键。
- locator/risk scan 等不可变工件可在失败后复用；candidate 状态由追加事件投影。
- `needs_attention` 无 worker 租约，等待用户风险核对/校对；用户动作后创建/推进同一构建命令，但最终只新建一次完整 revision。
- `ready` 表示完整 revision 已冻结且门禁通过，尚未激活。
- correction 作用于当前 active pair 时创建新的 processing candidate + Job，不改变已终态 snapshot。
- candidate 冲突/失败后重试不得复用为另一个输入；同键同请求回放，同键异请求冲突。

## 7. API 与前端最小合同

### 7.1 API

保持设计书路径，至少冻结以下请求/响应事实：

- 页接口分别返回 `raw_ocr`、`effective_text`、selected correction IDs、risk scan/review、locator precision/degradation；字段命名不得把 effective text 叫“原始识别”。
- correction POST 必须带 raw hash、原始范围、base processing revision、expected episode revision、幂等键；关键变化带显式 confirmation payload。
- processing revision GET 返回 revision kind、base ID、snapshot ID、完整清单 hashes、activatable 和逐门禁结果。
- activate POST 必须带 expected episode revision；响应返回 ActivationEvent ID、旧/新 pair 和新 episode revision。
- referenced-document create/patch/resolve/delete 都创建新 revision，不执行原地 UPDATE/DELETE；`DELETE resolution` 是追加 unresolved revision。
- 错误信封稳定区分：定位降级（非错误）、待核对、修订冲突、跨作用域、非完整修订、门禁失败、幂等冲突。

### 7.2 Slice 4.4 前端边界

- 中栏明确并列“原始识别文本”和“校对后文本”；任何切换都保留标签，不把校对层伪装成 OCR。
- 风险显示“识别核对”，不显示“临床风险/不符合标准”；blocking 只解释为“需核对后才能启用此资料版本”。
- locator badge 显示真实四级精度和降级原因。4.4 可展示 locator 元数据；真实连续页图、缩放映射和红框完整体验留给 4.5。
- 当前资料版本由 API `is_current/active IDs` 显示；历史 `ACTIVE` 状态不得都标为当前。
- “资料中提及但未提供”支持确认、修改、解除和关联已上传文件；确定性候选必须显示“待确认”。
- stale/409 后保留用户输入和 server diff，不自动换 base revision 重放。

## 8. 必须先写的反例测试

### 8.1 定位诚实性

1. text-only OCR 即使返回看似坐标的自由文本，也只能 text_range/excerpt/page_only。
2. bbox 有页尺寸但无同源 coordinate sidecar，拒绝。
3. sidecar/source text hash、page artifact、页码或 transform version 任一不匹配，拒绝。
4. bbox 越界、落在错误页、未覆盖目标文本或字符映射不完整，拒绝/降级。
5. 同页两处相同文本：只有明确同源 occurrence range 才可定位各自；仅给字符串必须降级，locator ID 不碰撞。
6. 重复表格日期不能默认取第一处；列表/字典顺序变化不改变结果。
7. 0 个 bbox 输出不能被计算为布局通过；量化分母必须覆盖全部目标。

### 8.2 风险不越权

1. 扫描前后 OCR raw bytes/hash 完全相同，数据库 OCRPage 行/payload/hash 不变。
2. 上述 ALT/AST/胆红素复合句只产生风险 flags；连接词和全文逐字不变，无 RuleExpression/ClinicalFact 写入。
3. 同一 raw hash+rule version 幂等；新 rule version 新建 scan，旧 scan 可回放。
4. 风险范围跨出 raw text、指向不同文本或重复 risk ID 均拒绝。
5. 种子集关键漏检为 0、页面误报率 <=10%，并证明所有 eligible 页进入分母。
6. informational 风险不阻断；任一未核对 blocking 风险阻断完整修订激活。

### 8.3 校对与回放

1. 数值/极性/单位/日期/小数点或 semantic connector 变化缺二次确认时拒绝。
2. 校对后 OCRPage.raw_text/hash、原始响应工件不变；effective text/hash 正确。
3. 两个无替代关系的重叠 correction 拒绝；显式 supersede 后只选新记录。
4. 双标签页用同一 base revision 提交不同校对，只允许一个链头成功，另一方收到差异。
5. 修订 R1/R2 各自选择不同 correction；读取 R1 永远得到旧 effective text。
6. 只标记受影响页/范围，不把其他文件、节点或项目加入影响范围。

### 8.4 完整修订与活动版本

1. base revision、缺页、失败页、缺 risk scan、未核对 blocking risk、metadata/locator/reference 越界均不能激活。
2. 构建完整 revision 时故障注入，不能留下可激活半清单。
3. 两个 ACTIVE snapshot 创建时间逆序/相同；只有 pointer 目标是 current。
4. pointer 为 null 但存在 ACTIVE status 时不得 fallback；上传 incremental 应明确要求先完成正式激活。
5. 候选 retryable/terminal failure、cancel、needs_attention 后 episode pointer/revision、旧结果状态均不变。
6. 两候选同 expected revision 激活，恰好一个成功；败者不影响胜者和旧历史。
7. ActivationEvent 插入后注入 pointer update 失败，整个事务无事件无指针变化；反向故障同样原子回滚。
8. rollback 新增事件并切换到历史 pair；不改旧事件/旧 revision/创建时间。
9. 服务重启、列表随机排序后 current 仍相同。

### 8.5 被提及资料

1. deterministic candidate 不经用户确认不能进入 confirmed 集合。
2. trigger locator 跨页/scope/processing revision 时拒绝。
3. 关联文件不属于当前 snapshot member 时拒绝 provided。
4. R1 unresolved，后续 R2 provided；回放 R1 仍 unresolved。
5. dismiss/解除只追加 revision，旧候选和触发原文仍在。
6. 任意操作均不创建 ClinicalFact、规则判断、ActionRequest 或改变 ReviewRun。

### 8.6 迁移与兼容

1. 0009 数据升级后 payload/hash、页清单和 base 不可激活性质逐字不变。
2. `review_episodes` 重建保留全部子表外键行；前后 row count/hash、WAL、FK/integrity check 一致。
3. 迁移不按 created_at/ID 回填活动指针。
4. 旧 fixture/legacy `evidence_snapshot_id` 仍可读，但 Phase 4 current 查询不消费它。
5. 含任何 0010 正式历史时有损 downgrade 明确拒绝；空绿地库才允许降级。

## 9. 建议的四个互斥写入工作包

四包必须串行合并，文件所有权互斥；后包只消费前包公开合同，不回改前包实现。

### WP-44A 领域与持久化闭包

**唯一写入：** `app/domain/contracts/*`、`app/storage/migrations/versions/0010_*`、新增 `app/storage/*locator*|*correction*|*activation*|*referenced*` 模型/仓储、现有 `models.py`/仓储注册点，以及 `tests/v2/evidence/test_slice44_*contracts.py`、`tests/v2/storage/test_*0010*.py`。

**交付：** discriminated base/complete revision、旁路工件、canonical hash、ReviewEpisode 单一合同、迁移/升降级、追加仓储。

**停止：** 不写服务、API、前端；以“旧 0009 逐字回放 + 0010 存储反例”结束。

### WP-44B 确定性引擎、构建服务与激活事务

**唯一写入：** `app/evidence/{locator,risk}.py` 及新 4.4 engine 文件、`app/services/evidence_*revision*|*correction*|*activation*|*referenced*`、必要的新 workflow executor 文件、`tests/v2/evidence/test_slice44_*engine.py`、`tests/v2/services/test_slice44_*.py`、`tests/v2/workflow/test_slice44_*.py`。

**交付：** occurrence-aware 定位、旁路风险扫描、校对投影、完整 revision builder、候选状态机、原子激活/回滚、失败隔离。

**停止：** 不写 API/前端；所有反例用 service/repository 接口完成。

### WP-44C API 合同与后端集成

**唯一写入：** `app/api/v2/evidence*.py`、新增 4.4 API/schema 文件、`app/api/v2/subjects.py`、`app/api/v2/schemas.py`、`app/api/v2/app.py`、API vocabulary/error mapping、`tests/v2/api/test_slice44_*.py`、OpenAPI snapshot/architecture-boundary 测试。

**交付：** 页分层读取、校对、处理修订、激活/回滚、被提及资料 API；Subject/Episode current IDs；统一中文错误。

**停止：** 不改 domain/storage/service 算法；任何缺口退回 A/B，不在 router 补逻辑。

### WP-44D 前端核对与引用资料最小闭环

**唯一写入：** `frontend/src/api/evidence/**`、`frontend/src/components/evidence-workspace/**`、`frontend/src/pages/EvidencePage*`、`frontend/src/styles/evidence.css`、对应 Vitest 和 `frontend/e2e/evidence-*`。

**交付：** raw/effective 并列、风险核对与关键确认、修订冲突恢复、current pointer 投影、被提及资料确认/修改/解除/关联。

**停止：** 不实现 4.5 连续原件滚动、缩放 bbox 红框、完整视觉验收和帮助中心。

共享导出/注册文件只归其声明包所有；其他包通过明确模块路径消费，禁止多个并行 writer 修改同一 `__init__.py`、`app.py`、schema 或测试夹具。A -> B -> C -> D 每包结束独立验证后再开始下一包。

## 10. Slice 4.4 停止点

满足以下全部条件才能放行 4.5：

1. 0010 升级/验证/有损降级拒绝通过，4.3 base rows 与原 OCR 无任何改写。
2. 四级定位量化门槛仍通过；正式扫描/照片路线保持无 bbox，重复文本反例无错位和 ID 碰撞。
3. 风险种子漏检 0、页面误报 <=10%、覆盖完整；扫描器副作用/临床越权/并列逻辑改写测试通过。
4. 校对关键变化必须二次确认，旧完整修订可精确回放 raw/effective/locator/risk/metadata/referenced closure。
5. base revision 不可激活；完整 revision 缺任一闭包要素均不可激活。
6. 活动版本所有读写路径只用成对 pointer；时间推断和 legacy fallback 的代码与测试均不存在。
7. 候选失败、取消、冲突和服务故障不能改变现行 pair 或旧审核结果；激活/回滚事件与 pointer 通过故障注入证明原子。
8. “资料中提及但未提供”只产生引用资料修订/满足关系，不生成临床事实或判断。
9. 后端全量 V2、前端 typecheck/Vitest/build、4.4 聚焦 API/E2E、Ruff/Pyright、`git diff --check` 全部通过，并由新鲜上下文独立检查者验收。

明确不在 4.4 验收：扫描/照片 bbox 能力采用、连续原文件滚动和缩放红框完整视觉、Phase 5 ClinicalFact/Patient Profile、Phase 6 入排判断/Action，以及真实临床资料试用。

## 11. 未决风险

1. `ReviewEpisode` 的 legacy snapshot 与 Phase 4 current pair 并存会增加迁移和 API 认知成本；实施时必须保持命名清晰，不能把旧字段悄然改义。
2. SQLite 重建 `review_episodes` 时已有多张子表引用它，迁移恢复和外键完整性是 0010 的最高风险点。
3. 当前 locator 的 ID 和字符串搜索不足以区分重复 occurrence；正式持久化前必须升级为 range/context-aware 身份。
4. 当前风险 scanner 是种子规则，不包含全部支配范围/参考区间/矛盾日期；量化门槛只能对冻结金标准负责，不能宣称一般临床准确率。
5. 完整修订构建若同时由 snapshot 状态和 processing candidate 状态驱动，可能形成双重状态真相；本文要求 candidate 管处理构建、snapshot 管文档候选，激活事务负责二者汇合。
6. 4.4 前端只能证明语义和事务闭环；真实页图联动、缩放和红框错位风险仍必须留给 4.5 浏览器验收。
