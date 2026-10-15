# Research: V2 证据领域模型与 SQLite 持久化现状

- Query: 现有 EvidenceSnapshot / Document / EvidenceSpan / OCR 合同和表有哪些；缺什么；Phase 4 最适合在哪些迁移、仓储、服务与 API 边界切入；必须保持哪些不可变与幂等约束。
- Scope: internal
- Date: 2026-08-19

## Findings

### 1. 设计与计划基线

Phase 4 的直接基线不是当前任务目录中的任务文档，而是总设计和总实施计划：

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:31-41` 冻结了上传、阶段隔离、冲突和校对原则：增量去重合并，全量创建完整新快照，后续阶段不得静默改写早期结果，原文件和原 OCR 不变。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:77-83` 冻结 SQLite/WAL + SQLAlchemy 2 + Alembic，以及 OCR 内容哈希缓存和最大 8 路准入。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:114-138` 定义了 EvidenceSnapshot、SourceDocumentVersion、OCRPage、CorrectionRecord、EvidenceSpan、ReferencedDocument 和 EvidenceExpectation 的职责，以及 `bbox > text_range > page_excerpt > page_only` 的诚实降级阶梯。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:297-319` 把文件指纹/分类/OCR、OCR 风险门控、Evidence Normalizer 和确定性 Gate 分开，并要求文件哈希、去重、快照和阶段隔离确定性实现。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:384-395` 要求显式全量/增量入口、后台 Job、跨受试者流水并行和全局 8 路 OCR，并要求部分失败产生 `stale` 而不是继续伪装最新。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:404-418` 要求 OCR 页幂等、人工 revision、迁移前备份、旧快照/原文件/ActionTransition 不覆盖。
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md:123-142` 是 Phase 4 的具体计划与退出门槛：内容哈希去重、内容哈希+页码+模型/参数缓存键、页面完整性、ReferencedDocument、原 OCR/页图/定位、风险校对及部分失败恢复。
- `.trellis/spec/backend/database-guidelines.md:5-13` 规定原文件、OCR 原文、EvidenceSnapshot、ReviewRun 等追加写，重试写必须有幂等键。
- `.trellis/spec/backend/database-guidelines.md:21-38` 规定小迁移、SQLite backup API、迁移后 schema/PRAGMA/读写验证、payload hash 与镜像列交叉校验。
- `.trellis/spec/backend/persistent-jobs.md:3-29` 规定用户动作先落持久 Job、步骤级检查点、租约、限定范围重试和 SSE 只读订阅。

### 2. 现有领域合同

#### 2.1 已存在的直接证据合同

1. `SourceDocumentVersion`

   - 定义于 `app/domain/contracts/evidence.py:68-76`。
   - 当前字段：`source_document_version_id`、`file_name`、`sha256`、`document_type`、`source_party`、`upload_mode`、`review_stage`。
   - 它是当前代码中的 Document 等价物；没有单独名为 `Document` 的 V2 合同。
   - `UploadMode` 只有 `full/incremental`，见 `app/domain/contracts/enums.py:150-152`；`ReviewStage` 为预筛/筛选/导入/基线，见 `app/domain/contracts/enums.py:15-20`。

2. `EvidenceSnapshot`

   - 定义于 `app/domain/contracts/evidence.py:78-93`。
   - 当前字段：快照 ID、subject、review episode、完整文档版本 ID 列表、upload mode、可选 prior snapshot、创建时间。
   - 合同只保证“增量必须有 prior；全量不能有 prior”，见 `app/domain/contracts/evidence.py:87-93`。
   - 合同测试覆盖该差异，见 `tests/v2/test_contract_logic.py:1977-1989`。

3. `EvidenceSpan`

   - 定义于 `app/domain/contracts/evidence.py:21-65`。
   - 当前字段：span ID、来源文档版本、页码、定位精度、单个 bbox、text range、excerpt、定位算法版本、anchor hash、匹配置信度、降级原因。
   - 合同已经拒绝伪精确定位：bbox 必须有坐标；非 bbox 不得带坐标；text range 必须是有效范围；page excerpt 必须有摘录；page only 必须说明降级且不能带伪摘录，见 `app/domain/contracts/evidence.py:48-65`。
   - 四级定位枚举见 `app/domain/contracts/enums.py:75-79`，测试见 `tests/v2/test_contract_logic.py:1931-1974`。

4. `EvidenceExpectation` / `ClinicalFact`

   - `EvidenceExpectation` 位于 `app/domain/contracts/evidence.py:96-135`，已把 `observed/observed_weak/referenced_missing/absent/not_due` 与具体 gap type 绑定；`ocr_or_parse_risk` 只能作为弱证据风险之一。
   - `ClinicalFact` 位于 `app/domain/contracts/evidence.py:205-253`，绑定 project/subject/episode/snapshot 和至少一个 EvidenceSpan，并约束未知极性不能夹带数值/单位。
   - `EvidenceExpectationTemplate` 明确说明 Phase 4/5 再按受试者 ReviewEpisode 投影具体期望，见 `app/domain/contracts/evidence.py:138-147`。

5. `ReferencedDocument` 与候选合同

   - 最小 `ReferencedDocument` 合同已存在于 `app/domain/contracts/evidence.py:282-286`，只有 ID、描述、引用它的 span 和 `provided` 布尔值。
   - `ReferencedDocumentCandidate` 与 Evidence Normalizer 候选集合已存在于 `app/domain/contracts/normalization.py:43-69`。
   - Evidence Gate 会检查候选引用的 span 是否在当前候选集合内，见 `app/domain/gates/evidence.py:154-175`。

#### 2.2 已存在的审核闭包

- `ReviewEpisode` 当前持有活动 `evidence_snapshot_id`，`ReviewRun` 固定绑定实际使用的 snapshot，见 `app/domain/contracts/review.py:75-97`。
- 注册作用域要求 project/protocol/ruleset/subject/episode/snapshot/run 完全一致，快照文档集合等于 AgentCall 来源集合，并拒绝读取未来阶段文档，见 `app/domain/gates/scope.py:45-124`。
- fixture 完整性门禁拒绝重复文档引用、快照外 span 和未来阶段文档，见 `app/domain/gates/integrity.py:799-826`。
- Evidence Gate 拒绝跨 scope fact、未验收 span、候选外冲突引用和快照外来源文档，见 `app/domain/gates/evidence.py:102-175`。

#### 2.3 尚不存在的 OCR 领域合同

在 `app/domain`、`app/storage` 和 `tests/v2` 中，OCR 目前只以风险枚举/汇总规则存在：

- `ocr_or_parse_risk` 枚举位于 `app/domain/contracts/enums.py:104-117`。
- `EvidenceExpectation` 允许它解释弱证据，见 `app/domain/contracts/evidence.py:114-119`。
- 当前没有 `OCRPage`、`OCRRun/OCRAttempt`、`OCRProfile`、`PageArtifact/PageInventory`、`CorrectionRecord` 合同。
- 当前没有 OCR 模型/参数指纹、页级原文、布局 sidecar、页图、页级质量指标、页级失败/重试状态的 V2 合同。
- `ReferencedDocument` 虽有合同，但未从 `app/domain/contracts/__init__.py:19-27` 导出，也没有正式持久化实现。

### 3. 现有 SQLite 表与仓储

#### 3.1 直接证据表

当前表均最初由迁移 `0002` 建立，当前迁移 head 是 `0007`：

| 表 | 当前形状 | 代码定位 |
|---|---|---|
| `source_document_versions` | PK、sha256、文档类型、来源方、上传模式、审核阶段、canonical payload/hash、created_at | `app/storage/models.py:786-795`; `app/storage/migrations/versions/0002_domain_schema.py:198-210` |
| `evidence_snapshots` | PK、subject FK、episode 延迟 FK、upload mode、self prior FK、payload/hash、created_at | `app/storage/models.py:797-818`; `app/storage/migrations/versions/0002_domain_schema.py:54-68` |
| `evidence_snapshot_documents` | snapshot-document 有序多对多；同快照下文档和 position 均唯一 | `app/storage/models.py:1361-1367`; `app/storage/migrations/versions/0002_domain_schema.py:230-240` |
| `evidence_spans` | PK、source document FK、页码、定位精度、payload/hash、created_at | `app/storage/models.py:821-835`; `app/storage/migrations/versions/0002_domain_schema.py:243-254` |
| `clinical_facts` | project/subject/episode/snapshot、事实类型/极性/值/单位/日期/conflict，追加写 | `app/storage/models.py:838-867`; `app/storage/migrations/versions/0002_domain_schema.py:624-647` |
| `clinical_fact_spans` | fact-span 有序引用 | `app/storage/models.py:1368-1374`; `app/storage/migrations/versions/0002_domain_schema.py:810-819` |
| `evidence_expectations` | 可变根，revision + requirement/episode/status/gap | `app/storage/models.py:148-171`; `app/storage/migrations/versions/0002_domain_schema.py:822-839` |
| `evidence_expectation_spans` | expectation-span 有序引用 | `app/storage/models.py:1375-1381` |
| `evidence_normalization_candidates` | project/protocol/subject/episode/snapshot/AgentCall 闭包，复杂候选保存在 payload | `app/storage/models.py:876-900`; `app/storage/migrations/versions/0002_domain_schema.py:842-861` |
| `conflict_groups` | 追加写，结构主要在 payload | `app/storage/models.py:870-874` |
| `review_episodes` / `review_runs` | episode 指向当前 snapshot；run 固定 snapshot 且可 supersede 旧 run | `app/storage/models.py:107-145`; `app/storage/models.py:920-942` |
| span 下游关联 | final assessment 和 action transition 均可有序引用 span | `app/storage/models.py:1389-1402` |

辅助基础设施已经存在：

- `idempotency_records` 支持 `(scope, idempotency_key)` 唯一、同键同 hash 复用、异 hash 冲突，见 `app/storage/idempotency.py:85-164`；并发测试见 `tests/v2/storage/test_idempotency.py:118-179`。
- `entity_staleness` 对同一 target/reason/source/source_revision 幂等打开，并由新 ReviewRun 精确关闭，见 `app/storage/staleness.py:58-149` 和 `tests/v2/storage/test_staleness.py:33-80`。
- Job/Step/Checkpoint/Event、租约和 SSE 已经具备，不应为 Phase 4 另造任务系统；V2 app 只注册 Job 与方案路由，见 `app/api/v2/app.py:21-43`、`app/api/v2/app.py:112-116`。
- episode/snapshot 双向 FK 被设计成 deferred，可在同一事务内创建闭包，测试见 `tests/v2/storage/test_domain_schema.py:175-265`。

#### 3.2 当前仓储模式

- `AppendRepository` 负责追加写 canonical payload/hash、规范化列和有序 association，读取时校验 payload hash 和声明的镜像列，见 `app/storage/repositories.py:224-338`。
- `SOURCE_DOCUMENT_CONFIG`、`EVIDENCE_SPAN_CONFIG`、`SNAPSHOT_CONFIG` 已注册，见 `app/storage/repositories.py:842-904`。
- `SNAPSHOT_CONFIG` 会保存文档有序关联，并只调用 `_check_snapshot_scope`；后者当前只验证 snapshot.subject 等于 episode.subject，见 `app/storage/repositories.py:346-353`。
- `persist_fixture()` 已按依赖顺序保存文档、快照、span、fact 和 expectation，见 `app/storage/repositories.py:2992-3015`。
- association 顺序和重复 fixture 拒绝已有测试，见 `tests/v2/storage/test_repositories_roundtrip.py:246-269`。
- `EpisodeRepository` 允许更新 `evidence_snapshot_id` 并使用 revision 乐观锁，见 `app/storage/repositories.py:1668-1724`。

#### 3.3 持久化层的关键缺口

1. 文档内容与文档版本没有分层。

   - `SourceDocumentVersion` 没有 blob/storage ref、MIME、大小、页数、上传时间、逻辑文档 ID、前一版本或内部版本号。
   - 表上的 `sha256` 没有唯一约束，不能单独承担“同内容只保存/OCR 一次”的缓存身份。
   - 文档没有 subject/project FK；任意已登记文档理论上可被关联到任意 subject 的 snapshot，真实 snapshot 保存边界并未执行 fixture 的完整阶段隔离门禁。

2. 快照语义只实现了骨架。

   - 增量快照没有验证 prior 属于同 subject/episode、没有防循环、没有验证新集合是 prior 集合的去重超集。
   - 全量快照虽不继承 prior，但没有独立 upload/batch 审计记录指向替换前活动快照，因此 UI 预览和“旧快照关系”没有持久来源。
   - `source_document_version_ids` 在合同本身不拒绝重复；fixture gate 和 association 唯一约束会拒绝特定写法，但没有一个可复用的 SnapshotRepository 入口统一给出领域错误。

3. 关联表没有参与读取完整性校验。

   - `AppendRepository._decode()` 只校验 payload/hash 与声明镜像列，不读取/比对 association 行，见 `app/storage/repositories.py:317-338`。
   - 因此 `EvidenceSnapshot.payload_json.source_document_version_ids` 与 `evidence_snapshot_documents` 被外部损坏后，通用 `get()` 不能发现漂移。Phase 4 查询不能直接沿用该缺口。

4. span 的来源闭包只在完整 fixture/Gate 中成立。

   - `EvidenceSpanRecord` 只 FK 到 document，不绑定 snapshot、OCR page 或产生它的 accepted candidate。
   - `ClinicalFact` 仓储 scope 校验确认 fact 与 snapshot/episode 一致，但没有逐个确认 fact 的 span 来源属于该 snapshot，见 `app/storage/repositories.py:356-370`。
   - 这些约束在 `validate_fixture_scope()` 中存在，但真实上传/OCR API 尚不存在，不能依赖 fixture 验证替代服务/仓储边界。

5. OCR、校对与引用文件完全未持久化。

   - 没有 OCR 表、页级缓存键、原始 OCR、页图/layout、质量信号、页状态、attempt 或 correction 表。
   - 没有 `referenced_documents` / resolution 表。
   - 现有 `ReferencedDocument.provided` 是可变化状态，却被建模成 VersionedModel；若直接追加写会缺少“哪个新文件解决了哪个引用”的不可变转换历史。

6. 没有 V2 证据 API/服务。

   - `app/api/v2/app.py:112-116` 目前只注册 jobs 和 protocol 路由。
   - `app/services/` 只有方案和 Job 服务，没有 subject evidence ingestion、snapshot、OCR、correction 服务。

7. 现有测试是 Phase 2 骨架测试，不是 Phase 4 验收。

   - 已覆盖定位合同、快照 full/incremental 字段差异、fixture scope、association 顺序、幂等记录、迁移备份/恢复。
   - `tests/v2` 没有页级 OCR 缓存、模型/参数变化重跑、部分页失败恢复、校对不改原文、布局能力或证据 API 测试。

### 4. 现有 legacy OCR 可复用边界

现有 OCR 实现在 V2 目录之外，只能作为适配器内核和回归参考，不能继续作为业务真相：

- 全局 event-loop semaphore 已存在，默认并发 8，见 `app/pipeline/ocr.py:74-88` 和 `app/config.py:23-28`。
- 当前缓存按文档 stem + 页码文件命名，部分路径以 mtime 判断命中，见 `app/pipeline/ocr.py:94-102`、`app/pipeline/ocr.py:236-245`、`app/pipeline/ocr.py:347-367`；这与 Phase 4 内容哈希+模型/参数键不相容。
- 当前页结果主要是 `(page_num, markdown_text, method)`，见 `app/pipeline/ocr.py:222-245`；没有稳定 OCR profile、原始响应 hash、布局、页图 identity 或持久 attempt。
- PDF 页并发和部分页异常继续处理已存在，见 `app/pipeline/ocr.py:412-471`；批量聚合会把失败页记录在临时 `stats.errors`，见 `app/pipeline/ocr.py:536-607`，但没有 durable page state/checkpoint。
- `clear_cache()` 会物理删除现有 cache，见 `app/pipeline/ocr.py:661-670`；V2 的“重置 OCR”不能复用这个语义，必须创建新 OCR run/profile 并保留原结果。

适合的封装方式是定义 V2 `OcrAdapter` 输入/输出 DTO，让 legacy OCR 代码只负责“给定不可变文件页 + 明确 profile，返回页结果”；缓存身份、持久化、幂等、重试、审计和原文保护由 V2 workflow/storage 拥有。

### 5. Phase 4 建议切片

#### Slice 4.1：证据摄取合同与迁移 `0008`

建议新增而不是改写 `0002`：

- `SourceBlob` / `source_blobs`：内容地址对象，`sha256 UNIQUE`，size、MIME、storage ref、完整性状态、创建时间；真实文件写入 `data_v2/blobs/`，沿用 `WriteBoundary.atomic_write_bytes()`，见 `app/storage/boundaries.py:37-65`。
- `EvidenceUpload` / `evidence_uploads` 与 `evidence_upload_items`：记录 subject/episode、full/incremental、调用方幂等键、上传前活动 snapshot、预览决策、每项 hash/重复/新增/拒绝/分类状态和 Job ID。
- 为新写入的 `SourceDocumentVersion` 增加可查询 scope/身份：subject、blob、逻辑文档 ID、前一文档版本、内部版本号、上传时间、分类状态。若要兼容现有 fixture/v1 payload，采用新增可空列 + 新合同版本门禁，不能原地要求旧 payload 出现新必填字段。
- 不对 `source_document_versions.sha256` 直接做全局唯一；同一 blob 可以在不同受试者/阶段形成不同受控文档版本。全局去重落在 `source_blobs.sha256`，临床 scope 留在 document version。
- 新增 snapshot 领域仓储，原子实现 `create_full()` / `create_incremental()` / `activate_on_episode(expected_revision)`；同事务写快照、关联、上传审计、episode 新 revision 和 stale 原因。

该迁移应遵循当前 `0006` 的“新增迁移、不回写旧迁移、有数据时拒绝有损 downgrade”模式，见 `app/storage/migrations/versions/0006_phase3_slice4.py:1-20`、`app/storage/migrations/versions/0006_phase3_slice4.py:352-375`。迁移编排已自动备份、校验和失败恢复，见 `app/storage/migrate.py:171-242`。

#### Slice 4.2：OCR 运行与页级缓存迁移 `0009`

建议分成以下不可变实体：

- `OCRProfile`：adapter/engine、model ID/version、参数 canonical JSON/hash、预处理器/提示版本、布局能力声明。
- `OCRRun`：source document/blob、profile、Job/step、页集合、开始/结束、总体状态；重跑创建新 run，不覆盖旧 run。
- `OCRPage`：run、page number、cache key、page input hash、raw OCR text/hash、method、page image/blob ref、layout sidecar/hash、质量指标、定位能力、状态、错误分类、完成时间。
- `OCRAttempt`（可单独建表或作为 Job event + page attempt history）：attempt、依赖错误、可重试性、耗时；最终成功页与失败尝试可审计。

数据库唯一键至少应覆盖：

`(source_blob_sha256, page_number, ocr_profile_sha256, page_input_sha256)`

同键成功结果复用；同文件但模型/参数/预处理版本变化产生新 key；失败 attempt 不应占用“成功缓存”唯一结果。8 路限制留在执行适配器/worker admission，不应写成数据库业务状态。

#### Slice 4.3：定位、校对与引用文件迁移 `0010`

- 扩展 EvidenceSpan 新合同，使 span 绑定产生它的页面表示：至少 `ocr_page_id` 或原生 PDF page artifact ID、source text/page hash、evidence type、坐标系/页尺寸/旋转。没有布局输出时只允许 text range/excerpt/page only。
- `CorrectionRecord` 追加写：target kind/id、原值/原 hash、校对值、理由、确认人/时间、是否极性/数值/单位/日期关键变化、supersedes correction、受影响 scope。任何 correction 不更新 OCRPage.raw_text。
- `ReferencedDocument` 应拆成不可变“被引用但未提供的声明”和追加式 `ReferencedDocumentResolution`；resolution 指向真正上传的 SourceDocumentVersion。不要原地翻转一个 `provided` 布尔值而丢失历史。
- 对 EvidenceSpan 和 OCRPage 的 active corrected projection 可以重建，但不能反向作为原文真相。

#### Slice 4.4：领域仓储与应用服务

建议使用专用仓储接口，不把 Phase 4 写路径全部塞入通用 `AppendRepository`：

- `BlobRepository.get_or_create_by_sha256()`：同 hash 同内容复用；落盘后回读校验 hash；异内容不可能复用同 identity。
- `SourceDocumentRepository.create_version()` / `list_by_subject_stage()`：校验 blob、subject、stage、逻辑版本链和分类状态。
- `EvidenceSnapshotRepository.create_full/create_incremental/get/list_by_episode()`：写前验证闭包，读时对 payload、镜像列和 association 有序集合三方交叉校验。
- `OCRRepository.find_success_by_cache_key/start_run/append_page_result/record_attempt()`：缓存命中与运行历史分离。
- `CorrectionRepository.append/list_chain()` 和 `ReferencedDocumentRepository.append_resolution()`：只追加，不覆盖。
- `EvidenceIngestionService`：拥有一个短事务中的 upload/snapshot/episode/stale 可见状态变化；大文件 hash、页渲染和 OCR 在 Job step 外部计算，结果提交时再次核对 lease generation 和输入 hash。

现有 `EpisodeRepository.update()` 在更新 snapshot 时没有重新调用 `_check_episode_scope()`，见 `app/storage/repositories.py:1710-1724`；Phase 4 不应直接暴露该通用更新，而应通过 `activate_snapshot()` 检查 snapshot 属于同 subject/episode、expected revision 和当前活动 snapshot。

#### Slice 4.5：V2 API 与持久 Job

建议 API 只做协议转换，调用 service/workflow，不直接拼 ORM：

- `POST /api/v2/subjects/{subject_id}/evidence/uploads/preview`：上传到受控 staging/blob，返回 hash 去重、分类、页数/完整性和 full/incremental 预览；不创建临床结论。
- `POST /api/v2/subjects/{subject_id}/evidence/snapshots`：携带 `Idempotency-Key`、upload ID、mode、review episode、`expected_episode_revision`；创建/复用持久 Job。
- `GET /api/v2/review-episodes/{episode_id}/evidence-snapshots` 与 `GET .../{snapshot_id}`：返回快照历史、文档集合和处理状态。
- `GET /api/v2/source-documents/{document_version_id}/pages/{page_number}`：返回原始页、原 OCR、active correction 和真实定位能力，不返回本机绝对路径。
- `POST /api/v2/ocr-pages/{ocr_page_id}/corrections`：关键极性/数值/单位/日期变化必须带明确确认；同请求幂等。
- `POST /api/v2/referenced-documents/{id}/resolutions`：绑定新文档版本并触发保守影响范围重算。
- OCR Job 至少拆成 `fingerprint/classify -> inventory/render -> OCR pages -> quality gate -> snapshot activation/stale publication`；页级 checkpoint 允许只重试失败页，SSE 继续复用现有 `/api/v2/jobs/{job_id}/events`。

### 6. 必须保持的不变量

#### 6.1 不可变与来源真实性

1. 原始 blob、原 OCR 文本、页图/layout sidecar、EvidenceSnapshot、OCR 成功结果、CorrectionRecord、ReviewRun 都只追加，不原地覆盖或物理删除。
2. correction 只能形成派生视图；任何页面都能同时回到原文件页、原 OCR、校对链和实际采用的版本。
3. EvidenceSpan 必须绑定一个真实存在、属于当前 snapshot 文档集合的页面表示；不得凭 excerpt 反造 bbox。
4. `page_only` 必须有 degradation reason；布局能力不足必须显式降级。这一合同已经存在，不能在 OCR 接入时放松。
5. 文档内容 identity 只由字节 SHA-256 决定，不用文件名或 mtime；同名异内容必须是不同 blob/version，同内容改名不重复 OCR。
6. 后续阶段文件不能进入更早阶段 ReviewRun；新资料若要回顾早期阶段，必须新建 ReviewRun，旧 run 和旧 snapshot 保留。
7. 增量 snapshot 是 prior 的去重超集；全量 snapshot 是本次完整集合且不继承 prior。两者都必须是“本次审核可见的完整集合”，不能只存 delta。
8. prior snapshot 必须属于同 subject/episode，不能自引用或成环。
9. ReviewRun 固定 snapshot；episode 活动 snapshot 更新不得让旧 ReviewRun 读取新文档。
10. partial OCR 失败不得发布为完整成功；失败页相关 fact/assessment/projection 标记 stale 或阻断明确化。

#### 6.2 幂等与并发

1. 上传命令：同 scope + idempotency key + 同 canonical 请求 hash 返回同 upload/Job；同 key 异内容返回冲突。复用现有 `IdempotencyRepository` 语义，不自行实现“先查后插”。
2. blob：同 SHA-256 只保存一次物理内容，但文档版本按 subject/stage/metadata 独立；不能因全局 blob 去重串联两个受试者的临床 scope。
3. snapshot：同 upload outcome 只能生成一个 snapshot；重复回调不能再次切换 episode revision 或重复打开 stale。
4. OCR：同 blob/page/profile/page-input key 的成功结果只生成一次；并发 worker 只能有一个赢家，其他复用；模型、参数、预处理或页面输入变化必须产生新 key。
5. Job：步骤提交必须核对 lease owner/expiry/generation；失效 worker 的晚到 OCR 输出不得覆盖赢家或激活 snapshot。
6. correction/resolution：同命令同内容只追加一次；不同 correction 必须有新 ID/supersedes，不允许 overwrite。
7. episode 活动 snapshot 切换必须携带 expected revision；并发标签页冲突时不覆盖。
8. snapshot 文档 association、OCR page association 和 correction chain 在读取时必须与 payload/hash 交叉校验；不能只相信一侧。
9. 一个用户动作的可见状态变化应在一个事务内提交；文件大对象先以内容地址安全落盘，事务失败留下的未引用 blob 只能由独立可审计 GC 清理，不能误删已引用内容。
10. migration 继续使用当前备份/验证/自动恢复路径；新增正式数据后有损 downgrade 必须拒绝。

### 7. 最低测试切片

1. 合同：OCR profile/cache key、OCR page 成功/失败、correction 原值绑定、span 页面绑定、ReferencedDocument resolution、增量超集和 prior 防环。
2. 存储：blob SHA 并发去重、跨 subject 同 blob 不串 scope、association/payload 漂移拒绝、未来阶段文档拒绝、旧 snapshot/run 不变。
3. 迁移：`0007 -> 0008 -> 0009 -> 0010` 升降级/恢复；有正式 OCR/correction 数据时拒绝有损降级；`foreign_key_check` 与 metadata 一致。
4. Job：第 N 页失败只重试失败页；kill/restart 从页 checkpoint 恢复；失效 lease 晚到结果丢弃；浏览器断开不取消。
5. OCR：同文件重复上传不重复 OCR；模型/参数/预处理任一变化必重跑；原生 PDF word box 与 oMLX layout spike；否认/确认、小数点、单位和日期 gold pages。
6. API：full/incremental 显式模式、幂等键冲突、expected revision 冲突、快照历史、原 OCR 与校对并列、页面定位精度真实返回。

## Files Found

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` - V2 冻结产品决定、证据实体、定位阶梯、OCR/恢复/不覆盖原则。
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` - Phase 4 工作项、退出门槛和统一 OCR/故障注入验证矩阵。
- `.trellis/workflow.md` - Trellis 阶段与研究工作约定。
- `.trellis/spec/backend/database-guidelines.md` - SQLite/WAL、追加写、幂等、迁移和 payload/镜像校验规范。
- `.trellis/spec/backend/directory-structure.md` - V2 依赖方向和 API/service/domain/storage 边界。
- `.trellis/spec/backend/persistent-jobs.md` - durable Job、租约、checkpoint、重试和 SSE 约束。
- `.trellis/spec/backend/quality-guidelines.md` - EvidenceSpan、来源闭包、stale 与测试要求。
- `app/domain/contracts/evidence.py` - 当前 EvidenceSnapshot、SourceDocumentVersion、EvidenceSpan、Expectation、Fact 和最小 ReferencedDocument 合同。
- `app/domain/contracts/normalization.py` - Evidence Normalizer 的事实、span、事件、用药和引用文件候选合同。
- `app/domain/contracts/review.py` - ReviewEpisode、ReviewRun 和 fixture 证据闭包。
- `app/domain/contracts/enums.py` - UploadMode、LocatorPrecision、ReviewStage、GapType 稳定机器值。
- `app/domain/gates/scope.py` - 注册审核 scope、快照文件集合和未来阶段拒绝。
- `app/domain/gates/integrity.py` - fixture 级文档/span/快照完整性和 accepted candidate 闭包。
- `app/domain/gates/evidence.py` - Evidence Candidate 到 accepted GateResult 的来源闭包。
- `app/storage/models.py` - V2 ORM、证据表和 association 表。
- `app/storage/repositories.py` - 通用追加写仓储、scope 校验、Episode/Expectation 仓储和 fixture 播种。
- `app/storage/idempotency.py` - 通用幂等争抢与冲突语义。
- `app/storage/staleness.py` - stale 原因幂等打开和 ReviewRun 精确关闭。
- `app/storage/migrate.py` - 迁移锁、SQLite backup API、迁移后验证和失败自动恢复。
- `app/storage/migrations/versions/0002_domain_schema.py` - 当前证据骨架表的初始迁移。
- `app/storage/migrations/versions/0006_phase3_slice4.py` - 新增迁移和有数据时拒绝有损 downgrade 的可复用模式。
- `app/storage/migrations/versions/0007_job_user_wait.py` - 当前唯一 migration head。
- `app/api/v2/app.py` - 当前 V2 app 只挂载 Job 和方案 API，证据/OCR API 尚未存在。
- `app/pipeline/ocr.py` - legacy OCR 核心、8 路 semaphore、mtime/stem cache、页级临时结果与物理 clear cache。
- `tests/v2/test_contract_logic.py` - EvidenceSpan 和 EvidenceSnapshot 现有合同测试。
- `tests/v2/test_contract_artifacts.py` - fixture scope、重复 ID、快照集合和阶段隔离测试。
- `tests/v2/storage/test_domain_schema.py` - 表存在、FK/唯一约束及 episode/snapshot deferred cycle 测试。
- `tests/v2/storage/test_repositories_roundtrip.py` - payload 往返、association 顺序和跨 scope 反例。
- `tests/v2/storage/test_idempotency.py` - 同键复用、异内容冲突和真实并发唯一赢家。
- `tests/v2/storage/test_migrations.py` - 迁移备份、PRAGMA、schema 验证和失败恢复。
- `pyproject.toml` - 当前固定依赖：Alembic 1.19.1、FastAPI 0.128.8、Pydantic 2.13.3、SQLAlchemy 2.0.52、PyMuPDF 1.26.4（`pyproject.toml:5-23`）。

## Code Patterns

- 追加写实体：canonical payload + SHA-256 + 规范化检索列；见 `app/storage/models.py:1-10`、`app/storage/repositories.py:247-338`。
- 可变根：revision 乐观锁；见 `app/storage/models.py:47-62`、`app/storage/concurrency.py:97-177`。
- 有序多值关系：owner/ref/position 两个唯一约束；见 `app/storage/models.py:1342-1358`。
- 幂等争抢：SQLite `ON CONFLICT DO NOTHING ... RETURNING`，同 hash 复用；见 `app/storage/idempotency.py:102-164`。
- 迁移：每次迁移前 SQLite backup API + integrity/hash 清单，迁移后 schema/PRAGMA 验证，失败恢复；见 `app/storage/migrate.py:171-242`。
- 临床 scope：注册表中的不可变实体副本 + canonical hash 对比；见 `app/domain/registry.py:90-175`。

## External References

- 未进行外部检索。本题是当前仓库状态盘点，结论来自本地设计、计划、规范、代码和测试。
- 当前已固定的相关开源版本记录于 `pyproject.toml:5-23`；Phase 4 不需要为证据持久化另引入 ORM、迁移或 Job 框架。

## Related Specs

- `.trellis/spec/backend/database-guidelines.md`
- `.trellis/spec/backend/directory-structure.md`
- `.trellis/spec/backend/persistent-jobs.md`
- `.trellis/spec/backend/error-handling.md`
- `.trellis/spec/backend/quality-guidelines.md`
- `.trellis/spec/backend/logging-guidelines.md`

## Caveats / Not Found

1. 活跃任务目录 `.trellis/tasks/08-19-phase4-evidence-ocr-v2/` 在研究开始时没有 `prd.md`、`design.md` 或 `implement.md`；因此 Phase 4 计划采用 `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md:123-142`，总设计采用 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`。若主会话另有未落盘的 Phase 4 决定，本报告无法覆盖。
2. 本次为只读研究，没有运行迁移或测试，也没有检查真实 `data_v2` 数据库内容；“当前表”指 ORM + Alembic head 的代码定义，不代表某个本地数据库实例已升级到 `0007`。
3. 没有对 oMLX 做实时布局能力调用；总设计要求的 layout spike 仍是 Phase 4 实施前置实验，不能从 legacy OCR 的文本返回推断 bbox 能力。
4. 未读取或修改 legacy 临床项目数据；legacy OCR 仅做代码边界盘点。
5. 当前工作树存在与本研究无关的用户改动/未跟踪文件；本研究没有修改它们。
