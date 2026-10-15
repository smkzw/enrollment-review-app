全部证据链核查完毕，成稿。

# Conference Output: r05-ocr-reprocessing-design-20260915 - evidence_single_object（第二轮：实现源码复核）

## Output

复核范围：完整读了 `app/services/evidence_reprocessing.py`（197 行）、`app/api/v2/evidence_reprocessing.py`（36 行）；核对了 `ocr_adapter.py` 新增 attempt 字段/`for_attempt`/prepare 缓存路径、`fingerprint.py`、`contracts/ocr.py` OCRProfile、`ocr_repositories.py`（OCRProfileRepository/get_by_fingerprint）、执行器 `manage_snapshot_status` 与 `recover_evidence_ocr_runs`、`evidence_progress_service.py`、`app.py` 注册，以及下游 `evidence_sidecar_preparation.py`、`evidence_revision_workflow.py`、`evidence_revision_builder.py`、`evidence_activation_service.py`、`jobstore.retry_failed`。只读源码结论，未运行任何代码，不宣称运行/临床验收。

### P0/P1 真实问题

**P0-1　激活重识别结果后，后续增量上传对未变化成员会静默回退到原始 OCR 文本。**
- 触发情形：重识别完成 → 用户确认启用（指针切到新完整修订）→ 之后任何增量上传（或复用同资料版本的新上传任务）。继承成员的 `source_document_version_id` 不变 → 页产物同一 id → 上传执行器用**未命名空间**适配器（`app/api/v2/app.py:289-311`，upload 与 reprocess 共用 config，upload 拿到的是 namespace=None 的基础适配器）→ `_process_visual_page` 的 v2 缓存键（页产物 id + 未命名空间指纹）命中**最初识别**的成功页（`evidence_processing_executor.py:1355-1390`；键构造 `ocr_adapter.py:628-645`）→ 新快照的基础修订清单引用**旧 OCR 页**。
- 后果链：新快照完整修订闭包严格按其 base 修订的页聚合（`evidence_revision_builder.py:132-137`，校对再按 base 过滤 `:196`），因此用户已确认启用的新识别文本在后续所有修订中被旧文本静默替换；重识别 base 上做的校对（绑定新页 id/新 base）也不会进入后续闭包；sidecar 沿用因 flag/页 id 不匹配同样不携带（`evidence_sidecar_preparation.py:128`、`:157`）。这与“确认启用”的产品语义直接矛盾。
- 最小修正方向（需所有者定夺）：(a) 执行器层“活动真值优先”复用——凡页产物出现在当前活动指针所指 base 修订清单中，优先复用该清单的 OCR 页（仿 `_commit_content_reuse` 的“复制为本键自有新行”模式，`evidence_processing_executor.py:1735-1774`）；或 (b) 激活事务内物化——`activate` 时把被启用页以未命名空间键落为新成功行，语义即“启用=接受该文本为当前识别”。两者都需显式规则文字，因为都 intentionally 把已接受文本发布进共享命名空间。

**P1-2　重识别执行器验证段把一切异常折叠为不可重试失败。**
- `evidence_reprocessing.py:129-131`：`except Exception` 一律转 `StepFailure(retryable=False)`。触发：`_source` 读库时遇 SQLite busy/锁超时等瞬时错误 → 任务直接 failed_final。代价：自动重试预算被浪费（人工重试可用且同命名空间缓存保留，故降为 P1 而非 P0）。
- 最小修正：仅把身份类错误（`ReprocessingError`、`RepositoryError/InvalidReferenceError`、`PersistedContractInvalid`）判不可重试；瞬时异常抛 `StepFailure(retryable=True)` 或原样上抛交 runner 分类。

**P1-3　`ReprocessingRetryService.retry` 不复核资料新鲜度。**
- `evidence_reprocessing.py:177-197` 只查任务类型、指纹与互斥；执行时验证（`:121-128`）也只核作用域/身份/collection/manifest，不核活动指针与快照状态。触发：失败与重试之间源快照被取代（新增量激活或另一次重识别启用）→ 重试对过期材料全额推理并冻结一个孤儿基础修订（历史无害，但费用与意图错位）。
- 最小修正：在 retry 中复用 enqueue 的新鲜度检查（`:90-94`），或在执行器验证段加指针/状态核对。

**P2（记录，不阻塞）**：① 取消的任务不可续跑（`jobstore.retry_failed:1231` 只收失败态），其已成功命名空间页不被任何后续尝试复用——符合所有者“取消不复用”语义，但用户取消后重发起要全额重付；`resume_cancelled`（`jobstore.py:1261+`）已存在，可作为后续可选的受控续跑入口。② `evidence_progress_service.py:199-201` 对每个指纹调 `get_by_fingerprint`，该方法在档案行缺失时抛 `InvalidReferenceError`（`ocr_repositories.py:240-245`）——档案与页同事务创建，不变量应成立，但任何历史数据洞会使上传进度读取整体失败，建议容忍缺失行（视为排除）而非抛错。③ enqueue 回放分支（`:81-88`）对任意终态任务都返回原 Job（含 cancelled/failed_final），依赖前端据 state 引导用新 request_key 重发起——语义可接受，需前端配合，此处仅记录。

### 专项核对结果（所有者声明逐条验证）

1. **pydantic 旧哈希保持：成立。** 合同 `attempt_namespace` 默认 None 且序列化时 pop 掉（`contracts/ocr.py:147-155`）；指纹载荷仅在非 None 时加入键（`fingerprint.py:42-46`），与合同校验器一致（`ocr.py:175-178`）；旧载荷缺键按 None 解码、None 再编码字节不变；`_verify_same_profile` 已比对命名空间（`ocr_repositories.py:261`）；未加数据库列，进度分流经 `get_by_fingerprint` 实现且不依赖列。无既有指纹失效风险。
2. **get/checkpoint/result 来源：成立。** `reprocessing_view` 的 revision_id 只取本任务 `evidence_processing` 步的 checkpoint（`:152-158`），并强校验 checkpoint 携带本命名空间/合同/activated=False，再回查修订归属快照（`:161-164`）；`new_revision` 与 previous_base 如实区分“纯原生文本无新结果”情形。
3. **取消/恢复独立：成立。** `manage_snapshot_status=False`（`evidence_processing_executor.py:212`）门控了启动（`:329`）、成功（`:457` 经 `:508` 门）、失败与顶层异常（`:287-301` 经同一门）四条快照状态写路径；恢复侧 `_recover_terminal_snapshot` 类型门（`:2030`）挡住快照投影，终态扫描已含 `"evidence_reprocess"` 但仅做运行收敛（`:1994-2003`）；取消回调链（`app.py:198-215`）对两类任务一致且不误伤快照。
4. **同参数真实新推理 + 本尝试成功页复用：成立。** 首次执行命名空间指纹进 v2 键与内容级复用查询（`ocr_repositories.py:878-891` 按指纹过滤）→ 两层皆未命中 → 经共享门禁真实推理（注册处 `app.py:289-312` 两个执行器共用同一 gate/inference/adapter 基座，`for_attempt` 完整复制全部构造参数且正确地不复制 `profile_id`，`ocr_adapter.py:616-626`）；重试同任务 payload → 同命名空间 → v2 命中免推理（`evidence_processing_executor.py:1388-1390`）。
5. **进度不串历史：成立。** 重识别分支只取本任务 events/runs（`evidence_progress_service.py:268`、`:300`、`:317-326`）；上传滚动统计先按“档案命名空间为 None”过滤（`:199-202`），旧上传进度不含重识别页。遗留风险见 P2②。
6. **命名空间取 project+request_key 哈希、不取修订计数：接受。** 失败未形成修订时计数确实会重复/漂移；现方案由 payload 全等拒绝跨资料复用（`:86-87`），request_key 唯一性责任在前端/调用方——记录为约定而非缺陷。
7. **sidecar 对“同原件新 OCR”的继承：无错误继承。** 对当前活动快照重识别时，沿用路径被“活动指针==快照自身≠prior”守卫直接跳过（`evidence_sidecar_preparation.py:102-112`）；即便守卫放行（READY 扩展场景），沿用也因 flag id/页 id 不匹配而空转（`:128`、`:157`）。新 OCR 页获得全新风险扫描/定位（`scan_page_in_session` 幂等、scan_id 逐页新派生，`evidence_risk_service.py:133-164`）。
8. **修订/激活链同快照不同 base：成立且历史保持。** 闭包严格绑定候选的 base 修订（`evidence_revision_builder.py:132-137`、校对 `:196`）；构建对 ACTIVE/READY 快照不写快照状态（`evidence_revision_workflow.py:506-522`）；激活对已 ACTIVE 快照不重复转换终态、成对指针切换且支持回滚（`evidence_activation_service.py:509-553`、`:223-226`、`:324-440`）。基础修订仍 `is_activatable=False`（`evidence_processing_executor.py` `_freeze_revision` 未改）。

### 上轮报告更正

**“崩溃后重试不会重复付费”不成立，予以撤回。** 推理在事务外进行（阶段 b，`evidence_processing_executor.py:1400-1613`），成功页在阶段 c 的提交事务内落库（`:1602-1613`/`_commit_ocr_success:1649-1706`）；推理返回后、提交落库前崩溃（或租约丢失触发 `_append_rejected_late:1856+`）该页结果即丢失，重试会重新推理、重复计费。缓存只保证“已提交成功的页”不重复付费。

### 关于 ACTIVE 限制能否安全扩展（应询给出精确状态依据）

可安全扩展到 **READY**（“原处理已终态且有基础修订”中唯一可行的态），依据：
- READY 快照必有完整修订：该状态只能经 `all_gates_passed` 进入（`evidence_repositories.py:115`），而该事件仅在冻结完整修订后追加（`evidence_revision_workflow.py:493-517`）→ `_source` 的 complete 要求可满足。
- 构建路径接受 READY 且不写状态（`evidence_revision_workflow.py:506-522`）；激活时首次发布 READY→ACTIVE 在激活事务内原子完成（`evidence_activation_service.py:509-553`，`:514-520` 只拒非 READY/ACTIVE）。
- 其余非 ACTIVE 态不可行：NEEDS_ATTENTION/RETRYABLE_FAILURE/TERMINAL_FAILURE/CANCELLED 构建即抛错（`evidence_revision_workflow.py:518-522`），且前两者出现于任何完整修订冻结之前、无 complete 可引用，`_source` 天然排除。
- 需要的资格改动（`evidence_reprocessing.py:90-94`）：接受「指针对==(snapshot, complete) 且 ACTIVE」**或**「快照 READY 且 `episode.active_evidence_snapshot_id in (None, snapshot_id)`」——指针守卫防止后续快照已激活时复活被取代材料。若采纳，P1-3 的重试新鲜度复核变得更重要。

### 边界

未运行应用/测试/数据库；前端接线、批量编排、新旧对照视图未在本轮范围（所有者已声明待实现）；`page_processor` 内部实现沿用上轮推断级结论。P0-1 的判定基于静态调用链，建议所有者以一次真实数据路径复核确认后再定修正方向。
