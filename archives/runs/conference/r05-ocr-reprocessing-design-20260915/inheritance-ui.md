复核完成，成稿。

# Conference Output: r05-ocr-reprocessing-design-20260915 - evidence_single_object（第三轮：确认识别继承与前端接线复核）

## Output

复核范围：完整读了 `app/services/confirmed_ocr_inheritance.py`（69 行）、前端 `frontend/src/api/evidence/reprocessing.ts`、`frontend/src/components/evidence-workspace/OcrReprocessingPanel.tsx`，以及 `evidence_upload_service.py`、`evidence_processing_executor.py`、`evidence_sidecar_preparation.py`、`evidence_progress_service.py`、`evidence_reprocessing.py` 的当前实现（后两者为未跟踪新文件，直接按当前内容核对）和 `EvidencePage.tsx` 的接线段（`:327-346`、`:905-989`、`:1790-1809`）。只读源码结论；未运行应用/测试/浏览器（用户已声明运行验收后置）。

### 结论：上轮 P0 已正确修复，未发现新 P0；发现 1 个 P1 功能缺陷 + 1 个 P1 健壮性缺陷 + 4 个 P2

**上轮 P0（激活后下次上传回退旧 OCR）修复成立，且遵守了“不改写旧缓存身份”的约束。** 机制核对：上传确认在过时基线校验后的同一事务内把当时活动完整修订冻进任务 payload（`evidence_upload_service.py:1077-1080`）；执行时 `load_confirmed_pages`（`confirmed_ocr_inheritance.py:47-69`）按「版本 ∈ 新快照成员 + 页行与清单页产物/页码镜像 + SUCCEEDED」解析确认识别页，`_process_prepared_page` 的继承分支直接复用**同一 OCRPage 行**（执行器 diff `:755+`），`_prepare_file` 把继承页排除出视觉页集合（`:719-723`）→ 继承页零推理、零租约、零门禁、零缓存写；`_freeze_revision` 清单因此引用确认页 id。旧命名空间/未命名空间缓存行原样保留，无任何改写。sidecar 沿用改用冻结来源而非活动指针（sidecar diff 携带分支），且因继承页 id 与前修订相同，风险复核与校对现在能正确携带（`_carry_forward_unchanged_sidecars` 的 flag/页 id 匹配命中）。重识别侧自动激活与快照状态改写均未出现（`activated: False`、`manage_snapshot_status=False`、恢复类型门不变）。

### P1

**P1-1（功能缺陷）纯原生文本增量快照的 no-op 重识别会毒化后续候选构建——`stored_inheritance` 分歧判定。**
- 触发链：快照 S1 为增量且全部成员为原生文本路线（其上传任务 payload `inherited_processing_revision_id` 非空，指向 C0）；对 S1 重识别 → 视觉页为零 → 所有页确定性复用源文本页 → manifest 与原基础修订 R1 完全一致 → `_freeze_revision` 幂等返回 R1（执行器 `:2130-2132` 语义）→ 重识别任务 checkpoint 的 `revision_id` 与上传任务的相同。此后任何从 R1 构建候选（如校对后重建）：`evidence_api_command_service._freeze_attempt_manifest → prepare_in_session → stored_inheritance`（`confirmed_ocr_inheritance.py:16-35`）同时命中上传任务记录 `{inherited: C0}` 与重识别任务记录 `{inherited: None}`（`:27-30` 对两类任务产出不同字典）→ `:33-34` 判“分歧”抛 ValueError → 构建永久失败，用户侧无解。视图层对该情形本身是诚实的（`reprocessing_view` `new_revision=false` → 前端显示“原件文字未变化”），毒点仅在后续构建。
- 最小修正：`stored_inheritance` 中上传类记录优先——存在任一上传任务记录时仅在上传记录内部做一致性校验并返回；仅当无上传记录时才采纳重识别记录（重识别 no-op 产生的 `{None}` 是回退声明，不是独立主张）。

**P1-2（健壮性）继承解析失败发生在 `_start_or_resume_snapshot` 之前，快照滞留 STAGED 且同成员集合上传被锁死。**
- 位置：`evidence_processing_executor.py:326-333`——`load_confirmed_pages` 在快照推进到 PROCESSING 之前执行；其抛出的裸 ValueError 走 `execute` 的通用异常分支，`_transition_snapshot_if_processing` 只处理 PROCESSING（`:510-513`），STAGED 无任何转换；`_recover_terminal_snapshot` 对 failed_final 只处理 PROCESSING/RETRYABLE（`:2045-2051` 附近），STAGED 不收敛。后果：任务反复重试至 failed_final，快照永久 STAGED；因 STAGED 属于 no-op 匹配态（`evidence_repositories.py:149-158`），相同成员集合的后续上传全部 no-op 返回该滞留快照且不建新 Job，仅剩“取消失败任务→快照 CANCELLED→重新上传”一条恢复路径，但界面上没有指向它的提示。
- 正常流程下 `load_confirmed_pages` 的校验按构造不可触发（inherited id 与 comparison 快照同事务读取；前修订清单无失败页），故定级健壮性而非主链缺陷；但数据漂移/行损坏正是本产品完整性立场要防御的场景，且修复代价极小。
- 最小修正：把 `load_confirmed_pages` 移到 `_start_or_resume_snapshot` 之后（失败即走 `_record_snapshot_failure` 的 terminal_error → TERMINAL_FAILURE → 集合幂等主张释放 → 重新上传可建新快照），并改为显式 `StepFailure(retryable=False, error_code="EVIDENCE_INHERITANCE_INVALID")` 以获得清晰用户文案。

### P2（记录，不阻塞）

1. 面板在 failed_final 后的“重新识别原件”总是铸造新 request_key/新命名空间（`OcrReprocessingPanel.tsx:47`、`:63-65`）→ 全额重付；而任务页通用重试（`ReprocessingRetryService`）会复用本尝试已成功页。建议为失败终态提供“重试本次识别”入口直连既有重试服务。
2. 构建幂等键仅存内存 ref（`EvidencePage.tsx:405`、`:905-913`、`:923-941`）：POST 已达但响应丢失 + 页面重载 → 同 base 产生重复候选（诚实冗余，激活仍走就绪候选）。可参照重识别键的 localStorage 先存模式。
3. 前端错误翻译复用 `decodeUploadPreviewError`（`reprocessing.ts:2,21`）——未核对其对 409 `EVIDENCE_REPROCESS_REJECTED` 形状的映射，遗留一验。
4. `ocr-reprocessing:{scope}` localStorage 键在激活/切换后不清理（面板无卸载清理）——仅存储残留，无正确性影响。

### 专项核对（应询逐条，源码依据）

- **不可变身份/哈希/来源/版本/框架**：继承全程零写——OCRPage 行原样引用，`get` 走闭包校验；页产物身份内容寻址、同版本必同 id；`original_frame` 取自同一页产物；旧缓存身份（含未命名空间原行与命名空间行）无任何改写或删除。所有不一致（合同不符、修订 id 非法、页镜像不符、非 SUCCEEDED）一律抛错，无静默丢弃引用。
- **同 base 纯文本情形**：视图诚实（`new_revision=false`）；但见 P1-1 的下游分歧毒化。
- **校对携带**：继承页 id 与前一修订相同 → `scan_page_in_session` 幂等复用同扫描 → flag id 匹配 → 复核与校对经 carried_id（(新base, 旧id) 哈希）幂等携带；新/替换成员不携带。修正了上轮“复核/校对无法随行”的担忧。
- **get_last_checkpoint 溯源**：`stored_inheritance` 以 step id `"evidence_processing"`（两类任务一致）取 checkpoint 并按 `revision_id == base` 过滤，仅认可产出该修订的任务；`reprocessing_view` 强校验 checkpoint 携带本命名空间/合同/`activated is False`（`evidence_reprocessing.py:155-160`）。
- **过时 UI/写态与 POST/卸载/localStorage 失败不确定性**：面板先写 localStorage 再发请求（`OcrReprocessingPanel.tsx:48-52`）；`jobId===null` 时复用同键重发 → 后端同命名空间幂等返回原任务，覆盖“响应丢失/卸载中止/服务器已受理”全部窗口；localStorage 写失败时请求未发出（setItem 在 fetch 前，异常进 catch）；`readReprocessing` 回显核对 project/subject/episode/snapshot/complete/job_id 六重身份（`reprocessing.ts:34-36`），错配即拒显；面板以含 snapshot+complete 的 key 重挂载（`EvidencePage.tsx:1791`），活动指针变化即卸载旧面板。终态后新点击换新键=新尝试，符合“取消任务不复用”语义。
- **候选/版本范围交互与失败恢复**：`onView` 打开确切新修订（`viewingReprocessed` 不要求 `isCurrent`，`:341-346`）；构建以新修订为 base 并带三重一致性守卫（`:919-922`）；启用走既有 expected_revision/幂等/候选绑定链，成功后清理候选存储并触发幂等的档案整理（`:952-989`）。DB 忙预检可重试（`evidence_reprocessing.py:129-134` + `is_database_busy_error`，`evidence_app_errors.py:581-587`）；人工重试拒绝已变化的活动源（`:188-191`，含“自身后继已启用”情形）。
- **进度不串历史**：`job_local_progress` 同时覆盖重识别与携带继承合同的新上传任务（`evidence_progress_service.py` diff），仅用本任务 events/runs；旧任务回退 legacy 滚动统计并按“档案命名空间为 None”过滤（`:199-202`）。

### 边界与不确定性

静态源码复核，无运行验证（用户后置）；`decodeUploadPreviewError` 对 409 形状的映射、前端测试文件、`EvidencePage` 全文其余部分未逐行核。P1-1 的触发需要“纯原生文本 + 增量来源 + no-op 重识别 + 其后重建候选”四条件叠加，实际病例资料中纯文本增量快照并不罕见，故不降级。不宣称临床/运行验收。
