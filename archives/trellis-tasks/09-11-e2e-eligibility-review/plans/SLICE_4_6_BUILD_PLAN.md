# Slice 4/6 构建方案（v2 冻结版）

任务：09-11-e2e-eligibility-review。日期：2026-09-11。
修订依据：EngReview（APPROVE-WITH-CHANGES，7 必改）+ UserViewReview（MUST 清单）双审阅。v1→v2 修订处标注【v2】。

## 0. 范围与目标

用户裁决：完整网页端 APP、消灭一切"开发中/后续版本开放"占位、端到端走通入排审核全流程。

- **Slice 4**：判断检索界面 + 待办汇总卡 + 术语统一（前端+**后端标签**）。
- **Slice 6**：入排工作台真实数据化 + 报告打印页 + 占位路由 redirect + 任务页真实化。

## 1. Slice 4 详细设计

### 1.1 前端 API client（frontend/src/api/judgment-search/）

【v2】沿用 **patient-profile 目录模式**（非 page-review——后者无独立 wire/ViewModels 文件）：`judgmentSearchTypes.ts` + `judgmentSearchHttp.ts`（内含严格解码，未知/缺字段抛 DecodeError）+ 可选 ViewModel。

端点对齐 `app/api/v2/judgment_search.py:33-73` 四端点。轮询：状态 running 时 2.5s（PageReviewTaskDetail.tsx:23-27 模式）；localStorage 存 job id（useFactNormalizationJob.ts:22-47 模式）刷新恢复。

### 1.2 书面判断检索卡（挂载点）

【v2】**不挂"证据面板旁"**（证据面板条件渲染）。挂载：SubjectsPage 档案头之下、"首屏重点"之后、"修订记录"之前，纵向卡片。

- 卡片标题：**「书面判断检索」**，首行说明：在本次提交的资料中查找研究者书写的判断文字。
- 无任务：说明 + 按钮动词宾齐全「开始查找书面判断」。
- 运行中：【v2】进度措辞"正在查找研究者书面判断…（第 x/y 项要求）"，不用"已检索 x/y 页"（页数口径误导）。
- 完成：每条要求一行，用后端中文标签（judgment_search_status.py:18-23 原文照用）。候选展开：页码 + 【v2】lane 用 laneLabel 中文名（如"用药""既往史"），**绝出现"通道"** + 摘录文本 + 点击跳原件页（复用 ProfileEvidencePanel.tsx:215-224 导航模式）。
- 已取消：「继续查找」按钮（POST resume，can_resume 时显示）。

### 1.3 待办汇总卡【v2 全面修订】

卡片标题：「本节点资料核对情况」。数据源：**前端从 patientProfileModel.items 按 gapType 客户端聚合**（真实 wire 无 gap_counts——v1 表述有误，两审阅者交叉证实）。

| 显示组 | 聚合来源 |
|---|---|
| 待补资料 | record_incomplete + referenced_file_missing + required_procedure_not_done + historical_source_unavailable |
| 待研究者判断 | professional_judgment + observation_unverified |
| 资料有矛盾 | 未解决冲突组数（items.kind==="conflict" && conflictResolutionRevision===null 计组数）+ interpretation_conflict 条目 |
| 【v2】待人工核对（原"未能读取"——名不副实，"描述不充分"≠没读到） | ocr_or_parse_risk + result_fields_missing + description_insufficient + date_or_anchor_missing + provenance_followup |

- 【v2】**前置：扩前端解码枚举**。ProfileGapTypeWire（patientProfileTypes.ts:66-79）与 GAP_TYPES（patientProfileViewModels.ts:396-410）补 observation_unverified + interpretation_conflict + provenance_followup + historical_source_unavailable（后端契约本就允许，patient_profile_v2.py gap_type 为任意 GapType；不扩则投影该值时整页 DecodeError）。中文标签："待研究者判断"/"解释材料与方案不一致"/"来源待补充核实"/"既往来源无法取得"。
- 【v2】**绿条措辞**（全部为零时）："本次提交资料中，暂无待补资料、待判断、矛盾或待核对事项"——事实性陈述，不用"核对完整"（越界）。
- 交互：每组徽章点击 → 若泳道收起先展开（all=1）→ 滚动到对应条目高亮。需给泳道条目补锚点 id。
- 与档案头"待核对 N 项"chip 并存说明：chip=需人工过目条目总数，卡片=按性质四组（工具条 tooltip 说明口径）。
- 视觉：一行四枚紧凑计数条（count-chip 放大版），≤56px 高，2×2 换行可接受；图标+文字，不只靠颜色。

### 1.4 术语统一【v2 扩到后端】

| 现状 | 改为 |
|---|---|
| 快照（前端：UploadModePicker/PreviewReview/ReferencedDocumentsPanel/ConflictSources/EvidenceDialog/EvidencePage/evidenceViewModels/labels/scenarios+【v2】**后端 vocabulary.py:139,179,188-196,238-241、errors.py:94**） | 统一"资料版本/完整资料版本"（与存量"资料版本 N"零冲突；不引入"完整资料集"第三同义词） |
| 读法（TargetedReviewDetail.tsx:33,38 三个轮次标签；PageReviewTaskDetail.tsx:26,41,44 复合词"N 项读法不同/读法分歧"） | 第一次识别/第二次识别/最初识别；读法分歧→识别结果不一致 |
| 【v2】判读全族（usePageReviewJob.ts:34,35,40,88,123,138,142；PageReviewTaskDetail.tsx:30-41；pageReviewHttp.ts:4；ProfileNormalizationStatus.tsx:24；SubjectsPage.tsx:469；EvidencePage.tsx:1579-1580） | 判读→识别（"资料判读"→"资料识别"；临床"判读"有固定含义，勿暗示医学判读） |
| 【v2】两路独立检索（**服务端** fact_expectation_gaps.py:266-267） | 两次独立检索 |
| 如 UAT-03（BoardToolbar.tsx:111） | 如 S-2026-101（真实编号格式） |
| 【v2】PrecisionBadge.tsx:23 "界面试用阶段未附带原始页图"（泄漏进正式模式） | "当前页面未附带原始页图，仅提供页码与摘录" |
| 【v2】decisionLabel "暂不能明确"（labels.ts:57-70） | 统一"无法判定"（与工作台/报告一致，含行动中心等展示） |
| 【v2】"结构块"（labels.ts block） | "文档段落" |

【v2】落地顺序：先改 fixture 断言基线→改后端标签+投影测试→改前端文案+组件测试。服务端 gap_detail 措辞变化影响新投影内容哈希：旧 revision 保留原文，新投影用新词（可接受，投影本就 append-only）。

## 2. Slice 6 详细设计

### 2.1 后端只读投影

【v2】新文件 `app/api/v2/eligibility_review.py`（薄路由）+ `app/services/eligibility_review_projection.py`（装配，两审阅者一致建议）。

`GET /api/v2/subjects/{sid}/review-episodes/{eid}/eligibility-review`

装配步骤（确定性，零模型调用）：
1. `authority_from_active_episode`。
2. `project_clause_pack`（clause_pack.py:137）取全部官方条款。
3. 【v2】**链头折叠**：`ClinicalFactV2Repository.list_for_authority`（fact_repositories.py:1316-1334）返回全部 revision 行，按 stable_identity 折叠取链头（先例 patient_profile_service.py:74-85 _chain_heads）；期望侧用 latest_by_template。
4. 【v2】**V2→Phase3 ClinicalFact 适配器**：EvaluationContext.facts 是 Phase3 契约（expression.py:30-69 + evidence.py:205），需写 ClinicalFactV2→ClinicalFact 适配（locator_ids↔span 映射实现时核实），保持 accepted_fact_ids/facts 集合全等。
5. 【v2】**anchor_dates 注入**（review.py:115 来源；缺失时求值器 fail-closed→date_or_anchor_missing，正确）。
6. 【v2】求值入口 `evaluate_component`（expression.py:557-573，**非 evaluate_expression**——例外条款靠它求值）。
7. 【v2】**冲突组→受影响组件映射**：V2 ClinicalConflictGroupV2 无 affected_rule_component_ids 字段（facts.py:569-601），须经 FactRuleLinkV2Repository 由冲突成员事实反推受影响组件，再入 derive_gate_gap_types——否则冲突条款会被误判可判定（医学边界红线）。
8. `derive_component_decision`（assessment.py:295-339）。

【v2】响应 decision 枚举补全（enums.py:110-122）：inclusion_met / inclusion_not_met / requirement_met / requirement_not_met / exclusion_triggered / exclusion_not_triggered / professional_judgment / conflict / not_due / not_applicable。determination_mode 第三值 **investigator_judgment**（clause_pack.py:16-19）。

【v2】响应补充**原件导航上下文**：evidence_snapshot_v2_id + complete_processing_revision_id（OriginalEvidenceViewer 需要 revisionId，ProfileEvidenceNavigationWire 模式），否则工作台右栏加载不了原件。

其余同 v1：undetermined 必带 gap_type+reason；不写库；非正式 ReviewRun。

### 2.2 前端工作台（/workbench）

- 新写正式版 WorkbenchPage（不继承 stub 版；勿继承"资料快照第 N 版"措辞）。
- 三区：左=条款列表（IN/EX 分组、父子缩进、过滤），中=详情（判定+原因置顶，结构化表达默认折叠），右=原件（OriginalEvidenceViewer + ProfileLocatorList）。
- 【v2】**过滤词按判定枚举命名**（消除"符合"在 EX 条款上的反向歧义）：全部 / 无法判定 / 已触发（排除）或未满足（入选）/ 未触发（排除）或已满足（入选）/ 尚未到期 / 不适用。列表顶部常显"无法判定 N 条"。
- 【v2】判定徽章沿用现有 status-badge--ok/danger/info 视觉语言，不发明新色。
- 1080P 拥挤对策：摘要/缺口徽章 max-width+ellipsis 悬停全文；三列 0.9fr/1.1fr/1.2fr。
- 【v2】4K 阅读质量：.app-shell__content 加 max-width（1800px）居中。
- 深链参数保留；档案页加「入排审核」入口。

### 2.3 报告打印页【v2 修订】

- 数据：eligibility-review 端点聚合；复用 SubjectsPage 的项目→受试者→节点选择模式 + 从工作台/档案带参跳入。
- 【v2】**打印 CSS 从零新写**（v1"沿用 profile.css 基础"为误——全 styles 零 @media print）：reports.css 新增 @media print 块——隐藏 SideNav/TopBar、解除面板 max-height/overflow 内滚动（否则打印裁掉第一屏外全部）、白底黑字、表格 thead 跨页重复、行 break-inside:avoid、徽章补边框。
- 【v2】**打印页显示完整 reason 不截断**（截断只用于工作台列表）；"无法判定清单"节置于逐条判定表**之前**；未到期/不适用条款也显示行（"尚未到期"），不静默省略（省略会被读成阴性）。
- 脚注："资料版本：第 N 版 · 档案版本：第 M 版 · 生成时间"（不用"权威元组"内部词）。
- 纯前端 window.print()（两审阅者一致：无需服务端 PDF）。

### 2.4 占位处理【v2 改为 redirect】

- 正式模式下 /today /board /actions /projects-new 深链 **redirect 到 /protocols**（仅移除导航不够——AppShell.tsx:16-23 ModulePending 文案会被深链命中）。trial 模式行为不变。
- /tasks showInNavigation 显式改 true（现绑 interfaceTrial，routes.tsx:134）。
- 【v2】TasksPage 真实化前置：**新增 GET /api/v2/jobs 列表端点**（现无，jobs.py 只有 POST/GET/{id}/cancel/retry/events）——列 Slice 6 后端工作项。

## 3. 实施顺序

1. Slice 4：前端枚举扩展 → judgment-search client+检索卡 → 待办汇总卡 → 术语统一（fixture→后端→前端）→ 组件测试。
2. Slice 6 后端：GET /api/v2/jobs 列表 → eligibility_review 投影+端点 → 装配测试（fixtures 全链，undetermined/冲突/not_due 路径必须覆盖）。
3. Slice 6 前端：工作台 → 报告页 → 路由 redirect → 全量。
4. Slice 5 真实实例联调（另文档）。

## 4. 风险与对策（v2 增补）

| 风险 | 对策 |
|---|---|
| V2→Phase3 事实适配器映射错误 | 适配器独立单测；locator→页码映射实现时核实（EngReview 唯一[未核实]项） |
| 冲突组漏映射（R3） | 装配测试含冲突 fixture 断言 conflict 判定 |
| observation_unverified 解码失败（R5） | Slice 4 第一步先扩枚举+标签 |
| 服务端改词影响投影哈希 | append-only 语义，旧 revision 不改 |
| 打印样式遗漏内滚动容器 | 打印验收点：连续打印≥2 页内容完整 |

## 5. 验收标准

- [ ] 后端 tests/v2 全量零失败；前端 vitest 全量零失败。
- [ ] 判断检索从档案页入队、轮询、取消/续跑、候选摘录跳原件页。
- [ ] 待办汇总卡四组计数正确、下钻滚动高亮、绿条措辞事实性。
- [ ] 工作台每条 IN/EX 有判定或无法判定原因；过滤词无反向歧义；右栏原件可加载。
- [ ] 报告打印：导航隐藏、表格跨页、无法判定清单在前、全文不截断。
- [ ] 正式模式全站无"开发中/后续版本开放/界面试用"（深链 redirect 验证）；trial 模式不受影响。
- [ ] 术语：全站无"快照/读法/判读/两路"面向用户暴露（前端 grep + 后端投影文案）。
- [ ] 1080P/2K/4K 真实浏览器验收 + 截图归档（Slice 5）。
