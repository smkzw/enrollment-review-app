# Conference Output: r05-ocr-reprocessing-design-20260915 - evidence_single_object

## Output

角色：`evidence_single_object`（重要证据审阅，只读源码设计审阅）。本报告全部结论来自本会话对工作区内源码的只读核查（仅用读取/检索命令，未运行产品、测试、数据库、模型、浏览器，未写任何文件，未外部检索，未扫描 artifacts 真实病例或主 checkout）。证据/推断/建议/不确定分别标注；不宣称临床或验收结论，最终采信归 Codex。

### 0. 结论摘要（TL;DR）

1. **“同一冻结原件集合创建新识别尝试”在现有代码中三重锁死，且都不是 bug 而是既有防篡改设计**：上传对相同成员集合 no-op（`app/services/evidence_upload_service.py:970-1002`，ACTIVE 属于 no-op 匹配态 `app/storage/evidence_repositories.py:149-158`）；快照状态机无任何路径让终态快照回到 PROCESSING（`evidence_repositories.py:104-133`、终态冻结 `:1558-1561`）；执行器只接受 staged/processing/retryable_failure（`app/services/evidence_processing_executor.py:466-494`）。**因此正确方向不是“复用旧快照状态”，而是新建一个不触碰快照状态的重识别任务类型 + 独立命名空间的识别缓存身份，最终产物挂到“同一快照的新基础修订”上**。修订表天然支持同快照多修订（`app/storage/ocr_models.py:301-359`，快照 ID 仅普通索引非唯一）。
2. **“换 job 仍拿旧 OCR”的精确机理已定位**：v2 页级缓存键与内容级复用查询都以 `ocr_profile_sha256` 为前提（`app/evidence/fingerprint.py:45-71`；`app/storage/ocr_repositories.py:878-891` 六列等值查询）。同配置新建任务会先命中 v2 键（`evidence_processing_executor.py:1388-1390`）、未命中也命中内容级复用（`:1403-1413`），两层都不会真实推理。**最小解法是把“重识别尝试命名空间”并入识别配置指纹**（条件包含，None 时不进哈希），两层缓存与内容级复用自动同域隔离；页图/原生文本复用不需要任何改动（页产物按确定性身份 get_or_create 去重；原生文本页 id 确定性复用）。
3. **“基础修订→风险/定位→完整修订→用户确认启用”链的下游全部是现有真接口**：构建排队 `POST /api/v2/evidence-processing-revisions/build`（`app/api/v2/evidence_processing.py:660-702`）、候选工作流对 ACTIVE 快照不改状态直接放行（`app/services/evidence_revision_workflow.py:506-522`）、同一 ACTIVE 快照切换到新完整修订并支持回滚是现有激活服务的既定行为（`app/services/evidence_activation_service.py:509-553`、回滚 `:324-440`）。**唯一整段缺失的是最上游：创建新识别尝试并产出新基础修订的入口**，以及批量编排与新旧识别对比视图。

### 1. 问题一：同一冻结原件集合创建新识别尝试，如何与 JobExecutor/取消恢复适配

**证据（确定）**：

- 上传确认对同集合快照 no-op 且不建新 Job：`evidence_upload_service.py:970-1002`（`find_by_collection` 命中→duplicate commit、`job_id=None`）；FULL 模式同内容文件分类 `EXPECTED_REPROCESSING` 但成员仍指向既有版本（`:631-637`、`:1283-1288`），集合哈希不变→必 no-op。并发第二创建也被集合幂等主张拦下（`evidence_repositories.py:1309-1355`，主张仅在快照终态时释放 `:1607-1613`）。
- 快照状态机：STAGED→PROCESSING→…→READY→ACTIVE，ACTIVE/READY 等终态禁止再跳转（`evidence_repositories.py:104-133`、`:1558-1561`）；READY→ACTIVE 只能由激活事务完成（`:1562-1568`）。
- 执行器入口三重门：已完成 Job 的 checkpoint 直接短路（`evidence_processing_executor.py:272-273`）；`_start_or_resume_snapshot` 状态门（`:466-494`）；执行器各失败路径会把状态投影写回快照（`_record_snapshot_failure :521-546`、成功后 `checkpoint_success :456-462`、顶层异常 `:293-301`）。
- 启动/取消恢复的快照投影按 Job 类型门控：`_recover_terminal_snapshot` 只处理 `EVIDENCE_PROCESSING_JOB_TYPE`（`evidence_processing_executor.py:2024-2026`）；取消回调对任何取消 Job 调 `recover_evidence_ocr_runs(cancelled_job_ids=[job_id])`，其中 OCRRun 收敛循环不分类型、快照投影被类型门挡住（`:1965-1976`；`app/api/v2/app.py:198-215`）；孤儿 RUNNING 运行兜底收敛不分类型（`app/storage/ocr_repositories.py:1201-1255`）。
- 执行器装配在 bootstrap 按 Job 类型注册（`app/api/v2/app.py:286-330`），适配器默认 `TextOnlyOcrAdapter()`（`evidence_processing_executor.py:268`）。

**最小方案（建议，P0）**：

1. 新增 Job 类型（如 `evidence_reprocess`）+ 独立执行器包装：复用 `_execute` 主体，增加 `mode="reprocess"` 参数——跳过 `_start_or_resume_snapshot`、跳过 `:456-462` 的成功状态投影、`_record_snapshot_failure`/顶层异常分支不写快照状态；其余（页池调度、租约、门禁、sidecar 准备 `:424-438`、选择性视觉入队 `:439-455`、`_freeze_revision`）原样复用。`_freeze_revision`（`:2068-2133`）对同一快照天然产出新 revision_id（manifest 哈希含新 OCRPage id）。
2. 源快照资格限制为 **ACTIVE**（推断级别：由状态机保证 ACTIVE 为终态，重识别任务对它的任何状态投影都必然 no-op，可彻底消除“重识别任务误伤同快照在途候选”这一并发隐患；见缺陷 D4）。创建时校验：快照 ACTIVE、存在既有基础修订、同快照无在途重识别 Job（互斥检查，防重复烧钱）。
3. 取消/恢复适配：沿用现有页边界取消（`_maybe_cancel`）；新类型被取消时，`project_cancelled_evidence_job`→`recover_evidence_ocr_runs` 的 run 收敛已类型无关、快照投影被 `:2024-2026` 类型门天然挡住——**该类型门必须保留，不可顺手“泛化”**（缺陷 D6）。启动终态扫描 `:1992-1997` 目前只扫旧类型，需把新类型加入扫描以获得 CANCELLED/FAILED 的准确区分，但快照投影继续按类型跳过（缺陷 D5）。
4. 每次尝试的持久身份：任务 payload 冻结 `{snapshot_id, attempt_namespace, 成员版本清单, 基线活动修订 id, 创建幂等键}`；JobRunner 租约恢复/重试复用同一 payload→同一命名空间→成功页经不可变缓存去重跳过，天然满足“限定重试取消恢复”。

### 2. 问题二：原件/原生文本复用与视觉 OCR 独立可重试缓存身份

**证据（确定）**：

- 页产物（页图/原生文本/坐标）身份是确定性的（`fingerprint.py:111-138`），执行器渲染后 `persist=repo.get_or_create`（`evidence_processing_executor.py:1048-1058`）——同一来源版本重跑必然复用既有页产物行与页图工件，不产生第二份存储（推断级别：`_build_page_artifact_detailed` 内部按身份哈希 get_or_create 的模式已从调用侧核实，其完整实现未逐行读，见“未核实项”）。
- 原生文本页走 `_get_or_create_source_text_page`（`:1067-1198`），页 id 由未命名空间的缓存键确定性导出——**只要命名空间只作用于视觉 OCR 配置指纹，原生文本页自动跨尝试复用同一行**，符合“原生文本允许复用”。
- 视觉 OCR 两层缓存：v2 键含 `page_artifact_id + ocr_profile_sha256 + page_input_sha256 + 布局/坐标版本`（`fingerprint.py:45-71`）；内容级复用按六列等值查询、不含页产物绑定（`ocr_repositories.py:878-891`），两层都以识别配置指纹为前提。
- 页工作租约与 `commit_guard` 都以 `cache_key` 为工作项身份（`evidence_processing_executor.py:1391-1396`、`:1664-1675`），键随指纹自动命名空间化，无需单独改。
- 档案为列+payload 双写（`ocr_models.py:51-73`；get_or_create 与 `_verify_same_profile` `ocr_repositories.py:240-320`）。

**最小方案（建议，P0，含两个实现路线取舍）**：

- 推荐：`OCRProfile` 合同新增可选字段 `attempt_namespace`（默认 None）。`build_profile_fingerprint` **仅当字段非 None 才加入哈希载荷**（`fingerprint.py:14-42` 处）——这是硬约束：无条件加键会使**全部既有档案指纹与页缓存键瞬间失效**，在途任务恢复全部重新推理、旧成功缓存全部孤儿化（缺陷 D2）。存储加可空列（或首版仅入 payload_json，符合“列用于检索、payload 为真源”的既有约定，`ocr_models.py:24-26`）；`_verify_same_profile` 比对补该字段。命名空间进入指纹后：v2 键、内容级复用查询、页租约、commit_guard 重算键全部自动同域隔离，**“不污染其他任务”由既有身份校验纵深（`cached_page`/`reusable_page` 的 `OcrCacheIdentityError` 防线，`app/evidence/ocr_adapter.py:631-706`）兜底**。
- 替代最小路线（若想避开迁移）：把命名空间并入 `request_params_sha256` 的哈希载荷（`ocr_adapter.py:574-579`）。无合同/DDL 变更、隔离效果等同；代价是语义略宽（命名空间不是 provider 请求参数），且原始请求工件不含该字段（请求工件按内容寻址去重，跨尝试复用同一请求工件反而省存储，是优点）。Codex 可二选一；我推荐显式字段（身份诚实、可检索）。
- 命名空间取值：确定性 `reprocess/{snapshot_id}/{n}`，`n` 在创建事务（SQLite 写保留锁，参照 `evidence_revision_workflow._begin_write` 的 `BEGIN IMMEDIATE` 模式）内取“该快照既有基础修订数+1”，随任务 payload 持久化——保证同一次尝试的重试/恢复复用同一命名空间（可重试复用），不同尝试互不命中（真重识别）。全局并发峰值仍由共享 oMLX 门禁限制（`evidence_processing_executor.py:130-138` 注释），命名空间不新增并发通道，不违反“不增加队列”。

### 3. 问题三：基础修订→风险/定位→完整修订→用户确认启用链——真接口与缺失

**现有真接口（确定，均已核对实现）**：

| 环节 | 接口/实现 | 位置 |
|---|---|---|
| 基础修订冻结（不可激活） | `_freeze_revision`，`is_activatable=False` | `evidence_processing_executor.py:2068-2133` |
| 风险提示/定位旁路准备（幂等） | `EvidenceSidecarPreparationService.prepare` | 执行器 `:424-438`；`app/services/evidence_sidecar_preparation.py:62-80` |
| 选择性视觉后处理入队（幂等） | `enqueue_selective_vision_postprocess_for_revision` | 执行器 `:439-455` |
| 完整修订构建排队 | `POST /evidence-processing-revisions/build`→`EvidenceApiCommandService.build_revision`→命令事务内冻结 attempt manifest + 建候选 + `evidence_revision_build` Job | `evidence_processing.py:660-702`；`app/services/evidence_api_command_service.py:480-541` |
| 构建（扫描→闭包→门禁→READY） | `EvidenceRevisionWorkflow.run_build`；**对 ACTIVE 快照不写状态直接放行** | `evidence_revision_workflow.py:278-306`、`:506-522` |
| 需核对处置与恢复 | 风险复核/校正/逐页复核端点 + `resume_after_attention_in_session` | `evidence_processing.py:477-621`；`evidence_api_command_service.py:631` |
| 用户确认启用（同快照切新修订） | `POST /activate`→`EvidenceActivationService.activate`；已 ACTIVE 快照不重复转换终态 | `evidence_processing.py:821-861`；`evidence_activation_service.py:509-553`、成对指针切换 `:217-276` |
| 回滚到旧修订 | `POST /rollback`（目标对须曾在激活事件出现） | `evidence_activation_service.py:324-440` |
| 任务取消/重试/进度 | `POST /jobs/{id}/cancel`、`/retry`、SSE 事件回放 | `app/api/v2/jobs.py:148-171`、`:174+` |

**缺失（需新建）**：① 重识别触发入口（创建尝试 + 新基础修订，问题一/二方案）；② 尝试实体与在途互斥；③ 批量编排（问题四）；④ 新旧识别文本对比视图（激活确认前的差异预览；未检索到现成接口，属设计建议）；⑤ 耗时/费用估算（Phase7 条目 7 的一部分；历史逐页耗时在 `ocr_attempts`/`ocr_pages` 时间戳中可得，可先做区间估计——设计建议）。

**要点**：激活链对“同一快照第二次启用新修订”没有任何隐藏障碍——候选 `expected_revision` 校验、并发败者 `REVISION_CONFLICT`、回滚、历史激活事件链全部现成；新尝试产出未启用的基础修订保持 READY 且永不可激活，与“新处理基础修订不自动启用、不覆盖旧报告事实”一致（`ocr_models.py:301-306` 注释即此语义）。

### 4. 问题四：批量调度复用既有 batch 服务而非复制

**证据（确定）**：`app/services/batch_review_workflow.py` 全文 268 行，模式为：冻结成员（上下文哈希）→ 父批 Job（每成员一个 step，`depends_on` 串行）→ 每步创建/关联子 Job 并等子 Job 终态→步完成；取消传播到可核实归属的子 Job（`:71-103`、`:97-103`）；续跑器复用 `recover_expired_jobs` + `JobStore.claim_job`（`:164-268`）；成员启动前重验冻结哈希防“批内资料漂移”（`:37-46`、`:213-216`）。

**建议（P2）**：其冻结/校验逻辑是审核域专用的（`require_prepared_review_intent`、routes/task_versions），**不可直接 import 复用**；但该文件短小、纯 JobStore/JobService 原语。推荐新建薄模块（估 150 行左右）复刻同一模式而非抽象公共层：成员=（episode, snapshot_id, 冻结的 collection_sha256 与基线活动修订 id），成员启动前重验活动指针未被替换；子 Job 即问题一的重识别 Job；取消按可核实归属传播。**不建议在本轮顺手重构 `batch_review_workflow.py` 做泛化**——它刚经过 C03 三次源码审阅修正，属受保护合同面；泛化是另一项任务。此为我的主动异议点之一：任何“抽公共批量基类”的诱惑都应推迟到第二条批量链存在之后。

### 5. 问题五：最小输入/版本、错误恢复、历史不变检查与中文操作流程

**每次尝试的最小冻结输入（建议）**：snapshot_id（须 ACTIVE）+ 成员版本清单与 `collection_sha256` 复核 + 基线 `active_evidence_processing_revision_id`（事后差异定位用）+ `attempt_namespace` + 识别配置指纹（含命名空间）+ `expected_revision`（episode 当前修订号，激活时再验）+ 创建幂等键 + created_by/at。

**错误恢复（既有语义直接继承）**：页级——同命名空间内成功页不可变缓存去重跳过、只重试失败页；任务级——`StepFailure` 可重试自动重试 3 次（`evidence_processing_executor.py:127-128`）→ failed_final → `POST /jobs/{id}/retry` 人工重试（复用成功页）；进程级——页租约 TTL + 心跳 + 启动恢复，孤儿 RUNNING 收敛类型无关（`ocr_repositories.py:1201-1255`）；取消——页边界安全取消，不触碰快照状态（类型门保证）。崩溃后重试不会重复付费（缓存命中路径不占门禁，`evidence_processing_executor.py:1388-1390`）。

**历史不变的来源检查（既有机制，无需新增）**：原件——SourceBlob/SourceDocumentVersion 内容寻址不可变 + 快照成员镜像/集合哈希交叉校验（`evidence_repositories.py:894-933`、`:1139-1150`）；旧识别——OCRPage 追加写 + 同缓存键单成功唯一约束（`ocr_repositories.py:958-969`）+ `commit_guard` 晚到拒绝；旧报告/事实——激活事件链与回滚、报告读取冻结 ReviewRun（设计 §17.6，`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md:409-427`）；新尝试永不写旧 ID（全部新行追加）。

**中文操作流程（建议稿）**：① 项目资料总览选择受试者/节点（1–50）→“批量重新识别”入口，页面前置说明：原件不变、旧识别与历史报告保留、新识别需人工确认后才启用、显示预计页数；② 提交前系统核对活动资料指针、成员清单指纹、无在途重识别任务；③ 后台逐个执行，页级进度“已处理第 X 页，共 Y 页”（复用现有 `page_progress` 事件与 SSE 回放），可取消、可断线重连；④ 每个成员完成后生成新基础修订并自动准备风险提示与原文定位，有阻断风险则进入“待核对”，人工处置入口与现有工作台一致；⑤ 用户核对（新旧识别对比视图待建）后逐个构建完整修订；⑥ 用户确认启用→活动指针切到新修订，可回滚；历史报告与旧识别全部保留可回放；⑦ 未启用的尝试保留为不可激活修订。

### 6. 缺陷清单（确定代码缺陷/陷阱 vs 设计建议，含优先级）

**确定（代码层面可指认）**：

- **D1（P0，缺失而非 bug）**：现有代码不存在任何为既有快照产生第二基础修订的路径（三重锁死见 §1）。批量 OCR 重置（Phase7 条目 4、恢复计划 T5 明记“批量OCR新修订…仍待实现”，`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md:113`）整段待建。
- **D2（P0，实现陷阱）**：向 `build_profile_fingerprint` 载荷无条件新增字段将使全部既有档案指纹/缓存键失效（`fingerprint.py:14-42` 的 `canonical_hash` 对载荷敏感），造成在途任务恢复期全量重推理与旧缓存孤儿化。必须条件包含（None 不进哈希）并写入稳定性注释。
- **D3（P0，机理确认）**：命名空间若只进 `cache_key` 不进识别配置指纹，内容级复用查询（`ocr_repositories.py:878-891`）仍会命中旧成功页（`ocr_adapter.py:669-706`），“换 job 拿旧 OCR”照旧发生。命名空间必须进入指纹。
- **D4（P1，并发隐患）**：重识别执行器若复用现有快照状态投影（`evidence_processing_executor.py:285-301`、`:456-462`、`:521-546`）且允许源快照为 STAGED/RETRYABLE，则原任务 retry→PROCESSING 期间重识别任务失败会经 `_transition_snapshot_if_processing` 把该快照误写成 TERMINAL_FAILURE。限制源快照为 ACTIVE（终态，投影必然 no-op）+ 重识别模式显式跳过快照状态写入，双保险消除。
- **D5（P1，小缺陷）**：启动终态扫描只认 `EVIDENCE_PROCESSING_JOB_TYPE`（`:1992-1997`），新类型任务的 OCRRun 只能靠孤儿兜底收敛为 FAILED，丢失 CANCELLED 区分；需把新类型加入扫描列表但快照投影继续跳过。
- **D6（P1，防回归约束）**：`_recover_terminal_snapshot` 的类型门（`:2024-2026`）是防止取消投影误伤快照的唯一屏障，实现时不得移除或泛化。

**设计建议（非缺陷）**：S1 尝试实体+确定性命名空间（§2）；S2 档案显式字段 vs 并入 `request_params_sha256`（§2，二选一，推荐前者）；S3 源快照限 ACTIVE + 每快照单在途尝试互斥；S4 纯原生文本快照重识别可能产出与旧版完全相同的 manifest→`_freeze_revision` 幂等返回旧 revision_id（`:2130-2132`）——须如实呈现“本次无新识别结果”，不得伪装新修订；S5 批量新薄模块、不动已审阅的 `batch_review_workflow.py`（§4）；S6 新旧识别对比视图与耗时/费用估算为独立后续项。

### 7. 最重要异议 / 给 Codex 的有界问题

1. **主动异议（对题设前提）**：“复用现有任务与缓存”在视觉 OCR 层面天然矛盾——真正重识别必然绕过（而非复用）既有推理缓存；能复用的只有页图/原生文本产物、执行器机制与下游修订链。方案已按此拆分，请 Codex 确认接受“新命名空间=新推理付费”这一成本语义。
2. **有界问题 Q-A（影响 D2/S2 路线）**：首版重识别是否固定为当前部署识别配置（同 prompt/参数，仅命名空间不同），还是允许用户选择新配置？安全临时路径：首版固定当前配置+命名空间；若允许选配置，指纹自然变化，命名空间仍需保留（区分“同配置重试”与“新配置”）。
3. **有界问题 Q-B（影响 D4）**：是否接受“源快照限 ACTIVE”作为首版权限？（READY 未激活快照的重识别场景建议等真实需求出现再加。）
4. **有界问题 Q-C（影响范围）**：批量“整批确认启用”是否首版就需要？现有激活是逐候选命令；整批激活需新增循环调用+失败中断策略，建议首版逐个确认。

### 8. 未核实项与证据边界

- `app/evidence/page_processor.py` 的 `_build_page_artifact_detailed` 完整实现未逐行读（页产物复用结论基于 get_or_create 调用侧与身份哈希函数 `fingerprint.py:111-138`，推断级别）；`evidence_revision_builder.py` 仅结构核对（build/gather_closure 按显式 id 驱动、无“单基础修订/快照”假设的迹象，推断级别）。
- 前端接线、真实运行时行为、迁移影响（若选可空列方案）均未验证——本任务为只读源码审阅，未运行任何代码；所有“可用”判断是接口存在性与调用链层面的判断，不构成运行验收。
- 未读 `app/workflow/jobstore.py`/`runner.py` 全文，Job 取消/重试语义取自 `batch_review_workflow.py` 与 `jobs.py` 的调用侧证据。
