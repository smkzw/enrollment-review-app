# 0.2.0 当前交接

更新时间：2026-10-13，M1功能包集中验证交回。**Goal active，未暂停；WP2完成、WP3/WP4已形成正式规则下的首份工作稿，等待用户M1验收。** 唯一计划03_PLAN，唯一进度05_PROGRESS；历史留Git，不覆盖旧回执，不是新执行包。

## 1. 五分钟接手

- 工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0`，分支dev/0.2.0。
- 本轮从HEAD12f4352e1db5ff6ea727406ba152fb9cba1751f5接续，clean；前序1ad63f94/41aea00c已推送。当前节点汇总、同源发布版本接线及覆盖复用作为一个功能包；核实际HEAD，不reset/clean。
- 验证源码固定5ac146005c4a36f9c3a17ca7d3cd49ffbe7fb71a，已推送origin/dev/0.2.0；后续仅更新记录，不把记录提交当成新源码测试。全量后端10250通过、243失败/6errors均为WP0同一249项，新增0；不是全库绿。前端tree44159f8与已验证41aea00c相同，831及构建结果有效。
- 用户要求：局部检验到工作稿；核IN-02；低把握原因、备选解释/有据推荐及手工调整；不重跑方案/变量建议；集中验证至M1。
- 生化第8页新增1次真实产品调用，9事实保存并进入Profile及v11工作稿。局部run partial，累计24页成功证明继续使用，不叫整例完整。
- IN-02外层ALL、内部观察ANY保持。本人已64/64审定rev2并发布正式规则v4；工作稿实际消费v4，verification_only=false，不再等待审定，也不重跑方案或建议。
- 用户D13批准当前节点汇总；IN04筛选3项满足，基线2项仍未到期。D14批准对应节点病历相关记载作为研究者判断依据；已完整检索而无记载为证据不足，尚未接入的判断能力仍系统问题，WP5落实。
- 审定页原因→分析→备选方向→目标手工预览已接通；无充分依据不推荐，不造准确率，预览不是保存/批准。
- M1必须用户本人正式审定与验收；构建者不能代签。A/B前次已各一次，不重派或声称v11再次独立通过。

## 2. 运行现场

| 项目 | 当前事实 |
|---|---|
| 自有服务 | 61134，PID62876，exec session71137，v22，运行5ac14600；`./run.sh --data-dir <本树>/data_v2 --port 61134 --no-browser`；显式本树.env；output/wp3-wp4-product-server-v22.log；保留供用户M1验收 |
| 已停止服务 | v17–21自有服务已停止、终态已收回；v20 session17708／v21 session47536均exit143；共享服务不动 |
| 数据库 | 本树data_v2/enrollment-review-v2.sqlite3；最终只读核23completed/139failed_final/2cancelled/2waiting_user，0活动；旧终态不改 |
| 浏览器 | 原Ego23不接管；本任务42，p1已发布方案、p2正式v4／v12工作稿及IN04第6页；三宽屏已看、自然视口恢复，SDK handOff已交用户。不重新接管／不新建空间作恢复 |
| 审定入口 | http://127.0.0.1:61134/#/protocols?job=fb814eb3b657424aa4c4c340e710394b |

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
| 工作稿 | 正式v4下v12，64父+88子=152行；18确定低置信、21未到期、51未定、58系统行/49独立问题，4不适用；122事实及24页沿用 | 18含父子重复，不能称18独立条款；WP5判断能力未接，不称病历无记载 |
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

- 产品路由未换：方案/变量OmniRouter cms-router/glm-5.3-flash high；资料ollama-cloud/deepseek-v4.1-flash high，65536；产品harness直连，不用个人CLI读病例。
- 本轮生化1实际请求，127.278秒stop；input37793/completion46160/total83953/cache0。receipt在raw_response，非evaluation_manifest；实际汇总output/wp3/reference-model-receipts.json。
- 52旧+1=53，已报3563.660+127.278=3690.938秒；3次历史usage未知保持未知。job数不是模型请求数。
- A codebuddy/hy4-preview/high，B grok-4.7/high前次各一次完成；只读/独立性限制保留，B审v7、owner修v8；不是本轮v11独立验收。output/m1-review/completed/不覆盖、不重派。
- 旧报告review-run:cba4a3598df742a9b4d1404f0d7ce324 hash17dec1cc14dc4ee109a8997b51aadb982e91db7d907768ca2ec6916817605844；review-run:88a8316e131041198e9a4ade3dff1144 hash47d76d3329eaa75c33c27e5cf54593857daaf1327fc992d04713b849b939c06d，本轮再次核不变。读取ID须保留review-run前缀。
- 历史正式报告API实际返回REVIEW_HISTORY_INCOMPLETE／500：该消费者要求FinalAssessment，而本版只写work_draft_items。不伪造正式结论来填它；WP7需接工作稿历史读取。当前只证旧存储及哈希保持，不称旧报告界面已通过；Profile在节点更新后标陈旧、历史保留，不能当当前投影。

## 8. 接续

1. 不再要求用户重复审定发布：本人64项已审定，正式v4已经消费。M1集中验证及实际结果自查已经结束，现交本人里程碑验收；A/B此前各一次不重派，不称新v12独立审过。
2. ANC筛选p3原图3.01行单位被便签遮挡、OCR误作%；不能由其他行猜单位或拿基线后值充筛选。FEV1 p5有表格数值，但未明示舒张剂前；不能由“肺功能正常”推pre-BD。保留精确原因，后续有源更正/补证/合法局部取证，不重读整例。
3. 当前工作稿用正式v4，原件、事实及24页相容证明已沿用。v42操作读取指导已实现／合同验证，但未新增真实模型复测，不宣称所有REQ已补齐；不要为提示微调重读成功数值。
4. M1之后，WP5按D14从对应筛选／基线原始病历寻找判断证据，不额外要求另写意见；完成检索无记载才证据不足，当前尚未接入仍系统问题。旧Profile完整投影仍保留，规则／节点更新使其标陈旧；不覆盖原Profile或将其冒称当前，重算留后续能力。
5. 集中窗口已结束，exec82399及functions cell3229均终态exit1（旧249项，新增0），不要继续轮询或重跑。M1验收前不进入WP5新模型任务。日历窗旧失败最小诊断为窗外观察返回unknown（below_time_window），不是把三个月按90天算；WP5消费时核状态政策，不笼统称旧失败均无关。

## 9. 复盘

进步是数据到可解释结果和用户可修改，不是新增调用次数。首错集中在表示/作用域/消费者：单位格式误拒、同义假冲突、局部“或”泄漏、对话框错目标；应先离线修相连链，不能每次整方案长读。

低把握可能是复杂逻辑、尚未实现、来源不足或真正医学裁量。应解释并提供有据方向，不为凑三个选项编造临床规则、虚报概率或强推推荐。当前备选来自已存原文和结构，不是新模型医学金标。

本人审定发布和同源工作稿已完成；下一步是M1本人验收后进入WP5，接通对应病历中的语义与研究者判断证据。不扩框架/读道、不写病例特例。Goal active；记录保全不构成暂停或交付完成。
