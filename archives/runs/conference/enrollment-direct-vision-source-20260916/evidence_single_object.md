我将按会议角色做独立只读审阅：先读取指定上下文和计划，再核对源码中双 VLM 去 OCR 前置依赖的真实接线。上下文包几乎是空的，我会直接从源码定位 `preparation_policy`、OCR 跳过路径和 `mtplx_owned_server` 的真实接线。已定位核心服务文件；接下来只在 `app/` 里核对 `DIRECT_VISION_PREPARATION`、无 OCR 放行条件和 mtplx 取消/所有权。`DIRECT_VISION_PREPARATION` 未进 `__all__`；我接着核对上传、执行器和规范化适配器的真实接线，并定位 `mtplx_owned_server`。已确认 `mtplx_owned_server.py` 存在。接下来对照 git diff 和执行器/规范化适配器，核对 OCR 跳过与历史任务恢复是否真的接线。接下来追踪 OCR 跳过后的页产物、冻结清单和真实消费者，重点看无 OCR 页会不会被后续流程误采信。# Conference Output: enrollment-direct-vision-source-20260916 - evidence_single_object

## Output

独立只读审阅结论：**当前“最小修改”不能让扫描件/图像新上传走到双 VLM 或视觉规范化。**  
`preparation_policy` 只让基础处理跳过外部 OCR，完整修订闭包仍强制每页成功 OCR；因此 `allow_image_only` 对这条新上传路径是达不到的死代码。不以编译或单测通过代表临床验收。Codex 仍是最终权威。

---

### 1. Evidence

**读过的指定材料**

- `context/enrollment-direct-vision-source-20260916_conference_context.md`：Source of Truth / Scope 仍为 TODO。
- `plans/codex_main_venue_enrollment-direct-vision-source-20260916.md`：分解与核验清单仍为 TODO。
- `runs/conference/enrollment-direct-vision-source-20260916/evidence_single_object.md`：runner 占位 PENDING，未当作审阅结论。

**工作树事实（只读 `git status` / `git diff`）**

- 相关已改文件：`app/domain/contracts/evidence_upload.py`、`app/services/evidence_upload_service.py`、`app/services/evidence_processing_executor.py`、`app/services/fact_normalization_source_adapter.py`、`app/services/fact_normalization_job_service.py`。
- `app/llm/mtplx_owned_server.py` 为未跟踪新文件；全库仅自身定义 `owned_mtplx_server`，无任何 import。
- 测试树无 `preparation_policy` / `allow_image_only` / `original-page-images` 命中。

**新上传任务确实带上了去 OCR 政策**

```1074:1082:app/services/evidence_upload_service.py
            payload={
                ...
                "ocr_inheritance_contract": "confirmed-ocr/v1",
                "preparation_policy": DIRECT_VISION_PREPARATION,
                "inherited_processing_revision_id": EpisodeRepository(session).get(
                    command.review_episode_id
                ).active_evidence_processing_revision_id,
```

常量：`DIRECT_VISION_PREPARATION = "original-page-images/v1"`（`app/domain/contracts/evidence_upload.py:62`）。未进入 `__all__`，但不影响具名 import。

**执行器：历史任务仍 OCR，新任务跳过外部 OCR，图像/native text 仍走渲染**

```323:327:app/services/evidence_processing_executor.py
    preparation_policy = payload.get("preparation_policy")
    if preparation_policy not in (None, DIRECT_VISION_PREPARATION):
        raise StepFailure(...)
    config = replace(config, direct_vision_preparation=preparation_policy == DIRECT_VISION_PREPARATION)
```

```739:805:app/services/evidence_processing_executor.py
    if visual_pages and not config.direct_vision_preparation:
        ocr_run_id = _create_ocr_run(...)
    ...
    inherited = config.confirmed_pages.get((prepared.version.source_document_version_id, artifact.page_artifact_id))
    if inherited is not None ...:
        ocr_page = inherited
    elif ... route == ExtractionRoute.VISION_OCR and prepared.ocr_run_id is not None:
        ocr_page = _process_visual_page(...)
    elif ... route != ExtractionRoute.VISION_OCR and artifact.native_text_sha256 is not None:
        ocr_page = _get_or_create_source_text_page(...)
```

- Pass A 仍渲染并落页图（`_render_all_pages`，约 721–728 行）。
- `VISION_OCR` 页在新政策下 `ocr_run_id is None`，且无继承时 `ocr_page` 保持 `None`。
- native/TXT 页仍生成 `OCRPage`（`_get_or_create_source_text_page`，约 1198 行）。
- 无 OCR 的成功页被计为完成：`ocr_page is None or status == SUCCEEDED` → `page_succeeded`（930–949 行）。
- 基础修订允许 `ocr_page_id=None`（冻结 2114 行；合同 `EvidenceProcessingRevisionPage` 只禁止失败页带 OCR，不要求成功页有 OCR）。
- 冻结后快照停在 `PROCESSING`，“等待后续定位、风险核对与校对”（476–481 行）。
- 已有 checkpoint 的任务直接返回，不重跑（275–276 行）。`preparation_policy is None` 的历史任务仍走外部 OCR。

**规范化适配器：无 OCR 仅在 visual+coverage 时放行**

```332:338:app/services/fact_normalization_source_adapter.py
        if entry.ocr_page_id is None:
            if not allow_image_only:
                raise FactPlanningSourceError("本页没有文字识别结果，请通过原件双读整理资料")
            artifact = PageArtifactRepository(session).get(entry.page_artifact_id)
            if (not artifact.page_image_sha256 or artifact.page_number != entry.page_number):
                raise FactPlanningSourceError("原件页图像缺失或页码不一致，不能整理资料")
            raw_text = ""
```

`allow_image_only = include_visual_sources and page_review_coverage_id is not None`（适配器 494 行；job_service 313 行）。  
`create_or_reuse_job` 在 `include_visual_sources and coverage is None` 时拒绝（437–438 行）。  
命令入口：`include_visual_sources=coverage_id is not None`（`fact_normalization_command_service.py:562`）。

**真实消费者仍以完整修订 + OCR 为前置**

| 消费者 | 位置 | 对无 OCR 页的行为 |
|---|---|---|
| 完整修订闭包 | `app/storage/evidence_locator_repositories.py:2738-2740` | `ocr_page_id is None` → `RevisionClosureError("缺少 OCR 页引用")` |
| 完整修订读取/构建 | 同文件 `_verify_referenced` 3261 行调用上述门禁 | 无法冻结/还原可激活完整修订 |
| 页审入队 | `app/services/page_review_job_service.py:98-106` | 从 `authority.complete_processing_revision_id` 取完整修订；缺页图才报错，但权威本身过不了完整修订 |
| 来源关联文本 | `app/services/page_association_sources.py:13-14` | `ocr_page_id is None` 直接跳过，视觉物化拿不到 association |
| sidecar 风险/行定位 | `app/services/evidence_sidecar_preparation.py:97-98,210-211,245-246` | 无 OCR 页跳过，不建 RAW_OCR 定位 |
| 文字定位 | `app/services/evidence_locator_service.py:270-271,290-291`；仓储 253-256 行 | RAW_OCR / EFFECTIVE_TEXT 必须绑定 `ocr_page_id` |
| 视觉定位 | `app/projections/page_review_visual_locators.py:96` | 允许 `ocr_page_id=None`，层为 `PAGE_REVIEW_VISUAL` |
| 视觉定位持久化 | `page_review_visual_sources.py:22-39,57-67` | 仍先 `FactAuthorityValidator` + 完整修订 `get()` |
| 覆盖选择 | `page_review_coverage_selection.py:36,71` | 绑定完整修订；不要求每页 `ACCEPTED` |
| 事实闭包取原文 | `app/domain/gates/fact_evidence_closure.py:226-227` | 非 page_excerpt 且无 `ocr_page_id` → 无原文 |

页处理器仍写着旧不变量：“绝不出现既无原生文本又无 OCR 的页面”（`app/evidence/page_processor.py:14-15,324-327`）。新执行器对 `VISION_OCR` 已打破该不变量。

**原件归属 / 哈希 / 历史恢复**

- 页产物身份含 `source_document_version_id + page_number + input_sha256 + 渲染/解码版本`（`app/evidence/fingerprint.py:116-143`）。
- 确认 OCR 继承键是 `(source_document_version_id, page_artifact_id)`（`confirmed_ocr_inheritance.py:70`；执行器 736、772 行），不是页图哈希单独键。
- 继承校验：`prior.evidence_snapshot_id == snapshot.comparison_snapshot_id`（`confirmed_ocr_inheritance.py:41-45`）。比较基线来自预览 `base_snapshot_id`（`evidence_upload_service.py:963`），继承指针来自**当前活动**完整修订（1080–1082 行）。两者不一致时 `_execute` 以 `EVIDENCE_INHERITANCE_INVALID` 停任务（347–348 行）。
- `evidence_reprocess` 载荷无 `preparation_policy`（`evidence_reprocessing.py:111-119`），恢复后仍会外部 OCR。
- 启动恢复现把 `evidence_reprocess` 终态 RUNNING OCR run 一并收敛（执行器 2018–2024 行）。

**`mtplx_owned_server`（未接线）**

- 文件：`app/llm/mtplx_owned_server.py`。
- 所有权只认本次 `Popen` 句柄，不按端口杀进程（73–74、111–112 行）；端口占用直接失败。
- 启动用同步 `Popen`，健康检查要求 `/health` 的 `startup.pid`、`launch_id`、`model`、`model_path`、`vision.enabled`（119–141 行）。
- 取消：`_finish_cleanup` 用 `asyncio.shield` 把 stop 跑完再重新抛 `CancelledError`（92–102 行）。默认 `shutdown_seconds=30`。
- 产品页审取消只取消 asyncio 任务并轮询 Job 状态（`page_review_cancellation.py:10-34`），释放的是进程内信号量（`page_review_admission.py:25-33`），不 stop MTPLX 进程。
- 模块文档写明：调用方必须在整个 context（含 shutdown）持有硬件租约；仓库内没有这样的调用方。

---

### 2. Inference

**最高影响缺陷：去 OCR 的新上传无法进入双读。**

新扫描件/图像路径是：

1. 确认上传 → payload 带 `original-page-images/v1`
2. 执行器跳过 oMLX，页图成功，`ocr_page_id=None`，基础修订可冻
3. sidecar 不给这些页做风险扫描/行定位
4. 完整修订闭包要求每页成功 OCR → 不能构建/激活
5. 页审权威来自活动完整修订 → 不能入队双 VLM
6. 无 coverage → `allow_image_only` 为 false → 规范化仍拒绝无 OCR 页

因此“最小修改”只打通了基础处理半段。对临床主体（图像、扫描 PDF、`VISION_OCR`）**新上传流程不能继续**。native/TXT 因仍写 `OCRPage`，可能碰巧走完旧 4.4；这不是双 VLM 去 OCR 的目标路径。

这与 `page_processor.py` 的显式不变量直接冲突：扫描页被设计为“无文本层则必须 OCR”，现在变成“无文本层也无 OCR”。

**`allow_image_only` 即使将来绕过完整修订，仍有错误采信面。**

- 开关是修订级，不是“coverage 已 ACCEPTED 的页”级。无 OCR 页一律 `raw_text=""`，`effective_text_sha256` 为同一空串哈希。
- `select_normalizer_coverage` 只要求唯一无 `lane_failures` 的 coverage，不要求每页 `ACCEPTED`。
- `build_page_review_normalizer_input` 只拦截 `FAILED_PENDING_REREAD`；无 `reconciliation_id` 的页仍进调用，只是不带读道记录。
- 视觉 locator 只在 `include_visual_sources` 时追加，且不要求每页至少一条视觉摘录。空正文 + 空/不完整视觉来源时，模型仍可能看到页图/条目并产出无锚点事实。

**继承可能让“去 OCR”名不副实，或直接卡死增量/全量重传。**

- 同版本、同页产物身份会**原样复用旧 OCR**，即使新任务写了 `preparation_policy`。
- 活动完整修订所属快照 ≠ 本次 `comparison_snapshot_id` 时，确认后的处理任务直接失败，原件未处理。
- 渲染/解码版本变化会产生新 `page_artifact_id`，继承键错过，扫描页再次变成无 OCR，随后同样卡在完整修订。

**`mtplx_owned_server` 不能承担产品取消/所有权。**

它是进程驱动雏形，不是页审适配器。若按现端口 8002 接线，会因“端口已被其他服务使用”拒绝，也不能接管 GUI 服务。取消推理不会卸载权重；shielded shutdown 最多阻塞约 30s。双模型串行加载/释放不存在。

---

### 3. Recommendation

在完整修订 OCR 门禁与页审权威来源未改之前，**不要把该政策视为可上临床的新上传路径**。历史 `preparation_policy is None` 任务应继续 OCR。

若目标是扫描件直接双 VLM，最小**成套**改动（需 Codex 拍板，不是再加一个布尔）：

1. **明确权威来源**  
   - 方案 A：完整修订允许 `VISION_OCR` 成功页 `ocr_page_id is None`，但必须有 `page_image_sha256`，且风险闭包改为“有 OCR 的页恰好一扫；无 OCR 页零扫、零 RAW_OCR 定位”。  
   - 方案 B：页审改为可从基础修订+页图入队，激活完整修订推迟到双读 coverage 之后。  
   只改执行器、不改闭包，流程仍断。

2. **`allow_image_only` 收成逐页合同**  
   仅当该页 `page_image_sha256` 与 coverage 条目一致、处置为 `ACCEPTED`、且存在至少一条校验过的 `PAGE_REVIEW_VISUAL` locator（摘录哈希=localized_text）时，才允许 `ocr_page_id is None`。其他页继续 fail-closed。

3. **继承键改为内容身份**  
   用 `(source_document_version_id, page_number, page_image_sha256)`，并规定：活动完整修订快照必须等于比较基线，否则确认阶段拒绝，而不是处理中途抛 `EVIDENCE_INHERITANCE_INVALID`。

4. **`evidence_reprocess` 政策显式化**  
   要么同样跳过外部 OCR，要么明确它是唯一 OCR 回门，且不得被新上传默认政策静默继承。

5. **`mtplx_owned_server` 保持隔离**  
   在没有硬件租约、空闲端口、cancel→unload、以及与 GUI 8002 的互斥策略之前，不要接入 `page_review_harness` / admission / runtime。

---

### 4. Uncertainty

- 未跑测试、未启动模型、未读生产库/原件、未做浏览器验收。
- 未证明当前 MTPLX GUI `/health` 是否满足 owned server 的 `launch_id`/`pid`/`vision.enabled` 形状；`--app-launch-id` 是否被已安装二进制接受。
- 未穷尽前端是否把“基础修订 READY + 快照 PROCESSING”展示为可开页审；后端权威路径显示不能。
- `create_or_reuse_from_source` 在 `vision_scope is not None` 的旧观察分支未传递 `include_visual_sources`（349–387 行）。coverage 路径 `attachments=()`，一般不触发；仍是潜伏不一致。
- 空 `effective_text_sha256` 碰撞是否被某消费者当页身份使用，只检查了规划/适配器主路径，不是全库证明。

---

### 5. 对 Codex 的异议、决策点和有界问题

**异议**

1. “最小修改”假设“跳过外部 OCR + 规范化放行无 OCR 页”即可去前置依赖。源码显示真正前置依赖是**完整修订 OCR 闭包 + 活动完整修订权威**，这两处未改。
2. 把 `include_visual_sources and coverage_id` 当作安全网，覆盖不到“尚未能做页审”的新上传，也覆盖不到 coverage 中未 ACCEPTED 的页。
3. 新上传一律写入 `preparation_policy`，没有按媒体类型/扫描页开关；native 页仍造 OCRPage，扫描页则造成“既无 native 又无 OCR”。
4. `mtplx_owned_server` 与本次去 OCR 上传链无调用关系；把它当作已接线的取消/所有权方案会误导。

**请 Codex 裁决**

1. 扫描件完整修订是否允许 `ocr_page_id=None`，还是页审改走基础修订？  
   **暂定安全路径：** 在二选一落地前，不把新政策用于真实病例上传。
2. `evidence_reprocess` 是保留 OCR 回门，还是与新上传同样跳过？  
   **暂定：** 视为仍会打 oMLX 的旧路径，不得当作“产品已去 OCR”。
3. 同内容重传应复用旧 OCR，还是强制只走页图双读？  
   **暂定：** 当前实现会复用旧 OCR；若产品要去 OCR，这是行为回归。
4. owned MTPLX 是替换 GUI 8002，还是只在空闲端口拉私有进程？  
   **暂定：** 保持未接线；现页审继续走 HTTP 客户端 + 进程内 admission。

**有界问题（会改变结论）**

1. 新上传是否必须在**无任何 OCRPage** 的情况下激活资料并启动双 VLM？若是，当前完整修订门禁是发布阻断；若否，本政策范围被说大了。
2. 混合文档（部分 native OCRPage、部分扫描无 OCR）是否允许进入完整修订？当前闭包是全页一刀切，混合同样失败。
3. 页审 coverage 是否必须全页 `ACCEPTED` 才能规范化？当前选择器不是；若产品要求全页采信，`allow_image_only` 还需加这道门。

**Resume point：** 若 Codex 选择方案 A 或 B，下一轮只核对那一套闭包/权威改动是否闭合本报告第 2 节的断链，不必重扫全库。
