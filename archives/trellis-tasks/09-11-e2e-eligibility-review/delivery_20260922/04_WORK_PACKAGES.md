# 分步骤实施包 W0–W7

所有相对路径从唯一worktree起算。每包共同要求：先读完整受影响定义和调用者；生产→保存→消费→可操作入口齐备；在implement更新一次有证据的状态，然后直接进入下一包。检查窗口见02，不逐小改执行测试。

## W0 可构建基线与受控输入
**输入**：e7f34d05、01_REVIEW C03/C05/C09、专家R2-04/05/06/12、09检查结果。
**改动范围**：frontend/src/domain/{labels,mappers}.ts、api/wire.ts及生成器真实合同源；pages/EligibilityWorkbenchPage{,.test}.tsx；scripts/build_scale_validation_set.py、run_scale_validation.py、wp08_muse_spark_watch.sh；原task元数据。
**动作**：
1. 逐项修6个编译问题，先核API/枚举生成关系；test fixture补完整属性，不能给正式DTO改可选来迁就旧fixture。
2. 规模材料构建复用PDF/图像解码器，单图1页、TIFF按帧、HEIC按实际解码能力；无法确定写unknown并阻止完整性通过。规范MIME。
3. 模块级os、resolve所有路径及回退；排除当前和主源码worktree/软链落点。每run独立目录和完整hash，保留原件，不覆盖同名结果。
4. 专用watch退役：从现行恢复说明移除，禁止执行，后续恢复走已有Job，不再修补该私人守望脚本或读取个人.omp/install-id。保留历史证据，不启动旧临床任务。
5. 合并当前状态，旧handoff保留但不作执行入口。列外部凭据轮换的unknown，不读历史泄露值/不发请求试探。
6. 先修10所证实的跨供应商密钥回退：当前ollama-cloud缺独立key却取GLM key，必须本地拒绝。不修改秘密值或自动替用户换模型；供应商合同集中W3验证。
**交付**：前端可编译改动、材料manifest可靠、无自动重启旧watch。Q1集中build；路径/混合媒体最小反例合并进现有scripts测试层，无临床文件入库。
**禁止**：新材料平台、删除历史、自动批量提交、把HTTP错误修复重新做一遍。

## W1 完整资格与工作稿计算统一
**输入**：C01/C07、R2-01/02，实际review_context与qualified材料合同。
**路径**：services/eligibility_review_projection.py、qualified_binding_selection.py、binding_qualification_support.py、frozen_review_calculation.py、component_review.py、published_clause_pack.py；domain/expression.py、contracts/qualified_binding_selection.py；api/v2/eligibility_review.py与前端DTO消费者。
**动作**：
1. 复用qualified_binding_selection现有选择实现，不新写平行选择器。对现有完整组装链作最小职责提取，提供工作稿可调用、真实回执已核但无正式采用副作用的入口；沿用_select_with_ordering、_select_facts_for_identity、_semantic_ordering及频次/复查/命题消费者。仅调用某个私有helper不足以覆盖401行起工厂的全部语义；正式封装继续验证真实授权，禁止伪seal或批准对象。
2. 授权与语义分层：工作稿可计算/查看不等于批准采用；正式签发继续校验授权与immutable scope。不得向现有sealed wrapper伪注入批准。
3. 选择结果保留显式state、identity、输入digest、selected pair+fact+attribute、日期来源、排除原因及特殊计算结果；尽量复用已有QualifiedBindingSelectionMaterial，不新建平行真相表。
4. 全拒绝/失败/未核/陈旧显式处置，不折None。新资格路径永不回退旧类型别名；legacy记录只按历史模式展示，不能自动成为新结果。
5. 任务按完整authority和当前事实/元数据/locator digest查找，先scope过滤再排序。当前scope新任务未完可展示历史结果但必须标陈旧，不默认为当前。错误payload不是无任务。
6. 官方与control来自同一published revision。计算后工作稿、行动、冻结报告复用同一结果结构；补充要求保留自身编号/来源，不伪造官方编号。删除return后旧逻辑。
7. 活接口增加并列controls，复用review_history已有显示结构；不将控制塞入官方clauses。若方案确只有补充要求，官方列表可为空，但必须有权威发布与覆盖依据及实际要求；总要求为零不能算审核成功。正常未加载用独立准备状态，不拿空列表当报告。
**Q1验证**：日期单独通过、值无合格日期、single多值（含两条同值）、正常值+日期、全部拒绝、未完成/陈旧、坏载荷不借旧任务、无policy反例，以及频次/复查/例外/命题/跨章正反例。修复后用现有服务路径而非抄函数独立probe。
**退出**：同冻结输入工作稿与正式计算语义相同，只有授权差异；一项不足不掩盖其他确定结果，无资格不作阴性。

## W2 方案Agent与跨章规则正确发布
**输入**：V3方案节、C04、现有RETURN_A来源记录，不以candidate_ready当发布证据。
**路径**：agents/protocol_control_deconstructor.py::_strip_invalid_evaluation_specs/parse_protocol_control_agent_wire及runner；protocols/protocol_control_gate.py、deconstruction_gate.py、protocol_control_planning.py；services/protocol_deconstruction_executor.py、protocol_control_execution.py、protocol_draft_service.py、protocol_publication_service.py、protocol_control_catalog_publication.py；frontend/components/protocols/和ProtocolsPage。
**动作**：
1. 查格式修复/预清洗所有分支，保留原始输出；错误evaluation标技术未解析并记录原因，禁止替换成无来源的investigator_judgment。原文确有研究者裁量才生成该mode。
2. 同源草稿及时预览，继续核对及有据局部修订；兄弟对象不变。格式字段修复不重复全图全包，语义修改仅受影响来源，最多两次无新信息停止。
3. 核完整方案单位覆盖和跨章依赖，不对全部章节重复精识；药物限制/洗脱/时间/例外/节点义务全量有处置。不能因难生成而把真正控制改non_control或裁剪掉。
4. 核发布入口control_job_id可选对当前方案的影响：有跨章要求不能漏发布；确实无要求应有来源化覆盖结果。官方/控制/节点要求同一事务和修订身份。
5. 对既有被预清洗的已发布控制先审查影响清单；需要时合法新草稿修订重发，下游标陈旧。不得修改原发布JSON或用手工临床答案补模型。
6. 一次新DOCX真实发布安排W6，不在本包重复跑多份完整方案；Q1用当前输出工件/纯合同验证变更。
**退出**：技术未解析和专业判断可区分；共同发布完整；原编号/父子/否定/时间/例外/未知保留。

## W3 主OCR与局部核实来源正式贯通
**输入**：C02/C06/C10、R2-03/07，原件图/可靠原生文本和当前已授权路由。
**路径**：api/v2/app.py、page_review.py、evidence.py；services/evidence_processing_executor.py、page_review_job_service.py、page_review_job_executor.py、page_review_runtime.py、selective_vision_observation_service.py、fact_normalization_{command_service,job_service,source_adapter,executor}.py、fact_publication_service.py；domain/contracts/{source_policy,page_review,evidence_normalizer}.py、page_review_evidence_sources.py；llm/page_review_harness.py、page_review_transport_options.py、page_review_format_repair.py；evidence/{ocr_adapter,pdf_native,reading_view}.py；storage/page_review_repository.py。
**动作**：
1. 定义产品显式读取策略并接既有plan/runtime；默认OCR/native→覆盖检查→受影响区域核实，旧双读只在显式legacy/dual策略。复用已有selective与targeted，不另建Agent平台。
2. 核所有require_page_review和coverage/normalizer/source gate依赖，替换为对当前政策的真实检查，不简单关开关。policy/observation/verification必须有生产者、仓储、消费者和恢复版本；旧记录保持旧语义。
   复用SourcePolicy/VerificationStatus可用词汇，但is_verified标记仍需核真实证据引用；不把未用ObservationRecord另建成第二套事实库，不混用ControlEvidenceSourcePolicy或绑定层同名字面量。self_consistent不可单独获得已核资格。
3. 关键字段单位/日期/否定/剂量、表格跨页表头、手写判断与签名归属等有上下文的区域核实。OCR产字不等于完整覆盖；无精确坐标只标页/区域，不伪精框。不让候选值/入组目标锚定首次核实。
4. 模型适配保存脱敏请求合同（端点path、headers存在性、图片hash/尺寸/MIME/bytes、prompt/schema版本、reasoning/output预算、stream/format、请求digest）；响应保留error code/message/param/request_id、finish、usage及失败阶段。无usage写unknown。
5. requested/reported/resolved identity和别名policy分别保存；缺reported不回填；未知变化不能冒充核实。流内变化、续跑、序列化、覆盖选择同步。不可要求远端证明未提供的真实权重，只清楚标“服务声明”。
6. C0文本→同客户端单页实际合同控制变量诊断，有据排除之后再3–5页。若新主线不需要该失败provider，就不为修旧双读耗完整矩阵。不要按HTTP400猜图像限额，不对泄露凭据发请求。
   10已完成无临床数据的文字/合成图诊断，不重复它。OpenCode稳定session与如实User-Agent是已证实接入要求；正式业务适用范围须确认。当前失败并非要求用户重新提供另一个模型才能继续所有开发。
7. 单页临床观察/来源→规范化→发布→Profile原件入口，保留已确认属性和疑问，不补日期。新策略缓存身份以source/policy/prompt/schema决定；不无条件借旧批准。
**Q2验证**：政策合法/不合法来源、无坐标、局部冲突、单位日期、当前scope、旧读兼容、预算length/429/流截断/取消恢复。端点例外检查只做必要次数。
**退出**：不再为了正常主OCR资料强制第二模型；未核源不发布成已核事实；运行和恢复都可追真实角色。

## W4 正式工作台与连续例外处理
**输入**：W1结果DTO、W3来源状态，R2-08/09/10。
**路径**：frontend/src/pages/EligibilityWorkbenchPage.tsx、EvidencePage、SubjectsCatalogPage、ReviewActionsPage、ReportsPage；components/evidence-workspace/OriginalEvidenceViewer.tsx、review/FrozenReviewReport.tsx；api/eligibility-review、api/review-history、app/routes.tsx、styles/workbench.css。
**动作**：
1. 同一左栏切换“待处理/全部条款”，组与成员用同一稳定优先序；显式深链优先、筛选后选有效项/空态；不是groups[0]直接取原首成员。
2. 同类缺口只分类展示。可一起解决的具体问题需对象/观察/时点/来源/行动范围一致，无法证实时不合并关闭。
3. 中栏短依据/影响/动作，原文独立展开；不把一段话分成三张大卡片，不模型重写事实。技术失败用临床用户可懂的“本次处理未完成”等，不冒充病历缺件。
4. 列表有合理上限、可调整，中栏可读、原件优先利用大屏，使用现有康哲3D规范克制表现。支持1080P/2K/4K和桌面缩放，不造手机页面、不缩根字号。
5. reference/candidate/browse三态明确。资料版本来自snapshot，节点revision单独显示。页码/文档/定位/历史快照必须一致；普通浏览首页不叫引用。
6. 受试者、问题、证据直达正确对象，返回恢复filter/search/sort/page/selection/scroll。所有动作包括取消/重试/更正/补证有后端状态和失败反馈。
**Q2检查**：一次前端build与集中组件/状态检查。Q3用Ego Lite实操、截图、宽屏、红框与原件核对；不在每次CSS修改后全轮截图。
**退出**：正式模式不依赖stub，长文/无事实/失败/待核也可操作；展示完整要求，不隐去高风险。

## W5 一次更正与补证完整闭环
**输入**：W1同源结果，W3观察身份，R2-11。
**路径**：app/services/fact_correction_service.py、fact_correction_job_service.py、fact_correction_executor.py；app/domain/planning/fact_correction_impact.py、app/storage/fact_correction_impact_queries.py；prepared_review_workflow.py、judgment_search_*、review_context_*、frozen_review_publication.py；app/api/v2/fact_corrections.py与既有前端纠错入口。
**动作**：
1. 同页/同对象只列相关候选，基于观察属性、原始位置、时间及明确派生lineage确认同观察。未知对象不能构成同一证明。
2. 一次用户更正预览影响→版本/幂等校验→新观察/派生事实→依赖失效→必要资格重算→新工作稿/新报告。不同派生属性重新推导，不批量复制值。
3. 新补证对覆盖范围的“未发现”检索失效，即使没有旧fact引用；局部数值更正不全例重读。保留累计事件/用药/冲突链。
   优先在judgment_search_repository/投影消费点校验既有scope_sha256和当前事实/期望版本头，确保同处理修订下事实更新也能使旧否定摘要失效；不同处理修订已有隔离，不另造影响引擎或新观察真相表。
4. 用户能看到更新中/需核对/完成；旧报告只读，历史定位不会跳新原件。并发/重复点击不产生多次修订。
**Q2验证**：同页不同观察不联改、真实派生同步、补证否定检索失效、旧版本不变、幂等和过期拒绝；W6统一真实更正。
**退出**：不需要用户逐条内部fact修复，也不让无关事实重写；没有原件依据不制造真实病历错误作演示。

## W6 正式全链试跑与集中临床检查
**输入**：W0–W5、06真实资料指向，原件+已发布规则；不得用人工编写gold替产品模型生成。
**路径**：现有正式API/UI和JobRunner；scripts/run_scale_validation.py仅编排正式入口；相关tests与验收证据目录。
**动作**：
1. 新项目从内置DOCX入口产生共同发布规则；保留官方/控制/节点总数、编号和coverage分母，不以23/69等历史数值硬编码通用验收。
2. 新受试者当前节点多文件完整摄入；实际页帧数、处理成功、可用/待核/失败逐页守恒；完整processing revision构建并合法激活，元数据确认不能晚于冻结后偷偷更换。
3. 主读取→局部核实→规范化→正式事实/累计Profile→当前review_context→binding/qualification→完整工作稿。必须实际跑新增事实后的资格步骤，不写“前置已完成”。
4. 正确正/负/未决核查：从原件解释为什么，不仅JSON可解析；研究者书面判断缺失正常报告、不弹用户确认循环。
5. 真实更正或补证→依赖失效→新资格/结果/报告，核旧snapshot/fact/report hash不变。报告页面/导出同源。
6. 技术阶段完成、证据可用、工作稿可用、正式签发分别记录。缺真实授权时验证合法拒绝和待批准状态，不能伪签或宣布正式签发成功。
**退出**：05中的A01–A12全部真实有证据或明确阻塞。全UNKNOWN、空clauses、旧事实拼新snapshot都失败；真实未决本身可接受但需原件支持。

## W7 泛化、视觉、性能与交付
**输入**：完整W6，旧Phase8/9范围。
**动作**：另一不同结构方案内置发布+另一受试者/异形资料验证；同值不同时间/对象、缺研究者判断、筛选至基线、重复上传/补证、失败恢复；正式各入口按05矩阵验收。
Ego Lite在1920×1080、2560×1440、3840×2160及合理桌面缩放核字体/间距/信息密度、原件滚动/标注/弹窗/键盘焦点、返回上下文。没有截图或交互证据不能判美学完成。
计时按首次方案、预处理、主读、局部核实、规范化、资格、报告、人工等待拆分，缓存注明；先消掉重复大输入和重读，不开展无限模型横评。
验证正式桌面启动、关闭/重启、断点续跑、隔离库备份恢复；发布不启stub；给普通用户短中文使用说明、操作者故障恢复和配置变量清单（无密钥）。
清理列明可删除产物与保留依据，只清本轮确认无引用的过期临时文件；弃用脚本不再被入口引用；原始资料/失败证据/历史报告保留。
**退出**：Q3完整验收表、已知限制、可启动交付入口、数据和配置恢复指引齐备；无未解决P1/P2功能缺陷。若仍需正式授权，只能声明软件验收通过/正式签发待授权，目标不得偷换成已完成临床批准。
