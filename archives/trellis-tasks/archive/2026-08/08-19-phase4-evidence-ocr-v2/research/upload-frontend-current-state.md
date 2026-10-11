# Research: 受试者上传、任务 API 与前端入口现状

- Query: 当前是否已有受试者、审核节点和上传 stub；增量/全量上传应落在哪些页面与 API；宽屏中文医学监查工作流应如何呈现预览、去重、影响范围和错误恢复；哪些现有组件可以复用。
- Scope: internal
- Date: 2026-08-19

## Findings

### 结论摘要

1. **受试者与审核节点已有，但目前是只读 fixture 链路。** 前端已有受试者列表、Patient Profile、按阶段选择的 `ReviewEpisode` 和入排工作台；合同与后端领域层也已有 `Project`、`Subject`、`ReviewEpisode`、`SourceDocumentVersion`、`EvidenceSnapshot`、`EvidenceSpan`。但通用前端仓储仍固定为 `kind: "stub"`，只提供查询方法，没有创建受试者、创建审核节点、上传、预览、提交或恢复等写操作（`frontend/src/api/stubRepository.ts:1-5,37-54,94-189,202-209`）。
2. **没有受试者证据上传 stub 或真实 API。** fixture 已表达 `full` / `incremental`、`prior_snapshot_id`、文件哈希和任务事件，但没有上传预览、去重决策、提交结果或候选快照合同。`app/api/v2` 当前只挂载通用持久任务和方案解构路由（`app/api/v2/app.py:23-43,64-87,112-116`），没有 subject、review episode、evidence upload、snapshot、source document 或 OCR 路由。
3. **任务基础设施是真实的，任务页面不是。** 后端已有持久 Job 的创建、状态、取消、失败范围重试和 SSE 续订（`app/api/v2/jobs.py:51-75,78-133,136-178`）；前端也已有 SSE 适配器（`frontend/src/api/jobEvents.ts:1-75`）。但当前 `/tasks` 使用 fixture 和 `sessionStorage` 演示，页面明确说明不会实际运行文字识别或审核（`frontend/src/pages/TasksPage.tsx:1-6,188-248,302-304`）。
4. **Phase 4 的正确产品归属是“受试者与资料”，不是“任务与系统”。** `/subjects` 应负责选择受试者、审核节点、上传模式和提交前预览；`/workbench` 提供当前节点的补充资料快捷入口；`/tasks` 只负责提交后的后台处理、恢复、取消和结果跳转。
5. **应采用业务专用的两阶段 API。** 浏览器先创建上传预览，再显式提交；服务端应用服务负责校验 subject/episode/snapshot 关系、定义任务步骤并创建持久 Job。不要让浏览器直接调用通用 `POST /api/v2/jobs` 自行声明 `job_type`、payload 和步骤图。

### Phase 4 已冻结的边界

- Phase 4 要求显式区分增量/全量上传并提供预览；按文件内容哈希去重；全量上传创建新 `EvidenceSnapshot`；OCR 缓存键为内容哈希、页码和模型/参数版本（`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md:123-134`）。
- 退出门槛要求同文件不重复 OCR、文件或模型变化必须重跑、增量只影响保守关联范围、全量保留旧快照、校对不覆盖原 OCR、定位精度不得伪造（`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md:136-142`）。
- 最终设计要求同一受试者明确选择上传模式；增量显示重复、已合并、新增和受影响规则；全量显示新旧快照关系；Job 详情按页、文件、受试者和节点显示失败原因、影响范围和重试粒度（`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:384-394`）。
- 工作台目标是 1080P 至 4K 最大化桌面三分栏，不新增移动端或窄屏交互分支（`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:364-374`）。

### 当前能力清单

| 能力 | 当前状态 | 证据与判断 |
|---|---|---|
| 受试者列表与选择 | fixture-backed UI | `/subjects` 已显示受试者列表，并通过 `subject`、`stage` 查询参数保持上下文；数据来自只读 stub。 |
| 审核节点 | fixture + domain/storage groundwork | `ReviewEpisode` 已包含阶段、快照和 revision；页面可切换节点，但没有真实创建/更新 API。 |
| Patient Profile | fixture-backed UI | 已有当前阶段、快照、主题泳道、完整明细和证据覆盖；适合作为上传主入口的宿主。 |
| 受试者证据上传 | 不存在 | `/subjects`、`/workbench` 无文件输入、模式选择、预览或提交动作；通用仓储无 mutation。 |
| 上传模式模型 | 合同/fixture 已表达 | `SourceDocumentVersion`、`EvidenceSnapshot` 含 `upload_mode`，增量快照含 `prior_snapshot_id`；只是展示数据，不是上传行为合同。 |
| 方案 DOCX 上传 | 真实但属于另一领域 | `ProtocolUploadPanel`、`protocolWorkbenchHttp` 和 `/api/v2/protocol/deconstructions` 可作为交互/适配器范式，不能充当受试者资料 API。 |
| Job 状态机与 SSE | 真实基础设施 | 后端持久 Job、Step、Checkpoint、Event 及前端 SSE 适配器已存在。 |
| `/tasks` 任务记录 | fixture + 会话演示 | 可复用视觉语言，不可作为持久任务接入完成的证据。 |
| 原文件页图预览 | 不存在 | `EvidenceDialog` 只显示定位元数据和 OCR 摘录，并明确当前原型没有原始页图。 |
| 上传去重/候选快照预览 | 不存在 | schema、repository、API 和 E2E 均未发现对应请求/响应模型。 |
| OCR page / correction persistence | 未发现完整落点 | 有 `EvidenceSpan`、文档版本和快照记录；未发现命名明确的 `OCRPage`、`CorrectionRecord` 合同/表或受试者证据应用服务。 |

### 页面落点

#### 主入口：`/subjects`

在选定 `subject + stage` 后，于 Patient Profile 顶部上下文区提供“上传资料”命令。这里已经展示受试者、当前节点和当前快照，是最不容易串受试者或串阶段的位置。入口必须携带 `subject_id`、`review_episode_id`、当前 `evidence_snapshot_id` 和 `episode.revision`，不能只依赖页面上可见的受试者编号。

建议增加一个无一级导航项的上下文路由：

`/subjects/upload?subject=<SubjectId>&episode=<ReviewEpisodeId>&mode=<incremental|full>`

它可承载完整的文件选择、预览、确认和提交流程，同时返回时保持原受试者与阶段。现有路由表已有无一级导航的上下文页面 `/projects/new`，可沿用该模式（`frontend/src/app/routes.tsx:43-76`）。若实现为 `/subjects` 内部工作区，也应把 `panel=upload` 写入 URL，确保刷新和返回可恢复。

#### 次入口：`/workbench`

在当前 `episode` 的证据栏提供“补充当前节点资料”，跳转到同一上传工作区，默认选择“增量上传”。工作台已有受试者、阶段、方案和快照上下文，因此适合发起有明确影响范围的补充资料；不能另造一套上传状态机。

#### 处理与恢复入口：`/tasks`

上传提交后跳转 `/tasks?job=<JobId>`。任务页只显示持久后台状态、页/文件粒度进度、失败原因、影响范围、取消和失败范围重试，并可返回对应受试者/节点。文件选择和“全量/增量”决策不应放到任务页，因为任务页缺少稳定的临床上下文且现有交互只是演示。

#### 不建议作为主入口

- `/board`：可以从节点单元格深链到该受试者/节点的上传工作区，但不应直接接收上下文不明确的文件。
- 一级新导航：不需要；“受试者与资料”已经承担资料入口语义。
- Phase 4 批量跨受试者上传：当前 Phase 4 计划聚焦同一受试者的证据快照。跨受试者批量解析需独立映射/确认流程，不能通过文件名猜测归属，也不应提前混入本切片。

### 建议 API 边界

#### 受试者和审核节点查询/建立

- `GET /api/v2/projects/{project_id}/subjects`
- `POST /api/v2/projects/{project_id}/subjects`
- `GET /api/v2/subjects/{subject_id}/review-episodes`
- 审核节点应从已发布 WorkflowStage 确定性建立，不让客户端提交任意阶段字符串。若需显式创建，使用受限的业务命令，而不是通用 CRUD。

#### 两阶段上传

1. `POST /api/v2/review-episodes/{episode_id}/evidence-upload-previews`
   - multipart 文件；字段包含 `mode`、当前快照 ID、预期 episode revision 和幂等键。
   - 只做暂存、内容哈希、格式/页完整性检查、文档分类候选、重复识别、候选快照成员计算和保守影响估算。
   - 不改变 `ReviewEpisode` 的当前快照，不启动临床审核。
2. `GET /api/v2/review-episodes/{episode_id}/evidence-upload-previews/{preview_id}`
   - 用于刷新/重开时恢复预览及文件级结果。
3. `DELETE /api/v2/review-episodes/{episode_id}/evidence-upload-previews/{preview_id}`
   - 放弃暂存；只清理尚未提交且可再生的暂存对象。
4. `POST /api/v2/review-episodes/{episode_id}/evidence-upload-previews/{preview_id}/commit`
   - 再次校验 episode revision、模式、文件选择和用户确认。
   - 原子登记不可变文档版本/候选快照并创建服务端定义的持久 Job，返回 `snapshot_id`、`job_id`、`created`。
5. `GET /api/v2/review-episodes/{episode_id}/evidence-snapshots`
   - 展示历史、当前快照、候选快照及新旧差异。
6. `GET /api/v2/source-document-versions/{document_version_id}/pages/{page_number}`
   - 受控返回原页图/PDF 页或安全文件流；不得向前端暴露本地磁盘路径。

提交后的任务继续复用：

- `GET /api/v2/jobs/{job_id}`
- `GET /api/v2/jobs/{job_id}/events?after_seq=<n>`
- `POST /api/v2/jobs/{job_id}/retry`
- `POST /api/v2/jobs/{job_id}/cancel`

业务上传服务应在服务端固定 Job 类型、步骤依赖、最大尝试次数和可重试范围。当前通用 `POST /api/v2/jobs` 允许调用方传入任务类型、payload 和步骤图（`app/api/v2/jobs.py:51-67`），不宜直接暴露给受试者上传页面，否则浏览器会越过业务校验并拥有编排权。

### 宽屏中文医学监查上传工作区

#### 稳定上下文带

页面顶部持续显示：项目、中心、受试者编号、审核节点、方案版本、当前快照和上传模式。受试者与节点不可在提交过程中静默切换；切换时必须放弃或另存当前预览。所有状态用中文表达“发生了什么、影响什么、下一步做什么”，不展示 pipeline、模型名或内部日志。

#### 模式选择

使用分段控件而不是普通按钮：

- **增量上传**：保留当前快照中的已有资料，把本次新增/更新文件合入新快照；预览必须显示“沿用、重复跳过、新增、同名新版本”。
- **全量上传**：本次选定文件构成新快照的完整成员集；旧快照永久保留。提交前明确列出旧快照中本次未包含的资料，并要求确认“未包含只表示不进入新快照，不删除历史资料”。

#### 三分栏预览

1. **左栏：文件与分类。** 文件名、页数、来源方、资料日期、文档类别候选；状态至少包括新增、当前快照重复、历史重复、同名内容变化、格式不支持、页损坏、需确认。允许移除/替换失败文件。
2. **中栏：原件与识别预览。** 显示真实 PDF/页图；OCR 可用后与识别文本并列或切换。定位精度复用四级 `PrecisionBadge`；无 bbox 时只显示 `text_range`、`page_excerpt` 或 `page_only`，不得伪造高亮。
3. **右栏：候选结果与影响范围。** 显示新快照成员数、沿用/新增/重复/未纳入文件、预计 OCR 页数、缓存命中、受影响的资料要求/规则/投影和后续任务。Phase 4 尚未实现 Phase 5/6 的事实与判断时，应写“保守重算范围”或“预计影响”，不得宣称已经完成临床影响判断。

三栏使用可调 `minmax()` 网格，页面本身不横向滚动；长文件名、表格和页图只在各自组件内滚动。支持 100%、150%、200% 缩放，焦点从上传入口进入并在关闭预览后返回触发位置（`.trellis/spec/frontend/component-guidelines.md:19-33`）。

### 去重与快照语义

- 以文件字节的 SHA-256 作为内容身份；“同名”不能判为重复。
- 同一内容、同一页、同一 OCR 模型/参数版本命中缓存，不重复 OCR；模型/参数变化只使相应 OCR 派生结果失效。
- 同一内容已在当前快照中：显示“重复，不新增”，默认不重复加入。
- 同一内容只在历史快照中：底层 blob/OCR 可安全复用，但新快照仍需留下明确、受试者归属正确的成员关系与审计记录。
- 同名但哈希不同：视为新文档版本，预览新旧差异，不得当作重复覆盖旧文件。
- 同一批次中内容重复：只保留一个候选成员并展示重复来源；若元数据不同，要求用户确认归并方式。
- 去重缓存可跨快照复用计算结果，但**文档归属和快照成员关系不能仅凭全局哈希推断**。相同内容可能出现在不同受试者或节点，服务端必须校验 project、subject、episode 和访问范围。
- 增量快照的预览必须展示“合并后的完整成员集”，而不只是本次新增文件。全量快照不依赖前一快照，但必须保留新旧谱系和可比较历史。

### 影响范围

上传预览至少分别给出：

- 内容影响：新增、内容变化、重复跳过、全量时未纳入。
- OCR 影响：需新识别页、缓存命中页、需重识别页、失败页。
- 资料要求影响：依据文档分类/ReferencedDocument 的保守关联节点和要求。
- 审核影响：可能需要新 ReviewRun 的规则组件、当前投影 `stale` 范围，以及不受影响的既有结果。
- 历史影响：旧快照、旧 ReviewRun、旧报告和 ActionTransition 均不覆盖；后续资料不会静默改写早期节点结果。

Phase 4 只能确定文档、页面、分类和保守依赖范围；具体 ClinicalFact、Assessment 或 Action 的变化应由后续阶段产生并经门禁发布。无关上传不得自动关闭已有行动。

### 错误与恢复

#### 提交前

- 文件级校验失败留在预览中，说明原因、影响和恢复动作；可移除/替换单个文件，不必重选整批。
- 受试者/节点不匹配、episode revision 冲突、当前快照已变化、零个可接受文件、格式不支持、文件损坏或存储不可用均应阻止提交。
- 预览失效或被其他标签页更新时显示差异并要求重新生成，不能静默套用旧预览。

#### 提交后

- commit 先创建持久 Job；浏览器/SSE 断开不取消任务。页面重开后以 `job_id + last_event_seq` 恢复订阅（`.trellis/spec/backend/persistent-jobs.md:5-10,25-35`）。
- 每个文件/页步骤成功后写 checkpoint；部分失败保留已完成输出，只重试失败页/文件，不重新处理全批。
- 取消只在安全步骤边界生效，保留检查点与历史事件。
- 候选快照处理失败或取消时，不得替换 `ReviewEpisode` 当前生效快照；只在发布门禁成功后原子更新当前快照指针。
- 失败页关联的派生结果标为 `stale` 并显示“哪些结论暂不能视为最新”；不能把失败候选显示为当前已完成结果。
- 重复 commit 使用同一业务幂等键和同一请求应返回原 Job；同键异请求返回明确冲突。
- 技术详情可写入审计日志，医学监查员页面只显示中文失败分类、影响范围和可执行恢复动作。

### 可复用组件与模式

#### 可直接复用

- `frontend/src/app/router.tsx` / `useHashRoute` / `updateParams`：保持 subject、episode、mode、preview、job 上下文。
- `frontend/src/app/useLoad.ts` 与 `frontend/src/components/shell/Feedback.tsx`：加载、空状态、错误与重试骨架。
- `frontend/src/components/shell/StatusBadge.tsx`：Job 和处理状态的中文 badge；状态不能只靠颜色。
- `frontend/src/api/jobEvents.ts`：持久 Job SSE 续订边界。
- `frontend/src/components/evidence/EvidenceCard.tsx`：文件、页码、摘录、精度和打开原文动作。
- `frontend/src/components/evidence/PrecisionBadge.tsx`：诚实呈现定位精度与降级原因。
- `frontend/src/components/evidence/EvidencePane.tsx`、`ConflictSources.tsx`、`ExpectationCoverage.tsx`：上传完成后的证据、冲突和应备资料覆盖视图。
- `frontend/src/components/protocols/ProtocolRecoveryBanner.tsx`、`ProtocolJobProgress.tsx`：恢复提示与任务步骤进度的视觉/状态模式。

#### 应抽取或改造后复用

- `frontend/src/components/protocols/ProtocolUploadPanel.tsx:1-90`：可抽取拖放、文件选择、焦点和错误显示行为；现组件只接收单个 DOCX 且文案/校验属于方案解构，不能直接复用为受试者多文件上传。
- `frontend/src/api/protocolWorkbenchRepository.ts` 与 `protocolWorkbenchHttp.ts`：可复用“typed repository + multipart + ErrorEnvelope 解码 + runtime normalization”的接入模式；应新建 evidence/subject feature repository，不要继续扩大只读 `EnrollmentRepository`。
- `frontend/src/components/protocols/ProtocolJobFlow.tsx`：可借用 job 状态分支、恢复 banner 和进度组织；当前实现以轮询为主，受试者上传应优先接入现有 SSE，并以持久状态接口作为真相。
- `frontend/src/components/evidence/EvidenceDialog.tsx`：可保留弹窗可访问性和定位元数据，但必须扩展为真实原页/PDF 查看器；当前组件没有页图，不能满足 Phase 4 原件预览。
- `frontend/src/pages/TasksPage.tsx`：可保留列表/详情信息架构和中文状态词，但必须替换 fixture/session demo 数据与本地状态推进。

#### 不应复用为业务真相

- `frontend/src/api/stubRepository.ts` 和 fixture：只适合 UAT 展示，不承担写入、幂等、并发冲突或恢复。
- `/api/v2/protocol/deconstructions` 与 `ProtocolWorkbenchService`：可参考上传登记和哈希处理，但其身份、文件类型、门禁和任务步骤均属于方案领域。
- 浏览器端自组 `POST /api/v2/jobs`：任务图必须由受试者上传应用服务生成。
- legacy OCR/router：可在 V2 服务后封装为适配器，并遵守全局最多 8 路并发；前端和 V2 路由不应直接调用 legacy 写路径。

### 合同 fixture 与 E2E 覆盖判断

- `contracts/v1/fixtures/uat-phase1-workspace.json` 含 8 个受试者、14 个审核节点，覆盖 pre-screening、screening、run-in、baseline；同时含 full 与 incremental 快照以及持久任务事件样例。
- fixture 的增量样例有 `prior_snapshot_id`，但每个样例只足以证明谱系字段存在，不能证明“增量快照已包含沿用 + 新增的完整成员集”，也不能证明内容哈希去重或 OCR 缓存真的执行。
- `contracts/v1/schema/fixture-v1.schema.json` 定义了 `EvidenceSnapshot` 和 `SourceDocumentVersion`，未发现上传 preview/commit、去重结果、候选快照、页级 OCR 结果或人工校对记录的请求/响应合同。
- `frontend/e2e/uat-interactions.spec.ts` 覆盖看板跳转、Patient Profile、证据定位、任务演示和布局压力；`risk-evidence.spec.ts` 覆盖三次以内打开证据；`desktop-routes.spec.ts` 覆盖桌面路由和横向溢出。
- 未发现 E2E 覆盖：真实文件选择、全量/增量切换、去重预览、preview/commit、浏览器关闭后恢复真实 Job、页/文件范围重试、取消安全边界、旧/新快照对比、失败候选不替换当前快照。

### 建议的 Phase 4 最小端到端验收路径

1. 从 `/subjects` 选定受试者和筛选期，进入增量上传；重复文件显示“不新增且不重复 OCR”，新增文件显示候选成员和保守影响。
2. 提交后创建真实持久 Job；关闭并重开浏览器，`/tasks?job=` 从持久事件恢复且无重复进度。
3. 制造单页 OCR 可重试失败；已成功页面保持完成，只重试失败页，当前有效快照在发布前不变化。
4. 同名不同内容作为新版本；同内容不同文件名作为重复；跨受试者相同内容不发生错误归属。
5. 全量上传遗漏旧文件时明确告警；确认后创建独立新快照，旧快照和旧报告仍可查看。
6. 在 1080P、2K、4K 最大化桌面及 100%、150%、200% 浏览器缩放下检查三栏、长中文文件名、错误消息、原页预览和键盘焦点。

## Files Found

- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`：Phase 4 工作项与退出门槛。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`：全局导航、Patient Profile、工作台、上传/批处理和恢复边界。
- `frontend/src/app/routes.tsx`：现有路由及“受试者与资料”“入排工作台”“任务与系统”入口。
- `frontend/src/api/stubRepository.ts`：受试者/节点/任务的只读 fixture 仓储，无写方法。
- `frontend/src/api/protocolWorkbenchRepository.ts`：真实/fixture 方案仓储选择模式。
- `frontend/src/api/protocolWorkbenchHttp.ts`：multipart、错误信封与响应归一化范式。
- `frontend/src/api/jobEvents.ts`：持久 Job SSE 订阅与断线续订适配器。
- `frontend/src/pages/SubjectsPage.tsx`：受试者、阶段和 Patient Profile 当前入口。
- `frontend/src/pages/WorkbenchPage.tsx`：规则/判断/证据三栏及当前快照上下文。
- `frontend/src/pages/TasksPage.tsx`：fixture 任务列表和会话内处理状态演示。
- `frontend/src/components/protocols/ProtocolUploadPanel.tsx`：单 DOCX 拖放/文件选择模式。
- `frontend/src/components/protocols/ProtocolJobFlow.tsx`：方案任务的状态/恢复/进度组织。
- `frontend/src/components/evidence/EvidenceCard.tsx`：证据摘要和原文入口。
- `frontend/src/components/evidence/EvidenceDialog.tsx`：当前只有 OCR 摘录和定位元数据的原型弹窗。
- `frontend/src/components/evidence/PrecisionBadge.tsx`：证据定位精度与降级说明。
- `frontend/src/components/evidence/EvidencePane.tsx`：证据、冲突与资料期望的组合视图。
- `app/api/v2/app.py`：当前只挂载 jobs 和 protocols 路由/服务。
- `app/api/v2/jobs.py`：通用持久 Job 状态、取消、重试和 SSE API。
- `app/api/v2/protocols.py`：方案 DOCX 上传 API，属于方案领域。
- `app/services/job_service.py`：Job 幂等创建、状态、事件、取消和重试服务。
- `app/services/protocol_workbench_service.py`：方案上传登记、哈希和方案任务编排参考。
- `app/domain/contracts/review.py`：Project、Subject、ReviewEpisode 领域合同。
- `app/domain/contracts/evidence.py`：SourceDocumentVersion、EvidenceSnapshot、EvidenceSpan 等证据合同。
- `app/storage/models.py`：受试者、节点、文档版本、快照和 EvidenceSpan 持久模型。
- `app/storage/repositories.py`：Project、Subject、ReviewEpisode 仓储；未发现命名明确的证据上传用例仓储。
- `contracts/v1/fixtures/uat-phase1-workspace.json`：Phase 1 受试者、阶段、快照和任务演示数据。
- `contracts/v1/schema/fixture-v1.schema.json`：fixture/v1 数据结构，不含上传命令合同。
- `frontend/e2e/uat-interactions.spec.ts`：主要 UAT 交互与任务演示。
- `frontend/e2e/risk-evidence.spec.ts`：证据可达性路径。
- `frontend/e2e/desktop-routes.spec.ts`：桌面路由和溢出检查。

## Code Patterns

- API 路由只做参数/DTO 适配，业务组合下沉 service：`app/api/v2/protocols.py:316-365`、`app/services/protocol_workbench_service.py:431-599`。
- 持久任务先落库、SSE 只读事件：`app/api/v2/jobs.py:78-178`、`frontend/src/api/jobEvents.ts:43-75`。
- 受试者和阶段通过稳定 ID/URL 上下文选择：`frontend/src/pages/SubjectsPage.tsx:79-117,189-294`。
- 工作台保持 subject/stage/snapshot 上下文并同步规则与证据：`frontend/src/pages/WorkbenchPage.tsx:205-296`。
- 证据定位诚实降级，不伪造 bbox：`frontend/src/components/evidence/PrecisionBadge.tsx:28-90`、`EvidenceCard.tsx:23-90`。
- UI 显式建模 loading/empty/error/retry：`frontend/src/components/shell/Feedback.tsx:1-44`。
- fixture 仓储不写回、不模拟后台成功：`frontend/src/api/stubRepository.ts:1-5`。

## External References

- 未使用外部资料。本研究是对当前仓库的只读现状核对；API 路径为基于现有边界的内部建议，不是已发布合同。

## Related Specs

- `.trellis/workflow.md`：研究输出和任务持久化规则。
- `.trellis/spec/frontend/index.md`：原生中文、三次交互内到达证据等前端原则。
- `.trellis/spec/frontend/directory-structure.md`：feature、repository、API adapter 和 raw response 边界。
- `.trellis/spec/frontend/component-guidelines.md:7-16,19-33`：显式状态、typed props、宽屏布局与可访问性。
- `.trellis/spec/frontend/state-management.md`：URL、服务器状态和临时 UI 状态的归属。
- `.trellis/spec/backend/directory-structure.md`：router、service/workflow、domain、storage 分层。
- `.trellis/spec/backend/persistent-jobs.md:5-10,20-35`：持久任务、checkpoint、失败范围重试、租约与 SSE。
- `.trellis/spec/backend/database-guidelines.md`：不可变证据/快照、幂等与后期资料不覆盖早期结果。
- `.trellis/spec/backend/error-handling.md`：稳定错误信封、部分失败和中文恢复动作。

## Caveats / Not Found

- 活跃任务目录在研究开始时没有 `prd.md`、`design.md` 或任务内 Phase 4 计划文件；本研究以全局实施计划和最终设计为 Phase 4 依据。
- 这是静态只读研究，没有启动应用、上传真实受试者资料或执行 E2E；“不存在”表示在指定代码、合同 fixture/schema 与 E2E 搜索范围内未发现，不代表后续未纳入其他未读分支。
- 尚未验证现有存储模型能否完整表达文档版本到快照的关系、OCR 页、校对 revision 和候选快照发布事务；这些必须在实施前形成明确合同和迁移设计。
- fixture 中的增量快照只能证明字段和谱系样例存在，不能作为增量合并、去重、缓存或影响范围算法通过验收的证据。
- `EvidenceDialog` 当前没有原始页图，因此现有“打开原文”体验不足以满足 Phase 4 的真实预览与定位验收。
- `/tasks` 的恢复按钮是会话内演示；在真实 Job repository、SSE 和 retry/cancel API 接入前，不应对外宣称任务恢复已打通。
