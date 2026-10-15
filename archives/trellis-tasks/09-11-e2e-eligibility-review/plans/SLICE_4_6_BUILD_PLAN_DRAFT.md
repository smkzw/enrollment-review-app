# Slice 4/6 构建方案（草案 v1，供多模型审阅）

任务：09-11-e2e-eligibility-review。日期：2026-09-11。
基线：383fd08 + Slice0 修复（PHASE5_V2_TABLES 登记、test_migration_0022、惰性摘要查询）。

## 0. 范围与目标

用户裁决：完整网页端 APP、消灭一切"开发中/后续版本开放"占位、端到端走通入排审核全流程。本方案覆盖两个 Slice：

- **Slice 4**：判断检索界面 + 待办汇总卡 + 术语统一（4A/4C）。
- **Slice 6**：入排工作台真实数据化（正式模式 /workbench）+ 报告页真实导出 + 移除全部占位页。

## 1. Slice 4 详细设计

### 1.1 前端 API client（frontend/src/api/judgment-search/）

对齐后端 `app/api/v2/judgment_search.py` 四端点：

| 端点 | 用途 |
|---|---|
| POST `/subjects/{sid}/review-episodes/{eid}/judgment-search-jobs` | 入队（requirement_ids 可空=服务端推导） |
| GET `.../judgment-search-jobs/{job_id}` | 状态+每条要求检索状态 |
| GET `.../judgment-search-jobs/{job_id}/results` | 候选摘录+未完成页 |
| POST `.../judgment-search-jobs/{job_id}/resume` | 续跑已取消 |

文件结构沿用 page-review 目录模式：`wire.ts`（类型）+ `judgmentSearchHttp.ts`（client）+ `judgmentSearchViewModels.ts`（严格解码，未知/缺字段抛 DecodeError）。

**状态轮询**：复用 useLoad + 2.5s 轮询（同 PageReviewTaskDetail.tsx:16-20 模式），localStorage 存 job id（同 useFactNormalizationJob.ts 模式），刷新后恢复。

### 1.2 入口与呈现（挂在哪）

**不新建页面**。挂载点 = SubjectsPage（受试者与档案）的证据面板区域旁，新增"书面判断检索"卡片：

- 无任务时：显示说明文字 + "开始检索"按钮（调用 POST，requirement_ids 留空）。
- 运行中：进度"已检索 x/y 页"，每条要求一行状态。
- 完成：每条要求显示 `status_label`（后端已给中文：已发现疑似书面判断待核对 / 本次提交全部资料未检索到 / 检索未完成）+ 候选数；点击展开候选摘录列表（页码+通道+摘录文本）+ 未完成页原因。
- 已取消：显示"继续检索"按钮（POST resume）。

**判定依据**（PRD 验收）：候选摘录必须带原件定位（page_artifact_id/page_number），点击跳转 OriginalEvidenceViewer 对应页（复用 ProfileEvidencePanel 的导航模式）。

### 1.3 待办汇总卡（ProfileHighlights 旁）

数据源：patient-profile wire 已有 `gap_counts`（wire.ts:94/109 professional_judgment 等字段已存在）。前端聚合四组：

| 显示组 | 数据来源 gap_type |
|---|---|
| 待补资料 | record_incomplete + referenced_file_missing + required_procedure_not_done |
| 待研究者判断 | professional_judgment + observation_unverified(判断类) |
| 资料有矛盾 | 冲突组成员数（patient profile 已有冲突泳道） |
| 未能读取 | ocr_or_parse_risk + result_fields_missing + description_insufficient + date_or_anchor_missing |

交互：每组计数徽章，点击滚动到对应泳道条目并高亮（复用现有 itemById 索引）。全部为零时显示"本节点资料核对完整"绿条。

### 1.4 术语统一（全局）

| 现状 | 改为 |
|---|---|
| 快照 | 完整资料集 |
| 建立快照 | 建立完整资料版本 |
| 读法 | 识别结果 |
| 两路 | 两次独立识别 |
| 如 UAT-03（BoardToolbar placeholder） | 如 01-0031（真实受试者编号格式） |
| "界面试用"反复前缀 | 保留一处（帮助页），其余移除 |

落地方式：labels.ts 词表 + 各组件文案 grep 全替换 + HelpPage 同步；每处替换跑对应组件测试。

## 2. Slice 6 详细设计

### 2.1 后端只读投影端点（新增）

`GET /api/v2/subjects/{sid}/review-episodes/{eid}/eligibility-review`

装配（全部既有确定性组件，**零新模型调用**）：

1. `authority_from_active_episode` 取权威。
2. ClausePack 投影（`app/projections/clause_pack.py`）取当前规则集的全部官方条款（含父子、determination_mode、expression）。
3. `ClinicalFactV2Repository.list_for_authority` 取已发布事实 + `FactRuleLinkV2Repository` 取事实-规则双向链接。
4. `EvaluationContext`（app/domain/expression.py:30）+ `evaluate_expression` 确定性求值（数值/日期/时间窗/逻辑组合）。
5. `derive_component_decision`（app/domain/gates/assessment.py:295）把求值+缺口映射为终局判定。
6. 缺口信号：`EvidenceExpectationV2Repository.list_by_episode` + judgment_search_summaries（限定"本次提交资料"措辞）。
7. 原件定位：profile locator links。

响应结构（每条官方 IN/EX 一行）：

```json
{
  "rule_code": "EX-07", "rule_kind": "exclusion",
  "text_summary": "…", "parent_rule_code": null,
  "decision": "exclusion_triggered|exclusion_not_triggered|undetermined|not_due|not_applicable",
  "decision_label": "中文标签",
  "reason": "一句话中文原因（含无法判定的具体缺口）",
  "fact_refs": [{"fact_id": "...", "locator_id": "...", "page_number": 12}],
  "gap_type": null,
  "determination_mode": "deterministic|semantic|professional_judgment"
}
```

**边界**：undetermined 必须带 gap_type + reason；semantic/professional_judgment 类条款若事实不足 → undetermined（绝不猜）；本端点不写库、不产生 ReviewRun（Phase 7 的正式审核运行另行立项）。

### 2.2 前端工作台（/workbench 正式模式）

- routes.tsx:111 的 `interfaceTrial ? ... : null` 改为真实 WorkbenchPage（新写，不复用 stub 版）。
- 布局沿用三区模式（workbench.css 已有）：左=条款列表（按 IN/EX 分组、父子缩进、状态过滤：全部/无法判定/不符合/符合），中=选中条款详情（原文+结构化表达+判定+原因+关联事实），右=原件面板（复用 OriginalEvidenceViewer + ProfileLocatorList）。
- URL 参数 component/evidence 深链保留（WorkbenchPage.tsx:19-21 模式）。
- 从受试者档案页加"入排审核"入口按钮直达（带 subject/episode 参数）。

### 2.3 报告页（ReportsPage 替换静态占位）

- 数据：调用 eligibility-review 端点聚合。
- 输出：打印友好 HTML 单页（window.print() 即可，不引入 PDF 库）：受试者信息表 + 逐条判定表（判定/原因）+ 无法判定清单（缺什么、谁补、怎么补）+ 资料版本脚注（权威元组+生成时间）。
- 打印样式 @media print 已有基础（沿用 profile.css 模式）。

### 2.4 移除占位页

- routes.tsx：正式模式下 today/board/actions/projects-new 四个路由 component=null 且 showInNavigation=false——保留 trial 模式行为不变，正式模式导航只剩：方案工作台 / 受试者与资料 / 任务与系统 / 系统帮助 / 报告 / 入排工作台。
- AppShell.tsx:17-26 的"后续版本开放"文案对应移除（导航不出现即无该文案）。
- TasksPage stub 任务列表：改为真实 `/api/v2/jobs` 列表（端点已存在，详情已真实）。

## 3. 实施顺序与验收

1. Slice 4 后端无改动；前端三件套 + 组件测试（每组件行为测试：渲染状态/轮询/错误路径）。
2. Slice 6 后端端点 + 装配测试（fixtures 全链：规则+事实+缺口 → 判定输出；undetermined 路径必须覆盖）。
3. 前端工作台 + 报告页 + 路由清理。
4. 全量：后端 tests/v2 零失败 + 前端 vitest 全过。
5. Slice 5 真实实例联调（另文档）。

## 4. 风险与对策

| 风险 | 对策 |
|---|---|
| eligibility-review 装配与 Phase 6 正式 ReviewRun 语义混淆 | 端点命名+文档明确"只读投影，非正式审核运行"；Phase 7 建正式 ReviewRun 时复用同一装配函数 |
| 术语替换漏网 | grep 清单化逐处替换+测试断言关键文案 |
| 占位页移除导致深链 404 | 路由保留 redirect 到 /protocols |
| 判定原因文案过长 | reason 截断到 120 字符，详情页全文 |

## 5. 待审阅问题（请审阅者重点回答）

1. eligibility-review 端点放在 api/v2 哪个 router 文件最合适（新文件 vs 挂 patient_profiles）？
2. 待办汇总卡的"资料有矛盾"分组数据源是否够（冲突组成员计数）？
3. 术语表还有哪些遗漏（审阅者自行 grep 补充）？
4. 报告打印页是否需要服务端生成（当前方案纯前端）？
