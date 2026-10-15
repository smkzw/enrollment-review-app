全部核验完成，成稿。

# Conference Output: r05-ocr-reprocessing-design-20260915 - evidence_single_object（第四轮：定向修复核验）

## Output

核验范围：`confirmed_ocr_inheritance.py`、`evidence_processing_executor.py`（`_execute` 继承段与错误分类）、`OcrReprocessingPanel.tsx`、`EvidencePage.tsx`（URL 持久化/幂等键/候选恢复/错误处理段）、`reprocessing.ts`、`evidenceJobHttp.ts`、`evidenceViewModels.ts` 译码器、`evidence_api_command_service.py` 幂等回放、`api/v2/errors.py` 信封、`review_action_worklist._raise_translated`。只读源码；未运行应用/测试/浏览器/模型。

### 结论：两项 P1 均已在源码层面解决；发现 1 个新的窄触发 P2；其余声明核实成立

**P1-1（stored_inheritance 分歧毒化）——已解决。** `confirmed_ocr_inheritance.py:16-37`：重识别任务不再向 `matches` 投影 `{None}` 记录，仅置 `reprocessed` 标志（`:28-30`）；无上传血缘且存在重识别产出时回退 `{inherited: None}`（`:33-34`）；有上传血缘时仅在血缘内部做一致性校验、冲突仍抛错（`:35-36`）。上轮触发链（纯原生文本增量快照 + no-op 重识别 + 其后重建候选）现解析为上传任务的 `{C0}` 记录，构建不再失败。全程只读，无缓存改写。

**P1-2（继承失败滞留 STAGED 锁死同集合上传）——已解决。** `evidence_processing_executor.py:330-342`：`_start_or_resume_snapshot` 先行，`load_confirmed_pages` 后置且被显式分类——DB 忙 → `EVIDENCE_INHERITANCE_BUSY` 可重试；其余 → `EVIDENCE_INHERITANCE_INVALID` 不可重试。StepFailure 经 `_record_snapshot_failure` 使快照进入 RETRYABLE_FAILURE/TERMINAL_FAILURE，终态释放集合幂等主张（`evidence_repositories.py:1607-1013` 既有行为），重新上传可建新快照，锁死路径消除。重识别路径不受影响（payload 无合同键，`:50-51` 早返回空映射，不触碰前修订）。

### 其余声明逐条核实（均成立）

- **失败尝试同任务重试**：面板 `retry()`（`OcrReprocessingPanel.tsx:58-68`）经 `retryEvidenceJob`（`evidenceJobHttp.ts:82-93`）走通用任务重试，按类型路由到 `ReprocessingRetryService`（同命名空间、新鲜度校验、复用本尝试已成功页）；按钮仅在 `failed_final` 显示（`:75`），`failed_retryable` 由自动重试覆盖、`cancelled` 仍走新请求，符合既定语义。
- **URL 持久化与精确校验**：`ocrSnapshot`/`ocrRevision` 参数派生 `reprocessedView` 并由 `setReprocessedView` 写/清（`EvidencePage.tsx:248-252`）；`onView` 同步切换选中快照（`:1803-1810`）；`viewingReprocessed` 要求 episode+snapshot 双匹配（`:331-332`）、`viewedRevisionConsistent` 要求回读修订 id 与快照 id 精确回显且未启用视图不要求 `isCurrent`（`:345-350`）；重载后快照自动选中活动项使视图重建成立（`:288-302`）。启用仅经显式 `activateReviewableRevision`（就绪候选 + expected_revision + 幂等键），视图路径无任何自动激活。
- **命令幂等键先存后发、确认后释放**：`idempotencyKeyFor` 以 `evidence-command:{subject}:{episode}:{action}` 为键，先写 localStorage 再随请求发出，ref+localStorage 双存（`:907-915`）；`completeAction` 在确认结果后删除（`:917-921`、build 成功 `:944`）。上轮 P2“POST 丢失+重载产生重复候选”由回放同键解决。
- **错误信封**：`decodeUploadPreviewError` 解析 `{error:{code,title,detail,recovery_action,context}}`（`evidenceViewModels.ts:505-530`），与 `errors.py:150/:228-237` 的 EvidenceAppError 信封逐字段对应；重识别 API 经 `_raise_translated`→`translate_storage_error`（`review_action_worklist.py:149-154`）。`retryEvidenceJob` 的 fetchImpl 注入与面板调用签名一致。

### 新发现缺陷（P2，窄触发，建议下轮顺带修）

**P2-NEW　已提交但响应丢失的构建命令 + 其后启用推进修订号 → 保留键换体永久 409 锁死该构建动作。**
- 机理（已核）：失败命令不落服务端幂等记录（记录与候选同事务，`evidence_api_command_service.py:1314-1342`），故普通的“失败后刷新重试”换体安全；但“服务端已提交、客户端未见响应”时记录已带旧命令哈希，若用户经 localStorage 候选恢复先**启用**了该候选（episode.revision 前进），再对同一 base 重建（如校对后 `build:{snapshot}:{base}` 同动作串），同键异体触发 `AppIdempotencyConflictError`（`:1450-1458` 同键异命令 409），前端无该错误码处理（全库 grep 无）、键仅在成功时释放 → 该动作串永久冲突，需手工清 localStorage 方可恢复。
- 触发面：单用户本地应用下需“响应丢失 + 启用先于重试”叠加，窄但后果是持久锁死。最小修正：在 `handleProcessingError`（或各 catch）识别幂等冲突错误码时调用 `completeAction` 清持久键并提示重试——冲突本身证明该键已绑定不同命令，换新键重试是安全且语义正确的。
- 同类交互已排查无碍：StaleRevision 首败不落记录，保留键换体重试干净；响应丢失但无启用插入时，同体回放返回原候选并释放键。

### 边界

LocalStorage 历史按所有者决定有意保留，本轮不提清理建议。运行时/浏览器/临床验收均未执行、保持未验证状态；本报告仅为静态源码结论，不构成最终采信。
