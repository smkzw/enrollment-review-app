# 0.2.0 当前交接

更新：2026-10-13，本轮。**Goal active；M1未验收，claims_complete=false。** 用户已审定发布IN03，正式v6。v24从真实UI保存后仍错误借用后来治疗，未作临床接受；已补审定资料限定与完整组合传递，v25正在核28受同一缺陷影响的条件，95不变来源复用。唯一计划03_PLAN、进度05_PROGRESS；§2是现行，其余旧方法／版本结果是历史，不重跑已终态任务。

## 1. 五分钟接手

- 工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0`，分支dev/0.2.0。
- 本次从e20b360b336fc945bb87337de0cdc1f0c85aec0d接续，clean；051a249d与2114f55b已提交推送。2114包含共同要求闭合／v23、连续审定来源继承、中文完整条件展示及相连测试／现行文档，是本次完整后端测试的源码；本交接随后只有证据记录更新。未引入框架、队列或新模型；以实际HEAD／dirty核后继，不把本机output或临床库当Git产物。
- 当前方法v25、提示v4；基线ffb31e99＋未提交功能包，当前相连277通过60.52秒。既有2114f55b整体回归249失败/错误ID与WP0相同、无新增，是旧快照而非本次全量；前端本次未改。v24两请求正常stop、116复用／123关系，仍存在错义，不作为M1通过。
- 用户要求：局部检验到工作稿；核IN-02；低把握原因、备选解释/有据推荐及手工调整；不重跑方案/变量建议；集中验证至M1。
- 生化第8页新增1次真实产品调用，9事实保存并进入Profile及v11工作稿。局部run partial，累计24页成功证明继续使用，不叫整例完整。
- IN-02外层ALL、内部观察ANY保持；本人已64/64发布正式v6，Job05641a…completed、草稿2 published，verification_only=false。IN03只细化对应治疗／疗效／节点来源，原文／字典／阶段不变，其他63项审定保留；不重读方案／建议。
- 用户D13批准当前节点汇总；IN04筛选3项满足，基线2项仍未到期。D14允许对应节点病历相关记载作为研究者判断；D15明确排除要求无相反依据、检验不违规时按已核资料范围稳健判断，不额外索签名，入选不能从沉默推满足。真异常／矛盾／不可读不套该政策。
- 审定页原因→分析→备选方向→目标手工预览已接通；无充分依据不推荐，不造准确率，预览不是保存/批准。
- M1必须用户本人正式审定与验收；构建者不能代签。A/B前次已各一次，不重派或声称v11再次独立通过。

## 2. 运行现场

| 项目 | 当前事实 |
|---|---|
| 自有服务 | PID4477／61134、exec84535，显式本树.env/data_v2；v25已加载，output/wp5-v25-server.log。仅在无活动任务时停止自己的旧服务，共享服务不改 |
| 数据库作业 | 新Job21d725dd39fd43cda107b0449a7df5f0 running，8持久批次，仅28需新读、95已核复用；不要重复提交或重启。旧241d2b…completed11/11、09a426…cancelled保持 |
| 最新保存工作稿 | v24 review-run:37742ed9c24b4910aeb27ec384797a32，正式v6、64父＋85子；7未决＋2系统，EX15有源否认已消费。IN03虽然满足，仍引用节点后背景治疗，**未作临床接受**。当前新run e9d557848a6b410a9320a8a58d041a9c尚未终态 |
| 正式规则 | 正式v6 verification_only=false、64/64本人medical_manager；EX06／EX09及IN03均已本人审定发布，不是工作稿签发 |
| 修订草稿 | Job05641a57cb874f399a81684aca010d06、revision2 published／completed。旧66事件及原件不改，发布由本人完成，非构建者代签 |
| 浏览器 | Ego42实查agent控制，p2两次从更新工作稿按钮合法新建。p1保留已发布稿；不新建空间。v25尚运行，不能用旧截图冒称本轮结果已验证 |
| 审定入口 | http://127.0.0.1:61134/?build=in03-review-20261013#/protocols?job=05641a57cb874f399a81684aca010d06 |

恢复核实际进程/端口/数据归属；在运行则复用，不因宿主会话变化重启已终态模型作业。

## 3. 现行边界

读本树AGENTS与docs/0.2.0/01–06相关章，archives仅按07索引找必要历史。单一构建者，不新建Trellis任务、框架、队列、模型榜单、规则真相库。旧跨章、prepared-review、全页固定双读及方法采用链不调用、不修补、不删除。

原方案/病例/人工IE/旧事实/报告不覆盖；真实追加仅本树验证副本。不提交data_v2、.env、原件、临床模型原答；output是受控本机材料，外部审阅仅凭路径不可取得。人工IE不入提示，D001在M3前保持留出。

不重跑完成的方案解构、变量建议、验证发布、24页成功证明、已终态生化局部调用。正式规则发布后先核输入/变量/来源相容，不能为换规则机械重读整24页。

## 4. 用户流程与身份

| 节点 | 已联通 | 未完成 |
|---|---|---|
| 规则 | 64项分类/重点/条件树/原文/多选、备选及目标手工；本人64/64审定正式v5，EX06/09已生效 | 新IN03提案待本人审定发布；M1尚需验收，规则发布不是签发 |
| 资料 | 5文件24页累计账本；9新事实/原值/单位/范围/采样日；Profile rev6 | 筛选ANC单位遮挡、FEV1用药前关系及部分操作事实 |
| 工作稿 | 原v12被退回；v23/正式v5实存，IN04当前满足、未来要求保留；共同要求不阻断已证且无关的结果，日期未核不能模型代算 | IN03关联提案尚未生效；EX14/REQ32人群及随机日期／ANC单位／FEV1关系等未决仍需核，数量不代表M1通过 |
| 原件 | 17确定行逐字同文档0失配；四原值/上限另看原图；正确第8页和三个宽屏截图 | 尚无准确区域坐标，不造红框；不是整例医学验收 |
| 闭环 | 旧版/原件hash保留 | WP5–8、M2/M3、IE、更正补证及D001未执行 |

项目draft-project-1153e25b4eba；方案draft-version-1153e25b4eba；原草稿rev21保留。验证RuleSet revision3/verification_only=true：23 IN/EX、88组件、41REQ、141绑定、197变量、402资料要求。

本人旧稿Job fb814eb3b657424aa4c4c340e710394b，revision2/published/Job completed；64 medical_manager原记录保留。当前正式v5来自Job3470091…（同规则谱系、同方案文件哈希），verification_only=false；旧v4及验证v3不是当前规则，不当新采用证据。

31001中心31，subject58ff71df0cff4a2c9107be743d82584b；筛选episode b843b2c07d6d4318a6df741eb7902eb3/anchor2025-08-08/节点rev6，当前正式v5。原件及成对活动指针不改：snapshot c69c297a3ea84c57a8fa953e07567b1d、complete-ad2f258d2aff46a98affc99dfac3ea78。基线e66f903e08cb4d02a50c9162cfb6c4b4未自动更新，不拿后续值判筛选。

历史v12 Job65ff4e0c686a4adca2ff14f4cea1a3f4及run2dfc9de…保留。当前52ba1ec…/6de018…从正式work-draft-jobs入口消费v5，supersedes403dff…；不是直接改病例。已有一致性备份及影子验证副本保持，受控本机不提交，不因恢复重造16GB备份。

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

### 6.1 本次 WP4/5（现行，D19尚未发布）

- 051a249d已推送：新版规则发布后GET因旧节点版本拒绝时，只有目录证明同谱系新修订才展示原更新入口；后端患者／节点／原件身份仍核。真实Ego更新v5 Job49b9818…/run24d6a5…，119复用0调用34.850秒；清旧component/page链接并重新读节点，没有改localStorage造结果。
- v21 Job782f9fd0b5ce40828522c38517bbad54/runae4cf552548f4288838410eb27068efd保存却误增14系统父项：共同要求重复添加已观察期望。发现后中止自有全库测试，exit1，不称通过。v22修复重复后仍4相连失败揭示实际后代被内容过滤缩小分母；已改先全找后代，再验证每项。v23允许原来源无类型限制时派生绑定加严，拒绝反向放宽、错类型及其他政策改变；测试正反例不删。
- v23 Job52ba1ec31d5c47798cb2e03a7e77a1c4/run6de018a1fa524e25bb2053a66649024f完整149行：8未触发、8未决、2系统、6入选满足、15未到期、21操作满足、4不适用。119复用0调用37.815秒；605引用出现次逐字0失配，15旧审核hash保持；初始正式v5更新另核16旧审核、125物理事实、5原件版本保持。当前冻结事实122与物理行125不是一分母。不能把IN03新的满足计作已验正确。
- IN03第一因果错误是解释／条件层失去治疗与疗效的对应关系，非没有读到用药。D19提案保留类别OR、研究者疗效判断及筛选／基线资料要求，只细化疗效对象／期间／当前节点，原文、字典、阶段及其他63项不变。真实UI从正式v5创建新Job后经既有SOURCE_ERROR保存草稿2，结构publishable=true、无新增gate提示；没有收费模型、重读病例、批准、发布或签发。私有output/wp5_prepare_in03.py --save已执行，revision1前置保护禁止重放。
- 实际UI暴露连续复制只读直接基线EX06／09两事件，遗漏最早64项批准。protocol_rule_review逐层恢复真实冻结输入及已发布基线，按逐条内容相等继承，不反算历史；改源、改义、撤销与循环正反例经过发布消费者。服务和API已读回63/64、66原历史、有效审定均本人；缺证明不继承。逻辑树又因变量短名称覆盖新关系，ProtocolReviewLogic改优先完整中文条件、英文属性保留中文变量回退，未改条件或内容哈希。
- 集中相连363通过／5第三方警告／127.74秒exit0，output/wp5-in03-consumer-family-final.log；初轮新增5夹具导入模块错／100通过，保留失败。前端初轮844通过／1新增夹具漏label，纠正后845通过12.47秒，output/wp5-in03-frontend-full-final.log；正式构建exit0，旧chunk提醒。当前整库实际命令`.venv/bin/python -m pytest -q --junitxml=output/wp5-v23-full-backend.xml`，同版2114f55b，10372通过／249基线失败与错误／1921.10秒exit1；XML逐ID比较新增0／关闭0，output/wp5-v23-full-backend-delta.json。不是全库绿或医学通过。
- 最后只读保全证明output/wp5-in03-preservation-audit.json：准备前16旧审核hash均保持，125物理事实及5原件版本不变，63有效记录全部本人medical_manager、66原历史事件；没有新本人签名。第一次curl路径错误未落文件，按现行router正确/api/v2/protocol/deconstructions读回exit0；不将错误探针当产品证据。
- Ego42三宽屏1920×1080、2560×1440、3840×2160/DPR1截图wp5-in03-review-{1080,2k,4k}.png已看，无横溢、完整关系可读；是视口模拟，实际缩放未证。已交回用户控制，p1仅IN03待审，p2旧v23结果不改。前两次浏览器调用误用不存在的getByRole等API和相对截图路径失败，读取Skill后改用已有ref/CSS与绝对路径完成，不以失败视图当验收。

### 6.2 先前 WP4/5（v19–20历史）

- v19：6请求、5stop、1无终止／用量；3359.703秒，已报输入105859／输出148995，未知调用不补0。复用反证：预检113/122命中，执行新子集却使第二组0/16命中。停止请求在当前组及其局部修正保存后转cancelled，未强杀、未启动后4组。`output/wp5-population-runtime-audit.json`及原服务日志／ArtifactStore。
- v20：正式入口105cc590…，run38a323…，152条、122唯一关系／复用证明、0新请求、36.995329秒；重复POST同Job／同Run。15旧审核payload hash保持，事实及原件版本表保持；630引用出现次（含父子重复）逐字0失配。这只证明身份／文字／运行，不证明全部语义与时序。`output/wp5-v20-delivery-audit.json`、workbench.json、idempotent.json、before-v20.sqlite3。
- 父项6未触发／9证据不足／2触发／2系统问题／5入选满足／15未到期／21操作满足／4不适用。变动IN06不足→满足；EX10未触发→不足（缺随机日期不让模型代算）；EX06不足→触发（读取暴露规则误拆，**不是正确接受**）。EX09旧错误仍触发，等修订发布。
- 最终相连242通过29.26秒exit0：原消费者、适用组合／例外、时间、实际分组复用、跨规则相容、网关保活与身份；`output/wp5-final-source-scope-consumers.log`。中间179/138/181/222/225/231/241不归到最终快照。初次不存在路径exit4未跑；新增夹具缺effort／anchor_dates及错误hash helper已修，不放宽生产门槛或称旧失败；全库未跑。
- 共用上下文邻近回归60通过34.80秒exit0，`output/wp5-shared-context-adjacent.log`（检索／prepared-review陈旧性与更正服务），仅校验共享消费者，不恢复旧产品链。最终只读原工作稿仍current／同Run／64+88，工程字段解释已净化，NA来源不再显示成无依据；未新增读取或更改旧内容。
- 前端NA无置信仍显示已核来源，未知仍待核；单页28通过4.20秒，完整99文件840通过10.64秒，构建exit0；`output/wp5-population-source-ui-*`、`wp5-source-applicability-frontend-full.log`。新NA实屏未运行，Ego42用户控制；D18三宽屏属上一包，实际缩放未证。
- EX06提案只撤误拆引导段及附属要求／阶段ID，其他条目内容哈希不变，EX09本人内容／审定有效。API63/64，仅EX06待审；`output/wp5-ex06-proposal-{preflight,save}.json`、review-readback.json。私有脚本`wp5_prepare_ex06.py --save`已执行，禁止重复（revision2前置保护）。publishable仅结构门槛，未批准、发布或启用。
- 新规则复用先核同原件／患者／节点／资料／字典／真实访视，旧请求对旧冻结规则整组核验后，仅取当前语义及来源完全相同的原子；删／改一项不让未改兄弟重读。共享纯来源相容函数，但不伪造抽取成功状态／资格。正反例已运行，跨版真实运行待本人发布；缓存不是新规则批准。

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

1. 当前Job05641a…草稿2仅IN03待本人审定发布，其余63有效，已一次通知并交还Ego42；勿重审或代签。真正发布后核新规则，按现有入口生成新版工作稿；旧正式v5及所有终态不重跑。先核原件／字典／访视及真正改变的关系，仅新目标和依赖读取，不机械重读整例。
2. ANC筛选p3原图3.01行单位被便签遮挡、OCR误作%；不能由其他行猜单位或拿基线后值充筛选。FEV1 p5有表格数值，但未明示舒张剂前；不能由“肺功能正常”推pre-BD。保留精确原因，后续有源更正/补证/合法局部取证，不重读整例。
3. v23的8未决和2系统父项逐条核：EX06/10缺实际随机日期、EX07/13受限解释、EX08 FEV1关系、EX09 ANC单位及未明HBV/其他判断、EX14/REQ32女性范围、EX15周饮酒量、REQ25环境记录。IN03旧满足另为已知关联错误，不能用节点后背景治疗和后续确认反推当时合格；D19修订后从完整条件核。EX03/12已有逻辑消费改善，仍逐条核真实意义，不以未决减少宣称临床准确。
4. 已提前接WP5必要病历消费；其范围／药物清单完整能力仍未全部交付。旧Profile保留；本轮source_read_refs不伪造ClinicalFact、不重新生成Profile，不把病历中未来计划当已完成动作。
5. v17–v23均终态，v21坏稿也保留，不再轮询或重跑；当前全库测试87584已收回exit1、249失败/错误ID与基线一致，不再轮询。没有新假设不重开模型分支。零调用是复用真实返回，不是模型提速；思考／费用缺报保持未知。来源、身份、软件回归与真正医学歧义分层，不把这些都改成患者需补证。

### EX09提案、审定继承与实际验证

以下63/64是准备时的历史，当前已本人64/64审定，见§2。

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

### D18 阅读优化（本轮）

首错在显示消费者的信息组织，不是字体不够小：父规则理由拼成一段、置信原因在多个位置重复、同一来源在审定／差异／手工预览反复铺开、常规OR机械套泛化疑点、长研究名称及等权三栏挤占阅读区。把更多内部信息直接展示并未增加可审阅性，反而让真正限定语与行动淹没。

已实现：判定理由保持原字按中文句界分点，已有项目标签加粗；低置信只留标记；备选A/B/C分列，标当前解释／有源推荐、说清“全部”与“任一”的命中差异；实际条件树和子项组合优先，长分析／阶段资料／来源／历史下钻。同位置来源精确展示去重，不同页／结构单元／坐标／快照保留；当前摘录与其他依据分开。项目用代号，三栏中间扩大，列表可收起并保持当前对象及来源。实屏又发现备选多子项一次铺开导致重复分析、全局reset隐藏分点、定位按钮被误认为返回依据；最小补丁分别使用子项details默认仅首组展开、显式list-style、分清“定位当前查看页”与“返回本条依据页”。未改规则、事实、原件、模型、数据库或旧结果；0模型调用。

验证分版本：dba677d2完整前端99文件838通过34.85秒、最后跨文件保护27通过；本次多子项展开反例加入后99文件839通过10.38秒exit0，最后导航措辞39通过3.85秒exit0，正式TS/Vite构建exit0，旧大chunk提醒保留。保留原树方向、逐字数值否定、跨页／版本来源、列表恢复和错误身份保护，不删测追绿。日志output/wp6-browser-followup-tests.log、wp6-browser-navigation-tests.log、wp6-browser-followup-build.log；初次命令含两个不存在的过滤路径只运行6项，未冒充三组通过；最终集中和导航窗口使用真实文件。

Ego42现已实际操作：1920×1080／2560×1440／3840×2160，DPR1的视口模拟均无水平溢出，原件图已解码；三组截图wp6-{review,options,workbench}-final-{1080,2k,4k}.png及源码hash／几何回执wp6-browser-followup-viewports.json。手工预览正确EX09b、只读2份不同摘录／0精确重复，取消未写。收起／恢复列表仍IN04与病历第6页；切换到另文件后旧摘录隐藏，点击真正“返回本条依据页”恢复。最初脚本滚动把summary放到固定页头后，调整取景完成，非业务失败；缩放快捷键未改变viewport/DPR，**实际浏览器缩放未验证**，不能将CDP视口模拟称缩放通过。

只读API复核64/64、all_reviewed=true；本稿API65条历史、全部有效记录ID／内容绑定及历史数与D18前相同（全库259事件是另一分母），output/wp6-browser-review-state.json。草稿仍saved未发布，旧正式v4及工作稿v18不改。output/data_v2及截图仅受控本机，不提交临床全文；外部审阅凭本机路径不可取得。已将p1 EX09审定和p2 IN04原件保留交还用户，未重跑方案／建议／OCR／病历、未替本人批准发布；M1仍未验收。

进步是数据到可解释结果和用户可修改，不是新增调用次数。首错集中在表示/作用域/消费者：单位格式误拒、同义假冲突、局部“或”泄漏、对话框错目标；应先离线修相连链，不能每次整方案长读。

低把握可能是复杂逻辑、尚未实现、来源不足或真正医学裁量。应解释并提供有据方向，不为凑三个选项编造临床规则、虚报概率或强推推荐。当前备选来自已存原文和结构，不是新模型医学金标。

本人审定发布已完成，但“保存一份大量未决稿”不等于医学经理能用上。前轮将关键判断消费排在M1之后，是验收顺序与真实用户需求不匹配；空semantic步骤更使技术性闭环遮住临床功能未接。当前提前补齐必要消费、保持数值与出处边界；完成新稿后再逐条解释剩余未决属于资料、含义、程序还是模型。不得为制造改善放宽事实真实性，也不把没有更强模型当盲重试理由。
