# 入排审核系统完整交接：2026-09-17

> 本文为V3之前的历史交接。用户随后批准V3，当前分工入口是同目录AGENT_ASSIGNMENTS_V3_20260917.md和prd/design/implement；全量双VLM、统一65K及旧下一步已被替代。本文Goal副本仅保留当时原文，不是现行目标。当前目标见GOAL_PROMPT_V3_20260917.md。本轮仅分工，未恢复产品运行。

## 0. 接手者先读：当前不是继续执行指令

本文面向下一位任务所有者。当前用户要求交接，原任务保持无损暂停；本文不启动服务、不恢复模型、不授权重跑旧作业。下一位 Agent 收到用户恢复授权后再执行下文步骤。

**一句话现状：** 系统已具有相当完整的方案、资料、审核和报告代码基础，但真实病例从原件读取到可靠采信、再到完整审核报告的最后闭环仍未验收。最近解决了本地模型切换的内存释放保护，以及原件方向和坐标的一部分问题；不是系统已完成，也不是仍停留在最初设计阶段。

**最重要的五点：**
1. 只在指定 worktree 工作，不在主 checkout 修改或运行临床应用。
2. 当前两位产品主读都是 MTPLX 本地模型，严格串行；不是 GLM+Gemini，也不是手写第三读。
3. 所有工程实现、模型接通、页面显示、临床准确性分别验收；`claims_complete=false`。
4. 先完成一个真实使用闭环，不再重复同一页的思考强度矩阵，不全面重写 harness。
5. 保留原件、原临床数据库、未提交代码、失败回执；禁止以清理为名 reset、覆盖或删除其他 Agent 工作。

## 1. 现场身份与可恢复状态

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`
- 主 checkout：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app`。本文中的源文件均指 worktree 版本，不应从主 checkout 取同名旧文件代替。
- 分支：`codex/phase5-clinical-facts-profile`。
- 当前审阅基线 HEAD：`4caf392c376ce7a9392fa2e8facc7d8a7f4e4a34`，2026-09-12，提交说明为 successor handoff。之后大量成果仍未提交，HEAD 本身不是完整交付。
- 当前任务：`.trellis/tasks/09-11-e2e-eligibility-review`。
- 父任务：`.trellis/tasks/09-05-phase55-dual-vlm-page-review`；更早父阶段为 `08-22-phase5-clinical-facts-profile`。
- 当前暂停记录：`.trellis/tasks/09-11-e2e-eligibility-review/CHECKPOINT_20260915_RETEST_TRIGGER_PAUSED.md`，**文头 2026-09-16 23时附近的暂停段优先**，下方多次“恢复”“尚待”属于历史。
- 2026-09-17 实际 get_goal 返回 `status=paused`。本次未修改目标状态。
- 本次只读状态盘点显示 git status 约 2365 行，含大量过程产物。不可把这个数解释成同等数量的有效代码修改。
- Sept16 暂停时本轮模型与会商均已终态。临时 Vite 5178 已结束；既有只读隔离服务 60414 保留，Ego 回到它的页面。**这些不是当前 PID/端口控制指令**；恢复前重新核验归属，不凭旧 PID kill 或重启。
- 不自动恢复任何旧会话号、functions cell、已取消或失败作业。其他 session 横评的句柄不属于本 session 可继续等待的工具句柄。

### 文档漂移警告

本次交接发现 task.json 仍写 Sept13 GLM+MTPLX、goal active、派发阻塞及 execution_paused_by_user=false，这些已过时。本次仅修正当前状态摘要；不删除历史审阅证据。

恢复 Plan 文头和阶段表有不同日期的陈述，部分“未暂停”“托管尚未接线”等已被 Sept16 成果覆盖。不能把这些文字当运行事实；应以本文状态、当前代码、冻结回执和最新用户指令共同核对。项目 AGENTS 中“仍在设计、未批准实施”是更早背景，后续用户已反复批准实施；但当前交接仍不等于恢复授权。

## 2. 权威来源与阅读顺序

以下全部是绝对路径；源码实现不能反过来覆盖临床方案权威。

1. 全局方法学：`/Users/smkzw/.codex/AGENTS.md`；项目规则：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/AGENTS.md`。
2. Trellis：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/workflow.md`、`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/spec/`。
3. 当前目标原文：`/Users/smkzw/.codex/attachments/3ebdd8dc-dc79-4a23-8649-8eef0387e7ee/goal-objective.md`；全文逐字附于本文末尾。
4. 临床/产品设计：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`。文件名日期不代表内容停留在八月；重点读 R3 的 §3.3、§4.2、§5.4、§7、§11、§12 修订裁决。
5. 工程设计：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`，重点 §6.1、§17 及后续复查条件修订。
6. 主实施计划：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。
7. 当前恢复计划：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md`，T0–T7 是贯穿原阶段的修复顺序，不是另一套替代产品。
8. 当前项目摘要：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/docs/PROJECT_CONTEXT.md`。
9. 最新暂停点：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/CHECKPOINT_20260915_RETEST_TRIGGER_PAUSED.md`。
10. Sept12 全量审阅：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/ENGINEERING_REVIEW_20260912_CODEX.md`。
11. 前任交接：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260912_SUCCESSOR.md`。
12. 历史目标草案：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/GOAL_PROMPT_20260912_REVIEWED.md`，不能覆盖当前附件目标。
13. 当前最终会商：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/runs/conference/enrollment-reading-recovery-prefix-20260916/evidence_single_object.md`。
14. 所有者对该会商的采纳/驳回：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/reviews/codex_conference_enrollment-reading-recovery-prefix-20260916_review.md`。

设计参考为用户最新指定的 kangzhe-design-3d，接手时读取实际 SKILL：`/Users/smkzw/.cc-switch/skills/kangzhe-design-3d/SKILL.md`（若路径变动，查当前技能清单，不用旧设计替代）。真实浏览器指定 Ego Lite。执行/会商应读取最新批准 route manifest 与 guard/runner，不照抄本文历史工程审阅模型。

## 3. 为什么建立这个系统

服务对象是一位中文原生、临床经验丰富、计算机与 AI 操作经验有限、希望少操作且对视觉敏感的医学监查人员。系统将作为医学经理工作台子系统，但当前交付是本地单 Mac、单用户、直接打开，不引入登录和复杂权限管理。

真正目标不是把扫描件转成文字，而是：
- 用户直接上传方案，系统理解筛选、导入、基线、随机/给药前相关审核要求。
- 用户在具体节点上传受试者资料，两位独立模型读取原件，保留摘录、出处、日期、数值、单位、手写判断及不确定性。
- 系统把可靠内容整理成病史、事件、用药暴露和纵向 Profile；按正式要求逐条判断，显示不能判断的具体原因。
- 用户从每个疑问直接看到对应原件和位置，明确由谁补什么、在哪个节点前补充。
- 后续补证形成新审核，早期结论与原报告仍可追溯。最终是否入组仍由有权人员决定。

用户不应手工预处理方案、逐页转向、理解模型路由/内部编号，也不应为了推进项目承担真人试用。测试者可以模拟临床角色，但不能冒充专业正式签收。

## 4. 需求演进：什么保留，什么已被替换

| 时期/主题 | 历史方向 | 当前有效结论 |
| --- | --- | --- |
| 初期架构 | 2026-08-12 设计与 Phase 分步实现 | 沿用主体，叠加 R3 和恢复计划，不从零重写 |
| Phase5 | SAR31001 规范化、Profile、启动凭据与失败快照问题 | 有代码基础；原件临床 QC 与整链仍未收口 |
| R3 | GLM 与 MiniMax 双主读、Qwen 手写第三读 | 单阶段对称独立双读原则保留；三读角色和旧模型名单已失效 |
| 模型多次调整 | GLM、Gemini、MiniMax、DeepSeek、本地多个平台横评 | 当前仅两个指定 MTPLX 本地主读；不恢复旧 fallback |
| 原方案输入 | 早期要求 PDF/DOCX | 当前目标明确方案 docx-only；病例 PDF/扫描/图片仍支持 |
| harness | 可参考/考虑 Pi 等成熟轻量实现 | 可研究但不是迁移指令；产品不依赖个人 Hermes/OMP/Pi 会话 |
| 时间窗口 | 曾未区分筛选/基线 | 明示锚点优先，未明示则分别按审核节点回溯 |
| 缺研究者判断 | 曾可能停下请用户确认缺失 | 充分核查本次范围后直接报告无法判定和需补判断，继续流程 |
| 用药对应 | 提出模型辅助配对 | 已批准隔离分项扩测，尚未批准正式自动采信 |
| 复查资料范围 | 是否需要“全部复查已提供”声明 | 不要求该声明；按本次资料判断，披露范围和已知缺件 |
| 测试策略 | 曾密集阶段测试、横评 | 当前不为每小步新建阶段测试；必要编译/关键核验保留，最终集中整链验收 |
| 前端 | kangzhe-design | 最新 kangzhe-design-3d，保留实际临床工作台，宽屏不做手机端 |
| 清理 | 曾要求删除旧路线代码说明 | 当前保护未提交工作和失败证据；只按核实清单清可再生产物，不批量抹历史 |
| 连续执行 | 多次自动短回合结束引发不满 | 恢复授权后连续实做；仅用户暂停/必要决策/真阻塞/真正完成时结束 |

原始方案、当前修订、受试者原件、人工入排跟踪表、原临床报告和历史库不得修改。真实方案是通用框架的检验材料，不是硬编码某疾病/评分/药物/患者答案的依据。

## 5. 当前架构与各部分职责

继续使用 FastAPI v2、React/TypeScript/Vite、SQLite/SQLAlchemy、现有 JobRunner、仓储和明确领域合同。不要再加一套任务队列，也不要把巨型文件继续作为所有新功能落点。

### 5.1 正式业务数据链

1. **方案来源与修订**：保存来源身份；独立语义执行器从 DOCX 结构理解审核有关要求。
2. **RuleModelRevision / ClausePack**：发布后的规则修订是权威。官方 IN/EX 编号与子组件 ID 分离；跨章限制进入正式要求全集，不能只留候选。
3. **节点与证据快照**：筛选与基线分别冻结资料范围、截止时间、处理修订；增量上传去重但保留历史。
4. **页产物与阅读视图**：原件图像及哈希保持；阅读视图是可逆派生件，方向与坐标绑定来源。
5. **独立双读**：A 全部页完成并释放模型后，B 读取同一冻结输入；普通事实与手写都由两者独立读取。
6. **对账**：先规范化，再比较对象、来源、时间、属性、数值/单位、极性；相似文本不是同一事实的充分证据。
7. **事实/病程/Profile**：从可采信集合整理；单源、未对应、冲突仍保存，不能为了让 Profile 非空而自动接受。
8. **审核求值**：确定性阈值、日期和逻辑由代码计算；语义谓词须有特定证据；研究者判断须有对应书面依据。
9. **ReviewRun / FinalAssessment / ActionRequest**：正式冻结本次审核、结论与行动；缺件与不符合不同。
10. **报告和界面**：全部同源、按冻结审核时间呈现；补证后生成新审核，关闭待办不直接改判。

### 5.2 临床约束

- “某类型事实存在”不等于任意临床条件已被证明。触发条件和例外条件分别绑定证据。
- 原文模型页读不输出最终符合/排除判断；页级允许的是观察、摘录及规定证据关系。
- 两轮针对性冲突复核是最多两轮，不是无上限重试；传输恢复另计，不能混不同轮次凑双源。
- 研究者判断至少区分：还没查、候选没核实、在完整本次范围内未见、已经核实存在。
- 检验异常箭头、签字、一般医嘱不是临床意义判断。方案没阈值且缺书面判断时，报告“无法判定”而非“满足/未触发”。
- 处方、购药、实际服用不同；药名、剂量、途径/频次、时间分别核实，不补日期。
- 部分日期保留区间；晚期资料不偷偷改写早期结论；复查不能默认“最新一次覆盖前面所有结果”。
- Profile 读取当前权威修订的完整累积集合，不能只取最后一轮 run，也不能把不同节点按 subject 粗合并。
- 红框须有核验定位；框落在图内只说明几何合法，不证明框确实指向对应原文。

## 6. 在整个计划中的位置

以下“已实现”指存在代码，不等于已通过临床验收。

| 阶段 | 实际基础 | 尚缺 |
| --- | --- | --- |
| Phase0–4 | 历史基础架构、规则/来源/节点等可复用 | 当前修订的跨章发布与真实消费仍需检查，历史归档不替代重验 |
| Phase5 | 事实、事件、用药暴露、Profile 与累计集合相关修订 | 当前原件 QC、来源闭合、31001 筛选/基线完整结果 |
| Phase5.5 | 双读合同、持久页记录、对账、恢复、模型接入大量实现 | 当前双模型临床质量、有效金标、全链及界面退出条件 |
| Phase6–7 | 正式审核、行动、冻结报告、摘要/批量等代码已推进 | 正式真实案例端到端证明，缺口与结论一致性 |
| Phase8–9 | 部分启动/只读展示/关闭恢复基础 | 留出项目、集中整测、安装恢复/备份、最终交付 |
| 全局 | 可持续修复的现有产品 | 未完成验收，不能发布“已可靠自动入排审核”的结论 |

恢复计划 T0–T7：
- T0：显式模型/额度/能力/环境身份与托管，基本已有；正式环境清单和消费者仍须现场确认。
- T1：谓词证据、时间与缺口矩阵等修复已有；真实临床闭环未完成。
- T2：组件/原件身份和显示改进；真实定位红框、恢复后继与用户更正入口待闭合。
- T3：跨章控制发布消费、累计 Profile/链接/期望；历史来源绑定与复杂复查条件仍待证据验证。
- T4：当前双模型、31001 双节点、金标及三档宽屏验收，未通过。
- T5：正式审核/行动/冻结报告/批量的实现已有，需真实同源结果。
- T6：留出项目泛化、性能与视觉验收未完成。
- T7：打包、恢复、清理与交付未完成。

用户后来允许 T4 尚未验收时继续构建已具备依赖的 T5–T7，这不意味着允许跳过 T4 或把 Phase5/5.5 标完成。

## 7. Sept12 接回时发现的主要根因

完整证据见 ENGINEERING_REVIEW_20260912_CODEX.md。这里列问题类别，不把当时数据库计数当今天状态。

- R01：宽泛事实类别被当作具体谓词/例外的证明，可能产生错误肯定判断。
- R02：即时页面投影与正式判定/缺口规则不一致，可能出现“通过”同时又有相关阻断缺口。
- R03：组件与官方编号混用，子项可能点击到第一个同编号父项。
- R04：不同文件同页码的引用可能选第一张，来源和真实定位没有贯通。
- R05：跨章节控制停留候选目录，未必被正式发布和审核消费。
- R06：Profile 可能只取最后 run，累计事实及校正后的来源/链接没有完全闭合。
- R07：未检索、候选未核实和查完未见被混淆，造成错误“缺失”或错误接受判断。
- 时间相关问题：部分日期、事件窗口、资料有效性和复查节点不应混同，具体逐项修订见上述审阅与恢复计划。

Sept12 曾有大规模测试输出，但它发生在随后大量代码修订之前，不能作为当前全库通过证据。历史事实数量混合多个 run/节点，也不能作为当前正确采信率。

## 8. 最近一轮已完成的工程工作与边界

### 8.1 本地模型释放

两个主读为：
- `mtplx/Youssofal--Qwen3.8-27B-MTPLX-Optimized-Speed`，xhigh。
- `mtplx/Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed`，xhigh。

使用产品显式 MTPLX 调用、实际权重清单、拥有者进程组和准入锁。原生 CLI 路径为 `/Users/smkzw/.mtplx/venv/bin/mtplx`，不是借用个人外部 harness。纯文本严格 JSON 与带图请求的兼容设置不同，不应统一误删。

已找到切换过快的证据：进程退出后，全机 wired 内存仍短时未回落；下一模型可能已开始加载。现有保护要求进程组结束、端口释放，并且 wired 回落到启动前基线加 1GiB 内，连续两次采样后才允许切换；失败保持禁止加载，不能假成功释放。

真实装卸验证记录 104 个样本、最大间隔 0.316 秒，没有双自有模型 PID；前一释放与后一启动的 wired 都是约 6.349GiB，最终约 6.325GiB。**这是有限实测，不是所有应用和所有内存状态下绝不重叠的保证**；全机 wired 是启发式，不能归因成某一模型独占内存。

核心路径：
- `app/llm/mtplx_owned_server.py`
- `app/llm/mtplx_model_lifecycle.py`
- `artifacts/mtplx-dual-basic-20260916/continuous-switch-memory-settle-v2/`

显式正式 env 上次核对缺 ENROLLMENT_MTPLX_MODELS_FILE，隔离运行有对应清单；恢复必须确认实际配置，不能读个人配置自动补默认。共享 OCR 扩展没有得到用户授权；新资料路径不应依赖外部 OCR 前置，旧 OCR 只能作为历史/侧车理解，不得为本任务擅自停止其他服务。

### 8.2 原件、阅读方向、来源与坐标

- 新增独立 reading_view：0/90/180/270 度、无裁切无插值的变换；原件与派生视图各有哈希、尺寸、版本；模型框反向换回原件坐标。
- 新 PageArtifact 尺寸改为实际渲染像素，避免 PDF points 当像素；旧版本仍可重现。
- 新 TXT 分页不再静默截断 54 行；按实际布局完整分割，保留字符范围与来源。
- EXIF 明示方向已处理，但这不是对横放扫描 PDF 的自动内容判向。
- 正式作业/请求留档/覆盖保存阅读方向，方向改变页必须重做 A/B 两路；未改变页在完整身份一致时可复用。
- 最后一项修复：恢复核对提示版本必须包括传输合同后缀，不能拿基础版本比较带后缀记录，也不能 split 后忽略差异。
- 原件查看器左右旋转已实现，图片与框同层旋转。**只是用户查看旋转，不会自动触发模型重新识别，也不会修改原件。**

关键版本供恢复时核代码，不用于强制迁移旧数据：
- 页读 prompt `page-review-r3/v20`；PageReviewRecord v6。
- 对账 `reconciliation/r3-v13`；页作业 v12；针对性复核任务 v8。
- 新方向阅读 `reading-view/quarter-turn/v1`。
- 新派生图请求回执 page-request/v2，原图 v1 保留。
- 坐标变换实际字符串 `slice4.0/v2`；render/v4、paging/v2。
- 托管部署身份仍 `owned-serial/v1`，内存等待策略单独记录，不因等待策略使旧临床输入无故失效。

### 8.3 源码入口地图

路径均以本 worktree 为根，修改前仍须读完整定义和相邻调用：

| 路径 | 职责/接手关注点 |
| --- | --- |
| app/evidence/reading_view.py | 来源保全、视图生成、坐标逆变换，不自动判向 |
| app/domain/contracts/reading_view.py | ReadingViewBinding |
| app/domain/contracts/page_review.py | 页记录、视图绑定、坐标与覆盖合同 |
| app/llm/page_review_harness.py | 实际模型提示/Schema/读页与格式恢复 |
| app/llm/page_review_context_layout.py | 旧稳定前缀实验；现已与 v20 默认重合 |
| app/domain/page_reconciliation.py | 对账、同视图约束，不做最终入排结论 |
| app/services/page_review_job_service.py | 冻结建任务、方向继承/变更与执行版本 |
| app/services/page_review_runtime.py | 正式运行入口 |
| app/api/v2/page_review.py | API 参数与任务入口 |
| app/services/page_review_job_executor.py | 读取/派生图存储/请求执行与回执 |
| app/services/page_request_receipt.py | 原件与阅读视图请求留档 |
| app/services/page_review_recovery.py | 复用、补读、前驱身份校验 |
| app/storage/page_review_repository.py | 覆盖和记录持久一致性 |
| app/services/targeted_page_review_jobs.py | 两轮针对性复核及方向继承 |
| app/evidence/artifacts.py | 原件与 reading_view_image 产物种类 |
| frontend/src/components/evidence-workspace/OriginalEvidenceViewer.tsx | 原件显示/缩放/旋转及框同层变换 |

原件查看器被 EvidencePage、EligibilityWorkbenchPage、ProfileEvidencePanel、FrozenReviewEvidence、ReviewActionResponseDialog 共享，修改必须考虑这些消费者。不要为了验证一个组件就声称所有入口已经验证。

### 8.4 前端实际核验到什么程度

Ego 中临时挂载了实际共享组件，读取只读隔离服务的真实两页。1920 截图、2560/3840 几何核验及缩放/旋转检查完成；临时挂载和 5178 已清理。证据为 `artifacts/reading-view-ui-20260916/REVIEW.md` 和截图。

这不是正式完整应用 E2E：当时没有可用于完整打开的正式报告；未验证真实已认证红框和完整病例审核。React 临时挂载初次版本不一致引发 hook 错误，后来改为复用实际模块版本；不应把临时调试错误误写为已知正式页面故障。

## 9. 双模型真实质量与耗时：证据和不能作出的结论

### 已完成的有限比较

`artifacts/mtplx-dual-basic-20260916/effort-comparison-v17/`：
同一横放原图、150DPI、完整 81 组件 ClausePack、产品 v17，每个模型 low/medium/xhigh。六次有五次结构接受，但原件核对有明确错值/遗漏；Flash Next xhigh 连接中断，无最终 usage，不能补造零用量，也不能直接认定 OOM。

`artifacts/mtplx-dual-basic-20260916/upright-comparison-v17/`：
只改变阅读方向，两路 xhigh 一次 stop，约 331.56 秒/419.38 秒；分别有 44/49 条事实和 1/3 条手写。内容改善但仍有 MONO#/EO# 错配、手写 NCS 错读/漏读、年龄遗漏、遮挡身份猜测等，**未通过临床验收**。人工确定转正的试验不能宣传为系统已自动判向。

两组提示为历史 v17，不是 v20 新质量证据。条数多不代表更准确。当前没有可批准的新默认思考档位，不能擅自降档“优化速度”。

### 对耗时的较可靠分析

- 每页约 3.7万–3.9万输入 token 的历史请求，条款包 110561 字符占主要输入；表达式约 42432、证据要求约 32363 字符。不是全部成本都来自图片。
- 当前处理器实算 1755×1240 图约 2145 视觉 token；双倍 DPI 可到约 8580。这是处理器计算，不是实测服务 usage。
- 横放资料、字段归属错误、重复全页格式修复和长思考都会增加成本。仅提高 effort 不能消除这些问题。
- v20 把完整共享条款/Schema 放在变化页面内容之前，核过 MTPLX 保留消息顺序；仅改页号时共享文字前缀约 114500/114815 字符。
- v20 **尚无实测速度改善结论**。可缓存前缀不等于一定命中，字符数不等于 token，也不能删跨章要求换“加速”。
- 原 stable-prefix 实验现已等同默认，不再作为独立比较组。
- 不把失败大额 token 当有效思考，也不把未知 TTFT/cache/usage 填零。

历史其他 Agent 的 Sept9 横评曾修复默认采样开关误删文本 AR 兼容参数，并增加测量器重复生成保护。这些修复有价值，但旧平台/档位结果不代替当前双本地视觉正式链路。当前带图 MTPLX 拒绝 AR，应使用实际支持的 MTP，不能机械照搬纯文本结论。

已调研方向分类轻量工具与 Qwen 图像处理建议，但未安装新方向分类器、未完成本机临床评估：
- https://www.paddleocr.ai/main/en/version3.x/module_usage/doc_img_orientation_classification.html
- https://github.com/PaddlePaddle/PaddleOCR
- https://github.com/QwenLM/Qwen3-VL

厂商方向分类准确率不是本系统真实病例准确率；Qwen3-VL 文档也不能直接当 Qwen3.8 当前权重配置。依赖引入前核许可证、Mac 运行方式、内存占用和 source-view 身份。

## 10. 最后一次独立审阅：采纳和未完成项

最后一轮 `enrollment-reading-recovery-prefix-20260916` 经批准 runner 执行，实际 CodeBuddy/codebuddy-cli/deepseek-v4.1-flash、请求 max、单轮 exit0，无 fallback。这是工程审阅模型，不是产品主读路线。

F1 完整传输版本比较已修；两页离线替身核验正常复用、改向页不复用、错误后缀拒绝。未触临床 DB，不能替代仓储实际闭环。

仍需处理：
1. **方向修改的用户入口**：现有 can_reread 偏失败页，不能把查看旋转当正式方向更正已完成。
2. **映射语义**：现在传方向映射为完整替换；省略继承，空映射清空。面向局部修改需明确 patch/reset，不能悄悄重置其他页。
3. **并发后继**：同一前驱可能出现两个后继；选择器后来拒绝歧义还不够，应在建任务时保证合法线性关系或明确冲突。
4. **仓储与覆盖**：需要真实隔离数据库验证派生图存储、复用、旧覆盖淘汰、来源/框定位。
5. **测试迁移**：旧断言依赖消息位置、版本号；按用户要求留待集中整测，但不能报告当前套件全绿。
6. **格式修复保真**：任何格式修复不能新增/删除/改写已有事实；同 normalization_key 也不足以证明相同时点/对象，勿机械简化。
7. **重复停滞**：历史测量器保护不等于正式默认调用全覆盖；正常长 prefill/思考与异常无新内容必须区分，不简单短超时。
8. **来源回执**：不得重写旧 raw receipt 的 job_id 来掩盖复用；可补 reused_from 元信息，原回执保持。

审阅存在限制：部分只读命令被工具拒绝，且审阅上下文含前次审阅记录，独立性不是完全盲审。实际报告与主场采纳记录保留；不据退出码声称临床或所有流程验收。

## 11. 为什么感觉一直停滞：复盘与责任

这不是单纯“模型慢”，也不是所有时间都花在有价值的临床理解上。

### 11.1 推进方式的问题

前期过度拆成小合同、小修复、小记录。局部确实不断完善，但未把“上传一例 → 看懂 → 采信 → 审核 → 可用报告”作为首要完成单位。最后一个步骤没闭合时，用户感知仍是原地打转。频繁短回合收尾和“继续推进”的文字进一步放大这种感觉；这是任务所有者应纠正的执行方式。

### 11.2 真实困难

- 扫描/手写/方向/字段归属问题会造成两模型都结构正确却临床错误，不能靠 JSON 合法率解决。
- 严格对账避免假事实，却会把不同措辞的真事实留在待核对；降低标准会冒更大风险，需分项及来源/时间验证。
- 通用跨章要求与长上下文成本矛盾，既不能只读 IN/EX，也不能每页机械重复无关全方案。
- 历史、修订、节点、原件、视图和派生结果身份很多，相邻消费者漏接会制造“可运行但不能用”的链路。
- 本地模型即使严格单 PID 也有释放滞后、长输入单模型内存高峰；名义串行不够。
- 后续需求合理地多次改路由，但配置、缓存、文档与版本未总同步，造成返工和状态误读。

### 11.3 下一位应避免

- 不新增另一份并行“大计划”来替代现有计划；修正文档冲突即可。
- 不通过再跑相同 effort 矩阵代替修方向/字段问题。
- 不直接换全新框架、不堆每页额外长模型调用、不按病种写修补映射。
- 不把验收的谨慎变成无限扩展边角条件；先完成最小真实垂直链，再集中反例验证。
- 不把没有验收写成没有实现，也不把实现写成已验收。
- 不用人工修好模型答案、删未知条款、补日期或虚造成功覆盖取得“闭环”。

## 12. 恢复后的详细执行计划

### 第一步：只读重锚

读取第2节文件、当前目标、最新全局机制；核 pwd、HEAD、dirty、任务、服务/端口/作业终态、显式 env 与实际权重清单。不要创建 app 指向原库进行“只读检查”：即便 run_runner=False，也可能有启动恢复写入。使用有身份记录的隔离副本。

确认两模型能被显式拥有和串行释放；不复用个人 MTPLX GUI 会话或未知其他任务服务。凭据不写入交接/日志。

### 第二步：把方向更正做成完整路径

明确用户查看旋转与模型阅读方向不同；设计局部更正/恢复原方向语义、保留未修改页、前驱后继唯一性。利用现有作业和覆盖，不新增队列。自动判向若引入轻量工具，应有来源保全和低置信处理，不要求用户预处理全部原件。

完成正式入口、真实仓储保存/恢复、原件坐标及旧覆盖取代的一次隔离闭环，再调模型。数学旋转检查不能代替实际 UI 红框验证。

### 第三步：少量正式当前双读

从合法入口新建当前版本任务；保持 source/ClausePack/Schema/effort/预算固定，用真正产品 harness 和足额输出。A 完成释放后 B；保留装卸内存、请求哈希、原始响应、usage、时间和失败原因。旧 c2e81ffe… 等冻结作业不要按 v20 原地恢复。

检查同源原件是否仍错值、漏手写、错对象。若仍失败，围绕证据形成小假设再修改；不要盲目扩大全受试者调用。

### 第四步：闭合采信和正式审核

在可靠来源上完成事实、病程、用药、Profile 和谓词绑定。缺研究者判断正常进入报告，不为等“全满足”卡死。用药分项扩测按既有授权推进；正式自动采信仍需留出结果和用户批准。

按筛选与基线分别形成 31001 的正式 ReviewRun、行动和冻结报告，验证后期资料不回写早期。跨章控制必须真的参与审核。

### 第五步：集中整体验证与交付

迁移旧版本/消息顺序测试，核当前工程回归；有效金标先核真值和输入同源；沿用事实并集召回≥0.95、金标负判定静默漏判0，另报采信召回/单源/假冲突/手写/错关联，不能只报并集。

使用另一个方案/新项目留出验证防过拟合；Ego Lite 在1080P/2K/4K核实际关键按钮、下钻、原件滚动/红框、补证与打印。最后核启动、恢复、备份、清理与交付，再分别更新 Phase 状态，最后讨论 claims_complete 和发布。AI 质量评估不替代最终医学授权。

### 何时再找用户

只有真实影响临床政策、正式自动采信批准、超出现有权限的新依赖/服务影响、模型变更或最终发布决定时提问。不要重复询问已允许的隔离用药扩测，不要求用户确认“没有研究者判断”本身。出现不能解决的阻塞要列已查证据和可选方案。

## 13. 工程执行、清理与验收纪律

- 读取最新全局 route/runner；工程独立会商与产品双模型严格分离。旧工程审阅用 DeepSeek 不代表产品可 fallback 到 DeepSeek。
- 工作包只给必要输入、路径、权限和验收。会商只读，不得访问工作区外临床原件；当前所有者负责整合。
- 用户要求长等待，不催慢但有进展的任务，不并发对同一会话 wait。工具的单次等待上限不等于整个任务超时。
- 记录在实质变化时合并更新。下一轮不要用很多“两行+2”文档修改充当工程推进。
- 按用户最新策略，不为每一小步增加阶段测试套件；编译、关键确定性反例和实际结果观察仍必要，集中最终测试不得省略。
- 清理前明确可再生且无引用的清单，保留失败证据、原件、库、会话和其他未提交工作。此次交接不进行清理。
- 不提交、不归档 unfinished Trellis 任务、不标目标 complete。
- 浏览器打不开/截图失败不偷偷换用户指定浏览器；先查现场，其他工作可继续，验收缺口如实保留。

## 14. 证据索引与历史入口

在第1节 worktree 下：
- `artifacts/mtplx-dual-basic-20260916/continuous-switch-memory-settle-v2/`：实际装卸内存采样。
- `artifacts/mtplx-dual-basic-20260916/effort-comparison-v17/`：六次旧提示同图档位比较、失败与错误。
- `artifacts/mtplx-dual-basic-20260916/upright-comparison-v17/`：转正单因素双读，未临床验收。
- `artifacts/reading-view-ui-20260916/REVIEW.md`：实际组件与只读真实图核验范围。
- `artifacts/review-20260912/`：接回审阅历史基线。
- `reviews/codex_conference_enrollment-reading-recovery-prefix-20260916_review.md`：最后采纳裁决。
- `runs/conference/enrollment-reading-view-integration-20260916/`、`runs/conference/enrollment-reading-view-review-20260916/`：相邻源码审阅，非临床 QC。
- `.trellis/tasks/09-05-phase55-dual-vlm-page-review/CHECKPOINT_20260908_MODEL_BENCHMARK_PAUSED.md`：横评长历史，其他线程运行说明不可当当前恢复动作。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md`：早期 SAR 作业恢复背景，取消作业不得机械重启。

真实输入路径、原件哈希、模型原始请求和隔离库身份应从各 artifact manifest/prepare_record/request receipt 读取，不从聊天摘要手打。本文不复制密钥或患者原文。无法从当前文档证实的旧细节应回到原回执，不补写推测。

## 15. 当前 goal 的完整原文

2026-09-17 get_goal 的 objective 原样为：

> Read the Codex goal objective file at /Users/smkzw/.codex/attachments/3ebdd8dc-dc79-4a23-8649-8eef0387e7ee/goal-objective.md before continuing.

实际状态为 paused。下面 fenced block 是该目标文件的逐字副本（保留原文转义、空行和历史措辞）。其中“当前工具无 pause 接口”等能力描述不代表 App 状态；以实际 get_goal 为准。本文没有修改原 goal。

```text
目标

在唯一工作树 `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`，复用现有R3架构，修复已证实的临床语义与证据/档案/界面缺陷，完成正式上传、方案解构、节点化资料双读、事实与病程整理、组件审核、研究者行动和同源报告整链；通过原件临床QC、当前独立双模型与有效金标、大屏真实交互及交付验证。系统辅助医学监查，不代替最终入组决定。

不要按旧goal恢复GLM low/Gemini、Qwen手写第三读、个人外部harness或旧失败作业。不要以文档、测试数、条款数、运行覆盖、打印文件代替实际目标完成。

## 先读与现场核对

1. 最新用户消息、全局及本树AGENTS、Trellis当前任务与相关层spec；按Ponytail最小完整改动。
2. 当前任务 `.trellis/tasks/09-11-e2e-eligibility-review/ENGINEERING_REVIEW_20260912_CODEX.md` 和 `HANDOFF_20260912_SUCCESSOR.md` 的最新接回段。下方旧交接是历史证据，不能覆盖当前发现。
3. `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`，尤其§3.3、§4.2、§5.4、§7、§11及修订。
4. `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`，尤其§6.1、§17；主Plan及 `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` 的T0–T7。
5. `docs/PROJECT_CONTEXT.md` 当前摘要与 `artifacts/review-20260912/`；有具体需要才读父任务/横评长历史。

每次恢复核对pwd、git HEAD/status、当前任务、进程与端口归属及未完成作业，不依据本文旧PID启动/停止服务。审阅基线4caf392，已有大量未跟踪/未提交工作，不能清除。原临床运行库只读；应用create\_app即使run\_runner=False也可能进行恢复写入，检查UI用有身份记录的隔离副本。

## 当前模型与通用性

- 产品当前仅用mtplx/Youssofal--Qwen3.8-27B-MTPLX-Optimized-Speed (xhigh)、mtplx/Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed (xhigh) 两个完整独立主读均读普通事实和手写，不设第三票。方案/整理首选mtplx/Youssofal--Qwen3.8-Flash-Next-MTPLX-Optimized-Speed (xhigh)。
- 这是当前部署，不是永久模型白名单。harness职责提示、临床判断、证据校验及采信标准必须跨模型/方案/疾病/药物/适应症通用。模型差异只在鉴权、能力、消息封装、effort映射、JSON、预算、流式及结束原因适配层处理。
- 不因某模型输出较差而降低标准、删除不认识的字段/条款、注入本病例答案或硬编码临床实体。不能把删掉模型名称校验称作泛化支持；能力必须真实验证。
- 产品自有harness直连API，只读显式ENROLLMENT\_ENV\_FILE/产品env；不调用个人Hermes/OMP/Pi/ZCode会话做产品识别，不运行时发现私人凭据。工程执行/会商与产品模型任务严格分离。
- 新语义任务至少65536起始输出额度，length最多一次131072，按厂商共享思考+正文及物理限制记录；不能静默继承8K/16K或强制xhigh降high。不能把给足额度解释成要求生成冗长答案。先能力/凭据/实际权重预检，再最小视觉/JSON调用；无支持则说明实际限制及替代方案，不静默换模型。
- 采样沿厂商默认。MTPLX纯文本严格JSON的AR兼容措施是传输适配；当前页读带图请求使用MTP，因为服务拒绝图片与AR组合。按请求模态和服务版本核验，保留既有修复与测试，不伪称所有解码设置默认，也不把该兼容措施推广为所有模型的临床提示规则。
- 云端2–3并发，当前本地主读1路；各本地平台和OCR由同一资源所有者协调串行、释放，勿抢占其他线程的服务。共享准入与租约复用，不再加一套队列。
- 每次冻结请求/实际模型、档位、预算、提示/Schema/算法/输入哈希和回执；旧响应按旧身份回放，不当作新组合质量证据。暂不扩大详细模型横评，先完成当前产品整链。

## 临床与产品不可退让的条件

- 本地单Mac单用户APP，直接打开；中文原生资深医学监查员只需上传、选节点、看问题、点原件、追踪补充。不要求理解模型、终端、log或内码，不要求真人代做测试。
- 当前方案导入docx-only，用户不预处理。原方案与现行修订优先；Q&A/函件/邮件只能澄清不能改方案。受试者PDF/扫描/图片保留原件，不覆盖OCR与人工IE。
- 方案以完整结构理解审核相关要求：官方入排、合并用药/洗脱/导入/基线/随机给药前条件、定义、例外、应做检查和有效期。模型负责语义解构，代码验证来源/覆盖/逻辑；不全方案逐页反复OCR，不把非临床管理章节拆成上百无关任务。
- 官方编号与组件身份分离；跨章控制须正式发布并进入要求全集，不止保存候选；其编号不得伪造成官方IN/EX。
- 筛选/基线分别提供和审核。方案明示时间锚点优先；未明示回溯锚点时按当前筛选/基线分别回溯。部分日期保留区间，不造精确日期；后期资料不改写先前结果。
- 页级模型只给原文观察/手写/规定证据关系，不给最终符合/排除判断。规范化先对账，精确Decimal不丢零；同对象/时点/来源/属性/极性才可能一致。单源、真冲突、尚未对应分别保留。
- 事实类型只用于候选筛选，不能证明任意临床谓词。各触发和例外分别有经验证的证据；同一事实可合法支持多谓词，不能用fact\_id相同简单判冲突。
- 确定性阈值/逻辑/日期由代码求值，semantic由受限语义层提供候选，investigator\_judgment须对应书面判断。统一实时/正式判定与缺口矩阵，阻断仅限实际相关组件，溯源提醒默认非阻断。
- 无阈值检验异常只承认对应报告批注或节点病历分析中的研究者判断；箭头、签名、常规医嘱、文件类别不能代替。未查完/候选未核实/完整供给范围未见/已核实判断四态分开。两路在有效完整范围均未见所需判断时，报告无法判定及应补内容，继续流程，不再要求用户确认缺失。
- 分歧最多两轮针对性回原件复核，不自动改写事实，不任意混合轮次凑双源。两轮仍冲突转具体人工核对；缺判断不进入这个重复确认循环。传输重试与业务轮次分别计数且有限。
- 用药分项已获准设计/隔离扩测，不再请用户重复批准实验。药物、剂量、用法、起止时间分别核实，不因某项一致就补齐其余；处方/购买不等于服用。同药多时段、部分日期、否认及未知归属保留。正式自动采信仍须留出评测达标并向用户确认。
- Profile读取当前authority的完整校正后集合，事实/事件/暴露/链接/资料期望共同闭合；不是最后一个run。不同节点/快照不按subject粗合并，保留历史重审版本。
- 原件引用绑定文档版本+页entry+定位+原文/哈希；不同文件同页码不得选第一张。右侧原件连续滚动，有真实核验坐标才红框，无坐标说明定位等级。子条款点击/刷新/过滤/打印均保持稳定身份。
- 正式审核冻结ReviewRun及FinalAssessment/ActionRequest，报告同源且用冻结审核时间。关闭行动不直接改判；补证后新审核。本次审核可带未决项完成，但不等于符合入组或claims\_complete。

## 执行顺序

2026-09-13最新用户调整优先：前端采用kangzhe-design-3d站点轨，保留现有React临床工作台，宽屏桌面及ego(lite)真实浏览器。不为小步骤新写阶段性测试或反复运行套件；完整测试集中在系统构建完成后，开发中仍做必要编译和关键正确性检查。T4验收未执行不阻止T5–T7依赖已具备部分的构建，不据此标记任何Phase验收通过。未获准的新语义对应保持隔离；不为了产出报告强行判定。每次真实双模型调用后依据实际输入、原文、遗漏/错误关联、用量、耗时及重试评估通用优化，必要时作针对性调研，不重复无证据的全例调用。

遵循恢复Plan的详细步骤，不重新发明并行规划：

1. T0先统一实际模型/effort/足额预算，能力预检和新任务身份，保持历史可读。
2. T1先写已证实反例，再修类型桶过宽、时间筛选、缺口/结论不一致、判断检索适用性。不要照搬旧handoff的“同fact\_id例外必冲突”补丁。
3. T2贯通组件及原件身份，真实浏览器一父多子/多文件同页码验证，消除内码和误定位。
4. T3跨章控制正式发布消费 + 当前累计Profile/链接/期望完整性；分项用药另作隔离扩测，不扩大采信。
5. T4从合法正式入口用新指定组合少量分层资料→31001筛选/基线整例，完成原件QC、有效金标和三档UI后分别收口Phase5/5.5。
6. T5实现正式审核/行动/冻结报告及真实摘要/批量；T6新项目留出验证和有据性能/视觉优化；T7打包启动/恢复/清理/交付。

允许提前修复已实现Phase6投影的严重问题，不因此跳过Phase5/5.5验收。保留现有FastAPI/React/SQLite/JobRunner/仓储/来源验证。新增代码独立小模块，只改共同根因的相邻消费者；不急于迁移Pi、LangGraph或另建队列。

## 证据与完成要求

- 每项：失败反例→最小完整修改→相邻回归→隔离当前库回放→受影响原件/真实UI验证。测试覆盖合法正例、错误反例及重命名/乱序/异时同值/多文件同页等泛化变形；不能只增加整齐同构样本。
- 有效金标先核来源与评分；保留校准/留出隔离。沿用并集事实召回≥0.95、金标负判定静默漏判0；另报采信召回、单源/未对应、假冲突、手写及错误关联。新增阈值有实测证据后报用户批准，不直接复用宽松旧分数。
- 时延分清来源读取/验证/模型/prefill/思考/正文/重试/缓存；未知用量不填0，并发测试期间数据不当单独性能基准。先优化测得的大头，不能牺牲上下文/质量。
- 工程回归、模型接入、原件临床QC、1080P/2K/4K真实交互、发布验收分别记录。实际点击每类关键场景，截图等待数据及图像加载，保留viewport和来源证据。
- 独立会商遵循最新批准route manifest/runner，派发前连通核验，记录真实model/effort/输出。不得把工程review或自评当正式医学签收。
- 任务记录在实质性变化时合并更新，连续完成长任务及后处理。只在真正目标完成、用户要求、确需决策或无法自行解决的阻塞结束；不以“继续推进”的收尾代替执行。
- 保留未提交工作、原件、历史已验收/失败证据和会话数据库；只按核实清单清可再生废弃缓存。用户明确无损暂停时保存当前步骤/回执/下一安全动作，不新派发。

现有goal未完成，不能为改prompt把它标complete。本文件可直接用于应用支持的目标替换入口；如果该入口不向当前工具开放，明确告诉用户已形成新prompt、运行时目标仍待应用更新，不谎称已改。





\##mandatory##

遵循全局Agents.md的方法学、执行/会商机制（120min超长轮询，期间主线程静默）、token saving机制。任务完成前不要自行创造断点、暂停点，不要反复停下。

产品服务原生中文资深临床试验医学监查人员。让用户通过上传、选择审核节点、查看明确障碍/待办、点击原件、追踪研究者回应完成工作，不要求其理解模型、终端、日志或后端术语。不安排真人监查员试用作为推进前提；本轮没有外部角色测试就如实说明，以可控测试、产品模型实跑、Codex 原件与浏览器检查留证，不伪称独立专业签收。```

## 16. 给接手者的最后提醒

先把已经搭好的链条真正接通并用原件证明，不要再从模型名单或大架构开始。用户要的是能放心看到“为什么这条能判断、为什么那条还不能”的实际工作工具，不是更长的技术过程。当前最接近主线的工作是方向更正、来源与后继任务的完整路径，然后用当前串行双模型完成一例双节点审核；不能用显示旋转和局部检查代替它。
