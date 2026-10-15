# 入排审核系统 Phase 5 → 下一棒 Agent 完整交接文档

### 新目标连续实施（2026-09-12，优先于下方审阅交付状态）

2026-09-13累计档案后续：已去除Profile/资料期望run过滤，共享active_facts选择器，先选链头再排除校正目标，防旧值复活；索引/校正/缺口消费者统一事实选择。新增补读反例修前丢3项；更正头反例修前2fail。核心相邻145pass，最后两个校正消费者改动后另80pass，diff通过。只读真实隔离库仍拒绝完整引用闭包：516事实/46事件/22暴露/9冲突/130期望，24项事件旧事实引用对应同语义新头但旧定位未全部保留，不能自动换号。新证据及未决设计见artifacts/review-20260912/T3_CUMULATIVE_PROFILE_20260913.md，工程设计§17.5与Plan T3同步。原库未写、模型未调用、所有本轮进程终态；R06/T0–T7未完成，不是暂停。下方Profile仍按run过滤为旧进度。

2026-09-13累计档案相邻修复：FactRuleLink.rebuild_for_authority不再按触发run缩小active集合并把其他批次事实索引列为stale删除。新反例首次是fixture缺gate_id，改用既有发布助手后真实复现旧事实被列stale；修复后索引/Profile37pass、规范化终结/校正52pass，diff检查通过。只改确定性的范围选择，不新增医学语义链接。Profile/资料期望仍按run过滤，R06未闭合；发现既有active_entity_ids_after_corrections会过滤悬挂引用，不能不加分析地拿来“完整合并”。Plan T3已细化。再次核实全局guard仍初始化失败，未改共享文件或绕过派发。

2026-09-13后续读取优化：page_image接入独立Session内最多4096个ORM记录的短期复用，全部来源校验不变，异常也释放；63项相邻测试通过。只读隔离库单页查询15946→3985，四次原图hash一致；全24页6线程成功22.5962秒，单页Python跟踪峰值约20.46MB（非RSS/并发峰值）。详细证据见下引T2记录新增段；不宣称浏览器最终性能或临床验收。本次是确定性修复直接执行，既有会商故障未绕过。此段替代下段“尚未并入产品”的旧进度，仅有界版本接入。

2026-09-13 T2真实浏览器复核与纠偏已合并记录于 `artifacts/review-20260912/T2_SOURCE_NAVIGATION_20260913.md`：切页回调接通、逐字摘录替代fact内码；真实浏览器发现并修复原件容器无高度约束、明确返回被滚动保护吞掉两项问题。最终三档实际原图进入可视区，前端573pass、后端13pass，构建通过；无坐标仍不画框，真实缩放及完整T2未验收。读取耗时另已剖析到每张图重复全修订核验，单请求约15946次execute；单Session保留ORM对象隔离试验降至3901次但尚未并入产品。模型未调用、原库未动、claims_complete=false。当前会商guard错误仍在，未绕过，R01/R07及T0–T7剩余范围保持不变；上一轮只重述泛化要求为无进展，本轮为上述实际代码/反例/浏览器证据进展。

2026-09-13共用原件查看器实证修复：新增异步定位到达/同值重渲染不回拉、跨文档同页定位不得画框两项反例，修前真实2fail/6pass。查看器现以文档版本+页artifact+页码过滤已认证bbox，并以revision/entry/locator/bbox/frame组成稳定高亮身份驱动滚动；异步到达可滚动，不因重新分配等值数组回拉，保留用户主动滚动抑制。修后聚焦13pass，全量前端78文件571pass、8.22秒，构建通过；所有测试会话终态。此为组件行为验证，不是原件坐标临床验收或大屏浏览器验收。产品原库/模型服务未动。

2026-09-13审核页定位接线：OriginalEvidenceViewer已有authenticated bbox能力，但审核页固定传null/[]，导致没有实际重点标注。现通过既有getOcrPage(ocrPageId,processingRevisionId)读取所选页定位，只传当前revision且locatorId/文档版本/页artifact/页码都一致的定位。已核实bbox才由既有查看器画框；无核实坐标或读取失败给中文说明/重试而不补坐标。聚焦工作台+查看器11pass，构建通过；随后补了响应processingRevisionId匹配检查。真实浏览器红框/异步定位滚动尚未验收，onSelectPage仍无操作，需继续完整导航验证，不以接线称R04完成。原件和原库未动。

2026-09-13审核原件身份贯通：_fact_refs原先丢弃定位内source_document_version_id/page_artifact_id，只发页码；现由已验证locator传出完整身份，API/前端类型解码同步。原件面板按文档版本+页面身份+页码共同匹配，找不到不再把null交给查看器显示默认其他页。服务测试增加与原locator身份一致断言；前端聚焦10pass、构建通过。多文件同页码真实浏览器反例、红框定位和完整导航尚未验收；不宣称已完成R04。没有模型调用、原库写入或原件改动。

2026-09-13来源树核对与前端全回归：RuleSet合同只定义Rule→RuleComponent，不定义组件之间递归父链。工作台去掉按官方编号查另一个组件的递归深度推导，按parent_rule_code是否有值显示一层归属；选择参数改名selectedComponentId，避免继续误用官方编号。此处不宣称新增了完整父规则分组展示；同号要点单层展示、独立点击测试5pass。全量前端78文件569pass，8.61秒，session37823终态；tsc/Vite通过，既有大包告警保留。仍需实际浏览器/原件验证，不以单元测试数量收口T2。未启动临床数据库或模型。

2026-09-13报告相邻身份检查：ReportsPage的问题清单与表格行key均改为ruleComponentId。前后端响应分别校验组件身份唯一，允许同官方编号的不同组件，拒绝同组件重复而不去重掩盖错误。前端三文件13pass，构建通过；API补同编号合法/同身份非法反例。仍未以自动测试替代浏览器与正式报告验收，父子层级映射待处理。未动原临床库、未改变医学判定或模型路线。

2026-09-13组件身份贯通：在R01绑定链规格待独立审阅期间，修复R03确定性选择缺陷。EligibilityClauseProjection/DTO/wire/view新增必填rule_component_id；工作台选中、React key和component链接使用组件身份，官方编号仅展示。失效链接不再回退第一项。新增同官方编号双组件独立点击及失效链接反例，前端三文件12pass、构建通过；后端服务10pass，API首次1fail为前轮R07文案旧断言，已同步为尚未完成/不得未见并增加组件身份断言。原件浏览器验收、父子层级仍按parent_rule_code的歧义、Reports行key/链接相邻消费者尚未全部核验，不能称R03收口。临床库未改，未调用模型；独立会商共享配置故障仍待处理。

2026-09-13来源身份前端贯通：上一轮仅重述泛化约束，未形成新实现，本轮修复相邻消费方。judgmentSearchHttp严格解码原先仅允许page_number/reasons，会拒绝后端新增来源字段；现同步类型和解码，强制保留文档版本与页面身份。新增跨文件同页码及缺身份拒绝反例，HTTP与卡片测试11pass，tsc/Vite构建通过（仍有既有大包告警）。没有放宽为任意字段或猜测来源，没有修改原临床库；真实原件点击和完整R04验收仍待完成。

2026-09-13判断检索来源身份：上轮消除错误缺失表述为实质进展。本轮确认JudgmentSearchCoverageSummary只有候选/完整未见/未完成三态，无已核实采信状态，不能把候选当第四态已实现。追踪相邻原件展示发现judgment_search_status._incomplete_pages仅按page_number聚合，跨文件同页码被合并；现改为source_document_version_id+page_artifact_id+page_number，返回保留两个来源身份，同页两读道原因仍聚合。新增两个文件同为第1页反例，与判断结果测试合计20pass。此为后端来源身份修复，前端导航/四态采信/临床QC仍未验收，不替代R03/R04整体闭合；未改原库或调用模型。

2026-09-13 R07先消除未经证实的缺失表述：上轮混合缺口测试为实质进展，本轮未收到共享路由修复授权，未改全局配置。发现_reason在缺少任何完整判断摘要时仍称“未见研究者书面判断”，与§17.2四态相违。已改为尚未完成核对、先核对原件、不能据此认定缺少判断，并删除面向用户的“判断检索摘要”术语；两处反例断言无“未见”。首次1fail/9pass为另一旧文案断言多一个“中”，修正后重跑。此处仅文案事实边界修正，尚未改变_summary_gaps(None)及evaluator专业判断缺口合并，因此R07未完成，不能声称四态已落地。后续必须按对应要求的实际检索覆盖/候选核实状态统一状态与动作，保留完整范围确实无判断时的报告缺口；不以文案修复代替这项实现。原库未写，无模型调用。

2026-09-13继续核验：上轮扩大回归及派发错误诊断为实质进展。本轮只读workflow_routes.json定位4个string候选混在list[dict]中：E03 peak[1]、E06 peak[1]、E08 off_peak[1]、C01 peak[1]，导致guard初始化即失败；C03自身结构正常，但不能绕过全局guard造packet。已异步询问用户是否授权仅格式化这4项、完全保留模型/档位/顺序，尚未改全局清单/工具、未派出模型。产品侧继续补必做未完成叠加冲突/未核实/专业判断三类反例与未来未到期反例，领域+服务35pass，diff检查通过，session75427终态。没有原库写入或临床验收；独立会商等待共享配置处理，不把局部阻塞当整体goal阻塞。

2026-09-13 R02扩大回归与会商接入：上一轮完整期望正反例为实质进展；本轮test_contract_logic.py、tests/v2/domain、test_component_decision_blocking_gaps.py共687pass/5第三方弃用警告，6.30秒，session36386终态；HEAD仍4caf392。准备冻结修改独立审阅时，`python3 /Users/smkzw/.codex/tools/hermes_workflow_guard.py --help`即在初始化失败：293行_declared_label(_node["peak"])→285行n['agent']抛TypeError:string indices must be integers, not 'str'。已读266–300行确认工具假定路由节点链为list[dict]；目前未验证实际清单结构，不能猜测模型或用旧packet绕过。conference_session_runner --help成功不等于合法派发；本轮无独立模型启动、无审阅结果、未改全局治理工具。独立审阅接入待恢复；这不阻断所有产品代码工作，不将整个goal标blocked或complete。下一步继续补不适用/混合缺口反例及真实UI核对，并核实批准清单与guard兼容入口后再派审阅；原件临床QC仍未完成。

2026-09-13 R02正反例闭合进展：上轮接口状态修复为实质进展。本轮补齐年龄正例的版本化流程节点、正式模板投影/仓储及EvidenceExpectationProjectionService覆盖核实；初次沿旧fixture未命名空间workflow写模板被仓储拒绝，改为与正式发布一致的rule_set:revision:stage身份并在临时测试节点绑定后，两条原断言不变通过。新增只有发布年龄事实但无资料覆盖时indeterminate+record_incomplete的反例；服务与领域两文件31pass。API三项使用命令级合成DECONSTRUCT_GLM_API_KEY、既有测试fixture禁止端点网络预检后3pass，证明此前错误是测试启动配置；没有读取真实密钥或调用模型、没有关闭产品预检。diff检查通过。所有测试已终态；原库不变，R02仍需混合缺口/不适用分支、正式assessment相邻回归、独立会商及真实UI，不能以本组通过宣布临床验收。

2026-09-13 R02反例追踪纠正：上一段关于年龄缺口来自_summary_gaps的推测不成立。隔离pytest内逐函数观察证明component-in-01的summary_gaps为空、derive_gate_gap_types为RECORD_INCOMPLETE、对应期望列表为空；原fixture年龄要求仅screening_record/identity_record，不要求专业判断。真正把资料不全显示成专业判断的是_decision_for_wire将INDETERMINATE改成PROFESSIONAL_JUDGMENT。现保留原判定身份，并同步API Literal、前端类型/解码、工作台未决筛选与图标、报告未决统计；新增wire恒等与HTTP解码反例。针对性后端21pass、前端三文件10pass、生产构建通过（仍有大chunk警告）。无真实浏览器验收或独立会商，不宣布R02收口。年龄两个旧正例只有已发布事实、没有当前期望覆盖；尝试调用期望投影发现没有对应模板，空操作已撤回，不能以修改预期代替补齐正式fixture链。下一步需为已完成覆盖和未完成覆盖分别建立正式仓储正反例；API测试仍需独立注入测试预检依赖。当前所有测试终态，无产品模型调用/原库写入，claims_complete=false。

2026-09-13 R02在制修复：上轮泛化合同为实质进展。本轮主线程直接建立三类规则×真假触发×三类相关缺口的18项反例，修前18fail/2pass；derive_component_decision现在让相关阻断缺口优先于确定触发，保留只有溯源提醒的明确结论，以及明确FALSE且只有必做未完成/字段缺失/记录不全缺口的必做未完成结论，20pass。这不是临床验收：扩大服务/API回归2fail/27pass/3error；两失败是年龄已知的IN-01被附加professional_judgment，定位到_summary_gaps仍按investigator_assessment来源类型/模板类型推导专业判断需求，须继续核实fixture与权威要求而非直接改断言或删除缺口。三API错误独立重跑确认是启动语义路由凭据预检，不是请求断言失败；应隔离测试依赖，不能关闭产品预检。applicable=FALSE及混合未来缺口等分支也未收口。新增测试tests/v2/test_component_decision_blocking_gaps.py；当前修改尚未独立会商，原库未写、模型未调用，claims_complete=false。测试session20136/91924均已终态，不重跑旧句柄。下一动作：从tests/v2/helpers/phase5_fact_chain.py→test_fact_normalization_persistence的权威fixture追溯IN-01判断要求，与R07需求选择统一后扩回归；不得宣布R02完成。

2026-09-13泛化要求补充：直接核对当前goal及设计§6.1、恢复Plan T6，模型/业务分离已在合同内；本次补齐病例、方案、模型三个独立验证层级，禁止把同方案换病例、合成重命名或换II/III标签当作跨方案验证。留出资料用于调优后须重新分类并另留独立验证资料；每项优化说明归属和反例，新增模型不能降低临床证据标准。本次为主线程直接进行的用户要求明确化，不是独立审阅或泛化实测通过，不改变当前模型组合、临床数据或goal完成状态。

2026-09-13兼容性复核：上一轮为有效期投影/存储的实质进展。本轮补充旧模板完整payload往返断言，复现1fail/5pass：虽然内层projection_sha256未变，新增空字段仍改变外层payload。已依照ReviewEpisode既有wrap serializer方式省略空source_validity_window，保留非空字段；模板与存储27pass，diff检查通过。继续追踪确认protocol_deconstructor原有提示已明确“检查结果资料时效不是事件回溯、按原文due_stage建要求、不得写入谓词time_constraint”。因此下一步应让资料期望消费已有资料时效并保留其原文节点，不能把该字段重新解释成所有time_constraint的用途标记。尚缺显式锚点/部分日期范围处理及对原始旧模板缺字段的受控升级策略，T1和六项strict-xfail仍未完成；没有模型调用或原库写入。

2026-09-13 T1资料有效期传递：定位到EvidenceRequirement已有source_validity_window，但EvidenceExpectationTemplate、模板投影及落库语义校验均遗漏。新增四种日历单位反例，修改前4fail/1pass；现模板保留原有TimeQuantity，非空有效期进入v2投影哈希，空有效期保留精确v1哈希及稳定模板身份；落库对比权威要求，拒绝即使自洽重算哈希但删去有效期的模板。不覆盖旧模板、不迁移原库。新增存储往返/篡改反例后51pass（模板、存储、判断来源）；此前模板/存储/受试者期望72pass；diff检查通过。此处只修复数据传递与完整性，不代表过期证据已在临床求值中正确处理。下一项仍是有来源依据的时间用途区分、锚点与期望覆盖消费，六项过期观察strict-xfail仍未收口；不得凭新增字段宣布T1验收。泛化约束沿用当前goal：临床内容来自方案，模型兼容留在适配层，不加疾病/药物/示例专属分支。所有本轮测试已结束，未提交任何本地或临床模型调用。

2026-09-13 C03已完成：实际zcode/GLM-5.3/max，881.98秒，一轮无fallback；报告及owner裁决在对应runs/reviews。时间先筛选修复验证201pass；独立审阅发现窗外资料与真实间隔条件缺乏用途区分。尝试全部窗外UNKNOWN导致9项既有间隔/日历/节点断言回退，已撤回实验，不改旧断言制造通过；新增6strict-xfail记录过期观察误判。最终201pass/6xfail，T1不验收。下一动作是有版本、保持旧hash的时间用途/证据选择合同及期望消费，不能只放宽矩阵或统一未知；宽类型alias仍待修。全部会商/测试进程已结束，无新增临床作业。

2026-09-13 T1时间范围修复进入独立审阅：上轮为真实配置/调用证据实质进展；本地仍忙不抢占。新增`test_expression_temporal_candidate_scope.py`复现5fail/2pass（窗外旧值/未知极性错误污染窗口内结果，同值缺日期因顺序变更结论）。修改expression先按时间成员筛选再聚合、保留时间未知、稳定顺序及同值来源集合后，六文件201 passed。临床语义尚未采纳：all-outside FALSE、未知时间与值为FALSE的三值组合须独立挑战。启用批准C03单名只读zcode/GLM-5.3/max，任务`t1-temporal-scope-review-20260913`；无产品模型/原库调用，审阅冻结当前expression与新反例，owner负责结论整合。主线程不改审阅中的文件。

2026-09-13 T0运行证据补充：上一轮为代码/测试实质进展。本轮只读配置发现产品`.env`仍指向Gemini；已仅修改第二路provider/url/model并显式加A high、B xhigh和65536额度，密钥未改、未输出。新进程`require_page_reader_routes`实际返回GLM high与MTPLX xhigh，两路65536；产品`preflight_page_reader_routes`真实/models均通过。8002由PID1249监听，返回`mtplx-flash-next-optimized-speed`、supports_vision=true、context_length=262144；输出上限和effort支持未在目录声明，因此不能当作实测通过。本地空闲检查两次报告in_flight，未提交本地推理、未重启服务；8001/11234无监听。

沿用`r3_synthetic_visual_probe.py`新增`--lane`以便只测空闲路线，默认双路不变；本地提交前复用已有idle检查。GLM main-A正式产品`read_page`合成视觉/JSON实跑成功，记录在`artifacts/review-20260912/t0-glm-visual-20260913/`：请求65536/high，实际返回glm-5.3-flash/stop，输入3529、输出3760（其中reasoning3044）、缓存0、66.962秒；正文正确保留1.234567、0、mmol/L与日期，handwriting=[]。保留图、原响应、回执和PageReviewRecord；single_lane_only/clinical_acceptance=false。不是双读验收或临床证据。下一安全动作：本地忙时不抢占，推进T1既有宽类型桶与谓词证据绑定的失败反例/设计；MTPLX可用后再做同源合成验证。T0仍未完整收口，原临床库未写。

2026-09-13 T0整合更新（连续实施，非暂停）：上一轮仅解释泛化要求，没有产品修改，归类为无进展；本轮接续已完成E03修改的所有者验证。修复期别语义GLM产品凭据/paas/v4地址、按配置保留effort、默认不覆盖采样、禁止本地输出预算静默压低；该环节length最多增额一次至131072，已在上限则停止。方案/控制/规范化传输亦禁止上限处重复或降低预算；非流式规范化不采信非stop的截断正文。默认GLM连接类型拼写错误不再静默替换。`.env.example`同步GLM high+MTPLX xhigh及65536初始额度；未改真实env、原库或本地服务。

验证：新期别连接/预算/档位/length反例与相邻检查通过；扩大`tests/v2/agents tests/v2/protocols tests/v2/llm tests/v2/services/test_page_review_execution.py`得到1927 passed、1 failed（旧默认8192断言）、1 skipped，用时274.98秒。更新该断言后独立VLM/语义路由/期别三文件重跑60 passed、1 skipped；`git diff --check`通过。不得把分组重跑说成最后版本全库通过。真实模型检查未启用，无新增临床结论，claims_complete=false。T0剩余：重试额度还须全面核对本地物理cap；消除新环境继承旧额度的静默压低；核对真实显式env/身份/能力及最小视觉JSON调用；完成执行包整合回执，再推进T1已证实临床反例。下方旧“代码/env未改”属于审阅历史。

同日后续：方案/控制/控制发现的环境继承预算不再静默压低；方案与控制的length重试若超过配置的本地cap则不发送。相关四文件回归68 passed。首次运行8个历史MLX Serve格式测试失败，原因是fixture未显式冻结额度、继承新的65536却受旧8192服务cap约束；已把纯wire回放fixture明确为历史8192，不修改其采样/Schema断言，不据此证明当前部署。上段T0待办中的这两项已完成代码修复，其余真实env/能力/最小调用及最终整合仍待做。

已读取用户新goal附件，上一轮归类为实质进展（审阅证据及设计/计划修订），现在进入T0–T7实施，不再把旧paused状态当阻塞。T0由主线程直接执行：配置、冻结路由及复核消费者共享可变状态，先用确定性反例和实际请求证据验证；临床语义修复完成后再按触发条件对冻结修改进行独立会商。此次不派独立临床处理，不抢占本地服务；原库只读。

T0追踪到方案/控制/整理传输与逐页读道的不同代码所有权后，细分出有独立路径和离线验收的协议传输单元，启用批准E03执行节点` t0-protocol-model-contract-20260912`（zcode/GLM-5.3-Flash/max）。所有者保留config、逐页、复核与最终整合；节点只改明确五个agents模块及相邻测试，不作产品识别。该拆分用于减少上下文与串行探索成本，不代表额外临床模型。

> 2026-09-12 Codex 接回审查：本轮只读工程与证据检查、必要测试，并修订设计/Plan/goal prompt；不启动新的临床处理或修改原库。采用“主线程全链审查 + 一名 C03 独立只读会商”，因为跨层判定语义及临床完成度存在实质不确定性，独立复核可减少原实现假设的影响。冻结代码基线为 4caf392；下文原交接结论均待复核。最新用户将产品双模型统一为 GLM-5.3-Flash high 与 MTPLX Qwen3.8-Flash-Next-MTPLX-Optimized-Speed xhigh，并要求充足输出额度。该变更不改写历史回执。

### 接回审阅交付（2026-09-12，本段优先）

本轮报告 `ENGINEERING_REVIEW_20260912_CODEX.md` 已形成；恢复计划已重整为T0–T7；工程设计新增§6.1/§17，主设计/阶段状态/本任务PRD/PROJECT_CONTEXT同步；新目标文本为 `GOAL_PROMPT_20260912_REVIEWED.md`。当前原生goal仍paused，工具不支持编辑objective/恢复，不标伪完成来替换。这是审阅交付，不是新增暂停指令。

确定性错误必须先修：宽类型桶无法证明临床谓词；缺口/结论矛盾；判断需求选择口径分裂；子条款身份丢失（EX-07点击一条选中29条）；同数字页码跨文件误定位；跨章控制候选未正式进入审核；最新Profile可能仅保留最后一次run。下方G2的同fact_id例外补丁不应照搬，研究者判断也不是永久不能有终态。原始601事实与校正后516为不同统计口径。

本轮后端4632通过/3跳过；前端563通过/1超时，独立重跑10通过；构建通过。C03独立zcode/GLM-5.3/max审阅成功，无fallback，具体采纳/否决见报告。真实浏览器在只读隔离库复现问题，并完成加载后不同宽屏布局检查；不宣称全应用或临床验收。Phase5/5.5仍未完成，正式审核/行动记录当前为0。

用户最新补充已进入设计：harness跨模型/任务/方案/疾病/药物泛化；当前组合仅部署配置，不能让模型适配影响医学采信。实际代码和env未改、模型未调用，T0必须兑现high/xhigh和足额预算并预检，不能拿这份文档称模型已切换。

本轮产物在`artifacts/review-20260912/`，审查副本与来源hash记录在isolated-server.json。下一步先回读现场，再执行T0/T1反例和纵向修复，不重跑旧整例、不改原库、不清未提交文件；用药分项扩测已有授权、正式自动采信仍未批准。下方历史“工作区干净/已全部提交/三件需用户裁决”等不代表当前现场。

写于 2026-09-12 凌晨。接收方：接手继续构建的下一个 Agent。目标：读完本文即可掌握全局、无缝继续。

---

## 0. 30 秒摘要

单机 Mac 入排审核工作台（AI 辅助，医学监查员使用）。Phase 5（临床事实链 + 入排判定 + 判断检索）工程链路已全线打通并经过独立会商审阅；本会话最后阶段发现并修复了一个**贯穿性根因缺陷**（fact_type 词汇表断链——确定性条款判定从未在真实数据上工作过），修复后真实数据上首次产出确定性判定。当前 HEAD=`45cc774`，工作区干净，全部提交在分支 `codex/phase5-clinical-facts-profile`。`claims_complete=false`，有三件待办在用户侧裁决后继续（详见 §5）。

---

## 1. 来龙去脉（任务规划全景）

### 1.1 项目背景与角色

- **用户**：资深临床试验医学监查员，原生中文，视觉敏感，不熟悉计算机/AI。所有面向用户的文字必须中文原生（不是翻译腔），不得出现工程术语、英文枚举、内部 ID。
- **产品**：本地单机、双击即用的入排审核工作台。AI 领导但**不代替医生做最终入排决定**；系统输出是工作底稿。
- **权威设计文档**：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`（用户三轮确认后的最终设计）。关键承诺：
  - L21：**「形成从最早可证明事件到当前审核节点的入排 Patient Profile」**（患者旅程）；
  - L40/441-443：增量上传去重合并；全量上传新快照；增量展示"重复/已合并/新增/受影响规则"；
  - L188：后台保存**全量事实**，首屏只突出入排相关/异常/临界/风险；
  - 医学红线：**无判断≠阴性；未核实≠缺失**；确定性条款代码判定、专业判断条款不猜；来源可回溯；后期资料不改写早期结论。

### 1.2 Phase 5 的任务与完成态

Phase 5 = 临床事实链（上传→OCR→事实归一化→发布）→ 入排判定（规则解构→期望投影→求值）→ 判断检索（书面判断候选双模型检索）。截至交接：

| 模块 | 状态 | 关键证据 |
|---|---|---|
| 事实链 | ✅ | 601 事实/46 事件/22 暴露（QC 核实），定位覆盖 100% |
| 判断检索 | ✅ | runtime06b/c：24 页 48 读步全带回执；7 要求中 6 条有候选、1 条诚实歧义 |
| 入排判定 | ✅（修复后） | 词汇表桥接（34d4f43）后真实数据首次产出确定性判定 |
| 界面验收 | ✅ | 三档视口截图 7 张归档 + 第三方测试 |
| 测试 | ✅ | 后端 4352 通过；前端 564 通过 |

### 1.3 本会话（09-11 → 09-12）的工作时间线

按提交顺序（`git log --oneline` 可查）：
1. `24a8c77` 组链头：冲突组链等早期修复
2. `eaa428d` **P0 修复**：判断检索执行器完成协议签名（3 参）——runtime06 首次真实跑失败（0 回执）的根因
3. `09bfe2b` UI 三修复：档案页延迟、链路漂移、判断卡中文原生
4. `3df9b09` 上下文文档
5. `e72bce6` 独立会商 4 项 findings 闭环 + 三档截图归档（eaa428d 的回归守卫测试含反例验证）
6. `f466bc2` 收口建议报告 v1
7. `15db86a` 深夜暂停记录（第 19 页 429 发现）
8. `406ae9d` 暂停记录 v2（WIP stash）
9. `c061aa6` **429 限流等待修复**：两读器 12×60s 有界等待 + 3 测试
10. `07d9ed3` **系统性发现落盘**：fact_type 词汇表断链
11. `34d4f43` **C 方案桥接**：谓词/事实词汇表打通 + 终局判定 reason 一致性修复
12. `f7a54e5` 收口建议 §五 更新
13. `15a3637` task notes
14. `45cc774` 第三方测试修复：理由通顺句 + 候选点击未关联页提示

---

## 2. 已实现 vs 未实现（深度分析）

### 2.1 已实现（有直接当前证据）

- **判断检索全链**：正式入口→持久作业→双读（GLM-5.3-flash + Gemini 3.7 flash）→摘要→界面卡片。48/48 读步带回执。6/7 要求 candidates_present。
- **词汇表桥接（34d4f43，本会话最重要产出）**：`EvaluationContext.predicate_fact_type_aliases`（谓词键→允许事实类型集合），投影层从组件 evidence_requirements 的 fact_type 生成映射。真实库效果：筛选「55PJ+26 未到期、零确定性」→「21PJ+14 未触发+2 满足+26 未到期+18 冲突」；基线「81 全 PJ」→「54PJ+18 未触发+9 冲突」。决策-文案矛盾 0。
- **429 有界等待**：c061aa6。GLM 限流不再被 2 次硬重试耗尽。
- **31001 原件 QC**（`QC_31001_20260911.md`）：22 条用药暴露完整；「0 暴露」= runtime05 run 级口径（partial run 收尾重建档案时以 run_id 过滤，坍缩见 §2.2-G1）；判断检索 7 要求 ↔ PJ 期望 7:7 闭环。
- **测试基线**：后端 4352/0 失败；前端 564/564。聚焦回归（投影 12/12、API 3/3、429 3/3、前端 14/14）。

### 2.2 未实现/已知问题（按严重度）

**G1【高危·数据正确性】partial run 档案坍缩**
- 机制：`fact_normalization_executor.py:1299-1304` run 收尾 `generate(run_id=publication.run_id)` → `patient_profile_service.py:342/356/370/390` 四处按 run_id 过滤 → **上一 run 的发布实体从档案消失**（QC_31001 实证：medication 泳道 33→2 条）。对照：`fact_correction_service.py:1163-1172` 修正路径**不传 run_id**（全权威口径）——同一服务两种口径。
- 为何平时无症状：正常 run 强制全页覆盖（planning 层 validate_full_page_closure），run_id 过滤后仍是全量链头；只有 **partial run**（如 runtime05 的 37/601）才坍缩。
- **用户裁决已给出方向**（交接前最后指令）：「第一次上传全量展示，之后全量+增量；区分筛选期/基线期；显示患者旅程」。完整差距清单见 `agent://JourneyAudit`（7 项差距，含 UI 概念：节点切换+旅程泳道+增量标记）。

**G2【高危·判定语义】桥接后判定质量复核未完成**
- ClinicalReview（`agent://ClinicalReview`，transcript: history://ClinicalReview）跑完 45 分钟但最终结构化输出因 GLM 429（5 小时限额）失败，其过程记录揭示两个**真问题**：
  1. **EX-07e 例外接管缺陷**：trigger=TRUE + exception=TRUE → 判「未触发排除标准」——trigger 与 exception 两个语义相反谓词命中同一条 allergy_history 事实，终局判定依据矛盾。唯一走例外接管路径的条款，但医学上不可接受。
  2. **IN-03「症状控制不佳」investigator_judgment 条款被判 inclusion_met**：声明需研究者判断的条款被代码下了终局结论——触碰「专业判断条款不猜」红线。桥接把"任意 affirmed 记录存在"当"满足"。
- **这两个必须修**：修法方向——determination_mode=investigator_judgment 的条款永远不产出终局判定（保持 PJ+检索候选）；exception 谓词与 trigger 谓词命中同一事实时降级 conflict。

**G3【中·判定可信度】18 条筛选 conflict 是"同页多事实"误触发**
- EX-07 疱疹/鼻窦炎/结核等 5 条共享同一组病史"否认…"事实，界面只说"存在冲突"不说冲突内容。第三方测试 P1-2。修法：conflict 卡片并列展示冲突事实原文+页码（候选 API 已有 excerpt 能力）；ClinicalReview 建议复核 conflict 判定树。

**G4【中·旅程】Patient Journey 视图缺失**
- SubjectsPage 每节点独立档案、无跨节点旅程聚合；档案历史端点已实现（`app/api/v2/patient_profiles.py:111-133`）但前端未消费。见 `agent://JourneyAudit` §UI 概念。

**G5【中·链路】用药史观察压制的真正根因=字段粒度对齐**
- 病历 p5 两主读字段粒度完全不同（main-A 按药名 23 字段 vs main-B 按大项 11 字段，交集仅 8 个体征项）→ explicit_conflict_fields 无同 key 可比 → 40 条观察全部 page_observation_unverified 压制。targeted 通道正确拒绝（该页无数值/日期/标记分歧）。这是 09-08 已记录的"受限语义对应隔离"试验范围，**未获用户扩测授权前不要动提示词**。

**G6【低】零散**：run.sh 启动的是 legacy v1 非 V2（P2 文档）；EX-06 子条款 determination_mode 不一致；not_due 带 fact_refs 口径；候选与档案 locator 的 page/source 口径根治（当前已有降级提示，45cc774）。

---

## 3. 当前节点分析

### 3.1 处在什么节点

Phase 5 工程建设**实质完成**（含一个贯穿性根因修复），卡在「判定语义可信度」的最后关卡：G2 两个真问题不修，桥接产出的终局判定不能交给医生看。用户已明确"整个工程构建期间不需要我逐项核对"——构建/测试自主推进，医学结论类决策仍需用户确认。

### 3.2 goal 原文（必须完整保留，不得缩小范围）

> 继续实施构建。注意充分利用orchestra+多sk role模型机制。注意读取最新全局AGENTS.md，遵循方法学、多sk roles model执行/会商机制及模型、Token节省机制。按照Trellis方式进行项目文件管理。定期进行阶段性清理，将不再使用的、旧版的过程文件、缓存文件、测试记录等等进行清理。
> 务必要从用户（懒惰、视觉敏感、不熟悉计算机知识和AI使用的原生中文背景资深临床试验医学监查人员）视角去看问题、查问题、想如何构建、计划哪些细节功能、用怎样的框架逻辑去引导Agent解构预筛/筛选期/基线期的规则、设计怎样的细节交互、使用怎样的视觉设计等等等等的内容。
> 测试者工作期间、执行/会商期间，请保持超长轮询。测试者、执行/会商首次启用要先进行连通性测试，不同harness调用方式存在差别，不要随意fallback。
> 每一步出现预期之外的结果（比如独立Agent没获取到任何方案入排标准、解析后的入排标准条目与研究方案不匹配、没获取到任何受试者病史背景信息等等），构建者、测试者都要去深挖背后的原因，不是说能跑通、html报告能看、流程能通就完了，是要模拟真实的人去真实构建、真实使用这个系统，真实的人遇到预期之外的反馈第一时间是去深挖为何出现这种情况，而不是无脑采信这个雏形系统！始终以第一性原理做构建和测试，始终以批判视角做构建和测试！每轮测试后的旧版文件、缓存、测试文件等等要定期清理。
> 所有的文字、标签等等，都需要中文原生（而不是翻译），且必须把程序员用语、后端标签、log类标签清空，如"xx门"、"xx信号"、纯英文标记等等，针对用户的中文语言要进行原生中文临床试验环境的针对性会商。
> 不需要针对系统做任何安全性的测试、担心，聚焦于面向用户的系统功能构建、测试即可。

### 3.3 goal 实施阶段分析

- **已完成阶段**：Phase 5 全链工程（事实/判定/检索/界面）+ 本会话三连修（429/桥接/UX）+ 独立会商闭环 + 第三方测试。
- **进行中**：多模型复盘三 agent——JourneyAudit ✅（agent://JourneyAudit）、ThirdPartyTest ✅（agent://ThirdPartyTest）、ClinicalReview/CodeReview 过程完成但结构化输出被 GLM 5 小时限额打断（**16:04:59 重置**；transcript 在 history://ClinicalReview、history://CodeReview，过程发现已提炼进本文 §2.2-G2/G3）。
- **下一阶段（按优先级）**：
  1. **修 G2 两判定语义缺陷**（investigator_judgment 不给终局；例外接管矛盾降级 conflict）→ 重跑真实库验证分布 → 前端回归；
  2. **修 G1 档案口径**（run 收尾 generate 去掉 run_id 过滤=全权威口径，与修正路径一致；JourneyAudit 有完整论证）；
  3. **患者旅程视图**（G4，UI 概念见 JourneyAudit）；
  4. **conflict 卡片并列冲突事实**（G3）；
  5. 全部完成后回写 Phase 5 PRD/claims_complete（需用户确认），Phase 5.5 含 A 方案词汇表深度对齐评估。

### 3.4 关键操作知识（避免踩坑）

- **环境**：worktree 路径 `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`。Python 用 `.venv/bin/python`（homebrew python3 缺依赖）。前端 `cd frontend && npx vitest run`。
- **启动 V2 后端**（供浏览器测试）：`ENROLLMENT_ENV_FILE=$W/.env ENROLLMENT_V2_DATA_DIR=$W/artifacts/phase55-takeover/20260911/glm-gemini-runtime-06c-page19-retry .venv/bin/python -m uvicorn app.api.v2.app:create_app --factory --port 8907`。**run.sh 是 legacy v1，不要用**。
- **测试数据根**：06c = 最新（含桥接后判定 + 48/48 检索回执）；06b = 429 前成功证据；e2e-runtime06 = P0 失败现场。**全部保留不删**。
- **模型调用**：GLM 5.3 flash 有 5 小时限额（重置 09-12 16:04）；429 等待已内置读器。连真实模型前先 1 次极小直连探测。
- **Trellis 任务目录**：`.trellis/tasks/09-11-e2e-eligibility-review/`——所有权威文档都在这（见 §4）。
- **承诺边界**：不动 06b/06c 原库做手工 SQL（重置只能做副本）；不擅自改提示词扩测语义对应；中文原生边界；无安全性测试。
- **sub-agent 纪律**：GLM 限额被打断的 agent，过程结论可从 transcript 提炼（history://<id>），勿盲目重跑 45 分钟长任务；先查限额重置时间。

---

## 4. 权威文档索引（全部相对 worktree 根）

| 文档 | 内容 |
|---|---|
| `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` | **最高权威**：最终设计（L21 旅程/L40 上传/L441 增量展示/L188 全量事实） |
| `docs/PROJECT_CONTEXT.md` | 项目状态摘要（顶部 09-11 条目） |
| `.trellis/tasks/09-11-e2e-eligibility-review/PHASE5_CLOSEOUT_RECOMMENDATION_20260911.md` | 收口建议（§五=最新状态） |
| `.trellis/tasks/09-11-e2e-eligibility-review/QC_31001_20260911.md` | 31001 原件 QC（22 暴露/run 口径/人工清单 5 项） |
| `.trellis/tasks/09-11-e2e-eligibility-review/FINDING_20260911_FACT_TYPE_DISCONNECT.md` | 词汇表断链发现（含 A/B/C 方案） |
| `.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260911_OMP_PAUSE.md` | 会话总入口（第一份暂停记录） |
| `.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260911_LATE_PAUSE.md` | 429 发现与 SQL 重置步骤 |
| `.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260911_FINAL_PAUSE.md` | WIP stash 记录 |
| `agent://JourneyAudit` | Patient Journey 设计符合性审阅（7 差距+UI 概念） |
| `agent://ThirdPartyTest` | 第三方测试报告（14 发现，P1-1 已修） |
| `agent://ClinicalReview` / `history://ClinicalReview` | 医学审阅过程（EX-07e/IN-03 两缺陷证据链） |
| `history://CodeReview` | 代码审阅过程（桥接实现细节疑点） |
| `artifacts/phase55-takeover/20260911/glm-gemini-runtime-06c-page19-retry/` | 最新测试数据根（06c） |

---

## 5. 立即可执行的下一步（建议顺序）

1. **修 G2-1**：`app/domain/gates/assessment.py` 的 `derive_component_decision`——`determination_mode=investigator_judgment` 的组件永远返回 PJ（不产出终局）。数据源：clause.determination_mode 已在投影层。
2. **修 G2-2**：`_evaluate_logical` 例外接管——trigger 与 exception 命中同一事实（fact_id 交集非空）时整体降级 UNKNOWN+conflict，而非 exception=TRUE→未触发。
3. 重跑真实库（§3.4 启动方式）验证分布变化 + 前端 `npx vitest run` + 后端聚焦回归。
4. **修 G1**：`fact_normalization_executor.py:1299` 去掉 `run_id=publication.run_id`（与修正路径口径统一）。加测试：partial run 后档案仍含上一 run 实体（现行为 33→2 坍缩，修后应保持 33）。
5. 提交后更新 `PHASE5_CLOSEOUT` §五，向用户汇报判定分布的新变化。
6. 之后：患者旅程视图（G4）→ conflict 卡片（G3）→ claims_complete 用户确认。

**一句话心态**：用户是医生不是工程师——界面每个字都要让医生一眼看懂；系统每个"无法判定"都要说清差什么；永不把"没找到记录"说成"没有病"。
