按方案 A 做定向复核：先重开完整修订闭包、基础修订 `preparation_policy` 和规范化下游，只核对这条路径。# Conference Output: enrollment-direct-vision-source-20260916 - evidence_single_object

## Output

定向复核（只读，未跑模型/测试/临床库）。方案 A 已把上一轮的完整修订 OCR 断链补上。先前把“空正文进规划”当成错误采信，对照 pending 政策与视觉来源校验后收回。本轮未发现可把未采信观察写成事实的新旁路。

---

### 已闭合的上一轮结论

| 原结论 | 现状 |
|---|---|
| 完整修订强制每页 OCR，扫描件无法激活/双读 | 已改。解码后的 **base** `preparation_policy == original-page-images/v1` 时，无 OCR 页只要产物成功、归属一致、有页图哈希即可（`app/storage/evidence_locator_repositories.py:2720-2746`） |
| 政策只在 Job payload，修订身份不含政策 | 已改。合同默认 `legacy-text/v1`（`app/domain/contracts/evidence_processing.py:122`）；冻结写入 payload（`evidence_processing_executor.py:2156`）；图像政策修订号追加 `-images-v1`（2131-2132） |
| 空正文页会被当成可采信来源 | **收回。** 不是旁路。见下文 |
| 应改弱继承键以去 OCR 名 | **未改，也不应改。** 仍是 `(source_document_version_id, page_artifact_id)`（`confirmed_ocr_inheritance.py:70`）；属既有确认页复用，不是新 OCR 推断 |

旧 payload 无 `preparation_policy` 时 Pydantic 默认为 `legacy-text/v1`，完整修订仍要 OCR。历史路径 fail-closed。

---

### 方案 A 路径（源码）

1. 新上传 Job 仍写 `preparation_policy: original-page-images/v1`（`evidence_upload_service.py:1079`）。
2. 执行器跳过外部 OCR，保留页图；native/TXT 仍落 `OCRPage`；无 OCR 成功页计入完成并冻进 base（`evidence_processing_executor.py:739-805, 930-949, 2114, 2156`）。
3. sidecar / 候选构建只扫 **有** `ocr_page_id` 的页（`evidence_sidecar_preparation.py:97-98`；`evidence_revision_workflow.py:570-576`；`evidence_revision_builder.py:135-167`）。无 OCR 页不要求风险扫描。有 OCR 的继承页仍走成功/风险/校对闭包（`evidence_locator_repositories.py:2750-2764, 2901-2933`）。
4. `builder.build` 复制 base manifest（`evidence_revision_builder.py:356-357`）→ `CompleteEvidenceProcessingRevisionRepository.create` → `_verify_terminal_successful_pages`。
5. 候选过门后快照 `PROCESSING → READY`（`evidence_revision_workflow.py:510-514`）。激活仍 `Complete...Repository.get`（`evidence_activation_service.py:496-498`），现可过图像政策无 OCR 页。
6. 页审仍要活动完整修订 + 页图（`page_review_job_service.py:98-106`）。规范化 `allow_image_only` 仍要求 `include_visual_sources and coverage_id`（`fact_normalization_source_adapter.py:332-338, 494`；`fact_normalization_job_service.py:313, 437-438`）。

元数据链头仍必须有（`evidence_revision_builder.py:142-147`）。这是既有 4.4 门禁，不是 OCR 断链复现。

---

### 空来源 vs 错误采信（收回）

对照指定文件：

- `page_review_pending_normalization.py:15-39`：整次调用没有任何已采信事实/手写（视觉政策下不算 clause_signals）时，直接 `unresolved_items`，**不调模型、不造病史**。
- `fact_normalization_executor.py:1043-1050, 1114-1120, 1123-1125`：coverage 任务带 `preserve-pending/v2`；无候选且无未解决项拒绝。
- `page_review_sources.py:35-98`：事实候选必须引用本次已采信观察；视觉定位必须对应该观察的读道/摘录/coverage。
- `page_review_visual_locator_validation.py:152-155, 161-172`：只接受 coverage `ACCEPTED` 页，并与物化视觉来源逐字节比对。
- 事件/暴露必须挂已校验事实候选，定位不得超出那些事实（`evidence_normalizer.py:253-268`）。

空白页、未解决读、无 locator **不是旁路**；`pending_only_output` 与页闭合（`validate_output_page_closure` 1859-1889）要求的是“候选或未解决覆盖”，不是每页都要有已采信事实。

混合切片（同一次调用里既有已采信观察又有空白页）会进模型；空白页若既无 unresolved 也无 locator 引用，步骤 **失败闭合**，不会静默成事实。这是作业失败风险，不是错误采信。

---

### 新确认缺陷

**完整修订/规范化主链：未发现可把未采信内容写成事实的新旁路。**

`allow_image_only` 只核对页码和页图哈希、不重复核对 `source_document_version_id`（`fact_normalization_source_adapter.py:335-337`）。规划前完整修订 `get()` 已用 ORM 列 + `PageArtifact` 镜像做过归属（`evidence_locator_repositories.py:2734-2746`；`ocr_repositories.py:514-541`）。不构成独立旁路，不必为去 OCR 改继承键。

**`mtplx_owned_server`（仅驱动本身，不谈未接线）：**

- 不会杀他人服务：占用端口直接拒绝（111-112）；stop/kill 只打本次 `Popen` 句柄（73-87）。
- **确认缺陷：** `_stop_owned` 在 `kill()` 之后 `while process.poll() is None: await asyncio.sleep(0.1)` 无上限（88-89）。僵死/D 状态会让 `finally` 的 shutdown 一直挂起。不是集成缺失。
- CLI `--app-launch-id`：按 owner 的 help 核对，本轮未跑进程。`/health` 的 `pid`/`launch_id`/`vision.enabled` 形状仍未在本机验证。

---

### 未验证运行时

- 未走真实上传 → 冻 base → 候选 READY → 激活 → 页审 → 规范化。
- 未验证 `-images-v1` 修订在现库与旧 `epr-…` 行并存时的读取。
- 未验证混合 native OCR + 扫描无 OCR 的激活与 sidecar。
- 冻结后仍入队 `selective_vision_postprocess`（`evidence_processing_executor.py:459-469`）；与激活无同步，是否空转未跑。

**给 Codex：** 方案 A 源码上已打通完整修订；不要再把空页无事实当成缺陷。驱动里值得改的只有 kill 后无超时等待。临床/浏览器验收仍归 Codex。
