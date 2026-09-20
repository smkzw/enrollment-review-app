# 执行输出：phase5-sar31001-closeout-r3-20260902 - worker_02

## 边界与上下文检查

- 已读取初始集合：`context/phase5-sar31001-closeout-r3-20260902_execution_context.md`, `plans/codex_execution_phase5-sar31001-closeout-r3-20260902.md`。
- 额外读取（合理；文件见下文）：暂停检查点 `CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md` 和 `CHECKPOINT_20260902_SAR_TARGETED_REPAIR_PAUSED.md`，之前的运行报告 `runs/execution/phase5-sar31001-facts-profile-20260902/worker_02.md`，以及 `app/workflow/`、`app/services/evidence_processing_executor.py`、`app/storage/`、`app/evidence/`、`app/domain/` 下的源代码文件。
- 已遵守边界：验收数据库 (`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`) 仅以只读方式打开（sqlite3 `mode=ro` / `-readonly`）；修改前后以及工作结束时，其 SHA-256 保持为 `79d93f382d93acf06ba0d45cfa1d8384b13146e70e96f574b5bd0666d28350ef`（WAL 为空，与暂停的检查点匹配）。未启动服务（8910 未被需要；诊断是通过代码 + 只读数据回放完成的）。没有激活失败快照，也没有复用已取消的作业。对分配的共享代码路径进行了代码编辑（与 worker_01 的“无共享服务”项不同，该项授权了最小代码修复）。本会话未触碰预先存在的未提交 Phase 5 更改。
- 遗留说明：工作树中包含暂停的 Phase 5 会话中大量预先存在的未提交更改；我的差异仅限于下文列出的缓存标识更改。

## 执行工作

**1. 故障现场重构（只读，来自暂停的数据库）。** 基线事件 `746385aba80c421ab83aaf439e084b7f` 有三个作业，每个作业都在一个新快照上（`79af5df608ce…`, `6f309de8d413…`, `fa4647247bea…` — 最后一个是仅 CBC 的探针，已取消）：
- 作业 `49bda9d56bb14d47a4641c35b2aade33`：尝试 1 处理了 24/24 页（5 个 OCR 运行，全部 `succeeded`，缓存速度），然后在最后一页 +8 毫秒处因意外的 `EXECUTOR_ERROR` 失败；执行器的通用处理程序将快照 79af5df6 切换为 `terminal_failure`（状态事件 `terminal_error`，06:47:56.279）。在 `retry_failed`（手动 API —— 事件载荷 `{"retry_scope":["evidence_processing"]}`，没有 `retry_not_before`）于 06:52:19 重置它后，尝试 2 在 14 毫秒内失败，报错 `SNAPSHOT_STATE_INVALID`（`_start_or_resume_snapshot` 中的有意为之的失败关闭：终端快照永远无法恢复）。作业 `ce47ea92…`（快照 6f309de8，相同内容）在 06:53:00 复制了尝试 1 的失败。因此，`SNAPSHOT_STATE_INVALID` 是为了重试一个已注定失败的作业而设计的响应；真正的根本原因是尝试 1 的意外异常。
- 这两个失败的快照没有 `evidence_processing_revisions` 行，也没有 `ocr_pages` 行 —— 24 个缓存的 OCRPage 行都属于 **screening（筛选）** 快照的 page artifacts（页面工件）。

**2. 通过代码分析进行根本原因诊断（未保留服务日志；先前的运行明确指出 API 从未暴露 traceback）。** 基线上传包含与 screening（筛选）节点相同的 5 个 PDF（新的事件 -> 根据 `logical_document_id(project, subject, episode, sha256)`，获得新的逻辑文档 -> 新的源文档版本）。渲染是确定性的，因此每页的 v1 OCR 缓存键 (`ocr_page_cache/v1` = 仅内容哈希 + 页面 + 配置) 与 screening 的匹配。命中路径 (`TextOnlyOcrAdapter.cached_page`) 验证了配置指纹、页面输入哈希、来源和页面编号 —— 但**不是** `page_artifact_id` —— 并返回了 screening 拥有的 OCRPage。`_freeze_revision` 随后冻结了一个将基线 artifacts 与 screening OCRPages 配对的清单，而 `EvidenceProcessingRevisionRepository._verify_manifest_artifacts`（第 1773 行）抛出了 `RevisionManifestError("OCRPage 与页产物不一致")`。该异常逃过了 `StepFailure` 处理 -> 快照 `terminal_failure` -> 不透明的 `EXECUTOR_ERROR`。重新运行真实 OCR 也无济于事：部分唯一索引 `uq_ocr_pages_cache_key_succeeded`（每个内容键仅有一个成功的行，在 `get_successful_by_cache_key` 中通过 `OcrIdentityError` 重新断言）使得第二个工件无法拥有自己的成功行，因此每次重新处理相同内容时，都会确定性地汇聚到这个崩溃点 —— 这与两次失败的基线上传情况完全一致。

**3. 修复了矛盾的不变性。** 系统范围的绑定不变性（`ocr_page.page_artifact_id == manifest entry.page_artifact_id`）在 13 个以上的位置被强制执行（冻结/重放、修订关闭、定位器服务/存储库、选择性视觉观察、事实规范化计划 + 源适配器）—— 这是一种刻意的反借用模型，即使只放宽其中一个门控，也只会将失败转移到下游并削弱临床来源。缓存是相对于它的异常。最小且一致的修复：**将缓存身份限定在页面工件上（方案 `ocr_page_cache/v2`）**，这使得外部工件的命中在结构上变得不可能，因此每个文档版本确定性地拥有自己的成功 OCRPage，并且每个完整性门控保持不变；版本内的重试/重放重用（缓存的用途）被保留。没有放宽任何门控；没有数据迁移（参见向后兼容性说明）。

## 工件与证据

代码（6 个文件，仅限缓存标识范围）：
- `app/domain/publication.py` — `ocr_page_cache_hash` 现在为 `ocr_page_cache/v2`，具有必需的 `page_artifact_id`；添加了 `legacy_ocr_page_cache_hash`（v1，仅用于旧版解码）。
- `app/domain/contracts/ocr.py` — `OCRPage.validate_page` 接受 v2（工件范围）或历史 v1 密钥，因此已经持久化的行（例如 screening 的 24 行）仍然可以解码和重放，无需数据迁移；新写入始终为 v2。
- `app/evidence/fingerprint.py` — `build_ocr_cache_key` 增加了必需的 `page_artifact_id`。
- `app/evidence/ocr_adapter.py` — `cache_key()`/`cached_page()` 增加了必需的 `page_artifact_id`；`cached_page` 重新检查 `hit.page_artifact_id` 作为纵深防御；`prepare()` 进行了传递。
- `app/storage/ocr_repositories.py` — `validate_work_identity` 和 `commit_guard` 验证/传递 `page_artifact_id`。
- `app/services/evidence_processing_executor.py` — 源文本页面缓存键和两个 `commit_guard` 调用都传递了工件 ID。

测试（6 个文件）：
- `tests/v2/evidence/test_ocr_adapter_cache.py` — `test_cache_is_scope_neutral_by_content_identity`（断言了导致事件的确切行为的已测试契约）被 `test_cache_is_scoped_by_page_artifact_identity` 替换（第二个版本 -> 未命中 -> 第二次推理 -> 两个成功行共存；相同版本重放仍然命中），以及事故级别的回归测试 `test_same_content_second_version_freezes_own_revision`（相同内容，两个版本，两个清单都通过 `EvidenceProcessingRevisionRepository.create`/`get`）；签名更新 + v2 密钥断言。
- `tests/v2/evidence/test_ocr_contracts.py` — 调用点更新；新 `test_ocr_page_accepts_legacy_v1_cache_key_but_not_arbitrary_drift`（v1 解码公差，v2 写入，任意漂移被拒绝）。
- `tests/v2/storage/test_ocr_repositories.py`, `test_migration_0010.py`, `tests/v2/domain/test_fact_evidence_closure.py`, `tests/v2/services/test_evidence_processing_executor.py` — 调用点更新。

结果：已修复。从合法的新快照中进行全新的基线上传现在将未命中（v2 对比旧版 v1 密钥），通过 oMLX 门控重新运行 24 页，冻结一个自有的基础修订版，并且所有下游绑定门控（sidecar/定位器/关闭/规范化）均保持不变。如果任何页面以前以源文本路由处理过，`SOURCE_TEXT_CACHE_CONFLICT` 仍然是一个精确的、非崩溃式的失败关闭（与本次事故无关；所有 24 个基线页面均为 VISION_OCR）—— 已标记为已知的不一致，本次未做更改。

## 命令与观察

- `shasum -a 256`（修改前后）— 验收数据库在暂停状态下未更改。
- `sqlite3 -readonly …` — 作业行/事件、快照状态事件、OCR 运行（2 次作业共 10 次，全部 `succeeded`，24 页）、`evidence_processing_revisions` 不存在、48 个 OCRPage 行绑定到 screening artifacts（0 个绑定到基线 artifacts）。
- 对 `/tmp` 中的 `_freeze_revision` 清单构造进行只读 Python 回放：对于真实基线数据，合约验证通过（ocr_page_id 为空）—— 排除了合约验证器，将崩溃定位到存储库的清单工件验证。
- `.venv/bin/python -m pytest`（全部绿色）：`tests/v2/evidence + tests/v2/storage` = **759 通过，1 跳过**；`tests/v2/services + tests/v2/workflow` = **434 通过，1 跳过**；`tests/v2/api + tests/v2/domain + tests/v2/projections + boundaries` = **768 通过**；以及针对性的适配器/合约/执行器运行。总计约 1,960 个测试通过，0 失败。并非所有 `tests/v2/protocols/agents/llm` 套件都在此过程中重新运行（未触碰这些代码路径；Codex 可以在检查时运行它们）。
- `uvx ruff`（0.16.5，项目未固定）：对包括未触碰的 `app/workflow/runner.py` 在内的所有文件标记了相同的预先存在的默认规则问题 —— 不是此次更改引入的；编辑内容遵循周围的风格。

## 障碍或缺失环境

- 无阻碍。注意：(1) 真正的修复方案是设计选择，这需要修改已测试的“作用域中性缓存”契约（已测试的 `scope-neutral` 行为已被故意更改并在此处标记，以供 Codex 验收）；替代方案 —— 放宽 13 个以上的完整性门控，或放宽上传版本身份 —— 被评估为风险更大，且未被采用。(2) 验收数据库中 screening 节点的旧版 v1 缓存行变成了无效的缓存条目（它们仍然可以解码/重放，但永远不会再次命中）；对 screening 没有影响。(3) 没有保留 8910 服务日志，因此异常层面的证据是从持久状态 + 代码中重建的； determinism（确定性）得到了两次独立的失败以及通过的回归测试的证实。

## 重运行请求或下一步

1. Codex 审查 diff（6 个应用程序文件 + 6 个测试文件，仅限缓存标识范围）并确认接受 `ocr_page_cache/v2` 工件范围的契约修订。
2. Worker_03 随后可以通过官方 API，在专用的 8910 边界内并使用显式环境契约，从合法的新快照运行基线处理；页面将通过 oMLX (8001) 真正地重新进行 OCR。不要重用快照 `79af5df6…`/`6f309de8…`/`fa464724…` 或作业 `2e28e867…`（仍为 `cancel_requested`）。
3. 保持 `claims_complete=false`，直到完整的 31001 事实/事件/暴露/配置文件链及其临床 QC 通过；Phase 5.5 仍未授权。
