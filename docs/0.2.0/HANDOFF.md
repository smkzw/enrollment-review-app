# 0.2.0 当前交接

更新时间：2026-10-13，v18真实工作稿已保存；用户批准准备EX-09修订，**草稿已就绪，等待本人审定／发布，不是已批准或M1通过**。运行时Goal仍显示blocked，工具不能直接恢复；不是用户暂停。唯一计划03_PLAN、唯一进度05_PROGRESS；§2当前表优先，旧v12及更早账本只作历史。

## 1. 五分钟接手

- 工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0`，分支dev/0.2.0。
- 本轮从HEAD12f4352e1db5ff6ea727406ba152fb9cba1751f5接续，clean；前序1ad63f94/41aea00c已推送。当前节点汇总、同源发布版本接线及覆盖复用作为一个功能包；核实际HEAD，不reset/clean。
- 最新病历消费源码15e97a62已推送；本轮追加同源审定继承的服务／API／前端及对应测试，核实际HEAD／dirty。4b06d370全量10284通过、249原有失败／错误只属于该版本；v18消费者167通过及本轮继承108通过不能冒充全库通过。
- 用户要求：局部检验到工作稿；核IN-02；低把握原因、备选解释/有据推荐及手工调整；不重跑方案/变量建议；集中验证至M1。
- 生化第8页新增1次真实产品调用，9事实保存并进入Profile及v11工作稿。局部run partial，累计24页成功证明继续使用，不叫整例完整。
- IN-02外层ALL、内部观察ANY保持；本人已64/64审定并发布正式v4。新EX09草稿2只改一条；实际沿用63旧审定，EX09待本人确认。工作稿仍消费旧v4，不重跑方案或建议、不提前换规则。
- 用户D13批准当前节点汇总；IN04筛选3项满足，基线2项仍未到期。D14允许对应节点病历相关记载作为研究者判断；D15明确排除要求无相反依据、检验不违规时按已核资料范围稳健判断，不额外索签名，入选不能从沉默推满足。真异常／矛盾／不可读不套该政策。
- 审定页原因→分析→备选方向→目标手工预览已接通；无充分依据不推荐，不造准确率，预览不是保存/批准。
- M1必须用户本人正式审定与验收；构建者不能代签。A/B前次已各一次，不重派或声称v11再次独立通过。

## 2. 运行现场

| 项目 | 当前事实 |
|---|---|
| 自有服务 | 61134，PID13658，exec session10850，15e97a62＋审定继承补丁／方法v18／提示v3；显式本树.env及data_v2。只有自己的服务在终态边界重启；共享不动 |
| 数据库作业 | b7c17f473be24ed38d462e54b41c15ce与cd40d59338534ba28f0f6ccbf8b65979均completed11/11；无queued/running/retryable。26完成、139旧失败、5取消、3等待用户，旧状态不改 |
| 当前工作稿 | review-run:2790334f5bc04baf96e3e48af63739bb，v18／正式v4，64父项＋88子项；12父项未决含2技术问题，31系统问题另含原来源失败，不混分母。低置信结果仍待医学核实，不是M1通过 |
| EX09修订 | UI同源反馈Job3470091d0cc54f9cb51814960c06ac4e；草稿revision2 saved，7子条件；63/64实际旧审定有效，只有EX09待审。258审定事件数不变，没有构建者代签或复制批准 |
| 浏览器 | 本任务Ego42，p1 EX09待审草稿，p2 v18工作稿／IN04原件第6页；原23不动。1920/2560/3840实际截图已查，无造坐标；最终handOff用户，恢复先查所有权 |
| 审定入口 | http://127.0.0.1:61134/?build=ex09-review-20261013#/protocols?job=3470091d0cc54f9cb51814960c06ac4e |

恢复核实际进程/端口/数据归属；在运行则复用，不因宿主会话变化重启已终态模型作业。

## 3. 现行边界

读本树AGENTS与docs/0.2.0/01–06相关章，archives仅按07索引找必要历史。单一构建者，不新建Trellis任务、框架、队列、模型榜单、规则真相库。旧跨章、prepared-review、全页固定双读及方法采用链不调用、不修补、不删除。

原方案/病例/人工IE/旧事实/报告不覆盖；真实追加仅本树验证副本。不提交data_v2、.env、原件、临床模型原答；output是受控本机材料，外部审阅仅凭路径不可取得。人工IE不入提示，D001在M3前保持留出。

不重跑完成的方案解构、变量建议、验证发布、24页成功证明、已终态生化局部调用。正式规则发布后先核输入/变量/来源相容，不能为换规则机械重读整24页。

## 4. 用户流程与身份

| 节点 | 已联通 | 未完成 |
|---|---|---|
| 规则 | 64项分类/重点/条件树/原文/多选、备选及目标手工；本人64/64审定并发布正式v4，141绑定保持 | 正式签发不是规则发布；M1尚需用户验收 |
| 资料 | 5文件24页累计账本；9新事实/原值/单位/范围/采样日；Profile rev6 | 筛选ANC单位遮挡、FEV1用药前关系及部分操作事实 |
| 工作稿 | 原v12的49问题／40父项无法判定已被用户退回；v18实际保存，病历到条件与组合消费已联通，64父项12未决 | EX09修订尚未采用；后续邮件／手写原件关系及剩余具体未决仍需核，不能以未决减少宣布可用或M1通过 |
| 原件 | 17确定行逐字同文档0失配；四原值/上限另看原图；正确第8页和三个宽屏截图 | 尚无准确区域坐标，不造红框；不是整例医学验收 |
| 闭环 | 旧版/原件hash保留 | WP5–8、M2/M3、IE、更正补证及D001未执行 |

项目draft-project-1153e25b4eba；方案draft-version-1153e25b4eba；原草稿rev21保留。验证RuleSet revision3/verification_only=true：23 IN/EX、88组件、41REQ、141绑定、197变量、402资料要求。

本人稿Job fb814eb3b657424aa4c4c340e710394b，revision2/published/Job completed；64 medical_manager记录及旧历史保留。当前正式v4（同规则谱系、同方案文件哈希）；verification_only=false。旧验证v3不是当前规则，不能当正式采用证据。

31001中心31，subject58ff71df0cff4a2c9107be743d82584b；筛选episode b843b2c07d6d4318a6df741eb7902eb3/anchor2025-08-08/节点rev5。原件及成对活动指针不改：snapshot c69c297a3ea84c57a8fa953e07567b1d、complete-ad2f258d2aff46a98affc99dfac3ea78。基线e66f903e08cb4d02a50c9162cfb6c4b4未自动更新，不拿后续值判筛选。

本轮新Job65ff4e0c686a4adca2ff14f4cea1a3f4 completed4/4，run review-run:2dfc9de967494c3d894b1bd25a3d0e35，method v12。通过正式work-draft-jobs入口更新当前节点规则并保存；不是直接写病例。采用前SQLite backup output/wp4/before-user-rule-adoption.sqlite3，integrity ok，受控本机不提交。

EpisodeRepository.adopt_published_rule_set核同源文件哈希／期别／规则谱系和唯一一致访视，专用乐观锁切换当前规则指向；不开放通用修改身份、不改旧上下文／报告。活动资料或工作稿期间不切换；源或节点不相容拒绝。review_context_assembly复用旧成功页须同患者／节点／快照／处理修订／规则谱系、同方案文件／期别／字典，不只数目相等；失败及未决继续保留。相同原文覆盖不代表新规则满足。

## 5. 修改、首错与消费者

### 审定及IN-02

- 旧外层ANY将诊断/病史/检测一起放宽；沿ProtocolWorkbenchService.apply_manual_edit保存rev2，只改ALL与误导标题；3谓词、阈值、原文、绑定、内部观察ANY及兄弟hash保持。不调模型、不冒充批准。
- 实际UI发现校验将观察内“当前季节或同期”误作独立条件连接。deconstruction_gate的分支核对现在排除逐字绑定、且不含兄弟锚点的局部观察范围；真外层OR仍拦错误ALL，错误ANY仍拒。现有gate结构-2重验旧缓存，不重读来源或改旧证明。
- 原稿诊断/检测要求研究者判断，但原文未明确所有内容需额外书面意见；**未擅自删要求**。页面列研究者书面判断/已有诊断客观结果/暂保留待审；有明文才推荐，需本人审定变量和资料要求。
- 前端protocolRuleReview.ts、ProtocolRuleReviewPanel.tsx、ProtocolJobFlow.tsx、ProtocolRedoDialogs.tsx、protocolManualEdit.ts；首稿和修订稿共用editDraft，不另调总结模型。
- 实际手工预览曾目标IN02、状态却携带IN01条件；已一起初始化component/editor/predicate并拒错身份提交。空/非法数值及布尔文本明确报错，不变0/false、不吞异常。
- 选项只打开预览；保存形成新稿，相关审定须重做；ID/来源只读。没有点击审定通过/发布。

### 生化到结果

- 现有build_fact_normalization_plan(max_pages_per_call=1)选择冻结第8页，沿FactNormalizationJobService.create_or_reuse_job新增任务，不伪装成功页失败、不造双读、不关覆盖校验。
- logical文档03151c316a6a541298cec36b135d49ab47ab10f27582ad3bd902ace2ebc1fcc8；doc版本3d9c12403620d02aa7a1b31dfadc10cafb41826a9cec13a1bde8a909d43847c6/page8。Job76c5287947b34cbea235472efc02dce0/run280952b7882549eea437357576a2d3f5 completed；run partial、35拒/29未决保留。
- 发布9事实，402期望/52链接/0冲突组；Profile rev6/profile:9e4f2680c4baae1a9d0bcd08cb3a1365累计不重置。局部另外23页未读，不等于累计24页未完成；消费者核旧call相容再复用。
- 原值/范围保存后，reference_upper_bound误拒qualifier带单位和双连接号；泛化格式修复保留同行对象/值/唯一范围/单位/正上限核验，错行/错单位/倒置拒绝，不改阈值。
- “阴性”和带数字阴性同义导致2假冲突；select_by_variable先复用comparison_reading再比较。真阳性/阴性仍CONFLICT，事实原文不改。
- 前序v11（现已被v12继承）：Jobaf80a06feaa04ca1885e8f62b07b6f12 completed4/4，run **review-run:784153c882304c588691302b62d9b212**，supersedes v10 review-run:5c2cc2a7856543a081c0af6a4485d76c；v9/v10/v11保留，不改旧哈希。
- EX09肝功能/肌酐子项未触发低置信；父项仍有研究者判断软件缺口，不写整条通过、也不称研究者没记录。未实现能力列系统问题。

### 时间成本

单次模型127.278秒，11:55:54Z完成；finalize到12:07:55Z约721秒，CPU高不是模型还在思考。_latest_record每模板扫描期望历史且逐行查locator；仅用现有prefetch一次读取关联，再逐行完整解码，所有历史hash/镜像/缺链接保护保留。实际只读探针2次locator SELECT/0.0353秒；无同条件整流程复跑，不能报整例加速倍数。

## 6. 验证及本机证据

| 验证 | 结果和边界 | 证据 |
|---|---|---|
| 结构/组合/保存/API消费者 | 544通过48.88秒exit0；局部观察、真正外层选项、错ALL/ANY、修订缓存和发布消费者 | output/wp1-observation-scope-consumers-final.log |
| 生化/同义/计算/API | 89通过2.38秒exit0，前序136通过56.25秒 | output/wp3-reference-qualitative-consumers-closed.log及原日志 |
| 完整前端 | 831通过98文件40.08秒exit0，workers2，未提高超时 | output/wp1-review-advice-source-directions-full.log |
| 构建 | exit0，正式模式interface_trial=false/protocol_stub=false | output/wp1-review-advice-build-source-directions.log |
| 原件/历史 | 17确定行逐字同文档0失配；四原值/上限看原图；旧2报告hash不变 | output/wp4/reference-v11-source-check.json、m1-medical-input/images/3d9c12403620-p8.png |
| UI | 目标手工预览取消未写；三方向/分析可见；当前正确第8页；1920×1080/2560×1440/3840×2160、DPR1，截图已看 | output/wp1/review-advice-delivery-*；output/wp4/reference-v11-workbench-*及-viewports.json |
| 草稿 | 最新publishable=true，IN02误拦关闭；原人群/节点提醒保留，非批准 | output/wp1/in02-scope-integrity.json、in02-local-source-revision.json |
| 完整后端 | **5ac14600**：10250通过/243失败/6errors、20skip/8xfail，3262.69秒exit1；249失败ID与WP0相同、新增0、关闭0；最终305相连通过。前序12f窗口单列，不混代码 | output/wp4-m1-user-rules-backend-delta.json、原XML/日志；wp4-published-rule-consumers-closed.xml |
| 正式新版工作稿 | 18确定行逐字/同文档0失配，24页累计证明、122事实；IN04当前满足、2基线子项未到期；旧2报告与v11哈希不变，0新模型调用 | output/wp4/user-rules-v12-summary.json、-source-check.json、-workbench.json |

所有output/data_v2是本机受控材料，外部审阅仅凭路径不可获得，未提交临床原答。失败保留：最初测试路径不存在exit4；一次未改文件250项列表5秒超时，单独/限制workers全量通过，未放宽；数据库忙503未入队，终态后成功；首次IN02锁失败未改rev，随后仅成功一次。截屏空间隐藏超时，打开**原空间42缩略图**后成功，不另建空间、不接管23。

## 7. 模型及历史账本

- 方案／变量仍OmniRouter cms-router/glm-5.3-flash high；OCR／事实抽取配置仍原身份。只有本轮工作稿病历原文核对按用户授权使用cms-router/glm-5.3-flash high 65536；产品harness直连，不用个人CLI读病例。
- 本轮生化1实际请求，127.278秒stop；input37793/completion46160/total83953/cache0。receipt在raw_response，非evaluation_manifest；实际汇总output/wp3/reference-model-receipts.json。
- 52旧+1=53，已报3563.660+127.278=3690.938秒；3次历史usage未知保持未知。job数不是模型请求数。
- A codebuddy/hy4-preview/high，B grok-4.7/high前次各一次完成；只读/独立性限制保留，B审v7、owner修v8；不是本轮v11独立验收。output/m1-review/completed/不覆盖、不重派。
- 旧报告review-run:cba4a3598df742a9b4d1404f0d7ce324 hash17dec1cc14dc4ee109a8997b51aadb982e91db7d907768ca2ec6916817605844；review-run:88a8316e131041198e9a4ade3dff1144 hash47d76d3329eaa75c33c27e5cf54593857daaf1327fc992d04713b849b939c06d，本轮再次核不变。读取ID须保留review-run前缀。
- 历史正式报告API实际返回REVIEW_HISTORY_INCOMPLETE／500：该消费者要求FinalAssessment，而本版只写work_draft_items。不伪造正式结论来填它；WP7需接工作稿历史读取。当前只证旧存储及哈希保持，不称旧报告界面已通过；Profile在节点更新后标陈旧、历史保留，不能当当前投影。

## 8. 当前接续

1. EX09按用户D17已准备局部修订：不再要求重审全部64项；仅这条等待本人审定发布。正式v4与旧结果保持，不自动启用草稿。本人发布后按输入／来源／消费者相容复验成功读数，不能机械重读整例。
2. ANC筛选p3原图3.01行单位被便签遮挡、OCR误作%；不能由其他行猜单位或拿基线后值充筛选。FEV1 p5有表格数值，但未明示舒张剂前；不能由“肺功能正常”推pre-BD。保留精确原因，后续有源更正/补证/合法局部取证，不重读整例。
3. 当前工作稿v18已完成：7排除未触发、10其他未决、2技术问题、1已触发、4入选满足、15未到期、21操作满足、4不适用。全部152行保留；31来源／系统记录与12未决父项不混算。读数合格、缓存相容不等于医学正确；尤其“邮件.pdf”同时含原始门诊病历和后续审核邮件，不能按整文件一律采信或排除。
4. 已提前接WP5必要病历消费；其范围／药物清单完整能力仍未全部交付。旧Profile保留；本轮source_read_refs不伪造ClinicalFact、不重新生成Profile，不把病历中未来计划当已完成动作。
5. v17/v18均终态，不再轮询或重跑。v17新增5调用2634.146秒（已报输入74063／输出136918），v18仅1调用287.201秒（12172／12507）；121/122关系复验旧原答，最后1项局部新读，不刷新历史预算。思考用量细分未知，回执中的0不当作实际零思考。

### EX09提案、审定继承与实际验证

- 同源反馈通过真实UI入口创建，原生成来源和正式基线均冻结。经既有`ProtocolDraftService.apply_feedback(SOURCE_ERROR)`及`_update_draft_checkpoint`保存revision2；作者明确构建者准备、未审定。移除两个误拆总述及其6资料要求／对应阶段ID，剩余7条件、原文、阈值、变量和来源不变。没有新模型调用、SQL临床写入、批准或发布。私有脚本output/wp5_prepare_ex09.py已保存一次，**不可再次--save**；脚本强制检查revision1防重写。
- 补齐`protocol_rule_review.current_reviews`同源继承：实际Job冻源／生成草稿／published基线三者一致，旧事件自身哈希有效，当前自身内容等价才沿用；新增解释来源不继承。REQ阶段只排除无关到期ID，自身要求、节点、时间、来源和变量仍严格核对；撤销优先。API `reviewed_content_hash`连接后端核验与前端，历史审定原哈希不改、不造新签名。
- 首次真实UI暴露继承记录原哈希与当前全阶段哈希不同导致解码拒绝；已补显式当前内容绑定，而非删除过期保护。108相连后端52.14秒exit0，正例及改源／项目／条款／节点／证明／撤销反例；前端5绑定测试、完整98文件834通过34.95秒及正式TypeScript/Vite构建exit0（旧大chunk提醒）。v18来源消费者167通过34.30秒；不能引用旧全库作为当前全量。Trellis record因未初始化developer失败；不重建旧任务／workspace，按0.2.0以05_PROGRESS和本交接合并记录。
- API及Ego实证63/64，仅EX09待审，其他旧事件原ID／人员保持。审定页仍有原完整性启发提醒，不静默删除，不将该提醒替代用户医学解读或修改通用gate制造绿色。新v18保持旧规则EX09触发，等待新规则真正发布后再算。
- 本机私有证据：output/wp5-ex09-proposal-save.json、wp5-ex09-draft-readback.json、wp5-ex09-current-reviews.json、wp5-ex09-review-heritage-final.xml、wp5-v17-v18-receipts-summary.json、wp5-ex09-review-*与wp5-v18-in04-*宽屏截图；外部审阅不能仅凭/Users路径取得。所有原答／原件／数据库/.env不提交。

### 历史诊断账本（以下v13–16为历史，不是当前运行状态）

- 第一因果错误在工作稿生产／消费，不在患者：semantic返回空的WP5_pending，判断／意愿／适用人群／暴露等特征在使用证据前被统一拒绝。原M1技术性保存及测试被过早当成用户可验收入口。纠正方法是实接原文→条件→组合→API→原件导航，不是更换病例或为每条加补丁。
- `work_draft_semantics.py`每批16条件，当前122目标／8批；22当前节点页，2明确后续页不借用。逐字引用、目标完整／唯一、对象／时间关系核对；合法兄弟结果冻结，仅重试坏项一次。数值原操作数须逐字存在、单位合法后由程序比较；复杂计算不由模型算。
- 复用现有Job、ArtifactStore、传输和表达式；source_read_refs与正式事实分开。真实冲突保留所有反证；“未见记录”保存已查范围，不伪造否认／NCS。未知子项只有经true/false反事实均不影响既有结果时才不阻断独立结论。
- v13 Job3cc7da81c88943d2a98899e9fd706d36 completed11/11，但8次Ollama均429月额度，0成功病历结果；run92b8d772…保持49问题，不宣称新消费成功。失败原答／账本保留。已补共同401/403/429阻止后续重复请求，技术未完成不能变not_found。
- 用户已授权本次核病历改用cms-router/glm-5.3-flash high。仅覆盖WORK_DRAFT_SEMANTIC，其他角色不变。v14两批600.146／600.004秒超时无正文及usage，余6批未发；cancelled保持原hash。v15共用两次请求预算，冻结流式模型参数；最小非病例连接预检9.971秒stop、实际GLM身份、上游322总token，用量细分重复／缺报保持原值，不算病例结果；001a04995…已终态，不再重跑。
- 4b06相连225通过；加入流式曾219／2失败（误放宽直连身份），已修保留反例。v16/73b相连233通过64.48秒；真实只读复验旧39方向保持、新7只保留未知，不新授确定资格；原编号缺失仍拒。前端833通过98文件35.92秒exit0，正式构建exit0。
- 4b06完整后端分v2与非v2两个相连窗口：10284通过／243失败／6errors，1803.68秒、均exit1；249失败ID与前轮／WP0相同，新增0。证据output/wp5-backend-full-combined-delta.json及两个XML／日志。核心73b的新增兼容复验／短引用／未知处理仅233相连验证，不把4b06全量归到73b。
- v15正常stop但局部恢复反复缩短页编号／混淆未知与否定。v16明示T/P枚举及可逆表，去空字段／目标机器编号而不删临床关系；真实旧请求／回答＋相同来源／条件／模型／语义指导经新校验，39旧方向保持，7附引用但时间不明仅转未知。48中另2来源错误用新格式读取362.974秒正常完成；前三批0格式错误，整例未完成。不得将39／48数量当医学准确率或完整交付。
- 实际停止流程发现cancel_requested不在前端回执枚举、轮询中断后按钮一直停用；已加合法停止状态及边界轮询，用真实同空间reload恢复后从UI新开v15，不改localStorage为假完成，也不新建浏览器空间。
- 真实Ego去彩条截图output/wp5-card-bars-removed.png，1908×917已看；最新v18与EX09三宽屏结果见当前表，没有造坐标。Kangzhe按功能优先局部应用，不称全站设计认证。
- 原报告cba4a…、88a831…及v12的payload hash再次核不变；SQLite backup output/wp5-before-source-relations.sqlite3保存。本轮全部模型原答／回执／截图受控本机，不提交临床全文、数据或.env。

## 9. 复盘

进步是数据到可解释结果和用户可修改，不是新增调用次数。首错集中在表示/作用域/消费者：单位格式误拒、同义假冲突、局部“或”泄漏、对话框错目标；应先离线修相连链，不能每次整方案长读。

低把握可能是复杂逻辑、尚未实现、来源不足或真正医学裁量。应解释并提供有据方向，不为凑三个选项编造临床规则、虚报概率或强推推荐。当前备选来自已存原文和结构，不是新模型医学金标。

本人审定发布已完成，但“保存一份大量未决稿”不等于医学经理能用上。前轮将关键判断消费排在M1之后，是验收顺序与真实用户需求不匹配；空semantic步骤更使技术性闭环遮住临床功能未接。当前提前补齐必要消费、保持数值与出处边界；完成新稿后再逐条解释剩余未决属于资料、含义、程序还是模型。不得为制造改善放宽事实真实性，也不把没有更强模型当盲重试理由。
