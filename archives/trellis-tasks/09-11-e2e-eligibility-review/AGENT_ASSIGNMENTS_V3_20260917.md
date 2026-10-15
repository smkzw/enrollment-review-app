# 干净会话接手分工与回交指引（V3，2026-09-17）

## 1. 给用户：怎么发给其他 Agent
建议按A→B→C接续。可以只交给一个Agent，让它连续完成三个包；也可以每个包交给不同Agent。**干净上下文不等于干净git worktree**：不要新建仅从HEAD拉出的树，那会丢失大量未提交成果。
只需将第8节对应启动指令给新Agent。无需粘贴全部聊天；它先读本文件和任务正文，再按需查V3。
本文件仅分配职责，未调用任何Agent、没有指定或更改全局执行路线。用户在新会话发出对应指令即为那个会话的接手范围；不是要求本session代启动。
当前Codex因用户额度安排停止于文档交接。可以做到哪里算哪里，但每个Agent交回时必须说明生产/保存/消费/入口分别做到哪，不能留下“已完成”但无人能接的状态。

## 2. 统一身份和最短启动阅读
唯一工作树：
`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`
任务目录：
`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review`

1. cd上述工作树，pwd、git branch --show-current、git rev-parse HEAD、git status --short；不要从主checkout启动。
2. 读最新全局 /Users/smkzw/.codex/AGENTS.md、此树AGENTS.md、.trellis/workflow.md，并按相关层spec行事。实际Codex inline，不从Trellis步骤直接派发原生子Agent；独立会商按批准guard/runner。
3. 读本文件、prd.md、design.md、implement.md、GOAL_PROMPT_V3_20260917.md。
4. V3只先读0、1和自己工作包章节：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/research/ENROLLMENT_REVIEW_AGENT_RECOVERY_V3_20260917.md`。源文件来自Downloads，冻结副本不代替后续用户新指令。
5. 查看自己包的最新RETURN记录及implement唯一状态，再读受影响完整函数。不要每轮再读三个月历史。
6. 现场task.py --help和current --source后按真实会话激活已有任务；不可伪造session上下文。任务完成前不archive。task finish只是清指针，不代表完成。

起点HEAD已核4caf392c376ce7a9392fa2e8facc7d8a7f4e4a34，branch codex/phase5-clinical-facts-profile；大量dirty是交接基础，不是废弃文件。此数值只供对照，不要求退回。
旧HANDOFF_20260917_CODEX.md是历史状态地图，其中全量双VLM、65K统一下限、旧验收优先级已被V3替代，不能照旧恢复。
比较附件SAR_PROTOCOL_THREE_MINUTE_COMPARATIVE_REVIEW_20260917.md在指定Downloads位置未找到。本轮未杜撰/重建附件；可定位其他实际副本，找不到就用正式原文核对，不能让缺比较说明阻止普通工程工作。真实原方案缺失或修订不明才是可能的实质阻塞。
implement.jsonl/check.jsonl占位不是inline阻塞，不强行填源码全集。

## 3. 当前新方向与保留边界
目标是内置方案Agent真实生产/核对/共同发布→一例完整当前节点→可回原件报告→一次更正/补证。已有合格规则可支持B调试，不代替最后A的真实DOCX链。
取消每个事实全量双模型一致要求；新主线原图准备→主OCR/可靠原生文字→有理由的局部视觉/人工→真实来源事实发布。不关闭检查来假装新方法已批准。
前置Agent相对独立是任务输入/产物/配置独立，不是新服务或新队列。保留框架、事实体系、临床逻辑、来源和历史。
角色预算按实际任务配置，非思考需真实参数支持，low不等于关闭。当前可用本地服务/权重需现场核验，不能悄悄用远端或个人harness代跑。
本地模型/OCR均由单一资源所有者安排；已有装卸等待保护必须复用。不能两个开发会话各自以为串行而同时加载。
用户界面中文临床原生、宽屏、Ego Lite；不要要求用户JSON、终端或手工逐页预处理。实现保留研究者判断的真实责任，不替研究者写医学判断。
30分钟为软优化目标，不能通过截断、漏页、删规则达到。代码/哈希/模型同意不证明医学正确。

## 4. 共享文件、资源和交接控制
默认同一时间只有一个**实施所有者**拥有本工作树写权限。A/B/C是接续职责，不是三个同时写共享源码的worker。
如果用户确实安排同时工作：A与B只可在双方明确文件清单后做不重叠源码工作，以下文件由当前实施所有者统一修改：app/api/v2/app.py、app/config.py、共同contracts/gates/来源枚举、数据库迁移、公共前端API、prd/design/implement/task.json、Goal。未确定所有者就按默认接续，不用文件锁临时发明协作平台。
另一Agent可先只读勘查自己的包，提交带基线hash的建议；未经所有者交接不得直接改共享文件。
模型服务、隔离临床库、端口和数据目录始终单所有者。交班须给端点/实际权重/加载状态/活跃job/归属；不是只给旧PID。
不在新worktree从HEAD重做。若必须隔离工作树，应由当前所有者导出确认的完整dirty基线和文件hash，不能只git cherry-pick老提交；本计划默认不需要这样做。
不git add -A、不reset、不清失败证据、不覆盖原方案/受试者源材料。提交按实际Trellis规则和用户批准，仅本会话明确变更路径；没有commit可用before/after hash与差异回交。

## 5. Agent A：方案生产、同源预览、核对与共同发布
对应P0/P0.P1–P0.P3。A先接手，临时承担唯一实施所有者；不要自行创建“项目经理Agent”。

### 输入与先读
V3第2.5、2.8–2.14、2.20–2.25、P0.P；task design。
源码从以下入口向真实调用者追，不依据固定行号补丁：
- app/api/v2/protocols.py、protocol_control.py。
- app/services/protocol_workbench_service.py（ProtocolWorkbenchService、publish_first_project/publish_re_deconstruction）。
- app/services/protocol_deconstruction_executor.py（_handle_extract/_handle_generate、_ProtocolSemanticBatchFileCache）。
- app/services/protocol_control_executor.py只是重导出；继续读app/services/protocol_control_execution.py及protocol_control_job_service.py。
- app/agents/protocol_deconstructor.py、protocol_semantic_transport.py、protocol_control_deconstructor.py及其实际wire/repair imports。
- app/protocols/parent_rule_semantic_segmentation.py、adaptive_batch_budget.py。
- app/services/protocol_draft_service.py、protocol_publication_service.py、protocol_control_catalog_publication.py。
- frontend/src/pages/ProtocolsPage.tsx、components/protocols/ProtocolDraftWorkbench.tsx、ProtocolComparisonWorkbench.tsx及实际API客户端。

### 实施范围
1. 补design中的一页短链：真实源结构→分包→作者Schema→水合→存储→预览→检查→局部修订→共同发布。标已存在与确实断点，不全仓再审。
2. 核实际Schema可选/领域必填、source_ref与source_span_id映射和首次/紧凑/修复路径；宿主缺陷直接修宿主。保留不同来源族，不能模糊匹配猜ID。
3. 一个完整语义来源单元产生合法候选后立刻保存并在原工作台预览，后续继续同一草稿。不给模型重复生成通过/不通过/摘要三种文字。未完整候选不允许发布。
4. 全范围官方与跨章核对，原父子内容/研究部分/时点锚/例外/未知/依赖可回源；仅修实际受影响小对象，保留兄弟。最多两轮无进展停止，不将不支持隐藏成恒真。
5. 核共同发布：当前publish中control_job_id非空才prepare/save控制目录，须确认实际工作台请求和强制依赖，不凭此条件猜全部已实现。全当前要求同一发布与下游修订身份。
6. 从正式DOCX入口真实跑通，记录首次可读/完整草稿/核对/可发布/发布和人工等待；不能只给prompt或测试脚本。

### 权属与限制
A拥有方案相关源文件和方案前端；共同文件由当前所有者处理。不要改资料采信合同假凑整链；将下游接口变化写入RETURN_A。
比较附件中的SAR16条、药名/阈值不可写通用常量。缺比较文件不等于缺正式方案。不会自动核对的真正语义歧义集中说明，不让用户重复整理整方案。
工程角色模型按实时批准机制，产品模型按显式产品配置；不混用。

### 退出与回交
交回一个真实内置发布的source/version、official+control+stage requirements、RuleSet/Revision及证据位置，能重新打开草稿和发布结果，下游能读取同一身份；一个局部修订证明未改变无关对象。
未完成也回交RETURN_A.md：具体阻塞对象、合法已保存批次、下一函数/入口、活跃作业状态。A发布完成不等于整个任务完成；交B不archive。

## 6. Agent B：真实读取来源→事实发布→整例资料
对应P1/P2。A交接后接手共享写权；若A未完成且已有经核验规则可用于调试，允许用户明确调度B先行，但P3不能用旧规则替代A。

### 输入与先读
V3第3–7、P1/P2；A的RETURN及design短链。
- app/api/v2/evidence.py → app/services/evidence_upload_service.py → evidence_processing_executor.py。
- app/evidence/ocr_adapter.py、pdf_native.py、page_processor.py、reading_view.py；app/services/omlx_gate.py。
- app/llm/page_review_harness.py、page_review_transport_options.py（复用适配，不复用整页全ClausePack业务提示）。
- app/services/page_review_runtime.py、fact_normalization_command_service.py、fact_normalization_source_adapter.py、fact_normalization_executor.py。
- app/agents/evidence_normalizer.py、verified_evidence_prompt.py及修复分支。
- app/domain/page_review_evidence_sources.py、contracts/evidence_normalizer.py、相关gates/locator；app/services/fact_publication_service.py。
- 现有资料/Profile/原件/更正API与前端，以真实消费者为准。

### 实施范围
1. 原图preparation保留，后接新明确读取策略，沿JobRunner/ArtifactStore/checkpoint。先检查等价manifest对象，新增最少必要字段，不建立第二事实库。
2. OCR原始文字/实际模型/输入图身份存档；pdf_native有字词坐标但可复制不代表可靠原生；OCR当前text-only且verified_coordinates=false，不能画假精确框。
3. 一份报告的源、对象/行列、原始值/单位/时间、核实方式、可用字段、未决完整进入现有来源分派；不是require_page_review=False了事。
4. 同步normalizer正文/修复、候选验证、locator、发布、恢复和历史消费者。OCR不能写两份reading，人工不伪装模型，不能补旧方法批准。
5. 决定性扫描字段和手写按报告/行组局部视觉核对，保留表头上下文；首次不提示OCR候选值/入组目标。不清楚转人工。默认一次主读取+一次有据核对，只有新方向/图像/来源才再读受影响区域。
6. 从正式入口让一份真实报告发布事实并可打开原件/核对或更正；然后扩到一例全部当前资料：多报告/双栏/跨页否定/药名/参考范围/评分与批注归属。
7. 累计事实/事件/暴露/Profile完整，不能最后一轮覆盖全集。已核实值与未知属性分别保留。

### 不做
不固定双读，不所有谓词再读几遍，不建立全医院模板/置信度平台。姓名遮盖不猜、不无限重读；不读心电波形算QTc/影像重评分。软件检查不能代替关键字段原件核对。
OCR与Qwen安排为同一本地所有者串行释放，现有共享服务若不支持某协调不要擅自修改影响别人，应在当前范围减少加载/记录实际限制。

### 退出与回交
一例当前资料全部页有处置，可用事实正式持久/可回源、关键字段核实依据明确、局部未决不隐藏。记录source policy版本、manifest/authority、实际调用/费用未知项、UI入口和所有未消费的新字段。
RETURN_B.md 必须给C可直接使用的数据身份与查询入口；不只提供合成fixture。未完时写最小下一步，不手工插入结果交差。

## 7. Agent C：当前节点判断、报告、更正与集中验证
对应P3/P4/P5。依赖A真实DOCX发布与B真实来源事实。默认接续唯一写权，不另建报告truth。

### 输入与先读
V3第6.7–6.8、第8、P3–P5、第11；RETURN_A/B和当前implement。
实际入口包括app/services/predicate_binding_input.py、predicate_binding_job.py、qualified_review_command.py、prepared_review_publication.py、frozen_review_publication.py、app/api/v2/qualified_review.py，以及既有Expression/FinalAssessment/ReviewRun/ActionRequest和前端消费者。

### 实施范围
1. 逐一追到当前实际需要的语义任务，输入是什么、解决什么不确定性；不预先重写全部执行器。
2. 新来源进入显式对象/属性/时点/出处谓词绑定。数值/单位/日期/布尔已有可计算的直接算，同原文相同问题合并有界语义核查。类型只找候选。
3. 取消新方法被旧双读覆盖/旧批准锁死的接点，但保留真实来源验证；旧数据按旧版本读，不造通过记录。
4. A发布的官方/跨章/例外/当前资料义务同一冻结范围；B新来源事实真实消费，足证支持规则给有效正/负结果，不全部UNKNOWN。
5. 缺研究者判断、没查完、未核候选、来源冲突、系统不支持各自说清；没有判断不反复找用户确认，自动报告应补什么。
6. 当前节点真实操作→冻结报告→重新打开；页面和导出同源，不再生成报告模型。
7. 一次真实更正或补证→新修订/受影响重算→新报告；旧报告与累计用药/事件不丢。没真实更正依据就隔离非临床样例核动作，不改原件制造错误。
8. 集中A1–A12核查，Ego Lite实际宽屏操作，另一资料及另一不同结构正式方案经内置入口验证。已见31010不是盲测，未做跨方案就明确未验证。
9. 汇总有效产出、实际错误采用/未决/人工负担、分阶段时间；30分钟软目标不篡改。当前节点可用先交付，整体剩余范围保留。

### 退出与回交
RETURN_C.md给应用启动方式（核实际脚本，不猜命令）、端口/库归属、报告/新旧审核/更正身份、验证记录、未决医学项与工程缺陷分开。用户普通操作不得靠开发者手写JSON。
如果A/B依赖没交齐，不以生成空报告宣布完成；可修已确认共因，必要时回交依赖状态。当前节点完成不自动claims_complete全产品或archive。

## 8. 可直接发送的三条启动指令

### 给 Agent A
你接手入排审核系统V3分工A：方案生产、同源草稿预览、核对与共同发布。唯一工作树为 /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile。
先读 /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md 的1–5、9节及当前prd/design/implement；按V3五分钟入口与方案相关章节工作，不重读全部历史。你暂为唯一实施所有者，沿已有任务，保留所有dirty与原件。完成P0/P0.P完整链，不恢复全量双VLM，不新增总结模型/队列/通用Agent框架。先核实际调用再最小改动，尽快正式DOCX试跑。阶段记录合并更新implement.md；回交写RETURN_A.md，按第9节逐项填写。可持续做到用户要求停止或任务真实完成，不因小步骤自动暂停；额度将尽时先保存可恢复状态和未完项，不冒称完成。不要自行启动B/C。

### 给 Agent B
你接手入排审核系统V3分工B：原图后主OCR、局部VLM/人工核实，真实来源进入现有事实发布并覆盖整例当前资料。唯一工作树为 /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile。
先读 /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md 的1–4、6、9节、prd/design/implement和RETURN_A.md（若不存在则核依赖状态，不编造）。确认前一所有者已交写权；未交接只读。沿V3资料章节实施P1/P2，不假造A/B、旧批准或仅关闭require_page_review，不复制事实库。已有合格规则可调试但不能代替最终内置方案发布。模型/OCR串行，由你明确管理拥有的服务，不抢占其他任务。先一份真实资料生产/保存/消费/入口，再整例。更新implement，回交RETURN_B.md，任何未完状态按第9节保存。不要自行启动A/C。

### 给 Agent C
你接手入排审核系统V3分工C：新来源谓词绑定、当前节点正式报告、更正补证和集中验收。唯一工作树为 /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile。
先读 /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile/.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md 的1–4、7、9节、prd/design/implement及RETURN_A/B。确认写权和实际依赖，不能以旧规则替代A真实发布、不能用伪数据填B缺口。沿现有求值/ReviewRun/Action/冻结报告完成P3–P5，缺判断正常报告，不全UNKNOWN凑成功、不新调报告模型。Ego Lite实操，原件核实与工程检查分开；未做的验证明确保留。更新implement，回交RETURN_C.md，供原Codex回来从实际进度接手，不归档全项目。

## 9. 每个Agent的回交格式（必须可部分完成）
写同目录RETURN_A.md / RETURN_B.md / RETURN_C.md，只维护自己的一份。下面是字段，不是必须新增数据库或管理工具：

- 角色、时间、接手来源、工作树、branch、开始/结束HEAD；是否有其他写者。
- 接手时已有dirty清单/选定文件hash的证据位置；本次实际修改文件清单与原因、before/after或patch位置。不要把全树dirty当自己成果。
- 本包及P子项状态：未开始/实施中/已实现未实跑/已实跑未验收/已验收；逐项列出处。
- 生产→保存→消费→正式可操作入口，各填实际函数/对象/URL与证据，不填“应该”当事实。
- 原方案/修订/规则/节点/受试者资料/manifest/run/report身份；真实输入与产物hash，路径绝对，敏感内容不抄进聊天。
- 实际模型provider/权重/effort或非思考参数/预算/端点/采样/回执；未调用写未调用。工程review与产品调用分别写。
- 运行中任务：job/session/端口/PID仅作线索，归属和安全等待/取消/恢复方式；服务已停还是保留，下一位如何确认。若有未完模型，停止前不能强杀造成不可恢复。
- 验证命令、退出码、实际原件/浏览器范围、未验证项；有失败保留原始stderr/响应，不只总结成功。
- 未决分为临床待澄清、技术阻塞、普通剩余；已尝试假设和下一次不同动作。不要以泛泛“继续推进”结尾。
- 新接口/配置/迁移、所有直接消费者是否已接；若未接，列精确路径与后果。
- 改动对其他包的影响，以及是否修改PRD/design/Goal；不得悄悄扩大范围。
- 下一安全动作：给出一个完整可执行步骤和预期观察；不要要求接手者再全面研究。
- 回滚/恢复：只撤本次改动的方案，保留原件/历史/别人dirty；没有安全自动回滚就说明，不能建议git reset。
- 当前交付六项同步implement.md；任务没有完成不archive，不以交班标complete。

建议把本次证据放现有artifacts下一个有明确包/日期的目录，复用已有结构；不要为每个函数单独建任务。每次实质里程碑更新，不逐分钟写记录。
当用户要求回交或额度接近耗尽，优先冻结可恢复状态和上述记录。新Agent仍可从未完成切片继续；无需为了交差强行达到临床结论。

## 10. 原Codex回来时的读取顺序
只读implement当前六项→RETURN_A/B/C（存在的）→变更文件和真实证据→V3涉及章节。先核未完进程/库/版本，不按本文旧句柄控制服务。
检查新来源真的可发布/可回看、内置方案真的共同发布、报告真的消费同一版本；没有证据的“完成”降回未核实，不抹掉已有工作。
Goal正文可同步，但工具若只能complete/blocked则不能借标complete改目标。当前目标通过附件文件指针读取；本次同步正文保持paused，不自动恢复其他Agent的运行时目标。新会话按自己的工具能力如实记录。
