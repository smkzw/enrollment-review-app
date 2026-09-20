Trellis SessionStart ✓ — 已加载。现在开始只读证据审阅。

Let me read the initial read set.

Now the services layer.

Now I'll trace adjacent consumers of reading views, bboxes, and rotation inputs.

Bash is unavailable in this session (permission denied, non-interactive). I'll continue with read-only file tools and will note this in the report.

Critical lead: the rotated view bytes are never stored in the artifact store, yet the request receipt re-verifies by SHA. Let me verify.

Confirmed `read_by_sha` fails hard when the artifact is absent. Let me check whether anything ever stores the view image.

Now checking the source-side metadata (PDF rotation handling) and image transport.

I have enough source evidence. Writing the report.

# Conference Output: enrollment-reading-view-integration-20260916 - evidence_single_object

## Output

**Role**: `evidence_single_object` · 只读审阅 · 未编辑任何产品文件 · 未调用模型 · 未读工作树外临床资料 · 未写 runner 报告路径
**Method**: 直接阅读 initial read set 全部 14 个文件，并沿下列相邻消费者/守卫独立核验：`app/services/page_request_receipt.py`、`app/evidence/artifacts.py`、`app/evidence/page_processor.py`、`app/evidence/render.py`、`app/evidence/segmentation.py`、`app/storage/page_review_repository.py`、`app/services/page_review_execution.py`、`app/services/page_review_coverage_selection.py`、`app/services/targeted_page_review_detail.py`、`app/projections/page_review_visual_locators.py`、`app/llm/page_review_format_repair.py`、`app/llm/page_reader_capabilities.py`、`app/llm/page_review_admission.py`、`app/llm/independent_vlm.py`、`app/domain/contracts/common.py`、`app/domain/contracts/evidence.py`、`frontend/src/api/page-review/*`、`tests/v2/evidence/test_pdf_native_coordinates.py`。
**标签**：`FACT` = 已在该行号读到 · `INFER` = 我的推导 · `REC` = 建议 · `UNCERT` = 本次无法证实。**下列所有"已验证缺陷"均为代码路径贯通核验，不是临床/视觉验收，也不是我代替 Codex 的最终接受。**

### 工具与证据失败（不隐藏）

- **Bash 工具在本会话被拒（non-interactive，权限不可用）**：因此本次**没有执行任何测试**、没有 `git log/diff`、也没有运行"可选的内存确定性检查"。所有结论来自源码逐行阅读与调用链追踪，V-1 属"路径贯通核验"而非"已复现的运行证据"。若 Codex 需要 1 个可执行的复现证据，请指派一次带 Bash 的会话或授权 `evidence_reading_view` 单测（不得新增测试文件的边界下，可用现有 harness 走一次内存小图）。
- 我读了同题历史会议产物 `runs/conference/enrollment-reading-view-review-20260916/evidence_single_object.md`（**仅作上下文，非权威**）；其中被我引用的每条结论都已对照当前源码重新核验，并在下文标注为 FACT 或已修正。

---

## A. 已验证缺陷（按影响排序）

### V-1（BLOCKING，VERIFIED）旋转阅读视图的模型调用**必然失败**，且失败原因被误记为"端点故障"、审计回执被跳过

`reading_rotations` 一旦生效，该页两张主读都读不到任何模型，页面最终落入 `failed_pending_reread`。

证据链（每一环均 FACT）：

1. `app/services/page_request_receipt.py:24-25`：回执写入前要求
   `artifact_store.read_by_sha("page_image", sha256(发送字节)) == 发送字节`。
2. `app/evidence/artifacts.py:105-106`：该工件不存在时抛 `ArtifactStoreError("工件 page_image/<sha> 不存在")`（**不**回退、**不**降级）。
3. 全仓 `put("page_image", …)` 只有一处写入者：`app/evidence/page_processor.py:317`（渲染出的原始页图）。我枚举了 `app/` 下所有 `artifact_store.put(` / `store.put(` 调用点（`page_processor.py:317,329,342,345`、`page_request_receipt.py:30`、`page_review_job_executor.py:137,146`、`judgment_search_job_executor.py:137,141`、`predicate_binding_job.py:123`、`judgment_content_job.py:175`、`binding_qualification.py:151`、`fact_normalization_executor.py:1034`、`ocr_adapter.py:257,977`、`judgment_search_artifacts.py:96`）——**没有任何调用把派生旋转图写入工件库**。
4. 旋转图只在内存中生成：`app/services/page_review_job_executor.py:97-103`（`make_reading_view(...)` → `image = view.image_bytes`），随后进入 `PageVisionInput(image_bytes=image)`（`:104-107`）。
5. 发送的就是这些字节：`app/llm/page_review_harness.py:410-417` 解码 data URL 并**要求** `sha256 == view.image_sha256`；`app/llm/independent_vlm.py:277-279` 是**无损透传**（`PageVisionInput.media_type` 默认 `image/png`，见 `independent_vlm.py:132`）。因此第 1 步算出的必然是 **view 哈希**。
6. 抛点在被 try 保护之前：`app/services/page_review_job_executor.py:110-111` 先 `store_page_request(...)`，`try` 只包住 `await self.completion(...)`（`:113-114`）→ 异常逃出，**不写 `error_receipt_sha256`**，`attempts` 保持空。
7. 失败被归类成端点故障：`page_review_harness.py:616-622`（`ArtifactStoreError` 无 status_code、文本不含过滤标记 → `"endpoint"`）→ `:697-713` 在配置了 `fallback_base_url` 时还会**多发一次注定失败的重试** → `PageReviewHarnessError(failure_kind="endpoint")`。
8. 由此被当成可重试的临时故障：`page_review_job_executor.py:170-173`（attempt 1 → `StepFailure(retryable=True, detail="原件暂未完成判读，将重试")`）→ 终次 `:178-182` 落 `lane_failure{failure_kind:"endpoint"}` → `:199-212` 产出 `failed_pending_reread` → UI 状态 `needs_reread`（`app/services/page_review_status.py:31,37,42`）。

影响：① 该功能当前**不可用**（不是概率性失败，是确定性失败）；② 用户看到的是"部分资料需要重新判读"，而"重新判读"（V-2）同样会失败；③ 项目"保留可复验来源"的边界在这一路径上**最关键的证据**（"模型实际看到的字节"）恰恰缺失，且无任何回执可查。
测试覆盖：`tests/` 下 `reading_rotations` 命中为 **0**（全仓 grep 只命中 app 与会议材料；`rotation=` 命中全是 `CoordinateFrame.rotation`，无关）。这解释了为什么至今未被发现。

**最小修复（3 处改动，保持"来源不可变 + 派生视图可溯源"）**
1. `app/evidence/artifacts.py:20-23`：在 `ARTIFACT_KINDS` 增加派生类别，例如 `"reading_view_image"`（**不要**把派生图塞进 `page_image`，该模块文档 `:19-22` 明确要求分开保存）。
2. `app/services/page_review_job_executor.py:97-103`：`view_artifact = self.artifact_store.put("reading_view_image", view.image_bytes)`，把 `(kind, sha)` 传下去。
3. `app/services/page_request_receipt.py:9-26`：签名增加显式 `image_artifact=(kind, sha256)`，用 `read_by_sha(kind, sha)` 复核；同时把回执里硬编码的 `"page_image_sha256"`（`:26`）改为带类别字段（否则旋转读的回执会把 view 哈希标成"原件页哈希"，属审计标签错误）。
   调用点同步：`page_review_job_executor.py:111`。
**不推荐的替代**：靠"重新推导视图字节"来验证——`reading_view.py:113-115` 用默认 PNG 编码，而 `READING_VIEW_VERSION`（`:17`）不含编码器版本，`page_review_execution_versions()`（`page_review_job_service.py:42-48`）也不含 Pillow 版本；一旦编码器字节行为变化，历史记录的 `view_image_sha256` 将无法复验，与"不可变完整证据快照"相冲突。

### V-2（HIGH，VERIFIED）已完成的判读**无法修正或新增阅读方向**；唯一替代路径会撞上"唯一可用判读"策略

- `FACT` `app/services/page_review_job_service.py:164-176`：仅当调用方 `reading_rotations is None` 时才继承前次方向。
- `FACT` `app/services/page_review_recovery.py:33-38`：`comparable != payload` → `PageRereadNotReady`。因此"把 90° 改成 180°"、"给无方向的任务补一个方向"都会 409（"前次判读与当前资料、条款或处理配置不一致，不能局部重读"）。逐记录的方向一致性检查（`:69-72`）是正确的，但它只在"方向已经被允许进入"之后才生效。
- `FACT` `page_review_recovery.py:56-57`：即使方向不变，前次判读**必须已有失败页**才允许重读（"前次判读没有读取失败的页面，无需重读"）。干净任务上的方向修正**永远**进不了重读路径。
- `FACT` 于是只剩"新建完整任务"。但新任务产出第二条 coverage，其 `subject/episode/snapshot/revision/clause_pack` 与前一条相同、`execution_versions` 相同（`page_review_job_service.py:42-48`，方向不在其中）、且二者无 `predecessor_coverage_id` 关系 → `app/services/page_review_coverage_selection.py:32-65` 得到 2 个候选 → `PageCoverageNotReady` 409 "当前资料没有唯一可用的判读结果，请核对资料处理记录。"（这条对"任何重复整轮判读"都成立，属既有策略；**方向无法在其中起区分作用**是本次集成引入的具体缺口）。
- `INFER`：用户为"方向错了"付出的代价是卡在 409，且提示语指向"资料处理记录"，与真实原因无关。

**REC（最小、复用既有谱系机制）**：把"方向修正"定义为一次显式重读操作——(i) 允许 `plan_page_reread` 的唯一差异为 `reading_rotations`；(ii) 该情形下放宽"必须有失败页"前置（注意 `app/storage/page_review_repository.py:297-298` 的 `_verify_coverage_scope` 会再次拒绝"前次无失败页"，必须同步放宽为"方向变更或有失败页"）；(iii) 仅对方向未变的页复用回执（现有 `:59-81` 逻辑天然支持，只需按页比较 `expected_rotation`）；(iv) 让既有的 supersede 机制（`coverage_selection.py:44-57`）自动淘汰前一条 coverage。**需要 Codex 先裁定这是否是产品要支持的动作**——若不支持，必须把 409 文案改成"方向变更需重新建立资料处理修订"，而不是现在的误导性文本。

### V-3（MEDIUM，VERIFIED）准入/回执阶段的失败不留可查原因（V-1 的通用面）

`FACT` `app/services/page_review_job_executor.py:110-145`：`try` 只包住 `self.completion(...)`。任何由 `store_page_request` 抛出的前置失败（工件缺失、data URL 前缀不合法、`base64` 失败）都不会写 `raw_response` 回执，`attempts` 为空，最终 checkpoint 只留 `lane_failures[{lane, "endpoint"}]`。
**REC**：把 `store_page_request` 移入 `try`（或包裹整个函数体），让准入失败也留下 `error_type/error_causes` 回执；`_failure_kind` 对 `ArtifactStoreError`/`ValueError` 应映射为独立类别（如 `admission`），不要并入 `endpoint`，否则"重试"语义是错的。

### V-4（LOW-MEDIUM，VERIFIED 的不一致 + HYPOTHESIS 的后果）送给模型的视图身份沿用了 `page_image_pixels` 这个名字，且视图源尺寸未与页产物帧交叉校验

- `FACT` `app/evidence/reading_view.py:59-71`：identity 同时含 `coordinate_space:"page_image_pixels"`、`source_width/source_height`（原页）、`view_width/view_height`（视图）。同一身份被放入提示（`page_review_harness.py:493`）。
- `FACT` `page_review_harness.py:491-493`：同一 JSON 里还有 `image_coordinates:{"space":"page_image_pixels", width=视图宽, height=视图高}`；系统提示（`:458-459`）要求 bbox 用"当前图片"像素。**同一个空间名对应两组尺寸**。
- `FACT`（现有缓解，确实有效）：schema `maximum` 按视图尺寸钳制（`:421-423`）＋ `page_review_format_repair.py:137-147` 按视图尺寸越界检查＋持久化后按 `reading_view.source_*` 再查一次（`app/domain/contracts/page_review.py:298-305`）→ **整轴互换会被拦住**。
- `HYPOTHESIS`：页内小范围框（两种空间的合法区间重叠）若被模型按原页尺寸给出，会被当成视图坐标再反演一次，得到错误但"合法"的框。当前无消费者读取该 bbox（视觉定位一律 `bbox=None, coordinate_frame=None, precision=page_excerpt`，`app/projections/page_review_visual_locators.py:102-104`），故目前不可观测。
- **REC（廉价）**：把模型可见 identity 里的字段改名为 `view_image_pixels`（或从模型可见载荷里移除 `source_*`，仅保留在持久化绑定中），并 bump `READING_VIEW_VERSION` + prompt 版本；持久化绑定的形状不必改。
- **REC（廉价加固，历史审阅 F-4 仍未闭环）**：在 `page_review_job_executor.py:96-103` 读取页图后，断言 `reading_view.source_width/height == PageArtifact.page_width/page_height`。今天这是**潜在**缺口（无实时消费者），但它决定了"视图源帧 = 产品唯一规范页帧"这一不变量是否被机器保证。

---

## B. 已验证正确（避免 Codex 重复排查，也给回归锚点）

| # | 结论 | 证据 |
|---|---|---|
| G-1 | 反演数学正确（三角度均按连续像素边，非像素中心）：90° `(y0, h−x1, y1, h−x0)`、180° `(w−x1, h−y1, w−x0, h−y0)`、270° `(w−y1, x0, w−y0, x1)` | 我独立推导 view(x,y)→source 映射后与 `app/evidence/reading_view.py:83-91` 逐项一致（`FACT` 代码 / `INFER` 推导） |
| G-2 | PIL 转置映射正确（`ROTATE_*` 为逆时针，故 90→`ROTATE_270`、270→`ROTATE_90`） | `reading_view.py:108-116` |
| G-3 | 视图进入记录身份并被记录级校验：`reading_view` 参与 `page_review_id` 哈希；记录要求 `source_page_artifact_id==page_artifact_id`、`source_image_sha256==page_image_sha256`，并按其源尺寸复检 bbox | `page_review_harness.py:790-814`；`app/domain/contracts/page_review.py:291-305` |
| G-4 | 对账要求两主读视图完全相同，否则拒绝合并 | `app/domain/page_reconciliation.py:67-68` |
| G-5 | 定向复核（targeted）方向传播正确：从原任务冻结的 `reading_rotations` 取方向、并要求已存主读记录的 `reading_view.clockwise_degrees` 与之一致；方向透传进补读载荷；辅助记录不落库 | `app/services/targeted_page_review_jobs.py:69-72,84-89`；`app/services/targeted_page_review_executor.py:116-119`；`page_review_job_executor.py:184-191` |
| G-6 | 续跑方向传播正确：`resume` 用冻结方向重建载荷并要求 payload 全等；无该键的历史任务仍能比对相等（空方向不写键） | `page_review_job_service.py:212-225`、`:132-133` |
| G-7 | 载荷校验拒绝未知页/非直角方向；未旋转路径行为不变（回执按 `page_image` 复核成功；`reading_view=None` 且 `exclude_if` 保证历史字节稳定） | `page_review_job_service.py:128-131`；`page_review.py:246`；`page_request_receipt.py:24` |
| G-8 | `PageReviewInput` 正确拒绝 0° 视图与哈希不符 | `page_review_harness.py:111-127` |

对历史审阅两点的**结论更新**（独立核验，非引用）：该轮 F-7 担心的"payload 多出 `reading_view` 键导致 `getattr` 无默认值 AttributeError"**在当前集成中不成立**——方向放在独立 `reading_rotations` 映射里，`page_review_recovery.py:73-77` 的 `binding` 仍只含四个既有页字段。该轮 F-10（EXIF）已在本分支被渲染层处理（见 C 节），不再是未闭环项。

---

## C. 自动图片方向：最小可行接续路径（按我的独立判断排序）

### C-1 原生元数据的覆盖能力（FACT）

| 类别 | 现状 | 证据 |
|---|---|---|
| 带 EXIF Orientation 的拍照/扫描图 | **已被应用**（渲染时 `ImageOps.exif_transpose`） | `app/evidence/render.py:122-126`（渲染器 v3/v4；当前 `RENDERER_VERSION = "slice4.3/render/v4"`，`:31`）。分段分析另有一处应用（`app/evidence/segmentation.py:195`），但单页路径原样返回原字节（`:222`），拼接路径用已摆正的图重编码 PNG（`:184`）——两条路径都**只应用一次**（`FACT` 代码 + `INFER` 无重复应用） |
| PDF `/Rotate` | **已被渲染器应用**（页图即"阅读朝向"像素） | 本仓自有契约测试以 `rendered_page.rotation_matrix` 把未旋转坐标映射后与**渲染 pixmap** 比较并要求重叠 ≥0.5（`tests/v2/evidence/test_pdf_native_coordinates.py:112-162`）——该断言的语义即"pixmap 是已旋转显示朝向"（`INFER`，来自该测试自身的合同） |
| **无元数据、像素本身侧躺**（扫描仪侧向进纸 JPEG/TIFF 无 EXIF；或 PDF 中扫描图被旋转放置而页无 `/Rotate`） | **无任何确定性信号** | 全仓 `exif/Orientation` 命中仅 `render.py`、`segmentation.py`；OCR 路由明确为 text-only、不产生坐标（`app/evidence/ocr_adapter.py:23`）；未接入任何本地方向模型（`UNCERT` 仅限"语料中此类页占比"——须读临床原件，超出我的边界） |

**结论**：原生元数据可覆盖 3 类中的 2 类，且这两类在本次集成中**已经不需要用户预处理**；剩下的"侧躺像素"类无法从元数据解决。按用户要求，我**不**用长宽比推断方向（并注意到 `segmentation.py:203-208` 已有基于 `min_stitched_page_aspect_ratio` 的启发式，但那用于拼接判定，绝不能被复用到方向判定上）。

### C-2 最小实现建议（两级，按风险递增）

**第 0 级（必须先做，且是 C-3 的前置）**：修 V-1。否则任何方向一旦被选中，该页必然失败——这会让方向功能"看起来像模型/端点问题"。同时补上 V-2 的方向修正通道，否则第一次方向选错就等于把项目卡死。

**第 1 级（无模型、无新载荷形态，最小可用）**：把"方向"变成**显式人工选择**而不是推断。
- 后端已具备：`reading_rotations` 入参（`app/api/v2/page_review.py:22`）、载荷冻结与校验（`page_review_job_service.py:128-131`）、记录级绑定（G-3）。
- 前端缺：`FACT` 全仓 `reading_view|reading_rotations|clockwise_degrees` 在 `frontend/` **零命中**（我只在前端找到 `page-review-jobs` 的提交/续跑与 conflicts 端点，`frontend/src/api/page-review/pageReviewHttp.ts:55`）→ **当前只有直接调 API 才能指定方向，产品界面完全没有入口**。
- 最小交互（满足"用户不必预处理原件"）：在页图上提供 0/90/180/270 的**应用内**方向选择，提交时带上 `reading_rotations`；至少要在复核视图上把"模型当时看到的朝向"如实回显——最省的**无损**做法是用记录的 `reading_view.clockwise_degrees` 对既有页图端点（`app/api/v2/evidence_processing.py:453-464`、`app/services/targeted_page_review_detail.py:109-110` 目前都指向**原始**页图）做 CSS 变换，不需要新字节；若采纳 V-1 的落盘修复，也可直接提供派生视图。
- 必须与 AGENTS.md 的"分离判定与缺口原因"一致：**"方向未经确认"必须是一个具名缺口状态**（责任人/动作/可接受证据/到期阶段），不能默默按 0° 处理。

**第 2 级（有界模型推断，我认为**值得做**，但必须满足 5 条约束）**：
- 复用现有产品模型（两条主读路由之一 + `direct_completion`），**不要**新建模型或新 provider：`require_page_reader_routes` + `PageReviewAdmission` 已可复用，输出额度上限 65536–131072 是**上限而非要求**（`page_reader_capabilities.py:10-11`，`page_review_harness.py:179-180`），一个小 JSON 答案不会被它阻止；代价是"每页多一次 VLM 调用"。
- **时序约束（关键，我最想提的架构点）**：方向必须在**入队前冻结**。因为 `reading_rotations` 在载荷内，而载荷决定 job 幂等键（`page_review_job_service.py:187`）、执行期版本/路由校验（`page_review_job_executor.py:46-55`）、续跑全等（`:224`）与局部重读全等（`page_review_recovery.py:37-38`）。因此正确形态是"**独立的方向提案步骤/任务**（一次调用、可审计、落盘），产出被 plan 阶段读取后冻结进 `reading_rotations`"，与现有 `page_association_sources` 在 plan 期冻结的模式一致；**不要**在 read 步内动态决定方向，否则等于让后续处理悄悄改写已冻结的依据。
- 必须记录 `direction_source`（如 `model_probe:<lane>/<provider>/<model>` + 响应哈希），使"阅读依据"可追溯（这也是历史审阅 D5 的建议，仍未实现）。
- 低置信/候选人分歧 ⇒ **不得**自动采用：按缺口处理并要求具名责任人，绝不默认 0°。
- 语义边界：本轮非目标明确排除"未证实就让源 bbox 视觉可信"，因此模型自报方向只作为"呈现依据"的显式记录，**不得**被当作 bbox 的认证依据。
- `UNCERT`：模型对 90/270 侧躺页的实际识别质量**我无法在本次证实**（禁止调用模型）。因此建议把"一次有界实测（非临床或授权样本）"作为启用推断的前提，而不是假设可用。

---

## D. 我最重要的反对意见（面向 Codex）

1. **反对"功能已集成完毕"这一读法**：`reading_rotations` 是公开 API 参数（`app/api/v2/page_review.py:22`），但一旦使用，整页必然失败（V-1），且失败被伪装成端点抖动。在 V-1 修复前，任何"已支持旋转读"的表述都不成立；本轮应把 V-1 视为**启用前必须清除的阻塞项**，而非改进项。
2. **反对用"重试/重读"消化方向问题**：`PageReviewJobExecutor:170-173` 把工件缺失归入可重试端点错误，`page_review_recovery` 又只允许"有失败页"的前次重读（V-2）。这两点叠加会让用户以为"再跑一次就好"，实际必然复现。
3. **反对把派生图混入 `page_image` 类别**：`app/evidence/artifacts.py:19-22` 明确"页图/原生文本/坐标/请求/响应分开保存"。修 V-1 时应新增派生类别，而不是放宽语义。
4. **反对以"无 bbox 消费者"为理由简化实现**：当前确实没有消费者（`page_review_visual_locators.py:102-104`），但记录是不可变追加（`page_review_repository.py:46-51,78-84`）。一旦未来某消费者读取 bbox，V-4 的"错空间但合法"框会变成静默污染；现在用一句改名 + 一条断言就能把该风险压住，成本远低于事后追溯。
5. **提醒一个必须显式裁定的产品动作**：V-2 的方向修正要么被支持（并修 3 处守卫），要么必须明说"需新建资料处理修订"。含糊处理会让"方向"成为不可回退的决策。

---

## E. 决策点与有界问题（可在同会话内回答）

| # | 决策 | 我的建议 |
|---|---|---|
| D1 | V-1 修法：新增派生工件类别 vs 不加类别的弱校验 | **新增 `reading_view_image`**，回执记录 `(kind, sha)`；弱校验会永久失去"模型实际看到什么"的可复验证据 |
| D2 | V-2 是否把"方向修正"作为受支持动作 | 若"是"：按 A-V-2 的 4 步最小改动，并同步放宽 `page_review_repository.py:297-298`；若"否"：改 409 文案并写明需新修订 |
| D3 | V-4 是否改名 `coordinate_space`→`view_image_pixels` 并 bump `READING_VIEW_VERSION` | **建议改**（模型可见名与尺寸对不上是真实歧义）；持久化绑定形状保持不变 |
| D4 | 方向推断是否复用两条主读路由（每页 +1 次调用） | **可以复用**；但必须（a）入队前冻结、（b）记录 `direction_source`、（c）不确定即缺口、（d）先做有界实测再启用 |
| D5 | 前端方向入口与"模型当时朝向"回显 | 先做**只读回显**（CSS 变换驱动，零新字节），再做选择控件；注意 `frontend/` 目前零命中 |
| D6 | `view_image_sha256` 编码器版本耦合（历史 F-9） | 若采纳 D1 落盘，此耦合自然消解；否则需在 identity 增加 `view_renderer_version` |

**有界问题**
1. （V-1）是否授权我按 D1 给出 3 处精确补丁？（我未改任何文件。）
2. （V-2）方向修正是否属产品功能？若属，是否授权同时放宽"必须有失败页"并在 UI/API 文案中区分"方向变更"与"读取失败"？
3. （C-1）语料中"侧躺像素且无 EXIF/无 `/Rotate`"的页是否存在（不读临床原件的替代证据：任一无患者标识的样例页元数据快照）？若不存在，我建议**不启动** C-2，只做 C-1 的第 1 级。
4. （C-2）方向提案是否应为**独立 job type**（我更倾向）还是在 plan 期同步调用一次？前者可审计、可重放、与冻结语义一致；后者更快但会引入一次无回执的模型调用。
5. （V-3）是否允许把 `_failure_kind` 增加 `admission` 类别（影响既有 failure_kind 词表与 UI 文案映射）？

---

## F. 不确定性与边界

- **未做**：未运行测试（Bash 被拒）、未 `git diff` 核对本分支改动范围、未调用任何模型、未读工作树外临床资料、未写 runner 报告路径、未编辑产品文件。
- V-1 是**代码路径贯通核验**：每一环都有行号，但**没有运行复现**；若需要"可执行证据"，请在同会话内授权一次 Bash（内存合成小图 + 现有 harness 单测即可，不新增测试文件）。
- `INFER` 未证实的部分：PDF `/Rotate` 由渲染器应用（依据本仓测试的断言语义，而非我运行过）；模型对侧躺页的实际识别率；"侧躺无元数据页"在真实语料中的占比。
- `UNCERT`：Pillow PNG 编码字节跨版本确定性（影响 D1 与 D6 的选择）。
- 本文任何内容都**不构成**临床、监管、视觉或生产验收；最终综合、裁定与交付仍归 Codex。
