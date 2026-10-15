All evidence gathered. The error-translation boundary maps every batch endpoint failure to stable Chinese envelopes. I have enough for the complete advisory report.

---

# Conference Output: r05-batch-ocr-review-20260915 - evidence_single_object

## Output

**Role**: `evidence_single_object`（重要证据审阅，只读核对批量重新识别的版本保留、幂等、取消恢复及前端衔接）
**Verdict**: 未发现 P0/P1 缺陷。版本保留、幂等、取消恢复与前端衔接四条主线在源码层核验通过（含会议上下文列举的全部五项“已修正”声明，均独立复核成立）。发现 1 项 P2 健壮性缺口（瞬态数据库忙被升级为终败）、若干 P3。本报告为建议性审阅，不构成运行时/临床/视觉验收。

### 一、核验通过项（证据 → 结论）

**1. 版本保留（不可变原件 + 不自动启用）**
- `app/services/evidence_reprocessing.py:186-191`：重识别执行器以 `manage_snapshot_status=False` 复用证据处理执行器；`app/services/evidence_processing_executor.py:330-331, 511-532` 证实快照状态迁移全部短路——ACTIVE 原快照状态不被重识别触碰。
- `evidence_processing_executor.py:2146-2147`：新冻结修订 `is_activatable=False`；启用只能走 `buildReviewableRevision` → `activateReviewableRevision`（`frontend/src/pages/EvidencePage.tsx:930-999`），且 `EvidencePage.tsx:937` 强制"构建基础=当前正在查看且一致性已验证的修订"。
- 原识别结果保留：子任务只新增修订，不删除/改写旧 base/complete 修订（`_freeze_revision` 为纯新增，`evidence_processing_executor.py:2151-2154` 幂等跳过已存在修订）。
- **纯文字 no-op 不产生新修订**（上下文声明，独立复核成立）：页产物 ID 确定性（`app/evidence/page_processor.py:175-205`，内容寻址，不含尝试命名空间）→ 原生文字页 profile 指纹不含 attempt_namespace（`evidence_processing_executor.py:1137-1148`）→ 缓存键命中复用同一 `ocr-page-source-*`（`:1178-1190`）→ 清单哈希一致 → `revision_id` 相同 → `reprocessing_view` 的 `new_revision=False`（`evidence_reprocessing.py:223`）。真 OCR 页则按 UUID 新页身份必然成新修订（`:1645`），符合“重新识别须真实重识别”。适配器 `for_attempt` 使跨尝试无页级缓存复用（`app/evidence/ocr_adapter.py:582-594, 616-626`），语义正确、代价为全量重推理。

**2. 幂等**
- 父批次：`app/services/batch_evidence_reprocessing.py:156-178` 在 `BEGIN IMMEDIATE` 内先建/查幂等父记录（幂等键含 `request_key`），再做新鲜度/冲突校验，失败随事务回滚（含幂等记录）——上下文声明成立。同键不同内容 → `IdempotencyConflict` → 409 信封（`app/storage/idempotency.py:116-125`；`evidence_app_errors.py:778-784`）。
- 子任务：`attempt_namespace` 由 `{contract, batch_job_id, member四元组}` 派生（`batch_evidence_reprocessing.py:181-182`），与单份提交命名空间（`evidence_reprocessing.py:150`）空间不相交；单份载荷序列化剥离 `batch_job_id` 保持旧哈希兼容（`evidence_reprocessing.py:52-58`）。`create_reprocessing_child_in_session:120-127` 对已存在子任务做全载荷等值复核，不等值即拒绝。
- 归属核验（上下文声明成立）：`owned_children`（`batch_evidence_reprocessing.py:66-99`）逐子任务核对 contract/project/batch_job_id/profile/派生命名空间，重复认领同成员即抛错。
- `BEGIN IMMEDIATE` 在 pinned SQLAlchemy 2.0.52 legacy pysqlite 模式下合法（方言文档 `sqlite/base.py:170,258-293` 证实默认不发显式 BEGIN；`enqueue_reprocessing_batch` 与既有 `evidence_api_command_service.py:229` 等同构且后者有既有测试链覆盖）。

**3. 取消与恢复**
- 取消传播：`change_reprocessing_batch("cancel")`（`:228-231`）请求父取消并取消可核实子任务；无法核实归属的成员在取消路径跳过保留（`:93-97`），不饿死其他成员的取消；续跑扫环（`:263-272`）逐批次 try/except，单批损坏不阻断其他批次——上下文检查点成立。
- 并发夹逼：子创建与父取消同受 SQLite 写锁串行——`_create_member_child` 在 `BEGIN IMMEDIATE` 内复核 `cancel_requested`（`:191-193`），任一先提交另一方即失败，无窗口。
- 恢复闭合：父步骤只在原子事务内 start+complete/fail，不会持久停留 running；崩溃后 `mark_expired_running`/`cancel_expired_cancel_requests`/`requeue_recovering`（`app/workflow/jobstore.py:1342-1424`）把 running/cancel_requested 收敛回 queued 或 cancelled，续跑由 `BatchReprocessingContinuation.__call__:258-283` 重扫（job_scope 含本 OWNER）。
- 父完成不遮蔽缺失子任务/检查点：`validate_completed_members`（`:102-117`）+ 视图每次读取都调用（`batch_evidence_reprocessing_view.py:65`），不一致即报错（fail-closed，非静默绿）。子级失败如实记入 `member_state` 检查点后继续下一成员（`:322-331`）。
- 父显式停止后拒绝子级重试（上下文声明成立）：`evidence_reprocessing.py:239-240`。批次级 retry 亦被 `cancel_requested` 永久拒绝（`batch_evidence_reprocessing.py:232-233`），与“已停止批次须重新发起”一致。
- 运行器不会误领父任务：`JobRunner.__init__` 将 claim 范围与已注册执行器类型取交集（`app/workflow/runner.py:112-113`），`batch_evidence_reprocess` 无执行器 → 仅续跑服务可认领。

**4. 前端衔接**
- 深链精确性（上下文声明成立）：`BatchOcrPanel.tsx:54` 传 `ocrSnapshot+ocrRevision`；`EvidencePage.tsx:288-308` 强制选中请求快照（优先于 active），`:337-357` 仅当修订属于该快照且一致时才展示内容/允许构建，否则 fail-closed 占位，不静默回退当前版本；`:1819-1823` 常驻横幅区分“正在查看新识别结果，尚未启用”。
- 当前 vs 记录双列（`BatchOcrPanel.tsx:51-55`）：`state` 为子任务当前态、`recordedState` 为批次收束记录，单独子级重试只改前者——与后端语义（`batch_evidence_reprocessing_view.py:5-7` 文档化）一致。
- 输入校验对称：1–50 成员、episode 去重、offset≤100000、PAGE_SIZE=20 翻页步长两侧一致；`reprocessingBatches.ts:12-18,33-45` 对服务端响应做严格白名单校验，畸形即整体拒显。
- 客户端幂等键：`BatchOcrPanel.tsx:73-82` 以成员有序指纹存取 localStorage request_key，网络中断重放同批次；成功后清除。
- 宽屏桌面：全部复用既有流式类（`reports-print__table`/`prepared-review`），无固定像素与移动变体；视觉验收按边界归 Codex。

### 二、发现（按严重度）

**P0/P1：无。**

**P2-1 瞬态数据库忙被升级为父步骤终败**（`batch_evidence_reprocessing.py:338-353`）
`_advance` 第二段提交事务是 deferred 读写事务；若 API 线程（取消/重试/新批次 intake）在其读快照后先行提交写锁，本事务升级将得到 BUSY/`database is locked`（busy_timeout 10s 后仍失败）。异常处理器不区分忙错误：非取消路径直接 `fail_step(retryable=False, CONTINUATION_FAILED_CODE)` → 父任务 `failed_final`。结果诚实且可经“重试未处理部分”恢复，但把瞬态竞争固化成需人工介入的终态；子任务执行器同类场景已映射为可重试（`evidence_reprocessing.py:180-185` 的 `is_database_busy_error` 先例）。
**最小修复建议**：在 `except` 分支中于 `step_id is not None` 前增加一类：`elif is_database_busy_error(exc) and step_id is not None: store.release_deferred(lease_ref[0])`（保持步骤 queued、父任务回队，交由下一维护轮重试；如担心忙振荡可加有限次退避）。同根因的 `change_reprocessing_batch`/`cancel_batch_children` deferred 升级暴露属 API 侧自然重试，维持 P3。

**P3（列出供 Codex 裁决，不阻塞）**
1. `validate_completed_members:106` 的 `steps[f"member_{index}"]` 与视图 `:74-79` 的仓储 `get`：行缺失/损坏时抛 KeyError/NotFound 未入翻译信封（500）。仅数据库级损坏可达；建议包成 `ScopeViolationError`。
2. `recent_reprocessing_batches`：`json_extract` 对非法 JSON 会直接报错（列表接口 500），与“损坏计入 unavailable_count”的哈希失效路径不一致；同为损坏级场景。
3. 批次父在子任务运行期间停留 `queued`，面板汇总显示“等待识别”而行内子任务为“正在识别”——如实但略含混；可在 UI 文案上区分“排队中”与“成员进行中”。
4. `failed_final` 批次一律显示“重试未处理部分”，包括 profile 已变更这类永久不可重试的失败（点击后才得到 409 文案）；可在前端读取 failure_detail 预判禁用。
5. `BatchOcrPanel` 依赖 `crypto.subtle`（需 secure context；桌面走环回端口满足，若未来换 file:// 打开会失败）。
6. 语义澄清（非缺陷）：批次级 retry 仅重试“子任务创建失败”的成员（其 attempt_namespace 稳定，重试幂等）；子级失败成员由受父停止守卫的子任务重试（jobs API → `ReprocessingRetryService`）救济。UI 文案“重试未处理部分”与此一致，建议在交付说明中向用户明示。

### 三、异议、决策点与有界问题（供 Codex）

1. **异议/建议（P2-1）**：如上，建议为续跑提交路径补忙错误分类。若 Codex 认为“终败+显式重试”即为设计意图（本地单用户、并发写者仅 API 线程、概率极低），可降级为已知限制并记录——请裁决。
2. **决策点**：P3-3 的批次状态文案是否值得本轮调整，或留给全量构建阶段的 UI 打磨。
3. **有界问题**：批量重识别的验收范围声明“不运行阶段测试或产品模型”——我据此未运行任何测试/应用/浏览器，静态证据链已闭合；若 Codex 需要，我可在同会话补做只读性质的测试文件清点（`tests/**` 中批量重识别覆盖面），但不执行。默认不做。

### 四、不确定性与未验证项（如实声明）

- **未运行任何**测试、应用、数据库、模型、浏览器（会议边界明确后置到全量构建）；本报告全部结论为源码静态核验。
- SQLAlchemy legacy 事务模式结论基于安装版 2.0.52 源码阅读 + 既有同构调用面的存在性证据，未做运行时探针（避免越界）。
- `EvidenceSnapshotRepository.current_status`、`OcrPageRepository` 缓存闭包校验等被依赖模块仅按调用契约与局部实现核对，未逐行全读。
- 视觉/宽屏/交互验收、真实 OCR 行为（含 no-op 复现在真实数据上的表现）均待 Codex 主场运行时验收。

**断点/续点**：本轮为完整有界审阅，无中断；若 Codex 就 P2-1 修复文本或 P3 清单需要同会话追问，可直接继续。

**证据与推论分离声明**：第一节所有"file:line"为直接源码证据；“语义正确/符合设计”的结论为推论，依据已在各条内注明；修复建议为建议，未经 Codex 采纳前不构成变更。
