所有检查均已通过。工作已完成 —— 这是我的最终报告。

# 执行输出：phase5-sar31001-nextflash-closeout-20260902 - worker_02

## 边界与上下文检查

- 已绑定到运行器的当前工作目录（`phase5-clinical-facts-profile` 工作树，分支 `codex/phase5-clinical-facts-profile`）。Delegated 模式已生效；未派发会议，未进行同行评审，未修改报告文件。
- 读取了初始集合（`context/..._execution_context.md`，`plans/codex_execution_...md`）。我的任务是工作项 2：OCR 缓存内容级推理复用与 `page_artifact` 所有权并存，并保留不可变证据门控和设计文档的内容哈希缓存契约，以及根本原因回归测试。
- 额外阅读（通过工具进行证据获取）：`app/evidence/fingerprint.py`，`app/domain/publication.py`，`app/evidence/ocr_adapter.py`，`app/storage/ocr_repositories.py`，`app/evidence/page_processor.py`，`app/domain/contracts/ocr.py`，`app/services/evidence_processing_executor.py`，`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`（缓存契约行），`tests/v2/evidence/test_ocr_adapter_cache.py`，`tests/v2/services/test_evidence_processing_executor.py`。
- 目标源文件包含来自主行的先前未提交的第 5 阶段进行中工作 (WIP)（v2 缓存键本身是未提交的）。我的更改是在工作树状态之上进行的增量更改；没有任何内容被回退。

## 已执行的工作

**根本原因审查（证据）：**
- 设计契约 (`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:85`)：缓存键 = 文件内容哈希 + 页码 + OCR 模型/参数版本。
- 基线事件（记录在 `app/domain/publication.py:37-43` 中）：v1 仅内容的缓存键使得具有相同内容的第二个文档版本**借用**了第一个版本的成功 `OCRPage`；清单完整性门控（`EvidenceProcessingRevisionRepository._verify_manifest_artifacts`：`ocr_page.page_artifact_id != entry.page_artifact_id` → `RevisionManifestError`）在冻结时拒绝了这种跨工件绑定，导致快照以不明确的 `EXECUTOR_ERROR` 终止。
- 未提交的 v2 修复将 `page_artifact_id` 绑定到了缓存键中 —— 恢复了所有权，但**彻底消除了内容级复用**：之前存在的测试断言在重新上传相同内容时 `calls == 2`（每页重新付费推断），这与设计文档的契约相矛盾，并使任务项 3 的新入口 SAR 31001 运行成本过高。

**最小实现（3 个源文件，追加式）：**
1. `app/storage/ocr_repositories.py` — `OcrPageRepository.list_by_content_identity()` 和 `get_latest_successful_by_content_identity()`：复用身份 = `source_sha256` + 页码 + `profile fingerprint` + 实际页面图像 `page_input_sha256` + 布局/坐标变换版本（设计契约；排除工件绑定）。每一行候选数据都经过完整的镜像/闭包验证，因此损坏的数据行会表现为 `PersistedContractInvalid`，而不会被静默复用；通过 `(completed_at, ocr_page_id)` 选择最新的成功数据行以确保确定性；FAILED/CANCELLED/PROCESSING 数据行绝不能作为复用源。基于列的匹配也使遗留的 v1 行能够作为复用源（历史行被读取，从不被重写）。
2. `app/evidence/ocr_adapter.py` — `PreparedOcrRequest.reused_page` 和 `OcrRecognition.reused_from_ocr_page_id`（均为默认 `None`，向后兼容）；`reusable_page()` 带有深防御性的身份重新检查（`OcrCacheIdentityError`）；`prepare()` 仅在 v2 未命中时填充 `reused_page`（保持零推理，检查点兼容）；新的 `finalize_reuse()` 通过当前的 v2 缓存键生成了**由当前页面工件拥有的新成功 `OCRPage`**（复制文本；重新计算确定性质量）；`recognize`/`finalize_success` 在不进行推理的情况下进行路由；`finalize_failure` 返回已经确定的复用结果，而不写入失败行或双重持久化。
3. `app/services/evidence_processing_executor.py` — `_process_visual_page` 在复用时跳过 `PROCESSING` 行，并重用现有的 `try/finally` 以确保页面租约始终被释放；新的 `_commit_content_reuse()` 在一个事务中提交，受 `PageWorkLeaseRepository.commit_guard`（缓存键重计算 + 所有者/生成/过期检查）+ `OcrPageRepository.create` 限制。没有写入 `OCRAttempt` 行，这与不可变缓存命中写入的（无）情况一致。

**保留的不变量：** 仅追加历史记录（源数据行从未被修改）；冻结的清单条目仅引用自己的工件 `OCRPages`（门控通过）；v2 工件范围键保持命中/写入标识；每个缓存键的单成功不变量未受影响；租约/`commit_guard` 延迟提交门控适用于复用提交。

## 工件与证据

- `app/storage/ocr_repositories.py` — +2 个存储库方法（内容身份查找）。
- `app/evidence/ocr_adapter.py` — 复用查找、`finalize_reuse`、数据类字段、`recognize`/`finalize_success`/`finalize_failure` 中的路由、文档字符串契约更新。
- `app/services/evidence_processing_executor.py` — 复用分支 + `_commit_content_reuse`。
- `tests/v2/evidence/test_ocr_adapter_cache.py` — 更新了 `test_cache_is_scoped_by_page_artifact_identity` 和 `test_same_content_second_version_freezes_own_revision` 为并存放契约；添加了 4 个回归测试：`test_prepare_reports_content_reuse_and_finalize_reuse_mints_owned_row`，`test_content_reuse_never_uses_failed_rows`，`test_content_reuse_surfaces_poisoned_source_row`，`test_latest_successful_content_identity_is_deterministic`。
- `tests/v2/services/test_evidence_processing_executor.py` — 添加了 `test_same_content_new_version_reuses_inference_and_owns_success_page`：两个具有相同内容字节的文档版本通过完整的持久作业恰好产生 **1** 个推理调用，两个版本都冻结了引用自己拥有的成功行的修订版本，并且清单完整性门控通过。

## 命令与观察

- `uv run pytest tests/v2/evidence/test_ocr_adapter_cache.py tests/v2/storage/test_ocr_repositories.py -q` — 基准 72 通过（更改前）。
- `uv run pytest tests/v2/services/test_evidence_processing_executor.py -q` — 基准 29 通过（更改前）。
- `uv run pytest tests/v2/evidence tests/v2/storage tests/v2/services -q` — 在所有源更改后：**1115 通过，2 跳过**（跳过 = 实时环境标志后面的真实提供商 e2e 测试；与此更改无关）。
- 最终组合运行（adapter-cache + ocr-repositories + executor + fact-evidence-closure）：**139 通过**。
- 执行器测试最初在并发下失败（`calls == [1, 1]`）：两个相同内容文件的页面在第一个成功行提交之前进行准备 —— 在准备时不存在复用源，因此实际推断是合法的收敛行为，而不是缺陷。测试现在在 `page_processing_concurrency=1` 下运行，并附带解释性注释；收敛重试仍然通过 v2 命中去重。
- 没有生产路径、数据目录或包被写入或安装。

## 阻碍或缺失环境

无。为 Codex 记录了两个既定的行为说明：
- 复用提交有意不写入 `OCRAttempt`（与缓存命中先例相同）；基于尝试的崩溃恢复页面计数可能会少计已复用的页面，直到重试通过 v2 缓存命中收敛 —— 这对 `OCRRun` 摘要来说是外观上的；修订版本冻结基于 `OCRPage` 行。
- 并发相同内容处理在竞争时可能会重新推断（在准备时不存在复用源）；结果仍然是正确的，并且每个工件拥有一行。

## 重新运行请求或下一步

此工作项无需重新运行。对于 Codex 验收：`git diff` 涉及上述列出的 5 个文件（请注意，这些文件还包含以前的未提交的 v2 键 WIP —— 我的更改是增量更改）。对于 worker_03：SAR 31001 从合法新条目关闭的相同内容基线证据现在在内容级别复用 OCR 推理，而不是为每个页面重新付费；`claims_complete` 门控未受此更改影响。
