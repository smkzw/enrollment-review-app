# Conference Participant Output: reference-ui-gap-review-20260915 - visual_single_object

## Boundary Check

- **工作空间与运行环境**：本审阅严格在授权工作区工作树根目录（`.`）内执行只读分析，未访问外部网络，未登录任何外部系统，未写入任何受控产物路径（包括 `runs/conference/...` 报告路径），完整审阅报告通过本应答直接交付供 Runner 持久化。
- **审阅角色与模型配置**：
  - Role ID: `visual_single_object`
  - 角色定位：独立视觉审阅（Independent Visual Reviewer）
  - 承载模型：`pi` / `google-antigravity` / `gemini-3.7-flash`（高思考负载）
  - 审阅模式：串行会议模式（Serial Conference Mode）
- **核查范围与输入证据集**：
  1. 外部试用观察记录：`artifacts/reference-ui-20260915/OBSERVATIONS.md`
  2. 外部界面截图（3 张）：
     - `artifacts/reference-ui-20260915/enrollment-reference-detail-20260915.png`（1280×649 视口）
     - `artifacts/reference-ui-20260915/enrollment-reference-pdf-20260915.png`（1920×1080 视口）
     - `artifacts/reference-ui-20260915/enrollment-reference-audit-20260915.png`（1920×1080 视口）
  3. 本地实现源码：
     - `frontend/src/components/evidence-workspace/OriginalEvidenceViewer.tsx`
     - `frontend/src/components/review/FrozenReviewEvidence.tsx`
     - `frontend/src/components/review/FrozenReviewReport.tsx`
  4. 邻近样式定义：
     - `frontend/src/styles/evidence.css`
     - `frontend/src/styles/reports.css`
- **合规与权威边界**：不作出任何临床有效性或产品最终验收裁定；不把外部演示环境的数据混装或识别异常推断为临床基准；严守本系统单机单用户、本地事实闭包与不可变快照的既定架构。

---

## Independent Work Product

### 1. 外部系统界面视觉与交互事实审计（Observed External UI）

基于提供的三张真实视口截图与观察日志，提取出以下客观视觉与交互特征：

1. **首屏信息密度与视口适配缺陷（`enrollment-reference-detail-20260915.png`，1280×649）**：
   - **首屏挤压**：顶栏占据 52px，页面标题与返回按钮占据约 70px，其下的“审核上下文”卡片占据了约 180px 的垂直高度。在 1280×649 的笔记本常见视口下，“代号/状态”行以及下方的“资料文件”标签页列表被直接挤压到折叠线（Fold）以下。
   - **扫描路径断裂**：监查员进入详情页的第一眼，无法直接看到该受试者上传的资料文件列表，必须向下滚动才能开始操作。
   - **医学上下文弱化**：顶栏左侧仅标注技术编号“项目 #3”，右侧角色为英文“inspector”。方案全称与方案编号（`【测试】MG-K10-CSU III期（MG-K10-CSU-001）`）混排为普通二级标题，缺乏医学监查场景所需的结构化受试者元数据看板。

2. **全屏模态弹窗对审核决策链的阻断（`enrollment-reference-pdf-20260915.png`，1920×1080）**：
   - **全屏遮蔽**：点击查看 PDF 原件时，系统弹出一个覆盖屏幕 90% 以上面积的大型模态弹窗（Overlay Dialog）。
   - **无法双屏/同屏对照**：弹窗打开后，下层的入组条件清单、AI 判定结果、待办补充项被 100% 遮挡。监查员核对 PDF 内容时，无法对照正在审核的条款规则；退出弹窗后又丢失了原件视线，严重破坏了临床审核的“边看条款、边查原件”工作流。
   - **PDF 容器故障态缺失**：该弹窗内嵌的浏览器原生 PDF 阅读器在抓取时呈现深灰色空白块（仅带顶部文件名进度条与底部“下载/关闭”按钮），无加载超时状态提示，无重试机制，无页码快速跳转。

3. **空态与识别中状态的低效视觉表达（`enrollment-reference-audit-20260915.png`，1920×1080）**：
   - **电商化空态插画**：“AI 识别资料”展开“邮件.pdf”时，展示了一个大尺寸的空纸箱插画配文“该文件尚未完成识别”。在严谨的临床医学软件中，此类插画不仅占用过多屏幕空间（约 300px 高度），而且未提供任何有效诊断信息（如排队中、OCR 进度百分比、预计剩余时间、或服务异常重试）。
   - **宽屏留白浪费**：在 1920 宽屏下，中间内容区为单列居中，两侧产生大面积无意义的灰白留白，垂直方向却层层嵌套折叠面板（Accordion），信息获取效率低下。
   - **粗粒度操作风险**：顶部提供“重新识别资料”按钮，并附注“重新 OCR 全部已提交资料，不改变参与者审核状态”，但缺少对单个损坏/识别失败文件的局部重试入口。

---

### 2. 本地系统源码视觉与交互实现对照（Source-Only Local Behavior）

对照本地相关核心组件源码（`FrozenReviewReport.tsx`、`FrozenReviewEvidence.tsx`、`OriginalEvidenceViewer.tsx` 及对应 CSS），梳理现有优势与不足：

1. **不可变快照与证据闭包呈现（`FrozenReviewEvidence.tsx` & `FrozenReviewReport.tsx`）**：
   - **优势**：
     - 严格执行版本一致性防御（`FrozenReviewEvidence.tsx:40-49`），核对 `revisionId`、`evidenceSnapshotV2Id`、`projectId`、`subjectId` 及 `reviewEpisodeId`。若出处不一致，直接阻断并提示 `原件与本次审核保存的出处不一致，暂不能定位；系统未改用其他资料。`，从不静默回退到最新原件。
     - 左侧列表（`review-source-dialog__refs`）明确标注资料文件名、页码、文字摘录以及红框精度级别（`已标出原文位置` vs `仅定位到所在页面，未标注具体区域`），具备完整的医学溯源语义。
   - **不足**：
     - 目前仍采用 `<dialog className="review-source-dialog">`（`reports.css:10-28`）模态呈现，虽然优于外部系统的纯 PDF 弹窗（本地弹窗左侧有摘录列表、右侧有多页连续画布），但在长篇报告审核多条不同条款时，频繁打开/关闭弹窗仍具有较重的心智与交互开销。

2. **连续平铺原件查看器（`OriginalEvidenceViewer.tsx`）**：
   - **优势**：
     - 支持所有页面按原始高宽比连续平铺（`aspectRatio: ${page.pageWidth} / ${page.pageHeight}`），避免分页点击跳转带来的断层感。
     - 支持 70%~180% 缩放，且在缩放时通过 `zoomAnchor` 记录视口顶部穿过的页面及百分比偏移，防止缩放后视口剧烈漂移（`OriginalEvidenceViewer.tsx:69-95`）。
     - 严格过滤未认证红框（`authenticatedBoxes`），确保无坐标时不画伪框（`OriginalEvidenceViewer.tsx:22-33`）。
     - 具备单页级网络图片重试计数与 `?retry=attempt` 缓存规避机制（`OriginalEvidenceViewer.tsx:228-236`）。
   - **源码缺口（Codebase Gaps）**：
     - **加载状态缺失**：当 `page.imageAvailable` 为 true 但网络图片正在下载时，没有骨架屏（Skeleton）或 Loading Spinner，直接显示空白白色画布，用户无法区分“正在加载”与“服务无响应”。
     - **全量 Eager 请求**：所有页面 `<img>` 标签均标记为 `loading="eager"`（`OriginalEvidenceViewer.tsx:290`）。当一份病历多达 30~50 页时，弹窗打开瞬间将并发发出数十个高分辨率页图请求，极易造成局部网络拥塞与渲染卡顿。
     - **常驻工具栏信息不足**：顶部工具栏（`original-evidence-viewer__toolbar`）仅包含静态文字 `<span>{pages.length} 页连续查看</span>` 与缩放按钮，缺少当前视口中正在阅读的“文档名称 · 第 X 页 / 共 Y 页”的动态指示。
     - **错误恢复提示丢失**：在网络图片加载失败分支（`imageFailed`，`OriginalEvidenceViewer.tsx:278-286`），仅渲染了通用的“原图未能载入 / 重新载入”，未能将调用方传入的权威快照说明（`unavailableRecoveryHint`）展示出来；该说明仅在元数据层 `!page.imageAvailable` 时才显示。

---

### 3. 核心设计挑战与风险审计：针对 Owner 提出的优化方案（Loading / Current-Page / Lazy-Loading）

针对 `OBSERVATIONS.md` 第 26、31 条中提出的“明确载入状态、常驻当前文件与页码、图片按临近可见区域加载”等设想，本独立审阅提出以下深层风险挑战与边界约束：

#### 挑战 A：图片懒加载/虚拟化与红框精确定位的冲突（Layout Shift & Bounding Box Drift Risk）

- **假设前提**：为了优化性能，将 `loading="eager"` 改为按临近可见区域懒加载（IntersectionObserver / 虚拟列表）。
- **严重风险**：
  1. **红框定位失效**：`OriginalEvidenceViewer` 的核心功能是定位高亮区域。在 `useEffect`（`OriginalEvidenceViewer.tsx:120-139`）中，程序化定位依赖于 DOM 中红框元素的实体坐标：
     ```typescript
     const locator = locatorRefs.current.get(selectedLocatorId);
     const box = locator.getBoundingClientRect();
     ```
     如果用户在左侧点击了位于第 15 页的摘录，而第 15 页因为懒加载尚未挂载 DOM 或未渲染内部 Canvas，`locator` 将为 `undefined`，导致红框定位直接失效或滚到错误位置。
  2. **回滚跳动（Scroll Jolt）破坏最近页判定**：如果未加载页面使用固定高度或空占位符，当用户快速滚动使得图片动态加载、高宽比重新撑开时，会产生累积布局偏移（CLS），导致 `handleScroll` 中通过 `nearest` 计算当前页面的逻辑发生剧烈抖动，进而向外抛出错误的 `onSelectPage`。
- **强制约束与解法**：
  - **严禁使用动态高度占位**：必须保证 `pages` 元数据中必须有确定的 `pageWidth` 和 `pageHeight`，页面外层 `<article>` 与 `.original-evidence-page__canvas` 必须在 DOM 初始化时就通过 `aspectRatio` 严格锁定几何尺寸。
  - **DOM 节点与红框骨架常驻**：虚拟化/懒加载只能针对 `<img>` 元素的资源加载（或视口缓冲区 ±2 页的图片解码），绝对不能卸载红框所在的 DOM 容器与定位锚点。
  - **定位目标预挂载守卫**：当触发程序化导航（`navigationKey` 变化）且目标页尚未渲染图片时，必须同步置位 `programmaticScrolling.current = true`，等待目标页 DOM 就绪并完成对齐后，再释放滚动监听锁。

#### 挑战 B：常驻工具栏“当前页码”与多文件连续滚动的身份混淆风险（Multi-Document Identity Ambiguity）

- **假设前提**：在常驻顶部工具栏（Sticky Toolbar）中动态显示“当前文件名称 · 第 X 页”。
- **严重风险**：
  1. **跨文件接缝处的误导性归属**：受试者资料通常由多份异构文件组成（例如：门诊病历 3 页 + 知情同意书 2 页 + 检验单 1 页）。当用户滚动到“门诊病历第 3 页”与“知情同意书第 1 页”同时出现在一个视口时，如果常驻工具栏单向显示“知情同意书”，监查员极易将视口上半部分属于“门诊病历”的临床内容误认为是“知情同意书”的内容，造成严重的归属混淆。
  2. **滚动防抖带来的状态滞后**：`handleScroll` 包含 220ms 的滚动判定定时器。在快速滑动过程中，常驻工具栏的页码跳动必然滞后于视口中央的真实内容。
- **强制约束与解法**：
  - **页面自带头部（Local Page Head）为主，常驻工具栏为辅**：每一页卡片内部现有的 `.original-evidence-page__head`（`OriginalEvidenceViewer.tsx:260-266`）必须保留且推荐采用局部 `position: sticky; top: 0;`，确保当该页在视口内滚动时，其文件名与页码始终吸附在当前页顶部。
  - **常驻工具栏仅展示全局进度**：顶部工具栏仅展示概括性进度（如：`资料 2/3 · 总第 4/10 页`），具体文件全称必须以页面内吸顶头部为准。

#### 挑战 C：网络传输故障与临床资料缺失/失效的语义混淆（Transport Error vs Clinical Gap）

- **假设前提**：增加原图加载失败与重试界面。
- **严重风险**：
  - 如果网络超时或图片服务器 500 导致的图片空白，被界面笼统展示为“该资料暂不可用”或“未找到原始资料”，监查员可能会错误地在审核报告中登记“受试者缺少该项检查资料”，进而开具错误的补充资料要求（Action）。
- **强制约束与解法**：
  - 严格区分三层失败状态与提示文案：
    1. **传输层临时失败（HTTP/Network Error）**：文案必须为 `网络图片载入中断（已锁定历史快照版本），点击重试`，且重试操作只能请求同版本哈希的图片切片，严禁调用重新解析接口。
    2. **生成层单页失败（Processing Page Failure）**：展示 `page.failureReason`，文案为 `该页原始图像生成异常，原审核结论依据保留`，并展示 `unavailableRecoveryHint`。
    3. **不可变绑定失效（Integrity Mismatch）**：若快照版本与上下文不符，触发 `FrozenReviewEvidence.tsx:62`，展示警告 `原件与本次审核保存的出处不一致，暂不能定位；系统未改用其他资料。`。

---

## Evidence And Assumptions

### 1. 结构化事实证据（Grounded Facts）

| 编号 | 来源位置 | 事实描述 | 界面/代码意义 |
| :--- | :--- | :--- | :--- |
| **F-01** | `artifacts/reference-ui-20260915/enrollment-reference-detail-20260915.png` | 1280×649 视口下，“审核上下文”卡片占据了近 200px 垂直高度 | 首屏文件列表被完全压入折叠线以下，信息密度低 |
| **F-02** | `artifacts/reference-ui-20260915/enrollment-reference-pdf-20260915.png` | 1920×1080 视口下，PDF 查阅为遮罩覆盖度 >90% 的模态弹窗 | 遮挡下层入排审核结论与条件，无法同屏比对 |
| **F-03** | `artifacts/reference-ui-20260915/enrollment-reference-audit-20260915.png` | “AI 识别资料”展开后展示大尺寸空纸箱插画，文案“该文件尚未完成识别” | 视觉风格不符合严肃医学监查，缺乏进度与诊断信息 |
| **F-04** | `OriginalEvidenceViewer.tsx:290` | `loading="eager"` 且 `decoding="async"` | 所有图片在组件挂载时并发无序发起网络请求 |
| **F-05** | `OriginalEvidenceViewer.tsx:278-286` | `imageFailed` 分支仅渲染 `RefreshCw` 与“原图未能载入” | 丢失了调用方传入的不可变历史快照说明 `unavailableRecoveryHint` |
| **F-06** | `OriginalEvidenceViewer.tsx:120-139` | 依赖 `locatorRefs.current.get(selectedLocatorId).getBoundingClientRect()` | 红框定位强依赖 DOM 实体节点的存在与准确布局 |
| **F-07** | `FrozenReviewEvidence.tsx:40-49` | 严格比对 `revisionId`, `evidenceSnapshotId`, `subjectId` 等字段 | 确保历史审核证据链完全锁定，无静默回退 |
| **F-08** | `reports.css:28` | `.review-source-dialog__body { grid-template-columns: minmax(0, 1fr) minmax(0, 2fr); }` | 本地弹窗保持了 1:2 的“左侧摘录列表 + 右侧多页原件”同屏对照 |

### 2. 推断与假设（Inferences & Assumptions）

- **推断 1（[INFERENCE] 性能瓶颈）**：当真实临床试验病历页数超过 30 页时，全量 `loading="eager"` 会引发前端渲染卡顿与网络请求排队（Chrome 同域名最大并发限制为 6），导致视口当前页图片加载变慢。
- **推断 2（[INFERENCE] 用户心智）**：临床监查员（CRA/MM）在审核不确定项时，注意力高度聚焦在“条款要求 - 摘录文字 - 原件红框”的三联验证上。全屏弹窗的反复弹出与关闭会导致明显的认知断层。
- **推断 3（[INFERENCE] 外部演示数据）**：外部演示站出现的“MG-K10-CSU III期（荨麻疹）”下出现“过敏性鼻炎”条款，属于演示库数据混装或测试配置，不能作为本系统临床逻辑或数据架构的参考。

---

## Risks, Gaps, And Verification Needs

### 1. 核心风险与缺陷分类

1. **高风险（High Impact）：红框定位在视口优化中的脆性失效**
   - 若直接引入粗粒度虚拟列表或未保留 DOM 几何尺寸的懒加载，当用户从左侧摘录点击定位到远端页面（如第 20 页）时，平滑滚动将因找不到 DOM 节点而静默失败，使红框定位功能完全瘫痪。
2. **中风险（Medium Impact）：大模态弹窗对连续审核流的阻断**
   - 现行 `FrozenReviewEvidence` 虽具备高保真溯源能力，但仍为覆盖式 Modal。监查员审核 20 条标准时需打开关闭弹窗 20 次，降低了高频审核效率。
3. **低风险（Low Impact）：多分辨率下的视觉留白与溢出**
   - 1280 宽度下表头和上下文卡片偏厚，2K/4K 分辨率下行长拉伸。

### 2. 验证需求与测试场景（Verification Needs）

- **场景 1（长文档红框跨页唯一定位验证）**：
  - 构造包含 3 份文件、共计 40 页的连续原件集合；
  - 选中第 35 页的一个 authenticated 边界框；
  - 验证：在初始加载、快速滚动、缩放（150%）及网络限速（Slow 3G）下，查看器是否能 100% 精确平滑滚动并将红框居中，无白屏漂移，无控制台报错。
- **场景 2（单页图片 404/504 恢复与不可变性验证）**：
  - 模拟第 5 页图片返回 500 错误；
  - 验证：第 5 页展示重试提示及 `unavailableRecoveryHint`，其余 39 页正常显示；点击第 5 页重试按钮后，仅重试该页请求，不破坏当前已选中的摘录焦点。
- **场景 3（多分辨率响应式排版验证）**：
  - 在 1280×720、1920×1080、2560×1440 三种视口尺寸下，验证紧凑元数据条高度均 ≤48px，首屏核心数据区无需滚动即可见。

---

## Recommended Next Step

基于“最小必要改进、严守事实闭包、中文医学原生”原则，建议按以下优先级开展实施：

### 阶段一：`OriginalEvidenceViewer` 健壮性与视觉最小必要修正（即刻执行）

1. **补齐加载与失败状态，串联快照恢复说明**：
   - 为正在加载的页面引入轻量级浅灰色骨架（Skeleton）与微型加载指示器；
   - 在 `imageFailed` 渲染块中补充展示 `unavailableRecoveryHint`，明确提示用户原审核结论已被保留，网络重试不会篡改历史快照。
2. **常驻工具栏补充紧凑进度指示**：
   - 工具栏左侧由 `<span>{pages.length} 页连续查看</span>` 升级为 `<span>资料共 {pages.length} 页 · 当前第 {selectedPage?.pageNumber ?? 1} 页</span>`；
   - 维持单页卡片头部（`.original-evidence-page__head`）的权威归属，设置 `position: sticky; top: 0; z-index: 1;`，使页面在长图滚动时始终保持文件名可见。
3. **无布局偏移的平滑按需加载（Safe Viewport Loading）**：
   - 保持所有页面的 `<article>` 节点与 Canvas 容器常驻 DOM，且严格基于 `aspectRatio` 锁定尺寸；
   - 仅对距离当前视口超出 ±2 页的远端 `<img>` 采用占位加载，并在触发 `navigationKey` 定位时提前预载目标页图片，确保 `getBoundingClientRect()` 永不失效。

### 阶段二：医学监查界面紧凑化与信息密度重构（下一轮迭代）

1. **废弃大尺寸占位插画，重构紧凑医学状态标识**：
   - 移除所有类似外部系统的“纸箱”类空态图形，以紧凑状态标签替代（如：`[解析就绪]`、`[排队处理中 60%]`、`[需要重新解析]`）；
   - 将“审核上下文”重构为高度 ≤40px 的紧凑横向条（包含：项目编号、受试者代号、审核阶段、版本轮次、提交人与时间），彻底释放垂直首屏空间。
2. **工作台三栏同屏对比演进评估**：
   - 在未来的完整工作台界面中，逐步将模态弹窗（Modal）转变为响应式三栏/双栏布局（左侧：入排清单与三态结论；中间：判定依据与原文摘录；右侧：连续原件查看器），实现真正零弹窗干扰的沉浸式医学监查复核。

---

### 给 Codex 的定界问题（Bounded Questions for Codex）

1. **关于多页原件图片按需加载的实现边界**：
   - *问题*：是否同意在保留全部页面 DOM 几何尺寸（基于 `aspectRatio`）和红框定位引用的前提下，仅对 `<img>` 图片资源的加载引入视口缓冲区控制（±2 页），以彻底杜绝虚拟列表卸载 DOM 造成的红框定位漂移风险？
   - *影响*：关乎长病历大图性能与红框精确定位稳定性的平衡。
   - *安全兜底路径*：若暂不引入视口缓冲区，则继续维持当前全量挂载，仅在图片标签上添加 `decoding="async"` 与加载骨架屏，优先保障定位正确性。

2. **关于未来原件查看形态是“维持弹窗优化”还是“推进三栏工作台”**：
   - *问题*：当前阶段是否仅限在 `FrozenReviewEvidence.tsx` 弹窗内部进行比例与工具栏优化，而将“条款-摘录-原件”三栏同屏工作台留待后续端到端工作台任务整体设计？
   - *影响*：决定当前改动范围是否严格限制在查看器组件级别（不做破坏性布局重构）。
   - *安全兜底路径*：当前仅修改 `OriginalEvidenceViewer.tsx` 与相关 CSS，保持调用方接口与弹窗挂载结构完全向后兼容。
