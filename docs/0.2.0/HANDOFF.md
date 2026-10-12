# 0.2.0 当前交接

更新时间：2026-10-12，本次恢复后的功能包收口。**Goal active，未暂停；WP3/WP4进行中，M1未通过。** 唯一计划03_PLAN，唯一进度05_PROGRESS；本文替换旧暂停现场，历史留Git，不覆盖旧回执，不是新执行包。

## 1. 五分钟接手

- 工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0`，分支dev/0.2.0。
- 本轮接手HEAD17ecbf58b4ef22adabd6230125462b5b68f08c71，clean；前序25ebd0f9/b0afe94c已推送。本轮WP3提交1ad63f94；审定及记录以包含本文件的随后WP1提交与现场HEAD为准，不reset/clean。
- 用户要求：局部检验到工作稿；核IN-02；低把握原因、备选解释/有据推荐及手工调整；不重跑方案/变量建议；集中验证至M1。
- 生化第8页新增1次真实产品调用，9事实保存并进入Profile及v11工作稿。局部run partial，累计24页成功证明继续使用，不叫整例完整。
- IN-02外层修成ALL，内部观察ANY保持；只改该条组合/误导标题，不改原文、谓词、绑定、兄弟。本人审定稿rev2，4/64本人记录保留，未批准/发布。
- 审定页原因→分析→备选方向→目标手工预览已接通；无充分依据不推荐，不造准确率，预览不是保存/批准。
- M1必须用户本人正式审定与验收；构建者不能代签。A/B前次已各一次，不重派或声称v11再次独立通过。

## 2. 运行现场

| 项目 | 当前事实 |
|---|---|
| 自有服务 | 61134，PID38329，exec session17708，v20；`./run.sh --data-dir <本树>/data_v2 --port 61134 --no-browser`；显式本树.env；output/wp3-wp4-product-server-v20.log |
| 已停止服务 | v17–19自有服务已停止、终态已收回；v19 session68060 exit143；共享服务不动 |
| 数据库 | 本树data_v2/enrollment-review-v2.sqlite3；只读核21completed/139failed_final/2cancelled/3waiting_user，0活动/租约；旧终态不改 |
| 浏览器 | 原Ego空间23保留用户控制，不接管；本轮空间42“0.2.0 审定备选与检验衔接验收”，p1审定/p2工作稿；交回动作看实际SDK回执 |
| 审定入口 | http://127.0.0.1:61134/#/protocols?job=fb814eb3b657424aa4c4c340e710394b |

恢复核实际进程/端口/数据归属；在运行则复用，不因宿主会话变化重启已终态模型作业。

## 3. 现行边界

读本树AGENTS与docs/0.2.0/01–06相关章，archives仅按07索引找必要历史。单一构建者，不新建Trellis任务、框架、队列、模型榜单、规则真相库。旧跨章、prepared-review、全页固定双读及方法采用链不调用、不修补、不删除。

原方案/病例/人工IE/旧事实/报告不覆盖；真实追加仅本树验证副本。不提交data_v2、.env、原件、临床模型原答；output是受控本机材料，外部审阅仅凭路径不可取得。人工IE不入提示，D001在M3前保持留出。

不重跑完成的方案解构、变量建议、验证发布、24页成功证明、已终态生化局部调用。正式规则发布后先核输入/变量/来源相容，不能为换规则机械重读整24页。

## 4. 用户流程与身份

| 节点 | 已联通 | 未完成 |
|---|---|---|
| 规则 | 64项分类/重点/条件树/原文/多选；备选分析与目标手工编辑；IN02rev2保存/读回/校验 | 本人4/64，完整正式审定及verification_only=false发布 |
| 资料 | 5文件24页累计账本；9新事实/原值/单位/范围/采样日；Profile rev6 | 筛选ANC单位遮挡、FEV1用药前关系及部分操作事实 |
| 工作稿 | v11保存，64父+88子=152行；17确定低置信、24未到期、53未定、58系统行/49独立问题 | M1未通过；17含父子重复，不是17独立要求；WP5能力未接 |
| 原件 | 17确定行逐字同文档0失配；四原值/上限另看原图；正确第8页和三个宽屏截图 | 尚无准确区域坐标，不造红框；不是整例医学验收 |
| 闭环 | 旧版/原件hash保留 | WP5–8、M2/M3、IE、更正补证及D001未执行 |

项目draft-project-1153e25b4eba；方案draft-version-1153e25b4eba；原草稿rev21保留。验证RuleSet revision3/verification_only=true：23 IN/EX、88组件、41REQ、141绑定、197变量、402资料要求。

本人稿Job fb814eb3b657424aa4c4c340e710394b，revision2/waiting_user/无租约；4本人记录及历史保留。publishable=true只说明可审定，不是已批准；人群/节点等提醒仍显示。

31001中心31，subject58ff71df0cff4a2c9107be743d82584b；筛选episode b843b2c07d6d4318a6df741eb7902eb3/anchor2025-08-08/节点rev4；基线e66f903e08cb4d02a50c9162cfb6c4b4，不拿后续值判筛选。snapshot c69c297a3ea84c57a8fa953e07567b1d；complete-ad2f258d2aff46a98affc99dfac3ea78。

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
- 最新v11：Jobaf80a06feaa04ca1885e8f62b07b6f12 completed4/4，run **review-run:784153c882304c588691302b62d9b212**，supersedes v10 review-run:5c2cc2a7856543a081c0af6a4485d76c；v9/v10/v11保留，API current。
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
| 前次完整后端 | **旧59bbca86**：10192通过/243失败/6errors，249失败ID与WP0相同；**本轮未重跑全库**，不能归到新源码 | output/wp4-m1-reviewed-backend-delta.json及原XML/日志 |

所有output/data_v2是本机受控材料，外部审阅仅凭路径不可获得，未提交临床原答。失败保留：最初测试路径不存在exit4；一次未改文件250项列表5秒超时，单独/限制workers全量通过，未放宽；数据库忙503未入队，终态后成功；首次IN02锁失败未改rev，随后仅成功一次。截屏空间隐藏超时，打开**原空间42缩略图**后成功，不另建空间、不接管23。

## 7. 模型及历史账本

- 产品路由未换：方案/变量OmniRouter cms-router/glm-5.3-flash high；资料ollama-cloud/deepseek-v4.1-flash high，65536；产品harness直连，不用个人CLI读病例。
- 本轮生化1实际请求，127.278秒stop；input37793/completion46160/total83953/cache0。receipt在raw_response，非evaluation_manifest；实际汇总output/wp3/reference-model-receipts.json。
- 52旧+1=53，已报3563.660+127.278=3690.938秒；3次历史usage未知保持未知。job数不是模型请求数。
- A codebuddy/hy4-preview/high，B grok-4.7/high前次各一次完成；只读/独立性限制保留，B审v7、owner修v8；不是本轮v11独立验收。output/m1-review/completed/不覆盖、不重派。
- 旧报告review-run:cba4a3598df742a9b4d1404f0d7ce324 hash17dec1cc14dc4ee109a8997b51aadb982e91db7d907768ca2ec6916817605844；review-run:88a8316e131041198e9a4ade3dff1144 hash47d76d3329eaa75c33c27e5cf54593857daaf1327fc992d04713b849b939c06d，本轮再次核不变。读取ID须保留review-run前缀。

## 8. 接续

1. 请用户在当前rev2核IN02是否需额外研究者判断及其他重点项，完成64项并正式发布。不能代签、把publishable当RuleSet或改写4条本人历史。
2. ANC筛选p3原图3.01行单位被便签遮挡、OCR误作%；不能由其他行猜单位或拿基线后值充筛选。FEV1 p5有表格数值，但未明示舒张剂前；不能由“肺功能正常”推pre-BD。保留精确原因，后续有源更正/补证/合法局部取证，不重读整例。
3. 当前工作稿仍用验证v3，不等于本人rev2修订稿；本人发布后核变量/来源/节点相容，复用合法资料生成新稿，旧版保留。
4. M1正式审定、完整确定性自查及新源码全量回归未通过；不能用通过总数代替。语义/用药/判断按WP5顺序，不因软件未接入断言患者缺材料。

## 9. 复盘

进步是数据到可解释结果和用户可修改，不是新增调用次数。首错集中在表示/作用域/消费者：单位格式误拒、同义假冲突、局部“或”泄漏、对话框错目标；应先离线修相连链，不能每次整方案长读。

低把握可能是复杂逻辑、尚未实现、来源不足或真正医学裁量。应解释并提供有据方向，不为凑三个选项编造临床规则、虚报概率或强推推荐。当前备选来自已存原文和结构，不是新模型医学金标。

下一步仍是本人审定后同源工作稿和精确缺口，不扩框架/读道、不写病例特例。Goal active；记录保全不构成暂停或交付完成。
