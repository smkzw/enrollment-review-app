# 入排审核系统：完整接管交接与阶段复盘

更新时间：2026-09-10 07:08 CST 后收尾。状态：用户明确要求完成手头工作后无损暂停，随后交由另一 Agent 接手。本文件是本产品线程的首要恢复入口，不是重新启动授权。用户向接任 Agent 发出继续实施指令后，再执行下文恢复步骤。

## 0. 接任者先读：不要重走的路

1. **只在下方 worktree 工作，不能在主 checkout 修改或启动。** 大量有效实现和证据未提交，单看 HEAD 会错判项目几乎没有进展。
2. **Phase 5 与 5.5 都未通过临床收口；claims_complete=false。** 不是已经可交付的系统，也不是从零开始的空壳。
3. 当前产品双模型是 **GLM-5.3-Flash low + Gemini-3.7-Flash high**。产品通过自己的 HTTP/OAuth 调用；针对性内容复核 high/high。不要恢复 MTPLX、MiniMax 或“手写第三读”的历史默认。
4. 最新判断检索模块已能调用、绑定、保存和回读，真实小样已跑；**尚未接正式持久任务、缺口生成和用户界面**。下一步是贯通这些已有模块，不是再造一轮叶子合同。
5. 用药分项匹配仍是用户批准的**隔离扩测**，没有正式自动写入病史的批准。不能因为新 Agent 接手就忽略该边界。
6. 不重新读取全部24页来恢复已有规范化；先核对现有回执和兼容性。新判断检索确实未搜索过的要求不能凭旧主读结果虚构“没有判断”。
7. 新框架迁移、详细多模型横评、同一校准样本继续刷提示都不是当前首要任务。先交付一个真实、可恢复、可追溯、可在页面看到结果的完整实例。
8. 不 reset、不 git clean、不批量删除未跟踪文件、不关闭其他线程本地模型。暂停只涉及本产品线程。

## 1. 工作区、线程与权威顺序

### 1.1 路径

主 checkout（仅用于辨认，不是本轮实施目录）：
`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app`

**唯一实施 worktree，以下记为 W：**
`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`

当前分支：`codex/phase5-clinical-facts-profile`。
当前 HEAD：`411832d8611ddd5ba9ac280df58261d40d358f75`。
产品线程：`01a071c0-eba6-7333-82c2-32a6dfc798aa`。
另一独立本地横评线程：`01a0813d-7937-7ff0-ae5f-c6e09eecd30d`。

当前 Trellis 任务：`W/.trellis/tasks/09-05-phase55-dual-vlm-page-review`。
历史父任务：`W/.trellis/tasks/08-22-phase5-clinical-facts-profile`。

### 1.2 必读权威文件（绝对地址）

按以下顺序读取，后来的用户明确指令优先于旧文件段落：

1. 全局原则：`/Users/smkzw/.codex/AGENTS.md`。
2. 项目原则：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/AGENTS.md`。
3. 架构设计书：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`。重点 R3 §3.3、§4.2、§5.4、§7.0、§7.2、§7.4、§11、§12；文头及后续修订优先，不能仅按文件名日期理解版本。
4. 接管工程设计：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`。
5. 总实施计划：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。
6. 当前纠偏计划：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md`。
7. 当前上下文：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/docs/PROJECT_CONTEXT.md`。首段最新状态优先，下方大量内容为历史。
8. 活动记录：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-05-phase55-dual-vlm-page-review/CHECKPOINT_20260908_MODEL_BENCHMARK_PAUSED.md`。**同文件混有另一线程横评更新，只按产品线程标识恢复本任务。**
9. 首次接管审查：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-05-phase55-dual-vlm-page-review/ENGINEERING_REVIEW_20260905_TAKEOVER.md`。
10. 历史交接：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-05-phase55-dual-vlm-page-review/HANDOFF_20260905_GPT6_PHASE55_R3.md`。它是历史，不覆盖本文件。
11. Trellis：`W/.trellis/workflow.md`、相关 `W/.trellis/spec/`、当前 `task.json` 与 `prd.md`。
12. 视觉规范用户指定入口：`/Users/smkzw/.cc-switch/skills/kangzhe-design/SKILL.md`。读取当前实际文件，不擅用名称相同的备份版本。

全局机制实现：`/Users/smkzw/.codex/tools/hermes_workflow_guard.py`、`route_policy.py`、`conference_session_runner.py`。它们用于**工程执行/会商**，不是产品临床识别依赖。

### 1.3 文档与 goal 已知漂移

- 平台 goal API 在本次只读检查中已经是 `paused`，但 objective 仍有 MTPLX 第二主读、旧手写多读道等过时文字。不要执行这些旧路线。
- 本次未调用创建/完成/阻塞 goal，也未伪称通过工具更改了 goal 内容。现有工具只能完成/阻塞，不能改写活动 objective 或暂停状态。
- 接任后若平台支持编辑 goal，应以本文件第14节的新目标文本替换旧意图；不能把未完成旧 goal 标为 complete 来绕过限制。
- 原计划 Phase 5.5 行之前写“v21验证中”，本次回写为真实 partial 与检索尚未接线。历史223事实/19事件/10暴露属于旧链，**不是**当前 runtime05 的37/5/0，二者不合并计数。
- 主 checkout 文件可能与 W 中的未提交修订不同。先比较，不把主树旧文档覆盖 W。
- 项目AGENTS若仍写“重构处于设计会商、未批准实施”，那是早期阶段说明，已被用户多次明确继续实施覆盖；不得因此要求重新批准全部重构。本次暂停则是新指令，须等接任继续授权。

## 2. 用户真正要完成的产品

用户是中文母语、资深临床试验医学监查人员，专业但不想学习电脑、模型和提示词，也对视觉设计敏感。产品未来作为医学经理工作台子系统，当前目标是本地单Mac、单用户、直接启动，不建设登录/多租户/移动端。

期望流程：上传未经人工预处理的方案及受试者原件 → 选择预筛/筛选/基线等审核节点 → 系统解构当前方案相关要求 → 两独立模型读取原件 → 核对事实、日期、单位、否定、手写和证据归属 → 生成可回源的病史、用药、事件及Patient Profile → 依据当前节点评估 → 显示无法判定的具体原因和待补充资料 → 原件定位与后续回应闭环。

核心不是“页面能打开”或“JSON能过”：医学上不能把未记录当阴性，不能把药物处方当实际服用，不能把异常箭头当研究者判断，也不能把未读清当确实缺失。

### 必须持续保留的产品要求

- 从整个方案理解审核相关控制点，包含合并用药、洗脱、导入、访视、随机/首次给药前条件与例外，不只读取入排章节。**不等于每次把全方案反复OCR/重读**。
- 保留正式IN/EX编号、父子逻辑、组合/例外、当前修订。真实SAR/D001只是验证资料，不能把具体疾病、药物、阈值、评分或时间硬编码进共享逻辑。
- 方案原文及当前修订有权威性；Q&A/邮件/解释不能改写方案。
- 日期锚点先按方案明确规定；未明确锚点的回溯要求按用户要求在筛选和基线分别评估。缺日期保留精度/范围，不补造日期；后期资料不能静默改写早期审核。
- 各节点分别提供、分别审核；上传应支持去重、增量和不可变快照。更正保留原件与历史，并仅重跑受影响范围。
- 无明确阈值的检验异常，需要报告批注或对应节点病历中的研究者书面判断；仅标记异常不够。缺少判断应说明无法判定，不能落为符合/未触发。
- 两模型都确认在当前提交范围未见必要判断时，**不再停下来让用户二次确认**，直接在审核结果说明并保留补充方向。不能扩写成“研究者从未作判断”。
- 对读取冲突允许最多两轮有针对性的原件核查，仍冲突才交用户；这是临床内容核对轮数，和输出截断重试/429等待不是同一计数。
- 模型输出只是候选或证据关系；确定性条款由代码计算，研究者判断不能由模型替代。未核实事实不能先整理成正式病史，原件和疑问保留。
- 用药拆为药名、剂量、用法、起止/时间角色分别核实；部分得到确认不表示其他部分可猜测。当前自动部分采信尚未批准。
- 用户界面全部为原生中文临床用语，避免后台状态、log标签、“xx门”“xx信号”等；准确但精简。
- 宽屏1080P/2K/4K，原件右侧滚动，PDF/图片/文档保真；有可靠坐标才红框，未知坐标不猜、不画伪精确框。
- 不要求真人医学监查员试用作为推进条件；工程审阅、模型角色测试、原件QC、真实浏览器验收各自留证，不能互相替代。
- 用户要求不做专项安全测试；聚焦功能、来源保真、流程、质量与体验。不能因此放弃当前来源/身份/历史一致性检查。

### 上传格式的边界要明说

用户早期提出方案DOCX/PDF直接上传，后续已形成当前正式DOCX方案范围，平台旧goal也明确DOCX。接任以最新设计/界面承诺核对，不静默宣称方案PDF全链已支持；受试者PDF/图像原件链已是现有产品范围。不得让用户先人工整理方案再交模型。若决定扩展方案PDF，这是相邻功能规划，不是本次暂停前已完成事项。

## 3. 来龙去脉与重要纠偏

| 时段 | 建设方向与后续修正 |
|---|---|
| 2026-08设计与早期实施 | 从既有入排工具重构为规则、证据快照、持久任务、事实/Profile及审核行动分层；Trellis按Phase推进，Phase0–4档案保留。 |
| Phase5初期 | 配置缺key、端点502、取消任务/快照状态等阻碍真实规范化；用户要求显式worktree env、先查现场，不复用cancel_requested任务、不激活失败快照。旧历史根因不能无日志编造。 |
| 09-01修订 | Phase5收口优先，新增5.5金标与模型评测；双VLM独立模块，避免扩巨型文件。旧链能生成大量事实并不等于内容正确，出现药名猜测/邮件当暴露/绑定错位。 |
| 09-02 R3 | 单阶段对称双VLM，不采用“识别双模型再评估双模型”；页层去判定词，ClausePack增加determination_mode；OCR侧车，规范化先于对账。初始GLM+MiniMax与Qwen手写第三读后来被模型路线新指令覆盖。 |
| 09-05接管审查 | 修复正式入口、来源闭包、持久执行/恢复、规范化输入、原件呈现等；形成接管设计与A–G恢复计划。禁止依赖本机个人Hermes/OMP执行产品识别。 |
| 后续模型/额度调整 | 用户批准共享思考+正文48000，测试又提高到至少64K；本地候选曾反复变更并要求串行平台。当前产品使用GLM/Gemini65536小样；不要把旧预算或其他线程131072配置覆盖当前产品。 |
| 双读一致性问题 | 两模型用不同字段粒度描述同一事实，严格对账产生大量未核实内容。用户允许受限对应关系隔离试验，不允许直接自动接受。错误必须回原图核实，不靠删单位/补日期追求一致。 |
| 09-08至09-09 | 当前双读24页完成，但整理因源定位、编号类型、跨调用归属、长思考、发布/回放成本等暴露问题；多次隔离运行，各有不同终态，不能拼成一个成功结果。 |
| 09-09产品收敛 | 正式仅GLM+Gemini，详细横评后置；另线程继续本地harness修复横评，与本产品状态分开。允许评估内嵌pi，不代表必须迁移。 |
| 09-10用药及判断检索 | 用药校准暴露相邻时间/剂量归属问题，仍隔离；更正后疑问保留修复完成。判断检索建立来源、候选、原始回答绑定和存取；单页/合批真实小样完成，但正式接线未完成。 |
| 本次交接 | 用户要求完成手头任务、无损暂停并交给其他Agent。已停止开启新实现；执行盘点与独立会商已终态，130项相关测试通过，写本交接。 |

### 已失效要求不要复活

- “全程自己做、不用执行会商”已被后来明确恢复机制覆盖；当前要按最新全局机制选择执行/会商，等待120分钟上限，不反复催促。
- MTPLX旧27B默认、FlashNext手写第三读、FlashNext第二主读、MiniMax第二主读都不是当前产品默认。保留历史证据，不将旧响应改名冒充新模型。
- 大范围模型横评暂后置。14+候选、三平台九组合的其他线程结果不能证明当前GLM/Gemini产品验收。
- 曾经授权从OMP迁移密钥不等于允许运行时发现其配置或委托其harness识别。产品独立传输已建立。
- 用户过去反复暂停/恢复不等于允许新Agent根据老消息自行恢复；本次暂停以最新用户接任指令解除。

## 4. 技术地图：代码在哪里、负责什么

技术栈按当前锁定文件：Python3.12、FastAPI、Pydantic2、SQLAlchemy2、Alembic、SQLite；React19/TypeScript/Vite、Vitest/Playwright、Lucide。精确版本以 `W/pyproject.toml`、`W/uv.lock`、`W/frontend/package.json` 为准，不擅升级。

| 区域/路径（相对W） | 职责与阅读重点 |
|---|---|
| `app/domain/contracts/` | 规则、阶段、事实、页判读、来源定位、资料期望等结构化合同；不是临床最终判定。 |
| `app/projections/clause_pack.py` | 从已发布规则投影ClausePack；对照真实规则版本，不以横评DOCX临时抽取包当权威。 |
| `app/agents/` | 方案语义/事实整理Agent框架；`protocol_semantic_transport.py` 历史类名含DeepSeek不必然实际调用DeepSeek，检查provider/receipt。 |
| `app/llm/page_review_harness.py` | 双主读提示、直接传输、实际读页、失败/截断路径；`gemini_transport.py` 是产品OAuth原生调用。 |
| `app/domain/page_reconciliation.py`、`page_normalization.py` | 规范化与对账；不要把格式归一化变成临床事实更改。 |
| `app/services/page_review_job_service.py`、`page_review_job_executor.py` | 已接API的持久逐页作业；冻结身份/配置、独立读道、覆盖及取消恢复。 |
| `app/services/targeted_page_review_jobs.py`、`targeted_page_review_executor.py` | 两轮辅助原件复核，保存原始结果，不自动改写正式事实；可复用持久runner模式。 |
| `app/services/fact_normalization_*` | 从经核实输入生成事实/事件/暴露候选及发布、Profile；确认具体运行是partial还是完成。 |
| `app/services/fact_correction_*`、`fact_expectation_gaps.py` | 事实更正及重投影，保留原疑问来源，不让更正误清空尚未解决缺口。 |
| `app/storage/fact_authority.py` | 当前快照/节点/规则/完整处理修订校验；新增validate_and_get_revision避免同次重复解码，不跨调用缓存信任。 |
| `app/storage/`、`app/workflow/` | 仓储、作业步骤/租约/检查点/恢复。复用它们，不新造持久任务框架。 |
| `app/evidence/artifacts.py` | 内容寻址原始图片、文本、请求/回答工件；保存并按hash回读。 |
| `app/projections/evidence_expectations.py` | 资料覆盖、缺失、未来阶段、来源弱等投影；已有stage_rank只是阶段先后，不等于条件适用性。 |
| `app/api/v2/` | 正式HTTP入口；`page_review.py`已连接普通双读，新增判断检索还没连接。 |
| `frontend/src/pages/` | 项目、受试者、资料等页面；存在不代表所有数据为真实正式链。 |
| `frontend/src/components/evidence-workspace/` | OriginalEvidenceViewer、PageReviewTaskDetail、TargetedReviewDetail等原件及任务明细。 |
| `frontend/src/components/profile/` | Profile泳道、来源列表、更正记录、整理状态、原件面板。 |
| `frontend/src/api/patient-profile/`、`features/patient-profile/` | Profile接口和显示模型；小心fixtures/stub，不以假数据验收。 |
| `frontend/src/features/fact-normalization/usePageReviewJob.ts` | 最近完成/可恢复任务指针等；历史入口不应自动再触发整理。 |

本次没有完成“整个代码库每个组件逐行复核”；上表是接管导航。更早审查结论见接管review，不要把导航表写成全面验收。

## 5. 当前完成度：实现、接线、验收分开

| 项目 | 实际状态 |
|---|---|
| Phase0/0.5/1、1.5、2/3/4 | 原计划记已完成/归档；本次没有重新全量验收这些历史阶段。Phase4部分扫描来源text-only，无坐标不能画红框。 |
| 工作树env与启动预检 | 历史收口记录已实现；当前显式`.env`产品GLM/Gemini调用实际可用。不要打印key。 |
| SAR规则发布 | 历史记录修订16已发布；runtime05隔离规则集revision1是另一层身份，不能混为同一编号。 |
| 正式双页读、任务API、取消恢复、覆盖绑定、规范化入口 | 已实现并有测试/隔离运行；不等于整个系统临床正确。 |
| 24页GLM/Gemini主读 | 已完成，回执可复用；不能说24页临床信息完整。 |
| 两轮手写复核 | 已有正式API及真实两轮记录；原件SS/CS仍分歧，正确保留未核实。 |
| 视觉摘录来源链 | 已接候选、存储、发布和Profile读取的合成整链；真实整例QC仍欠。 |
| 更正后缺口保留（D1） | 共享修复和相关回归/独立复核完成；旧状态无法复现时保留未核实，不重造旧临床结论。 |
| 判断检索（D2前置） | **模块和隔离脚本完成，正式任务/缺口/API/UI未接**。 |
| 用药分项对应 | 仅隔离试验，有真实反例，未达到自动采信条件。 |
| 31001事实/事件/暴露/Profile | 当前runtime05 partial；未临床收口。 |
| Phase5.5产品金标验收 | 当前组合未完成同金标全链复跑；历史金标不自动等于当前产品成绩。 |
| Phase6–9 | 原计划未开始；不因基础测试多而提前宣布进入。 |

### 5.1 当前最重要的真实运行

隔离目录：`W/artifacts/phase55-takeover/20260909/glm-gemini-product-runtime-05-verified-64k/`。
数据库：该目录 `enrollment-review-v2.sqlite3`。
规范化job：`ecf027d8ef8d4d53999ba0ba41a2163d`。
规范化run：`af200d2e98104dd78589d9257deef7c1`。
已观察状态：步骤15/15完成，但run为partial；37事实、5事件、0用药暴露、54保留事项。
**这不是最新又跑了一次，只是当前保留运行。步骤完成不等于临床完整。**

当前权威身份供恢复核对，不可硬编码进产品：

```text
project_id=draft-project-09b593a721e7
protocol_version_id=draft-version-09b593a721e7
subject_id=0675cabcc979452dbdd5f5c1570c36d8
review_episode_id=59b98368e962465ca5d62ff55b4da07d
episode_revision=4
evidence_snapshot_v2_id=2685d8e0c0a948ff83a13cb7952eb915
complete_processing_revision_id=complete-529c2876e47544c1824edae2e923d11a
rule_set_id=ruleset:draft-version-09b593a721e7:phase_iii
rule_set_revision=1
coverage=subject-page-coverage:0dc545b481fb5962d9622c3172c52827
```

### 5.2 最新判断检索能力与真实小样

新增/主要文件：
`app/domain/contracts/judgment_search.py`；`app/domain/judgment_search_coverage.py`；`app/llm/judgment_search_reader.py`；`app/services/judgment_search_source.py`；`judgment_search_results.py`；`judgment_search_artifacts.py`；`scripts/run_judgment_search_probe.py`。

- 当前单目标提示 `judgment-search-reader/v4`，批次提示 `judgment-search-batch/v1`，单v4保持兼容。
- 目标从当前已发布父条款原文、子项表达式、资料要求构建，不只发送可能含“上述疾病”的脱离上下文description。
- 每页区分手写与打印病历分析；状态found/not_found/unreadable/ambiguous只是检索状态，不是入排判断。
- 保留原文、独立uncertainty_note；坐标固定标记unverified，不猜单位/缩放。
- 当前scope为24页完整供给清单，不证明外部所有资料已到齐。
- 两独立读道、来源hash、目标hash、当前版本、实际响应模型与原始回答都绑定检查；未知模型不能算独立双读成功。
- 批次每目标必须有结果，漏/多/重复ID整体失败；不同目标合法相同摘录不因相同文字而自动拒绝，也不自动采信。
- 工件存raw_response、完整回执/原始回答保留；读回重核当前来源。没有正式任务索引和重试编排。
- `candidates_present`仍可同时带缺页，消费者必须看状态和缺口列表，不能只看标题当全部读完。

最新目录均在 `W/artifacts/phase55-takeover/20260910/`：

| 目录 | 样本与结果 | GLM/Gemini耗时 |
|---|---|---|
| `judgment-source-probe-v4-report1-sige` | 检查报告单第1页、单目标：GLM ambiguous，Gemini found，手写前缀/归属未核实 | 4.929 / 7.728秒 |
| `judgment-source-batch-v1-report1` | 同页两目标：相关IN目标保留上述分歧；EX目标双读未见；每模型一次调用，结果存取往返通过 | 6.148 / 16.760秒 |
| `judgment-source-batch-v1-page9` | 病历第9页、两目标均未见相关判断；没有把签名/常规医嘱误作判断 | 10.860 / 5.878秒 |

以上为校准小样，不是独立留出集，不是完整覆盖。单页24页scope的每目标仍有46个未测“页×读道”结果。两目标批次共享同一原始completion，**token/费用按每模型实际调用计一次，不能按每目标回执重复累计**。只证请求数减少，未证明端到端提速；没有按账单核实API费用。

可靠原件身份（本次只读查源库确认，纠正两份审阅报告的名称误写）：
- `f55350a8cb5726dd2500151b6f3264fd310b1e3efd8c4dd80a893e65c4cd42c5` = `31001-病历.pdf`；本次病历第9页不是检验页。
- `7462fdcc295840431f0d9ae270c4a82cf63420bfdbb1d1f52ada3b78972f007a` = `31001筛选期检查报告单.pdf`；本次报告第1页不是病历页。
- 页号不能与整个队列索引混用；旧手写复核报告第1页对应队列索引10。

### 5.3 仍保留的错误及其意义

- v1 Gemini完整JSON代码围栏被严格解析器拒绝：v2支持完整单围栏，原失败不改写成成功。
- v2 GLM将签名占位/常规医嘱当相关候选：v3校准改善，不能据校准页推出总体精度。
- v3 GLM遗漏不清前缀：v4要求独立uncertainty_note保留不清位置，不在摘录中补字。
- Gemini认为手写为CS，GLM仍不确认：保留分歧，不反复加提示直到强迫一致。
- 未知坐标单位只作候选，不据其画红框。

### 5.4 用药试验：已批准什么、还差什么

详情：`W/artifacts/phase55-takeover/20260910/MEDICATION_EXPANDED_FINDINGS.md`。
实现：`scripts/medication_component_experiment.py`（v5.2）与`run_medication_component_experiment.py`。

已改善：区分实际用药/处方/购买/明确未用药/非用药/不明；不把疾病起病时间变成用药开始；未知HR不展开药名；三份处方不合并三倍量。
仍失败：相邻病史“持续中”归属、页尾日期碎片、每喷规格与每次剂量、相同值的日期精度标签、购买不能证明服用。
v5约26输出25结构绑定，v5.1约14输出14绑定；不是40独立样本或准确率。31006已用于调提示，必须改称校准集。
同输入GLM low约7.448/9.058秒，high约110.107/155.844秒，纠正部分剂量但有剩余差异；不能因此全系统升high。v5.2仅离线比较语义修订，未重跑模型。
下一步是预先定义分项判据+新留出资料，不是v5.3继续同页刷结果。评测通过后，再向用户申请正式接入。

## 6. 为什么耗时久、为什么像在原地打转

### 6.1 首要责任在推进方式，不应归咎用户或模型

**我把完成单元反复定义为“一个模块+一批测试+一次审阅”，没有优先定义为“用户能从真实入口完成一件事”。** 新判断检索已经有来源、Schema、读器、装配、存储、探针，却仍无正式任务消费者。局部质量提高是真的，但对用户的新增可用能力落后于投入。

第二个问题是验证重心失衡：重复做底层重解析/身份校验/合成测试与同族会商，而端到端执行、恢复、缺口呈现、Profile原件QC一直被写成下一步。严格检查本身有价值，但边界检查不能无限成为推迟接线的理由。

第三个问题是不断在同一组校准页上发现新差异、修提示、再验证。没有预先冻结独立留出集和终止条件，循环自然不会结束。用户看到的是一直忙，却始终不能用。

第四个问题是记录持续叠加、模型路线和goal漂移、另一横评线程混用活动记录，增加恢复成本。没有及时把“最新有效决策”压成一个可靠入口，接续时容易回到旧问题。

第五个问题是工程执行/会商拆得过细。每轮初始化、读取上下文、生成报告都耗时，且目前多为同GLM模型家族，独立性收益有限。下一轮应让执行单元覆盖完整纵向功能，会商审阅冻结的端到端结果，而不是继续每个小助手都开一轮。

### 6.2 已有真实技术瓶颈，不能一笔抹去

| 瓶颈 | 证据/现象 | 合理方向 |
|---|---|---|
| 模型输入任务过重 | 正规化密集组长思考；runtime03成功调用约83%输出为思考，四次约34分钟；不是全部由格式重试造成 | 已核实内容和待核实内容分开、缩小定向问题，别让模型反复重建整例 |
| 一致性判据过于依赖表述 | 同事实字段/粒度不同，已读到仍不能进入正式病史 | 保留严格来源，做受限语义对应的独立评测；不能删单位/猜日期 |
| 源链语义不一致 | 视觉摘录和OCR字符串不完全相同曾被当作无来源；数字登记号曾被误作测量值 | 视觉来源合同、编号类型/单位校验已修，继续来源QC |
| CPU重复验证 | 8处来源检查25.860→3.279秒，约7.9倍仅该段；原finalize曾约56分钟 | 复用同一次验证结果，不关闭验证，不把局部倍数冒充整例加速 |
| 更正后疑问丢失 | 更正重投影gap_signals空可能把未解决疑问清掉 | D1共享重建和来源保留已修复 |
| 研究者判断语义 | 报告异常、签名、病历综合结论与具体条款判断不是一回事 | 限定本次供给资料、明确对象/节点、缺失/歧义分开 |
| 本地平台配置/生成问题 | 另线程发现MTPLX AR兼容开关丢失、重复生成/断流等 | 保留其证据，不作为当前GLM/Gemini产品继续延期的前置 |

对外费用、整体P50/P95、所有模型优劣尚无完整可比数据，不能编造。

### 6.3 现在不建议整体换harness

当前已有持久runner、API、直连模型、任务恢复与来源仓储。Pi可以提供通用代理循环，但不会自动解决：条款适用性、药物时间归属、研究者书面判断、原件定位、Profile与审核结果同源。现有证据不足以支持此刻大迁移。

保留未来用轻量SDK降低传输/工具调度重复的可能；必须有具体瓶颈、许可证/集成成本、受控等价测试。不能把“换一个成熟框架”当本轮停滞的万能解法。

## 7. 独立执行/会商：已做与未采纳意见

本次暂停收尾充分使用批准runner，全部已自然结束、无fallback：
- E03：`runs/execution/written-judgment-search-contract-20260910/pause-inventory.md`，GLM-5.3-Flash:max，同执行会话。
- C03：`runs/conference/written-judgment-scope-20260910/pause-retrospective.md`，GLM-5.3:max，**新会话**只读阶段复盘。
- 此前同任务报告：`receipt-binding.md`、`receipt-artifacts.md`、`batch-candidate-reader.md`；会商`integration-cost-review.md`、`supplied-absence-semantics.md`。

限制：C03文本路由不能看原图，且与执行者同GLM家族；不是独立视觉医学审签。原图核对由所有者做，报告内图片结论不能冒充目视。

所有者采纳：停止新增叶子合同、先纵向接线；不整体迁移harness；不继续刷31006；本次供给范围缺判断不二次打断用户；缺页和候选分歧留存。

**必须纠正的审阅表述：**
1. 审阅盘点把两份PDF类型写反；本次查数据库`file_name`已核实，正确身份见§5.2。
2. `stage_rank`只解决尚未到期，不能证明条件适用、同阶段具体节点或对象关系。下一实现不能只加一个stage_rank就宣称D2完整。
3. 已引用未提供的文件应保留`referenced_file_missing`，不能一律变成`observation_unverified`。
4. “未见判断”不存在可引用的判断原文，不能伪造摘录/红框。应链接已检索资料范围及方案要求。
5. 相同摘录跨目标不必然是污染；不能用文本重复启发式无条件拒绝。
6. 回执hash与重解析不是外部鉴证；必须由正式调用/持久任务记录绑定，但不再新造证书框架。

## 8. 接任后的具体计划：先完成一条真实纵向流程

### 第一步：只读接管，确认未被另一线程修改

- 对照本文件、最新用户消息和`product-pause-state-0708.json`，核对W、branch、HEAD、相关文件SHA256及当前task状态。
- 读取最新全局AGENTS/Ponytail/Trellis层规范；执行机制要用实际live路线，不硬抄本次zcode模型选择。
- 只读核对runtime05作业、租约、活动节点/快照/规则；旧cancel_requested或失败快照不激活。
- `.env`只核变量是否已配置和实际路由，key不输出；不读个人OMP当运行依赖。
- 不启动本地模型，不重跑24页普通双读。先确定新任务真正缺的是哪一段。

### 第二步：一次完整执行单元，把已有检索接入现有runner

范围：一个当前已发布、语义可明确的要求组，一个受试者当前节点，完整供给页域，两个独立直连模型。

1. 从服务端当前authority准备要求、父条款/子项和页域，不接受客户端伪造scope或手工复制ID作产品信任来源。
2. 复用JobService/JobStore/PreparedStepResult与原件ArtifactStore；按页×读道保存结果，按有界目标组一次调用，不做每条要求独立全页扫。
3. 冻结提示/目标组/模型/预算/来源版本；重启只复用兼容已成功回执；失败明确保留。补取消、租约失效、恢复、部分失败的真实临时库测试。
4. 复用现有失败语义：length按明确预算重试一次、429等待不消耗内容核查轮次、过滤/端点异常不算not_found。两模型独立计数，不能因共享batch重复计费/计读。
5. 最终装配前再次核对当前来源/目标；候选、未测、读取失败和歧义分别保留。批次失败不能把缺失目标补成未发现。
6. 不为存取再造索引框架；需要登记时使用既有任务检查点的工件引用。

完成标准：从正式入口入队，可取消恢复，已成功结果不丢，当前引用可回读；不是“新增模块单测通过”。

### 第三步：形成正确的“无法判定原因”

- 先判明确当前要求是否需要书面研究者判断、是否到期、是否适用于当前对象/节点；条件依赖不明时保持未决。
- 找到候选不等于已确认判断；作者、对象、对应测量/时间不明继续核对。
- 全部当前供给页双读对该要求明确未见，且没有相关歧义/失败/已知缺文件等冲突条件时，生成**本次提交资料范围内**的professional_judgment缺口。
- 已知缺文件保留原类型；未读清保留未核实；未到期保持future-stage；不得让它们互相覆盖。
- 使用现有EvidenceExpectation投影和更正保留链，避免补资料/更正后静默清空旧疑问。
- Phase5仅形成结构化缺口，正式ActionRequest按后续阶段和当前设计接入，不为了漂亮演示提前写最终入排结论。

完成标准：同一正式输入能在Profile/资料要求中看到自然中文原因、对应条款与检索资料范围，状态不误升为符合；无需用户再次确认“确实缺判断”。

### 第四步：代表受试者QC并决定Phase5收口

- 复用合法24页主读，不使用历史不同模型输出拼接；在新隔离后继执行需要更新的整理。
- 对37事实/5事件/0暴露/54未决逐类对照原件，明确0暴露是证据不足还是产品漏接，不能用“没通过对账”敷衍。
- 另走用户已批准的用药隔离扩测：预先冻结分项比较判据、新独立留出资料、实际处方/服用/购买/否定/部分日期等，不再调同校准页。未获正式采信批准前不接入。
- 筛选和基线分别验收，不把一个节点成功外推另一节点。
- 通过后才回写Phase5 PRD/计划/claims_complete；任何不足保留清单。

### 第五步：Phase5.5与之后

- 当前GLM/Gemini产品在既有金标上做必要质量复核，满足现有退出门槛；不要恢复广泛多模型竞赛作为前置。
- 历史金标目录：`/Users/smkzw/tmp/ie-vlm-benchmark-20260902/`。计划记载71页、SAR事实832、7例条款158；**本次未重新核全部文件与标注质量**。先核hash/版本/争议和适用当前Schema，不把历史成绩转移给新harness。
- 已设门槛：双模型并集事实召回≥0.95、金标负判定静默漏判0；新增采信阈值仍需用户批准。阈值是产品验收，不是单页JSON成功率。
- 真实浏览器1080P/2K/4K：资料任务→病史/Profile→原件→补充/更正→重算，验证刷新恢复与来源一致。没有坐标的材料不画红框。
- Phase6结构化条款审核，Phase7行动/批量/报告，Phase8新项目全流程临床验证，Phase9切换打包/清理。每阶段前后复盘，不同时打开所有阶段。

### 下一阶段推进纪律

- 每个执行包覆盖一条纵向用户功能和明确验收，不只交一个helper。
- 一次独立审阅冻结的接线结果；除实际缺陷外不为继续扩边界合同开新轮。
- 两次同类失败无新证据就换假设/拆任务，不追加额度或无穷调提示。
- 测试计数放证据附录，进度以“正式入口是否可用、临床来源是否核对”衡量。
- 记录在实质变化时合并更新，避免几十条“继续推进”堆叠。非用户要求不要自造阶段暂停。

## 9. 验证现状与可复制命令

最后实际聚焦回归：**130 passed，12.42秒，5条第三方SWIG警告**。命令在W：

```sh
.venv/bin/python -m pytest \
  tests/v2/llm/test_judgment_search_reader.py \
  tests/v2/llm/test_judgment_search_batch_reader.py \
  tests/v2/services/test_judgment_search_results.py \
  tests/v2/services/test_judgment_search_artifacts.py \
  tests/v2/services/test_judgment_search_source.py \
  tests/v2/domain/test_judgment_search_coverage.py \
  tests/v2/scripts/test_judgment_search_probe.py -q
```

`git diff --check`通过；未跟踪文件不会因这条命令自动得到审查。
最后一次全V2：4453通过、1失败、3跳过；唯一失败为并发测试假设doc-a先进入，已改为阻塞实际首个进入文件，单文件30项通过。**没有修复后全库零失败复跑**。不要把130与4453相加称全量。
本次无前端改动和新整链浏览器验收。历史手写明细页三档视口核验不能代表整应用。

真实探针入口（恢复后先读help和版本，不覆盖旧目录）：

```sh
.venv/bin/python -m scripts.run_judgment_search_probe --help
.venv/bin/python -m scripts.run_isolated_page_revision --help
```

探针分prepare/execute，prepare只读冻结源，execute显式`.env`、产品直连、独立attempt目录；已有attempt拒绝覆盖。新目录用于新尝试，不修改旧失败status。
本轮探针是实验入口，不是正式API验收入口。不要用`frontend`的`build:e2e`（含stub标记）或`start_v2_uat.sh`静态试用入口冒充完整产品服务。正式启动先读`scripts/start_enrollment_review.command`和`app/api/v2/app.py`，核对端口/数据根/显式env，暂停状态下不要启动。

## 10. 无损暂停现场与文件保全

状态证据：`W/artifacts/phase55-takeover/20260910/product-pause-state-0708.json`，含SHA256、HEAD/branch和特定产品探针进程检查。
检查时相关产品探针、暂停盘点/会商无活动匹配；本轮启动的执行会话与测试均已取回自然终态。未停止任何其他线程服务，也不声称整台机器所有模型已停。
没有打开后续判断检索持久任务实现，没有新临床入队、没有原临床库写入。

Git计数口径：盘点普通porcelain为2033项（目录可折叠）；所有者`--untracked-files=all`为19668文件项，其中19353未跟踪、315已跟踪变化。**不是本线程新增19668文件**，包含大量共享证据/横评/历史工作。交接文档落盘后数字还会变化，以现场为准。
不做自动提交，不执行reset/clean，不清缓存/证据。用户早期允许阶段清理不覆盖当前无损暂停和共享工作保护。后续清理须先分清可再生物、唯一原回执、其他线程所有权。

需要保留：当前代码及测试、两设计/两计划、所有原始请求/回答/错误、runtime数据库/工件、Trellis记录、模型/提示/来源hash。不要为减小目录删除失败证据；不要迁移/整理Codex会话数据库。

## 11. 会商路线和接任工具注意

本次实际E03：zcode / zcode / GLM-5.3-Flash / max；C03：zcode / zcode / GLM-5.3 / max。是工程节点，不是产品识别节点。全局route随时间变化，恢复时核验支持/预算/manifest，不默换模型。
既有执行会话`sess_d36a476e-8bd3-4370-965e-471fedeabc95`已结束当前任务；不要因知道sessionid而自动发新任务。独立复盘是新会话，runner回执在对应输出旁；读实际metadata，不猜sessionid。
执行工具无apply_patch曾用原生Edit/Write，边界偏差已披露；所有者手动修订用apply_patch。接任节点要给明确允许文件、输入、验收，不让只读会商改代码。
用户要求120min长等待期间静默、不无故重复派发。长等不是等满120分钟，拿到终态即处理；不能因stdout安静判断模型失败。

## 12. 仍需未来用户决定的事项

- 用药/观察分项语义对应若新留出评测达标，正式自动采信需用户确认；目前没有达标证据，不提前问“是否直接上线”。
- 新增采信阈值按实际数字报批，已有质量门槛不能静默降低。
- 若重新扩大方案上传格式或替换当前双模型，先明确范围与证据，不假定旧横评授权就是当前产品默认切换授权。
- 正式发布/切换仍需明确验收；AI审阅不等于正式医学/项目签署。

不需要再问：是否允许隔离用药扩测、是否缺判断应显示无法判定、是否产品必须独立调用、是否只做宽屏、是否需要真人试用、是否保持原件、是否允许执行会商。均已有明确答案。

## 13. 证据索引补充

- 性能/规范化分析：`W/artifacts/phase55-takeover/20260909/NORMALIZER_SCOPE_FINDINGS.md`。
- 用药扩测：`W/artifacts/phase55-takeover/20260910/MEDICATION_EXPANDED_FINDINGS.md`及同级`medication-components-v5-*`、`medication-components-v51-*`目录。
- 本次源探针计划：`W/artifacts/phase55-takeover/20260910/judgment-source-probe-plan.md`，不是正式产品提示，金标/预期不进入模型请求。
- 判断检索真实结果：§5.2三目录及早期`judgment-source-probe-page7/page8/page9`、`judgment-source-probe-v3-*`；未执行的prepare目录不算调用。
- 原手写辅助两轮：同级上日`targeted-handwriting-report-page1-v3.json`及对应正式任务历史；恢复先用文件发现核对实际位置。
- D1独立复核：`W/runs/conference/written-judgment-scope-20260910/independent-risk-review.md`。
- 另一线程交接：`W/.trellis/tasks/09-05-phase55-dual-vlm-page-review/HANDOFF_20260909_HARNESS_REPAIR.md`。仅作协作边界/兼容性证据，不执行其旧session/端口命令。

## 14. 接任goal prompt建议（供用户/平台更新，不代表已设置新goal）

> 在唯一worktree phase5-clinical-facts-profile中，按最新R3设计及09-05恢复计划接管入排审核系统。先核对09-10交接与现场，保留共享未提交工作、原始研究方案/病例/数据库和全部失败证据。当前Phase5/5.5未临床收口，claims_complete=false。产品仅GLM-5.3-Flash low与Gemini-3.7-Flash high独立直连，针对性复核high/high，显式env/OAuth，不使用个人OMP/Hermes作为产品harness，不启动其他线程本地模型。先将已完成的判断检索来源、single-v4/batch-v1读器、回执绑定和工件存取接入既有持久任务，完成一条真实来源→双读→失败恢复→当前节点适用性→本次提交资料缺少书面判断的正确原因→Profile/界面的纵向实例。无判断不等于阴性，未核实不等于缺失，条件适用不明不猜测。用药分项匹配保持隔离，先新留出评测、后向用户申请正式采信。随后完成31001原件QC与Phase5收口、当前组合必要产品金标/大屏验收，再按Phase6–9推进。暂缓广泛横评、新harness迁移与继续堆叶子合同。按全局执行/会商机制，围绕完整功能派发和独立复核，长任务最多120分钟等待、收到终态接续，不反复自行暂停；只在用户要求、真正阻塞/必要决策或目标完成时结束。记录在实质变化时合并更新，测试和临床验收分别报告，任何未完成不得用完成标记或漂亮页面代替。

## 15. 交接的最终结论

这不是“模型完全不可靠导致做不成”，也不是“已经做完只差美化”。已经建成大量必要基础，真实双读可用，若干关键错误已修，但本线程没有把工作及时收束为正式用户流程，因而反复停留在局部完善。接任最重要的改变应是**以端到端可见成果为执行单元和验收单位**，而不是再从头调研框架或继续增加合同层。保留真实性和未决事项，不以降低医学要求换取表面跑通。
