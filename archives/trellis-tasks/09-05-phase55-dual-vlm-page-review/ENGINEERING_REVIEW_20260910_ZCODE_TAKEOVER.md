# 入排审核系统 ZCode 接管工程审查（2026-09-10）

状态：接管审查已完成，作为连续实施的前提基线。本文是第二份接管审查（第一份为 `ENGINEERING_REVIEW_20260905_TAKEOVER.md`），聚焦当前时点的接线缺口、工程问题定级与解决方案，并给出用户视角的产品建议。审查方式：只读核对暂停现场 → 权威文件全文阅读 → 双路代码结构摸底（后端任务/存储/LLM/缺口链路 + 前端页面/组件/文案）→ 基线测试。

## 0. 接管核对结论（无损暂停确认）

- worktree `W=.worktrees/phase5-clinical-facts-profile`，分支 `codex/phase5-clinical-facts-profile`，HEAD `411832d8` 与暂停记录一致。
- 暂停快照 `product-pause-state-0708.json` 中 9 个关键文件 SHA256 全部逐一致，无其他线程篡改。
- `.env` 具备 GLM Coding Plan、Gemini OAuth、CMS_SMK 等凭据（仅核对变量名，0600 权限，未输出值）。
- runtime05 隔离库只读核对：job `ecf027d8` state=completed 15/15，与交接描述一致（run 仍为 partial：37事实/5事件/0暴露/54保留）。
- 基线测试：前端 554 项中 1 项失败（字段白名单断言漂移，`isPageReview/isTargetedReview` 为合法业务路由字段，测试过时——本次已修正并复跑通过）；后端全量 V2 复跑进行中，结果回填本节。

## 1. 项目现状一句话

数据结构、持久任务框架、双模型直连读页、规范化、Profile 的"零件"已大量建成且质量不低；但**从用户正式入口到"看到缺什么"的纵向闭环没有一条完整贯通**，最新完成的判断检索五模块（来源装配/单页v4/批次v1读器/结果装配/工件存取）零消费，Phase 5/5.5 均未临床收口（claims_complete=false）。

## 2. 工程问题清单（按严重度定级）

### P1-A 判断检索未接线（阻断用户价值的第一缺口）

- 事实：`judgment_search_source/reader/results/artifacts` + `contracts/judgment_search.py` + `judgment_search_coverage.py` 完整且有 130 项测试；全仓 grep 确认无任何 `app/api`、`app/workflow`、`fact_normalization_*`、`fact_expectation_gaps`、前端消费方。结果只存内容寻址工件（`artifacts/raw_response/<sha>`），无 DB 表、无 job 类型、无 API、无 UI。
- 后果：用户最关心的"这条异常没有研究者书面判断，所以无法判定"在界面上不存在；professional_judgment 缺口目前只来自 assessment gate 的 unresolved items（`app/domain/gates/assessment.py:197`），没有"双模型确认本次提交资料内未见"的检索证据链。
- 解决方案（连续实施主线）：复用 `JobService/JobRunner/PreparedStepResult` 模式新增 `judgment_search` 作业类型 → API → 缺口信号 → Profile 呈现，五切片见 §5。

### P1-B 正式启动入口未收敛（对"双击启动"用户是阻断级）

- 事实：恢复计划 §11 已记录——根 `run.sh` 自称生产 v2 却启动 `app.main:app`+8900（legacy）；`run_enrollment_review_service.sh` 用系统 Python/旧应用；`start_v2_uat.sh` 仅静态试用页。`scripts/start_enrollment_review.command` 是正式入口候选但未按当前 create_app 核对端口/数据根/env。
- 后果：目标用户（不熟悉计算机）没有任何可靠的一键启动方式；错误入口还会给人"系统坏了"的观感。
- 解决方案：在纵向接线完成后、大屏验收前，收敛为唯一 `.command` 入口：显式 `ENROLLMENT_ENV_FILE`/数据根/端口核查、接 `app.api.v2.app`、预构建前端；旧脚本只读保留并加退役说明。

### P1-C 端到端验收欠账（流程性问题）

- 事实：交接 §6.1 自我复盘确认——完成单元长期是"一个模块+一批测试+一次审阅"；runtime05 是最接近真实的运行，但也停在 partial，未做原件 QC；"整例上传→整理→Profile→缺什么→原件定位"从未在真实浏览器走通过一次。
- 解决方案：此后每个执行包必须以纵向用户功能为单元（本次接管已按此组织）；验收问题清单化挂在任务目录。

### P2-A 术语泄漏与信息架构（用户视角的直接伤害）

- "快照"广泛面向用户（`UploadModePicker.tsx:19-25,70`、`EvidencePage.tsx:2021`、`PreviewReview.tsx:53,144`、`HelpPage.tsx:76,188`）；"读法"（`TargetedReviewDetail.tsx:33,38`、`PageReviewTaskDetail.tsx:26,41,44`）。用户是医学监查员：快照是照相术语，读法是内部分析概念。
- 解决方案：统一术语表——快照→"完整资料集"（动作为"建立完整资料版本"）；读法→"识别结果"（两路→"两次独立识别"）；一次全局替换 + Help 同步。低成本高感知，随 Slice 4 一起做。

### P2-B 缺口无汇总面

- 正式模式导航仅 3 项（方案工作台/受试者与资料/系统帮助）；缺口只散在 Profile 泳道单条目（`ProfileItemCard.tsx:155-166`）与首屏重点里；帮助文档承诺的"应备证据覆盖"面板在 trial-only 的 `/workbench`。用户无法一眼回答"本节点还缺什么"。
- 解决方案：个例档案首屏加"本节点待办汇总"卡：待补资料 / 待研究者判断 / 资料有矛盾 / 原件未能读取 四组计数+下钻。数据源就是 EvidenceExpectationV2 投影（已存在），只是聚合呈现。这是 Slice 4 的核心。

### P2-C EvidencePage.tsx 巨型单体（2094 行）

- 中心列 5+ 堆叠状态块、进度轮询/上传/OCR核对/启用版本/Profile 触发全部内联。
- 解决方案：本次不拆文件（避免无收益重构），只做两件事：状态块合并为单一"当前步骤"条、按术语表改文案。结构性拆分排到 Phase 6 前后。

### P2-D prd.md 模型路线漂移

- 任务 prd.md 仍写"GLM-5.3-Flash 与 MiniMax-M3 主读、Qwen 手写补读"，与 2026-09-08 用户裁决（GLM low + Gemini high 双对称主读）矛盾。task.json notes 是最新的。
- 解决方案：本次接管更新 prd.md 验收标准与 goal prompt，消除新旧执行者误读风险。

### P3（记录不动作）

- 前端 bundle 1.68MB（gzip 252KB）chunk 提示；无日常 lint 绑定；`/tasks` 不在正式导航（深链可达，暂可接受——证据页已有内嵌进度）。

## 3. 测试基线

- 前端：554 项，修正 1 项过时白名单后 554/554 通过（vitest，15s）。
- 后端：全量 V2 复跑（4615 collected）结果见文末回填；交接记录上次 4453 通过/1失败/3跳过，失败已修但未零失败复跑——本次补上。
- 判断检索相关 130 项此前通过，包含在本次全量中。

## 4. 用户视角产品建议（懒惰、视觉敏感、非技术、中文母语医学监查员）

### 本阶段必做（随纵向接线）

1. "无法判定"要说人话：`排除标准第X条：本次提交的资料中未见研究者对该项检查异常临床意义的书面判断，暂无法判定是否符合本条要求。`＋已检索资料范围＋补充方向。禁止工程词。
2. 个例档案首屏"本节点待办汇总"卡（见 P2-B），点击直达条目与原件。
3. 术语统一（见 P2-A）。
4. 双击启动（见 P1-B）。

### Phase 5.5–6 推荐

- 规则匹配工作台（Phase 6 正式开放给用户的核心界面）：每条官方 IN/EX → 符合/不符合/无法判定 + 一句话原因 + 原件定位，可按状态过滤；这是用户最终打开系统的第一理由。
- 审核结果单页打印/导出（监查员要交给 PI 签字确认的物理载体）。
- 方案歧义确认的批量模式（当前逐条，方案大时点击成本高）。

### 不建议（维持既有裁决）

- 移动端/多用户/登录、模型选择面板、桑基图雷达图类装饰图表、更换 harness/框架迁移、广泛模型横评、用药分项自动采信（未达标未批准）。

## 5. 连续实施切片（判断检索纵向接线）

目标：从正式入口入队一个"判断检索"持久作业 → 双模型读页 → 可取消/恢复 → 装配 coverage 摘要 → professional_judgment 缺口带检索范围 → Profile/界面中文呈现。全部复用既有模式，不新造框架：

- **Slice 1（持久作业）**：`judgment_search` job type + payload 冻结（scope hash/目标组/路由/提示版本）+ executor（复用 batch-v1 按页×读道提交，PreparedStepResult 模式）+ 取消/租约/恢复语义测试。
- **Slice 2（API）**：`POST .../judgment-search-jobs`（服务端派生权威，幂等）+ `GET` 状态/结果；注册进 `app.api.v2.app` 的 default_executors；通用 jobs 端点自动可见。
- **Slice 3（缺口）**：`fact_expectation_gaps.py` 消费 coverage summary——双读完整、当前适用、确需书面判断、无候选/歧义/失败 → `PROFESSIONAL_JUDGMENT` 缺口附"已检索范围"；已知缺文件保留 `referenced_file_missing`；未读清保留 `observation_unverified`；未到期保留 `future_stage_not_due`，互不覆盖。
- **Slice 4（UI+术语）**：Profile 待办汇总卡 + 缺口文案 + 术语表替换；前端测试。
- **Slice 5（真实实例）**：runtime05 后继（或新受控实例）跑一个要求组全链，核对中文呈现与原件范围；之后按交接第四步做 31001 QC 与 Phase 5 收口判断。

每个 Slice：聚焦测试 + 相关回归 + 证据落 artifacts；Slice 5 后做一次独立会商审阅冻结结果（按全局 manifest 路线），再决定 Phase 5 收口回写。

## 6. 验收口径（本次接管新增约束）

- 完成标准是"正式入口可用、结果可在界面看到、来源可回读"，不是"新增模块单测通过"。
- 测试计数只作证据附录；后端全量与前端全量零失败是本阶段工程底线。
- 临床收口仍按交接 §8 第四步（原件 QC）判定，claims_complete 维持 false 直到那时。

---
（回填）后端全量 V2：进行中，结果：见下。
