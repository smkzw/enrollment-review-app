# Enrollment Review App Project Context

## 当前产品摘要（2026-09-10，以本节和活动检查点为准）

- 用户最新要求完成手头工作后无损暂停并交接另一Agent；本产品线程已收尾，未经新继续指令不恢复。主入口为 `.trellis/tasks/09-05-phase55-dual-vlm-page-review/HANDOFF_20260910_PRODUCT_PAUSED_AGENT_TAKEOVER.md`，含完整决策沿革、接线现状、停滞复盘、代码/证据地址和恢复计划。另一线程本地横评不受本次暂停影响。
- 判断检索single-v4/batch-v1、当前来源/目标绑定、既有工件库存取和两页两目标隔离批次完成；130项相关回归通过/12.42秒。尚未接正式持久任务、缺口生产者和UI。批次减少调用数，未证明整链提速；手写分歧及未测页保留，不认定缺判断或符合。接任先纵向接线，不再新增一轮叶子合同。仅GLM low/Gemini high产品自有HTTP/OAuth，旧goal的MTPLX文字已失效。
- 最新全V2仍为4453通过/1失败/3跳过；该并发测试假设已修，单文件30通过，未做修复后全量零失败复跑。下文各历史测试数不得相加或覆盖此限制。Phase5/5.5未收口，claims_complete=false。
- runtime05完成15/15但实际运行partial：37事实、5事件、0用药暴露、54待处理项，不等于临床收口。原finalize约56分钟；保存点、前后代次、跨调用集合问题已修，限定视觉批量经两轮独立审阅和源hash等价检查：8定位25.860秒降至3.279秒，仅该段约7.9倍，非整例速度。原数据库和失败记录保持不变。
- 用户批准用药分项隔离扩测而非正式接入。当前v5.1：用途区分已阻止两条明确未用药病史混入用药时间；HR不展开药名但保留治疗中。定向原图复核比宽泛重读更能解决相邻病史归属，仍存在剂量粒度、未知日期精度标签分歧。GLM high单因素小样纠正每喷含量误作每次用量，成本上升，不能据两对改变产品默认档位。59项分项测试及7项诊断入口通过；新增真实结果在artifacts/phase55-takeover/20260910。尚无独立留出集通过证据，不接正式病史、不继续机械叠加提示；保持product_acceptance=false、claims_complete=false。全V2 4318通过/2旧合同失败/3跳过，旧额度断言及四份GapType schema已同步，相关70项复跑通过。
- 24页GLM/Gemini双读已完成；runtime03整理作业e5c3b71…为failed_retryable、9/15步骤，第10步断流，没有完成病史发布。四次成功调用约34分钟、约83%输出token用于思考；不能归因为多次格式修复。
- 视觉原件摘录已接入来源、候选、存储、发布和Profile读取的合成整链，不重写旧文字处理修订，不伪造坐标。原件临床QC及真实浏览器整链尚未完成。
- 待核对原文保全v2已接；计数化模型视图和调用内短引用仍仅隔离验证。稀疏页改善，密集页仍约10分钟，输出日期关联/要求绑定需继续核对。已核实观察专用提示与同范围格式修复正在实际验证，不按候选数量冒称质量等价。
- 已修复混合来源将检验结果当研究者判断的问题，并禁止文件类别单独证明判断。报告批注/对应节点病历分析的类型化正向证据及适用性仍缺；当前缺口明确为“尚无已核实…”，不是断言原件不存在，不要求用户确认才能继续。
- 最新测量、限制和审阅修正见 `artifacts/phase55-takeover/20260909/NORMALIZER_SCOPE_FINDINGS.md`。完整V2回归已结束4227通过/3项真实服务跳过（早于本轮增量）；verified-v1密集组445.767秒，仍非临床通过。C03及同会话实施复查均已完成；“资料尚待核实”不再误称判断缺失，弱覆盖及已核实事实保留的反例通过。书面判断正向证据及充分覆盖后的缺失证明仍待接线。
- 实际手写辅助复核5121562951df4703bd1bd09515894b8a已由产品GLM/Gemini high完成两轮，仍为SS/CS分歧且归属未核实，不自动采信、不宣称缺少判断。原件为筛选报告第1页、全局队列索引10；新脚本可核对图像哈希，防止混淆文件页码与队列索引。证据在targeted-handwriting-report-page1-v3.json。两轮摘录、原图加载、缩放和滚动已在Chrome 1080P/2K/4K核验，无横向溢出；未绘制未经核实的红框，不代表整例浏览器验收。定向任务19项、前端24项及harness/传输97项聚焦回归通过，范围不累加。
- Phase5/5.5均未临床收口，claims_complete=false。下一步先核实提示回放质量与日期传播、补书面判断证据和条款分歧闭合，再经正式隔离入口完成事实/事件/用药/Profile核查；按恢复计划E/F条件验收，不提前进入Phase6。

以下为按当时状态保留的历史，不覆盖上述当前摘要。

## 2026-09-08 最新连续执行与模型变更

最新实际终态：7d31fb6…第二次正式尝试已failed_final/3 of15，无产品模型作业在跑。页3-4已完成但只有保真登记号1候选、17待核对项（包含原三项检验结果），不称临床收口；页5-6又因影像报告摘录不与文字定位完全一致而失败。完整V2回归4133通过/4失败/3跳过；4失败为格式修复增加调用后旧计数断言，已修断言并复跑相关8项通过；来源反馈115项通过。C03 source-authority-followup 已结束并撤回“OCR逐字一致必需”的假设。E03 r3-visual-source-contract-20260909 已完成同会话实现与修复，实际 GLM-5.3-Flash/max，无替代路线；新增独立视觉来源合同，暂未接正式写入。所有者修正来源配对：既有精确位置算法直接返回观察对，保留旧键集合API，避免重复数值跨位置配错；相关67项实跑通过。下一步审阅新合同与正式持久化/发布/回放/原件展示接线，禁止用图像哈希冒充文字哈希或以新处理修订制造覆盖循环。主读仍GLM/Gemini，claims_complete=false，非暂停。

2026-09-09 当前产品状态（覆盖下文旧运行状态）：旧整理任务4bc1c6a46e3f41e28a120996345e11a1已failed_final，完成2/15步骤；流式取得完整回复，但第三组的数字登记号被代码转成数值并触发缺单位错误。C03独立工程审阅发现v21编号标签可绕过测量单位校验；现已补草稿、候选持久合同和门禁的共同编号检查，保留前导零并拒绝小数/指数及原句紧随单位的数字误标，289项回归通过。整数且原句无单位时仍不能仅凭格式证明其是编号，需来源与临床QC，不宣称全面语义保证。正式新整理任务7d31fb6cad90410b868f518597bd3d20已201建立并运行，使用v21、GLM high/65536与已完成24页双读；旧任务未跨提示版本恢复。证据及源码哈希在runtime-02/normalization-v21-attempt.json。当前不是暂停，claims_complete=false。

当前构建组合为 GLM-5.3-Flash low 与 Gemini-3.7-Flash high，详细横评后置至系统构建完成。Gemini OAuth 凭据已按授权一次性迁入显式产品环境，原生 HTTP/刷新由产品自身实现，不调用 OMP 等个人 harness、不在运行时读取个人配置。真实视觉调用确认逻辑 gemini-3.7-flash/high 对应供应方请求 gemini-3.7-flash-high，实际响应模型 gemini-3.7-flash。两模型均承担普通事实及手写判读，不设第三读。

2026-09-09：隔离 runtime-02 的24页正式双读完成，格式和页覆盖通过；格式修复仅允许同模型带原图重答一次，不能由代码删字段或补临床事实。正式整理作业 4bc1c6a46e3f41e28a120996345e11a1 第一组完成、第二组两次600秒超时。已修试运行脚本失败后空等、正式 retry 对开放运行的衔接，并接正式取消/失败回调，不直接改库。E03 有限执行新增 GLM 流式接收，主线程补连接释放和实际模型身份校验；184项相关测试通过，最小真实GLM high调用13.23秒、stop、思考172/总输出183 tokens。当前76039使用相同冻结资料/提示/模型，经正式retry进行流式尝试；只改变传输接收方式，不降低核实要求。流式最多1200秒块间检查，单次阻塞仍有600秒超时，实际总时间可多一个阻塞窗口。传输源码SHA256=07998f33961f386db4ed6d51ce51d5cd366504538734ce181456eeba45d53b4e，不把原冻结源码快照冒充新尝试。此处仍不代表事实完整性或临床正确性通过，claims_complete=false。下文旧模型和暂停安排仅为历史，不驱动当前构建。

用户已恢复执行并更新goal：GLM-5.3-Flash low + MTPLX mtplx-flash-next-optimized-speed作为两个完整主读，MTPLX不再是手写第三读；旧MLX任务/原始资料保留，不跨模型续跑。恢复接口、前端继续判读与取消传播已实现针对性测试，Chrome三档9项通过；真实新组合、规范化和原件QC尚未完成，claims_complete=false。8002在线但刚才存在共享请求，未提交新病例；当前无暂停授权，下方暂停段落仅历史。最新细节统一见活动任务CHECKPOINT_20260908_MODEL_BENCHMARK_PAUSED.md文头，后续从原完成来源新建隔离正式尝试。

## 2026-09-08 当前用户暂停（覆盖下文状态）

已按“无损暂停”停止本次执行。模型覆盖身份v8及正式整理选择、本地凭据隔离、只读错误处理、测试65,536额度/路线冻结检查已实现并通过针对性回归，扩大API349项通过；独立工程复查结束。新隔离作业c52611642d48418f8cf793e380d4a8e5已发正式取消请求；执行进程13198随后按暂停要求结束，2项主读完成、2项未提交本地读取、69项未启动，数据库仍cancel_requested，禁止伪称已终态或临床完成。完整恢复清单、快照哈希与唯一入口见活动任务CHECKPOINT_20260908_MODEL_BENCHMARK_PAUSED.md文头。新运行目录artifacts/phase55-model-comparison/20260907/product-runtime-v8-20260908；未运行规范化，claims_complete=false。共享模型服务未停止，恢复先核对在途请求与租约，当前不再自动执行。

## 2026-09-08 横评与已批准处理方式

当前有效覆盖：用户已要求先补正式产品环节，再全链横评；goal主读改为GLM low + mlx-serve指定ddalcu Flash-Next。新配置/本地串行/凭据隔离/就绪视觉声明检查已实现，82、45、23、66项各自回归通过（重叠不相加）。产品文本直连68814已终态stop且模型ID匹配，非视觉验收；共享服务忙导致耗时不可比。无已核实内容不整理病史的完整V2回归78085已结束4005通过/3跳过；其后新接线完整回归94589运行中。隔离正式入口增加--normalize及源码/计划冻结，5项入口边界测试通过；24页新尝试尚未提交，等待共享本地服务空闲且回归结束。不修改历史作业/原始病例，不声明claims_complete=true。下段及历史记录中的运行状态与默认模型以本段为准。

有效恢复入口是活动任务CHECKPOINT_20260908_MODEL_BENCHMARK_PAUSED.md文头，历史“暂停/待确认”不覆盖后续授权。辅助对应仍只做隔离评测：低档真实远端组合三次误把相邻定量限配到结果，高档两次正确但增时，尚未批准产品化；九份结果统一评分另存alignment-source-field-summary-v2-20260908.json，不用字段对应分数冒充临床召回。已落实2026-09-07批准的无已核实内容不调用整理模型：新R3作业冻结preserve-pending/v1及新幂等身份，保留逐页说明、无病史候选，检查点注明没有模型调用，历史作业行为保持。76项相关测试通过；真实冻结14组中6组适用，全部只读验证且库哈希不变。全V2回归session78085仍在运行；没有新模型调用，没有改正式病例、默认读道或claims_complete。详细接入发现见artifacts/phase55-model-comparison/20260907/harness-findings.md第48–51项。

## 2026-09-06 连续实施进展（非暂停）

- 2026-09-07最新用户批准：内容尚未核实清楚，先不整理成正式病史；原件、不同读数和疑问完整保留并继续核对，不跳过审核、不判为符合。允许落实此前零已采信观察组不调用规范化模型的方案，但须保留真实处理状态、来源与待核实事项，不伪造模型调用或已完成记录。仅记录批准，尚未宣称实现或测试完成。双方确认缺少研究者书面判断时直接报告无法判断及具体缺口，无需用户重复确认。此批准覆盖此前“该提议待确认”的历史状态。

- 2026-09-07用户授权新增鉴权排查：本次直接执行，因同一请求、同一原图下比较三组凭据属于客观诊断且涉及共享密钥，不另派会商。只读取得OMP cms-smk节点https://new-api.mediportal.com.cn/v1与OmniRoute绑定该节点的3组凭据；仅内存解密，产品direct_openai_completion直接调用cms-model/high/4000，无外部harness推理、无网关或产品默认配置变更。三组均成功stop，返回model=MiniMax-M3，耗时10.409/16.216/14.168秒；同一SHA5245d99c…原图为河北省中医院血常规，三次分别误写东方医院心电图、中南医院心电图、武汉市第三医院体检。回执在artifacts/phase55-takeover/20260907/cms-model-auth-check-01/credential-{1,2,3}.json，无密钥、无正式事实写入。因此排除本次三组凭据无法鉴权，不证明上游真实权重或具体视觉故障原因；不能宣称更换标识已修复。已用非工程化语言解释“无确认内容时暂不生成正式病史”的提议，未擅自实施跳过规范化。历史受阻记录保留，本次授权已实际执行。

- 2026-09-07受阻审计：同一MiniMax视觉质量/端点问题已在首次明确报告及后续两次目标续轮持续存在；本轮只读核对header-diagnostic-01回执与隔离库，活动作业0、Normalizer失败无租约。产品侧来源/恢复/SDK传输防线和隔离诊断已完成，不能用更多同例重试、放宽采信或跳过Phase5验收代替解决路线问题。等待端点修复信息或用户授权替代路线；另有零已采信组无模型处理方案待确认。目标标记受阻而非完成，完整范围不变。恢复先核对最新用户指令及显式env，再做非敏感视觉验证和隔离原页验证，禁止自动重启历史失败任务。

- 2026-09-07追加最小原图诊断header-diagnostic-01：同图SHA5245d99c…、不提供条款或正确答案，仅抄医院/科室/项目。两主读high各一次4000预算，GLM stop/80.19秒抄出河北省中医院/耳鼻喉科/血常规（不称全文精确）；MiniMax stop/19.82秒却写北京东直门医院/超声科/妇科超声等另一报告内容。证实短提示亦复现，不可只归因于长提示；不能据此定位上游内部原因。产品direct_openai_completion原样传messages，新增实际SDK序列化HTTP请求体测试验证图像字节不替换、无temperature。该路线真实视觉质量未满足验收，不盲目继续病例调用，不擅自换模型或端点。完整诊断输出仅在隔离artifacts，未写事实。需用户/供应方核查cms-smk视觉路线或授权替代端点后重验；Normalizer无模型处理提议仍未获答复。

- 已在用户批准的隔离观察配对评测范围运行真实误读页：alignment-rotated-page-01/page-9.json，明确coverage07a504…第9项，产品direct API GLM返回stop，19.43秒，25组提议；确定性校验全部未通过，其中23组对象未核实、23组时间未明、22组值/单位分歧、4组字段不符、2组缺context（可重叠计数）。存在性别→年龄错误配对，不把25组称正确关联或召回。无事实/覆盖写入，product_acceptance=false，不接入自动配对，不放宽检查。下一步仍需原页定向纠偏与关联契约评估，不能用仅减少Normalizer调用掩盖主读质量问题。

- 原页QC新增实证：Normalizer首组对应logical_document3de286…，不是页任务数组第0项，而是第9项旋转血常规页。图像SHA5245d99c…已直接查看：河北省中医院、耳鼻喉科、血常规；main-B记录44ac049c…却含潍坊市中医院/风湿病门诊/红斑狼疮检查等不符文字。其实际请求工件d81cc55b…引用同一图像SHA，说明本地请求绑定一致，但尚不能区分模型误读与上游内部处理错误。main-A记录730ecf47…同页。未更改原图/旧读数，不以Codex读图代填产品事实。尝试正式辅助复核入口第9页返回409，未启动模型；代码入口只允许explicit_conflict_fields找到的同字段冲突，字段对应关系不同导致这类错误不能进入现有两轮复核。这属于真实覆盖不足，不能将409称临床正常。新增run_targeted_page_review.py仅通过正式API提交隔离指定页，201以外不执行历史作业；本次未生成运行receipt。下一步应在已批准的隔离关联小样范围验证原文对象对应与原页定向复核，不擅自接入产品自动配对或自动改写事实。

- 用户尚未答复无已采信观察组的无模型处理提议，未实施该契约变更。本轮继续补查相邻恢复路径并修复：有检查点和仅持久结果两条恢复入口均以冻结coverage重建输入，复验候选来源；旧非R3任务不静默挂新coverage。逻辑独立放fact_normalization_replay_sources.py，合法复用不增加调用，拒绝时不改已有候选。14项相邻测试、66项持久化/API回归通过，追加两种恢复方式×合法/拒绝故障注入4项通过，证实拒绝时模型调用仍仅首次1次、原候选保持单份。目标与临床验收仍未完成，失败Normalizer不盲目重启。

- 离线审计normalizer-source-audit.json已按只读库重建14个冻结调用：6组无任何已采信观察，但仍携带待核对资料；压缩后输入仍约3.18万至13.31万字符。唯一旧候选通过新增来源引用校验，不等于临床正确。113项本批回归通过，git diff --check通过。拟将待核对项直接按来源保存（不合并、不判断），零已采信组不发Normalizer请求并明确记录未调用模型；该项涉及新增无模型审计契约，尚未实施，不以改变旧检查点方式伪装恢复。旧失败作业不自动重跑，无运行中的本批命令。

- 24页覆盖后的正式Normalizer作业7c81237d1a24462f91223b36ca0960e9（run19f9582990b44400b6a8ecce2e23960a）在第4组600秒客户端超时，failed_retryable；前3组仅0/1/0候选、10/11/12未解决项。GLM high三次16384截断中报告思考16346/16336/16334 tokens，翻倍后第4组超时；不盲目续跑、不改历史结果。选择一次只读工程会商，因真实溯源和输入精简存在实质解释风险，r3-normalizer-input-review-20260906以ZCode/GLM-5.3-Flash:max完成，无fallback，仅代码与汇总证据，不处理病例。确认真实Runner遗漏已采信观察来源校验：现与结构化路径共用后解析校验，空/伪造/待核对refs在有界修复耗尽后拒绝，合法来源可修复通过。基础101项回归通过，新增正向修复与输入测试100项通过。待核对投影仅移除派生规范值/几何重复，保留原文、上下文、原因和来源；尚未实施会商建议的系统派生缺口或跳过模型调用，避免未经验证改变持久化审计。下一动作是离线重建当前冻结输入并审核旧候选来源及输入体积，再决定合法新运行；claims_complete=false，临床QC未完成。

- 用户明确接受思考与正文共享48000额度。正式API增加single_length_recovery受限选项：只接受单一length失败读道，冻结48000共享预算、禁止翻倍/端点fallback/额外步骤重试，完成后禁止再开例外后继；成功记录原样复用，非截断或多读道失败拒绝。87项相关回归通过，补状态检查4项通过。真实隔离作业a317e5a3ef3f4e50b123cfa1fa78b969完成，覆盖subject-page-coverage:07a5041c131a95fd1fb7ca66fccd85d4，24/24页ready；47份复用主读检查点逐值不变。仅read:17:main-B一次48000调用，MiniMax-M3/stop/132.503秒，正文27414字符、思考29092字符；网关completion_tokens19329但reasoning_tokens仍0，不能推出分项token。原响应35e0a6ca…、请求1d72ed14…和length-recovery-48000.json留存。预算阻塞已解除，继续正式HTTP事实规范化；临床QC未通过，claims_complete=false，不将24页ready称为临床采信完成。

- 预算兼容决策待答期间继续完成一个已证实的前端缺陷：完成判读后原hook删除唯一任务指针，刷新丢失原件复核入口。现将待恢复与最近完成指针分开，按受试者+节点隔离；完成指针须GET核验ready，仅展示历史入口，不触发Normalizer回调、不新建任务。资料页与个例页接入“查看最近一次资料判读”。本批直接执行，因为同一hook及两个消费者共享状态，确定性测试可验证、不涉及临床采信。13项前端回归通过，tsc通过，Chrome1080P/2K/4K刷新到原任务再到辅助复核3项通过，截图completed-review-*与targeted-review-*；不是临床验收。此入口不是完整服务端历史列表，清除本机缓存后历史发现仍待补齐。未进行新的临床模型调用，claims_complete=false。

- 用户已批准单失败读道48000补读，并提出思考不额外设限、正文限48000；不再沿用“尚未批准补读”的旧表述。本批直接检查预算语义，因属于可通过接口资料和最小调用验证的传输问题，不新增会商节点。MiniMax官方OpenAI文档将reasoning_split定义为返回格式开关，未给出独立正文预算参数（https://platform.minimax.io/docs/api-reference/text-openai-api）；现用cms-smk最小合成请求（无病例）实际返回MiniMax-M3/stop，正文14字符、reasoning_content90字符，但completion_tokens35/reasoning_tokens0/output_tokens0，证实零推理计数不可靠。请求max_tokens512仅为接口探针，不是临床补读。产品回执已增加正文/思考字符数，缺失记null，保留原usage不推算正文token、不修改事实/旧记录；75项harness/执行器测试通过。尚不能把max_tokens48000称为“正文独立48000且思考不受限”，未发临床补读；当前需要明确共享额度的兼容行为，不能用reasoning_split冒充预算分离。

- 最近日志：合法后继7ee02a10b5294e0cae40a1a2b98e95cb已完成，覆盖subject-page-coverage:04ac4edf32626b58693a6ac089a0fb1b，23/24页读完、47份成功主读保留；仅第17号条目main-B仍length，12000→24000第二次仍截断（末次16434字符）。不再原样第三次尝试。拟请求用户批准仅此失败读道一次48000上限补读，保留成功来源和精确配置、禁止继续翻倍；这是读取恢复的预算例外，不是第三轮事实冲突复核。未实施该例外，未改模型强度；事实规范化/QC和手写缺口仍未收口，claims_complete=false。会商r3-output-failure-review-20260906已评估，采用局部恢复，未采用自动布尔翻转或输出内容修补。

- 当前正式来源运行：runtime-02的2c7da09f在模型调用前因隔离脚本漏复制artifacts失败，证据保留；脚本已补复制并在提交前核验每张页图，故障注入1项通过。runtime-03合法新作业4d8d8ea91e014a00af8dd5b3d1a5bd5a完成但仅16/24页accepted、8页failed；A24次stop总877.97秒，B32次含10length总4385.814秒。失败原响应离线复验见schema-failure-replay.json：未知条款ID、null对象、缺bbox.y1、无相关却输出事实；schema-failure-audit.json是首次诊断脚本漏usage的工具错误，不是模型错误证据。不盲目再读，选择r3-output-failure-review-20260906只读工程会商，审查结构约束/受限恢复边界；产品模型调用与会商严格分离。claims_complete=false。
- 空白对象反例证实正式来源匹配和辅助比较存在误一致风险，已只在对账侧拒绝空白对象，包含手写；历史模型不改写，对账版本升r3-v11，页合同仍v6/main提示v11。77项相关回归及36项历史/规范化边界检查通过（部分重叠）。

- 对应关系隔离反例补测：02批原提示漏配值/单位冲突且误配缺对象/日期；03批澄清目标对应不等于数值一致后10例9例正确、3正确配对/1错误/0漏配，仍有缺对象误配。未接入产品，未继续刷提示；实验代码补空白对象反例，13项通过。详情及真实响应在artifacts/phase55-takeover/20260906/observation-alignment-contrasts-03/assessment.md；不把合成配对分数当临床验收。当前产品主读预检仍A GLM low/B MiniMax high，C未解析出有效路线；未擅启本地模型。

- 旧读复用工程会商r3-source-reprojection-review-20260906已完成：zcode/GLM-5.3-Flash:max实际身份验证、825.419秒、无fallback，guard复核通过；采纳旧响应不得冒充新提示，纠正报告误称未留原响应/哈希被后处理改变。补产品精确请求工件（原文及可还原图像引用，不含密钥）。反例证实旧response-only唯一约束阻碍不同提示同正文入库，新增0021移除该约束，保留读ID不可变保护；带对账/覆盖的历史行逐值不变、外键完整、有损降级拒绝。存储全套及相关请求/执行/辅助/API共545 passed，86既有依赖警告，271.76秒；未迁移临床库、未新增模型调用。仍不为换规范化键盲目重跑全页，不冒称临床签收。

- 两轮辅助复核已补产品只读原件/逐轮摘录接口、明确分歧列表和前端发起/查看入口。普通页判读与辅助复核不再请求OCR进度；资料页任务链接携带受试者及节点。辅助原件按冻结修订、页、图像哈希核对，不写正式事实/覆盖，无可靠坐标不假画红框。前端相关34项、后端API/持久任务15项通过；Chrome三档1920/2560/3840合成界面点击、轮次、缩放、图片解码和溢出检查3项通过，截图在frontend/e2e/screenshots/targeted-review-*。浏览器首跑缺Playwright内核，改用已安装Chrome成功；合成检查不是临床验收。本批未新增真实模型调用。下一项仍是受控当前版本来源/规范化及原件QC，不改变claims_complete=false。

- 两轮辅助复核最终紧凑提示v2及相邻94项检查通过。继续沿书面判断链发现真实投影缺陷：只有非要求来源的检验事实时，显式professional_judgment被一般溯源提醒遮蔽。已仅对要求investigator_assessment、无完整覆盖且无解析风险的情况保留具体缺判断；事实与原件不改，存在解析风险仍保留风险。新增测试先发现测试辅助器给要求编号加前缀，修正绑定后得到红灯，再完成修复；投影26项、相邻Profile/复核137项通过（范围重叠）。另修复辅助状态在取消/失败时误示正在复核，正式HTTP取消反例与正常两轮2项通过。尚无新增真实模型调用、UI验收或临床收口；缺判断不暂停处理与最终条款/报告链仍须完成。

- 当前直接实现用户已批准的两轮辅助复核，复用既有持久runner及产品read_page，不引入外部harness；共享任务状态和事务由主线程持有，完成工程验证后再独立审阅，不以会商替代测试。新增focus合同、明确同对象读值冲突筛选、持久两轮计划/执行及POST入口；正式事实/对账/覆盖不写入。测试暴露原读记录唯一键不含轮次，已改为辅助记录仅保存本任务检查点，原响应仍留工件；另发现compare默认不可恢复，已补重试属性，正在复验。尚未宣称真实复核、完整前端或临床收口通过；此前“等待批准”记录已被用户后续批准覆盖，不再据此阻塞。

- 本批复验：持久两轮/恢复/接口/提示96项通过；随后服务与LLM扩大回归532 passed、2真实调用opt-in skipped，191.26秒。会商r3-targeted-durable-review-20260906完成，采用明确未采信结果类型、失败分类、只读GET；拒绝配置变化重置两轮建议。修订后24项接口/结果合同/恢复/失败/文本反例通过，扩大回归早于这些末次修订。审阅路线pi/cursor/default未解析底层模型，报告自述失败的子worker尝试，已记边界局限，非临床签收。
- 原件只读检查又发现：31001现有页4“既往用药”所谓冲突为完整句与紧凑表达不同，不能视为确定读值矛盾。入口现仅自动筛选同对象、同时间且唯一对应的数值/日期/异常标记分歧；文字对应关系仍隔离评测。未发起新的真实复核，不对既有两轮样本再跑第三轮。当前旧完整覆盖冻结main v10、页合同v4、对账v9；新执行为main v11、页合同v6、对账v10，不能冒充已重建的新覆盖。该版本复用问题仍需有来源证明的受控方案，不盲目重跑24页。

- 用户最新确认受限复核机制，并要求两主读均确认的研究者书面判断缺失作为非阻断审核发现：条款无法判定、继续其他审核及报告，不另请用户确认缺失。已更新工程设计§16与恢复计划B；尚需正式条款/报告链实现及测试，不冒称已上线。有效读取覆盖与缺判断分开，漏页/模型失败不能伪装成缺判断；自动事实纠正及新阈值仍未批准。

- 独立生产venv的offline/frozen/no-dev安装37包完成；正式模块导入、空临时库迁移0020和create_app/OpenAPI 200（59路径）通过，Python3.12.13/SQLite3.53.4。关闭runner和模型预检，故不冒称真实模型/上传/双击启动通过。发现run.sh及旧服务脚本仍指向legacy，UAT脚本仅静态服务，已记录恢复计划工程纠偏节；未启动旧端口或修改病例库。

- 当前服务层扩大回归422 passed、1 skipped、5 warnings，171.90秒，覆盖本次v20规范化投影及恢复测试；跳过需SELECTIVE_VISION_LIVE_E2E=1的真实单页检查，不计临床通过。接管审查报告新增当前状态索引，明确机制已恢复、正式API/逐读持久已接线、旧描述为历史，仍保留临床未验收和关联未闭合。未改真实病例库、未启动新模型调用。

- 规范化输入复查确认：未采信观察没有被删除，但同对象同数值的相反/缺失箭头被笼统写作关联待核。已增加read_annotation_disagreement，保留原文、unresolved_only和不作临床意义判断；不改变采信规则。模型输入布局升v20，历史响应不改，旧失败作业不恢复冒充新提示。103项领域/提示与21项规范化接线/Profile检查通过；真实规范化仍未重新运行，不能称零候选问题已闭合。辅助复核接入决策未收到答复，未擅自接入。

- 本次直接执行正式页任务恢复验证：共享runner与页执行器有明确持久状态可验证，不涉及临床解释或新增模型路线。新增两种中断注入：双读提交后、对账前进程退出；同一时点已有取消请求再租约过期。新执行器恢复后A/B各仍只调用一次、读检查点完全不变、覆盖最终生成；取消请求先落cancelled，显式恢复后才续做。页执行器及runner合计30项通过（14.63秒），diff检查通过。只用隔离测试数据，非操作系统kill实测；辅助复核产品接入仍待用户决策，未实施自动采信。

- 两版式隔离复核及工程审阅已终态：未证明可自动消解，正式自动采信不接入。新审阅使用批准runner的pi/cursor/default，实际底层模型身份未解析，不冒称指定模型独立临床审阅。采纳字段/对象身份未证实的独立诊断标记，明确对应关系不等于数值一致；28项隔离配对/严格计分检查通过。正式harness新增非stop结束拒绝，15种读道/结束原因反例及执行器失败覆盖验证通过（71项相关检查，追加后执行器15项，数字有重叠）；原响应保留，不生成成功读记录。完整V2回归3886结果早于这些修复。审阅证据见活动任务r3-reread-evidence-audit-20260906的reviews及metrics；Phase5/5.5仍未验收，claims_complete=false。

- 金标16条新增项已完成首轮原图核查并保存页哈希、摘录及差异，未改旧表或产品库。发现随诊文字不符、来源时间角色误定、方案阈值混作报告参考范围、采样/报告日期混用，以及06001文件名与06002清单归属待核。结果为独立评测修订候选，不是全部832项验收；不删除问题条目抬高召回。详情合并至BENCHMARK_SCORING_AUDIT_20260906.md及fact-gold-source-qc.json。
- 本批后续检查：456项领域/隔离复核/金标清点通过，严格来源键评分及配对保护23项通过（另13项单独结果包含其中）。24页1028观察只读数值重算改变16项，但严格键配对仍19，不能将单位修复称关联闭环。第二版式6目标盲核中MiniMax两项串行，第二轮GLM读对而MiniMax4000→8000一次预算重试仍length/空正文；已止于两业务轮，不单源放行，详见conflict-reread-second-layout-02/assessment.md。正式自动纠偏未接入，尚无代表性达标证据。

- 金标16项追因完成：不是无新增裁决，原review JSON均唯一对应“新增”及外层subject；apply_gt_review.py追加列映射错误把备注放裁决列，且subject取错层级。已保存fact-gold-provenance.json含源review哈希，多候选不自动覆盖测试通过。原文件不改、832分母不删；原review也缺excerpt，下一步从原页补核摘录。此前“缺明确裁决”仅限导出表结构，已在评分审计中纠正，不能解释为原审阅没有新增意图。

- 金标只读清点发现832历史非删除项含16条自由裁决说明，这16条同时缺受试者字段及摘录；明确保留/修正共816，不据此静默缩分母。源哈希、行号、缺项保存fact-gold-inventory.json，原XLSX不变，清点回归通过。下一步须按page_id追原页并建立独立金标裁决修订，不能把产品病例库填成人工结论，也不能沿用历史宽松数字命中成绩。

- 实测箭头错误进一步定位到对账缺口：相反箭头在数值规范化后可能同键。现算法r3-v10在精确键及来源定位关联两条路径保留异常标记分歧，不将其视为整条事实一致；数值/原文不改，箭头不承担医学判定。相反/单路缺标记/相同标记及来源关联回归通过，62项执行/API/领域检查与追加后的43项领域检查（重叠）通过。旧对账历史保留，不声称已重建正式覆盖；3886全量结果早于本修复，不能混算。

- 两轮真实隔离原件复核完成：GLM high与MiniMax high直连产品API，同图只核对WBC/P-LCC，未给候选答案。第一轮18.86/44.49秒，第二轮残余P-LCC13.48/17.04秒；GLM两轮均将原图↓写↑，MiniMax均↓；GLM第二轮摘录夹解释文本。两轮停止、不采信、不加第三轮。详见conflict-reread-blind-02/assessment.md及两轮原响应。3项隔离脚本边界检查通过，不代表正式持久复核/临床验收；下一步需区分数值单位一致与原件标记冲突，避免忽略箭头后错误声称完全一致。

- 用户新增建议：冲突项采用GLM high与MiniMax high针对原件最多两轮复核，仍冲突再交用户。采用一次独立设计会商（解释性临床采信边界存在不确定性），主路zcode/GLM-5.3-Flash max一轮完成，无fallback；工程设计已追加隔离验证提案，未接产品。审阅引用旧检查点提出重复建设前驱链，现代码已核实并驳回；采纳同族不计双源、首轮不见候选值、失败不放行。原件矛盾/研究者判断缺失不能被复核抹平。完整V2回归3886 passed、3 skipped、139 warnings、2 subtests，809.75秒；跳过历史OCR工件缺失和两项需显式开启的真实模型检查。全部测试进程终态，临床验收仍未完成。

- 页读端点异常现在逐次保留绑定job/step/attempt/读道的失败回执（仅异常类别/状态/耗时，不保存异常消息或请求密钥），内容寻址工件在后续重试中保留；末次步骤检查点只列本次请求，不冒充全历史。注入证明两次端点失败均落盘且A只调用一次，20项执行器/API通过，diff检查通过。产品路线、重试数量与采信未改，仍无临床验收结论。

- 本轮选择直接执行：单位解析是有确定输入输出的通用语法修复，可用反例与历史字节验证，不涉及新增语义采信；前轮为实质进展，非等待。当前HEAD 411832d8611ddd5ba9ac280df58261d40d358f75。新页合同v6只补完整数值后/μL（含NFKC微符号、ASCII u）的单位分离，保留零、比较符号，拒绝夹杂数字的箭头及未知单位；v5及更早冻结解释。468项领域/执行器/API通过，98份真实历史记录只读往返字节与哈希不变。没有整例重读、旧覆盖升级或临床放行。配对同一提示的5组合成反例（异项目/日期/标本/极性与零值真对应）均符合冻结答案，原响应见observation-alignment-contrasts-01；这是窄合成探针，不是金标临床达标。下一步仍需受控历史重投影方案及更具代表性配对评测，正式新增语义步骤未获批准。

- 规范化直连 transport 增加逐次请求回执（包括 length 翻倍重试、失败类别、耗时与响应），正式执行器写入已有内容寻址工件，绑定 job/step/call/run；成功步骤留回执哈希，失败工件仍保留，不改变模型、重试预算或临床采信。204项相关检查通过，包含失败落盘注入；非真实超时复跑，旧v18失败作业未重启。隔离配对增加严格ID金标计分：错误配对、漏配与重复分列，空集不伪报100%召回；9项实验检查通过。仍仅隔离评测，正式接入未批准，claims_complete=false。

- 用户批准仅隔离评测观察配对，未批准接入。两页试验30对，约5/8秒，仅5对基本兼容，全部accepted=false；原图核查及合成反例见observation-alignment-pilot-01/assessment.md。完整V2回归3865 passed/3 skipped，783.14秒；之后新增配对6项另计。主读提示v11补可见单位、不得猜单位，62项相邻和42项提示检查通过。单页GLM low诊断59.65秒返回27条观察，血常规单位部分改善，但WBC文字、P-LCC箭头仍误读，/μL规范化不支持；详见unit-prompt-pilot-01/assessment.md。不当作双读或临床通过，未重跑整例，98份历史页记录字节/哈希往返不变。当前无模型任务或测试进程遗留；继续处理尚未闭合问题，不是暂停。

- 规范化23f235…已终态failed_retryable/TRANSPORT_FAILED：前两组完成但仅输出7/8个未解决项、无候选；第三组Request timed out，不能当临床通过。只读重建前三组输入，Normalizer v19紧凑投影从118274/139285/197363字符降至87644/103518/145650（约26%，不是token或速度实测）；保留原文、观察引用及冲突，原存储不变，96项相关回归通过。旧v18任务不在新v19下盲重试。独立只读审阅r3-observation-alignment-review-20260906完成，无fallback，产品仍直连API。实际24页1028条观察、62个已采信观察成员的诊断中，仅忽略位置最多新增2项，故不采纳无条件放宽位置或删除冲突建议。新增页合同v5修正规范数值后、单位前箭头（如9.1↑ %），v4及更早冻结解码保留；61项定向及460项领域/页执行/API通过（集合重叠）。v5使旧v4覆盖不能冒充当前新运行，尚未重跑整例；完整V2回归进行中，Phase5/5.5仍未验收。

- 输入预算进一步核对纠正了上一条的初步方案：即使一页也有约10万以上字符的双读附件（观察/未对齐项/对账信息），缩页不是根本解决。按用户“系统内置模型不受人为上下文限制”，仅移除R3路径旧100000字符门槛，legacy仍保留；未截断原文、未自动换模型。撤回本轮刚加的自适应缩页代码与注入测试，避免无效复杂度；替换为R3超过100000字符完整保留的回归，相关95项通过。23f235…经正式HTTP retry恢复，原失败历史保留，真实规范化结果待返回。页1原件抽查见LIVE_LOW_MAIN_A_QC_20260906.md，发现字段粒度、时间关联及非忠实摘录差异，不等于质量通过。

- 低强度主读3bd4e1…已完成（00:57:04–01:35:12 UTC）：24页中23页accepted、1页MiniMax schema失败；GLM24次共670.87秒、最长63.382秒，MiniMax31次共2986.99秒，整例38分钟仍不理想。合法后继f04c88357e93484ba32ba4a21161ad45复用70步骤后完成。正式HTTP规范化初次409暴露失败历史也参与唯一候选的问题，已在先解析重读链之后排除失败候选，双成功仍拒绝；14项回归通过。随后201创建23f235…，模型调用前139870字符超旧100000字符上限而失败。现补建任务前完整提示预算检查，超限按更小连续页组重建并冻结身份，不截断资料；95项相邻检查及新增分组故障注入通过。新正式HTTP尝试正在进行，尚无规范化/临床验收成功声明。

- 新低强度主读作业仍在运行；保存的 read:2:main-B 原响应按产品归一化过程复验，26条事实之外的18条条款关系均缺少 region 摘录，是实际 schema 拒绝原因，不是归一化字段缺失。不得由构建者补写摘录或放宽放行。执行器补齐手写第三读成功及格式失败的原响应、usage、耗时留存，14项执行器回归通过；当前已加载作业不受代码更新影响，端点异常跨步骤重试的完整响应历史仍未补齐。

- 最新用户goal将页主读GLM改low，产品route已改，MiniMax仍high/C仍low，方案语义和Normalizer未随改。旧 high 重读598d15…通过合法取消边界终态cancelled，37步骤completed/36cancelled，进程正常返回。新正式PageReviewRuntime作业3bd4e1a089064b2a8a3c1a295036ef1d已启动，预检确认三读道low/high/low；使用运行时共享准入，不调用外部harness。新记录身份纳入effort避免同正文跨强度冲突，历史high保留；相关71项合同/仓储/harness通过，正式HTTP高低路线不混复用6项通过。模型实跑与临床结果尚待作业完成。
- 独立审阅采纳后的即时提交增加取消回调观测终态和ProcessDeath同伴保留反例，并行7项通过。历史横评评分只读复现跨字段/时间同值与任意正文数字误命中、数值零丢失；核查记录为活动任务BENCHMARK_SCORING_AUDIT_20260906.md，不改旧成绩、不把0.969当正式字段级证据，后续分列宽松对照和正式口径，阈值未变更。

- 用户最新要求恢复全局执行/会商机制，旧“仅自行执行”不再适用。针对共享调度和恢复语义已完成一次只读 zcode/GLM-5.3-Flash:max 审阅（r3-durable-reader-review-20260906），无 fallback；产品真实判读仍使用自己的直接 API harness。会商不读取临床资料或凭据。实证反例确认并行波次等待全部结束才提交成功结果，已移至每个 future 返回即经原租约写栅栏提交，取消通知移至事务提交后。工作流+页执行/API 105 项通过，追加慢同伴 ProcessDeath 的即时持久化检查后并行测试 6 项通过；尚不代表全链或临床验收。关于重置 attempt 的建议暂不直接采纳，需核历史与恢复入口。
- 失败原响应现由 ArtifactStore 保存，主读检查点含各次 SHA、响应模型/ID、finish_reason、预算和耗时，后续新增 usage 留存；12 项执行器测试验证成功/截断/格式失败留存。endpoint 中途失败以及手写 C 响应的完整尝试历史仍待补齐，不能称全部可追溯。旧无 execution_control 的串行任务仅允许补调度字段后复用，其余身份严格相等；正式 HTTP 旧/新任务恢复及相邻 21 项通过。
- 隔离受控重读 598d15a5736f476f97e2c7f500704f38 已从终态前驱 9b71eb527b7e4abfae53e4ffd5345ef7 合法建立，复用38份成功主读，只调用10个失败读道。当前仍在运行（终态以现场为准），不因观察等待重启。该进程在逐个提交修复前启动，仍使用旧已加载 runner；不能用本轮状态证明新 runner 性能。已见 GLM 12000 length 空正文及24000仍截断，部分读道重读成功，尚不可进入规范化验收。
- MTPLX GUI 已重新显示并自动恢复服务，设置与 /models 确认 Flash-Next optimized-speed，未启用27B。产品 low 最小文本请求返回 handwriting 空数组、stop、response_model=mtplx-flash-next-optimized-speed，仅证明连通。现有作业冻结两主读路线，不中途添加 C；C 的受控补读和视觉验证仍待完成。未调用 GUI 内任何 Hermes/Pi 功能。

- 隔离正式作业 9b71eb527b7e4abfae53e4ffd5345ef7 已终态返回，73 步 completed，但24页覆盖仅14页 accepted、10页 failed_pending_reread；A/B保存16/22份记录、274/566条观察，14份对账共56键，不能当56项临床事实。7处length均A，schema为A1/B2；8份对账另有手写configuration失败。coverage=subject-page-coverage:28a1d80bf1f513a765859c93538bbda3。无活跃执行进程。系统sqlite3只读查询连续报open错误，产品venv sqlite3使用绝对URI mode=ro可读，未以此重启作业。
- 实跑确认性能缺陷：默认并行scope仅discovery_*，R3 read步骤实际串行。已给新页任务冻结execution_control，仅read步骤白名单，限额为两主读各自并发上限之和，对账/覆盖仍串行。15项任务/执行器回归通过；追加双线程Barrier证明两主读确实同时进入后12项执行器通过。保留旧作业和成功记录，不修改历史冻结payload。下一步补失败原响应留存（当前只记failure_kind导致schema根因证据不足）及受控重读，不直接重跑整例、不宣称临床通过。

- 实时 /models 预检通过 GLM Coding Plan 与 cms-smk MiniMax 两主读；手写 C 的 http://127.0.0.1:8002/v1 为 ConnectError，未换模型。先前未预检冻结的 d2229b1e207b44afb9e12d41ed079c2a 已经 JobService 合法取消（未执行）。按已解析两主读配置新建隔离正式作业 9b71eb527b7e4abfae53e4ffd5345ef7，尚未执行；下一步只运行此 ID，不能用未解析的三路线配置触发身份不符。手写缺失必须留在覆盖，完整验收仍未满足，MTPLX 后续仅 GUI 恢复指定模型。

- 已以源库只读 SQLite backup 创建隔离副本 artifacts/phase55-takeover/20260906/sar31001-r3-runtime-01，仅复制 artifacts/blobs（不复制旧 runtime/凭据）；副本迁移 0019→0020、integrity_check=ok。正式 PageReviewJobService 已按筛选活动权威新建 R3 作业 d2229b1e207b44afb9e12d41ed079c2a，未执行模型步骤，旧作业未恢复。下一动作：产品读道预检后只运行这个 job_id；不扫描运行副本中的历史待办，不改原库或基线活动指针。

- 真实来源前置核对已用 SQLite mode=ro + 产品 authority_from_active_episode、CompleteEvidenceProcessingRevisionRepository、page_association_sources 执行：筛选 59b98368e962465ca5d62ff55b4da07d 与基线 746385aba80c421ab83aaf439e084b7f 各 24 页、24 个非空所选来源文本，当前完整修订校验通过，无校正项。未激活或修改快照。下一步从该库一致性备份建立隔离运行副本并按当前迁移/正式任务入口运行；不把来源存在当作原件 QC 或临床通过。

- 实测准备已只读核对产品显式 .env 的非秘密配置：Normalizer 实际为 zhipu-coding-plan/glm-5.3-flash/high，端点 https://open.bigmodel.cn/api/coding/paas/v4，max_tokens=16384，产品凭据存在，未读取外部 harness 配置。传输虽名 deepseek_evidence_normalizer_transport，实际按冻结 ModelConfig 选供应商；正式链路为 fact_normalization_executor → EvidenceNormalizerRunner.run → transport_factory。现有保存 input 多为旧期工件，不能冒充 R3 正式实测输入；下一步须从当前冻结来源和有效 coverage 生成输入，不能绕过来源/版本检查。

- 近期 r3-v9 对账和 Normalizer v18 的相邻流程回归：页任务服务、判读执行、规范化持久化/命令/Profile 执行/来源适配共 77 项通过，27.17 秒（5 个 SWIG 警告）。检查了既有测试范围，部分接线测试直接注入 coverage，不能替代正式真实入口实测。未调用外部 harness 或新模型；下一实测复用产品 fact_normalization_executor 的 transport_factory 与输入构造，不另造识别流程。

- Normalizer 提示 v18 明确页读 context.time_text 不自动证明事件或用药起止日期，须核对原文中的日期关系；就诊/处方/发放/使用/停药不可互换，缺起止时保留用药事实及未知时间缺口。95 项适配及 R3 接线测试通过（5 个 SWIG 警告），只证明提示实际传入且合同接线未回归，不证明真实模型遵循或临床已通过。后续须以正式 Normalizer 实跑及原件检查验证，不将本轮提示修订当作时间问题闭环。

- 正式 coverage 选择已补直接验证：持久作业完成后按冻结权威可选择同一结果；仅改变复核所用来源文本及合法哈希，旧对账身份即被拒绝，精确配对/来源辅助两种场景均覆盖。执行器 12 项通过（5 个既有 SWIG 警告）。用依赖替换模拟来源变化，未修改真实库；仍非临床验收。后续继续时间证据及正常产品流程的语义质量验证。

- 正式来源构造扩测通过：仅应用所选校正、保持原 OCR 不变、哈希随有效文本变化、错页拒绝、无 OCR 不伪造来源、错误校正锚点拒绝。新服务测试与持久执行器共 17 项通过（5 个既有 SWIG 警告）。这些是隔离依赖的服务合同测试及既有持久任务测试，不冒称真实临床验收；继续补正式覆盖选择与有效文本恢复的一致性。

- 来源定位根因进一步确认是全角冒号、空白和跨行药名等排版差异。r3-v9 加逐字符 NFKC/去空白及原偏移映射，不去数字/日期/否定/比较符号；27 项领域及执行器检查通过。同批 v10 保存双读+同源页 OCR 诊断复放可关联键从 2 到 14，不能当成 14 项事实或临床通过，用药时间仍需原件核对。设计 §8.1 已同步；未新调模型、未写临床库，继续推进。

- 已完成 v10 真实保存病历页的只读来源关联诊断：通过横评 manifest、实际原 PDF 哈希和页码核对同源；两条成功 OCR 文本一致（503 字符），但库页图与横评 JPEG 属不同渲染。来源关联得到 2 个观察键，A/B 唯一精确摘录命中 7/23、5/18；不足以解决整页采信。详情保存在原诊断目录 source-association-review.md；不写正式结果/coverage、不将原始 OCR 冒充当前修订有效文本。下一步区分 OCR、摘录粒度和对象时间差异，继续正式来源异常验证，未暂停。

- 原有精确键路径确认存在同对象同时间多值中择一配对的同源歧义，现统一剔除同一读道同字段完整 context 的重复观察所涉及键；来源辅助合并后亦应用，不影响明确不同时点的观察。算法 r3-v8，完整领域与执行器 440 项通过（5 个既有 SWIG 警告），含有/无来源辅助、同时间矛盾和不同时间反例。未改模型路线、临床库或原始读数；后续继续真实来源文本复放与覆盖恢复验证，临床验收仍未完成。

- 继续由当前 Codex 直接执行，复用现有连续任务，不派发外部会商。新增来源关联发现并修复“按值分组隔离第三条矛盾观察”的缺口：先核对同范围同对象观察唯一性，再比较值/单位；算法升 r3-v7，历史结果保留。正式持久任务增加位置描述不同、同一原文数值的合成反例，20 项执行器/来源关联测试通过（5 个既有 SWIG 警告）。Normalizer 附件范围哈希包含新对账字段，未发现兼容拒绝。尚需真实保存记录复放、来源异常及原有精确键路径的多读数歧义核查；零事实采信和 GLM 耗时尚未获真实改善证据。未新增暂停点，claims_complete=false。

- 正式页任务现从完整处理修订及所选校正冻结 association_sources，作业合同 v7；执行器只在两主读完成后传入对账，不进入模型消息。coverage 选择用同一权威处理修订重新生成来源文本复核结果身份。16 项执行/接线/API 检查通过，追加对账文本哈希等于作业冻结哈希断言后的执行器 11 项通过（重叠）。尚需真实保存记录复放、来源异常/恢复扩测，未宣称临床通过。

- 来源匹配已作为显式可选输入接入 Reconciler：新对账合同 v3/算法 r3-v6，保存文本哈希并进入结果身份；旧 v1/v2 不得附加新来源依据。记录重验证拒绝伪造规范值，重复观察不凑双源，同对象时间/极性差异仍保留。完整领域及 R3 规范化接线回归通过；正式任务尚未传入冻结文本，运行效果未验收，下一步完成任务与 coverage 同源接线。

- 已新增独立 page_source_association 领域模块：校验冻结文本哈希、文档页与双主读原件身份；唯一精确摘录范围只替代自由位置描述，对象/时间/极性/字段/值/单位仍参与匹配，保留原观察。5 项起始反例通过；未接正式 Reconciler/任务/coverage，不能用于正式放行。下一步补齐数值/重复观察与输入重验证反例后接版本化对账，避免孤立模块冒充完成。

- 工程设计 §8.1 已记录来源关联的正式实施顺序：冻结侧车文本身份、唯一摘录范围替代自由位置身份、其余对象/时间/属性/极性/值/单位严格核对、新版本对账及 coverage 重建验证。明确未实施正式接线，不声称零采信解决。下一步按该合同实现，避免继续仅增加提示或外围检查；不改变 R3 模型及单阶段结构。

- 未采信投影补充 same_source_passage：仅两主读各一条、同文档/页/有效文本哈希/唯一文字范围才相互链接，明确仅表示原文范围相同，不表示事实一致；多观察歧义或重复原文不建立此链接。已接 Normalizer v17，101 项关联/适配/接线通过；采信键完全不变。仍需把可证明的属性、对象与时间关系接入正式对账，不能将这项来源辅助链接算作零采信已解决。

- 未采信观察现可附确定性唯一文字范围：只在同文档版本/同页有效文本中精确唯一定位，保存有效文本 SHA256、字符范围与摘录；重复/缺失/改写不猜测，标明 effective_text，绝不作为图像坐标或临床采信。已接 Normalizer 输入，提示 v16；100 项投影/适配/接线检查通过。此为来源关联的定位基础，尚未完成跨读道实体对应，未新增模型调用或临床库写入。

- 普通事实来源核对补充同页摘录检查：每个已采信观察的 region.excerpt 须在候选所选同页 locator.localized_text 中可核对，只做 NFKC/空白规范，不删除否定、比较符号或日期；空/page_only 或同页无关文本不放行。96 项关联/适配检查及追加 3 项来源检查通过（有重叠）。这是文字对应校验，不是语义或原件视觉验收。尚不拼接跨多个定位的摘录；此类需可靠连续范围，不能任意拼接，以免跨段借证。双读零采信问题仍待来源关联层解决。

- 当前完整后端 V2 回归结束：3823 passed、3 skipped、139 warnings、2 subtests passed，813.38 秒；使用 tests/fixtures/isolated.env，未启用真实模型测试。跳过分别为缺少 Slice 4.0 历史 oMLX 探针工件、未开启 Coding Plan live 标志、未开启 selective vision live E2E 标志。警告为 SWIG 与 SQLite datetime adapter 弃用。未将跳过算通过，临床/浏览器验收仍未完成。源码补查确认普通事实的同页摘录关联尚不完整，既有用药专项来源校验不能替代全类型来源核对；下一步继续该缺口，不新增暂停。

- 来源链核查补齐候选页绑定：Normalizer 现在用冻结 available_locators 核对候选 locator_ids 的页集合与已采信 source_observation_refs 的来源页集合，拒绝跨页借用或缺失定位；原有观察成员校验保留。96 项来源/适配/接线检查通过。初次接线误用属性名 locator_inputs，测试暴露后改为实际 available_locators 并重跑通过。此只证明页级对应，不证明同页摘录语义正确；同页来源关联仍待推进，未改真实库。

- v10 真实病历页复测结束：两路 23/18 条事实、采信 0、冲突集合 23；MiniMax 33.747 秒，GLM 234.805+246.532 秒。药物拆分局部改善但自由位置/关联仍未遵循，不能以冲突数量下降宣称改善。停止仅堆叠提示重复同页，继续工程设计 §8 来源标签/位置与展示名分离及可证明关联；实测记录在 history-diagnostic-03-v10/diagnostic-review.md，无后台诊断进程遗留，无阶段暂停。

- 未采信观察投影现分别标明单源、对应关系待核对、同对象读值不一致；不同日期不标成读值矛盾，来源身份不同不参与比较。只影响 Normalizer 的未解决项输入（提示 v15），不增加 accepted_fact_keys，不修改原始记录，不宣称已完成前端分类展示。98 项投影/Normalizer/正式接线检查通过；仍需完善观察身份及真实模型验收。

- 主读提示 v10 补齐单对象事实粒度、原件标签优先、药物分别记录和就诊/给药日期不可替代的通用规则，两主读对称适用，不修改手写读道规则。452 项 harness+完整领域检查通过（5 个既有 SWIG 警告），diff 检查通过；首次回归仅旧提示版本断言失败，更新断言后重跑。此为提示契约修正，尚无 v10 真实效果证据，未放宽对账或修改历史记录。后续继续核查字段身份/关联方式及正式端到端质量，不以本轮测试结束作为阶段暂停。

- v9 病历页真实复测已结束（history-diagnostic-02-v9）：A 24/B 18 条有效事实，NONE 合同错误本次未复现；采信仍为 0、事实冲突 32 项。GLM 214.080+281.906 秒，MiniMax 40.283 秒。已定位自由字段/context 和用药粒度差异，不将执行 accepted 冒充临床通过。详细核查在运行目录 diagnostic-review.md；继续通用观察身份/粒度契约纠偏，不增加预算盲跑，不暂停、不改真实临床库。

- 针对病历页 none+摘录错误，补齐 ClauseEvidenceSignal 对外 JSON Schema 条件约束：none 只能无 region/null，其他关系必须提供对象摘录。此前仅 Python validator 知道此约束，模型看到的 Schema 不完整；现发送 Schema 与服务端校验在 8 组关系/摘录组合上保持一致。主读提示 v9，73 项合同/历史/harness 检查通过。未修改模型返回值、未放宽标准，也未宣称新提示实际质量已通过。
- 正向病历页 `sar31001-history-diagnostic-01` 已结束：MiniMax 42.452 秒，主要病史/三项用药已读到，但 clause_signals[7] 的 none 携摘录导致拒绝，保存响应离线复现；GLM 经 length 重试共 543.302 秒、22 条事实。两端返回模型名与请求一致，仍 failed_pending_reread，无临床采信。该页版式和内容均不同，不能单因果归因于方向。后续分开处理视觉稳健性、合同遵循和上下文成本，原始回执与诊断已保存。
- 页记录身份已纳入文档版本、页码及冻结审核上下文，避免相同图像/条款/响应在不同节点产生相同 ID；同一冻结输入重复仍保持同 ID。作业合同升 v6，旧作业不得静默按新身份逻辑续跑。46 项 harness/执行器/API 检查通过，含相同响应在不同文档版本、节点修订、筛选/基线下身份分离；不改历史记录。
- 时间规范改动后的完整 `tests/v2/domain` 回归 412 passed、5 个既有 SWIG 弃用警告，6.28 秒；仅领域层工程证据，不是完整 V2 或临床验收。继续审核运行身份与 R3 页处置合同：无价值处置当前只有通用理由，尚未保留两主读各自说明，需补原始理由而非包装为已验收。
- 日期时间规范化已版本化接入：页合同 v4、对账合同 v2、对账算法 r3-v5；同一明确分钟时间的分隔符/补零差异归一，保留分钟/秒/小数精度、时区与目标区分，非法日期时间拒绝。历史 v3 事实及旧手写/对账按冻结算法读取，不覆写。73 项关联/API 检查与后续 32 项历史/存储/接线检查通过（有重叠，不累加）；现存 9 条真实诊断记录及对应对账重新解码后 JSON 完全相同。未进行新临床验收。
- 产品 direct completion 现保留服务端 response_model/response_id，诊断回执写入两字段，30 项 harness 检查通过。最小无临床内容真实请求：A 请求/返回均 glm-5.3-flash（202609060200136c3cf5a526d745ec）；B 均 MiniMax-M3（06eb8bafd42671d7b6944d339647b6f1），均 stop。此为接口回报身份，不证明内部视觉处理正确；历史回执未采集字段，不可事后补造。未使用其他 harness 或读取其配置。
- 高细节诊断 `sar31001-dna-diagnostic-04-high-detail` 已结束，main-A 329.273 秒，main-B 85.847 秒；B 正常返回但空 raw_value 导致 Schema 拒绝，保存响应离线重放已复现，原件错读仍在。该轮 main v8，对比上一轮 v7 存在提示差异，不作纯参数因果结论。详细诊断已落 artifacts，不用于临床采信，不放宽校验；下一步核供应商返回身份/视觉能力与紧凑条款表达。
- 原件发送边界补查：构造模型消息时校验最终内嵌图片字节与冻结哈希，防止路径文件在输入校验后变化；相关路径变更反例及 harness 29 项通过。实测误读并非由该路径问题引起，诊断使用已加载字节。SAR 原始条款包字段体积分析（紧凑 JSON 字符，不是 token）：expression 64766、evidence_requirements 37970、source_text 42834，原文去重不是全部性能空间。后续须核查表达式与证据要求的紧凑投影，不直接删除临床语义。
- 已补 R3 §7.4 最小审核节点上下文：正式 PageReviewJobService 从服务端 Episode 冻结 stage、workflow_stage_id、anchor_dates、节点 ID/修订，执行器传入两主读同一 PageReviewContext。手写 C 不携带；空日期保持空，不从原件文件名推测。主读提示 v8、作业合同 v5 阻止旧作业静默续用；完整 payload 相等校验继续约束局部重读。42 项 harness/作业检查及 26 项 API/存储/Normalizer 接线检查通过，diff 检查通过。此前 v7 实测保留为历史证据，不冒称 v8 已实测。Phase 5/5.5 临床状态仍未通过。
- 条款负担对照已结束：`sar31001-dna-diagnostic-03-no-clause` 仅诊断移除用户消息 clause_pack；GLM 114.475 秒正常结束（5867 输入），MiniMax 55.755 秒（5256 输入），相比完整包显著减少本次耗时，但 MiniMax 原文误读持续，采信仍为零。两类问题分开处理，不能宣称缩短提示已解决视觉问题。诊断隔离测试通过，harness 27 项通过；正式产品不启用无条款模式。
- v7 同页复测已结束：`sar31001-dna-diagnostic-02-v7`，GLM 含重试 409.666 秒、MiniMax 153.057 秒，事实采信仍为零，不能宣称提示修复有效。图片编码回环核验与原件字节一致（JPEG 1555×2200，无 EXIF 方向）；不证明供应商视觉实现正确。详见该运行目录诊断记录。下一步分离图像读取与条款负担的诊断，不再只增加提示重复同页。
- 输入审查另发现多种图片来源并存时，哈希读取优先级与发送优先级不同。PageReviewInput 现禁止多来源并存，三组歧义回归覆盖，harness 26 项通过，diff 检查通过。这不是本轮真实误读根因；真实调用只有 image_bytes，临床验收仍未通过。
- 最新进展：`sar31001-dna-diagnostic-01` 的 v6 双路已返回，GLM 经一次 length 重试总计 432.414 秒；两路事实采信为零。原件复核发现 MiniMax 错读医院、生成本页不存在项目、混淆时间，详见运行目录 `diagnostic-review.md`。消息哈希相同，不能归因于两路收到不同图片。此页仍未临床通过。
- 现行主读/手写提示 v7：明确 JSON 输出、原文抄录、方案不作受试者事实来源、不得按模板补齐、不做页级计算。34 项 harness/执行器检查通过，v7 尚无真实复测结果。Normalizer 提示 v14 同时移除 NONE 信号的“已采信证据”输入，95 项适配/来源、39 项下游合同/接线通过（重叠集合不累加）。继续不同版式验证及输入边界排查，不暂停，不新增人工决策前提。
- 最新真实诊断：`scripts/r3_page_diagnostic.py` 仅调用产品 API，核图片哈希和 ClausePack、独立输出，不读横评答案或写临床数据库。31001 旋转血常规页两次运行均失败在 GLM length（各已按合同重试一次），MiniMax 正常返回但不能单路放行。`sar31001-blood-diagnostic-01` GLM 241.258+446.653 秒、约 79267 输入 token；`sar31001-blood-diagnostic-02-compact` GLM 209.488+468.375 秒、37883 输入 token。原始响应/覆盖/usage 均在 `artifacts/phase55-takeover/20260906/`，作业已终止返回，不是仍在后台等待。
- 当前提示 main v6 / handwriting v6。仅传输层去重父条款原文及省略空字段，SAR 81 子条款字符减 42.1%、D001 67 子条款减 30.6%，两包均可还原并通过原哈希；权威存储不改。手写 C 请求不再携带条款，仍仅输出 handwriting。输入减少不等于耗时/质量已改善。旧横评同图 GLM 也需 293.74 秒（8176 输入 / 11804 输出 token），不能拿它当快速成功基线。
- 修复 NONE 条款信号作为事实候选来源的问题：保留覆盖结果，但不分配可支持事实的来源引用；反例与 pending 共 4 项、规范化/执行器相关 105 项、正式页相关 24 项、投影/harness/来源最终聚焦 33 项通过（集合重叠，不累加）。Ruff 当前虚拟环境及 PATH 均不可用，未声称 lint 通过。
- 下一连续动作：停止同页重复放大预算，用不同版式隔离图像复杂性与提示/输出合同因素；核真实页批注归属与坐标约定；继续金标来源及真实正式链路。当前仅诊断，未完成金标评测、31001 临床 QC 或整例产品验收。不需要用户决策，不新增暂停文件。
- 工作树和 HEAD 仍为 `.worktrees/phase5-clinical-facts-profile`、`411832d8611ddd5ba9ac280df58261d40d358f75`，任务 `09-05-phase55-dual-vlm-page-review`。用户要求持续推进，只在确需用户决策时停下。
- 产品持久页任务已接正式 POST、状态 GET、注册执行器及规范化前置选择；执行合同 v4、页记录 v3、main 提示 v4、手写提示 v3、对账 r3-v4。下方 09-05 未接通及旧提示版本描述保留为历史。
- 受控重读以显式前驱作业派生新任务；只重读失败读道，复用成功记录与未失败页核对；覆盖追加前驱关系，存储核对来源及版本，规范化只接受唯一有效末端，不按时间择优。
- 前端遇到 PAGE_COVERAGE_NOT_READY 才发起前置判读；支持刷新恢复、局部重读、完成后衔接整理、切换受试者拒收迟到响应，以及离线进度查询。任务状态 completed 不等于所有页成功。
- 验证分层：全 V2 3779 passed / 3 skipped（早于随后重读增量）；重读相关 49 项、状态相关 20 项、最后 API 4 项通过（集合重叠，不累加）。前端全量 537 项通过、正式构建通过；Chrome 1920/2560/3840 三档正式证据页恢复与重读交互通过，使用可控 HTTP 合成数据，不是临床/模型实跑。
- 正式 `/profiles` 已从资料目录接入；明确失效的项目/受试者身份不再回退到其他对象。聚焦前端 32 项、三档 Chrome 六项流程通过，含原文下钻及红框；1080P 截图已查看。均为合成接口数据，不能替代真实临床验收。待办另含多页/进程中断恢复、31001 原件 QC、金标产品复跑、后续 Phase 6–9。
- 当前产品真实合成页探针 `artifacts/phase55-takeover/20260906/synthetic-current-prompt-01`：GLM 73.926 秒，MiniMax 20.252 秒；数值均正确，但自造位置描述造成零事实采信，且打印声明被误作手写。页执行 accepted 不代表事实采信或临床完成。现将提示升级 main v5 / handwriting v4，明确位置仅抄原件标题、日期字段不自关联、打印声明不能作手写；22 项 harness 测试通过，真实复测另存 `synthetic-current-prompt-02`，以其实际产物为准。
- Phase 5/5.5 未临床验收，claims_complete=false；未修改真实临床数据或模型路线。没有新增暂停文件。
- 提示 v5 实跑复测已返回：`synthetic-current-prompt-02` 两个数值（含零值）及编号共三项采信，手写误报与第三读误触发消失；日期仍因一路缺 context 未采信，标题/说明仍有差异，不能宣布关联问题解决。GLM 79.436 秒、MiniMax 23.834 秒。下一步扩展不同版式并接真实资料/金标诊断，不为单张探针加特例。

## 2026-09-05 文档优先修订

用户要求先形成完整新设计、实施规划与新 goal prompt，暂不设置 goal。当前入口为 `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`、`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` 及活动任务 `GOAL_PROMPT_20260905_R3_TAKEOVER.md`。旧阶段计划保留，Phase 5/5.5 未临床完成。

凭据已按用户授权从 OMP 一次性迁移至产品显式 env；产品自身双主读合成页已成功，不调用 OMP harness。当前提示 main v3 / handwriting v2。页任务规划器 3 测试通过，执行器及最近对账提取尚未验证、未接正式入口。下方此前“尚无真实模型”等描述属于历史状态。保留恢复检查点，不清未提交实现。

## 2026-09-05 接管审查与继续实施

- 最新用户授权：当前 Codex 独立全面审查、必要测试、更新计划与持续实施；本轮不使用外部执行/会商机制。
- 当前权威工作树仍为 `.worktrees/phase5-clinical-facts-profile`，Trellis `09-05-phase55-dual-vlm-page-review`。
- 接管报告：该任务内 `ENGINEERING_REVIEW_20260905_TAKEOVER.md`；历史 handoff 保留，当前检查点已标注恢复，Plan 增加接管纠偏顺序。
- 已修复重复单源信号被误作双源、归一化精度/零值丢失、可选手写预检阻断、运行上传依赖遗漏；页模型改为输出原文、代码计算规范值，提示版本 v2，并拒绝不存在的条款引用。
- 前端 526 测试及正式构建通过；扩大后端 480 通过/1 真实探针跳过（最后提示修订前），最后 R3 聚焦 51 通过。尚无本轮真实模型/浏览器/临床验收。
- 最大未完成项：R3 持久逐页任务及正式 API 接线；当前底层 coverage 参数不等于正式链路已经启用。还需处理位置/时间关联对账、规范化键版本兼容、金标和 31001 QC。
- Phase 5/5.5 保持未完成、claims_complete=false。产品不得依赖本机 Hermes/OMP 的 harness 或凭据文件。

## 2026-08-19 Milestone: Phase 4 Slice 4.2 Accepted

- The upload preview service and append-only `0008a_evidence_upload_previews` migration are accepted after counterexample repair: only an effective snapshot may be an incremental base, and every new confirmation request revalidates episode revision and base before duplicate convergence.
- The frozen six endpoint contract is implemented exactly. Idempotent replay is no longer conflated with a new upload that resolves to an identical collection; the API exposes truthful `created`, `replayed`, and `duplicate` facts.
- Cancellation cleanup failure remains visible as a retryable cancelling state, blocks commit, and does not leak staging paths or hashes through the error envelope.
- Codex independently verified `89` focused tests and `1034` full V2 tests, plus clean focused Ruff, Pyright, and `git diff --check`.
- The `/subjects/:subjectId/evidence?episode=...` workbench now provides the two upload modes, item-level preview review, stable per-preview idempotent retry, cancellation-safe replacement, snapshot-derived current-version display, and a fluid three-column evidence skeleton. It deliberately shows truthful waiting states and no red boxes before real page artifacts and verified coordinates exist.
- Codex independently verified frontend `310` tests, `9` focused evidence Playwright cases across 1080P/2K/4K, `40` desktop-route cases with `2` viewport-specific skips, and a production build. Final screenshots have no page-level horizontal scroll or sticky-header overlap.
- Slice 4.2 is accepted and Slice 4.3 is the next safe implementation boundary. Slice 4.4 must replace temporary ACTIVE-status base selection with the unique `ReviewEpisode.active_evidence_snapshot_id` authority.

## 2026-08-14 Checkpoint: Phase 3 Slice 3 In Progress

Current deterministic results, not yet a completed Phase 3 release:

- Real official parent catalogs now freeze exactly MG-K10-SAR III IN 7 / EX 16 and
  CMS-D001 II IN 6 / EX 30. Every parent has at least one unique rendered text range;
  all formal excerpts verify against the claimed physical page.
- Required pre-baseline procedure catalogs now contain 41 MG items (25 screening/run-in,
  16 baseline) and 50 D001 II items (23 screening, 27 across two baseline/randomization
  checkpoints). Study-drug handling, diary logistics, randomization action and D1
  post-dose safety collection are excluded.
- Exact source recovery can disambiguate repeated text only inside proven structural/
  physical bounds and can anchor a cross-page paragraph with a unique exact fragment.
  Adjacent-page interpolation remains degraded and cannot satisfy publication coverage.
- Required-procedure items now preserve a structured review stage rather than asking the
  semantic model to infer stage ownership from display text.
- The protocol Agent adapter and 12-check gate exist. DeepSeek V4 Flash max JSON-mode
  connectivity and same-session continuation passed a two-turn live probe in 2.82 seconds.

Pending before slice acceptance: complete calendar-unit time windows and deterministic
input-package assembly, run real MG/D001 semantic drafts through the Agent and gate,
independent Trellis review, full-repository regression, and cleanup/archive.

## 2026-08-14 Milestone: Phase 3 Slice 2 Implemented, Pending Independent Acceptance

Implemented the reviewed slice 2 boundary only:

- Added traceable protocol metadata candidates with deterministic source priority,
  template/protocol separation, conflict records, explicit identity confirmation,
  and independent identity authority versus rule-locator precision.
- Added paragraph/table-row/visit-column phase applicability, strict single-phase
  projection, and a seamless candidate gate requiring explicit design plus the same
  subject cohort; operation seamlessness, dose handoff, and new Phase III subjects
  do not qualify.
- Added `InterpretationSource`/`InterpretationConflict` authority checks: only the
  current amendment may change formal requirements; other interpretation material
  can clarify an ambiguous source only, with conflicts remaining publication blockers.
- Added the append-only ORM/repository mappings and Alembic `0005` migration, plus
  focused contract/property/storage/real-protocol read-only tests.

返修 evidence after the main-venue rejection:

- Table cells are now atomic paragraph source blocks. Row/visit-column aggregates
  inherit only when all local children agree; mixed/unknown aggregates are excluded
  from ordinary single-phase projections and retain child block IDs plus source spans.
- `PhaseApplicabilityBlock.text` remains source text. Single-phase display changes are
  derived only in `projection_text`; real MG/D001 projections contain zero opposite-
  phase markers in their consumer-facing text and zero opposite-only or mixed/unknown
  blocks. Shared source blocks that mention both phases remain explicitly marked as
  shared/comparison evidence.
- Metadata conflicts now compare only the highest formal/non-fallback priority layer.
  D001 formal `D001-02-002` no longer conflicts with filename fallback `CMS-D001`; the
  D001 template version `00` and formal protocol version `1.0` remain separate, with no
  spurious version/date confirmation.
- Added a synthetic large-table counterexample and stronger real-protocol text,
  source-ownership, and read-only hash/stat/directory assertions.

Verification: `tests/v2/protocols` 59 passed; `tests/v2` 396 passed; compileall and
`git diff --check` passed. Both real protocol source files were hash/stat/directory
checked before and after read-only extraction. Slice 3 Agent deconstruction, API,
frontend, subject OCR, and clinical eligibility review remain unstarted. Independent
acceptance is still required before treating this slice as released.

## 2026-08-13 Milestone: Phase 1 Frontend Shell Accepted, Phase 1.5 User Gate

Completed:

- Built the no-login React/Vite frontend shell against frozen `fixture/v1` and a typed stub repository, without reading legacy Markdown or old SPA state.
- Implemented nine Chinese-first work surfaces: 今日工作、项目看板、方案工作台、受试者与资料、入排工作台、行动中心、报告、任务与系统、系统帮助。
- Added risk-first Patient Profile, staged rule/evidence/action workbench, parent-child rule rollups, evidence precision, responsibility/action detail, deep links, narrow layout and keyboard paths.
- Independent Kimi K3 visual review first blocked the phase on an `undefined` time-window defect, then accepted the corrected shell in the same session. Codex closed two additional nonblocking findings before archival.

Important root causes retained:

- The time-window defect came from a Wire contract that assumed obsolete fields instead of the frozen fixture's anchor/direction/bounds model. Contract, ViewModel, mapper, UI and regression coverage were corrected together.
- A protocol-diff path bypassed the shared display-code mapper and leaked `REQ-02`; all user-facing required-check codes now display as `必做-xx` while internal IDs remain unchanged.
- Hash navigation plus `networkidle` can measure the prior/loading page and produce false visual-test passes. Route checks now await the new page heading, key content and loading-state exit.
- CSS `body.zoom` does not reproduce browser zoom media-query behavior. The acceptance test now uses the equivalent CSS layout viewport for a 1440 physical display at 150%/200%.

Verification:

- 19 unit/component test files, 137 tests passed.
- Build passed; known fixture-bundle warning remains nonblocking for this read-only phase.
- Playwright: 153 passed, 27 viewport-specific skips, 0 failed across 1280/1440/1920/390, keyboard, evidence paths, accessibility and screenshots.
- 38 screenshots regenerated; Codex visually accepted representative desktop, narrow and 200% equivalent-zoom pages.

Current hold point:

- Phase 1 is complete. The local trial site remains at `http://127.0.0.1:4173/` for Phase 1.5.
- User must compare 今日工作 vs 项目看板 and complete the scripted workflow UAT before Phase 2.
- Do not begin the database, real OCR/LLM, durable Graph workflow or legacy migration until the user explicitly accepts Phase 1.5.

## 2026-08-12 Milestone: Launcher Recovery And V2 Design Approval Checkpoint

User request:

- Restore the desktop launcher, then take over and reassess the complete enrollment-review workflow before another large implementation pass.
- Add a source-traceable Patient Journey covering demographics, disease state/course, medical history, medication/treatment timelines, and eligibility-related risk markers.
- Evaluate the supplied comparator UI and whether Graph engineering/multi-Agent orchestration is appropriate.
- Inventory code, documents, prior sessions, test evidence, runtime artifacts, and previous pitfalls; ask multi-round product questions before finalizing the design and implementation plan.

Launcher repair:

- Root cause: port `8900` was occupied by another local service, while the old launcher treated any HTTP 200 health response as the enrollment-review app.
- The enrollment health endpoint now exposes `service=enrollment-review-app` and `version=2.0.0`.
- Repository and desktop launchers now select/persist a free port in `8901-8910` and validate service identity.
- Live service verified at `http://127.0.0.1:8901`; launcher syntax and identity checks passed.
- Regression test added; full suite passed 131 tests with 1 optional-fixture skip.

Discovery conclusion:

- The current product is a useful file-driven prototype, but not yet a versioned clinical-fact, Patient Journey, durable workflow, or multi-role adjudication platform.
- Repeated clinical errors share structural causes: Markdown rules do not encode AND/OR/NOT, time anchors, exceptions, evidence requirements, or investigator judgment as executable components; model-text corrections have accumulated as post-processing guards.
- The next architecture should preserve upload/OCR adapters, real project samples, error regressions, phase separation, stage anchors, and compatible exports, while replacing file/Markdown business truth, the single top-level verdict, request-bound batch processing, and vague unresolved-action labels.
- Graph engineering is recommended for state, branching, recovery, retries, and human gates. It must not become a free-running Agent swarm or the clinical source of truth.
- Preliminary Agent boundary: Evidence Normalizer, Eligibility Assessor, independent Safety/Provenance Critic, deterministic validators, and structured action routing. The app is AI-led but is not the final enrollment decision authority.

Durable evidence:

- Discovery and first-round questions: `docs/REARCHITECTURE_DISCOVERY_20260812.md`.
- Task contract and loop log: `context/enrollment_review_rearchitecture_20260812_context.md`.
- Current runtime screenshots: `output/product_audit_20260812/`.

Round-one decisions:

- Target is a single-Mac, single-user local application; do not design a multi-user approval system.
- The app should lead the review and state what is not met or unresolved. Every such item must specify which party should provide which exact evidence, description, judgment, or follow-up before the rule can be clarified.
- Same-subject incremental and full upload modes are both required.
- This product's Patient Profile covers all longitudinal events from the earliest evidenced point through prescreen/screening/baseline, with eligibility links and source traceability.
- Protocol/amendment version is authoritative. Only an amendment changes standards; Q&A/letters/email/medical interpretation may clarify ambiguity and must be warned when contradictory.

Current hold point:

- Second-round decisions are complete: delete login/multi-account behavior; support immutable full snapshots and deduplicated incremental uploads; preserve stage history; allow source-preserving single-user OCR/fact correction; use non-final stage judgments; keep full test data but highlight only eligibility-relevant/abnormal/borderline/trending results on the Patient Profile first screen.
- The system must distinguish incomplete medical-record documentation from genuinely absent procedures or source files. It must not convert a history item omitted from the screening note into a definitive absence or a generic request for prior source documents.
- Do not begin the large rearchitecture until the third-round questions in `docs/REARCHITECTURE_DISCOVERY_20260812.md` resolve history-evidence semantics, fixed action owners, dashboard aggregation, action closure, legacy migration, and visual-prototype sequencing.

Third-round decisions:

- Screening-record positive history/long disease duration is usable current evidence but requires an enhanced provenance reminder.
- Remove subject as an action owner; all collection, questioning, documentation, analysis, and closure route through investigator-side, CRC, CRA, or sponsor medical/project roles.
- Dashboard uses primary status plus categorized issue counts.
- The system may auto-close actions after new evidence/recalculation; the user may override, with a complete state-change record.
- Legacy projects are read-only counterexample anchors. The new architecture creates fresh projects from the protocol and reruns the full workflow rather than mutating legacy project state.
- Build and approve an interactive workflow prototype before data-layer and Graph implementation.

Independent conference and final architecture:

- Clinical and architecture participants independently reviewed the confirmed requirements and current source/runtime constraints.
- Shared conclusion: the principal defects are weak clinical representation, non-durable state and missing deterministic gates; adding more free-running Agents would not solve them.
- Selected runtime spine: SQLite/WAL + durable Job/Checkpoint + explicit state machine. Protocol Deconstructor, Evidence Normalizer and Eligibility Assessor are bounded typed semantic calls; Safety/Provenance Critic is conditional, veto/downrank/action-only.
- Evidence conflicts hard-block the contested component and remain side-by-side; V2 removes the old prior-source auto-preference.
- Auto-close is gap-specific and source-linked in a new ReviewRun. Arbitrary uploads never close actions; manual override/reopen remains fully audited.
- Old projects remain read-only counterexample anchors. V2 projects start from the original protocol and rerun the complete workflow.

Final artifacts:

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `reviews/codex_conference_enrollment_review_design_conference_20260812_review.md`
- `metrics/enrollment_review_design_conference_20260812_conference_metrics.md`

Current hold point:

- Product clarification and independent conference are complete.
- Wait for explicit user approval of the final design and Phase 0-9 plan before starting V2 implementation.
- No V2 business code, old project state or clinical review result has been changed at this checkpoint. The repaired legacy service remains available at `http://127.0.0.1:8901` when running.

## 2026-08-13 Milestone: Phase 1.5 Acceptance Method Changed

User decision:

- The user will not organize or personally perform a human medical-monitor UAT round for the Phase 1 prototype.
- Phase 1.5 final acceptance is instead performed by multiple independent model reviewers role-playing a lazy but expert Chinese senior clinical-trial medical monitor in the real local browser.
- Reviewers must freely explore clinical comprehension, evidence traceability, rule hierarchy, Patient Profile, interaction and visual quality. They must distinguish current synthetic-prototype behavior from Phase 2-8 capabilities that are not implemented yet.
- Exact model names requested by the user are used only when the current global route manifest registers them; actual provider, model, session and fallback evidence must be retained and no route may be impersonated or force-bypassed.

Completed technical preparation:

- Phase 1.5 scripted tasks, reset path, desktop launcher and independent Chinese UAT recorder are implemented and verified.
- The former human-UAT task was closed as technical preparation and archived. Its historical evidence remains immutable; its requirement for at least ten human participants was superseded by the later user decision.

Current hold point:

- Active task: `.trellis/tasks/08-13-phase1-5-agent-monitor-uat`.
- Phase 2 remains blocked until independent visual/interaction and clinical/evidence role reviews complete, current-phase blockers are corrected and retested, and Codex records a final acceptance decision.

## 2026-07-02 Milestone: Hermes Multi-Model UI/Product Audit And Narrow Fix Loop

User request:

- Use the Codex x Hermes cooperation mechanism and the requested model routes `qwen3.7-plus`, `minimax-m3`, and `mimo-v2.5`.
- Run a full-system, full-flow critique of the enrollment-review app for bugs, aesthetics, UI interaction, operational logic, and alignment with the user's original requirements.
- Organize cross-model discussion, form consensus, then tune/debug/retest in a LOOP.

Workflow performed:

- Created Codex/Hermes task packet `enrollment_fullflow_model_audit_20260701`.
- Built bounded review context:
  - `context/enrollment_fullflow_model_audit_20260701_context.md`;
  - Playwright route snapshots under `output/model_audit_20260701/screenshots/`;
  - UI contact sheet `output/model_audit_20260701/screenshots/ui_contact_sheet.png`;
  - UI snapshot summaries under `output/model_audit_20260701/snapshots/`.
- Model outputs:
  - Qwen 3.7 Plus: `runs/hermes_enrollment_audit_qwen37_20260701.md`;
  - MiniMax M3 fallback no-tool audit: `runs/hermes_enrollment_audit_minimaxm3_20260701.md`;
  - MIMO V2.5 fallback no-tool audit: `runs/hermes_enrollment_audit_mimo25_20260701.md`.
- Codex consensus and review artifacts:
  - `runs/hermes_enrollment_model_consensus_20260702.md`;
  - `reviews/codex_enrollment_fullflow_model_audit_20260701_review.md`;
  - `metrics/enrollment_fullflow_model_audit_20260701_metrics.md`.

Important route/pitfall notes:

- Qwen generated a usable visual/text audit but was slow and produced little stdout.
- MiniMax and MIMO long file-read/write prompts timed out; both were rerun as bounded no-tool advisory reviewers.
- MiniMax proposed moving baseline/randomization anchor date to project-level metadata; Codex rejected this because each subject can have a different baseline/randomization date. Keep subject-level phase anchor dates.
- Do not blindly adopt model suggestions. Codex must verify against clinical workflow, source code, and rendered UI.

Accepted and implemented fixes:

- Mobile table usability:
  - Before patch, mobile subject list and report pages clipped table content while page overflow was hidden.
  - `.table-wrap` now uses horizontal scrolling with touch scrolling, and mobile-only hints tell users to swipe horizontally.
  - Desktop width behavior was preserved.
- User-facing terminology cleanup:
  - Replaced visible `LLM` wording with `系统` / `智能审核` / `解析反馈`.
  - Replaced primary `Markdown` labels with `导出报告` / `报告导出` / `个人报告`, while preserving `.md` export files because Markdown report output is still an explicit requirement.
- Phase selector clarity:
  - The subject-list stage dropdown is now labeled `批量操作阶段`.
  - Explanatory copy says it affects only batch review/rerun/export; each row can directly enter its screening or baseline phase.

Validation completed:

- `python3 -m compileall app tests scripts`
  - passed.
- Extracted frontend JS from `static/index.html`, then `node --check /tmp/enrollment_index.js`
  - passed.
- `python3 -m unittest discover -s tests`
  - 130 tests passed, 1 skipped fixture.
- Post-patch Playwright metrics:
  - mobile subject list `.table-wrap`: `clientWidth=362`, `scrollWidth=1741`, `scrollLeft` changed to `1379`, `overflowX=auto`;
  - mobile report `.table-wrap`: `clientWidth=362`, `scrollWidth=904`, `scrollLeft` changed to `542`, `overflowX=auto`;
  - desktop subject list: no body overflow and no horizontal scroll needed;
  - checked visible text had no `LLM` or primary `Markdown` labels.

Residual risks:

- Health check during this audit returned `{"status":"ok","omlx":false,"deepseek":true}`. This patch did not fix launcher/oMLX startup; run a separate launcher test before claiming full offline OCR readiness.
- Mobile is now reachable by horizontal scrolling, but a touch-native card layout remains future product work.
- The large single-file frontend remains a maintainability risk; do not refactor it without a separate scoped plan.

## 2026-06-25 Milestone: MG-K10-SAR III New Project, Center 31 First Batch, Parser QC Fixes

User request:

- Create/test a new MG-K10-SAR project from the uploaded protocol and audit `Ⅲ期` only.
- Use source documents under `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/13. CFDI核查/自查/入排/各中心原始入排资料`.
- Run `31 河北省中医院` subjects as the first batch.

Implemented run:

- Created project `MG-K10-SAR-III` from `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`.
- Project metadata after extraction:
  - project code `MG-K10-SAR-III`;
  - protocol ID `MG-K10-SAR-001`;
  - version/date `V2.1 / 2025-09-19`;
  - fixed stage `Ⅲ期`.
- Center 31 subjects processed:
  - `31001`, `31006`, `31008`, `31010`, `31013`, `31014`, `31015`, `31016`, `31017`, `31018`.
- Each subject was processed through both `screening_run_in` and `baseline_randomization`.
- Final baseline project-list verdicts:
  - `fail`: `31001`, `31010`, `31015`;
  - `investigator`: `31008`, `31014`;
  - `insufficient`: `31006`, `31013`, `31016`, `31017`, `31018`.
- Key run logs:
  - `projects/MG-K10-SAR-III/rerun_logs/mgk10sar_iii_center31_batch_20260625_135429.json`;
  - `projects/MG-K10-SAR-III/rerun_logs/mgk10sar_iii_center31_qc_after_backfill_20260625_144142.json`;
  - `projects/MG-K10-SAR-III/rerun_logs/MG-K10-SAR-III_center31_baseline_markdown_20260625_144817.md`;
  - backfill logs under `projects/MG-K10-SAR-III/rerun_logs/backfill_center31_*_20260625_*.json`.

System issues found and fixed during this batch:

- Protocol schedule-stage inference had treated a shared MG-K10 II/III schedule table as `Ⅱ期` because it inferred phase from generic terms such as treatment/safety follow-up. Fixed stage inference so generic schedule terms do not imply II, and scoped universal phases to the selected project stage.
- LLM deconstruction header could hallucinate protocol IDs such as `MG-K10-SAR-301（假设）`. Added header sanitization from extracted protocol metadata.
- Parser guards were using hard-coded rule IDs such as `EX-15` and `EX-11` from D001 semantics. MG-K10 reuses those IDs for different criteria, so the parser incorrectly downgraded MG-K10 `EX-15` alcohol to investigator judgment. Fixed compound-condition guards to be semantic, not ID-only.
- Parent rows could include cross-rule contamination, for example EX-07 parent mentioning EX-09g. Parent rows are now recomputed only from same-prefix children.
- If a model omits parent rows but outputs child rows, the parser now inserts inferred parent rows and recomputes their verdicts. This restored all MG-K10 reports to the expected 56 rule rows.
- Child rows that explicitly say the current child did not trigger, while redirecting residual concern to another child such as `EX-09g`, now keep the current child local and pass the current child.
- Current-stage evidence gaps, such as missing D1/baseline blood chemistry while screening ALT/AST are below the exclusion threshold, are downgraded from hard fail to `insufficient` with a specific evidence-gap explanation, not a generic researcher-compound warning.
- Syphilis exception logic is now semantic and not limited to D001 `EX-22`; any syphilis-specific antibody-positive row requires both non-specific antibody negativity and explicit cured-prior-infection judgment.
- `review_raw.md` is now preferred for backfill when available, so old normalized reports do not contaminate new parser logic. `review_report.md` remains the fallback if raw output is absent.
- ASCII `-` in the verdict cell is now mapped to `na`.
- Markdown export wording now uses the neutral wording `提醒项`, not `低干预` or `低强度`.

Validation completed:

- `python3 -m unittest tests.test_phase_workflow`
  - 97 tests passed, 1 skipped.
- `python3 -m compileall app tests scripts`
  - passed.
- Local service restarted from the desktop launcher and health returned `{"status":"ok","omlx":true,"deepseek":true}`.
- API verification showed 10 center-31 subjects in `MG-K10-SAR-III`, all `reviewed`, all center code `31`, all ICF date `2025-07-02`.
- File QC confirmed all 20 stage reports have 56 rule rows and no scanned internal phrases such as `疾病存在、异常存在或用药存在本身不等于完整排除触发`, `definitive`, `按要求排除`, `仅III/仅Ⅲ`, or cross-parent `EX-09g` leakage.

Operational notes:

- First-pass OCR is the time bottleneck: about 43-61 pages per subject and roughly 94-143 seconds per first phase. Baseline reruns usually hit cache fully, except subjects with an extra baseline blood routine file, where only the new page was OCRed.
- The center-31 batch was run serially for QC traceability. OCR now reports max 8 VLM calls, and cache reuse worked as expected.
- `31017` included one JPG in prior records; it uploaded and OCRed without pipeline failure. Follow-up QC should still inspect whether its content materially contributes to historical evidence.

## 2026-06-22 Milestone: Historical Diagnosis/Duration Provenance Warning

User correction:

- For protocol criteria requiring historical facts or duration, such as prior allergic rhinitis diagnosis for more than 3 years, earliest symptom onset more than a certain period ago, prior treatment, prior medication exposure, prior testing, or prior surgery, screening/baseline narratives are not enough to prove the historical fact by themselves.
- Prior medical records, diagnosis certificates, discharge summaries, historical test reports, prescriptions, or older progress notes must have higher evidentiary priority for these historical facts.
- If only screening/baseline records contain a transcribed history statement and no older source file is available, the system should warn the reviewer instead of treating the item as a plain pass.

Implemented decision:

- Added a distinct internal rule verdict `pass_verify`.
- LLM output should use `✅通过（需验证：病史来源需溯源验证）` when a historical diagnosis/duration item is apparently met but supported only by screening/baseline history narrative.
- `pass_verify` does not downgrade the overall report by itself. If there is no `fail` / `insufficient` / `investigator`, the subject overall verdict remains `pass`.
- Project/center Markdown exports do not include `pass_verify` items in待处理明细; they count them separately as `溯源提醒`. Subject exports continue to show all rule rows.
- Frontend report pages show a separate“溯源提醒” success-style callout, distinct from ordinary“证据不足”.
- The evidence bundle and review system prompt now use contextual evidence hierarchy:
  - current-visit facts such as ICF, current vitals, current lab/exam, and current scores prioritize screening/baseline source documents;
  - historical facts and duration prioritize historical source documents.

Implementation notes:

- `app/pipeline/reviewer.py`
  - added historical fact provenance instructions to the review system prompt and user prompt;
  - parser now recognizes `pass_verify`;
  - parser now checks“不通过/fail” before generic“通过/pass” to avoid false pass mapping.
- DeepSeek V4 Pro prompt decision:
  - local `.env` already uses `REVIEW_MODEL=deepseek-v4-pro` and `REVIEW_BACKEND=deepseek`;
  - DeepSeek official docs say JSON Output requires `response_format`, prompt wording containing json, and a JSON example, but may occasionally return empty content;
  - current review artifacts and parsers are Markdown-table based, so the safer change is tightening the existing Markdown contract rather than switching output protocol midstream;
  - DeepSeek official docs also state thinking mode is enabled by default for `deepseek-v4-pro`; the prompt therefore says not to output chain-of-thought and asks only for final conclusion plus source quotes.
- `app/pipeline/bundler.py`
  - revised the evidence hierarchy notice to separate current facts from historical facts.
- `app/models.py`
  - added markdown rendering for `pass_verify`.
- `app/markdown_export.py`
  - added `pass_verify` labels and `溯源提醒` summary counts, while excluding `pass_verify` from issue sections.
- `static/index.html`
  - added `pass_verify` badges and report callout.
- `tests/test_phase_workflow.py`
  - added regression coverage for `pass_verify`, plain“不通过”, prompt wording, and Markdown issue exclusion.

## 2026-06-22 Milestone: Project Info Management, Global Centers, Shared Read-Only, Markdown Export

User requirements addressed:

- Added a project information management page as a project tab and project-list entry.
  - Project name, project code, protocol ID, protocol version/date, source filename, and fixed study stage can be edited.
  - Only the project creator or `admin` can edit project metadata or rules.
  - Project code changes safely rename the project directory and update subject `project_code` values.
- Changed the permission model after user correction:
  - all logged-in users can read all projects, subject lists, and existing review reports;
  - project mutation remains limited to project creator or `admin`;
  - subject upload, OCR reset, rerun/re-review, and subject deletion are limited to the subject creator/uploader or `admin`;
  - legacy subjects without `owner_username` remain modifiable by the project creator/admin, so old data is not silently taken over by another user.
- Added global center roster support:
  - centers are now stored globally in `projects/_system/centers.json`, not inside one project;
  - all users can select a center created by another user;
  - ordinary users can modify/delete only their own centers; `admin` can modify all;
  - subject creation and subject upload can set `center_code` and `center_name`, and new centers become reusable globally.
- Added center roster management in the project information page:
  - manual add/edit/delete center rows;
  - batch import from Excel/CSV/TXT or pasted text;
  - center deconstruction endpoint first parses structured rows, then asks the deconstruction LLM to refine the draft, falling back to the structured draft if LLM refinement fails.
- Added Markdown export:
  - project-level Markdown report;
  - center-level Markdown report;
  - subject-level Markdown report;
  - project/center reports omit passed rules and focus on not-qualified, evidence-insufficient, investigator-judgment, or missing-report items;
  - subject reports include every rule row.
- Updated help page:
  - global center workflow;
  - shared read-only vs owner-write permissions;
  - subject upload center selection;
  - batch processing limited to owned/modifiable subjects;
  - Markdown export differences by project/center/subject scope.

Files changed:

- `app/authz.py`
  - separated read access from modify access;
  - added subject-level ownership checks.
- `app/models.py`
  - added `owner_username`, `center_code`, and `center_name` to `SubjectInfo`.
- `app/centers.py`
  - new global center roster helpers and Excel/CSV/TXT/text parsing.
- `app/markdown_export.py`
  - new Markdown report generation for project, center, and subject scopes.
- `app/router/projects.py`
  - project metadata PATCH endpoint;
  - global center list/deconstruct/save endpoints;
  - project/center/subject Markdown export endpoint;
  - project mutation endpoints now require project creator/admin.
- `app/router/subjects.py`
  - subject creation/upload stores center and owner;
  - subject mutation endpoints require subject owner/admin.
- `app/router/pipeline.py`
  - OCR/review/process endpoints now require subject owner/admin because they mutate derived outputs.
- `static/index.html`
  - added project info tab, center management, center import, Markdown export tab, upload/add-subject center inputs, read-only button logic, and help updates.
- `tests/test_phase_workflow.py`
  - updated project visibility tests for shared read-only model;
  - added subject ownership and global center tests.

Validation completed:

- `python3 -m compileall app tests scripts`
  - passed.
- Extracted JS from `static/index.html`, then `node --check /tmp/enrollment_index.js`
  - passed.
- `python3 -m unittest discover -s tests`
  - 27 tests passed, 1 skipped because the local MG-K10-SAR/06003 OCR cache fixture is absent.
- Service health:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}` during QC.
- Playwright visual/API QC:
  - desktop `1440x980` and mobile `390x844`;
  - routes covered: audit project list, MG-K10-SAR project info/global centers, Markdown export, add-subject modal, upload modal;
  - page-level horizontal overflow was 0 on checked pages;
  - browser console errors: 0;
  - Markdown export API returned a project Markdown report with expected headings.

Screenshot/artifact paths:

- `output/playwright/shared-qc-desktop-audit-list.png`
- `output/playwright/shared-qc-mobile-audit-list.png`
- `output/playwright/shared-qc-desktop-project-info-centers-v2.png`
- `output/playwright/shared-qc-mobile-project-info-centers.png`
- `output/playwright/shared-qc-desktop-markdown-export.png`
- `output/playwright/shared-qc-mobile-markdown-export.png`
- `output/playwright/shared-qc-desktop-add-subject-center-modal.png`
- `output/playwright/shared-qc-upload-center-modal-targeted.png`
- `output/playwright/shared-qc-markdown-project.md`
- `output/playwright/shared-permissions-center-export-qc.json`

Operational notes and pitfalls:

- A first implementation treated centers as project-scoped. The user corrected this: centers are global and reusable across projects/users. The code now stores them under `_system`.
- A first permission pass accidentally put write checks on read-only project endpoints; this was corrected so all logged-in users can read projects/phases/reports.
- The service launcher reported the old service as running while a subsequent curl briefly failed. For QC, the app was run through `scripts/run_enrollment_review_terminal.command`; before final handoff, start the visible service window rather than leaving a Codex tool session as the only service process.
- Existing MG-K10-SAR subjects created before `owner_username` exist as legacy rows; they are treated as project-owner/admin editable.

## 2026-06-22 Milestone: Phase Is Project Identity, Subject List No Stage Picker, Simple ER Icon

User requirements addressed:

- A selected protocol phase is now part of the project identity, not a subject-list audit option.
  - If a protocol contains both `Ⅱ期` and `Ⅲ期`, the user must choose the phase during protocol deconstruction.
  - Newly created/saved multi-phase protocol projects use a phase suffix in the project code, such as `MG-K10-SAR-II` or `MG-K10-SAR-III`.
  - The saved project workflow is scoped to the selected phase, with `study_stages` reduced to one value and `requires_study_stage_selection=false`.
  - Subjects belong to that project only; they are not shared across II/III phase projects.
- The subject list/project page no longer shows a `研究阶段` dropdown.
  - It now only shows the audit timepoint/stage dropdown, such as `筛选/导入期` or `基线/随机前`.
  - The page displays a fixed project-phase note, for example `项目期别：Ⅲ期（解构时已固定，受试者不与其他期别项目共享）`.
  - If an old legacy project still has a mixed-phase workflow and no fixed `study_stage`, the UI blocks temporary subject-page phase selection and tells the user to re-deconstruct/save as a single-phase project.
- The logo was simplified again after visual QC:
  - removed the `入排审核` text;
  - removed the `ELIGIBILITY REVIEW` text;
  - removed the bottom ECG/horizontal line;
  - retained only a compact ER shield/check/search icon.

Files changed:

- `app/router/projects.py`
  - added helpers to treat selected phase as a project-code suffix for multi-phase protocols;
  - fixed the edge case where an already scoped workflow still has `protocol_study_stages`, so saving a draft still produces `-II`/`-III`;
  - persists project workflow after deconstruction as single-phase scoped workflow.
- `app/phases.py`
  - `load_review_workflow()` now reads `config.json`; if `study_stage` is fixed, returned workflow is single-phase and does not ask for phase selection.
- `app/router/pipeline.py`
  - review/process endpoints default to the project config's fixed `study_stage`.
- `static/index.html`
  - removed the subject-list research-stage selector;
  - added fixed project-phase display and legacy mixed-phase warning;
  - updated help text so monitor workflow says phase is selected during deconstruction, not during subject audit.
- `static/header_logo.svg`
  - simplified to icon-only ER logo.
- `tests/test_phase_workflow.py`
  - added coverage for `-II`/`-III` project-code suffixing, including already-scoped workflows;
  - added coverage for workflow scoping from project config;
  - skipped the MG-K10-SAR/06003 evidence bundle cache test when the local OCR cache fixture is absent.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 26 tests passed, 1 skipped because current local MG-K10-SAR/06003 fixture has raw files but no OCR `cache` directory after prior delete/rebuild testing.
- `python3 -m compileall app tests scripts`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- Source scan confirmed no remaining `studyStageSelect`, old `header_logo.png`, logo text, logo English text, or `erLine` artifacts.
- Service restarted through the desktop-entry fallback path:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`.
- API verification:
  - `/api/projects/MG-K10-SAR/phases` returned `study_stages=["Ⅲ期"]` and `requires_study_stage_selection=false`.
- Playwright visual QC:
  - desktop and mobile project page had no `studyStageSelect`;
  - `reviewPhaseSelect` remained present;
  - fixed project-phase text was visible;
  - page-level horizontal overflow was 0;
  - logo used `/static/header_logo.svg`.

Screenshot artifacts:

- `output/playwright/qc-desktop-header-logo-crop.png`
- `output/playwright/qc-mobile-header-logo-crop.png`
- `output/playwright/qc-desktop-project-fixed-stage-logo.png`
- `output/playwright/qc-mobile-project-fixed-stage-logo.png`

Operational notes and pitfalls:

- Existing legacy project `MG-K10-SAR` is still kept at its original path to avoid breaking current 06002/06003/06004 test data, but its workflow is now treated as fixed `Ⅲ期` because `config.json` has `study_stage="Ⅲ期"`.
- New multi-phase deconstruction/save flows should create phase-specific project codes (`-II`/`-III`), so separately deconstructed phases do not share subject folders.
- The local service usually cannot stay up as a hidden child process from Codex; the reliable path is the existing launcher fallback that opens a visible Terminal service window. Keep that service window open.

## 2026-06-22 Milestone: Standalone Phase Rules, Re-Deconstruction Layout QC, ER Logo SVG

User requirements addressed:

- After the user selects `Ⅱ期` or `Ⅲ期`, protocol deconstruction must treat that selected phase as an independent project ruleset.
  - Do not mix the other phase into formal IN/EX rules.
  - Do not compare against the other phase.
  - Do not output wording such as `仅Ⅲ期`, `适用期别：Ⅲ期`, `按本次所选Ⅲ期编号`, or `与Ⅱ期对应条款一致/差异`.
- MG-K10-SAR saved III期 rules were cleaned to remove the prior `Ⅱ期对应/实质一致` notes while preserving the official III期 parent IN count and EX count.
- The re-deconstruction project selector layout was fixed from the root:
  - project select now uses compact option labels;
  - full long protocol titles wrap inside the project summary card;
  - card/grid/flex containers now use `min-width:0`, wrapping, and bounded widths to prevent page-level horizontal overflow.
- The old PNG logo was removed and replaced with one self-contained SVG asset:
  - `static/header_logo.svg`;
  - the asset is now an icon-only ER mark after later visual QC;
  - the frontend does not assemble the logo from a separate image plus adjacent logo text.

Files changed:

- `app/deconstructor.py`
  - updated the LLM deconstruction prompt to require standalone selected-phase rules;
  - strengthened `sanitize_selected_stage_scope_language()` to remove mixed-stage notes independent of word order.
- `app/router/projects.py`
  - updated re-deconstruction stage instructions sent to the LLM.
- `projects/MG-K10-SAR/criteria_rules.md`
  - removed mixed II/III explanatory notes from the saved III期 rules.
- `static/index.html`
  - replaced logo reference with `/static/header_logo.svg`;
  - fixed project selector, project summary, project header, rule toolbar, workbench grid, card, and mobile wrapping behavior;
  - mapped backend `needs_evidence` verdict to the Chinese `待补证` badge.
- `static/header_logo.svg`
  - new single-file ER logo.
- `tests/test_phase_workflow.py`
  - updated tests for standalone selected-phase rules and SVG logo serving.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 23 tests passed.
- `python3 -m compileall app tests scripts`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- MG-K10-SAR rules grep check:
  - no `仅III/仅Ⅲ`, `适用期别`, `对应条款`, `对应避孕`, `对应知情`, `实质一致`, `按本次所选`, `另一阶段`, `另一期别`, or `一致/差异` remained in `projects/MG-K10-SAR/criteria_rules.md`.
- Live service restored through the desktop-entry fallback path:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`.
- Browser QA via Playwright:
  - 18 screenshots across desktop `1440x980` and mobile `390x844`;
  - routes covered: login, task home, help, first-deconstruct, re-deconstruct, audit, project subjects, upload modal, project rules, and 06004 screening report;
  - all routes used `/static/header_logo.svg`;
  - browser console had 0 errors;
  - page-level horizontal overflow count was 0.
- MG-K10-SAR long-title re-deconstruction专项视觉检查:
  - desktop and mobile screenshots both had `docScrollWidth == innerWidth`;
  - project select displayed `MG-K10-SAR · MG-K10-SAR-001 · V2.1 · 2025-09-19 · Ⅲ期`;
  - full long project title wrapped inside the summary card rather than stretching the page.

Screenshot artifacts:

- `output/playwright/visual-qc-summary.json`
- `output/playwright/qc-desktop-re-deconstruct-mgk10.png`
- `output/playwright/qc-mobile-re-deconstruct-mgk10.png`

Operational notes:

- The service is currently running on port `8900` from the visible service-window fallback. Keep that Terminal service window open.
- The desktop launcher remains `/Users/smkzw/Desktop/启动入排审核系统.command`.

## 2026-06-21 Milestone: Login, Deconstruction Workspaces, Batch Audit Entry, System Logo

User requirements addressed in this milestone:

- Add a restrained custom system logo to the top-right of every page.
- Prevent generic protocol titles such as `临床研究方案` from being shown or saved as the project name.
- Add a lightweight local login system:
  - first entry requires registration;
  - username is required;
  - password is optional;
  - registration does not auto-login;
  - first registration shows a full-system help page before login.
- Split post-login entry into three explicit routes:
  - `#/first-deconstruct`: new project, first protocol deconstruction, cannot overwrite an existing project;
  - `#/re-deconstruct`: existing project protocol re-deconstruction, with current project info, upload area, LLM feedback, original vs revised rule panes, change summary, save/cancel;
  - `#/audit`: existing project audit list and batch audit guidance.
- Keep MG-K10-SAR phase-aware audit controls visible:
  - stage selector shows `Ⅱ期` and `Ⅲ期`;
  - review phase selector shows screening/run-in and baseline/randomization stages;
  - batch processing requires the phase/stage controls.

Files changed:

- `static/index.html`
  - unified header with `/static/header_logo.svg`;
  - login/register/help views;
  - task home with three work entry cards;
  - first deconstruction workspace;
  - re-deconstruction workspace;
  - audit project list and batch audit guide;
  - project-name display guard for generic protocol titles.
- `static/header_logo.svg`
  - replaced the previous CMS/康哲 asset with a custom ER icon.
- `app/main.py`
  - mounts `/static` with `StaticFiles`.
- `app/router/auth.py`
  - local lightweight auth endpoints.
- `app/router/projects.py`
  - re-deconstruction endpoint and generic-project-name save guard.
- `tests/test_phase_workflow.py`
  - added tests for generic project name guarding, static logo serving, and passwordless local auth.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 14 tests passed.
- `python3 -m compileall app scripts tests`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- `zsh -n scripts/start_enrollment_review.command`
  - passed.
- `zsh -n /Users/smkzw/Desktop/启动入排审核系统.command`
  - passed.
- Browser QA via Playwright against `http://127.0.0.1:8900`:
  - logo visible on register/login/help/task/first-deconstruct/re-deconstruct/audit/project pages;
  - first registration enters help page and remains logged out;
  - login reaches three-entry task home;
  - first-deconstruct page only offers `保存为新项目`;
  - re-deconstruct page shows original vs revised panes and project selector;
  - audit list shows MG-K10-SAR title as `MG-K10-SAR`, not `临床研究方案`;
  - MG-K10-SAR project page shows `Ⅱ期`/`Ⅲ期` selector and screening/baseline review phases;
  - browser console had 0 errors.
- Screenshot artifact:
  - `output/playwright/audit-list-with-logo.png`.

Operational notes:

- The temporary QA user `qa_codex` was removed after browser testing.
- If the app is already running from an old process, restart it so the new `/static` mount takes effect.
- The desktop launcher remains:
  - `/Users/smkzw/Desktop/启动入排审核系统.command`.

Known continuation items:

- Continue full clinical-flow regression on MG-K10-SAR III期 for 06002/06003/06004 after this UI refactor, especially classified upload, OCR, phased review, and revised protocol deconstruction behavior.
- The current UI still uses the existing subject-level report rendering; deeper reviewer-oriented HTML report redesign should remain source-bound and avoid exposing internal evidence IDs or model/debug terms.

## 2026-06-21 Milestone: Project Ownership, Admin Account, One-Time Help

User requirements addressed:

- Add a super administrator account:
  - username: `admin`
  - password: `20121116`
  - role: `admin`
  - can view, add, edit, audit, and delete all projects.
- Ordinary users can only view and operate projects they created.
- Ordinary users cannot see other users' projects in project lists.
- Ordinary users can delete their own projects only.
- Add a first-login vs repeat-login mechanism:
  - normal user records now include `help_seen`;
  - first login shows the full-system help page if `help_seen=false`;
  - clicking the help completion button marks the user as read;
  - later logins no longer force the first-use help page.

Implementation notes:

- `app/authz.py` is the shared authentication/authorization layer.
- API requests carry:
  - `X-Enrollment-User`
  - `X-Enrollment-Token`
- SSE processing uses query params `user` and `token` because `EventSource` cannot send custom headers.
- `ProjectConfig` now includes `owner_username`.
- Existing legacy projects without `owner_username` are accessible to admin, and to the single registered normal user when there is exactly one normal user. This preserves current MG-K10-SAR access for the existing local `smkzw` account while still hiding projects once explicit owners are assigned.
- Frontend delete buttons are display-only affordances; backend authorization is the source of truth.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 15 tests passed.
- `python3 -m compileall app tests`
  - passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- Live API checks against `http://127.0.0.1:8900`:
  - admin login returned role `admin` and `requires_help=false`;
  - normal `smkzw` login returned role `user`;
  - admin project list included `CMS-D001`, `MG-K10-SAR`, and `test01`;
  - normal `smkzw` still sees current legacy projects under the single-normal-user compatibility rule.
- Browser QA via Playwright:
  - admin login did not route to the help page;
  - header showed `admin（超级管理员）`;
  - audit list showed all projects;
  - each project card showed a `删除项目` button for admin.

Pause note:

- User instructed: pause now and resume only after explicit user instruction.
- Current implemented scope before pause:
  - `admin` / `20121116` super administrator exists as a built-in account.
  - Normal users have token-based sessions, `help_seen` first-login tracking, and role `user`.
  - Project ownership is stored in `owner_username`.
  - Project APIs, subject APIs, pipeline APIs, and report/evidence APIs enforce owner/admin access on the backend.
  - Frontend stores `enrollmentReviewUser`, `enrollmentReviewToken`, and `enrollmentReviewRole`.
  - Frontend shows project delete controls only when backend returns `can_delete=true`.
  - Admin sees all projects and delete controls for all projects.
  - Normal users see only owned projects; legacy projects without owner are visible to the single normal local user for compatibility.
- Current verification before pause:
  - `python3 -m unittest discover -s tests`: 15 tests passed.
  - `python3 -m compileall app tests`: passed.
  - `node --check` on extracted frontend script: passed.
  - live admin API check: admin sees `CMS-D001`, `MG-K10-SAR`, `test01`, all with `can_delete=true`.
  - browser console check: 0 errors.
- Local service state at pause:
  - Desktop launcher was used to restart the service.
  - `http://127.0.0.1:8900/api/health` returned OK before pause.
  - Service may still be running from the desktop launcher; confirm with `lsof -nP -iTCP:8900 -sTCP:LISTEN` when resuming.

## 2026-06-21 Milestone: Stage-Specific Protocol Deconstruction and MG-K10-SAR III期 Regression

New user requirements addressed:

- Protocol deconstruction must keep parent IN/EX counts, order, and numbering exactly aligned with the protocol for the selected study stage.
- If a protocol contains both II/III phases, the system must ask the user to choose II期 or III期 before deconstruction; it must not mix both phases into one ruleset.
- Complex parent criteria may have subcomponents such as `IN-04a`/`IN-04b`, but subcomponents must stay under the official parent ID and must not create new parent IN/EX numbers.
- Baseline-and-earlier required procedures from the schedule table remain in a separate workflow-check appendix and must not change formal IN/EX counts.

Implementation changes:

- `app/deconstructor.py`
  - strengthened the LLM deconstruction prompt with exact parent numbering/count rules;
  - added explicit selected-stage behavior for II/III protocols;
  - fixed DOCX criteria extraction to skip table-of-contents entries and use body headings;
  - supports `extract_docx_criteria(..., study_stage="Ⅲ期")`, which now returns MG-K10-SAR III期 as IN=7 and EX=16.
- `app/router/projects.py`
  - all deconstruction endpoints now accept `study_stage`;
  - multi-stage protocols return HTTP 409 with `study_stage_required` before deconstruction if no stage is selected;
  - new projects save `study_stage` in project config.
- `app/models.py`
  - `ProjectConfig.study_stage` added.
- `static/index.html`
  - first deconstruction, re-deconstruction, new-project modal, and project deconstruction modal now show a deconstruction-stage selector;
  - project cards and re-deconstruction project info display saved `解构期别`;
  - report links keep the selected review phase; report pages default to the first protocol review phase rather than `full`.
- `app/pipeline/reviewer.py`
  - review prompt now says each parent rule ID may appear only once;
  - parser merges duplicate parent rule rows conservatively, e.g. pass + investigator becomes investigator.
- `app/router/reports.py`
  - report/bundle endpoints fall back from `phase=full` to the first configured protocol review phase when no `full` artifact exists.
- `projects/MG-K10-SAR/criteria_rules.md`
  - corrected to the selected III期 parent structure:
    - IN-01 to IN-07 only;
    - IN-05 is baseline EOS `>=300/μL`;
    - EX-01 to EX-16 only;
    - no duplicate IN-02/IN-03 and no EX beyond protocol parent count.
- `projects/MG-K10-SAR/config.json`
  - `study_stage` set to `Ⅲ期`.

Important pitfalls found and fixed:

- Old DOCX extraction started from the table of contents (`5.1 入选标准`, `5.2 排除标准`) and then counted schedule/procedure rows as exclusion criteria, causing bogus counts such as IN=21 and EX=29.
- Clean auto-deconstruction previously produced only EX-01 to EX-08 and even changed identifiers to `MG-K10-SAR-III`; this is now blocked by prompt constraints and selected-stage extraction.
- Existing manual MG-K10-SAR rules had duplicate parent IN-02/IN-03 for II vs III. The III期 ruleset now contains only the III期 parent IDs.
- Report buttons without phase query previously requested `phase=full` and produced 404. Frontend and backend fallback were both fixed.
- LLM review sometimes split one parent rule into multiple rows, e.g. duplicate IN-04. Parser now merges duplicates while keeping the stricter verdict.

MG-K10-SAR III期 regression run:

- Source protocol:
  - `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`
- Source raw documents:
  - `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/13. CFDI核查/自查/入排/各中心原始入排资料`
- Clean rebuild log:
  - `projects/MG-K10-SAR/rerun_logs/mgk10sar_phase3_rerun_20260621_223702.json`
- Previous project backup before clean rebuild:
  - `output/deleted_project_backups/MG-K10-SAR_20260621_223702`
- Inventory observed in clean run:
  - 7 centers;
  - 93 subject folders;
  - 491 supported source files.
- Subjects rerun:
  - `06002`, `06003`, `06004`
- Phases rerun:
  - `screening_run_in`
  - `baseline_randomization`

Review/QC outcomes after corrected rules:

- All six reviewed subject-phase reports parse to exactly 23 parent rows:
  - IN-01 to IN-07;
  - EX-01 to EX-16;
  - no missing parent IDs;
  - no duplicate parent IDs after parser merge.
- All six overall verdicts are `needs_evidence`, not plain pass.
- 06004 EOS behavior is now conservative:
  - screening phase treats screening EOS 250/μL as not final for IN-05;
  - baseline phase remains `needs_evidence` because D1/baseline EOS source is missing, rather than definitively failing solely from the screening EOS.
- 06002 baseline now remains `needs_evidence` because IN-04 baseline rTNSS/iTNSS exact component means are missing despite D1 EOS passing.

Validation completed:

- `python3 -m unittest discover -s tests`
  - 21 tests passed.
- `python3 -m compileall app tests scripts`
  - passed in earlier full check; targeted compiles after later edits passed.
- `node --check` on extracted `static/index.html` script
  - passed.
- Live API checks:
  - MG-K10-SAR protocol draft without `study_stage` returns 409 and asks for II/III selection;
  - `/api/projects/MG-K10-SAR/subjects/06004/report?phase=full` now falls back to `screening_run_in` and returns 23 rule rows.
- Browser QA via Playwright:
  - login page shows custom logo and no CMS logo;
  - help page is detailed and does not expose admin password;
  - task home shows three entry cards;
  - first-deconstruct workspace shows `本次解构期别` selector plus editable rules and feedback panes;
  - audit list shows MG-K10-SAR version/date and `解构期别: Ⅲ期`;
  - project page shows II/III study-stage selector and screening/baseline review-phase selector;
  - 06004 screening report renders with parent rows IN-01..IN-07 and EX-01..EX-16.
- Browser screenshot artifact:
  - `output/playwright/mgk10sar_06004_screening_report_20260621.png`

Remaining risk/next QC targets:

- The LLM summary for 06004 baseline still uses wording like screening EOS 250/μL being below threshold while correctly stating D1 data are missing. Keep monitoring this wording; rule-level verdict is insufficient, not definitive fail.
- Report visible labels still show raw enum text such as `needs_evidence` in the subject list; a later UI polish pass should translate these to Chinese badges consistently.
- Full bulk run beyond 06002/06003/06004 remains pending if the user wants broader center-level validation.

## 2026-06-21 Final Startup Fix and Verification

Additional issue found late in validation:

- The desktop launcher previously said the service had started, but no process was listening on `127.0.0.1:8900` after the launcher exited.
- Existing `~/Library/LaunchAgents/com.smkzw.enrollment-review.plist` repeatedly failed with `last exit code = 78`.
- Direct foreground `python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8900 --loop asyncio` worked.
- LaunchAgent execution from the user domain could not reliably access/run the app path under `Documents/康哲项目资料`; the service wrapper did not write its first diagnostic line when started only through LaunchAgent.

Startup changes:

- Added `scripts/run_enrollment_review_service.sh`
  - sets `HOME`, `PATH`, `PYTHONUNBUFFERED`;
  - writes service-start diagnostics to `output/runtime_logs/enrollment-review-uvicorn.log`;
  - starts uvicorn with `--loop asyncio`.
- Added `scripts/run_enrollment_review_terminal.command`
  - opens a visible service window;
  - tells the user to keep that window open because closing it stops the service.
- Updated both:
  - `scripts/start_enrollment_review.command`;
  - `/Users/smkzw/Desktop/启动入排审核系统.command`.
- Launcher behavior is now:
  - verify/start oMLX;
  - try LaunchAgent first;
  - if `/api/health` is still not ready after timeout, unload the failing LaunchAgent and open the visible Terminal service fallback;
  - open `http://127.0.0.1:8900`;
  - tell the user to keep the service window if one appears.

Final validation after startup fix:

- `zsh -n` passed for:
  - `scripts/run_enrollment_review_service.sh`;
  - `scripts/run_enrollment_review_terminal.command`;
  - `scripts/start_enrollment_review.command`;
  - `/Users/smkzw/Desktop/启动入排审核系统.command`.
- `plutil -lint ~/Library/LaunchAgents/com.smkzw.enrollment-review.plist`: OK.
- Running `/Users/smkzw/Desktop/启动入排审核系统.command` started service via visible service-window fallback.
- `lsof -nP -iTCP:8900 -sTCP:LISTEN` showed Python listening on port 8900.
- `GET http://127.0.0.1:8900/api/health` returned:
  - `status=ok`;
  - `omlx=true`;
  - `deepseek=true`.
- `GET http://127.0.0.1:8000/v1/models` returned content.
- `python3 -m unittest discover -s tests`: 21 tests passed.
- `python3 -m compileall app tests scripts`: passed.
- `node --check` on extracted `static/index.html` script: passed.
- Admin login endpoint works with `admin` / `20121116`.
- Authenticated MG-K10-SAR checks using `X-Enrollment-User` and `X-Enrollment-Token`:
  - `/api/projects/MG-K10-SAR/phases` returns `study_stages=["Ⅱ期","Ⅲ期"]`, `requires_study_stage_selection=true`, and two review phases;
  - `/api/projects/MG-K10-SAR` returns version `V2.1`, protocol date `2025-09-19`, study stage `Ⅲ期`;
  - `/api/projects/MG-K10-SAR/subjects/06004/report?phase=full` falls back to `screening_run_in`, verdict `needs_evidence`, and 23 `rule_results`.
- Workspace is not a Git repository, so `git status` / `git diff` are unavailable here.

Current operational note:

- The service is running from a visible Terminal service window. Do not close that service window during active use. If it is closed, double-click `/Users/smkzw/Desktop/启动入排审核系统.command` again.

## 2026-06-24 D001 Phase II Batch Test and Semantic Verdict Guard

User-confirmed scope:

- Use account `smkzw`.
- Protocol:
  - `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`
- Source folder:
  - `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/全量-入组`
- All subject folders under that source root whose folder name contains `筛败` are D001 Phase II subjects.
- Attachment filenames must not be used to exclude a subject from Phase II. In particular, missing `Ⅱ期` or a stray `Ⅲ期` in an attachment filename is not a subject-level phase signal.
- Photo/image-like files, compressed archives, hidden system files, and exact duplicate files are not review source files.

Batch inclusion root cause and fix:

- The first batch logic inferred study phase from attachment filenames, causing many valid Phase II screen-failure folders to be excluded or left unreviewed.
- A second bug used `\bSA\d{5}\b`, which missed subject IDs followed by Chinese characters because the word boundary did not behave as intended in Chinese filenames.
- Added `app/batch_sources.py`:
  - discovers subject folders from folder name plus `SA\d{5}`;
  - applies a fixed project stage `Ⅱ期`;
  - filters unsupported images/archives/system files and photo-like DOCX names;
  - deduplicates by SHA-256.
- Added regression test:
  - `test_d001_screen_failed_batch_uses_project_stage_not_filename_phase_markers`;
  - confirms 22 subject folders and includes `SA07025` despite attachment phase wording.

Batch run artifacts:

- Script:
  - `scripts/d001_phase2_batch_review.py`
- Run log:
  - `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_093440.json`
- Final Markdown report:
  - `projects/D001-02-II/reports/d001_phase2_screening_full_batch_report.md`
- Final HTML report:
  - `projects/D001-02-II/reports/d001_phase2_screening_full_batch_report.html`
- Project Markdown export:
  - `projects/D001-02-II/reports/D001-02-II_screening_run_in_project_report.md`
- Processed subjects:
  - 22 folders, no batch errors.
- Final parsed overall counts after semantic guard and `pass_verify` downgrade:
  - `fail`: 4;
  - `needs_evidence`: 17;
  - `pass`: 1.

Manual IE comparison notes:

- Manual IE sheet had usable manual records for 15/22 subjects.
- Seven subjects had no manual IE record in the workbook extract:
  - `SA01025`, `SA03008`, `SA03009`, `SA03010`, `SA12008`, `SA12010`, `SA14002`.
- Manual `未判断` subjects:
  - `SA20011`, `SA20013`.
- Known mismatch/risk examples still requiring human QC:
  - `SA07020` and `SA07025`: manual EX-30 not system-hit;
  - `SA07030`: manual IN-01 due withdrawal of informed consent, but uploaded source did not contain a clear withdrawal source statement;
  - `SA16002`: manual EX-22 not system-hit.

DeepSeek/LLM semantic conflict found and fixed:

- Failure mode: for complex exclusion rules, especially lab package rule EX-20, model output sometimes wrote table verdict `❌不通过` while the reasoning later said the protocol-defined trigger was not met, such as `未触发排除标准` or `故本条通过`.
- Root cause is semantic, not just formatting:
  - model may confuse local abnormality/reference-range deviation with protocol exclusion trigger;
  - model may write an early mistaken comparison and then self-correct later in the same reasoning sentence;
  - parser previously trusted the verdict cell too strongly.
- Prompt-level fix in `app/pipeline/reviewer.py`:
  - added a判定闭环 rule;
  - every rule must first complete semantic trigger judgment;
  - EX rows can be `❌不通过` only when the reasoning explicitly states `触发判断：已触发` or equivalent trigger facts with subitem/value/unit/threshold;
  - complex lab/package clauses must compare actual value versus protocol threshold, not just abnormal/NCS/CS wording.
- Additional semantic fixes after user QC:
  - lab analytes must match exactly; `GGT` cannot substitute for `ALT` / `AST` / `总胆红素` in EX-20g;
  - evidence topic must match the rule topic; urine glucose or occult blood cannot prove EX-07 active infection / acute disease;
  - protocol AND conditions must remain AND. EX-20h requires other laboratory abnormality + clinical significance + investigator assessment that participation may pose unacceptable risk; missing any component is not a direct exclusion trigger.
- Parser-level guard:
  - detects positive trigger, negative trigger, and investigator semantics;
  - uses the last valid semantic judgment in the reasoning so later `重新确认/故本条通过` can override an earlier mistaken草判;
  - downgrades analyte substitution, topic mismatch, incomplete AND logic, and possibility-only wording to `investigator` instead of hard fail.
- Key D001 checks after fix:
  - `SA16005` EX-20 changed from spurious fail to pass, subject overall `needs_evidence`;
  - `SA18011` EX-20 pass, subject overall `needs_evidence`;
  - `SA07007` EX-20 changed to investigator, but subject remains fail due EX-09;
  - `SA01025` EX-20 changed away from hard fail because `GGT` does not trigger EX-20g; if clinically concerning it belongs under other-lab/investigator assessment;
  - `SA03009` EX-07 and EX-20 changed away from hard fail because urine glucose/occult blood do not prove infection and EX-20h all-of components were incomplete;
  - `SA16002` is overall `pass` with IN-03 retained only as `溯源提醒`.

Pass-verify output wording:

- User clarified that internal prompt-strength wording must not appear in UI or reports.
- The system now writes `溯源提醒`, not the internal strength wording.
- If `pass_verify` is the only non-plain-pass rule result, the overall verdict is `pass`.

HTML report cleanup:

- User rejected log/instructional phrases such as `按要求排除`.
- Final HTML no longer displays:
  - source directory;
  - batch id;
  - upload/exclusion counts;
  - folder inclusion rules;
  - `系统一致性校正` or similar parser-log wording.
- These operational details remain in run JSON/Markdown/context, not in the clinical-facing HTML.
- Mobile visual QC found the summary table was too cramped; tables now render inside `.table-wrap` scroll containers on narrow screens.

Validation completed:

- `python3 -m py_compile app/pipeline/reviewer.py scripts/d001_phase2_batch_review.py app/batch_sources.py`
  - passed.
- `python3 -m unittest discover -s tests`
  - 44 tests passed, 1 skipped.
- HTML forbidden-term scan for:
  - `按要求`, `按用户`, `排除上传`, `剔除`, `源目录`, `批次`, `上传N`, `日志`, `log`, `用户确认`, `纳入规则已`, `未上传审核`, `文件夹名包含`, `系统一致性校正`
  - returned no matches in final HTML.
- Browser QC via Playwright:
  - mobile 390px: `scrollWidth=390`, `.table-wrap` count 23;
  - desktop 1440px: `scrollWidth=1440`, `.table-wrap` count 23.
- Screenshot artifacts:
  - `output/playwright/d001_phase2_report_mobile_clean_html_v2.png`
  - `output/playwright/d001_phase2_report_desktop_clean_html_v2.png`

Follow-up UI/verdict validation after user QC:

- User clarified:
  - `通过（需验证）` should be treated as `pass` when it is the only non-plain-pass rule result;
  - user-facing text should say `溯源提醒`;
  - maximized windows should use the available page width rather than leaving a large blank right area.
- Implemented:
  - `static/index.html` removes the global `1680px` page cap for `#app` and `.header-inner`;
  - D001 batch HTML report removes the `1440px` main cap;
  - `app/pipeline/reviewer.py`, `app/markdown_export.py`, `app/models.py`, and `static/index.html` align `pass_verify` wording and final verdict behavior;
  - D001 generated reports and subject `info.json` were refreshed from existing raw review outputs, without rerunning OCR/LLM.
- API validation after restart:
  - `/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`;
  - D001 subject list returned 22 subjects: `4 fail`, `17 needs_evidence`, `1 pass`;
  - `SA16002` report returned overall `pass`, with only `IN-03 pass_verify`.
- Browser visual QC at 2048px width:
  - project page `#app` width `2048`, right gap `0`, subject table width `1984`;
  - SA16002 page `#app` width `2048`, right gap `0`, verdict card shows `可入组`, callout title `溯源提醒`;
  - generated D001 HTML report `main` width `2048`, right gap `0`.
- New screenshot artifacts:
  - `output/playwright/d001-project-wide-2048-fullwidth-v4.png`
  - `output/playwright/sa16002-report-pass-traceability-v4.png`
  - `output/playwright/d001-batch-html-wide-2048-fullwidth-v4.png`
- Final verification:
  - `python3 -m unittest discover -s tests` passed: 54 tests, 1 skipped;
  - `python3 -m compileall app scripts tests` passed;
  - `node --check /tmp/static_index_inline_final.js` passed.

OCR concurrency note:

- User later requested OCR concurrency be adjusted to at most 8.
- Implemented default `OCR_MAX_CONCURRENT=8` in `app/config.py` and explicit `OCR_MAX_CONCURRENT=8` in project `.env`.
- `app/router/pipeline.py` now calls `ocr_documents_parallel()` for the OCR stage instead of processing files one by one.
- `app/pipeline/ocr.py` now uses one shared VLM semaphore across concurrent files so the cap means at most 8 VLM OCR calls total, not 8 per file.
- Added regression coverage showing 9 one-page image files reach exactly 8 concurrent patched VLM calls under the default OCR path.
- Caveat: an already-running uvicorn process keeps its imported config/code. The active D001 batch that started before this change still uses the old service process until the service is restarted.

2026-06-24 continuation - D001 remaining-subject batch gate:

- User clarified that after system fixes, every remaining subject folder under `/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/全量-入组` should be audited; the statement that remaining subjects were manually judged eligible is comparison-only and must not be included in DeepSeek prompts.
- Root cause of missed subjects:
  - `scripts/d001_phase2_batch_review.py` hard-coded discovery to folder names containing `筛败`, so only the 22 already reviewed screen-failed subjects entered the batch.
  - The source tree contains 143 unique `SAxxxxx` subject IDs; 22 already existed in `projects/D001-02-II/subjects`, leaving 121 remaining IDs for this continuation run.
  - A naive all-folder `rglob` sees 187 candidate directories because nested photo folders and duplicate transfer folders repeat the same SA ID.
- System-level fix implemented:
  - `app/batch_sources.discover_subject_folders(..., folder_keyword=None)` now supports all-folder discovery.
  - Subject discovery skips photo-like candidate directories, collapses nested directories under the same subject root, and keeps multiple non-nested roots for one subject as `BatchSubjectFolder.folders`.
  - `collect_review_files_from_folders()` merges those roots into one upload package and deduplicates by SHA-256 while still skipping photos/images, archives, hidden/system files, unsupported files, and duplicates.
  - D001 batch script gained `--all-folders`, `--only-new`, and `--limit`; run logs explicitly state `manual_ie_usage = 人工IE仅用于审核后对照，不进入DeepSeek提示词。`
  - Batch report parsing now prefers corrected `review_report.md` over raw LLM output, matching the API report endpoint.
  - Manual IE comparison now treats `IE=是` as an explicit pass baseline: if the system still reports fail/needs-evidence/investigator items, the report says `存在差异：人工通过但系统仍有关注条目` instead of `人工未填具体条目`.
- Verification so far:
  - Added and passed target tests in `tests/test_phase_workflow.py` for all-folder subject discovery/merge and D001 batch report parsing/manual-pass comparison.
  - Real source discovery check: `discovered 143`, `existing 22`, `new 121`, `multi_roots 4`.
  - `python3 -m compileall app/batch_sources.py scripts/d001_phase2_batch_review.py app/markdown_export.py tests/test_phase_workflow.py` passed.
  - `python3 -m unittest tests.test_phase_workflow.SubjectUploadTests` passed.

2026-06-24 D001 remaining-subject pilot QC:

- Ran a 3-subject pilot with `python3 scripts/d001_phase2_batch_review.py --all-folders --only-new --limit 3 --username smkzw --password ''`.
- Pilot subjects: `SA01001`, `SA01002`, `SA01003`; all completed without batch errors.
- Run log: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_122506.json`.
- Pilot observations:
  - The revised all-folder discovery/upload path worked end to end.
  - HTML report forbidden-term scan found none of `按要求`, `排除上传`, `文件夹名包含`, `系统一致性`, `低强度`, `log`, `日志`, `用户确认`, `人工判定满足`.
  - Manual IE comparison correctly reports `存在差异：人工通过但系统仍有关注条目` for manually eligible pilot subjects with system investigator items.
  - EX-20h pilot reasoning preserved all-of logic: urine/protein/lipid abnormalities were not direct exclusions unless laboratory abnormality + clinical significance + investigator unacceptable-risk assessment were all supported.
- New system-level issue found and fixed:
  - EX-11 reasoning could borrow EX-20h/EX-21 language and say `不可接受风险` instead of the EX-11-specific second component `研究者明确判断不具备临床研究条件`.
  - Added parser tests:
    - `test_review_parser_uses_ex11_specific_researcher_component_not_generic_risk`;
    - `test_review_parser_downgrades_ex11_fail_when_only_generic_unacceptable_risk_is_stated`.
  - `app/pipeline/reviewer.py` now has EX-11-specific component detection and wording normalization; generic `不可接受风险` no longer counts as EX-11 definitive fail.
  - Existing SA01003 EX-11 report now reparses as: `研究者尚未明确评估这些情况是否导致受试者不具备临床研究条件...当前依据未完整证明该研究者判断。`
- Verification after EX-11 fix:
  - `python3 -m unittest discover -s tests` passed: 70 tests, 1 skipped.
  - `python3 -m compileall app scripts tests` passed.
- User added a post-batch experiment requirement:
  - After the 121 remaining-subject batch finishes, select several successful/pass subjects and several screen-failed/fail subjects.
  - Run a separate JSON schema output experiment using the same evidence packages, compare against the current Markdown-table-plus-parser route.
  - Compare practical advantages: parsing stability, missing-rule rate, all-of/compound-condition consistency, report readability/generation cost, speed, and failure modes.
  - Do not switch the main route during the active batch; only adopt JSON schema output if the controlled experiment shows clear advantage.
- User clarified another reminder-class requirement during the batch:
  - `基线期评估待后续阶段复核` and similar future baseline/D1/randomization gaps should be a reminder at the same strength as traceability reminders, but must not be mixed with `溯源提醒`.
  - Implemented as the same internal `pass_verify` verdict for compatibility, with reasoning-based labels:
    - `通过（溯源提醒）` for historical/provenance gaps;
    - `通过（后续阶段复核）` for baseline/D1/randomization components not yet reached in screening review.
  - API report rows now include `verification_type` (`source_traceability`, `future_phase`, `other`).
  - Frontend individual reports render separate callouts: `溯源提醒` and `后续阶段复核提醒`.
  - Project/center Markdown summary counts these two reminder types separately; subject-level rule tables use separate labels.
  - D001 batch report now has a separate `提醒条目` column and subject-level reminder table, distinct from `系统关注条目`.
  - Added tests:
    - `test_review_parser_separates_future_phase_verify_from_traceability_verify`;
    - updated `test_screening_phase_adjustment_does_not_downgrade_future_baseline_gap`;
    - `test_markdown_export_treats_pass_verify_as_traceability_note`.
  - Targeted reminder tests passed.

2026-06-24 continuation - subject-list filters and split pending verdicts:

- User requested the old overall `待补证` bucket be split:
  - `insufficient`: evidence/source material is missing and extra documents are needed (`证据不足`);
  - `investigator`: available data exist but need investigator or medical-monitor judgment (`需研究者判定`);
  - legacy `needs_evidence` is retained only for old persisted reports and shown as `需处理`, not as the new canonical label.
- Backend verdict changes:
  - `app/pipeline/reviewer.py` system prompt now asks DeepSeek for `pass / fail / insufficient / investigator`.
  - Overall priority is `fail > insufficient > investigator > pass`.
  - `pass_verify` does not downgrade the overall verdict.
  - Legacy raw outputs containing `needs_evidence` or Chinese `待补证` are reparsed into `insufficient` or `investigator` when rule-level semantics make that clear.
  - Legacy summaries saying `补充资料或研究者判断` are rebuilt so missing-source cases and investigator-judgment cases are not mixed.
- Export/UI changes:
  - `app/models.py` and `app/markdown_export.py` now expose separate labels/counts for `证据不足` and `需研究者判定`.
  - `static/index.html` renders separate badges and separate report callouts for missing evidence vs investigator judgment.
  - Existing old report data still appears as `⚠️ 需处理` until the running batch finishes and the backend is restarted/backfilled.
- Subject table UX changes:
  - Removed standalone `按中心筛选`.
  - Added per-column filters and sortable headers for: subject ID, center, uploader/creator, ICF date, status, and review conclusion.
  - Center is compacted as code on the first line and hospital name as smaller grey text.
  - File count column remains removed.
  - Checkbox handlers no longer re-render the whole project page, fixing the bug where clicking a subject checkbox jumped back to the top.
  - Clear filter / clear selection update the visible DOM state without replacing the whole page.
- Visual/manual browser QC:
  - In Edge at `127.0.0.1:8900/#/project/D001-02-II`, per-column filter inputs and sort buttons are visible.
  - Filtering `筛ID = SA01009` reduced the table to exactly one visible subject and showed `当前显示 1 名`.
  - Clearing filters restored `当前显示 53 名`.
  - Sorting `受试者ID` changed the header icon to `▲` and then `▼`; descending order moved `SA20013` to the first row.
  - Clicking a subject checkbox and clearing filters did not jump to the top; viewport stayed on the subject-table area.
  - The table fits the current maximized window width without requiring horizontal scrolling to see the operation column.
- Automated verification:
  - `python3 -m unittest tests.test_phase_workflow` passed: 75 tests, 1 skipped.
  - `python3 -m compileall app tests scripts` passed.
  - Extracted inline JS from `static/index.html` and ran `node --check /tmp/enrollment_index_check.js`; passed.
- Backfill preparation:
  - Added `app/report_backfill.py` and `scripts/backfill_review_reports.py`.
  - Purpose: after the active batch finishes, reparse persisted `review_report.md`/`review_raw.md`, rewrite normalized `review_report.md`, and update each subject `info.json` `overall_verdict` so the subject list no longer shows legacy `needs_evidence`/`需处理`.
  - Added regression test `test_backfill_reports_rewrites_legacy_needs_evidence_to_specific_verdict`; it first failed on missing module, then passed after implementation.
  - `python3 scripts/backfill_review_reports.py --project D001-02-II --phase screening_run_in --dry-run --output /tmp/d001_backfill_dry_run.json` succeeded without writing project files.
  - After adding the backfill utility, `python3 -m unittest tests.test_phase_workflow` passed: 76 tests, 1 skipped; `python3 -m compileall app tests scripts` passed.
- Active batch caveat:
  - D001 remaining-subject batch is still running in exec session `21757`.
  - Do not restart the service while that batch runs; backend verdict splitting will apply to new requests after restart.
  - After the batch completes, restart the enrollment-review service and run a legacy-report backfill/reparse so old `needs_evidence` reports are split into `insufficient` or `investigator` where possible.

2026-06-24 continuation - OCR concurrency raised to 8 and D001 resume handling:

- User asked to raise OCR concurrency from the observed two-way behavior to at most eight-way.
- Root cause:
  - `app/config.py` defaulted `OCR_MAX_CONCURRENT` to `2`.
  - `/api/.../process` and `/run-ocr` were still iterating documents sequentially.
  - `ocr_documents_parallel()` had a per-document semaphore model that did not provide one shared global cap across files.
- Implemented:
  - `OCR_MAX_CONCURRENT` default changed to `8`; `.env` also explicitly sets `OCR_MAX_CONCURRENT=8`.
  - `app/pipeline/ocr.py` now accepts a shared VLM semaphore and `ocr_documents_parallel()` uses one shared `asyncio.Semaphore(OCR_MAX_CONCURRENT)` across all files/pages, so total VLM OCR calls are capped at eight.
  - `app/router/pipeline.py` now uses `ocr_documents_parallel()` for both direct OCR and SSE process OCR, and emits `OCR并发处理中: ...最多8路VLM调用...`.
  - Added regression test `test_default_parallel_ocr_allows_up_to_eight_concurrent_vlm_calls`; full `tests.test_phase_workflow` passed after change.
- Running-batch correction:
  - Existing D001 batch session `21757` was using old imported code. It was stopped at SA07009 after confirming a safe resume path was needed.
  - Added `--only-unreviewed` to `scripts/d001_phase2_batch_review.py`; it skips only subjects with `status=reviewed`, non-empty `overall_verdict`, and an existing phase/legacy `review_report.md`. Subjects left as `processing`, `pending`, or missing report remain eligible and are recreated by default.
  - `--only-new` was not enough because it only checks whether a subject directory exists and would skip interrupted half-products such as SA07009.
- Service-start pitfall:
  - LaunchAgent restart failed with `EX_CONFIG` and detached/nohup/disown processes were cleaned up by the execution environment after health checks.
  - Stable workaround for this run: keep uvicorn in an explicit long-running exec session (`18548`, server PID `50936`) while D001 batch continues in session `19959`.
  - Failed LaunchAgent was booted out to stop spawn interference; durable desktop-start cleanup remains a later maintenance item.
- Runtime verification:
  - New D001 resumed run log: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_144818.json`.
  - SA07009 event log confirms: `OCR并发处理中: 7个文件，最多8路VLM调用...`.
  - SA07009 completed under new service with `overall_verdict=investigator`, confirming the split pending-verdict path is active.
  - Resume command: `python3 scripts/d001_phase2_batch_review.py --all-folders --only-unreviewed`.

2026-06-24 continuation - overlapping OCR and LLM across subjects:

- User correctly pointed out that batch mode was still `A受试者 OCR -> A受试者 LLM -> B受试者 OCR`, leaving OCR idle while DeepSeek reviewed A.
- System-level fix:
  - `app/pipeline/ocr.py` now has `global_vlm_semaphore()` with one event-loop-local shared semaphore for all OCR VLM calls in the server process.
  - This prevents subject-level concurrency from multiplying the OCR cap. Without this, two simultaneous subject requests could each create an 8-way semaphore and effectively hit oMLX with up to 16 VLM OCR calls.
  - `ocr_document()`, `ocr_documents_parallel()`, and `ocr_pages_batch()` all use the global semaphore unless an explicit test semaphore is injected.
- Batch-script fix:
  - `scripts/d001_phase2_batch_review.py` now supports `--subject-workers N`.
  - Default remains `1` for conservative behavior.
  - For D001 continuation we switched to `--subject-workers 2`, so one subject can be in DeepSeek review while the next subject is already uploading/OCRing/bundling.
  - Each worker uses its own authenticated HTTP session; progress is written to the run log after each completed subject.
- Verification:
  - Added `test_parallel_ocr_uses_one_global_limit_across_batches`, covering two concurrent OCR batches and asserting total concurrent VLM calls still peak at `8`, not `16`.
  - `python3 -m unittest tests.test_phase_workflow` passed: 78 tests, 1 skipped.
  - `python3 -m compileall app tests scripts` passed.
  - Current concurrent D001 run log: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_153846.json`.
  - It records `subject_workers=2`; SA10002 has `OCR并发处理中: 8个文件，最多8路VLM调用...`.
- Operational decision:
  - Do not jump directly to 4+ subject workers until observed stable over multiple centers, because DeepSeek review, oMLX OCR, upload, and evidence-bundle generation can all compete for local CPU/memory and remote API rate limits.
  - Current recommendation: use `--subject-workers 2` for large batches; consider `3` only after confirming no oMLX timeouts, DeepSeek rate limits, or memory growth.

2026-06-24 checkpoint - D001 batch intentionally stopped before full completion:

- User asked to checkpoint and not finish the entire remaining batch.
- Actions taken:
  - Let the active in-hand subjects complete where practical:
    - `SA10003` completed with `investigator`;
    - `SA10005` completed with `investigator`;
    - `SA11003` completed with `investigator` while the thread pool was being stopped;
    - `SA11004` had generated a report but was interrupted before `info.json` final save, so it was manually reconciled to `status=reviewed`, `overall_verdict=pass`;
    - `SA11005` had no report and was reset to `status=pending`, empty `overall_verdict`.
  - Stopped the concurrent batch process `scripts/d001_phase2_batch_review.py --all-folders --only-unreviewed --subject-workers 2`.
  - Left no `processing` subjects in `projects/D001-02-II/subjects`.
- Current D001 source/project counts:
  - Source-discovered II期 subjects: `143`.
  - Completed reviewed subjects by `completed_project_subject_ids()`: `96`.
  - Remaining unreviewed subjects: `47`.
  - Remaining starts with: `SA11005`, `SA12001`, `SA12002`, `SA12003`, `SA12007`, `SA12009`, `SA13002`, `SA13003`, `SA14001`, `SA14003`, `SA16001`, `SA16004`, `SA17001`, ...
- Current run logs:
  - Serial resumed run: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_144818.json`, logged 25, errors 0.
  - 2-worker overlap run: `projects/D001-02-II/rerun_logs/d001_phase2_screening_batch_20260624_153846.json`, logged 4, errors 0.
- Important caveat:
  - The project still contains older pre-split `needs_evidence` reports from the earlier batch. Before final reporting/QC, run the backfill/reparse utility to split legacy `needs_evidence` into `insufficient`/`investigator` where the saved report supports it.
  - Suggested later resume command if needed: `python3 scripts/d001_phase2_batch_review.py --all-folders --only-unreviewed --subject-workers 2`.

2026-06-24 checkpoint next step - JSON schema route experiment:

- User previously asked to test a JSON schema output route on a few successful and screen-failed subjects, and only adopt it if it clearly improves the current technical route.
- Implemented a non-production experiment script:
  - `scripts/experiment_json_schema_review.py`
  - It does not modify project reports or the production review flow.
  - It reads existing D001 criteria and evidence bundles, asks DeepSeek for strict JSON, writes raw and parsed JSON under the project reports folder, and compares against current Markdown reports.
- Representative samples:
  - `SA11004`: current `pass`.
  - `SA09002`: current `fail`.
  - `SA07009`: current `investigator`.
  - `SA10002`: current `insufficient`.
- Output folder:
  - `projects/D001-02-II/reports/json_schema_experiment_20260624_155126/`
  - Key files: `summary.md`, `summary.json`, `assessment.md`, plus per-subject raw/parsed JSON.
- Surface metrics looked good:
  - All 4 JSON responses parsed successfully.
  - Each covered 36/36 expected rules.
  - No missing rule IDs or invalid verdict enums.
  - Overall verdict matched the existing route for all 4 samples.
- Critical item-level finding:
  - Overall agreement hid safety downgrades.
  - `assessment.md` found item-level differences:
    - `SA07009`: 6 rule differences, 6 potential downgrades. JSON kept overall `investigator` only because EX-20 remained investigator, while EX-11/EX-21/EX-30 were downgraded to pass.
    - `SA09002`: 9 rule differences, 6 potential downgrades, including missing/weakening several safety-relevant interpretations.
    - `SA10002`: 1 minor difference.
    - `SA11004`: 0 differences.
- Decision:
  - Do not replace the production Markdown-table route with prompt-only JSON schema output yet.
  - JSON is promising as a structured sidecar/validator because parsing and rule coverage are strong.
  - Before adopting it, add item-level downgrade detection and missing-reminder detection; otherwise it can make the same overall decision while silently weakening specific clinical review points.

2026-06-24 startup issue - desktop launcher appeared stuck at "入排审核服务未运行，正在启动...":

- User observed `/Users/smkzw/Desktop/启动入排审核系统.command` hanging after `oMLX 已就绪。入排审核服务未运行，正在启动...`.
- Root-cause evidence:
  - `http://127.0.0.1:8900/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}` during investigation, so oMLX and the FastAPI app were not fundamentally broken.
  - `lsof -nP -iTCP:8900 -sTCP:LISTEN` showed Python/uvicorn listening on `127.0.0.1:8900`.
  - `launchctl print gui/$(id -u)/com.smkzw.enrollment-review` returned "Could not find service", so the LaunchAgent was not registered even though the plist existed.
  - This matches the earlier LaunchAgent pitfall where restart failed with `EX_CONFIG`; the visible Terminal service fallback can run the app while the original launcher window still looks uninformative.
- System-level fixes:
  - Updated `scripts/start_enrollment_review.command` and recopied it to `/Users/smkzw/Desktop/启动入排审核系统.command`.
  - Added bounded `curl` health checks (`--connect-timeout 2 --max-time 4`) so a half-responsive endpoint cannot freeze the launcher.
  - Added `output/runtime_logs/enrollment-review-launch.log` for LaunchAgent bootstrap/kickstart diagnostics instead of suppressing every `launchctl` error.
  - Made the LaunchAgent plist mode conventional (`chmod 644`) after writing.
  - Changed startup flow so the visible service window is the primary cold-start path. The unreliable LaunchAgent path is no longer the first user-facing startup route; it remains only as a fallback diagnostic route if the service window cannot respond.
  - Added progress dots during waits so the terminal does not appear dead.
  - Changed `scripts/run_enrollment_review_service.sh` log heading from `LaunchAgent service start` to `enrollment review service start` because the service may now be started from a visible Terminal window.
- Verification:
  - `zsh -n scripts/start_enrollment_review.command` passed.
  - Desktop launcher and repository launcher are byte-identical after sync (`cmp` exit `0`).
  - `curl -fsS --connect-timeout 2 --max-time 4 http://127.0.0.1:8900/api/health` returned healthy.
  - Running `/bin/zsh /Users/smkzw/Desktop/启动入排审核系统.command` completed with:
    - `oMLX 已就绪。`
    - When already running: `入排审核服务已运行。`
    - After cold stop: `入排审核服务未运行，正在打开服务窗口...` then `入排审核服务已在服务窗口中启动。请保留该窗口。`
    - `正在打开浏览器...`
    - `完成。若出现单独的服务窗口，请保留该窗口以维持服务运行。`
  - Cold-start health after final change: Python/uvicorn listening on `127.0.0.1:8900`, and `/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}`.

2026-06-25 third-party system review response:

- Source reviewed:
  - `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/SYSTEM_REVIEW_REPORT.md` was read in full and treated as a review report, not as binding instructions.
- Findings accepted as real and fixed systemically:
  - Path traversal risk in project/subject identifiers and upload filenames.
    - Added centralized storage ID validation in `app/shared.py`.
    - Applied validation in project/subject paths, subject creation, protocol upload, and subject material upload.
    - Rejected path separators, `..`, empty names, unsupported subject-upload extensions, and unsupported protocol-upload extensions.
  - OCR hallucination/repetition risk entering evidence bundles.
    - Added OCR quality detection in `app/pipeline/ocr.py` for dominant repeated lines, repeated segments, and very long page outputs.
    - New OCR cache pages now carry explicit OCR quality warnings and deduplicated/truncated content before entering review evidence.
    - Old OCR cache artifacts are not silently rewritten; affected subjects need OCR reset/rerun or a separate cache-cleaning pass.
  - ICF date extraction selected non-source discussion material and another subject's date.
    - Made `app/subject_dates.py` category-aware.
    - Prefer `screening_record`; exclude communication/discussion/enrollment-eligibility files from date extraction.
    - Reject candidate dates if nearby text references a different subject number.
  - Evidence bundle source filenames always showing `.pdf`.
    - `app/pipeline/bundler.py` now preserves the real extension from `file_categories.json`.
  - Subject/file mismatch not surfaced.
    - Evidence bundles now warn when OCR text contains a different `SAxxxxx` than the subject folder.
  - Concurrent duplicate processing for the same subject.
    - Added `app/processing_locks.py`.
    - OCR/review/process endpoints now reject duplicate in-process subject workflows with HTTP 409 and reset cleanly on errors.
  - Admin token/password weakness.
    - Admin password can now be overridden by environment variable while preserving the required fallback `20121116`.
    - Admin session token is now random, in-memory, TTL-bound, and different on each login.
    - New normal-user passwords are stored with PBKDF2-SHA256; legacy hashes still verify for compatibility.
  - Missing audit trail.
    - Added `app/audit.py`.
    - Project, subject, upload, reset, OCR, review, and process operations now write audit events.
    - Audit events are written both to the project ledger and to a system ledger at `projects/_system/audit_ledger.jsonl`, so delete events remain after project deletion.
  - Project statistics were too coarse.
    - Project list stats now separate `pass`, `pass_verify`, `fail`, `insufficient`, `investigator`, `pending`, `error`, and `pending_total`.
  - Frontend route race risk.
    - `static/index.html` route rendering is serialized so rapid hash changes do not interleave async renders.
  - Draft protocol workflow loss.
    - Saving a protocol draft now attempts workflow extraction from uploaded DOC/DOCX when workflow JSON is otherwise empty.
  - `.txt` ownership/upload regression surfaced during tests.
    - Subject uploads now allow `.txt`, and OCR pipeline supports text-file extraction into cache.
- Findings judged valid but not fully adopted in this pass:
  - Large `reviewer.py` decomposition is real architecture debt, but immediate broad splitting is higher risk than value while D001 semantic guards are still being tuned. Keep as a future phased refactor with tests around parser/prompt/rule guards.
  - Swagger docs hiding was not changed. This app remains a local clinical-review tool where API docs help debugging; add an environment-gated production mode before any network deployment.
  - `.env` encryption/keychain storage was not implemented. `.env` remains local and gitignored; keychain or encrypted settings should be a separate credential-hardening task.
  - Full cancellation of in-flight OCR/VLM calls was not completed. Review streaming now detects client disconnect and cancels the review task, but individual OCR page calls are still best-effort once submitted.
- Extra cleanup/verification:
  - Checked for the reported path-traversal artifact `etc/passwd`; no such repo path exists after the fix.
  - Restarted the running service through the visible service-window path after discovering `nohup` startup from the Codex shell could exit immediately. Keep the service Terminal window open.
- Regression tests added:
  - Storage ID path traversal rejection.
  - Upload filename traversal/extension rejection.
  - ICF extraction ignoring discussion files and other-subject IDs.
  - OCR hallucination deduplication.
  - Evidence-bundle real source extension and subject-mismatch warning.
  - Duplicate subject workflow lock.
  - Project stats split for `insufficient`/`investigator`.
  - System audit survives project deletion.
- Verification passed:
  - `python3 -m unittest tests.test_phase_workflow` -> 86 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - Extracted scripts from `static/index.html` and ran `node --check` -> OK.
  - Restarted service and verified `/api/health` -> `{"status":"ok","omlx":true,"deepseek":true}`.
  - API smoke:
    - Admin login works and consecutive admin tokens differ.
    - Creating subject `../../../etc/passwd` returns HTTP 400.
    - `/api/projects` returns split stats including `insufficient`, `investigator`, and `pending_total`.
- Remaining limitation:
  - Browser visual screenshot QC was attempted earlier but the automated screenshot captured the macOS lock screen rather than the page. Do not treat visual QC as passed for this report-response turn; only API, parser, unit, compile, and JS syntax checks passed.

2026-06-25 login button no-response fix:

- User-facing symptom:
  - On the login card, clicking `登录` appeared to do nothing.
  - Live Edge state showed `127.0.0.1:8900/#/task`, header already displayed an authenticated user, but the main content was still the login form.
- Root cause:
  - Backend auth was healthy; `/api/auth/login` returned a valid token for `smkzw`.
  - `submitLogin()` persisted auth and called `navigate('#/task')`.
  - When the browser was already on `#/task`, assigning the same hash did not fire `hashchange`, so `route()` never rerendered the main content.
  - This created a split state: header read the new localStorage auth session, while the body stayed on the old login DOM.
- Fix:
  - In `static/index.html`, after successful login and no first-help redirect, force `await route()` when the current hash is already `#/task`; otherwise keep normal `navigate('#/task')`.
  - Scope intentionally kept narrow; backend auth and route serialization were left unchanged.
- Verification:
  - Reproduced before the fix with Python Playwright: after clicking login, `localStorage.enrollmentReviewUser = smkzw`, `location.hash = #/task`, but task home text was absent and login card remained.
  - `node --check` on the extracted frontend script passed.
  - `/api/health` returned `{"status":"ok","omlx":true,"deepseek":true}` and direct `/api/auth/login` returned a valid `smkzw` token.
  - Re-ran the same Playwright path after the fix: task home text appeared, login card disappeared, hash remained `#/task`, and user was `smkzw`.
  - Refreshed the real Edge tab, clicked login, and confirmed the visible UI entered the task home as `smkzw`.

2026-06-25 staged review anchors, phase-level subject list, OCR polarity review, and conmed-denial guard:

- User-facing triggers:
  - MG-K10 SAR subject list only showed one final conclusion; screening and baseline/randomization review results required using the top phase dropdown and then entering the subject report, which was not intuitive.
  - Parent and child rules such as `EX-06` / `EX-06f` had the same visual hierarchy in the report table.
  - SAR time-window rules such as `EX-06f` and `EX-12` depend on "随机前/基线前" anchors; without a baseline/randomization date, the model could over-infer from screening dates or report dates.
  - OCR polarity error risk was observed in source text like "否认3个月内有大量饮酒" being read as "确认3个月内有大量饮酒".
  - Missing standalone concomitant-medication records were being over-treated as evidence insufficiency even when the medical record explicitly denied relevant prohibited medication/treatment categories in the required protocol time windows.
- Root causes:
  - `SubjectInfo` only stored one `overall_verdict`; phase reports existed under `llm/<phase_id>/review_report.md`, but `list_subjects` did not expose phase-level summaries.
  - Review anchoring only included screening/ICF/first-dose/birth dates. There was no phase-specific baseline/randomization anchor, and reviewer/bundler prompts still used legacy wording that encouraged the LLM to "identify key dates" broadly.
  - Native PDF text extraction skipped VLM when enough text existed, so high-risk polarity pages had no image cross-check.
  - Parser guards covered several AND/OR and lab-substitution failure modes, but did not yet handle the specific "missing conmed table + explicit source denial" false-insufficient pattern.
- System-level fixes:
  - Added `SubjectInfo.phase_anchor_dates` and PATCH support for `phase_anchor_dates`.
  - `subject_anchor_dates(subject_path, review_phase)` now exposes `review_phase_anchor_date` for the selected phase.
  - OCR/review/process endpoints pass the selected phase into anchor-date construction and evidence bundling.
  - Subject list API now returns `phase_reviews` for each configured non-full review phase, parsed from corrected `review_report.md` before raw LLM output.
  - Report API now returns rule hierarchy metadata: `parent_rule_id`, `is_child_rule`, `is_parent_rule`, and `hierarchy_level`.
  - Reviewer prompt now states:
    - baseline/randomization anchors must be explicit;
    - if no baseline/randomization anchor is provided or found, random-before/baseline-before/first-dose-before time-window components should become evidence-insufficient or investigator-judgment items rather than inferred passes;
    - explicit source-record denial of relevant prohibited medications/treatments and time windows is valid negative evidence; missing a separate conmed log alone should not create evidence insufficiency, though it can remain a `溯源提醒`.
  - Evidence bundle anchor table no longer says "待LLM从证据识别"; it now says missing structured values may only be verified from explicit source text and must not be substituted with report/print/upload dates.
  - OCR now flags high-risk native text pages for VLM polarity review when they contain combinations such as `否认/确认/有/无/阴性/阳性/未使用/已使用` plus clinical trigger terms or protocol time windows.
  - OCR cache for such pages stores both native text and image-OCR review text with an explicit quality warning.
  - Parser now downgrades the specific false-insufficient pattern to `pass_verify` when a missing conmed log is the only gap and the reasoning itself contains explicit time-window denials for relevant prohibited medication/treatment categories.
  - Frontend subject list now renders one column per review phase with direct report/review buttons; baseline/randomization-like phases show an inline date input for the anchor date.
  - Row operation buttons no longer duplicate generic "execute/review report" actions that ignore phase context.
  - Report table visually distinguishes parent rows and child rows; child rows are indented with a connector marker.
  - Subject-list phase/filter columns were made responsive; checkbox clicks stop propagation and no longer jump the page to the top.
- Verification:
  - Focused tests added and passed for:
    - saving phase anchor dates and using them in `subject_anchor_dates`;
    - subject-list phase review summaries;
    - report API parent/child hierarchy metadata;
    - high-risk OCR polarity text detection;
    - baseline prompt behavior with and without a phase anchor;
    - conmed-denial false-insufficient parser guard.
  - `python3 -m unittest tests.test_phase_workflow` -> 103 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - Extracted frontend script from `static/index.html` and ran `node --check` -> OK.
  - Temporary uvicorn service on `127.0.0.1:8900` returned `/api/health` healthy.
  - Playwright visual/QC:
    - `#/project/D001-02-II` at 1920 px showed direct screening and baseline/randomization phase columns.
    - `document.documentElement.scrollWidth` and `window.innerWidth` were both `1920`; table right edge stayed inside the viewport.
    - Baseline/randomization phase date inputs were present.
    - Checkbox click test kept `window.scrollY` at `650` before and after click.
    - Temporary hierarchy report rendered one `rule-parent-row` and one `rule-child-row`, with child row shown as `↳EX-06f`.
- Pitfalls:
  - Starting uvicorn via background `nohup` from the Codex shell can pass a health check and then be cleaned up by the command environment. For persistent user-facing startup, keep using the desktop/Terminal launcher service window; for validation, use a foreground controlled session and stop it explicitly.
  - Native HTML `input type=date` cannot preselect only year/month without a day. Empty inputs still open the platform date picker around the current date/month, which satisfies the practical "no default day selected" constraint without inventing a custom date widget.
  - OCR polarity review improves risk detection but does not guarantee truth when native text and image OCR disagree. Reports must preserve the warning so clinical reviewers can open the source page for final adjudication.

2026-06-25 OCR model options research:

- User asked for an independent sub-agent style assessment of PaddleOCR-VL 1.6, UnlimitedOCR, and PP-OCRv6 for enrollment-review source materials.
- Conclusion:
  - Keep PaddleOCR-VL 1.6 as the main OCR/VLM path for now.
  - Consider PP-OCRv6 plus PP-StructureV3 later as a targeted secondary verifier for pure printed Chinese text, lab-report numbers, and tables.
  - Do not move UnlimitedOCR into the production path now; it is interesting for long-document research but mismatched with page-level clinical evidence traceability.
- Rationale:
  - Enrollment review is most sensitive to polarity and exact facts: `否认/确认`, `有/无`, `阴性/阳性`, dates, time windows, lab value/unit/reference-range triples, and investigator judgment wording.
  - PaddleOCR-VL 1.6's public positioning covers document parsing, tables/layout, reading order, Chinese text, stamps, scanned/tilted/photo-like documents, and complex document elements, which better matches mixed clinical source packets than character-only OCR.
  - Current app already defaults to `models--PaddlePaddle--PaddleOCR-VL-1.6` through oMLX, so short-term engineering risk is lower than replacing the OCR stack.
  - Important limitation: the app currently calls the VLM via an OpenAI-compatible visual prompt route, not the full official PaddleOCR-VL document parser pipeline. Treat current output as page-image Markdown extraction, not a guaranteed reproduction of official full-pipeline benchmarks.
  - PP-OCRv6 alone is stronger as a fast OCR engine but not enough for complex layout/table reconstruction; PP-StructureV3 would be needed for table/layout use cases.
  - UnlimitedOCR's long-document one-pass strategy conflicts with this app's need for page-level source references, retryability, and exact evidence localization.
- Evidence sources named in the research branch:
  - PaddleOCR-VL 1.6 official algorithm page: `https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/algorithm/PaddleOCR-VL/PaddleOCR-VL-1.6.html`
  - PaddleOCR-VL pipeline usage: `https://www.paddleocr.ai/latest/en/version3.x/pipeline_usage/PaddleOCR-VL.html`
  - PaddleOCR-VL Apple Silicon usage: `https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.html`
  - PP-OCRv6 technical report: `https://arxiv.org/html/2606.13108v1`
  - PP-OCRv6 model collection: `https://huggingface.co/collections/PaddlePaddle/pp-ocrv6`
  - PP-StructureV3 usage: `https://paddlepaddle.github.io/PaddleOCR/main/en/version3.x/pipeline_usage/PP-StructureV3.html`
  - UnlimitedOCR GitHub: `https://github.com/baidu/Unlimited-OCR`
  - UnlimitedOCR arXiv: `https://arxiv.org/html/2606.23050v1`
- Proposed empirical benchmark before any OCR replacement:
  - Build an 80-120 page local gold set covering Chinese research records, scanned PDFs, phone photos, lab reports, eligibility discussion tables, stamps, low-resolution/tilted/shadowed pages, signatures, historical records, and screening/baseline records.
  - Force inclusion of high-risk pages containing negation/polarity, date windows, SA IDs, lab values/units/reference ranges, and investigator judgment text.
  - Measure full-text CER/WER, key-field exact match, polarity recall, date/window accuracy, lab triple accuracy, table-cell F1/TEDS, reading-order error rate, stamp/signature detection, hallucination/repetition rate, page/source traceability, p95 latency, memory use, 8-concurrency stability, and downstream eligibility-verdict difference rate.
  - Replacement threshold: do not change the primary OCR unless key-field accuracy improves or stays at least equal, hallucination is lower, source traceability is preserved, and throughput remains clinically usable.

2026-06-25 DeepSeek V4 Flash/Pro review-parameter audit and prompt hardening:

- User asked to deeply judge DeepSeek capability and optimize prompts around DeepSeek behavior, then specifically challenged whether V4 Flash should be considered because default Flash is much faster and cheaper than Pro.
- Current production `.env` before this pass used:
  - `REVIEW_BACKEND=deepseek`;
  - `REVIEW_MODEL=deepseek-v4-pro`;
  - no explicit review reasoning effort.
- Official DeepSeek docs checked:
  - thinking-mode docs describe `deepseek-v4-pro` thinking mode and `reasoning_effort` values such as `high` / `max`;
  - pricing/model page lists `deepseek-v4-flash` and `deepseek-v4-pro` as separate models and indicates Flash has lower per-token pricing and higher concurrency limits than Pro.
- Experiment design:
  - Used 6 known historical semantic-error cases from D001 and MG-K10-SAR:
    - D001 `SA01025` `EX-20g`: GGT must not substitute ALT/AST/TBil.
    - D001 `SA03009` `EX-07`/`EX-20h`: urine glucose/occult blood must not imply infection; EX-20h is AND.
    - D001 `SA16002` `EX-22`: TPPA positive + TRUST negative still needs explicit cured-prior-infection judgment.
    - SAR `31001` `EX-09e/g`: threshold child vs other-abnormal researcher component.
    - SAR `31010` `IN-05`: unreadable/missing current-stage baseline evidence is insufficient, not fail.
    - SAR `31015` `EX-09e/g`: ALT/AST not above exclusion threshold; CS abnormality must route to researcher component.
  - First run compared `V4 Flash max`, `V4 Pro high`, `V4 Pro max` in `output/deepseek_reasoning_mode_comparison_20260625/`.
  - User then requested Flash default; added and ran `V4 Flash default` in `output/deepseek_flash_default_20260625/`.
  - Old timing method started before acquiring the concurrency semaphore, so queue wait contaminated elapsed time. This made old Flash max latency numbers invalid, although request parameters and semantic outputs were still valid.
  - Rechecked Flash default vs Flash max after fixing API timing and strengthening the focused experiment prompt in `output/deepseek_flash_default_vs_max_recheck_20260625/`.
- Corrected comparison after timing fix:
  - `V4 Flash default`: average score `93.3`, `5/6` perfect, average true API time `19.7s`, average total tokens `6038`, average reasoning tokens `1441.5`.
  - `V4 Flash max`: average score `100.0`, `6/6` perfect, average true API time `40.8s`, average total tokens `7812.8`, average reasoning tokens `3110.5`.
  - Earlier `V4 Pro high`: average score `93.3`, `5/6` perfect, average elapsed in the old queue-contaminated run `203.3s`, average total tokens `5943.3`.
  - Earlier `V4 Pro max`: average score `81.7`, `4/6` perfect, and incorrectly hard-failed the syphilis exception case.
- Capability judgment:
  - DeepSeek V4 is capable on these eligibility semantics when prompted with explicit fail gates and AND/OR decomposition.
  - V4 Flash default is strong enough for routine batch review and much faster in true API time, but it can still use global IE wording (`初步符合入排/不符合排除/发放导入期药物`) as a substitute for rule-specific researcher judgment.
  - V4 Flash max fixes the SAR-31015 style ambiguity in this small set, but costs about 2x true API time and substantially more reasoning tokens than default Flash.
  - V4 Pro max is not automatically safer; it can over-reason and hard-fail missing exception components.
- Production decision:
  - Changed actual `.env` review path to `REVIEW_MODEL=deepseek-v4-flash` and `REVIEW_REASONING_EFFORT=default`.
  - `REVIEW_REASONING_EFFORT=default` means the client does not send provider-specific `reasoning_effort`; this preserves Flash's default speed/cost profile.
  - `.env.example` now documents `default | high | max`; `high`/`max` should be used for targeted difficult-case reruns, not routine bulk review.
- System prompt hardening:
  - Added a `DeepSeek输出前自检` block to the formal review system prompt:
    - every official parent rule ID must be output;
    - fail requires a positive trigger and cannot coexist with missing/needs-confirmation wording;
    - aggregate IE/global eligibility wording cannot replace rule-specific researcher judgment;
    - threshold child criteria and other-abnormal researcher criteria must be separated;
    - incomplete exceptions must not be forced into pass or definitive fail.
  - Added the same self-check reminder to the user prompt tail so long prompts keep the constraint near the output instruction.
- Parser/postprocess hardening:
  - Syphilis exception guard now handles both directions:
    - pass/na/pass_verify is downgraded if TPPA/TP-Ab positive lacks the complete exception;
    - fail is also downgraded to investigator when the only missing element is the cured-prior-infection judgment and the case cannot be passed by exception yet.
  - Fixed negation-scope detection so `未见研究者明确判断既往感染已治愈` and `表明未判断为不适合入组` are not misread as positive judgments.
  - Added a generic guard for global IE substitution: a pass that relies on `初步符合入排标准/不符合排除标准/可入组/发放导入期药物` while abnormal/CS evidence exists and the rule requires a rule-specific researcher component is downgraded to `investigator`.
- Verification:
  - `python3 -m unittest tests.test_phase_workflow` -> 117 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - Focused DeepSeek experiment artifacts:
    - `output/deepseek_flash_default_20260625/comparison.md`;
    - `output/deepseek_flash_default_vs_max_recheck_20260625/comparison.md`;
    - `output/deepseek_reasoning_mode_comparison_20260625/combined_flash_default_summary.md`.

2026-06-25 MG-K10-SAR III期 31中心 Flash max 全流程重跑与QC闭环：

- User decision and active runtime:
  - After the corrected timing comparison showed `V4 Flash max` averaged about `40.8s` true API time with better semantic accuracy than Flash default on the focused difficult-case set, the user chose quality over default-speed mode.
  - Current `.env` is intentionally set to:
    - `REVIEW_BACKEND=deepseek`
    - `REVIEW_MODEL=deepseek-v4-flash`
    - `REVIEW_REASONING_EFFORT=max`
    - `OCR_MAX_CONCURRENT=8`
  - This supersedes the earlier default-Flash production note above for current SAR rerun work. Flash default remains a possible routine-batch option, but SAR III center-31 rerun used Flash max.
- Scope:
  - Project recreated as phase-scoped `MG-K10-SAR-III`, study stage `Ⅲ期`.
  - Protocol source: `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`.
  - Raw subject source root: `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/13. CFDI核查/自查/入排/各中心原始入排资料`.
  - First batch center: `31｜河北省中医院`.
  - Subjects processed: `31001`, `31006`, `31008`, `31010`, `31013`, `31014`, `31015`, `31016`, `31017`, `31018`.
  - Review phases processed for every subject:
    - `screening_run_in`（筛选/导入期）
    - `baseline_randomization`（基线/随机期）
- Main run artifacts:
  - Full rerun log: `projects/MG-K10-SAR-III/rerun_logs/mgk10sar_phase3_rerun_20260625_212425.json`.
  - Workflow snapshot: `projects/MG-K10-SAR-III/rerun_logs/protocol_workflow_snapshot_20260625_212425.json`.
  - Project config: `projects/MG-K10-SAR-III/config.json`.
  - Review reports: `projects/MG-K10-SAR-III/subjects/<SUBJECT>/llm/<PHASE>/review_report.md`.
  - Raw LLM retry capture exists for model omission cases:
    - `projects/MG-K10-SAR-III/subjects/31001/llm/screening_run_in/review_attempt_1_raw.md`
    - `projects/MG-K10-SAR-III/subjects/31001/llm/screening_run_in/review_attempt_2_raw.md`
    - `projects/MG-K10-SAR-III/subjects/31010/llm/screening_run_in/review_attempt_1_raw.md`
    - `projects/MG-K10-SAR-III/subjects/31010/llm/screening_run_in/review_attempt_2_raw.md`
- System-level fixes discovered during this rerun:
  - Baseline/current-stage required evidence must not be substituted by screening-only evidence. This was enforced for baseline/D1/randomization-current requirements.
  - Source labels such as `筛选-基线病历` are not proof that a baseline-specific procedure was completed; guards must inspect the actual phase requirement and source content rather than the label string.
  - Screening-phase future baseline/randomization/D1 components should be `pass_verify` follow-up reminders, not ordinary pass/NA.
  - If DeepSeek omits official rule IDs, `run_review` now retries once with explicit missing IDs; if still missing, placeholders are inserted as evidence-insufficient.
  - EX-08 FEV1 pass requires numeric or interpretable FEV1 percent-predicted support. Header-only or OCR-muddled lung-function text is insufficient.
  - Positive biologic/monoclonal exposure with uncertain washout must not be neutralized by broad concomitant-medication denial wording.
  - Historical diagnosis/duration rules such as SAR IN-02 require source traceability. If the duration is supported only by screening/baseline medical-record narrative, keep the rule as `pass_verify` / `溯源提醒`; only prior medical records, diagnosis certificates, prior prescriptions, discharge summaries, or similar traceable prior records support ordinary pass.
  - A final missed expression was found in 31001 baseline IN-02: `病史自2000年起≥2年`. The generic historical-duration regex now covers this pattern and a regression test locks it.
- Backfill/QC:
  - After parser-guard changes, reports were backfilled for both phases:
    - `output/sar31_flash_max_rerun_20260625/backfill_after_parser_guards.json`
    - `output/sar31_flash_max_rerun_20260625/backfill_after_history_regex_fix.json`
  - Final QC outputs:
    - `output/sar31_flash_max_rerun_20260625/qc_summary_final.md`
    - `output/sar31_flash_max_rerun_20260625/qc_summary_final.json`
    - `output/sar31_flash_max_rerun_20260625/qc_flags_final.json`
  - Final QC result: 10 subjects x 2 phases all had 23 rules; preset QC flags were `0`.
  - QC scanned rule count, duplicates, missed reports, IN-02 history traceability, EX-08 numeric FEV1 support, EX-06/EX-12 washout uncertainty marked as pass, EX-09 threshold/non-trigger fail conflicts, and fail/reasoning polarity contradictions.
  - One temporary QC false positive on 31001 baseline IN-05 was due to the QC regex treating ordinary `不符合/不通过` wording as contradiction. The QC regex was tightened; the clinical report was correct.
- Exported reports:
  - Screening Markdown: `output/sar31_flash_max_rerun_20260625/MG-K10-SAR-III_31中心_screening_run_in_Markdown报告.md`.
  - Baseline/randomization Markdown: `output/sar31_flash_max_rerun_20260625/MG-K10-SAR-III_31中心_baseline_randomization_Markdown报告.md`.
  - Combined HTML: `output/sar31_flash_max_rerun_20260625/MG-K10-SAR-III_31中心_FlashMax_双阶段入排审核报告.html`.
  - HTML body leakage check found no `模型`, `RAW-`, `EDC-`, `按要求排除`, `review_raw`, `review_attempt`, `backfill`, `DeepSeek`, or debug wording in visible body text.
  - Browser rendering QC used local Microsoft Edge via Playwright package with explicit executable path; screenshots saved:
    - `output/sar31_flash_max_rerun_20260625/html_qc_1440.png`
    - `output/sar31_flash_max_rerun_20260625/html_qc_1920.png`
    - `output/sar31_flash_max_rerun_20260625/html_qc_390.png`
    - metrics: `output/sar31_flash_max_rerun_20260625/html_visual_qc.json`
  - Visual/browser QC: 1440, 1920, and 390 px viewports had no horizontal overflow; page contained 10 subject sections and final QC-zero text.
- Test and service verification:
  - Targeted historical-duration tests passed.
  - `python3 -m unittest tests.test_phase_workflow` -> 130 tests OK, 1 skipped.
  - `python3 -m compileall app tests scripts` -> OK.
  - `git diff --check` was attempted but this workspace is not a git repository, so it is not applicable here.
  - Service was restarted after backend parser changes using the project Terminal service script. New process served `/api/health` as `{"status":"ok","omlx":true,"deepseek":true}`.
- Pitfalls to remember:
  - Do not trust a healthy API alone after parser changes; restart the uvicorn service or the browser/API will keep using old imported code.
  - Do not reuse a QC regex that flags any co-occurrence of `不符合` and `不通过`; those words can be a correct reason for an inclusion fail.
  - Keep report exports separate from operational/raw retry files. Raw retry files are useful audit artifacts but should not leak into clinical-facing HTML.
  - For SAR 31 center, many baseline/randomization results remain `证据不足` because required D1/baseline raw records or anchor dates are not present, not because the system should infer from screening records.

2026-08-12 expanded V2 architecture conference (Kimi K3 + CodeBuddy GLM-5.2):

- User requested a second complete conference emphasizing independent Agent implementation, testing LOOP, frontend/interaction, provenance and user-oriented workflow.
- Active independent routes were fixed to:
  - `pi/kimi-code/k3-256k:max`, session `019ff580-3595-7000-bc4c-2ab69f8ee01c`, one complete pass, no fallback;
  - `codebuddy/codebuddy-cli/glm-5.2:max`, session `6bce0b95-89e9-49e3-85e9-6f08f18b1e7c`, one complete pass, no fallback.
- Qwen 3.8 was never dispatched. The user first replaced it with GLM-5.2 and then explicitly requested that no Qwen 3.8 conference be run later.
- Codex independently confirmed the live legacy problems cited by the panel:
  - reviewer prompt still auto-prefers prior source on conflict;
  - OCR cache uses mtime;
  - SSE request/disconnect owns and can cancel model review;
  - SubjectInfo still has one `overall_verdict`;
  - OCR adapter returns plain text and strips LOC tokens, so exact bbox provenance is not currently guaranteed.
- Accepted architecture changes:
  - new Phase 0.5 freezes fixture/API, RuleExpression, Agent I/O, rollup and UAT contracts;
  - Phase 1 is the real React shell over a stub API, followed by Phase 1.5 measured user acceptance before backend work;
  - EvidenceRequirement/EvidenceExpectation make absent expected records/procedures first-class;
  - EvidenceSpan has a visible precision ladder `bbox > text_range > page_excerpt > page_only` and a Phase 4 capability spike;
  - Assessor emits semantic candidates; deterministic Evaluator/Gates own final component state, rollup and Action transitions;
  - AgentCall/PromptVersion, optimistic revision, stale scope, per-item Job UX and ReviewRun diff are required;
  - testing expands to contract, deterministic/property/mutation, Agent/OCR eval, clinical regression, failure injection, E2E/visual/accessibility/performance and UAT.
- Rejected/deferred:
  - no day-one LangGraph, free-running swarm, always-on Critic or extra Profile/Report Agent;
  - no split Safety/Provenance Critic until evaluation proves value;
  - no database/backend implementation before Phase 1.5 approval;
  - no fake bbox, silent conflict source preference or legacy verdict migration.
- Conference evidence:
  - `runs/conference/enrollment_review_expanded_design_conference_20260812/`;
  - `reviews/codex_conference_enrollment_review_expanded_design_conference_20260812_review.md`;
  - `metrics/enrollment_review_expanded_design_conference_20260812_conference_metrics.md`.
- Updated baselines:
  - `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`;
  - `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`.
- Hold point remains active: no V2 business implementation, legacy project write, deletion or clinical rerun until the user approves the revised design. After approval, only Phase 0/0.5/1 starts; Phase 1.5 is the next mandatory user gate.

2026-08-12 V2 Phase 0 与 Phase 0.5 合同候选进度：

- Phase 0 已经独立 checker 验收并归档：候选 `97dbadd` 首轮因默认 pytest 覆盖不足、写边界假阳性、依赖/镜像记录不足和文档漂移被拒绝；经 `6fa901d`、`8036d6a` 修复后由同一 checker 接受，验收提交 `2fbe25c`，归档提交 `56bf2f5`。
- Phase 0.5 Trellis 任务为 `.trellis/tasks/08-12-phase0-5-contracts`，当前仍是候选，尚未归档。
- 新合同实现包含 `app/domain/contracts/`、`app/domain/gates/`、`app/domain/expression.py`、`app/domain/rollup.py`、`contracts/v1/`、`scripts/generate_v2_contracts.py` 和 `tests/v2/`。
- 根因防线：Agent 只能写 draft/candidate/CriticRun；FinalAssessment、Action 阻断和 EpisodeRollup 由确定性 Gate/Projection 产生；`ALL/ANY/NOT` 有独立真值语义测试，防止“和”被弱化为“或”。
- 证据状态、判断状态和待办阻断等级分离；溯源待办非阻断、后续节点为关注、当前缺口/专业判断/冲突为阻断。
- Agent/交互/UAT 合同由独立 Luna worker 在限定写域完成，主线程核对后将概念字段统一为 `RuleSet.revision`、`EpisodeRollup`、`AgentCall.model_config_id`。
- 三个合成 Fixture 覆盖明确障碍、未发现明确障碍、缺口/冲突及四级 EvidenceSpan；Schema/OpenAPI/Fixture 连续生成 SHA-256 一致。
- 首轮 Phase 0.5 候选 `43896d1` 被独立 checker 拒绝，finding 包括：表达式只有逻辑结构而无比较器/单位/时间求值、Agent/Gate Schema 与文档漂移、OpenAPI 不可直接消费、3 个单节点 Fixture 不足以执行 UAT、rollup 对弱证据/溯源误判、缺少 ProtocolIntegrity/StageIsolation Gate，以及 FinalAssessment/Action/EpisodeRollup 可直接绕过 Gate 构造。
- 现已按根因修复形成待复核工作树：三值 Evaluator 计算比较器/单位/显式锚点和时间窗，trigger 与 exception 独立；Assessment Gate 从规则类型与求值结果推导状态并拒绝不一致候选；最终 DTO 在模型边界自校验；共享 gap 阻断策略驱动 rollup；新增机器可读 Agent I/O Schema、可消费 OpenAPI、ProtocolIntegrity/StageIsolation 闭包 Gate，以及 6 名受试者 x 2 Episode 的 UAT 工作区。
- 修复后候选测试：合同专项 `82 passed`；V2 默认全套 `218 passed, 1 skipped`；legacy Python 3.9 `130 passed, 1 skipped`。8 个生成 Schema/OpenAPI/Fixture 连续生成 SHA-256 一致；唯一跳过仍是 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。
- 复核前最后一次测试收集发现 `AgentContractsV1.model_config` 与 Pydantic v2 保留配置名冲突；复合合同字段改为 `model_configuration`，底层审计引用仍为 `AgentCall.model_config_id`，并通过生成器、Schema 和全套回归重新验证。
- 本阶段没有调用真实 LLM/OCR、没有临床重审、没有修改 legacy 项目数据；用户明确要求不再找 Qwen 3.8 会商，后续执行与 checker 路由均排除 Qwen 3.8。
- 下一硬门槛：新上下文独立 checker 无阻断 finding，Codex 接受后才归档 Phase 0.5；Phase 1 只构建真实 React 产品壳和 stub API，Phase 1.5 仍需用户批准后才进入后端业务层。

2026-08-12 Phase 0.5 同一 Luna checker 二次复核：

- 修复提交 `9a47bbc` 仍被拒绝；OpenAPI 可消费性已确认关闭，其余边界只有部分关闭。
- 新的根因级 finding：数值谓词单位可省略且 Evaluator 没有事实 scope；事实极性仍允许空值 fail-open；AssessmentCandidate 可用 gap 改写 UNKNOWN；`historical_source_unavailable` 被错误降级；角色 I/O 与 GateResult runtime 仍未完全兑现；UAT 只有筛选/基线且复制了错误的 baseline `not_due`；ProtocolIntegrity 依赖调用方给出编号答案；Final/Action/Rollup 可用内部一致但未经 accepted Gate 的对象绕过。
- 决定按四组处理：事实/求值范围、Gate 发布链、权威方案与阶段闭包、真实 UAT 前置条件。Phase 1 继续冻结，Qwen 3.8 继续禁用。

2026-08-12 Phase 0.5 二次拒绝后的根因修复（进行中）：

- 用户再次明确“不用再找 Qwen 3.8 会商”；本轮未调用 Qwen，后续仅复用已存在的同一 Luna checker 会话。
- ClinicalFact 已强制 Project/Subject/Episode/Snapshot 范围和 typed polarity；数值事实/谓词必须有显式单位，无量纲使用 `unitless`。Evaluator 只能读取 Gate 接受且与当前范围一致的事实。
- Assessment Gate 现在独立从 EvidenceRequirement/EvidenceExpectation、阶段、冲突和三值求值重建 gap 和 decision；Agent 候选不能用 gap 改写 UNKNOWN。得到确定 TRUE/FALSE 的逻辑树不会继承不影响结果的兄弟分支不确定原因。
- 纯未到期组件在当前阶段直接发布 `not_due + future_stage_not_due`，不被当前证据冲突提前升级为阻断；到期后必须重新投影为当前证据状态。
- FinalAssessment、ActionRequest 和 EpisodeRollup 均由发布函数生成指纹及 accepted GateResult；Fixture 完整性校验会拒绝被拒 Gate、输出哈希不符或跨范围引用。
- ProtocolIntegrity 不再接受调用方填写的官方编号清单；改为对比绑定正式方案哈希的 ProtocolIntegrityManifest，逐项校验完整 Rule 树、逻辑、单位、时间窗、例外、EvidenceRequirement 和 WorkflowStage。
- 合成规则已实际包含嵌套 `ALL/ANY/NOT`、研究者专业判断和随机日期时间窗，不再只是 Schema 理论能表达。
- UAT 生成器不再把筛选 Fixture 换 ID 后复制成基线；每个 Episode 都按当前阶段重新计算 Expectation、Candidate、FinalAssessment、Action 和 Rollup。当前 UAT 是 6 名主要受试者 x 筛选/基线 12 Episode，加预筛和导入/洗脱期 2 个模板，共 14 Episode。
- ProtocolDiffExample 现携带当前和拟议两套真实 RuleSet，新增、删除和逻辑/时间窗变化编号由代码从实际结构差异验证，调用方无法自行“宣布”差异。
- 当前合同专项验证为 `91 passed`，默认全套为 `227 passed, 1 skipped, 18 subtests`，legacy 只读回归为 `130 passed, 1 skipped`；编译、diff 检查和 8 个生成制品的两次哈希重现均通过。尚未完成同一 Luna checker 三次复核，因此 Phase 0.5 仍不可归档。

2026-08-12 Phase 0.5 同一 Luna checker 第三次复核后的修复（进行中）：

- 复核提交 `3eb994f` 仍被拒绝。真实问题不是文案矛盾，而是发布权边界仍有旁路：Assessment Gate 接受 caller-supplied evaluation；UNKNOWN 事实可夹带 typed value；`on` 时间方向忽略区间/半衰期；候选可伪造观察值、单位和 Span；Agent 输出 scope 不完整；方案 Manifest 仍可由调用方自证；Action/Rollup 未强制验证完整上游 publication。
- Assessment Gate 已改为在 Gate 内从 accepted Evidence Gate、规则组件、事实、Span 和锚点独立重建 Evaluation；候选观察逐项对比 Evaluator 推导值、单位、fact/span 和 reason code。UNKNOWN 事实禁止携带 value/unit，`on` 禁止携带上下界或半衰期参数。
- 新增 Evidence Acceptance Gate；AssessmentCandidate、FinalAssessment、ActionRequest、EpisodeRollup 形成逐层 accepted GateResult 闭包。Action 必须引用产生其 gap 的 AssessmentPublication，Rollup 必须验证同一 Episode 内 Assessment/Action publication，不能只凭自洽指纹进入汇总。
- 新增 `ProtocolAuthorityRecord` 与独立 Authority Gate：记录正式方案哈希、期别、完整规则/流程、逐规则来源锚点及人工核对元数据；Manifest 只能从 accepted Authority Record 构建，Protocol Integrity Gate 再对 ProtocolVersion/RuleSet/Workflow/Manifest 闭包重算。
- AgentCall 的 `gate_result_ids` 强制非空；受试者 Agent 及 Eligibility/Evidence/Critic 输出完整绑定 Project、RuleSet revision、Subject、Episode、Run、Snapshot、Source 和创建调用，跨 scope/call 候选被拒绝。
- UAT 模型现强制实际覆盖 `ALL / ANY / NOT`、可执行时间窗、明确障碍/当前缺口/未见明确障碍、四类阶段及基线增量重算；新增语义退化测试，不能靠 14 个结构化 Fixture 的数量通过验收。
- Evidence Gate 进一步封闭为 Normalizer AgentCall -> EvidenceNormalizationCandidate -> Fact/Span -> accepted GateResult；Fixture 保存候选并可重算闭包，Assessment 不能在 Gate 外替换另一组事实。FinalAssessment 与 ActionRequest 也补齐 RuleSet revision，Action 额外绑定 Snapshot。
- AgentCall 进一步补入 `protocol_version_id`，并要求 Candidate Gate 依赖已接受的 Agent 输出 Schema Gate；FinalAssessment、ActionRequest 和相应 Agent 输出也完整携带 ProtocolVersion/RuleSet revision 作用域。
- 新增回归后 V2 合同专项为 `106 passed, 2 subtests passed`；默认全套 `236 passed, 1 skipped, 18 subtests`；legacy Python 3.9 `130 passed, 1 skipped`。生成物双跑哈希一致，同一 Luna checker 四次复核尚未完成，Phase 0.5 继续冻结。
- 用户已明确“不用再找 Qwen 3.8 会商”；Qwen 3.8 保持禁用，本轮仅复用原 Luna checker 会话。
- 本轮本地全量验证的唯一跳过仍为既有 MG-K10-SAR/06003 OCR 缓存 Fixture 不存在。`compileall`、`git diff --check` 通过，4 个 Schema/OpenAPI 与 4 个 Fixture 连续两次生成 SHA-256 一致。

2026-08-13 Phase 0.5 同一 Luna checker 第四次复核后的根因修复（待第五次复核）：

- 第四次复核拒绝 `e2cfd9c`，提出 7 个 P1、2 个 P2：下游只核局部 Gate；AgentCall 未绑定实际 typed Candidate；Assessment 可替换组件；Fixture 保存未水合 Candidate；AgentCall 未核 Protocol/RuleSet scope；方案权威缺服务侧确认事件；Pydantic 条件未进入 Schema；UAT 可在保持计数时改变语义且无真实 `historical_source_unavailable`；错误码仍是自由字符串。
- AssessmentPublication 现保存 RuleSet、AssessmentCandidate、Evidence Candidate、两个 AgentCall、各层 Gate、锚点、Expectation 和 Conflict，并在验证时从完整闭包重算。ActionPublication 内嵌 AssessmentPublication 并重算；EpisodeRollup 对每条 Assessment/Action 完整闭包重放，不接受另一份调用方上游对象。
- Fixture 重放不再按“第一个相同 Candidate”取 Gate，而从 FinalAssessment Gate 的输入引用反向锁定唯一 Candidate Gate 和 Evidence Gate。修复过程中还发现 AgentCall Gate 校验块误缩进在异常分支后、正常路径未执行，已纠正为每个调用核对 ProtocolVersion、RuleSet/revision 及唯一 accepted Schema Gate。
- AgentCall 用 `typed_output_hashes` 逐实体绑定实际 Candidate；Fixture 持久化水合后的 AssessmentCandidate。`AgentCall.error_codes` 和 `GateResult.error_codes` 改为封闭 `RuntimeErrorCode` 枚举。
- 新增由服务记录的 `ProtocolAuthorityConfirmation`，精确绑定方案 SHA、AuthorityRecord SHA/ID、确认命令、确认人和时间；Authority Gate、Manifest、ProtocolVersion 和 Integrity Gate 均纳入该事件。逐规则来源锚点必须以当前 `protocol_version_id` 为前缀。
- UNKNOWN ClinicalFact 禁止 value/unit、`direction=on` 禁止时间窗/半衰期的约束已进入 JSON Schema/OpenAPI 条件语句，并由生成 Schema 的反例测试验证。
- UAT 除统计运算符外，逐 Episode 校验关键复合排除规则为固定 `ALL(研究者判断, ANY(阈值, 随机前28天用药), NOT(测量无效))` 语义；新增保持 ALL/ANY 数量但互换位置及 28->29 天的变异测试，并由第 4 名合成受试者筛选 Episode 实际产生 `observed_weak + historical_source_unavailable`。
- 当前验证：V2 `111 passed, 2 subtests`；默认全套 `241 passed, 1 skipped, 18 subtests`；legacy Python 3.9 `130 passed, 1 skipped`；唯一跳过仍为 06003 OCR 缓存缺失。生成器双跑 8 个制品 SHA-256 完全一致，`compileall` 与 `git diff --check` 通过。
- 用户明确不再找 Qwen 3.8 会商；本轮未调用 Qwen，后续仅复用现有 Luna checker `019ff5fa-ccc9-7cc0-8f38-2cc489783423`。在该 checker 无阻断接受前，Phase 0.5 保持 `in_progress`，Phase 1 继续冻结。

2026-08-13 Phase 0.5 同一 Luna checker 第五次复核：

- 候选 `39fd4de` 被拒绝，Phase 0.5 继续 `in_progress`，不得进入 Phase 1。已关闭：Fixture 水合 Candidate、Agent Protocol/RuleSet scope、Schema/OpenAPI 条件、UAT 语义/历史来源场景、封闭错误码。
- 仍开放的根因不是字段缺失，而是“调用方提供一整套可同步重算的自洽对象”仍可冒充服务端已接受状态：ReviewEpisode/锚点/Expectation/Conflict/半衰期、Agent Schema Gate、RuleSet/Integrity Gate、ProtocolAuthorityConfirmation 和来源清单均缺少只读服务注册表反查。
- 具体 P1：Assessment 可接受伪阶段/锚点/Expectation；伪 Agent Schema Gate 可同步重算；最终 Assessment 未再次验证 typed Candidate；同 ID/revision RuleSet payload 可替换；Fixture 顶层 Fact/Span 只比 ID 不比 payload；Confirmation 与 Manifest source_refs 可自造。P2：Evidence 路径误用 `gate_result_ids[0]`；文档过早宣称闭环。
- 下一修复不再继续堆哈希字段：建立服务端只读发布注册表和版本化 ReviewContext publication；所有发布路径按 ID 解析唯一上游。方案确认改为注册的命令事件，方案来源改为注册的来源目录；Fixture 对 Fact/Span 逐 payload 比较，并补“同步重算全部 Gate 仍拒绝”的对抗测试。
- 用户要求继续严格按设计书/分阶段计划/Trellis 实施；最新全局与项目 `AGENTS.md` 已重读。所有用户文字保持中文临床语境，清除程序员/日志式界面术语；不扩展安全性测试，聚焦产品功能、临床逻辑、证据与真实可用性。测试与复核采用长等待，不因延迟随意 fallback；Qwen 3.8 继续禁用。

2026-08-13 Phase 0.5 第五次拒绝后的根因修复（待第六次复核）：

- 新增只读 `TrustedPublicationRegistry` 与版本化 `ReviewContextSnapshot`。Assessment 不再接受调用方重复提交阶段、日期锚点、Expectation、Conflict 或半衰期；这些输入只从已登记上下文派生。Action/Rollup 必须携带同一注册表重放完整发布链。
- Agent Schema Gate 必须同时被 AgentCall 的 `gate_result_ids` 声明；Assessment 发布再次核对 typed Candidate 哈希并精确重算 Candidate Gate。同 ID/revision 的 RuleSet 仍按完整 payload 哈希核对，并绑定已登记的 Protocol Integrity Gate。
- 方案权威确认改由已登记的服务操作事件派生确认人和时间；Manifest 的来源字符串改为可解析的登记来源记录。Fixture 额外持久化命令事件和来源记录，但验证时必须使用验证前已存在的注册表，禁止从待验证 Fixture 自建信任。
- Fixture 顶层 Fact/Span 与 accepted Evidence Candidate 逐完整 payload 比对；Agent/Evidence Gate 不再依赖 `gate_result_ids[0]`，按门类型、调用声明和唯一性解析。
- 新增同步重算对抗测试，覆盖伪 Evidence Candidate+AgentCall+Gate、伪 Assessment Candidate+AgentCall+Gate、同 ID/revision 替换 RuleSet、重算服务确认事件、重算方案来源记录。局部对象全部自洽仍不能替代服务端登记状态。
- 当前验证：V2 `115 passed, 2 subtests`；默认全套 `245 passed, 1 skipped, 18 subtests`；legacy Python 3.9 `130 passed, 1 skipped`；唯一跳过仍为 06003 OCR 缓存缺失。8 个生成制品双跑哈希一致，`compileall` 与 `git diff --check` 通过。
- Phase 0.5 仍为 `in_progress`，必须由同一 Luna checker 第六次无阻断接受后才可归档并创建 Phase 1 Trellis 子任务。Qwen 3.8 保持禁用。

2026-08-13 Phase 0.5 同一 Luna checker 第六次复核：

- 候选 `9becd6b` 被拒绝，任务继续 `in_progress`。第五轮的审核上下文、typed Candidate、同 ID/revision RuleSet、Fixture Fact/Span 和 Gate 顺序问题已关闭；服务事件/来源与既存注册表只部分关闭。
- 真实 P1：Candidate/Evidence Gate 自身仍未反查注册表；Authority Gate 可只改时间戳后由调用方重算；EpisodeRollup 接受空 Assessment/Expectation/Action 并发布“未发现明确障碍”；Action 的责任方、动作、可接受证据、到期阶段和重算范围仍由调用方任意填写；临床 SourceDocumentVersion、PromptVersion、ModelConfig、Subject、Snapshot、Run 未进入注册表完整 payload 闭包。
- P2：Fixture 可附加未登记但自洽的额外 AgentCall/Schema Gate；证据文档对 Action/Rollup 闭包表述过早。
- 根因统一为：仍有发布函数只验证调用方传入对象的内部一致性，或只验证“被选中路径”，没有证明全集来自验证前既存服务状态。下一轮必须让 Candidate/Evidence/Authority/Action/Rollup 全部消费注册表解析出的唯一实体和完整期望集合。
- 第六轮独立复核自行确认 V2 `115 passed + 2 subtests`、8 个生成物逐字节一致、`compileall`/`git diff --check`/`uv lock --check` 通过；测试绿灯不构成验收。Phase 1 继续冻结，Qwen 3.8 继续禁用。

2026-08-13 Phase 0.5 第六次拒绝后的根因修复（待第七次复核）：

- `TrustedPublicationRegistry` 已扩展到 Candidate、Evidence、Assessment、Action、RuleSet、ReviewContext、Project、Subject、Episode、Snapshot、Run、SourceDocumentVersion、Expectation、Prompt、ModelConfig 及方案权威/来源/完整性审计实体；所有读取均返回深拷贝，只能由应用服务签发。
- Candidate Gate、Evidence Gate 和 Authority/Integrity Gate 均反查验证前已登记的完整 payload。Evidence Gate 的闭包包含完整来源文件版本；Integrity Gate 的闭包含完整 Authority Gate，而非仅绑定 ID。
- Action 发布接口只接受最终判断、缺口类型与服务生成 ID；责任方、补充内容、可接受证据、到期节点、触发证据和重算范围由规则组件、证据要求、当前节点和已发布判断确定性派生。旧生成器中已失效的人工文案参数与映射已清理。
- EpisodeRollup 必须一一覆盖 RuleSet 全部组件和全部 EvidenceRequirement，并为每个最终判断缺口包含唯一 Action；空集合、不完整、重复、跨节点或与注册表全集不一致均拒绝。
- Fixture 完整性校验要求其全部 AgentCall、Gate、Candidate、Assessment、Action、临床来源与审计对象已预先登记；夹带内部自洽的额外记录不能成为信任来源。
- 修复过程发现 UAT 基线新增的后续节点事实只进入 Evidence Candidate、未回写 Fixture 顶层事实，导致完整 payload 集合不一致；已从生成源修复并补回归测试，而非放宽校验。
- 新增 13 项对抗场景；当前 V2 `128 passed + 2 subtests`，默认全套 `258 passed, 1 skipped + 18 subtests`，legacy Python 3.9 `130 passed, 1 skipped`。8 个 Schema/OpenAPI/Fixture 连续两次生成的 SHA-256 完全一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 仍为 `in_progress`，不得创建 Phase 1；下一动作是提交本候选并复用同一 Luna checker `019ff5fa-ccc9-7cc0-8f38-2cc489783423` 进行第七次验收。Qwen 3.8 保持禁用。

2026-08-13 Phase 0.5 同一 Luna checker 第七次复核：

- 候选 `ac0e982` 被拒绝，Phase 0.5 继续 `in_progress`，不得进入 Phase 1。已确认关闭：EpisodeRollup 的完整 Assessment/Expectation/Action 集合；Action 责任方、动作、证据形式、到期节点、触发定位和重算范围的确定性派生。
- P1 根因仍是完整作用域图未成为同一个注册表不变量：Candidate、Evidence、AgentCall 可以同步改成未登记的 `protocol_version_id`，同时保留原 Episode/Run/Project/RuleSet，局部对象仍会被接受。Registry 尚未独立登记 `ProtocolDocumentVersion`。
- 另一个 P1：Protocol Integrity 虽已绑定完整 Authority Gate，但仍未对调用方传入的 ProtocolVersion 与 ProtocolIntegrityManifest 执行完整 payload 反查，可替换版本号或新建自洽 Manifest。
- P2：PromptVersion 只按 ID 存在性查找，尚未强制节点与 AgentCall 一致；Fixture 对完全相同 ID 的 Fact、Span、Call、SourceDocument、Prompt、Model 等重复记录会先经 set/dict 折叠；实施证据文档把“本地已修”写成“已关闭”过早。
- 下一轮统一改造：新增独立 ProtocolVersion 注册实体和共享审核作用域解析器；Evidence、Candidate、Assessment 统一核对 Project/ProtocolVersion/RuleSet/Episode/Run/Snapshot/Prompt；Integrity 先反查 ProtocolVersion 与 Manifest；Fixture 所有顶层实体先做 ID 一对一基数检查。
- 同一 checker 实测 V2 `128 passed + 2 subtests`、8 个生成物一致、`uv lock --check`/`git diff --check` 通过；这些绿灯没有覆盖上述绕过。第八次仍复用同一 checker，不调用 Qwen 3.8，不 fallback。

2026-08-13 Phase 0.5 第七次拒绝后的本地根因修复（待第八次复核）：

- 新增 `app/domain/gates/scope.py`，把 Project、独立 ProtocolDocumentVersion、RuleSet、Subject、ReviewEpisode、ReviewRun、EvidenceSnapshot、SourceDocumentVersion、PromptVersion 和 ModelConfig 解析为一个不可混搭的已登记审核作用域。Evidence、AssessmentCandidate 和最终 Assessment 均复用同一校验，不再各自维护局部 ID 比较。
- Registry 新增独立 `protocol_document_version` 类型。Project 内嵌方案版本必须与该登记 payload 完全一致；Episode、Run、RuleSet、Snapshot 与 AgentCall 的 protocol/project/revision/source 集合必须构成同一图。
- Protocol Integrity 在重算前精确反查 ProtocolVersion 与 ProtocolIntegrityManifest；调用方替换版本名、重算自洽 Manifest 或更换 Manifest ID 均不能成为新信任根。
- PromptVersion 必须满足 `prompt.node == agent_call.node` 且 Schema 合同版本与候选一致；ModelConfig 仍由已登记 ID 唯一解析。
- Fixture 对 19 类顶层/嵌套实体列表在任何 set/dict 折叠前执行 ID 唯一性检查，覆盖 checker 复现的相同 Fact、Span、Call、Document、Prompt、Model 重复以及相邻实体。
- 新增跨未登记 protocol、Prompt 节点漂移、ProtocolVersion/Manifest 替换和 11 类完全重复记录反向测试。本地 V2 `132 passed + 2 subtests`，默认 `262 passed, 1 skipped + 18 subtests`，legacy `130 passed, 1 skipped`；8 个制品双跑 SHA-256 一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- 本节只记录本地候选，不宣称独立关闭；Phase 0.5 保持 `in_progress`，第八次只复用同一 Luna checker。

2026-08-13 Phase 0.5 同一 Luna checker 第八次复核：

- 候选 `6bfba2c` 被拒绝；第七次五类 finding 已全部确认关闭：未登记方案版本无法发布 Candidate/Evidence/Assessment；ProtocolVersion/Manifest 替换被拒绝；Prompt node 错配被拒绝；19 类 Fixture 实体重复 ID 被拒绝；文档正确区分本地候选与独立验收。
- 新 P1：共享 scope 解析了 SourceDocumentVersion 但只比较 ID 集合，未比较 `source.review_stage <= episode.stage`，导致筛选 Episode 的直接 Candidate/Evidence/Assessment 发布可消费已登记的基线来源。
- 新 P2：Snapshot 的 `source_document_version_ids` 可重复同一 ID；AgentCall 的 `gate_result_ids` 可重复同一 Schema Gate。set 比较和局部 Gate 检查会掩盖重复引用。
- 下一修复在共享 scope 统一加入阶段排序、Snapshot/Agent 引用唯一性和唯一 Schema Gate 检查，并补三层直接发布负例。Phase 1 继续冻结，第九次仍只复用同一 checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 第八次拒绝后的本地根因修复（待第九次复核）：

- 共享审核作用域新增来源阶段排序，当前 Episode 不能读取更晚节点的 SourceDocumentVersion；该检查位于直接发布共用路径，不再仅依赖 Fixture 完整性校验。
- EvidenceSnapshot 的来源 ID、AgentCall 的来源 ID 和 Gate ID 均必须唯一；每个 AgentCall 必须且只能绑定一个结构化输出 Gate。Fixture 在进入 set/dict 处理前也显式检查相同引用基数。
- 新增 Evidence 与 Candidate 直接发布未来来源负例、FinalAssessment 重放未来来源负例、重复 Snapshot 来源和重复 Gate 引用的直接发布及 Fixture 负例。
- 本地验证为 V2 `135 passed + 2 subtests`、默认全套 `265 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑 SHA-256 一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- 本节仍只描述本地候选，Phase 0.5 保持 `in_progress`；第九次继续复用同一 Luna checker。

2026-08-13 Phase 0.5 同一 Luna checker 第九次复核：

- 候选 `e12b88e` 被拒绝；第八次所有 finding 已确认关闭，包括 Candidate/Evidence/FinalAssessment 的未来节点来源、Snapshot/Gate/Source 重复引用、零个或多个 Schema Gate 及三组相邻阶段边界。
- 唯一 P2：共享 scope 只保证恰好一个 Schema Gate，未验证 AgentCall.gate_result_ids 中额外声明的 Gate。直接发布可夹带一个 rejected 或 scope/hash 错配的额外 Gate，Fixture 路径则会拒绝。
- 下一修复统一直接发布与 Fixture 合同：共享 scope 对每个声明 Gate 逐一检查 accepted、AgentCall 引用、input scope、revision map 和 output hash。Phase 1 继续冻结，第十次仍复用同一 checker。

2026-08-13 Phase 0.5 第九次拒绝后的本地修复（待第十次复核）：

- 共享 scope 现在逐一读取 AgentCall.gate_result_ids 的所有已登记 Gate，不再只挑选唯一 Schema Gate；每项必须 accepted，input/accepted refs 必须包含当前调用，input_scope_hash、input_revision_map 和 output_hash 必须与 AgentCall 完全一致。
- 新增 Evidence 直接发布夹带 rejected Gate、夹带 scope 错配但 accepted 的 Gate，以及 FinalAssessment 夹带 rejected Gate 的反向测试；Fixture 与直接发布合同现使用同一严格度。
- 本地验证为 V2 `137 passed + 2 subtests`、默认 `267 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 仍为 `in_progress`；第十次继续复用同一 Luna checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 同一 Luna checker 第十次复核：

- 候选 `a249d9a` 被拒绝；第九次直接发布 finding 已确认关闭。Evidence、Candidate、FinalAssessment 均拒绝 rejected Gate 和五类错配 accepted Gate，并允许一个 Schema Gate 加多个完整接受的非 Schema Gate。
- 唯一 P2：Fixture 的 AgentCall 循环仍有一份较弱手写 Gate 检查。追加一个未参与下游发布的 AgentCall 时，可夹带 input_scope_hash/input_revision_map 错配的 accepted 非 Schema Gate。
- 根因是直接发布和 Fixture 重复实现同一闭包。下一修复让 Fixture 每个 AgentCall 无条件复用 `require_registered_review_scope`，不再依赖是否被 Evidence/Assessment 使用。Phase 1 继续冻结，第十一次仍复用同一 checker。

2026-08-13 Phase 0.5 第十次拒绝后的本地修复（待第十一次复核）：

- `validate_fixture_scope` 的每个 AgentCall 现在无条件调用 `require_registered_review_scope`，因此所有声明 Gate 都执行与直接发布完全相同的 accepted、调用引用、scope、revision 和 output 闭包检查。
- 新增未参与任何 Evidence/Assessment 发布的额外 AgentCall 场景：即使 Schema Gate 合法，只要附加 accepted Gate 的 input_scope_hash 或 input_revision_map 错配，Fixture 也会拒绝。
- 本地验证为 V2 `138 passed + 2 subtests`、默认 `268 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 继续 `in_progress`；第十一次仍只复用同一 Luna checker。

2026-08-13 Phase 0.5 同一 Luna checker 第十一次复核：

- 候选 `1535304` 被拒绝；未参与 Evidence/Assessment 发布的 AgentCall 现已确认执行全部 Gate 闭包检查。
- 唯一 P2：可向 Fixture 和预先 registry 同时追加一个完全不被 AgentCall、Protocol、Assessment、Action、Rollup 引用的 GateResult，当前只检查其已登记，未检查它属于当前发布图。
- 下一修复按 Protocol Authority/Integrity、AgentCall 声明 Gate、Assessment 发布链、Action 和 EpisodeRollup 建立显式 Gate 归属集合，拒绝任何无业务归属 Gate 或孤立 Gate 子图；自由 input 引用不能产生归属。Phase 1 继续冻结，第十二次仍复用同一 checker。

2026-08-13 Phase 0.5 第十一次拒绝后的本地修复（待第十二次复核）：

- Fixture 的 GateResult 集合现在必须与当前发布对象显式拥有的 Gate 集合完全相等；历史/审计对象若未来需要保留，应进入独立集合，不能夹带在当前发布 Fixture。
- 新增单个孤立 Gate、互相引用的孤立 Gate 子图、以及向合法 Schema Gate 注入孤立 Gate ID 的反向测试，三者均在发布前拒绝。
- 本地验证为 V2 `139 passed + 2 subtests`、默认 `269 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 保持 `in_progress`，第十二次继续复用同一 Luna checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 同一 Luna checker 第十二次复核：

- 候选 `c22b4bb` 被拒绝；第十一次的孤立 Gate、孤立子图和自由引用绕过均确认关闭。
- 唯一 P2：可向 Fixture 与既存 registry 同时追加一个 scope 合法的 AssessmentCandidate，而不提供 Candidate Gate、不绑定 AgentCall typed output、也不进入 FinalAssessment，当前仍会接受。
- 下一修复从每个已验证 FinalAssessment 发布链反向取得 Candidate 与 Candidate Gate，要求 Fixture 候选集合精确等于已发布候选集合，且每个候选只进入一个最终发布链。Phase 1 继续冻结，第十三次仍复用同一 checker。

2026-08-13 Phase 0.5 第十二次拒绝后的本地修复（待第十三次复核）：

- Fixture 先为每个 FinalAssessment 构造完整 AssessmentPublication，再反向汇总已发布 AssessmentCandidate；候选 ID 不得重复进入多个发布链，且集合必须与 Fixture 的候选集合完全相等。
- 新增“registry 中已登记、scope 合法，但无 Candidate Gate、无 AgentCall typed output、无 FinalAssessment”的候选负例。
- EvidenceNormalizationCandidate 已由 Evidence Gate 与 Fact/Span 全集相等约束覆盖，不存在同构的空候选夹带路径。
- 本地验证为 V2 `140 passed + 2 subtests`、默认 `270 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- Phase 0.5 保持 `in_progress`，第十三次继续复用同一 Luna checker，不调用 Qwen 3.8。

2026-08-13 Phase 0.5 同一 Luna checker 第十三次复核：

- 候选 `efbebe6` 获得 `ACCEPT`，无 P1/P2/P3 阻断 finding；第十二次的 AssessmentCandidate 发布全集问题及前十二轮回归面均确认关闭。
- 独立复现覆盖已登记未发布候选、Candidate Gate 无 FinalAssessment、候选重复发布、同步替换、额外 AgentCall 与 EvidenceNormalizationCandidate；独立测试为 V2 `140 passed + 2 subtests`、默认 `270 passed, 1 skipped + 18 subtests`、legacy `130 passed, 1 skipped`、定向 `21 passed`，8 个制品逐字节一致。
- Phase 0.5 已满足退出门槛，按 Trellis 归档；Phase 1 不混入本阶段提交。

2026-08-14 Phase 1.5 多模型医学监查员角色验收：

- Phase 1 合成交互原型经 Kimi K3-256K 真实浏览器视觉/交互审评、独立临床逻辑审评、Codex 根因修订和新鲜 Kimi 会话复测。Grok Build 会话两次被运行时取消，不计端到端覆盖；Cursor/Grok 后备因浏览器权限受限，只计静态审查。
- 已从共享层关闭看板关注类别计数、冲突来源并列、父子/例外语义、无效导航回落、空 Profile 主题误判、溯源分类、证据快照/应备要求、合成时序与阻断不变量、布局跳动等问题。
- 复测发现并关闭 Patient Profile 事件借用同节点其他证据的问题：事件证据关系分为原始依据、判断依据、关联规则资料和无独立定位；可点击事件的规则组件必须与 EvidenceSpan 实际属主一致。
- 最终确定性证据：前端 205 项测试、后端 281 项测试、Playwright 283 项、桌面启动器 14 项全部通过；1 项历史 OCR 固定样本因文件不存在按条件跳过。真实 Chrome 100%/150%/200% 和 1280/1440/1920/390 视口无关键溢出、裁切或重叠。
- Phase 1.5 裁决为可进入 Phase 2。该裁决只接受信息架构、中文交互、证据诚实性和合成数据工作流，不代表真实方案解析、OCR、事实抽取、模型审核、持久化或真实报告已实现。
- Phase 2 必须承接：SQLite 领域层与持久任务；冲突同页来源的可区分摘录；Patient Journey 真实事件时间/精度；390px 长规则名称的渐进展示。V2 继续与 legacy 写路径物理隔离。

## 2026-08-14 Phase 2 规划冻结点

- 当前子任务：`.trellis/tasks/08-14-phase2-sqlite-domain-jobs`，状态 `planning`。
- 已完成：需求、技术设计、实施顺序、验收标准和执行/检查上下文清单；Trellis 校验及 `git diff --check` 通过。
- 已确定：V2 写入独立 `data_v2/`；使用同步 SQLAlchemy 2、SQLite WAL 和 Alembic；迁移前使用 SQLite backup API 生成并校验一致备份；领域历史记录追加写；任务、步骤、检查点和事件持久化；支持租约恢复、幂等、乐观并发及精确过期范围。
- 未开始：任何 Phase 2 产品代码、数据库迁移、接口、后台任务或前端订阅改造。
- 边界：本阶段不接入真实方案解析、上传/OCR、临床事实抽取、Patient Journey 或模型审核，不迁移或写回 legacy 项目。
- 下一安全动作：等待用户在最终规划摘要之后明确批准；获批后执行 `task.py start`，再按 `implement.md` 六个批次实施和独立验证。

## 2026-08-14 Phase 2 实施候选与验收前检查点

- 用户已批准Phase 2最终规划；Trellis子任务`.trellis/tasks/08-14-phase2-sqlite-domain-jobs`已进入`in_progress`。本轮未进入Phase 3方案解析、Phase 4上传/OCR或真实临床审核。
- V2已建立独立`data_v2/`边界、SQLAlchemy 2模型、Alembic `0001-0003`、WAL/外键/同步级别/忙等待/SQLite版本门禁、一致备份与完整性清单、迁移后schema与基础读写验证、失败自动恢复及首次失败半成品清理。
- 核心领域合同已映射为规范化关系与canonical JSON/hash；历史型记录追加写，人工可编辑记录使用revision；幂等键同内容复用、异内容冲突；上游变化打开结构化stale，新ReviewRun只关闭其覆盖范围。
- 持久Job支持同任务复合步骤主键、依赖图预检、原子事件序号、租约generation、长步骤心跳、检查点、退避重试、取消安全边界、进程中断与启动恢复。SSE支持`after_seq`和`Last-Event-ID`，断开不改变任务。
- SQLite物理时间列采用归一化UTC无时区存储，canonical payload保留合同时间；API边界强制恢复带UTC时间，避免浏览器猜测。该约定已写回数据库规范并有接口测试。
- 由于V2尚无真实业务数据且未发布，Phase 2内修正了`0002`的Job步骤复合主键/外键后从空库重建；这不是对已使用迁移的改写。进入真实项目后只能新增迁移。
- 当前本地证据：后端`460 passed, 1 skipped, 18 subtests passed`（唯一跳过为历史MG-K10-SAR/06003 OCR缓存夹具缺失）；前端Vitest`207 passed`；生产构建通过；Playwright`283 passed, 109按项目配置跳过`，覆盖1280/1440/1920/390视口。构建仅有既存主包体积提示。
- 尚未裁决Phase 2完成：下一步用独立新鲜上下文复核数据完整性、迁移恢复、并发、幂等、任务续订和当前页面无回归；找到问题必须回到系统层修复后重测。

## 2026-08-14 Phase 2 完成裁决

- 独立审评发现并关闭了五类真实基础缺陷：并发幂等冲突回滚外层事务、任务终败缺少独立终态事件、Checkpoint恢复与依赖级联事件进度不实、SSE异常游标回报客户端值、SQLite异常被笼统称为繁忙。
- 修复后第二轮审评进一步发现异常回填状态下未到退避时间的步骤可能泄漏租约，以及422错误无法指出具体字段；已从共享状态机和中文错误投影层修复并补回归。
- 两项结构扩张被Codex否决并写入数据库规范：ReviewRun通过唯一ReviewEpisode规范化继承rule_set_id，不重复保存第二份真相；stale的source_revision是内部不可变修订，同一已覆盖原因保持关闭，新发布必须产生新内部修订。
- 最终确定性证据：后端`467 passed, 1 skipped, 18 subtests passed`；前端`207 passed`；生产构建通过；Playwright`283 passed, 109按视口配置跳过`，覆盖1280/1440/1920/390及中文、无障碍、键盘、证据路径与横向溢出。
- CodeBuddy/Kimi 2.6给出静态`ACCEPT`；Pi/Minimax在运行全套测试后给出`REVISE`，其真实发现已修复，争议项由Codex按领域合同裁决。Grok 4.6修复后复核连续两次由自身运行时取消，没有终局结论，明确不计为通过；其上一轮完整报告中的真实问题均已纳入修复。
- 临时V2验收服务、临时数据库、测试结果目录和模型原始stdout已经清理；既有4173前端服务及两张并行修改的截图未触碰。
- Phase 2仅完成SQLite领域持久化与持久任务底座，不代表真实方案解析、OCR、Patient Journey、模型审核或真实入排项目已完成。下一阶段必须从Phase 3方案权威链与规则解构开始，不得将旧项目写回V2。

## 2026-08-14 Phase 3 最终规划与独立审评检查点

- 当前子任务：`.trellis/tasks/08-14-phase3-protocol-deconstruction`，状态 `planning`；尚未执行 `task.py start`，未写入 Phase 3 产品代码。
- 已完成 `prd.md`、`design.md`、`implement.md`、`research.md` 及 implement/check 上下文清单。真实只读探查确认：MG-K10-SAR 页眉可直接取得 `MG-K10-SAR-001`、`V2.1//2025年09月19日`；D001 页眉同时含模板版本和正式方案 `D001-02-002/V1.0/2025-12-10`，必须进行字段分类而非采信第一个版本号。
- 已复现旧链路的系统级失败：MG-K10-SAR III 可得到 IN 7/EX 16，D001 II 可得到 IN 6/EX 30，但两份研究流程表均返回空节点。Phase 3 因此把“流程表非空”升级为 Agent 前冻结并逐项核对的基线及以前必做项目录，漏项、占位项、跨访视误去重或来源只指向标题均阻止发布。
- 冻结两份目录：官方父规则目录；按研究期别和访视实例拆分的基线及以前必做项目录。Agent、手工修订和同会话修复不得增删目录项；相同检查在筛选和基线重复执行时保留两个 requirement 实例。
- II、III 默认独立项目和受试者空间；“操作无缝”、剂量选择衔接或继续纳入新的 III 期受试者均不构成合并依据。只有同一受试者队列连续跨期才可提出合并候选，且默认仍为独立、需二次确认。
- 来源采用 python-docx/OOXML 结构通道和 LibreOffice 派生 PDF 渲染通道；结构定位为主，“本次渲染页”为辅助。Docling-slim 与 pdfplumber 只在切片 1 用两份真实方案做有停止条件的许可/保真 spike，不预设采用。
- 首次解构和重新解构分开；同方案编号+同一期别已有正式项目时首次入口不得再建平行项目。重新解构要求同方案谱系和研究期别，合法新版本允许版本、日期、哈希变化，跨方案/跨期文件拒绝发布。
- CodeBuddy CLI/kimi-k2.6、Pi/cms-router/minimax-m3、Grok Build/grok-4.6 均以用户指定模型完成只读规划审评，无 fallback，均结论“修订后可开始”。共同根因已采纳；未采纳会阻断合法修订、写死子编号或复制事实源的建议。会商门禁已通过，精简证据位于 `reviews/codex_conference_phase3-protocol-plan-review_review.md` 和 `metrics/phase3-protocol-plan-review_conference_metrics.md`。
- 下一安全动作：等待用户审阅 Phase 3 最终规划并明确批准；获批后执行 `task.py start`，从切片 1 文档结构/开源候选 spike 开始，不跳到 Agent、前端或真实受试者审核。

## 2026-08-14 Phase 3 切片 1 完成裁决

- 用户已批准 Phase 3 最终规划，Trellis 子任务进入 `in_progress`；切片 1 已完成原始方案登记、DOCX/OOXML 结构提取、LibreOffice 渲染、双通道来源定位、不可变块集、领域契约与 Alembic `0004`。
- 原始 DOCX、规范块集和派生 PDF 均按 SHA-256 内容寻址保存；提取和渲染入口重新核对登记哈希，原路径被替换时拒绝继续。两份真实方案及其所在目录前后哈希、大小、mtime 与目录项一致。
- 独立审查复现并关闭了系统性问题：重复文本/表格锚点猜第一页、两个结构块借用同一物理范围、摘录仅在结构块内自证、CJK 字距漏配、`w:basedOn` 层级错误、`w:sdt` 静默漏提、未支持内容容器不提示、旧 PDF 被重渲染覆盖、长 span id 超出列宽。
- 精确来源门槛现在要求跨页与页内唯一、页范围可回验、跨 span 不碰撞；页眉页脚为降级提示。Pi 独立复测 MG/D001 剩余精确范围碰撞 `0/0`、页级核验失败 `0/0`。
- 已知限制：MG/D001 仍约有 1954/2120 个非空正文段落无可靠渲染页，均为诚实拒绝而非伪造页面。切片 3 前做带逆序检测的受限邻块插值 spike；插值/降级页不得单独满足 `source_coverage` 发布门槛。
- 最终确定性证据：协议测试 `47 passed`；全仓 `514 passed, 1 skipped, 18 subtests passed`。唯一跳过为遗留 06003 OCR 缓存夹具缺失。Grok 4.6 的有效静态发现已纳入，后续不完整输出不计最终放行；Pi 最终给出无 P0/P1 的独立放行结论。
- 下一动作：提交切片 1，随后进入切片 2 元信息、研究期别与权威解释材料；明确区分“身份来源权威性”和“规则正文定位精度”。

## 2026-08-14 Phase 3 切片 2 完成裁决

- 已完成方案身份元信息候选、正式方案与模板字段分离、优先级/同级冲突、II/III/共同/混合/未知适用图、严格单期投影、真正无缝候选和解释材料权威边界；对应 Alembic `0005` 与追加写仓储已建立。
- 主会场从真实 MG-K10 方案发现首轮投影会丢失整组共同排除标准；根因是整表聚合污染、同一表格单元格无局部上下文、共同适用语义过窄。现已改为原子段落先分类、同单元格最近标题继承，行/访视列仅在子块一致时聚合。
- 共同语义保守化：裸“共同排除标准”可建立共享上下文；“III期共同适用”仍属 III 期；同时出现 II/III 但没有明确两期配对+共享语义时必须为 `mixed`，不进入任一单期 Agent 输入。
- 元信息不再由低优先级文件名制造伪冲突；文件名兜底分开编号/版本/日期。确认后决策不得仍携带未解决冲突，必须精确选中候选并保留既往解决历史、显式项目代号与 day/month/year 日期精度。
- 来源 `text/source_ref` 始终不变，`projection_text` 只能是跨期原文的派生显示；项目代号、官方日期和确认时间均加入列/payload 镜像检查。未增加 SQLite UPDATE/DELETE 触发器：本地单用户且不做安全性测试，继续遵循 Phase 2 已冻结的仓储追加写+读取哈希/镜像拒绝边界，不为本切片另造全库触发器。
- 新鲜独立 Luna 审查会话三轮拒绝，逐次揭示冲突状态、单期共同词泄漏、裸共同标题丢失、日期精度和混合语句过宽等边界；第四轮给出无 P1/P2 的 `ACCEPT`。最终协议切片 `63 passed`，全仓 `530 passed, 1 skipped, 18 subtests passed`；唯一跳过仍为既有 06003 OCR 缓存夹具不存在。
- 下一安全动作：切片 3 先执行有停止条件的页定位恢复 spike，再冻结官方父规则目录和基线及以前必做项目录；未完成目录对账前不进入 Agent 发布。

## 2026-08-14 Phase 3 切片 3A 页码定位恢复冻结点

- 已用真实 MG-K10-SAR 与 CMS-D001 完成同结构容器邻块留一验证。同页夹逼分别为
  `130/130`、`158/158` 全部正确；允许相邻页后准确率降为 `92.27%`、`95.35%`，
  允许两页范围更低，因此不采用跨页猜测。
- 正式来源层只在前后精确正文定位同容器、同派生物、同页且各距不超过 12 个结构块
  时补充页面提示；跨 section/表格单元格、相邻页、顺序倒置及页眉页脚均拒绝推断。
- 补充结果始终为“降级页面提示”，不含伪摘录或字符范围，不能单独通过来源覆盖门槛；
  原始唯一文本范围和唯一表格页定位仍是正式来源定位。
- 定向来源层与两份真实方案测试 `19 passed`。下一步进入官方父规则目录和基线及以前
  必做项目录冻结；目录未与原文逐项对账前，不调用解构 Agent 发布规则。

## 2026-08-14 Phase 3 切片 3 无损暂停点

- 已建立冻结官方父规则/基线前必做项目录、结构化解构合同、同会话分批输出、局部定向修复和确定性发布门禁。
- 修复 OOXML 上标/下标丢失与显示脚注污染：结构来源保留 `^`/`_`，语义标签只移除末尾脚注，不破坏 `10^9/L`。MG 目录不再出现“漏胸片、收随机动作”的同数错换，有效审核项为 41；D001 为 50。
- 全新 MG-K10-SAR III 期真实运行在 6 次同会话尝试后通过门禁：IN 7、EX 16、41 个必做项，23 条父规则、73 个组件、187 条证据要求、2 个工作流节点，最终问题数 0，源方案未变。
- 任务保持 `in_progress`。尚未运行 D001 II 期真实 Agent，尚未做切片 3 最终全量回归和独立终局审查。恢复时先跑完 `tests/v2/protocols`，再运行 D001，不跳到切片 4。

## 2026-08-15 Phase 3 切片 3 D001 根因修复检查点

- 修复前 D001 II 期新鲜运行已完成目录与初稿验证：IN 6、EX 30、50 个基线及以前必做项，源方案未改变；但有限修复耗尽后仍需核对。完整反例已归档，不能作为正式草稿。
- 已从系统层分离“审核阶段”和“相对日期锚点”，新增首次给药日，建立公平修复轮转和逐父规则防回退，并强化非连续逐字溯源。未加入 D001/SAR 特异条款。
- 当前确定性证据：方案模块 `180 passed`；契约/领域逻辑/日期评估 `165 passed`；传输、适配器和门禁聚焦 `48 passed`。
- 修复后首次真实重跑在初稿分批期间遇到远程模型空正文。传输现只做一次同请求重试；连续失败时保留已完成会话并正常返回“需要核对”，同时仅记录结束原因和推理长度，不保存推理正文。
- 切片 3 仍为 `in_progress`，未进入切片 4。下一步是重新运行 D001 II，并对时间锚点、阶段资料要求、例外、父子逻辑和逐字来源逐项验收，再做独立终局审查。

## 2026-08-16 Phase 3 切片 3 完成裁决

- 最终独立审查从真实原文发现旧门禁漏掉两种频次：D001 EX-04“2年内发生2次或以上”
  和 MG EX-04“1周≥4天”。共享层已改为从完整组件提取频次、要求直接事件分支绑定，
  并支持次数/周期及发生天数/周期；频次不能套到无关兄弟分支。
- 多段逐字来源的换行现为明确边界，括号时间限定不再跨段误归属。DeepSeek 无状态会话
  支持从完整持久历史恢复，已水合草稿可无损还原语义候选并仅替换指定父规则。
- D001 II 最终会话 `protocol-chat-0cf91707a73a40a4ad46964068ae336d`：IN 6、EX 30、
  必做 50，EX-04 复发性带状疱疹独立保留 2 次/2 年，12 类门禁全通过。
- MG III 最终会话 `protocol-chat-d13b5ca3a69944b099912d92bc6f4671`：IN 7、EX 16、
  必做 41，EX-04 保留 4 天/1 周；唯一问题为 EX-07w“6个月内存在或疑似蠕虫感染”
  未命名回溯起点，系统保持 `TIME_ANCHOR_UNRESOLVED`，不猜筛选日或随机日。
- 修复前后除 EX-04 外的父规则、组件、资料要求和顶层结构逐字段一致；原始方案哈希、
  大小、mtime 未变。新鲜独立 Luna 审查为 `ACCEPT`。
- 最终全仓回归 `687 passed, 1 skipped, 18 subtests passed`，唯一跳过为遗留 06003 OCR
  缓存夹具不存在；`git diff --check` 通过。
- Phase 3 父任务仍为 `in_progress`。切片 4 首次解构持久用例/API、前端工作台和受试者
  审核尚未启动；后续必须直接消费冻结的 `occurrence_window`、`source_clauses` 和访视实例，
  不重新猜测频次或时间锚点。

## 2026-08-16 Phase 3 无损暂停点

- 用户要求在详细记录和阶段清理后暂停。当前代码基线为 `e3dddb5`，切片 1-3 已完成；
  本轮只重读切片 4 范围和后端规范，未开始流程节点、发布事务、V2 API 或前端工作台实现。
- 完整恢复记录位于
  `.trellis/tasks/08-14-phase3-protocol-deconstruction/CHECKPOINT_20260816_PAUSED.md`，
  包含真实会话、数量锚点、唯一保留歧义、验证结果、下一步顺序和禁止误删边界。
- 阶段清理只移除最终修复前的 Agent 中间归档及可再生测试/字节码缓存；MG/D001 最终验收结果、
  页定位 spike、正式会商结论、任务设计记录和所有临床源文件保留。
- `output/` 下旧临床项目备份和受试者资料虽体积较大，但并非可确认缓存，本轮明确不删除。
- 恢复时先读取 Trellis 上下文和暂停检查点，再从切片 4 开始；不得跳到切片 5 前端或受试者审核。

## 2026-08-17 Phase 3 切片 4 完成裁决

- 已建立基线及以前的流程节点、规则事实与流程必做资料要求、无受试者资料核对模板、
  不可变草稿 revision、手工编辑/反馈/取消恢复、完整结构化差异和原子发布事务。
- 本轮反复审查定位并从共享层修复：重复访视误合并、发布重放输入不完整、澄清材料换绑
  方案来源、局部差异漏报、模板孤儿引用、规范化列漂移被列表隐藏、状态转换偷改审计正文，
  以及创建时间未纳入不可变镜像。没有加入 MG、D001 或具体条款的项目特异规则。
- 模板物理表现强制同 RuleSet revision、真实资料要求、真实审核节点三组外键及非空节点；
  读取先验正文哈希，再对全部镜像列和创建时间交叉校验。发布失败、旧草稿并发、输入变化、
  部分写入与幂等重放均有事务反例。
- 同一独立 `gpt-5.6-luna:max` 审查会话多轮 `REJECT` 后终局 `ACCEPT`，并额外复测通用
  Snapshot/Gate 创建时间漂移。隔离 V2 `667 passed, 2 subtests passed`；合并主分支后
  全仓 `797 passed, 1 skipped, 18 subtests passed`。唯一跳过仍为遗留 06003 OCR 缓存缺失。
- 当前代码基线从 `bc3f0dc` 前进至 `91a53cb`；两张并行修改的 UAT 截图未触碰。
  下一安全动作是切片 5 V2 API 与首次解构工作台，前端只消费已冻结合同，不自行重算临床逻辑。

## 2026-08-17 Phase 3 切片 5 实施中无损暂停

- 切片 5 初版位于隔离工作树 `.worktrees/phase3-slice5-exec`；主分支仍停在切片 4 验收提交 `aa7fca8`，未合并本切片代码。
- Codex 拒绝了“样例页面可操作即完成”的验收：后端原实现没有方案解构执行器，前端默认始终走样例仓储，因此已有测试未证明真实上传链路。
- 后端定向补全提交为 `bcadc56`，执行者报告已建立上传→结构/渲染→身份确认→类型化草稿→完整性→审阅的持久路径，V2 `676 passed`。该数据仍属执行者证据，Codex 未独立复测或放行。
- 前端 HTTP 补全、真实前后端联调、真实浏览器宽窄屏/缩放验收、新鲜独立审查与合并均未完成。
- 恢复时以 `.trellis/tasks/08-14-phase3-protocol-deconstruction/CHECKPOINT_20260817_SLICE5_PAUSED.md` 为第一依据。切片 5 通过前不进入重新解构、真实方案全流程或多模型医学监查员视角试用。

## 2026-08-17 Phase 3 切片 5 完成裁决

- 首次方案解构已形成真实 V2 API 与桌面工作台闭环：上传、任务恢复、方案信息和研究期别核对、
  草稿审阅、完整性检查、来源定位、保存及发布均使用切片 4 的持久合同。
- 上传元数据进入持久任务输入，执行器领取后与检查点合并，避免任务领取快于首个检查点写入时
  丢失来源文件；并发回归已覆盖。前端对未知响应做运行时校验，不再用类型断言掩盖合同漂移。
- 父子规则保持正式编号与层级；子项来源按自身 source span 映射。来源页优先采用真实渲染页，
  无页码时显示“结构块”，绝不把结构序号伪装成方案页码或伪造摘录、高亮。
- 产品视口冻结为最大化 1080P、2K、4K 桌面，不承担窄屏适配。真实 HTTP 浏览器在 1920 和
  3840 宽度均满足 `scrollWidth === innerWidth`、无控制台错误；三栏使用完整可用宽度。
- 最终确定性证据：V2 后端 `690 passed, 2 subtests passed`；前端 Vitest `225 passed`；生产
  构建通过；删除已不在产品边界内的窄屏专项后，Playwright `247 passed, 38 skipped`。并发跑
  普通构建与 `build:e2e` 曾互相覆盖
  `dist` 并制造 404，顺序复跑已证明非产品缺陷，后续验收命令必须串行写构建目录。
- 新鲜独立 `gpt-5.6-luna:max` 审查已完成并关闭 API/任务竞态、期别/日期类型、父子来源映射
  和定位精度问题。下一安全动作是切片 6；不得让前端重新计算八类差异或发布合法性。
- 2026-08-18 合并主分支后全仓后端 `820 passed, 1 skipped, 18 subtests passed`，前端
  Vitest `225 passed`、生产构建和 Playwright `247 passed, 38 skipped` 均通过。阶段清理已
  删除隔离工作树、一次性执行记录、trace 和失效截图矩阵；两张用户 UAT 图片保持未暂存。

## 2026-08-18 Phase 3 切片 6 完成裁决与无损暂停

- 已在同一项目内完成“上传同谱系新方案”和“基于反馈修订现有方案”两条重新解构路径；项目必须显式选择，研究期别和方案谱系沿用正式版本，成功发布形成新的不可变 RuleSet revision，不创建平行项目。
- 正式版本与新草稿逐父规则并列，确定性显示新增、删除、原文、逻辑、时间窗、例外、证据要求、应完成阶段八类差异。组件先按全局稳定来源对齐、再以展示编号保守兜底；仅 a/b 编号交换不会误报语义变化。
- 手工编辑只允许调整结构化理解，方案原文、顶层来源、组件来源引用/摘录全部冻结。原文纠错由语义修订器只重建选中官方父规则；规则、子项、来源映射及资料要求在保存前做全局唯一与一一闭包校验，阻止跨父规则身份复用和隐蔽重挂。
- 前端不再接受任意差异对象：单一解码边界校验 AND/OR/NOT 元数、比较符和值、时间锚点/方向/单位/上下界、例外、资料要求、应完成阶段及类别粒度；错误结构明确中止，不交给展示层猜测。
- 后台任务初始化修复为同事务写入任务、初稿和检查点，关闭执行器抢先领取造成上下文缺失的竞态。真实 HTTP 验收覆盖首次发布、项目选择、原文纠错和再次发布。
- 新鲜独立 `gpt-5.6-luna:max` 审查会话三轮拒绝后终局 `ACCEPT`。最终确定性证据：V2 后端 `746 passed, 2 subtests passed`；前端 Vitest `258 passed`；生产构建通过；常规 Playwright `256 passed, 41 skipped`；真实 HTTP 1920/2560/3840 三宽度 `3 passed`。
- 发生过一次非产品故障：真实 HTTP 生产构建与常规测试仓储共用 `frontend/dist`，且 Playwright 可复用旧 4173 preview，导致常规套件误连未启动 API。终止旧 preview、串行重建测试仓储后全量通过。后续不可并行运行两个会写 `dist` 的套件。
- 用户要求完成当前步骤后暂停。切片 7 尚未启动；未读取仓库外临床原始资料。恢复时先读取本节和 `CHECKPOINT_20260818_SLICE6_COMPLETE_PAUSED.md`，再用清洁 V2 数据目录开始 MG-K10-SAR III 与 D001 II 真实方案验收。

## 2026-08-18 Phase 3 切片 7 完成裁决与无损暂停

- MG-K10-SAR III 从原始 V2.1 方案完成清洁 V2 全流程：IN 7、EX 16、41 个基线及以前必做项、80 个子组件、201 条资料要求、3 个审核节点。EX-07“6个月内”没有命名回溯锚点，系统保留唯一 `TIME_ANCHOR_UNRESOLVED` 并阻止正式发布，没有猜测筛选/基线/随机日。
- D001 II 从原始 V1.0 方案完成清洁 V2 全流程并正式发布：方案编号 `D001-02-002`、项目代号 `D001-02`、IN 6、EX 30、50 个必做项、61 个子组件、127 条资料要求、3 个审核节点；完整性阻断 0，发布幂等重放未重复写入。
- 真实偏差均从共享机制修复：事件频次不再被当作检验指标；检查结果时效不再被当作事件发生窗；时效必须绑定原文点名检查及各审核节点；门禁缓存具备语义版本；局部反馈发生问题替换或增加时拒绝保存；Mac 休眠后的长任务在租约未被抢占时可续订；恢复 revision 可合法进入保存/取消/发布生命周期。
- 原始两份 DOCX 的 SHA-256、大小和 mtime 前后不变。最终验收 JSON 位于 `.trellis/tasks/08-14-phase3-protocol-deconstruction/metrics/slice7/`。
- 最终确定性证据：V2 `765 passed, 2 subtests passed`；前端 Vitest `267 passed`；生产构建通过；真实 HTTP/SQLite/后台任务在 1920×1080、2560×1440、3840×2160 为 `3 passed`。
- 用户要求无损暂停。切片 8 的 CodeBuddy CLI `hy3(max)`、Pi `cms-router/minimax-m3`、Grok Build `grok-4.6 (medium)` 三路视觉医学监查员试用尚未启动；恢复入口为 `CHECKPOINT_20260818_SLICE7_COMPLETE_PAUSED.md`。

## 2026-08-19 Phase 3 完成裁决

- 切片 8-9 已完成共享机制修正、两路有效独立医学监查员视觉复测、Codex 真实浏览器验收、全量回归和阶段清理。终局恢复记录归档于 `.trellis/tasks/archive/2026-08/08-14-phase3-protocol-deconstruction/CHECKPOINT_20260819_PHASE3_COMPLETE.md`。
- D001 II 保持 IN 6 / EX 30 并已发布；MG III 保持 IN 7 / EX 16，仅 EX-07s 的“6个月内”未命名回溯锚点阻止发布。这是正确的不确定保留，不是待用默认日期消除的系统错误。
- 共享层新增语义调用前的冻结输入检查点，防止整句来源污染兄弟原子条件时间窗，拒绝局部修订用新问题替换旧问题，并补全父规则实质性来源覆盖。前端将已发布任务与中断恢复分开，规则树默认只展开当前父项并支持深链自动展开。
- 最终回归：后端 `909 passed, 1 skipped, 18 subtests passed`；Vitest `275 passed`；生产构建通过；Playwright `256 passed, 41 skipped`。CodeBuddy `hy3(max)` 为“修正后接受”，Pi `minimax-m3` 为“接受”。Grok Build 4.6 medium 在旧会话、恢复会话和新会话中均因其 `read_file` 工具输出错误取消，没有可用裁决；未换模型或伪装完成。
- Phase 3 可归档。下一安全动作是按总实施计划建立 Phase 4 的受试者资料摄取、来源保留 OCR 与证据标准化任务。

## 2026-08-19 Phase 4 最终规划待批准

- 已在隔离工作树 `.worktrees/phase4-evidence-ocr-v2` 和分支 `codex/phase4-evidence-ocr-v2` 建立 Trellis 子任务 `.trellis/tasks/08-19-phase4-evidence-ocr-v2`；状态保持 `planning`，尚未修改 Phase 4 产品代码。
- 规划基于现有 V2 领域/SQLite/Job/前端审计、旧 OCR 来源保真审计和外部能力核查，形成 `prd.md`、`design.md`、`implement.md`：10 项需求、13 项验收标准、6 个带停止点的实施切片。
- 冻结的用户语义为“补充资料”和“建立完整资料快照”；两者均先预览后确认。快照不可变、按受试者和审核节点隔离；后续节点不得静默改写早期结果。
- 原生 PDF 正式路径计划使用现有 MIT 许可的 `pdfplumber` 获取真实坐标；扫描页先验证完整 PaddleOCR-VL 布局流水线。现有 oMLX 纯文本通道可保留，但不能伪装为布局或区域坐标。
- OCR 缓存身份升级为文件内容哈希、页码、识别配置和页面产物版本；全局 8 路准入使用持久租约，页面渲染另设背压。原文件、原 OCR 和页图不覆盖，校对追加写并记录影响范围。
- Phase 4 不实现临床事实、Patient Profile、逐条入排判断、行动闭环、跨受试者批量审核或报告。真实临床资料只读，旧项目不迁移。
- `implement.jsonl` 与 `check.jsonl` 已配置真实规范和研究上下文，`task.py validate` 通过。下一安全动作：等待用户审阅本版最终规划；仅在后续消息明确批准后运行 `task.py start`，从 Slice 4.0 页级金标准与布局能力试验开始。
- 独立 Sol 规划审查曾拒绝初稿，指出仅固定文件集合不足以复现当时有效 OCR/校对、资料替代与增量继承冲突、候选/失败/回滚状态机不闭合、文件格式分页路线缺失、定位/风险验收可被低质量实现绕过，以及 8 路计数单位不明。规划已统一修正为：快照绑定不可变 EvidenceProcessingRevision，激活/回滚追加 ActivationEvent；同名异内容必须选择新版本或并列保留；逐格式保存渲染/解码版本和页图输入哈希；冻结文本回读/定位/风险量化门槛；共享 oMLX 门禁是唯一真实推理 8 路额度。
- 宽屏验收不再把 1920×1080 的 200% 缩放错误当作三栏工作台支持范围，而按有效 CSS 宽度≥1280 组合验证。用户已明确不亲自试用，三路模型按量化无辅助任务脚本替代；该结果不得表述为真人可用性研究。
- 独立 Sol 共进行四轮只读规划审查。终局确认终态候选无出边，校对/回滚/冲突重试均创建新命令或新链；资料元数据和被引用资料关系均进入不可变处理修订；`0009` 基础处理修订不可激活，`0010` 只新建完整修订而不回写。最终裁决为“可提交用户最终审批”，记录见 `.trellis/tasks/08-19-phase4-evidence-ocr-v2/reviews/final-planning-review.md`。

## 2026-08-19 Phase 4 已批准并启动

- 用户已明确批准 Phase 4 最终规划。Trellis 子任务 `.trellis/tasks/08-19-phase4-evidence-ocr-v2` 已由 `planning` 切换为 `in_progress`，当前只执行 Slice 4.0 能力金标准；能力门槛未通过前不得创建正式 OCR 持久化或进入数据库迁移。
- 用户新增的证据工作台合同已写入 PRD、设计和实施计划：右栏按实际页序连续滚动 PDF、图片、多页 TIFF 和文档派生页；只有通过真实性门禁的页内区域坐标才绘制风险红 `#C00000` 重点框。文本范围、页内摘录或仅页码定位不得估算或伪造红框。
- 设计轨确定为 Kangzhe `site`，只支持有效 CSS 宽度不低于 1280 的最大化宽屏桌面，并按 1080P、2K、4K 及规定缩放组合验收；不新增窄屏工作流。
- 执行图已登记为三个顺序工作边界。首个实际工单收窄为 Slice 4.0，由当前日间首选路线 `Pi/cms-smk/deepseek-v4-flash:max` 执行；不因长耗时重复派发，完成后由独立新上下文检查者拥有放行权。
- 恢复锚点：先读取本节、任务 `prd.md`/`design.md`/`implement.md` 和 `runs/execution/phase4-evidence-ocr-v2/worker_01.md`；核对真实 diff 和量化测试后，才决定是否进入 Slice 4.1。
- 2026-08-19 检查者已修复并验收 Slice 4.0 基线：跨进程金标准生成确定性、pdfplumber 原生 PDF 四种旋转坐标、四级定位来源/边界绑定、OCR 页级哈希/状态/UTC 时间合同、风险去重与全页覆盖度量均有回归证据。布局候选结果明确是合成度量机制演示，不是 OCR 能力采用结论。
- 2026-08-19 同会话恢复复核确认：共享 oMLX 门禁下发起选择 `GLM-OCR-bf16` 的隔离请求，在 2 个无 PHI 合成视觉页上逐字回读一致，原始响应和门禁请求可由哈希/SQLite 记录复核；未发现显式机器坐标，因此冻结 text-only 文字路线、无坐标不画红框。响应模型名是 provider 自报，未保留独立服务清单/启动日志，不能宣称实际加载身份、一般准确率或生产适配器完成。
- Slice 4.0 能力停止条件现已满足；本次复核未进入 Slice 4.1、未创建迁移或正式 OCR 持久化。当前共享树的 Slice 4.1 ORM 已注册 6 张 `*_v2` 证据表但迁移 head 仍为 0007，标准 V2 迁移后校验报告 6 张表缺失；本检查不创建该越界迁移，故不对当前 Slice 4.1 代码放行；验收记录为任务 `research/slice4-real-omlx-probe.json`、`research/slice4-omlx-gate-probe.md` 和 `research/slice4-goldset-coordinate-spike.md`，历史 worker 报告保持不改写。

## 2026-08-19 Phase 4 Slice 4.1 独立检查者裁决

- 在隔离工作树中完成 Slice 4.1 复核并修复边界问题：`0008_evidence_ingestion` 与 ORM 的 6 张 Phase 4 证据表一致，SQLite 外键/WAL/备份及升降级有回归证据；含证据数据的降级会拒绝，避免丢失不可变历史。
- SourceBlob、逻辑资料版本、元数据修订、EvidenceSnapshot、成员、集合哈希和状态事件的作用域、前序链、镜像字段、成员身份、不可变状态和状态历史均有确定性检查；增量继承/新增/显式替代、完整快照遗漏、重复集合 no-op 和并发重复提交均有反例测试。
- 受试者/审核节点基础 API 已验证跨项目隔离、重复受试者、时间序列、中文错误信封和查询路径；未引入前端、上传流程或 OCR 正式持久化。
- Slice 4.0 诚实结论保持不变：真实门禁请求仅证明合成样本下 text-only 行为；provider 自报模型名没有独立身份凭据；无真实坐标不画红框。
- Slice 4.1 满足停止点，可进入 Slice 4.2。EvidenceProcessingRevision、ActivationEvent 的正式表/仓储以及处理修订漂移、激活、回滚仍是后续切片边界，不能被本裁决解释为已实现 4.2。

## 2026-08-19 Phase 4 Slice 4.1 无损暂停

- 用户在独立检查者终局放行后要求无损暂停；未启动 Slice 4.2、未创建上传预览、未实现正式
  OCR 持久化，也未运行任何外部视觉试用。
- 当前隔离工作树为 `.worktrees/phase4-evidence-ocr-v2`，分支为
  `codex/phase4-evidence-ocr-v2`；所有 Slice 4.0/4.1 代码、测试、研究证据和执行报告均保留，
  尚未提交或合并。
- 检查者修订前 Codex 全量 V2 为 `900 passed, 58 warnings, 2 subtests passed`；检查者修订后
  由新鲜 Luna 会话报告 `914 passed, 58 warnings, 2 subtests`，目标 Ruff、限定 Pyright、编译
  和 `git diff --check` 通过。暂停时 Codex 未再次重跑修订后的 914 项，因此恢复后第一步必须
  独立复测，不能把检查者报告替代为 Codex 终局验证。
- 已知非阻断残余：`subjects(project_id, subject_code)` 无数据库级唯一约束，跨进程并发创建仍
  有风险；当前单机单用户 Slice 4.1 不阻断，后续迁移设计时需明确处理或保留理由。
- 下一安全动作：先读取 `CHECKPOINT_20260819_SLICE41_PAUSED.md`，关闭工作树漂移检查，串行运行
  Slice 4.1 目标回归与 `tests/v2 -q`；全部通过后才按 Slice 4.2 计划建立上传预览、确认和前端骨架。

## 2026-08-19 Phase 4 Slice 4.2 恢复门禁

- Codex 已在检查者修订后独立重跑 V2 全量回归：`914 passed, 58 warnings, 2 subtests passed`；
  目标 Ruff、使用项目虚拟环境的限定 Pyright、`git diff --check` 和 Trellis 上下文校验均通过。
- Slice 4.1 执行 review-gate 已通过；三份紧凑 worker 报告已归档，43MB 可再生原始 stdout
  日志进入清理范围，不作为正式证据保留。
- 发现总设计与切片拆分的迁移边界不一致：设计原把上传预览表写入 `0008`，但已验收的
  `0008_evidence_ingestion` 只有六张证据基础表。为不回改已验收迁移，Slice 4.2 新增
  `0008a_evidence_upload_previews`，后续 `0009_ocr_artifacts` 编号和职责不变。

## 2026-08-19 Phase 4 Slice 4.2 服务层检查点

- 第一工作项已在日间主路由 `Pi/cms-smk/deepseek-v4-flash:max` 完成，并在 Codex 发现基础语义问题后沿用同一 session `01a018bb-d3d6-7000-b82e-f7aa0be82179` 修订；未触发 fallback。
- `0008a`、上传预览/逐文件差异、补充与完整资料集合、显式冲突处置、取消待清理、候选快照与持久任务同事务写入已实现。候选可用于同集合 no-op 收敛，但不再冒充有效继承基准；所有新确认在任何 no-op 前重验节点修订号和活动基准。
- 取消清理失败不再静默：预览保持 `cancel_pending`、确认入口关闭、重试可完成自有暂存清理，共享 blob/快照/历史不受影响。
- Codex 实测：聚焦 `111 passed`；全量 V2 `988 passed, 58 warnings, 2 subtests passed`；Ruff、限定 Pyright、`git diff --check` 通过。
- 当前 Slice 4.2 尚未完成 API、前端及无辅助宽屏任务。Slice 4.4/`0010` 落地活动指针后，必须以 `ReviewEpisode.active_evidence_snapshot_id` 取代当前过渡性的 `ACTIVE` 状态选择。

## 2026-08-19 Phase 4 Slice 4.3 页产物与识别底座检查点

- 已完成 `0009_ocr_artifacts`、不可变 PageArtifact/OCRProfile/OCRPage/OCRRun/OCRAttempt、
  原始请求响应工件、页工作租约和不可激活基础处理修订的合同、迁移与仓储；同一证据快照允许
  产生多个不可变处理修订，失败/取消识别结果不再原地覆盖。
- 逐格式处理覆盖 PDF、普通图片、多帧 TIFF、TXT、DOCX 和 DOC。失败页不再填充全零哈希、
  1×1 尺寸或虚构旋转；TXT 保留原文但不伪造坐标；扫描页仅保存文字，无真实坐标不画红框。
- 页工件身份与数据库唯一键现同时包含渲染、解码和坐标变换版本；DOCX/DOC 使用源内容与
  转换程序版本形成稳定身份，避免转换文件元数据变化触发重复识别。实际送入文字识别的是
  内容寻址存储中的同一页图字节，不再二次渲染。
- 识别流程已拆成“准备请求”和“完成结果”两个阶段，支持任务在真实模型调用前持久化检查点。
  用户可见失败/降级文本已去除 provider、异常类名、`text-only`、适配器和推理等工程措辞；
  技术诊断仅通过内部字段交给任务尝试记录。
- Codex 独立回归：聚焦 `141 passed`；V2 全量 `1187 passed, 58 warnings, 2 subtests passed`；
  Ruff、Pyright、`git diff --check` 通过。下一步仅实施页级持久执行、共享 oMLX 8 路准入、
  晚到结果拒绝、渲染背压、限定重试/取消/恢复和 SSE 只读进度；Slice 4.3 尚未最终放行。

## 2026-08-19 Phase 4 Slice 4.3 最终质量检查

- 独立 fresh-context 复核已补齐并验证页工作租约 -> 共享 oMLX 租约 -> 外部推理的固定顺序、
  租约心跳/代次/晚到结果原子拒绝、取消/重试/进程死亡恢复、持久进度与 SSE 投影，以及
  失败 provider 响应的原始字节回放工件。聚焦回归 `150 passed`，V2 全量 `1233 passed, 2 subtests passed`；
  Ruff、生产代码 Pyright、`git diff --check` 通过。
- 现场真实 oMLX 合成探针使用 `http://127.0.0.1:8001` 和 `GLM-OCR-bf16`：12 路请求全部返回，
  门禁峰值为 8，剩余租约为 0，响应模型身份与非空文本校验通过。Slice 4.3 仍不生成定位/风险/校对，
  基础处理修订保持不可激活；启动脚本按项目边界继续使用 legacy 默认入口，V2 通过独立 factory 启动。

## 2026-08-20 Phase 4 Slice 4.4 WP-44A 最终验收

- 已完成 `0010_evidence_locator_corrections`、唯一审核节点合同、基础/完整处理修订辨别，以及定位、识别风险、校对、被提及资料、处理候选和激活事件的追加式持久合同；旧识别原文、旧基础修订和旧审核节点字段未被回写。
- 完整修订不再只验证候选自报清单：新建时必须完整纳入当前资料元数据、当前有效校对、当前被提及资料和当前满足状态；历史读取则严格按当时冻结的 ID 与内容哈希回放，不因后续合法修订失效。
- 同一基础修订、同一识别页和同一原文范围只能建立一条校对链，仓储预检与 SQLite 部分唯一索引共同约束；不同非重叠范围可各自拥有校对链。
- 定位器所有读取路径都复核精确页产物、识别页、来源层和原文哈希；页内摘录必须能在同源文本中回放。完整修订的根、实际页子表和关联表在同一保存点写入并读回，失败不会留下可激活半成品。
- 最终确定性证据：聚焦 `225 passed`；全量 V2 `1361 passed, 2 subtests passed`；Ruff、限定 Pyright 和 `git diff --check` 通过。独立 `gpt-5.6-sol:high` 复核终局无 P0/P1/P2，裁决 `ACCEPT`。
- 仅 WP-44A 放行。下一安全动作是 WP-44B 的确定性定位、风险扫描、有效校对投影和原子激活/回滚服务；WP-44C/D 继续阻塞。

## 2026-08-20 Phase 4 Slice 4.4 WP-44B 最终验收

- WP-44B 已完成并由同一新鲜 `gpt-5.6-sol:high` 独立会话终局放行。复核先后两次拒绝，定位到重叠文本误判唯一、被提及资料链头与人工确认混淆、默认激活幂等不足、孤立激活事件，以及陈旧 READY 候选可切换权威指针但不进入 ACTIVE 的仓储旁路。
- 修复后，重叠 occurrence 不再生成伪红框；确定性发现来源与用户复核状态分离；确认/修改/解除保留非空原因及不可变历史；激活仓储在同一保存点写 ActivationEvent、审核节点成对指针和候选 ACTIVE 事件，并验证候选冻结修订号。
- 风险种子集固定断言关键漏检 `0/26`、干净页误报 `0/13`、覆盖 `23/23`，仍只代表确定性规则种子集，不代表扫描件/照片识别的一般准确率。
- Codex 最终证据为聚焦 `209 passed`、V2 全量 `1455 passed, 130 warnings, 2 subtests passed`、限定 Ruff/Pyright 与 `git diff --check` 通过；独立终局无未闭合 P0/P1/P2。
- 下一安全动作仅为 WP-44C：实现页、校对、完整修订、激活/回滚和被提及资料 API，以及只读 current 指针投影。前端 WP-44D、连续原件滚动与真实红框视觉验收继续阻塞。

## 2026-08-21 Phase 4 Slice 4.4 WP-44C 最终验收

- WP-44C 后端接口已完成并由同一 fresh-context `gpt-5.6-sol:high` 独立会话终局放行。首轮复核拒绝了重复启用当前版本返回 500、跨受试者资料可被登记为已提供，以及 API 错误映射器依赖上传/存储异常三个 P1。
- 根因修复收敛为共享边界：重复启用当前成对版本返回结构化 `409 CURRENT_VERSION_UNCHANGED`，不追加激活事件、审核节点修订或幂等历史；被提及资料的已提供关系必须与登记链同项目/受试者/审核节点，且资料版本属于该节点当前活动快照，服务与仓储均独立拒绝绕过。
- API 错误映射器只消费应用错误，不再导入上传服务、存储模块或 SQLAlchemy。上传公共服务把已知内部失败转换为固定中文应用错误；技术异常、绝对路径、SQL 和内部哈希不进入用户错误信封。
- Codex 证据：聚焦 `39 passed`；API+services `335 passed`；V2 全量 `1537 passed, 130 warnings, 2 subtests passed`；Ruff、项目虚拟环境 Pyright、`git diff --check` 通过。独立复核另跑修复相关 `180 passed, 2 subtests passed`、API+services `335 passed` 和全量 `1537 passed, 2 subtests passed`，终局无未闭合 P0/P1/P2。
- WP-44D 中文核对闭环现已解锁。下一安全动作仅实施中栏原始识别/校对后文本、风险核对、关键确认、定位精度与降级原因、被提及资料关联以及 409 输入保留；连续原件滚动和真实红框完整体验仍属于 Slice 4.5。

## 2026-08-21 Phase 4 Slice 4.4 最终完成

- WP-44C-R 已把校对、风险核对和显式构建收敛为“原子排队、冻结输入、后台持久执行”；HTTP 请求不再同步构建，进程死亡后可用同一任务与候选恢复，READY/ACTIVE 重放不重复生成完整修订或候选事件。
- WP-44D 已完成原始识别/校对后文本、风险核对、关键确认、定位精度与中文降级原因、被提及资料闭环及 409 输入保留。旧候选恢复与新候选创建之间增加候选编号和本地锚点双重隔离，晚到成功或 404 均不会覆盖/删除新候选。
- 独立 fresh-context 检查曾两轮拒绝同步构建、候选输入时序漂移、READY 恢复、轮询退避、恢复竞态和技术术语；按共享状态机修复后，同一 `gpt-5.6-sol:high` 会话终局 `ACCEPT`。
- 最终验证：后端全量 `1543 passed, 130 warnings, 2 subtests passed`；前端 `336 passed`；生产构建和三档宽屏 Playwright `6 passed`；Ruff、项目虚拟环境 Pyright、`git diff --check` 通过。
- 当前边界：Slice 4.5 尚未开始。右栏仍是诚实占位，不具备连续原件滚动、真实坐标缩放覆盖层或风险红框；任何无真实坐标的证据继续不得绘制红框。
- 下一步：实施 Slice 4.5 的文件/页/文本/原图联动、真实证据滚动、真实 bbox 映射、任务中心中文详情、帮助页和 P4-AC01 至 P4-AC13 宽屏验收；通过后才进入三路独立试用。

## 2026-08-21 Phase 4 Slice 4.5/4.6 无损暂停检查点

- Slice 4.5 用户面功能与 P4-AC01 至 P4-AC12 本地确定性验收已完成：连续原始资料滚动、真实坐标红框、无坐标诚实降级、持久任务中文详情和帮助说明均已落地；后端 V2 全量 `1546 passed`，前端 `344 passed`，证据 Playwright `15 passed`，生产构建与限定静态检查通过。
- P4-AC13 尚未通过。Pi 独立真实浏览器试用发现生产前端仍混用 Phase 1 stub 基线仓储与 V2 HTTP 证据仓储，导致真实 V2 受试者无法从生产前端进入证据链。这是跨项目通用的数据访问边界缺陷，不能靠测试夹具或项目特异逻辑掩盖。
- CodeBuddy 正式试用受其非交互权限限制，仅作为静态审阅；Grok Build 正式试用需从既有会话 `5dbfce0f-a5e8-4dd6-a249-d86c4fba4e39` 继续，禁止因暂停而新建或替换会话。
- 恢复顺序：续跑同一 Grok 会话；修复生产默认 HTTP/stub 显式隔离；重跑全量确定性验证与三路独立 UAT；由 Codex 重新裁定 P4-AC13。Phase 4 放行前不进入 Phase 5。
- 用户已要求立即无损暂停。暂停时无相关活动进程，UAT 报告、截图、提示词与失败证据均保留，未做清理。

## 2026-08-21 15:51 Phase 4 最新暂停锚点

- 会商顾问与独立试用者必须分离：前者只读挑战设计，后者在隔离清洁环境真实操作产品；两者报告不可互相替代。
- R4 后已修复跨上传方式冗余版本、增量旁路核对沿用、风险扫描时机、真实定位自动纳入、原生文字页进度 `0/0` 和用户界面完成状态歧义。
- 前端全量 `372 passed` 并构建通过；后端相关回归通过。后端全量最终一轮因用户暂停在约 9% 中断，Phase 4 仍未放行。
- 精确恢复文件：`.trellis/tasks/08-19-phase4-evidence-ocr-v2/CHECKPOINT_20260821_1551_PAUSED.md`。恢复后先完成后端全量，再做新隔离浏览器矩阵与 R5 三路真实试用；不得直接进入 Phase 5。

## 2026-08-21 22:25 Phase 4 Slice 4.5 终局与独立试用中间检查点

- 后端同一代码基线全量 `1557 passed, 130 warnings, 2 subtests passed`；前端终局 `382 passed`，生产构建、stub 证据流程 `15 passed`、真实后端 1080P/2K/4K `3 passed`。Slice 4.5 用户体验与本地确定性检查完成。
- 三路 R3 均使用用户指定的测试模型且未替换：CodeBuddy `hy3(max)`、Pi `cms-router/minimax-m3(high)`、Grok Build `grok-4.6(medium)`。共同确认阅读态、单框定位、重复文件、上传收拢和当前版本语义；测试者报告不替代 Codex 浏览器验收。
- Codex 以实际 1080P 截图确认短文本红框压字，从共享呈现层改为框外描边；通用定位列表过滤纯标点但保留风险核对本身；空白“资料中提及但未提供”登记表默认收拢；受试者与中心增加明确分隔；“页面已就绪”改为“原件可查看”。未添加项目特异规则。
- 1366×768 意见不采纳，因为产品合同只覆盖最大化 1080P 至 4K、有效 CSS 宽度不低于 1280 的桌面组合。4K 右栏宽度属于偏好，未限制原件阅读空间。
- P4-AC13 仍未完成：三名模型测试者尚未分别在隔离清洁库完整执行创建/删除项目和受试者、全上传/OCR/校对/失败恢复及量化无辅助脚本。Phase 4 保持 `in_progress`，不得进入 Phase 5。恢复文件为 `.trellis/tasks/08-19-phase4-evidence-ocr-v2/CHECKPOINT_20260821_2225.md`。

## 2026-08-22 Phase 4 P4-AC13 测试路线更新

- 当前三名独立测试者固定为 Cursor CLI `cursor-grok-4.6(medium)`、Pi `cms-router/minimax-m3(high)`、Pi/oMLX `Qwen3.8-27B-oQ8e-fp16-mtp(medium)`；测试角色不得与执行或会商角色互相替代。
- 本地 Qwen 已完成指定模型与中等推理强度的真实连通性测试，并在测试后卸载；正式端到端试用须与产品 OCR 串行，避免模型占用和性能测量互相污染。
- 旧 `pi/opencode-go/ox-alpha-free(high)` 连通性结果仅作为被替换路线的历史失败证据保留，不得用于当前 P4-AC13 的连通性或端到端验收。

## 2026-08-22 Phase 4 完成边界

- P4-AC01 至 P4-AC13 已完成。三路指定测试者在互不污染的 D001 II 期隔离副本中完成真实资料试用，Codex 复核实际浏览器、持久任务深链、数据库不变量和临床边界；测试者仍不等同真人可用性研究。
- 终局系统修复包括：从不可变提交恢复处理中快照的 `upload_job_id`；关键校对仅持久化最小变化范围；严格半开区间覆盖；风险/审核/校对按处理修订隔离；批量读取消除页数相关 N+1；严重整页重复风险不得由普通阅览关闭。
- 决定性验证：后端 `1633 passed, 139 warnings, 2 subtests passed`；前端 `49 files / 416 tests passed`；生产构建通过；1080P/2K/4K Playwright `9 passed`；真实隔离 D001 证据页可进入准确的资料处理详情；fresh-context 独立检查最终 `ACCEPT`。
- 最终恢复记录为 `.trellis/tasks/08-19-phase4-evidence-ocr-v2/CHECKPOINT_20260822_PHASE4_COMPLETE.md`。Phase 5 只能读取当前审核节点已激活的证据快照和完整处理修订，继续保持来源版本、页图、OCR 原文、有效校对和定位可回放；不得让候选或后续阶段资料静默改写早期事实。

## 2026-08-22 Phase 5 最终规划待批准

- 已从 Phase 4 终局提交 `32f5997` 建立隔离工作树 `.worktrees/phase5-clinical-facts-profile`、分支 `codex/phase5-clinical-facts-profile` 和 Trellis 子任务 `.trellis/tasks/08-22-phase5-clinical-facts-profile`；任务保持 `planning`，未修改产品代码或运行 `task.py start`。
- 当前代码审计确认阻断错链：Phase 2 占位事实/Profile 绑定旧 `evidence_snapshots`，Phase 4 当前权威是审核节点成对指向的 `evidence_snapshots_v2 + complete processing revision`；新规划使用独立 v2 写表并冻结旧占位表读路径，不做外键原地重定向。
- Evidence Normalizer 只输出候选；候选与发布合同分离。事实、事件、用药暴露、冲突、资料期望和 Profile revision 均绑定完整权威元组，发布前重验活动指针；只引用 Phase 4 已认证 locator，无真实坐标不画红框。
- 沉默、未提及、缺页或空白只形成资料期望缺口，不能生成否定/正常事实；否定必须有明确对象和原句。部分日期保存上下界，事件时间与记录时间分开，“既往”不推断结束；筛选病历转述的阳性长期史作为较弱事实并产生溯源提醒。
- 首屏突出集合由后端确定性投影，不把所有规则关联都当作风险；本阶段不显示入排主结论、ActionRequest、通过/不通过或方案阈值/洗脱裁决。事实到规则只做精确身份索引。
- 独立规划会商实际使用 `DeepSeek V4 Flash max` 与 `Grok Build 4.6 high`，均完成一轮且无 fallback；两者的一致阻断意见已由 Codex 在源码中核实并选择性采纳。会商与未来测试者继续分离。
- 当前第三独立测试者已固定为 `pi/omlx/Qwen3.8-27B-oQ8e-fp16-mtp(medium)`，替换 ox-alpha；仅在 Phase 5 确定性门禁和真实运行完成后先连通性测试、再用隔离真实项目进行端到端试用，测试后卸载本地模型。

## 2026-08-22 Phase 5 独立测试路线更新

- 用户后续指令替换前述 Phase 5 测试路线。当前三名独立测试者固定为 Cursor CLI `auto`、Pi `cms-router/minimax-m3(high)`、Pi `opencode-go/ox-alpha-free`；它们只承担真实项目、真实浏览器与系统内独立 Agent 的端到端试用，不得与执行或会商角色相互替代。
- 三种 harness 首次使用均先单独做连通性测试；按各自调用方式运行并保持最长 100 分钟等待，不因模型目录预检或短暂无输出而随意 fallback。该测试安排在 Phase 5 确定性门禁、真实 Normalizer 与 Patient Profile 界面可用之后执行，Slice 5.1 不提前制造伪端到端证据。
- 最终规划产物为 `prd.md`、`design.md`、`implement.md`、`research/current-state-and-conference.md` 及已配置的 implement/check 上下文清单。下一安全动作是等待用户明确批准；批准后才切换为 `in_progress`，从 5.0 基线和 5.1 权威合同/迁移开始。

## 2026-08-22 Phase 5 Slice 5.1 合同与权威存储基座

- 用户已批准进入实施，任务状态为 `in_progress`。Slice 5.1 新增候选/发布分离合同、不可变权威元组、部分日期/来源强度/持续状态、`0013_clinical_facts_profile_v2` 及 v2 仓储；旧占位事实表仍为只读回归锚点。
- 独立检查修复了三类存储边界：候选 payload 现在自带并镜像校验 `call_id / candidate_kind / created_at`，调用与运行用复合外键防止伪来源；不可变列表和 revision/幂等链头先解码全部 payload 再过滤，权威快照/处理修订/定位/资料/快照成员也先验 canonical hash 与镜像，漂移不再静默隐藏坏行；多态 locator/rule 链接新增类型化真实父外键和一致性 `CHECK`。
- 事实候选的被断言对象必须与 AssertionBasis 一致，数值拒绝 NaN/无穷值，用药暴露保留独立 `record_time`；Slice 5.1 只能创建未解决冲突，不提前开放 Agent 或无理由的冲突裁决。
- 验证：合同/仓储/迁移及共享仓储回归 155 项通过，历史迁移 40 项通过，`tests/v2` 全量 `1735 passed, 1 skipped, 2 subtests passed`；跳过项为既有的 oMLX 真实探测工件未提供。Slice 5.2+ 的事实门禁、Normalizer、API、UI、ReviewRun 和入排结论未实施。

## 2026-08-23 Phase 5 Slice 5.2 确定性门禁验收

- 已在不调用模型的结构化候选上完成九步门禁中发布前可判定部分：完整页覆盖、当前修订定位闭包、有效原文与哈希、否定对象、数值/单位、部分日期、来源、记录时间、候选引用、精确重复和未解决冲突。关键 OCR 风险只阻断实际关联候选；空输出、缺页、虚构定位、跨调用越界和跨权威修订均拒绝。
- 根因修复不落项目特异规则：否定词必须直接支配被断言对象，不能因同句出现“无”而误判；事实稳定身份包含被断言对象，避免 ALT/AST 等同值同单位事实误合并；事件稳定身份包含去重后的引用事实对象；事件/暴露定位只能来自其引用事实定位并在持久化读回时再次校验。
- 运行编排只接受成功调用和完整处理修订，并核对项目、受试者、审核节点、活动快照与完整处理修订的冻结权威。发布事务门在 Slice 5.2 不伪造成功，由后续发布仓储负责。
- 已发布的 `0013` 迁移恢复原始形状；新增 `0014` 单独收紧 `clinical_facts_v2.assertion_object` 为必填。旧库存在空值时拒绝升级并恢复，不根据类型或原文猜测医学事实；有数据升级后五类事实子表外键和删除保护保持完整。
- 最终证据：聚焦 `222 passed`，历史迁移 `54 passed`，Codex 全量 V2 `1854 passed, 1 skipped, 139 warnings, 2 subtests passed`；`compileall`、`git diff --check`、Trellis validate 通过。独立 Trellis 核查的限定 Ruff/mypy 通过且无未闭合问题。唯一跳过仍为既有 oMLX 真实探测工件缺失。
- 下一安全边界是 Slice 5.3：真实 Evidence Normalizer 的中文提示词、严格结构化输出、连续页组切分与可恢复持久运行。事实发布、Patient Profile API/UI、ReviewRun、入排结论和真实项目端到端试用仍未放行。

## 2026-08-23 Phase 5 Slice 5.3 Evidence Normalizer 验收

- 已完成中文原生严格 Schema、逻辑文档连续页组、真实 DeepSeek/oMLX 传输、PromptVersion/ModelConfig 内容绑定，以及运行、调用、候选、未解决项、检查点、租约和失败/取消恢复。模型只生成语义草稿；运行身份、时间、稳定候选身份和来源哈希均由系统注入。
- 模型输入现在携带每个 Phase 4 定位的页码、来源层、精度、来源文本哈希和可回放局部原文，且完整定位摘要进入调用与运行幂等哈希。page-only 不支撑具体断言；无法还原局部原文时在规划阶段失败。
- 真实合成探针首次暴露遗漏明确收缩压、从资料沉默制造舒张压/心率缺口和断言对象不在原文；共享提示词与合同修订后同时抽取否定病史和收缩压数值，仅保留测量日期缺口，断言哈希与 Phase 4 来源一致。
- 最终独立检查又发现并促成修复：终败任务人工重试同步恢复领域运行；提交回调异常立即落为步骤终败且事务回滚，不等待租约过期。仅未解决项或存在门禁拒绝的运行保持保守 `PARTIAL`，不冒充完整可发布结果。
- 最终验证：聚焦扩展 `348 passed`；V2 全量 `1972 passed, 1 skipped, 139 warnings, 2 subtests passed`；`compileall`、`git diff --check`、Trellis validate 通过。唯一跳过仍为既有 Phase 4 真实探针工件缺失。
- 下一安全边界是 Slice 5.4：事务发布 ClinicalFact/Event/MedicationExposure、构建精确 FactRuleLink 双向索引并投影资料期望。Patient Profile API/UI、ReviewRun、入排结论和三路真实项目试用继续阻塞。

## 2026-08-23 Phase 5 Slice 5.4 事实发布、规则索引与资料期望验收

- 规范化运行现在以一个数据库事务发布去重后的事实、事件、用药/治疗暴露、三类同类型未解决冲突、定位链接、精确规则索引和资料期望；必要资料期望缺少事实或结构化缺口时终败并整体回滚。
- 规则关联只依据候选冻结的资料要求编号与事实类型，不从自由文本猜测；审核阶段来自权威 ReviewEpisode，同阶段工作节点不唯一时拒绝投影。外院或来源不明结果不会升级为当前中心同期客观证据。
- 序列测量与方案变化按时间关系保留为纵向信息；只有时间重叠或未知且值不兼容才形成冲突。`0016` 为事件和用药/治疗暴露新增类型化冲突成员表，旧事实冲突 payload 仍可按合同默认值回放。
- 历史迁移快照遗漏新增表、SQLite JSON 等值数值形态和日期/时间镜像差异均在共享机制修复并固化回归。最终 V2 全量 `2040 passed, 1 skipped, 139 warnings, 2 subtests passed`；唯一跳过为既有 Phase 4 真实探针工件缺失。
- 下一安全边界是 Slice 5.5 Patient Profile API 与投影。界面、入排主结论和 Phase 5.8 三路真实项目试用尚未开始；当前测试路线仍为 Cursor CLI `auto`、Pi `cms-router/minimax-m3(high)`、Pi `opencode-go/ox-alpha-free`，不得与执行/会商模型互换。

## 2026-08-23 Phase 5 Slice 5.5 Patient Profile API 与投影验收

- 已实现不可变 Patient Profile revision、13 条主题泳道、确定性首屏突出集合、当前链头/历史/指定修订查询，以及生成中、失败和派生陈旧状态；Profile 只读取同一冻结权威下已发布的 v2 事实、事件、暴露、冲突和资料期望。
- 真实 HTTP API 不读取 fixture 或旧事实，不输出 Phase 6/7 入排主结论或行动。证据定位详情复用 Phase 4 映射，并按 Profile 自身冻结的完整处理修订重验；缺失或跨修订定位拒绝响应，没有真实坐标时不返回坐标。
- 根因修复：同一冻结权威下，后续运行若只改变同一语义事实/事件的 Profile 泳道，发布服务会拒绝该冲突，避免用泳道变化制造重复事实和历时线分叉。
- 验证：本切片合同、投影、仓储、服务、发布与 API 组合回归 `111 passed`；500 事实 API 回归 `26.63s`；V2 全量 `2144 passed, 1 skipped, 139 warnings, 2 subtests passed`。唯一跳过仍为既有 Phase 4 oMLX 真实探针工件未提供。
- 下一安全边界是 Slice 5.6：将宽屏 Patient Profile 页面切换到真实 HTTP repository，完成首屏重点、全量历时信息、证据滚动定位与真实 bbox 红框，并做 1080P/2K/4K 浏览器验收。ReviewRun、入排主结论和 Phase 5.8 三路真实项目试用仍未开始。

## 2026-08-23 Phase 5 Slice 5.6 宽屏 Patient Profile 界面验收

- 生产受试者页已切换到真实 HTTP Patient Profile repository；fixture 仅用于隔离测试。后端首屏重点集合、13 条泳道、档案/资料版本、生成时间、待核对数，以及事件时间与记录时间分别呈现，未提前显示 Phase 6/7 入排主结论或行动。
- 点击事实、事件或冲突可在右侧连续原件中定位；只有已核验 bbox 绘制一个红框。测试发现“发热”事件曾复用血压定位，已从 fixture、源图和端到端断言三处改为独立语义定位；原图必须解码，红框还必须覆盖预期原文目标，不能只检查框存在。
- 实际 Chrome 100%/150%/200% 缩放均已触发真实布局宽度和 DPR 变化。修复旧媒体查询后，即使 200% 下 Profile 与原件仍左右并列且无页面级横向滚动；最大化 1080P、2K、4K 截图已复核。
- 决定性验证：后端同一基线 `2145 passed, 1 skipped, 139 warnings, 2 subtests passed`；前端 `57 files / 479 passed`；生产构建通过；完整 Playwright `280 passed, 50 skipped`。唯一后端跳过仍是既有 Phase 4 oMLX 探测工件未提供。
- 下一安全边界是 Slice 5.7：实现有理由的事实修订、影响范围计算、局部增量重算和不可变历史回放。Phase 5.8 三路真实项目试用继续阻塞，不得用执行或会商角色替代测试者。

## 2026-08-23 Phase 5 Slice 5.7 人工事实修订与增量重算验收

- 人工修订必须填写理由，冻结完整修改前/后语义快照、原候选、定位和影响范围；修订提交绑定的是本次修订生成的新 Patient Profile revision，不得把旧 Profile 解释为被原地改写。
- 影响范围先由定位、文档、事实和精确规则索引确定；不能证明局部安全时扩大到整个审核节点。历史节点和后续节点保持各自不可变版本，迟到回包、重复回调、取消、重启和局部失败均有持久任务回归。
- 最新独立视觉会商实际使用 `kimi-code/k3-256k high`，无 fallback。会商确认核心历史/红框/中文边界成立，同时提出进行中窗口可关闭、摘录与红框不一致、失败页恢复死路、4K 信息密度、重复阶段信息和重复断言；Codex 在共享层修复后重新生成并逐张复核六张 1080P/2K/4K 截图。
- 最终验证：后端同一基线 `2255 passed, 1 skipped, 139 warnings, 2 subtests passed`；前端 `493 passed`；生产构建通过；完整 Playwright `283 passed, 50 skipped`；`compileall`、`git diff --check` 通过。Vite 主包超过 500 kB 仍是既有非阻断性能债。
- 下一安全边界是 Slice 5.8：在隔离目录从原始输入新建 D001 II 与 MG-K10-SAR III 代表项目，完成病例级事实、Patient Journey、证据定位和三路独立测试者验收。执行者、会商顾问与测试者继续分离，不得互相替代。

## 2026-08-24 Phase 5 Slice 5.8 结构化输出暂停边界

- 当前最新执行路线为 `codex-subagent/codex/gpt-5.6-luna:max`，同一执行会话完成五轮修订且无 fallback；独立测试路线没有启动，也没有被执行模型替代。
- 三次 D001 II 隔离真实运行分别揭示长度截断/可空对象、混合图节点、存在性比较符携带值三类共享合同缺陷，均按系统层修复；三次运行都失败，只作为诊断证据保留。
- 当前结构化输出使用存在性、标量、集合谓词节点及独立逻辑节点，随后合并到统一图空间进行重复、环、孤儿、共享子节点、根、例外和领域校验。Codex 聚焦回归 `80 passed`，执行器完整协议回归 `425 passed, 58 warnings`；编译和定向差异检查通过。
- 第五轮尚未进行真实 oMLX 复跑，D001 II 与 MG-K10-SAR III 代表病例、Patient Journey/定位人工核对及三路独立测试者验收均未完成。界面终败诊断过于笼统、全任务截止时间缺失是已记录的后续改进项。
- 恢复时从 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260824_STRUCTURED_OUTPUT_PAUSED.md` 开始，以新隔离数据目录先跑 D001 第一批真实探针；不得把旧失败目录视为清洁运行或验收通过。

### 首批真实探针结果与再次暂停

- 第五轮 wire 合同真实请求耗时 140.025 秒并返回完整结果，但领域水合拒绝两种严格 Schema 未阻止的非法形态：单个原子条件同时使用单段/多段定位，以及 `ALL/ANY` 仅含一个子表达式。
- 失败摘要和原始回包位于 `artifacts/phase5-acceptance/20260824/probe-wire-v5/`；旧冻结输入只读，未写回数据库。该结果仅为根因证据。
- 用户要求立即无损暂停。恢复时先在共享合同层补齐定位互斥与逻辑最小基数并写回归，再用新目录重跑首批；不得继续完整 D001/MG 或独立测试者验收。

## 2026-08-24 Phase 5.8 `dnf-v1` 实施立即暂停

- v6-v9 的真实回包证明旧 compact 引用图在严格 Schema、提示词加强和同会话修订后仍会产生悬空节点与语义漂移；已停止补丁式修复。
- 三份独立设计复核一致接受无引用 `dnf-v1`。实施已完成 Schema/中文合同和确定性水合/系统身份两项，执行者分别报告 20 与 29 项聚焦测试通过。
- 第三项旧测试迁移与完整协议回归在用户要求“立即无损暂停”后以 KeyboardInterrupt 退出；其报告仍是 `PENDING`，当前代码未经父 Codex 完整回归和最终接受。
- 新 DNF 还没有运行真实 oMLX，D001/MG、浏览器和三路独立测试都不得计为开始。恢复入口是 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260824_DNF_V1_IMPLEMENTATION_INTERRUPTED.md`。

## 2026-08-24 Phase 5.8 `dnf-v1` 实施合同验收

- 仅恢复并完成原 Worker 03，未重跑前两名执行者、未替换声明路线。旧适配器、候选/修订 Schema、强 Kleene 三值逻辑、合取弱化变异测试及 v6-v9 旧图反例均已迁移到 `dnf-v1`。
- Codex 独立审阅发现 `source_clauses` 被身份归一化排序会抹掉原文重构顺序；现仅集合取值按无序语义归一化，来源片段保持协议原文顺序并进入稳定谓词身份。
- 决定性验证：聚焦 `105 passed, 5 warnings`；完整协议测试 `450 passed, 58 warnings`；`compileall`、`git diff --check`、执行审计和 review gate 均通过。实施过程已归档，v5-v9 真实失败工件继续保留。
- 此验收只覆盖传输与水合合同，不等于真实 oMLX、D001/MG、Patient Profile 或浏览器验收。下一步必须在新隔离目录先跑 D001 第一批真实探针。
- 全局执行/会商路线对本地模型注入上下文的限制，不适用于产品内置本地 LLM/VLM。产品内模型上下文由模型能力、硬件负载、输入分块与真实准确性证据决定；当前切片尚未改变产品模型运行参数。

## 2026-08-24 Phase 5.8a 全方案控制合同与全文清单骨架

- 方案解构输入已从“官方 IN/EX + 流程表”扩展为三类并列来源：官方入排条款、流程必做项、方案其他章节的审核控制。其他控制只使用稳定内部身份和中文顺序标签，不制造新的官方编号。
- 正式合同分为全文覆盖清单、Agent 候选处置、发布控制目录三层；一个控制可同时包含完成/核对、达到条件、禁止事件、禁止药物或治疗暴露、必须记录、必须专业评估等多项义务，并保留组合逻辑、时间锚点、审核节点作用、最低证据与跨来源关系。
- 单期投影不再过滤全文清单。选定期别只固定项目身份；投影外 UNKNOWN/MIXED 正文也必须进入清单等待逐项处置。正文缺期别图块立即失败，脚注/尾注/文本框仅在有明确来源片段时以待确认进入。
- 真实只读 D001 II 探测暴露并修复嵌套表格外层/内层行错误合并。终态为 3,581 个结构块、3,405 个期别图块、513 个旧投影块、1,689 个全文清单单元；表 5 全部 13 行保留，785 个期别未知与 25 个混合适用单元不再静默丢失。
- 验证为专项 `24 passed`、协议全量 `512 passed, 58 warnings`，`compileall`、`git diff --check` 与 Trellis validate 通过。当前只接受 5.8a 和 5.8b 的确定性清单骨架；逐项处置、Agent、发布门禁、D001/MG 人工对照、受试者审核和三路独立测试仍未完成。

## 2026-08-24 Phase 5.8b/5.8c 全文控制 Agent 与发布门禁

- 全文清单现按冻结来源顺序和标题路径确定性分批；关键词仅决定处理优先级。结构单元与候选为双向复数闭包，模型不能创建稳定身份、官方编号、审核节点或未来控制编号。
- 其他方案控制使用独立中文 Agent，而不复用官方 IN/EX 成员合同。触发、义务、例外和适用条件分别保留 DNF；精确摘录只能来自候选拥有的来源单元。
- 发布权威只来自完整的系统水合批次结果；旧 manifest、单数候选链接或调用方单独提交的候选均不能绕过全文处置、来源、期别、节点、时间、逻辑、关系和冲突门禁。
- 验证为聚焦 `73 passed`、协议全量 `561 passed, 58 warnings`，定向编译与公开导入通过。D001 只读清单的 1,689 个单元中仍有 802 个 `UNKNOWN/MIXED`；表 5 表头与 12 个控制行均未丢失，但尚不能发布为 II 期规则。
- 下一步先建立通用、可回源的期别适用性解析层并用 D001 II 人工矩阵核对。未知期别不得默认为 II/III 共享，发布门禁也不得代替语义解析。

## 2026-08-24 Phase 5.8c-1 DOCX 结构标题恢复

- 真实 D001 方案使用数字样式 ID 和中文自定义样式；旧结构块丢弃 `styles.xml` 样式名与 outline level，导致上位章节在 Agent 前消失。
- 新提取层保留原始样式 ID、样式名、`basedOn` 继承轮廓和段落直接覆盖；标题路径只由有效结构轮廓建立，编号列表不作标题。
- 表 5 的表头与 12 条禁限用药行均保留“研究治疗 → 合并用药/治疗 → 禁止的合并用药/治疗 → 表 5 禁止的合并用药/治疗”来源路径。
- 期别上下文现在同级/上级标题处关闭。D001 仍有 1,433 个 `UNKNOWN/MIXED`，较旧的 802 增加，是因为移除了表 5 等章节的错误Ⅲ期继承，不是条目丢失。
- 决定性验证：聚焦 `53 passed`；协议全量 `566 passed, 58 warnings`；D001 源哈希、大小和 mtime 不变；执行路线无 fallback。
- 恢复入口为 `CHECKPOINT_20260824_DOCX_HEADING_RECOVERY_ACCEPTED.md`。下一步是独立、可回源的语义期别适用性解析层；仍待确认项继续阻止发布。

## 2026-08-25 Phase 5.8c-2 语义期别适用性验收

- 结构明确的选定期别、对侧期别和跨期共用单元现由确定性路径保留；只有真正模糊单元进入 Agent。语义结果为选定期别、对侧期别、跨期共用或仍待确认四类，未知不得默认共享。
- 摘录必须逐字回源到引用的冻结结构单元。发布视图不改写原清单，且要精确匹配协议版本、文档哈希、快照、选定期别和每个源单元的完整内容；缺失、未决、错期别或源包漂移均阻断发布。
- 真实 D001 初版规划产生每批约 171.5 万字符、总计约 4.03 亿字符，被拒绝。目标相关检索修复后 235 批每批上下文中位数 40 个单元/61,674 字符，最大 145 个单元/207,886 字符；同表上下文仍完整闭包。
- Codex 验证聚焦 `100 passed`、协议全量 `605 passed, 58 warnings`，D001 源文件未变。这不等于 1,433 个 D001 模糊单元已被解决。
- 下一安全边界是 Slice 5.8d：建立 D001 II 全方案人工控制对照矩阵，再运行实际语义解析。受试者审核、浏览器试用和三路独立测试者继续阻塞。

## 2026-08-25 Phase 5.8d D001 v4 重构立即暂停

- 通用控制矩阵合同已推进至 v4；D001 II 官方规则与流程控制的全量原文重构执行中途收到立即暂停指令。
- 同一执行会话已用中断信号停止且无残留进程。磁盘上的 D001 JSON/Markdown 是未生成正式执行报告、未经父级临床验收的中间产物，禁止作为发布目录或病例审核依据。
- D001 原始方案 SHA-256 仍为 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`。Worker 03、会商、独立测试和受试者审核均未开始。
- 恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260825_D001_V4_RECONSTRUCTION_INTERRUPTED.md`。

## 2026-08-25 Phase 5.8d D001 v5 官方入排与流程控制验收

- 恢复同一 Worker 02 会话后，父级临床复核发现 v4 的全局例外无法限定豁免触发分支，可能让潜伏结核、中药缩短窗口、来氟米特清除或梅毒例外跨分支误放行；该问题已在通用合同层修复，不以 D001 特异文本规则补丁处理。
- v5 为触发 DNF 分支建立稳定身份，并要求每条例外路径以直接来源声明精确作用域；ALL/ANY/NOT、来源闭包、时间、最低证据和中文序列化保持确定性校验。旧 v4 工件不会静默按 v5 接受。
- D001 II 已从真实只读方案重建并由父级接受官方/流程范围：6 条 IN、30 条 EX、22 条流程控制。EX-09、EX-12、EX-18、EX-22 的例外作用域及 EX-11/20/21 的 AND 逻辑已逐项反向映射原文核对。
- 决定性验证为协议相关 `169 passed`、v5 加载与序列化通过、源方案 SHA-256/大小不变。矩阵仍为 `claims_complete=false`；下一步仅启动 Worker 03，从全文覆盖清单补齐其他章节控制后再进行会商、真实项目端到端和三路独立测试。
- 恢复入口更新为 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260825_D001_V5_OFFICIAL_FLOW_ACCEPTED.md`。

## 2026-08-25 Phase 5.8d 混合期别表格结构修订中断

- D001 结构标题继承修复后的当前基线为 1,689 个全文结构单元、1,284 个待语义处置单元和 217 批；第一批真实期别适用性探针已接受。
- 紧凑 v2 的真实批次 32 虽经修订后通过技术门禁，但临床核对发现同一表格行内分别列示的 II/III 期成员被整行判为跨期共用。根因是表格行在期别处置前被聚合成不可再分的单个结构单元。
- Worker 01 初版对任一未知/混合成员拆行导致 2,403 个单元，已拒绝。随后同会话的窄化修订已写入代码与测试，但暂停前未产生报告、未运行验收测试、未重建 D001，因此只算未验收中间状态。
- 执行会话和子进程已停止；Worker 02/03、真实批次 32 重跑、217 批全量、会商、浏览器、独立测试者与受试者审核均未开始。
- 最新恢复入口为 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260825_MIXED_TABLE_ATOMIZATION_INTERRUPTED.md`。下一步必须先验证当前拆分判定、重建 D001 并重新临床核对批次 32。

## 2026-08-26 Phase 5.8d 期别批次与真实理由门禁验收

- D001 II 期别语义计划在保持 1,298 个目标逐项一次覆盖的前提下，由 217 包压缩为 137 包；新策略只合并相邻小章节，不跨表格或明确期别边界，也不拆散原本可完整容纳的结构段。历史 v1 计划仍可按原 217 包身份和输入哈希读取。
- 真实第 69 包证明“未限定某期”不能作为跨期共用正向证据，并暴露来源片段跨单元拼接、待确认候选误写 `unknown` 两类模型合同问题。提示和同会话修复合同已在共享层补强，门禁没有放宽。
- 最终真实同会话修复通过 11 个目标的结构、来源、候选、理由和完整性门禁，且全部保守保留为待确认。该结果验收合批和门禁，不是 D001 合并用药章节的最终临床适用性结论。
- 完整协议回归 `715 passed, 58 warnings`；D001 源 SHA-256 不变。当前 137 包新断点为 `slice58i-v2-plan`，全部保持待运行。
- 恢复入口为 `CHECKPOINT_20260826_PHASE_PACKING_AND_RATIONALE_ACCEPTED.md`。下一步先用人工控制矩阵确认共同章节结构范围，再选择少量异质包验证；不得直接把 137 包技术运行当作 5.8d 临床闭包。

## 2026-08-26 Phase 5.8d D001 矩阵来源闭包验收

- 通用确定性映射器已将交叉章节清单 47/47、合并矩阵 155/155 个来源锚点唯一回绑到当前 1,840 单元冻结全文清单；原始人工矩阵未覆盖，闭包结果单独保存。
- 两份矩阵的来源与关系闭包均通过。交叉清单实际引用 16 个外部控制目标，合并矩阵为 0；统计口径只计算真实引用，不再误用可用目标全集。
- 独立复算发现并保留关键阻断：交叉章节仍有 46 个期别问题，合并矩阵仍有 136 个期别问题；冻结清单无最终 disposition 且 `claims_full_coverage=false`，所以两份矩阵继续 `claims_complete=false`。
- 聚焦矩阵与方案控制回归 `92 passed`；执行 review gate 和 audit 通过；D001 源 SHA-256 保持 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`。
- 旧 1,689 单元汇总移入 `legacy-artifacts/slice58e-1689/`，仅作历史反查。恢复入口为 `CHECKPOINT_20260826_D001_MATRIX_SOURCE_CLOSURE_ACCEPTED.md`；下一步处理 152 个实际被矩阵引用的结构单元之正向期别依据，再选择异质真实语义包，禁止直接全跑 137 包。

## 2026-08-26 Phase 5.8d 单位级期别证据设计验收

- 独立会商接受“152 个矩阵引用单元为主视图、矩阵处置仅作待核对主张、多来源行全部闭合后再汇总”的最小设计；结构混合与语义未决必须分开处理。
- 当前 152 个引用单元中 116 个结构期别未知、35 个明确Ⅱ期、1 个混合；136 个问题实际影响 78 行。问题条数不能当作剩余控制数。
- 共同章节、盲法或“Ⅱ/Ⅲ期评估和程序一致”不能被全局广播。只有同一义务家族存在正向来源、且无期别特异兄弟内容改变该义务时，才可作为共享适用候选。
- 下一安全边界是确定性单位级证据视图、行级阻断汇总、异质代表包清单和共同章节提示收紧；继续保持 `claims_complete=false`，不全跑 137 包，不启动病例或视觉测试。

## 2026-08-26 Phase 5.8d 单位级证据父级复核暂停

- 活动执行任务 `phase5-slice58k-d001-unit-phase-evidence-20260826` 的三个执行者已经返回，但 Codex 最终 review、metrics、review gate 与审计尚未完成。
- 确定性视图当前复算为 82 行、155 个来源锚点、152 个唯一单元；没有执行语义包，`claims_complete=false`，D001 原始方案哈希未变。
- 父级拒绝将理由文本关键词作为共享适用性的确定性门禁。恢复后删除该词法层，只保留语义提示强化和已有结构化闭包；增加无需固定术语也能通过的反例测试。
- `candidate_closed` 可能误示语义闭合，须先核对并改为仅表达结构支持的候选状态，再重建与验收。
- 恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260826_D001_UNIT_PHASE_EVIDENCE_PARENT_REVIEW_PAUSED.md`。当前禁止全跑 137 包、病例审核和视觉测试。

## 2026-08-26 Phase 5.8d 单位级期别证据视图验收

- D001 II 当前合并矩阵形成 152 单元主视图：29 个结构支持候选、116 个语义未决、6 个来源冲突、1 个结构阻断；82 行汇总中仅 4 行为结构支持候选。
- “结构支持候选”不是临床闭合。矩阵期别主张仍非来源权威，`claims_complete=false`，137 个语义包均未运行。
- 父级删除执行者新增的理由文本关键词门禁。共同义务范围由 Agent 基于冻结来源包理解，确定性层只校验结构化身份、来源、目标、处置和闭包。
- 双次重建字节一致；聚焦 `162 passed`、协议全量 `716 passed, 58 warnings`、Trellis validate、review gate 与 execution audit 通过；D001 源哈希未变。
- 下一步只运行 6 个异质代表包，逐包核对真实来源与处置，不直接全跑 137 包。恢复入口为 `CHECKPOINT_20260826_D001_UNIT_PHASE_EVIDENCE_ACCEPTED.md`。

## 2026-08-26 Phase 5.8d 同一规则标题族来源闭包验收

- D001 II 当前冻结清单保持 1,840 个结构单元、1,298 个目标和 137 个计划包，`claims_complete=false`；本切片未请求全量语义运行。
- 目标标题族反向检索只在Ⅱ期与Ⅲ期正向来源成对存在时扩充上下文；门禁基于结构化标题、期别范围、来源摘录和交叉引用，已删除理由文本固定词语死代码。
- 第 59 包真实 Qwen3.8 默认推理运行经 2 次尝试在 404.981501 秒完成，12/12 均为跨期共用，且每条同时引用Ⅱ/Ⅲ期成对来源。
- 第 73 包原真实运行仍诚实保留“需要核对”；其第三次真实响应在修正后的同标题族交叉引用门禁下离线重放为 9/9 跨期共用。重放不是新模型调用，也不覆盖原始运行历史。
- 聚焦回归 `70 passed`，协议层全量 `724 passed, 58 warnings`，`compileall` 通过。下一步只继续能提供新信息的异质代表包，禁止据此直接全跑 137 包或进入病例/视觉测试。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260826_D001_RULE_FAMILY_CLOSURE_ACCEPTED.md`。

## 2026-08-26 Phase 5.8d 当前期别全局章节纳入验收

- 方案全局章节不再因为无法证明另一期间也适用而被机械保留为待确认：只要位于期别专属分支之外、形成明确研究控制且无对侧专属证据，即可纳入当前已固定的Ⅱ期项目；该结论不外推为Ⅱ/Ⅲ期共用。
- 第 63、69、70 包真实核对覆盖生活方式、筛选失败/重新筛选、合并用药/治疗父章节及表 5 子集，共 29 个目标，最终均为当前Ⅱ期适用。第 70 包仅含表头和其后 11 个冻结行，不代表表 5 全部闭合。
- 支持来源现在必须直接指向目标，或明确指向目标所属规则标题/表题族；同包内无关段落不能支持期别处置。收紧后第 59、73 包的合法跨期标题引用仍能通过。
- 第 69 包首次输出可重复生成未闭合引号的截断理由。统一中文理由完整性合同拒绝后，同一会话修复为完整中文；诊断运行保留，不覆盖为成功。
- 真实接受运行合计 1,223.797839 秒；默认本地模型配置在语义方向上有效，但仍依赖严格结构门禁和同会话修复，当前证据不足以调整产品内模型推理参数。
- 聚焦 `46 passed, 5 warnings`，协议层全量 `730 passed, 58 warnings`。当前仍为 1,840 单元、1,298 目标、137 包，`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260826_D001_SELECTED_PHASE_GLOBAL_CHAPTER_ACCEPTED.md`。下一步只选能增加新临床信息的异质包，不全跑 137 包，不启动受试者、浏览器或独立测试者。

## 2026-08-26 Phase 5.8d 混合段落强边界修复无损暂停

- D001 II 已接受基线仍为 `1840` 单元、`1298` 目标、`137` 包，`claims_complete=false`。
- 首轮 58p 的 `1857/1304/138` 重建因把比例、剂量、括号期别参照和访视列表切成不完整义务而被拒绝；失败目录保留为诊断证据。
- 同一执行会话的强标点边界续修已部分落盘，但在用户要求暂停时中断，未产生续修报告、测试、重建或父级验收，当前代码只能视为未验证中间态。
- 执行器及子进程已停止。未启动全包语义运行、受试者、浏览器、视觉或独立测试。
- 最新恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260826_D001_MIXED_PARAGRAPH_STRONG_BOUNDARY_FIX_INTERRUPTED.md`。

## 2026-08-26 Phase 5.8d 混合段落强边界原子化验收

- 软标点切分被永久拒绝；通用结构层现在只在句号、问号、叹号、分号和换行等强边界处分段，并合并相同期别范围的相邻完整分句。比例、剂量组合、括号期别参照和访视列表不得被期别标记或软标点截断。
- 真实 D001 当前为 3,581 个结构块、3,405 个期别图块、1,846 个全文覆盖单元、1,303 个待语义目标和 138 个包。9 个衍生原子全部按字符范围完整回放；`body.p801` 保持完整混合句，`body.p1237#atom-100-160` 为直接 II 期适用且不属于第 111/112 包。
- 第 67、78、79、80、111 包身份、成员和中文叙述与机器差异一致，历史语义结果未复用。D001 源 SHA-256、大小和 mtime 不变；协议层全量 `741 passed, 58 warnings`，执行审计通过。
- 当前 `1846/1303/138` 仅为新的结构基线，不能解释为全文临床闭包；已接受 5.8o 和被拒 58p 均作为不可变对照保留。`claims_complete=false`，未运行语义模型、全包、病例、浏览器、视觉或独立测试者。
- 恢复入口为 `CHECKPOINT_20260826_D001_MIXED_PARAGRAPH_STRONG_BOUNDARY_ACCEPTED.md`。下一步仅对受影响且能增加临床信息的第 67、78、79、80、111 包做独立治理的真实语义验证。

## 2026-08-27 Phase 5.8d 期别交接与有边界语义验收

- 强句边界仍是默认保护；只有逗号两侧形成不同主期别，且右侧直接出现新期别或重复同一主语时，才把并列期别义务进一步拆分。因果和引用关系不得机械拆开。
- D001 II 当前真实结构基线为 3,581 个结构块、3,405 个期别图块、1,848 个全文单元、1,301 个待处置目标和 137 包，源 SHA-256 保持不变。
- 第 67、110 包真实语义结果接受；第 79 包最初因缺少跨期共用正向来源被拒绝，加入结构化问题驱动修复后接受。三包共 22 个单元完成父级临床核对。
- `body.p815` 最终Ⅱ期义务为筛选、基线、第12周及提前退出访视的妊娠试验，不包含Ⅲ期第16、52周；`body.p1237` 的Ⅱ期数据分析与Ⅲ期建议因果关系保持完整。
- 协议层全量 `774 passed, 58 warnings in 761.65s`。`phase5-slice58r5-*` 与 `phase5-slice58r8-*` 作为不可变失败反例保留。
- 当前只接受结构修复与三个代表包，`claims_complete=false`；其余 134 包、受试者、浏览器、视觉和三路独立测试者仍未开始。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260827_D001_PHASE_HANDOFF_AND_BOUNDED_SEMANTIC_ACCEPTED.md`。下一步继续选择不同结构风险的代表包进行真实语义验证，不直接全跑 137 包。

## 2026-08-27 Phase 5 内置语义 Agent 默认改用 MTPLX

- 后续审核、方案解构、期别适用性判断和证据规范化统一默认使用 `MTPLX/mtplx-qwen38-27b-optimized-quality:medium`；OCR 继续由 oMLX 承担，两个服务不共用端点。
- MTPLX 默认端点固定为 `127.0.0.1:8002`，启动与真实探针均要求精确模型 ID；不得静默切换到 oMLX、DeepSeek 或其他模型。
- 方案解构和证据规范化的 MTPLX 路径已提升为严格 JSON Schema，方案本地批次输出上限 8192。活动 Phase 5 单批探针同步改为新默认，历史运行记录保持不变。
- 宿主机真实启动首次暴露 MTPLX 缺少其声明的 `llguidance>=1.7` server 依赖，表现为严格 Schema HTTP 400；安装 `llguidance 1.8.0` 后，模型身份、`medium` 推理和严格结构输出通过，响应约 1.99 秒。
- 聚焦回归 `71 passed, 5 warnings`，静态检查和执行审计通过。根目录旧 `.env` 与桌面静态 UAT 入口须待分支整合后再切换，当前不提前破坏旧运行环境。
- 本次不改变 `claims_complete=false`，也未运行其余 134 个 D001 包、受试者、浏览器或独立测试者。恢复入口为 `CHECKPOINT_20260827_MTPLX_DEFAULT_SEMANTIC_ROUTE_ACCEPTED.md`。

## 2026-08-27 Phase 5.8d 规则家族修复与 MTPLX/DeepSeek 有边界对照

- MTPLX 对源包 36、60、78 的首轮真实运行暴露共享门禁把相同末级章节标题下的不同检查/流程注释误当成同一规则家族。共享修复把隐式同族传播收紧到相同非通用标题且逐字相同的原子义务；明确标题引用和交叉引用仍走独立合同，不写入项目特异规则。
- 修复后 MTPLX medium 在同一冻结范围完成 36/36；DeepSeek V4 Flash max 同源对照也完成 36/36，最终处置差异为 0。DeepSeek 主运行 399.19 秒，包 36 的 16384 重试 56.78 秒；MTPLX 为 1009.21 秒。该结果只描述本轮有边界样本，不构成模型全面排名。
- 受影响源包 67 重跑后 11/11 为选定期适用；“随机化”和共同 IWRS 流程只引用自身全局原文，不再将 II 期 1:1:1 与 III 期 2:2:1 的不同分组设计合并为同一跨期义务。源包 79、110 在新门禁下继续通过。
- MTPLX 的源包 67 首轮因长度上限保守终止，第二次同样以实际 8192 上限一次闭合；名称含 `16k` 的诊断目录不代表实际 16K，本地传输身份仍是 8192。默认语义路线保持 MTPLX medium，DeepSeek 仅作本轮对照。
- 协议层全量回归为 `781 passed, 58 warnings`。`claims_complete=false`；当前只增加三个新异质包的 36 项核对并重验既有包 67/79/110，剩余 131 包、受试者、浏览器、视觉和独立测试者均未启动。恢复入口为 `CHECKPOINT_20260827_RULE_FAMILY_AND_MODEL_COMPARISON_ACCEPTED.md`。

## 2026-08-27 Phase 5.8d 当前小批量方案适用性修复与 16K 预算验收

- 真实运行源包 57、61、121（各 12 单元）。包 121 首轮链即接受，12/12 选定期适用（8192）；包 57 首轮因成对来源下仅列本期处置失败，修复后以 8192 接受，1× 选定期适用 + 11× 跨期共用；包 61 经历三次运行（slice59d/59e/59f）共 9 次同会话修复尝试（全部 16384、gate v2、冻结输入相同），第 9 次（slice59f r3）以 12/12 跨期共用、0 未决接受。
- 失败由两类独立机制构成：包 61 在 8192 下的修复响应连续两次达到长度上限，16K 解决了截断；扩容后仍出现异质目标同组、成对来源仅列本期、共用缺正向来源和候选处置冲突，这些语义问题由聚合门禁反馈与定向修复提示收敛。16K 是必要的工程修复，但不是语义正确性的充分条件。
- 验证 MTPLX 16384 与 OMLX 8192 为独立的本地批次输出预算：`app/config.py:96-101` 默认、两条传输路径对 60000 的独立钳制、两个聚焦预算测试均通过。
- 修复新预算用例误插入原 live 测试中段导致的结构破坏：原测试恢复自包含、新预算测试独立成例；聚焦文件 7 个测试全部通过。
- 完整 protocols 回归 `786 passed, 58 warnings in 179.99s`；包 57/61/121 正位工件经强类型执行状态重放，在 gate v2 下 3/3 accepted、0 问题。
- Codex 已逐条核对 57/61/121 共 36 个目标，确认当前期别处置及关键 AND/OR 逻辑保持原文。`claims_complete=false`；无生产写入。恢复入口为 `CHECKPOINT_20260827_SMALL_BATCH_PHASE_APPLICABILITY_ACCEPTED.md`。下一步仅选择下一组结构风险不同的少量代表包；不得全跑 128 包，不得启动受试者、浏览器、视觉或独立测试者。

## 2026-08-27 Phase 5.8d 流程表期别作用域与表 5 小批量验收

- 旧计划第 39 包的技术绿色结果被父级拒绝：`表 2 Ⅲ期临床研究阶段流程表` 后的说明因表题无大纲层级而被错误交给Ⅱ期语义模型。通用结构修复后，表 1 后 28 条明确为Ⅱ期、表 2 后 28 条明确为Ⅲ期。
- 新 D001 Ⅱ期基线为 `1848` 个覆盖单元、`1245` 个语义目标、`131` 包。稳定原文比较只移除上述 56 条，无新增、无其余原文语义变化；旧计划验收不自动迁移。
- 新计划第 63/64/65 包的 24 个目标完成真实运行和父级核对：全部为当前Ⅱ期适用，表 5 父段、表题及 r0-r12 来源所有权闭合。
- 第 63 包首轮理由含 82 个 U+000B，不可见字符门禁现统一覆盖结果、证据、未决和分组理由；干净重跑 11/11、控制字符 0。
- 本轮只接受期别适用性，不接受控制点结构化完成。来氟米特清除剂缩短洗脱、较长者运算、中药两周例外、表 5/附录 3 引用仍须进入后续控制合同。
- 协议层全量 `789 passed, 58 warnings`；新计划当前仅 3 包接受、剩余 128 包，`claims_complete=false`。受试者、浏览器、视觉和独立测试者未启动。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260827_D001_PHASE_TABLE_SCOPE_AND_TABLE5_ACCEPTED.md`。

## 2026-08-27 Phase 5.8d 表 5 结构化控制点代表行验收

- 控制点 Agent 的严格结构输出现在还必须在 Runner 内通过发布门禁；语义、时间窗、来源或例外作用域不闭合时，问题会回到同一会话定向修复。
- 首次真实修复虽技术绿色，但越界重写 3 个无关候选及处置，已由 Codex 父级拒绝并保留为反例。通用修复范围保护现在以首次水合输出为基线，只允许改动原始拒绝问题涉及的结构单元；越界改写以 `REPAIR_SCOPE_ESCAPE` 阻断。
- 新的 D001 Ⅱ期表 5 重放使用 `MTPLX/mtplx-qwen38-27b-optimized-quality:medium`，2 次同会话调用后 4/4 代表控制点通过。来氟米特 24 个月默认窗与清除剂触发的 6 个月替代窗、其他生物制剂 3 个月和 5 个半衰期较长者、中药/中成药局部 2 周例外及全部持续至研究结束的约束均保持原文逻辑。
- 接受工件为 `artifacts/phase5-slice59m-d001-table5-mtplx-control-replay-bounded-repair-20260827/`；聚焦 `75 passed`，协议层 `823 passed, 58 warnings`，review gate 与 execution audit 通过。
- 当前仍是 `1848/1245/131`，只增加 4 个代表行的结构化控制点接受；剩余 128 包未完成，`claims_complete=false`。未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260827_TABLE5_STRUCTURED_CONTROL_REPLAY_ACCEPTED.md`。下一步继续小范围验证不同结构风险，不做全量运行。

## 2026-08-28 Phase 5.8d 病毒学与结核跨章节控制点验收

- 使用冻结 D001 Ⅱ期 DOCX 解构结果完成两组真实 MTPLX medium 运行，证明系统可从未经用户预处理的方案原文结构继续抽取散落于流程表、正式排除标准和专门检查章节的控制增量。
- 病毒学 V10 只发布 3 个增量控制：筛选期补充 HBsAb/HBeAg/HBeAb、全部病毒学结果首次给药前 28 天有效性、三类条件病毒学检测结果的共同 28 天有效性；EX-22 已覆盖内容未重复发布。
- 结核 V5 只发布 4 个增量控制：IGRA 阳性后 CT、活动性结核不得随机、潜伏性结核不得随机及 4 周治疗例外、不确定结果可复测 1 次；EX-09 已覆盖内容未重复发布。
- 通用门禁新增并验证：单条件也必须有触发层、同组重复语义原子拒绝、例外按候选自身语义范围识别、可选动作语气保留、禁止随机/给药锚定事件本身、不同最终决定阶段拆分。
- 聚焦回归 `76 passed`，协议层全量 `845 passed, 58 warnings`；父级验收与关键哈希位于 `artifacts/phase5-slice59n-d001-viral-tb-parent-acceptance-20260828/acceptance-summary.json`。
- 当前仍为 `1848/1245/131`，剩余 128 包，`claims_complete=false`；未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_VIRAL_TB_CONTROL_REPLAY_ACCEPTED.md`。

## 2026-08-28 妊娠/FSH 代表组：系统加固通过，临床解构未接受

- 原始 DOCX 自动结构化输入可到达控制 Agent，不要求用户提前整理方案；但当前混合来源单元同时含已覆盖分支、唯一增量分支和治疗后操作，单批输出契约尚不能稳定收敛。
- V4 确定性门绿色但父级临床拒绝；V5 新门禁正确阻断错误输出，11 次尝试仍无可水合终稿。两轮均作为不可变反例保留，禁止将技术绿色描述为医学接受。
- 通用系统已增加：候选局部条件边界、不同最终决定时点拆分、治疗后程序排除、豁免语气保持、已覆盖控制及分支去重。协议层全量 `861 passed, 58 warnings`。
- 当前仍为 D001 II `1848/1245/131`、剩余 128 包、`claims_complete=false`；未运行病例、OCR、浏览器、视觉或独立测试。
- 下一安全动作是先在语义调用前按决定时点和覆盖差异拆分混合来源，而非继续增加模型重试。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_PREGNANCY_FSH_CONTROL_REPLAY_HARDENED_NOT_ACCEPTED.md`。

## 2026-08-28 妊娠/FSH V7：时点拆分通过，最早适用节点未闭合

- 共享发布门禁现逐个触发事实核对陈述和直接摘录，不能再用一个首次给药锚点承载“筛选时或首次给药前”两个最终判定时点；候选和正式控制均受约束。
- 聚焦回归 `120 passed`，协议层全量 `866 passed, 58 warnings`。V7 真实 MTPLX medium 运行 9 次调用、`734.447232s`，技术解析并形成 3 个候选。
- 父级核对确认筛选/首次给药阳性已拆开，治疗后复测、已覆盖检查和已覆盖人群未重复，初潮前豁免语气正确；但初潮前候选只绑定基线与首次给药前，未在最早受影响的筛选节点生效，因此整组不接受。
- 新根因是补充控制尚未与被补充流程要求的最早受影响节点做结构化对齐。下一步先建立通用合同和反例，不运行 V8。
- D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；受试者、OCR、病例审核、浏览器、视觉和独立测试者均未运行。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_PREGNANCY_FSH_V7_STAGE_ALIGNMENT_NOT_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 妊娠/FSH 多访视目标合同已落地，V9 仍未接受

- 当前控制点 Agent 不再把跨访视原文压成单一流程目标；筛选、基线和首次给药前目录身份可同时保存，并在输入、水合和发布三层逐项核对。
- D001 原始 DOCX 产品目录实证同一妊娠/FSH 检查存在三个不同访视目标。V8 因旧单值字段丢失基线/D1 闭包而拒绝；V9 已能输出三目标和阶段拆分，但未生成可水合终稿。
- V9 失败显示验收器串行返回发布问题与临床问题会造成修复范围不完整。当前代表组验收已同轮合并两类问题；这一修复已通过确定性回归，但未用追加模型调用宣称临床成功。
- 完整方案层回归 `872 passed, 58 warnings`；合并反馈后的聚焦回归 `165 passed`。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_PREGNANCY_FSH_V9_MULTI_VISIT_REPAIR_NOT_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 妊娠/FSH V10 访视覆盖边界未接受

- 同轮汇总发布与临床问题后，V10 在 6 次真实 MTPLX medium 调用内形成技术可发布终稿；筛选阳性、首次给药前阳性和初潮前豁免三个增量候选的核心语义已明显改善。
- Codex 父级临床复核仍拒绝：`body.p815#atom-11-74` 声称筛选、基线、D1 三个目标同时完整覆盖 II 期 W12 和提前退出访视，但这些链接目标的 `visit_instance` 不含上述访视；首次给药前阳性候选也错误绑定 `flow-baseline`，没有使用冻结的 `flow-d1-pre-dose`。
- 系统根因是访视级流程目录项复用了整段跨访视来源说明，造成来源摘录范围大于目标访视身份；发布门禁目前只验证目标 ID 和集合，不验证处置声称的访视覆盖集合。下一步必须让流程来源语义与访视实例结构化对齐，并精确区分基线与首次给药前节点。
- 聚焦回归 `167 passed`，协议层全量 `872 passed, 58 warnings`。V10 父级评估位于 `artifacts/phase5-slice60d-d001-pregnancy-fsh-parent-assessment-20260828/assessment-summary.json`。
- 当前仍为 D001 II `1848/1245/131`、剩余 128 包、`claims_complete=false`；未运行 V11、受试者、OCR、病例审核、浏览器、视觉或独立测试者。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_PREGNANCY_FSH_V10_VISIT_SCOPE_NOT_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 访视覆盖范围和精确审核节点门禁

- 共享发布边界现在不再以流程目标的宽泛来源摘录代替访视身份；`required_procedure` 处置必须证明链接目标的 `visit_instance` 并集覆盖 owned 原文中全部明确的选定期访视。
- 明确标注为对侧期别的访视短语先从当前期别比较中排除。D001 II 反例只报告 W12 和提前退出未覆盖，不误报 III 期 W16/W52。
- 带首次给药、随机或基线锚点的控制，如果冻结流程存在对应专门节点，最终判定必须落在该节点；相同 `ReviewStage` 不再被视为相同访视。
- 保存的 V10 水合结果已在新代码下重放并确定性拒绝。聚焦回归 `169 passed`，协议层全量 `874 passed, 58 warnings`。
- V10 临床结果仍不接受，未运行 V11。当前保持 D001 II `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_VISIT_SCOPE_AND_EXACT_NODE_GATE_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 访视合并时间边界已修复，基线值层级回放未接受

- 时间合同、求值器、发布门禁和中文显示现显式区分 `＞/≥/＜/≤` 及是否包含边界；时间锚点缺失优先定位到具体原子和原句。
- 使用未经用户预处理的 D001 Ⅱ期原始 DOCX 产品链完成一次 MTPLX medium 回放。第三次响应正确保存 `≤7天` 闭合上界、`＞7天` 开放下界和 `D1前7天内` 闭合上界。
- 回放仍被父级拒绝：明确要求 D1 给药前取值的生命体征、PASI、PGA、BSA、DLQI 和皮损照片被错误扩展到较宽基线窗口，并重复了冻结精确节点已覆盖的义务。
- 当前只接受通用时间合同与诊断修复，不接受或发布本组临床解构。组合回归 `213 passed`。
- D001 II 仍为 `1848/1245/131`，剩余 128 包，`claims_complete=false`；未运行受试者、OCR、病例审核、浏览器、视觉或独立测试者。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_VISIT_MERGE_OPEN_BOUND_FIXED_REPLAY_NOT_ACCEPTED.md`。下一步先建立通用默认规则/精确特例层级反例，不原样重跑本组。

## 2026-08-28 Phase 5.8d 时间义务作用域合同

- 上轮真实 D001 回放暴露的系统根因已下沉到共享合同：访视安排、检查结果有效期和基线值选取不能再共用通用“完成/核对”语义。
- 访视安排只能关联自身冻结流程节点；结果有效期必须关联受影响的精确流程必做项；基线值选取必须在通用流程节点和精确检查项两种作用域中择一，通用原则与特例需拆分候选。
- Agent 输出水合与最终发布门禁采用同一边界，阻止通用时间窗向具体检查项传播，也阻止绕过 wire 的领域对象直接发布。
- 保存的第三次 D001 响应在新合同下被拒；人工只做结构化等价拆分后可水合，但不构成新的模型运行或临床接受。
- 聚焦回归 `218 passed`，完整协议层 `887 passed, 58 warnings`。当前仍为 D001 II `1848/1245/131`、剩余 128 包、`claims_complete=false`；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_TEMPORAL_OBLIGATION_SCOPE_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 胸部CT结果有效期与盲态验收边界

- D001 Ⅱ期 `body.p797` 的胸部CT要求来自未经用户预处理的原始 DOCX 产品链。冻结流程必做项已经同时保留筛选期检查、知情同意书签署日前1个月结果有效期和“满足评估要求”。
- MTPLX medium 首轮正确返回 0 个新候选并关联既有胸部CT流程项；“研究中心可酌情决定是否复测”不是必须执行或必须形成记录的义务。
- 原验收配置把 `body.p797` 预设为必须生成候选，并将 `CONTROL_DELTA_DROPPED` 作为同会话修订错误回传，导致后续响应迎合预期、虚构“访视记录应体现复测决定”。这是验收器确认偏差，不是结果有效期合同缺失。
- 当前金标准候选期望只参与父级最终验收，不再进入 Agent 修订提示。保存首轮响应离线重放为 0 候选、发布门禁接受、临床拒绝问题 0；未再次调用模型，也未发布新控制点。
- 聚焦回归 `146 passed`，方案层完整回归 `887 passed, 58 warnings`。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_CT_VALIDITY_CONFIRMATION_BIAS_FIXED.md`。后续小批量真实验证必须保持 Agent 与父级金标准隔离。
# 2026-08-28 Phase 5 当前暂停点

避孕附录代表组已完成 v3 真实 MTPLX medium 回放但未接受。共享条件/沟通持续期门禁与提示合同已修复，p1326 输出已收敛；p1325 的 ICF 至末次给药后 3 个月锚点仍未正确生成。暂停前最后提示补丁尚未验证，恢复入口为 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_CONTRACEPTION_SEMANTIC_REPLAY_V3_PAUSED.md`。D001 II 仍为部分基线 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

## 2026-08-28 Phase 5.8d 避孕附录计划访视闭包验收

- v4 虽保留附录避孕语义并通过旧技术门，但把“计划的访视点”压缩为仅筛选节点，父级临床拒绝。
- 共享门禁现在要求计划访视控制覆盖冻结目录的每个 `visit_instance`，并在各节点分别判定；非计划访视不触发该闭包。
- v5 在与 v4 完全相同的冻结来源和批次上，以 2 次 MTPLX medium 调用生成 2 个控制。父级确认 IN-06 不重复、ICF 至末次给药后三个月区间、禁止激素类避孕、方法讨论/知晓、计划访视告知、病历记录、参与者同意和条件联系指令全部保留。
- p1326 同时绑定筛选和基线决定节点，两个阶段均有到期最低证据，未发明治疗期访视。
- 聚焦 `129 passed`；方案层全量 `896 passed, 58 warnings`；父级验收证据位于 `artifacts/phase5-slice60m-d001-contraception-documentation-replay-planned-visit-closure-20260828/parent-clinical-acceptance.json`。
- 当前仍为 `1848/1245/131`、剩余 128 包、`claims_complete=false`；受试者、OCR、病例审核、浏览器、视觉和独立测试者均未启动。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_CONTRACEPTION_PLANNED_VISIT_ACCEPTED.md`。下一步只选择一个能增加新语义覆盖的极小异质组，不直接全跑剩余包。

## 2026-08-28 Phase 5.8d 病史/治疗史采集代表组

- 四个正文单元和 14 个跨章节只读上下文直接来自未经用户预处理的 D001 Ⅱ期 DOCX 冻结结构。只读上下文已真实进入 Agent 提示，但不会取得批次所有权或成为候选来源。
- 系统把“自筛选/上次访视以来”的回顾区间起点与实际执行访视分开保存；已知流程事项不得降级为普通补充说明来规避访视闭包。
- 流程目标显式声明资料家族，独立结构期望只供确定性门禁使用，不进入 Agent 首轮输入；共享代码不扫描模型理由或 D001 目录编号推断链接。
- v9 真实 MTPLX medium 运行 2 次后接受：`p772` 绑定筛选+基线病史，`p773` 绑定筛选+基线治疗史，`p858` 绑定基线病史+治疗史，`p871` 绑定 D1 给药前病史+治疗史；0 新候选。
- 父级确认近2年尽力收集、银屑病完整病程、其他疾病半年治疗史和正式排除标准各自时间窗保持分层。接受证据见 `artifacts/phase5-slice60w-d001-history-treatment-collection-replay-structured-family-20260828/parent-clinical-acceptance.md`。
- 最终代码聚焦回归 `189 passed`；完整方案层回归 `911 passed, 58 warnings`。
- D001 II 仍为 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_HISTORY_TREATMENT_COLLECTION_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 知情同意/人口学节点前动作闭包

- 当前活动来源仍是 D001 Ⅱ期原始 DOCX 自动结构化链和 131 包冻结计划；旧 217 包快照只能解释历史诊断，不能定义活动包序号。
- 真实回放显示“筛选前解释所有研究程序”既不是 ICF 签署事实，也不能用旧通用完成义务准确表达。仅改提示连续两次遗漏；加入动作覆盖门禁后又暴露结构表达缺口。
- 共享合同新增“节点前完成”，只允许 `before` 方向并保留命名锚点；流程目标同步声明覆盖动作，使遗漏动作由确定性门禁发现。
- v4 以 2 次 MTPLX medium 调用接受：p768 形成 1 个筛选前解释候选，p770 由筛选期人口学流程覆盖；IN-01、IN-02、签署和采集四字段均未重复。
- 聚焦回归 `174 passed`，完整方案层 `912 passed, 58 warnings`，执行治理审计通过。
- Phase 5 未完成：D001 Ⅱ期保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；受试者、OCR、病例审核、浏览器、视觉和独立测试者均未启动。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_ICF_DEMOGRAPHICS_ACTION_CLOSURE_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 身高/体重共享门禁接受，代表组未发布

- D001 Ⅱ期活动 131 包计划第 68 包直接来自未经用户预处理的原始 DOCX 结构化链。流程目录只覆盖身高/体重测量执行与记录，章节另有准备、设备、体位、操作步骤、单位和精度要求。
- 共享合同现可冻结每个来源单元的流程目标和结构标题；发布门禁阻断目标阶段越界、动作遗漏、标题提升及记录精度压缩。冻结目标优先于“其余访视点”等模糊文本解析。
- v7 曾形成语义正确的身高/体重拆分，但提升了结构标题；v8/v9 分别因 kg 一位小数和 cm 整数被压成一般核对义务而拒绝。v9 在七次有界调用内未形成终稿，不追加重试。
- 当前只接受系统失效关闭能力，不接受或发布第 68 包控制点。聚焦 `149 passed, 5 warnings`，方案层完整回归 `919 passed, 58 warnings`；执行治理审计通过并已归档。
- D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；未启动受试者、OCR、病例审核、浏览器、视觉或独立测试者。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_D001_HEIGHT_WEIGHT_GATES_ACCEPTED_AGENT_UNRESOLVED.md`。下一步设计通用的修订状态确定性保留机制，先离线验证，不直接重跑或扩批。

## 2026-08-28 Phase 5.8d 修订状态确定性保留验收

- 无机器可读范围的水合后错误现立即失效关闭；同一会话使用滚动失败基线，不再永久保留第一个错误版。
- 普通候选修订按精确来源结构单元键保留；明确重分区时要求授权来源全集守恒，任何交叉越界或来源丢失都阻断自动修订。
- 记录单位/精度问题现携带精确义务原文定位。候选与原子对应唯一时只替换该原子；候选其他字段、同组兄弟原子和范围外候选均由系统恢复。
- 候选内容修订后的系统 ID 重算按来源闭包规范化比较，不再误报为处置链接越界。
- v9 保存响应显示：第 6 次已将 `body.p780` 的记录要求压成 `must_professional_assessment`，第 7 次只修复体重候选并保留该错误。因此新机制被接受，但第 68 包仍是“需要核对”。
- 聚焦回归 `153 passed`；方案/事实/存储组合回归 `1033 passed, 58 warnings`；编译、差异检查和执行审计通过。
- D001 II 仍为 `1848/1245/131`，剩余 128 包，`claims_complete=false`；受试者、OCR、病例审核、浏览器、视觉及独立试用均未启动。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_BOUNDED_REPAIR_RETENTION_ACCEPTED_D001_UNRESOLVED.md`。下一步从活动计划选新的极小异质组，先建立盲态来源闭包和父级检查清单，不重跑第 68 包。

## 2026-08-28 Phase 5.8d 权威目标原文传递验收

- 完整方案上传链此前只把冻结目录身份和来源编号交给控制 Agent，官方规则与流程必做项原文会在后续跨章节判断前丢失；旧代表组脚本的人工矩阵补齐不是产品能力。
- 冻结目录现保存逐来源权威摘录，规划器将定位与摘录成对排序并传入 Agent。纯结构表格根以 `null` 占位，既保留结构归属又禁止补写不存在的原文；旧目录哈希保持兼容。
- 首次方案层回归因 MG-K10-SAR 的无文本表格根失败，修订后 CMS-D001 与 MG-K10-SAR 的真实 DOCX 链均通过。D001 EX-20 的 ALT/AST/总胆红素阈值及研究者不可接受风险合取已进入提示，GGT 未被混入。
- 聚焦回归 `143 passed`；方案层与合同工件 `974 passed, 58 warnings`；执行审计通过。
- 本切片未运行第 70-71 包语义 Agent，未接受任何新控制点。D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_AUTHORITATIVE_TARGET_EXCERPTS_ACCEPTED_LAB_NOT_RUN.md`。下一步用产品冻结目录准备实验室代表组干跑，不能再使用人工矩阵补齐权威目标。

## 2026-08-28 Phase 5.8d 实验室动作保留门控

- 第 70–71 包的最终干跑已使 `body.p316`、`body.p325`、`body.p802`、流程表四行及 EX-20 权威原文进入提示；来源闭包机制接受。
- 唯一一次 MTPLX medium 运行结构合法，但将 `body.p799` 的采集样品和按标准程序执行降为普通说明，父级医学审查拒绝，未发布。
- 根因是产品规划器没有向确定性门控填充必备动作元数据；现已以项目无关规则冻结采样和按规定程序执行两类动作。
- 保存原始输出在新元数据下稳定触发 `REQUIRED_ACTION_DISCARDED`，证明系统已能在模型结构正确但语义遗失时失效关闭。
- 聚焦回归 `158 passed`，完整方案模块 `944 passed, 58 warnings`，Hermes 审计与 review gate 通过。
- D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；第 68 包不变。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_LABORATORY_ACTION_GATE_REJECTED.md`。下一步建立新修复切片，用修复后产品批次重跑一次，不把父级期望答案注入 Agent。
## 2026-08-28 Phase 5.8d 实验室动作门控重放

第 70 包在修复后的动作门控下完成一次真实 MTPLX medium 调用。模型错误地把检查项目和访视目录视为对“采集样品”和“按标准实验室程序执行”的完整覆盖；确定性门控触发 `PROCEDURE_ACTION_UNCOVERED`，父级拒绝且未发布。下一步只建立通用的候选义务动作覆盖证明并离线验证，不原样重试模型或扩大到剩余包。恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_LABORATORY_ACTION_GATE_RERUN_REJECTED.md`。
## 2026-08-28 Phase 5.8d 候选义务动作覆盖证明

共享门控现要求其他控制候选以当前来源单元的义务陈述逐项保留流程目录未覆盖动作，关闭只改处置类型、来源摘录冒充和跨单元借用。保存的 60zv 错误响应仍被拒绝；本轮无模型调用、无发布。恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_CANDIDATE_ACTION_SEMANTIC_COVERAGE_ACCEPTED.md`。

## 2026-08-28 Phase 5.8d 病毒学条件豁免重评暂停

病毒学代表组 v6 在 4 次 MTPLX medium 响应后技术通过当时门禁，但独立审查发现 `body.p804` 的乙肝表面抗体、乙肝 e 抗原、乙肝 e 抗体被拆成无条件筛选完成义务，未继承同段整组病毒学检查的首次给药前 28 天有效期和条件性无需再次检查。父级已撤回临床接受，v6 不发布。

共享代码已加入条件豁免绑定与过度证据检查，并把同源候选修订改为与模型数组顺序无关的未授权兄弟唯一匹配；最新仅完成 `17 passed` 聚焦验证，完整方案层回归和 v7 真实重放尚未执行。恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_VIROLOGY_WAIVER_REASSESSMENT_PAUSED.md`。

## 2026-08-28 Phase 5.8d 病毒学 v8 范围拆分拒绝

- v7、v8 均已作为不可变失败记录保留；v8 使用 MTPLX medium 运行 5 次、336.866189 秒，最终未水合、未过门禁、未发布。
- v8 第 5 次响应正确修订 p804 目标候选但越界改写 p805。共享有界恢复现丢弃不同来源改写并恢复上一轮候选；同源未授权兄弟、候选数量和来源分区仍严格冻结。
- 离线恢复后 p805 可接受，但 p804 的三项补充病毒学检查仍被拆成无条件筛选义务，没有继承同段 8 项检查共同的 28 天有效期及条件性无需再检，触发 `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`。
- 独立 Gemini/Grok 审查支持该工程修复和临床拒绝；当前 guard 生成器只生成两角色而验证器要求 `cursor-cli`，`review-gate` 通过但 `validate-conference` 未完全闭合，未伪造第三路结果。
- 聚焦 `29 passed`；完整方案层 `989 passed, 58 warnings`；编译与差异检查通过。
- D001 II 仍为 `1848/1245/131`、剩余 128 包、`claims_complete=false`；本轮未扩大至受试者、OCR、病例审核、Patient Profile 或前端。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_V8_SCOPE_SPLIT_REJECTED.md`。下一步先设计 p804 同源来源闭包的候选合并/重写合同，冻结 p805；确定性测试和独立审查通过前不启动新模型回放。

## 2026-08-28 Phase 5.8d p804 来源闭包权限验收

- 来源闭包重写的传递候选来源全集现必须包含于确定性问题的结构单元授权；授权不完整时在调用模型修订前返回“需要核对”。
- 控制级问题现保留原始候选起点。每轮仅允许来源闭包、普通重分区或原子/临床修订中的一类拥有修订范围，其他问题保留在消息中并在后续校验轮次重新出现。
- 真实 Runner 的跨单元候选、控制级起点、混合问题隔离均有回归。聚焦 `47 passed`，产品代码完整回归 `1007 passed, 58 warnings`，四轮独立审查最终接受工程合同。
- 本轮没有运行 LLM/VLM 重放，没有发布控制点。v8 仍是已拒绝反例，`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260828_P804_SOURCE_CLOSURE_AUTHORITY_ACCEPTED_REPLAY_DEFERRED.md`。下一步先固化可重现重放 harness，决定串行修订预算，再对一次新的不可变 p803-p805 重放单独做 go/no-go。

## 2026-08-29 Phase 5.8d 模型无关重放基础设施验收

- 产品现可从原始 DOCX 经正式结构化链确定性生成冻结快照、完整清单、指定来源批次、Agent 输入和提示词；默认不创建传输层、不调用模型。
- 全局修订预算固定为 1 次传输尝试和最多 2 轮串行结构修订；错误类别改用结构化代码，重复输出无进展时终止。
- 重放校验覆盖 summary、replay input、manifest、snapshot、batch、agent input、每个来源单元和工具链；重复 `source_ref`、路径泄漏或身份漂移均失效关闭。
- D001 p803-p805 只读锚点完成两次独立构建，外部指纹均为 `cdb75fbc9812940acf2048a44ef28455a3b3111af57611ed81ac055db21d61d3`。聚焦 `73 passed`，协议全量 `1033 passed, 58 warnings`，编译和差异检查通过。
- 独立复审提出的 F1-F6 已逐项关闭；工程代码无 D001 或人工矩阵特异规则。工具链升级必须按检查点旁的再锚定说明双构建后更新锚点。
- 本轮未调用临床模型、未发布控制点，v8 仍拒绝，`claims_complete=false`。PDF 目前只能渲染，尚不能进入统一结构化方案链；下一切片优先补齐 PDF 原始上传解构入口。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_MODEL_FREE_REPLAY_HARNESS_ACCEPTED_CLINICAL_REPLAY_DEFERRED.md`。

## 2026-08-29 Phase 5.8d 原生文字 PDF 结构入口验收

- 未经用户预处理的原生文字 PDF 现可按魔数进入与 DOCX 共享的冻结块、提取快照和来源定位链。
- PDF 块保留物理页号、页文本区间和字符坐标框；对齐前逐字核对原页子串，不匹配即拒绝伪精确。PDF 直接复用原文件展示，不经二次转换。
- 扫描、混合文本层、零页、加密、损坏和哈希不一致均失效关闭；加密 PDF 现可穿透 `pdfplumber` 包装异常正确识别。
- DOCX 序列化不带空 PDF 定位字段，D001 指纹保持 `cdb75fbc9812940acf2048a44ef28455a3b3111af57611ed81ac055db21d61d3`。
- 真实 SAR V2.1 PDF 两次均为 120 页、285 块和 285/285 bbox 直接定位，哈希 `7843e5e55966da24044b224e2221418d3d838bcf819cf557824702ca4ad726c3`，无降级/未对齐，源文件字节和 mtime 不变。
- 聚焦 `12 passed`；后端全量 `2977 passed, 1 skipped, 139 warnings, 2 subtests passed`；独立审查通过“入口接受，质量待续”的有限结论。
- PDF 标题/表格层级、多栏阅读顺序和空白页/图像扫描页分流尚未与 DOCX 等价，必须作为下一独立质量切片。
- 本轮未调用临床模型、未发布控制点；D001 v8 仍拒绝，`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_NATIVE_TEXT_PDF_ENTRY_ACCEPTED_STRUCTURAL_PARITY_PENDING.md`。

## 2026-08-29 Phase 5.8d 原生文字 PDF 结构保真验收

- 真实 SAR V2.1 原生 PDF 现恢复 120 页的阅读顺序、158 个正文标题、48 个结构表格以及重复页眉页脚分区；2756 个结构块全部保留坐标级来源定位。
- PDF 两次解析内容哈希一致，源文件字节和修改时间不变；DOCX 的 154 个正文标题归一化后在 PDF 中无缺失。
- 兄弟来源范围碰撞、临床单位误判标题、超高/短页页边文字和表格局部失配污染均已从共享机制层修复并回归。
- 最终后端全量 `3154 passed, 3 skipped, 141 warnings, 18 subtests passed`，独立会商与 Codex 主会场均无高、中等级阻断。
- 接受边界只覆盖原生文字 PDF。扫描/混合 PDF、跨页表语义拼接、多栏与全宽表混排仍延后；没有临床模型调用或控制点发布，D001 `claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_PDF_STRUCTURAL_PARITY_ACCEPTED_NEXT_FULL_PROTOCOL_DECONSTRUCTION.md`。下一安全动作是从原始 DOCX/PDF 上传链选择新的极小跨章节来源组，继续全方案控制点解构。

## 2026-08-29 Phase 5.8d 心电图控制点、来源字形与动作合同验收

- 心电图代表组的第二次真实运行第三响应已通过离线完整门禁：1 个候选、1 个控制点，发布门禁与临床拒绝门禁均为 0 问题。
- 原始响应 SHA-256 为 `6e18be457055732ca68697a495e60db4e12fd47d5f2df6dc8c916e76a7e1cba0`，未发起新的模型调用。
- 共享校验仅恢复唯一、连续、等长的引号字形差异；词、数字、单位、比较符、空白、普通标点、多重匹配和跨来源变化继续拒绝，原始 wire 不被修改。
- 深层根因不是单纯引号不一致：冻结计划要求的 `prepare_participant` 与 `calculate_qtcf` 在共享动作检测器中没有可识别语义。已补充项目无关动作目录及负向回归，不含 D001 或条款特例。
- 聚焦回归 `283 passed`；协议模块全量 `1106 passed, 58 warnings`；受控执行审计和独立审阅通过。
- 本轮只接受心电图代表组，未并入 131 包正式目录；D001 II 保持剩余 128 包和 `claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_D001_ECG_CONTROL_ACCEPTED_ACTION_CONTRACT_FIXED.md`。下一步选择新的最小异质来源组，先冻结来源闭包、目录覆盖和父级检查清单，再决定一次有界语义重放。

## 2026-08-29 Phase 5.8d 生命体征操作模态代码闭环，真实模型阻断

- D001 II 生命体征代表组保留必做测量、推荐性休息准备和治疗期 PK 同点尽力顺序三种不同强度；EX-21 合取排除逻辑继续保持独立。
- 多轮真实回放暴露的共因已进入共享门禁：不得把实际休息改写为仅告知建议，不得把建议项强化为必备资料，不得遗漏筛选或 D1 给药前阶段，不得在正式义务、最低证据和审核指引之间丢失列举项，也不得把新增要求降为普通解释。
- v10 虽通过当时技术门禁，但父级仍因“四类检查/五个读数”口径错位和关系强度不足拒绝。v11/v12 在最新门禁下连续遭遇 MTPLX 服务端 500；会话缓存从约 49.1 GB 回落至约 24.1 GB 后，v13 两个新会话仍返回 500，未产生可供最终临床验收的终稿。
- 最新聚焦回归 `155 passed, 5 warnings`；方案模块完整回归 `1145 passed, 58 warnings`。只接受共享代码和确定性回归，不接受或发布生命体征代表组。
- D001 II 正式状态保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`；受试者、OCR、Patient Profile、浏览器及视觉工作未启动。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_VITAL_SIGN_MODALITY_INFRASTRUCTURE_BLOCKED.md`。下一安全动作是用非临床诊断夹具隔离 MTPLX 的长提示与严格结构化输出服务端路径；基础设施修复后再进行一次新的同源重放和 Codex 父级临床验收。

## 2026-08-29 Phase 5.8d 生命体征操作模态与MTPLX严格结构输出验收

- 服务端4000字符前导边界与MTP推测解码在严格语法边界附近共同造成状态失步。系统没有依赖服务重启或环境变量，而是让四条MTPLX严格JSON Schema传输显式使用请求级AR；DeepSeek和oMLX不变。
- v14沿用v13冻结来源、临床问题和父级检查清单。三次同会话响应依次被结构门禁、阶段门禁拦截并修复，最终1候选、1控制，发布门禁和临床拒绝门禁均通过。
- 父级临床接受四类生命体征及五个显示数值、建议性休息实际动作、筛选+D1基线双节点、p786治疗期隔离，以及流程目录和EX-21不重复。
- 两次独立审阅完成；夜间DeepSeek V4 Flash max无回退复核未发现临床或结构阻断。主线程不把四类项目误拆为五类检查，也不把v14恢复归因于未发生的服务环境修改。
- 聚焦回归 `45 passed, 5 warnings`；方案与语义传输组合回归 `1189 passed, 58 warnings`。
- 本代表组不并入131包正式目录；D001 II仍为`1848/1245/131`、剩余128包，`claims_complete=false`。后续工作流和视觉阶段未启动。
- 后续受试者判定引擎必须保证推荐性动作偏离只形成提醒；治疗期模块需显式承接p786；后续真实运行证据需记录严格结构化生成模式。父级验收用独立追加文件表达，不改写不可变运行工件。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260829_VITAL_SIGN_MODALITY_AR_ACCEPTED.md`。下一安全动作是选择新的极小异质来源组，先冻结来源闭包、已知控制覆盖和父级检查清单。

## 2026-08-30 Phase 5.8d 疗效评分方法与阶段来源闭包验收

- 第 74 包以未经用户预处理的原始 D001 DOCX 为基座，最终形成 PASI、PGA、BSA、DLQI 四个独立方法学控制点；结构标题、冻结流程和 IN-04 未重复发布。
- 共享机制修复了表头脚注作用域、方法增量分类、问卷回顾期与研究时间窗混淆、规则依据冒充受试者证据、自评工具错误专业化及权威引用缺少同原子逐字支持六类系统问题。
- 第 1-4 次回放分别因来源、证据、专业判断和溯源问题拒绝；第 5 次 MTPLX medium 请求级 AR 回放经 2 次有界响应形成 4 候选和 4 控制，技术、临床和发布门禁均通过。
- 父级确认 IN-04 仍仅为 PASI/PGA/BSA 三项合取；DLQI 只绑定 D1 给药前，不成为入排阈值，也不要求研究者评估记录。
- 聚焦回归 `186 passed, 5 warnings`；方案与 Agent 全量回归 `1197 passed, 58 warnings`。
- 本代表组不并入正式 131 包目录；D001 II 仍为 `1848/1245/131`、剩余 128 包、`claims_complete=false`。未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_EFFICACY_METHOD_SCOPE_ACCEPTED.md`。下一安全动作是按冻结计划检查第 75 包，先建立来源闭包和父级临床清单。

## 2026-08-30 Phase 5.8d 第 75 包模型外语义边界验收

- 第 75 包已拆分为四个结构标题、三类治疗期执行、一项非受试者级研究执行和一项 ICF 后资料收集候选，不再按结构包整体发射同类控制。
- p837 是本组唯一候选，绑定筛选、基线、D1 给药前，必须保留开始/结束、剂量、频率、途径或方法、适应症；资料收集不得升格为入排不通过条件。
- 共享门禁新增来源组成要素完整性检查，只检查模型语义陈述，不允许原文摘录掩盖模型漏项。
- 首次模型外准备因无关已知流程目标的访视实例不一致而停止；修正语义目标注入边界后通过，未放宽校验。
- 模型外准备 `9 owned / 17 attached / 26 total`；聚焦 `109 passed, 5 warnings`；方案与 Agent 全量 `1198 passed, 58 warnings`；执行审计通过。
- p529 与操作层 PK 安排的方案内部不一致，以及 p839-p979 未拥有的访视正文，继续作为需要核对和规划覆盖缺口保留。
- 未调用临床语义模型，未发布控制点，未并入正式目录；D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE75_MODEL_FREE_BOUNDARY_ACCEPTED.md`。下一步在一次有界第 75 包语义重放与继续第 76 包模型外闭包之间按 Phase 5.8d 顺序选择，不扩到受试者或视觉阶段。

## 2026-08-30 Phase 5.8d 第 76 包安全性摘要模型外边界验收

- 第 76 包五个拥有来源已固定为三个结构标题和两个安全性分析摘要，全部禁止发射入排候选。
- 父级发现初版只在元数据声明 `body.p985-p1024` 后续包边界，真实提示未携带这些来源；已补齐为 40 个只读附加来源并保持第 77-80 包所有权。
- p988 的筛选既存情况按病史/伴随疾病记录、p1023 的 ICF 后至首次服药前事件不作为 AE，现均进入真实提示并有准备证据回归。
- 模型外准备 `5 owned / 47 attached / 52 total / prompt 51527`；第 76 包 `24 passed`，聚焦 `198 passed`，方案与 Agent 全量 `1198 passed, 58 warnings`；治理审计通过。
- 未调用临床语义模型、未发布、未并入正式目录；D001 II 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE76_SAFETY_SUMMARY_BOUNDARY_ACCEPTED.md`。下一步进入第 77 包 AE/TEAE 定义与筛选前病史边界的最小来源闭包，不扩到受试者或视觉阶段。

## 2026-08-30 Phase 5.8d 第 77 包 AE/TEAE 与给药前病史边界验收

- 第 77 包 body.p985-p994 保持 10 个拥有单元；两个标题仅作结构归属，其余八项定义/除外语义均为治疗期记录范围，零受试者级控制候选。
- 真实只读闭包加入 body.p318/p340/p835/p885 和第 78-80 包 body.p995-p1026，共 41 个附加来源；模型外准备为 10 owned / 41 attached / 51 total / prompt 51140。
- 五类“不作为 AE 记录”情形保留研究者判断、加重、致检查疾病、高于预期及“预期周期性波动且未恶化”等合取/例外；TEAE 保留给药后新发及相对治疗前恶化两条路径。
- D1 给药前基线和入排复核不改变 AE 于 D1 启动给药后开始记录的时间锚。
- 共享 runner 修复了 CodeBuddy 结构化 429 在退出码为 0 时被误判成功的问题；治理工具 16 项单元测试通过。
- 专项 32 passed；相邻回归 112 passed；方案与 Agent 全量 1198 passed, 58 warnings；差异检查与执行审计通过。
- 未运行临床语义模型、未发布、未修改正式矩阵；D001 保持 1848/1245/131、剩余 128 包、claims_complete=false。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE77_AE_TEAE_HISTORY_BOUNDARY_ACCEPTED.md`。下一安全动作是第 78 包 SAE 定义与严重性标准的最小模型外来源闭包。

## 2026-08-30 Phase 5.8d 第 78 包 SAE 严重性模型外边界验收

- 第 78 包 `body.p995-p1006` 固定为一个结构标题和 11 项治疗期 SAE 定义/判定语义，全部禁止发射筛选或基线入排候选。
- 33 个只读来源真实进入提示：前接 AE/TEAE 定义、D1 给药前后流程锚点，以及第 79-80 包的住院除外续、严重性标准尾项、ADR/SUSAR 和 AE 收集边界。
- “任何一项”的 OR 语义、死亡结果、实际危及生命、重大功能干扰、住院由不良事件所致及研究者综合判断均由确定性回归保护。
- 父级驳回“p1011+p1012 合并为一个列表项”的建议；两者是同一连续清单中的两个独立来源单元和相邻备选项。
- 模型外准备 `12 owned / 33 attached / 45 total / prompt 48398`；专项 `37 passed`，相邻 `149 passed`，方案与 Agent 全量 `1198 passed, 58 warnings`，治理工具 `16 passed`。
- 未调用临床语义模型、未发布、未修改正式矩阵；D001 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE78_SAE_SERIOUSNESS_BOUNDARY_ACCEPTED.md`。下一安全动作是第 79 包 `body.p1007-p1014` 的最小模型外来源闭包。

## 2026-08-30 Phase 5.8d 第 79 包 SAE 尾段模型外边界验收

- 第 79 包 `body.p1007-p1014` 固定为六项住院除外清单续和两项 SAE 严重性标准尾项，全部禁止发射筛选或基线入排候选。
- 32 个只读来源真实进入提示，其中六个同词异域锚点隔离严重感染住院、受试者免疫缺陷、生殖资格、妊娠状态与参与者后代先天异常。
- 父级发现并修复 `body.p1007` 将原文“现存疾病诊断或择期手术治疗”错误改成两者同时满足的逻辑反转，并新增析取反例回归。
- `body.p1014` 只保留医学和科学判断及预防严重后果条件；不替代第 80 包 ADR/SUSAR 定义，也不提前裁定后续 SAE 报告时限与流程。
- 模型外准备 `8 owned / 32 attached / 40 total / prompt 46286`；专项 `39 passed`，相邻与共享闭包 `206 passed`，Phase 闭包 `210 passed`，方案与 Agent 全量 `1198 passed, 58 warnings`，治理工具 `30 passed`。
- 未调用临床语义模型、未发布、未修改正式矩阵；D001 保持 `1848/1245/131`、剩余 128 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE79_SAE_TAIL_BOUNDARY_ACCEPTED.md`。下一安全动作是第 80 包 `body.p1015-p1026` 的最小模型外来源闭包，不提前吞并后续特殊肝功能 SAE、因果共同判断或报告时限与流程。

## 2026-08-30 Phase 5.8d 第 80 包 ADR/SUSAR 与 AE 收集记录边界验收

- 第 80 包 `body.p1015-p1026` 固定为 ADR/SUSAR 定义及 AE 收集记录边界，12 个拥有来源均禁止发射筛选或基线入排候选。
- 父级修订分离 ADR 因果与 SAE 严重性、一般“非期望”与监管“非预期”，并锁定 SUSAR 可疑+非预期+严重三维 AND。
- `p1022` 与 `p1024` 的两种终点表述分别保留，不推断等同、不同或先后；`p1026` 不外推临床事件拆分、合并或诊断更新规则。
- 模型外准备为 `12 owned / 35 attached / 47 total / prompt 49402`；专项 `43 passed`，相邻 `192 passed`，Phase 闭包 `253 passed`，方案与 Agent `1198 passed, 58 warnings`，治理工具 `30 passed`。
- 未调用临床语义模型、未发布、未修改正式矩阵；D001 保持 `1848/1245/131`、剩余 127 包、`claims_complete=false`。未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE80_ADR_SUSAR_AE_COLLECTION_BOUNDARY_ACCEPTED.md`。下一安全动作是第 81 包 `body.p1027-p1032` 的最小模型外来源闭包，不提前吞并第 82-84 包记录细则。

## 2026-08-30 Phase 5.8d 第 81 包 AE 诊断与继发事件边界验收

- 第 81 包 `body.p1027-p1032` 只承担 AE 诊断术语、无法诊断时记录、后续诊断替换和继发事件主要原因判断，不形成预筛、筛选或基线入排候选。
- 初版来源闭包只给出“具体示例见表 7”而没有表格正文。父级将第 82 包表 7 与第 83 包易混同规则作为只读来源加入真实提示，解决模型凭常识补表和实验室异常规则混同的系统性风险，同时保持包间所有权分离。
- 诊断术语是优先偏好而非立即确诊义务；多项表现的合并受同一疾病/损害归属条件约束；无法诊断时症状/体征和实验室异常值是并列记录路径；继发事件不是一律拆分或一律合并。
- 模型外准备为 `6 owned / 62 attached / 68 total / prompt 61555`；专项 `35 passed`、相邻 `227 passed`、Phase 闭包 `288 passed`、方案与 Agent `1198 passed, 58 warnings`、治理工具 `30 passed`。
- 未调用临床语义模型、未发布、未修改正式矩阵；D001 II 保持 `1848/1245/131`、剩余 126 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE81_AE_DIAGNOSIS_SECONDARY_EVENT_BOUNDARY_ACCEPTED.md`。下一安全动作是第 82 包 `body.t12.r0-r4` 的表 7 模型外来源闭包。

## 2026-08-30 Phase 5.8d 第 82 包表 7 继发事件记录边界验收

- 第 82 包 `body.t12.r0-r4` 仅承担表 7 的列结构与四个继发事件记录分支，不形成预筛、筛选或基线入排候选。
- 父级移除无关Ⅲ期疗效表的反向提示注入，并纠正把示例细节提升为必要条件的列关系错误。
- “重度/严重”不得混同，但表 7 未明示引用 SAE 定义，因此不能自动等同；相邻全量记录和单一术语规范也不能反推表 7 的拆分、合并条件。
- 模型外准备为 `5 owned / 23 attached / 28 total / prompt 42315`；专项 `37 passed`、Phase 闭包 `325 passed`、方案与 Agent `1198 passed, 58 warnings`、治理工具 `30 passed`；执行审计无警告或错误。
- 未调用临床语义模型、未发布、未修改正式矩阵；D001 II 保持 `1848/1245/131`、剩余 125 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE82_TABLE7_SECONDARY_EVENT_BOUNDARY_ACCEPTED.md`。下一安全动作是第 83 包 `body.p1033-p1042` 的最小模型外来源闭包。

## 2026-08-30 Phase 5.8d 第 83 包持续/复发与实验室异常 AE 记录边界验收

- 第 83 包 `body.p1033-p1042` 只承担 A/B 注记、持续/复发 AE 记录及实验室异常判断与强制报告逻辑，不形成预筛、筛选或基线入排候选。
- 持续与复发、研究者判断与强制报告已分层；`p1039` 外层 OR、`p1040/p1042` 内层 OR 和 `p1041` 非穷尽示例均由确定性门禁保护。
- 相邻 `p986` AE 定义不再被提升为额外“有临床意义”前提，`p1024` 全量记录义务也不再被提升为持续/复发规则的逻辑父条款。
- 模型外准备为 `10 owned / 27 attached / 37 total / prompt 46736`；专项 `43 passed`、Phase 闭包 `368 passed`、方案与 Agent `1198 passed, 58 warnings`、治理工具 `30 passed`；执行审计无警告或错误。
- 未调用临床语义模型、未发布、未修改正式矩阵；D001 II 保持 `1848/1245/131`、剩余 124 包、`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE83_PERSISTENT_RECURRENT_LAB_AE_BOUNDARY_ACCEPTED.md`。下一安全动作是第 84 包 `body.p1043-p1054` 的最小模型外来源闭包。
## 2026-08-30 Phase 5.8d Package 84 生命体征异常与既存疾病记录边界验收

- D001 II 冻结计划第 84 包 `body.p1043-p1054` 已完成模型外来源闭包；12 个拥有来源不产生预筛、筛选或基线入排候选。
- 生命体征异常保持“研究者医学/科学判断”与“任一条件满足即必须报告”两层逻辑；既存疾病只有在研究期间发生频次、严重程度或特征恶化/改变，且该变化不是预期疾病进展时才记录为 AE。
- `body.p988` 与 `body.p1023` 作为必要只读上下文补入：筛选发现的既存情况及知情同意后至首次给药前事件按病史/伴随疾病记录，不作为入排门槛，不给 `p1051-p1053` 增加额外条件。
- 模型外准备：12 owned / 19 attached / 31 total，`claims_complete=false`；专项 42、Phase 闭包 410、方案与 Agent 1198、治理工具 30 项测试全部通过。
- 正式状态仍为 1848 个结构单元、1245 个语义目标、131 个包；剩余 123 包。下一安全动作是 Package 85 `body.p1055-p1066`。

## 2026-08-30 Phase 5.8d Package 85 严重肝损伤与肝功能异常 SAE 边界验收

- D001 II 冻结计划第 85 包 `body.p1055-p1066` 已完成模型外来源闭包；12 个拥有来源不产生预筛、筛选或基线入排候选。
- 父级修正了 `p1059` 的结构错误：不能把 `p1061-p1066` 脱离 `p1060/p1063` 人群前提扁平化为任一即触发；必须保持“人群前提 AND 对应子分支 OR”的两组结构。
- 基线人群的 `AST/ALT和总胆红素` 关系仅保留方案原文，不擅自形式化为任一或全部异常。黄疸病因限定、诊断优先回退、24 小时获知时钟、较小者与总胆红素增量阈值均已固定。
- 模型外准备为 `12 owned / 11 attached / 23 total / prompt 38233`；专项 39、Phase 闭包 449、方案与 Agent 1198、治理工具 30 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，剩余 122 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE85_HEPATIC_INJURY_SAE_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 86 `body.p1067-p1073`。

## 2026-08-30 Phase 5.8d Package 86 DILI 评估、调查及潜在/确诊边界验收

- D001 II 冻结计划第 86 包 `body.p1067-p1073` 已完成模型外来源闭包；7 个拥有来源不产生预筛、筛选或基线入排候选。
- `p1072` 的“上述两个标准”没有唯一两条来源绑定。系统完整携带 `p1060-p1066` 的两类基线人群和分支结构作为只读语境，但不得擅自选两条、不得将五个分支扁平化；无法唯一闭合时保留“需要核对”。
- 48 小时返院评估、24 小时申办者报告、调查项目必做/按需层次、GGT 调查职责及潜在转确诊条件均已分别固定，不能相互替代。
- 模型外准备为 `7 owned / 12 attached / 19 total / prompt 36744`；专项 42、Phase 闭包 491、方案与 Agent 1198、治理工具 30 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，剩余 121 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE86_DILI_EVALUATION_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 87 `body.p1074-p1083`。

## 2026-08-30 Phase 5.8d Package 87 死亡、药物过量与给药错误记录边界验收

- D001 II 当前冻结计划第 87 包 `body.p1074-p1083` 已完成模型外来源闭包；四个结构单元和六个治疗后记录/报告语义均不产生预筛、筛选或基线入排候选。
- 死亡保持“结果而非独立事件”、通常一项、不明死因替换及猝死限定；所有死亡在 AE 收集期内均记录并立即报告，与研究药物关系无关。
- 药物过量固定为意外或故意使用 CMS-D001 片且用量严格高于指定研究剂量；等于不满足，不能追加伤害/毒性等必要条件或泛化对象。漏用/未按计划使用不属于给药错误。
- 任何过量或给药错误进入给药表，相关 AE 另记 AE 页，标签本身不是 AE；`p1080` 功能性短句与 `p1083` 后续章节标题保持不同层级。
- 模型外准备 `10/9/19`、提示 `36076`；专项 44、Phase 闭包 535、方案与 Agent 1198、当前治理工具 16 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，剩余 120 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE87_DEATH_OVERDOSE_MEDICATION_ERROR_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 88 `body.p1084-p1086`。

## 2026-08-30 Phase 5.8d Package 88 不良事件严重程度评估边界验收

- D001 II 当前冻结计划第 88 包 `body.p1084-p1086` 已完成模型外来源闭包；两个结构标题与一个治疗后严重程度评估方法均不产生预筛、筛选或基线入排候选。
- CTCAE 保持版本 6.0 和“可参考”的允许性强度；未收录事件只能先采用方案具体定义，方案没有定义时才回退表 8 通用准则。
- 第 89 包表 8 完整只读进入。父级发现并修正 SAE 来源错配：实际危及生命定义是 `p999`，`p1000` 是永久或严重残疾或功能丧失标准，二者不能互换。
- 严重程度等级不机械等同 SAE 严重性。三个拥有来源与十一个只读附加来源均已纳入零候选门禁。
- 模型外准备 `3/11/14`、提示 `34957`；专项 41、相邻 85、Phase 闭包 576、方案与 Agent 1198、当前治理工具 16 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，剩余 119 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE88_AE_SEVERITY_ASSESSMENT_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 89 `body.t13.r0-r5`。

## 2026-08-30 Phase 5.8d Package 89 表 8 不良事件严重程度分级边界验收

- D001 II 当前冻结计划第 89 包 `body.t13.r0-r5` 已完成模型外来源闭包；表头仅作结构，五个等级行保持治疗后严重程度分级职责，不产生预筛、筛选或基线入排候选。
- 父级纠正源结构解释：`r4/r5` 的 `c1` 类型单元格为空，仅 `c0` 分级与 `c2` 定义有值，不能解释为类型与定义列合并，也不能虚构类型。
- 各等级定义内分号分支保持 OR；3 级“但不会立即危及生命”仅修饰第一分支，“并未卧床不起”仅修饰自理性活动受限分支。
- 表 8 等级不机械等同 SAE 严重性；第 88 包 CTCAE 6.0、“可参考”和方案定义优先回退层级均不可被本包反向改写。
- 模型外准备 `6/9/15`、提示 `35538`；专项 45、相邻 86、Phase 闭包 621、方案与 Agent 1198、当前治理工具 16 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，剩余 118 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE89_TABLE8_SEVERITY_GRADING_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 90 `body.p1087-p1097`。

## 2026-08-30 Phase 5.8d Package 90 不良事件因果关系判断边界验收

- 第 90 包 `body.p1087-p1097` 已完成模型外来源闭包；第 91 包表 9 只读进入，不改变所有权。
- `p1095`“表7”与紧接的“表9”是原始方案内部不一致，系统保留原文并标记需要核对，不静默更正。
- 五要点仅用于研究者综合评价；统计相关仅前三类；SAE 双方分歧时任一方判断相关即进入报告范围，不能升级为最终确认相关。
- 攻击审阅暴露短语探针可被同义改写绕过；父级以来源身份零候选门禁补充真实运行回归，没有扩充项目特异共享关键词。
- 模型外准备 `11/8/19`、提示 `39306`；专项 46、相邻 91、Phase 667、方案与 Agent 1198、治理 16 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，剩余 117 包，`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE90_AE_CAUSALITY_ASSESSMENT_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 91 `body.t14.r0-r7`。

## 2026-08-30 Phase 5.8d Package 91 表 9 因果关系评价矩阵边界验收

- 第 91 包 `body.t14.r0-r7` 已完成模型外来源闭包；`r0` 仅作结构，`r1-r7` 保持治疗后因果关系评价表职责，19 个拥有/只读来源均由来源身份门禁阻断入排候选。
- 父级核实表格 10 列 8 行及合并结构：`r1.c0` 是空结构单元格，不进入冻结计划成员；五级结论仅位于 `c1/c2/c3/c7/c9`。逐格序列由冻结来源契约校验，不由关键词推断。
- 攻击审阅发现反例测试的恒真分支，已删除并补入空单元格排除回归；`-`、`-/?`、`±`、`++` 的用途与未知状态边界分别固定。
- 模型外准备 `8 owned / 11 attached / 19 total / prompt 39306`；专项 56、相邻 147、Phase 715、方案与 Agent 1198、治理 16 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，剩余 116 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE91_TABLE9_CAUSALITY_MATRIX_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 92 `body.p1098-p1101`。

## 2026-08-30 Phase 5.8d Package 92 不良事件预期性与报告章节入口边界验收

- 第 92 包 `body.p1098-p1101` 已完成模型外来源闭包；三个标题仅作结构，`p1099` 只保留参见 CMS-D001 片《研究者手册》评价预期性的关系，六个拥有/只读来源均不形成入排候选。
- 方案句子没有提供研究者手册版本、具体风险或个例结论。系统不得默认最新版本、凭常识判定预期/非预期，或将缺少手册正文改成确定结论。
- 第 80 包 `p1018/p1019` 只读进入，分别保持 SUSAR 可疑+非预期+严重三维合取及《研究者手册》主要参考地位；已知性、因果关系、严重性和预期性不互相替代。
- `p1100/p1101` 不生成具体报告义务；第 93 包应报告事件、24 小时时限和新信息随访未进入提示。
- 模型外准备 `4 owned / 2 attached / 6 total / prompt 29681`；专项 45、相邻 192、Phase 721、方案与 Agent 1198、当前治理测试 2 项通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，按当前逐包闭包记录剩余 115 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE92_AE_EXPECTEDNESS_REPORT_HEADING_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 93 `body.p1102-p1112`。

## 2026-08-30 Phase 5.8d Package 93 应报告事件与新重要信息随访边界验收

- 第 93 包 `body.p1102-p1112` 已完成模型外来源闭包；`p1102` 仅作结构，`p1103-p1112` 保持治疗后安全性报告职责，11 个来源均不形成入排候选。
- 首次事件报告与新重要信息随访保持两项不同义务：前者从研究者获知死亡、SAE 或妊娠事件计时，后者从获知这些事件的新重要信息计时；“立即”和 24 小时上限同时保留。
- 死亡、SAE、妊娠保持三类并列对象，妊娠不附加 AE、SAE、严重性或药物相关前提；24 小时要求不泛化到全部 AE、TEAE、实验室异常或常规安全资料。
- 五类新重要信息均保留，事件结果变化明确包括恢复；第 94 包表单、书面途径、联系人、伦理/监管、治疗、死亡资料及附录 7 内容未进入提示。
- 模型外准备 `11 owned / 0 attached / 11 total / prompt 31972`；专项 49、相邻 241、Phase 770、方案与 Agent 1198、当前治理 2 项测试通过，执行审计无警告或错误。
- 正式状态仍为 `1848/1245/131`，按当前逐包闭包记录剩余 114 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE93_AE_REPORTABLE_EVENTS_FOLLOWUP_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 94 `body.p1113-p1123`。

## 2026-08-30 Phase 5.8d Package 94 SAE 记录、报告表、死亡资料与途径边界验收

- 第 94 包 `body.p1113-p1123` 已完成模型外来源闭包；五个结构标题和六个治疗后安全性记录/报告语义均不形成入排候选。
- 第 93 包 `body.p1103-p1112` 仅以只读语境保留事件对象、随访对象和不同获知时钟；第 95 包 `body.p1124-p1135` 未进入本包来源或提示。
- 病历与对应事件报告表是并列双重记录；p1117 保留研究期间全部 SAE、与药物关系无关、治疗限定作用域、完整记录、报告表所有使用部分、签名/日期、书面报告和独立 SAE 获知时钟。
- 首次与随访报告保持分离；随访使用新表并标记。死亡资料同时面向申办者和监管机构，尸检/最终医学报告只是示例。附录 7 不提供虚构联系人，变更须所有相关方书面确认后生效。
- 父级删除了反例短语自证测试，改为结构化合同变异测试；来源身份分区才是运行时零候选硬门禁。通用阶段列表仅为回放器脚手架，不构成本包阶段适用性证据。
- 模型外准备 `11 owned / 10 attached / 21 total / prompt 37024`；专项 47、相邻 288、Phase 817、方案与 Agent 1198、当前治理 9 项测试通过，执行审计与 review-gate 通过。
- 正式状态仍为 `1848/1245/131`，剩余 113 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE94_SAE_RECORD_FORM_DEATH_ROUTE_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 95 `body.p1124-p1135`。

## 2026-08-30 Phase 5.8d Package 95 申办者 SUSAR 快速报告边界验收

- 第 95 包 `body.p1124-p1135` 已完成模型外来源闭包；`p1124` 仅作结构，`p1125-p1135` 保持治疗后申办者药物警戒职责，17 个拥有/只读来源均不形成入排候选。
- 第 80 包 SUSAR/预期性定义、第 90 包分歧边界及第 96 包列表后两项只读进入；所有权不转移，第 94 包研究者报告职责和第 97 包随访职责均未吸收。
- 接收方、机构名、SUSAR 三维合取、7/8/15 天时钟、报告区间、研究结束后分流及对象内分歧规则均按原文保留；“一般/不建议”未强化为绝对禁止。
- 独立攻击审阅发现测试把正向与禁止字段拼接后可互相遮蔽。父级改为权威正向字段与禁止反转独立校验，并补齐例外规则单字段最小矛盾回归。
- 模型外准备 `12 owned / 5 attached / 17 total / prompt 35200`；专项 65、相邻 394、Phase 929、方案与 Agent 1198、治理 30 项测试通过；review-gate 与执行审计通过。
- 正式状态仍为 `1848/1245/131`，剩余 112 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE95_SPONSOR_SUSAR_EXPEDITED_REPORTING_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 96 `body.p1136-p1137`，只读回接 `p1133-p1135`，不提前吞并 Package 97 `body.p1138` 起的不良事件随访。

## 2026-08-30 Phase 5.8d Package 96 预期严重不良反应与主要疗效终点报告边界验收

- 第 96 包 `body.p1136-p1137` 已完成模型外来源闭包；第 95 包列表前段和第 80 包预期性定义只读进入，第 97 包随访内容未被吸收，七个来源均不形成入排候选。
- `p1136` 保持严重 AND 属预期及“一般不作为快速报告内容”的非绝对强度；`p1137` 保持主要疗效终点条件、“不建议”、申请人、个例安全性报告形式和国家药品审评机构，不允许反向推出其他 SAE 必报。
- 独立攻击审阅暴露逐短语测试仍可被同义改写绕过。最终检测转为净化正向字段上的组合关系模式，区分条件扩大、预期性与不严重/非严重错误等同，并以禁止语境控制证明不会误报。
- 模型外准备 `2 owned / 5 attached / 7 total / prompt 30141`；专项 99、相邻 493、Phase 1028、方案与 Agent 1198、治理 137（2 skipped，16 subtests）项通过；review-gate 与执行审计通过。
- 正式状态仍为 `1848/1245/131`，剩余 111 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE96_EXPECTED_SERIOUS_PRIMARY_ENDPOINT_REPORTING_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 97 `body.p1138-p1149`，保持治疗后随访层次，不提前吞并 Package 98 `body.p1150-p1157`。

## 2026-08-30 Phase 5.8d Package 97 不良事件随访与结果状态边界

- 第 97 包 `body.p1138-p1149` 已完成模型外来源闭包；第 98 包 `p1150-p1156` 只读进入，`p1157` 和第 99 包未进入，19 个来源均不形成入排候选。
- 保留积极处理与禁用医疗措施退出的不同层次，锁定退出路径合取、四类随访终点析取、相关事件尽力随访、分条件资料收集和六类结果状态名称。
- 独立攻击审阅暴露正反字段遮蔽、同义关系绕过、尽力绝对化和无句末标点的正确否定误报。最终使用净化正向字段和关系词族，并以独立正向子句不被否定语境吞并的成对回归验证。
- 模型外准备 `12 owned / 7 attached / 19 total / prompt 35619`；专项 85、相邻 578、Phase 1113、方案与 Agent 1198、治理 137（2 skipped，16 subtests）项通过；review-gate 与执行审计通过。
- 正式状态仍为 `1848/1245/131`，剩余 110 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE97_AE_FOLLOWUP_OUTCOME_STATUS_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 98 `body.p1150-p1157`，保留六类结果定义与结束时间规则，不提前吸收 Package 99 妊娠职责。

## 2026-08-30 Phase 5.8d Package 98 不良事件结果定义与结束时间边界

- 第 98 包 `body.p1150-p1157` 已完成模型外来源闭包；第 97 包 `p1142/p1144/p1148/p1149` 只读进入，第 99 包妊娠报告与随访未进入，12 个来源均不形成入排候选。
- 痊愈不要求恢复正常范围；好转与持续保持互斥；恢复期症状不自动成为后遗症；多个并存 AE 只有实际致死事件可选择致死结果。
- 结束时间保留解决、恢复至基线、稳定且不能进一步恢复三个备选路径；资料不足时保留年月而不虚构日。退出时间、事件结束时间与死亡时间保持不同对象。
- 死亡时非直接死因且仍持续的事件结束时间留空、状态持续；直接或主要死因事件才以死亡时间结束。
- 独立攻击证明开放式中文短语检测不适合作为冻结配置验收。最终采用独立正向语义摘要、整配置/冻结计划/结构块指纹和逐字来源核对，40 个新增同义反例与八个逐来源字段变异均被阻断。
- 模型外准备 `8 owned / 4 attached / 12 total / prompt 32452`；专项 55、相邻 592、Phase 1168、方案与 Agent 1198、治理 137（2 skipped，16 subtests）项通过；review-gate 与执行审计通过。
- 正式状态仍为 `1848/1245/131`，剩余 109 包，`claims_complete=false`。未调用临床语义模型，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE98_AE_OUTCOME_DEFINITION_END_TIME_BOUNDARY_ACCEPTED.md`。下一安全动作是 Package 99 `body.p1158-p1167`，保持妊娠事件报告、处置和随访分流，不提前进入 Package 100 统计学章节。

## 2026-08-30 Phase 5.8d 第 99 包妊娠报告与随访边界验收

- 第 99 包 `body.p1158-p1167` 已完成模型外来源闭包；第 77/78 包 AE/SAE 定义只读进入，第 98 包结果定义和第 100 包统计学章节未进入。
- 临床父级复核保持双对象、末次给药后 3 个月、疑似妊娠、确认后 24 小时报告、角色差异停药、AE/SAE 条件分流、参与者/伴侣决策、退出后随访、较晚者终点及胎儿评估条件/例外。
- 初轮测试存在动态摘要、对象/先天异常例外缺少独立变异及重复攻击样本；已在原执行会话修订为字面量摘要、四个命名变异和 48 条唯一攻击，并由原独立审阅会话复攻通过。
- 验证：专项 60、Package 90-99 相邻 607、Phase 闭包 1228、方案与 Agent 1198、治理 137（2 skipped，16 subtests）项通过；JSON、Hermes review-gate 与执行审计通过。
- 当前仍为 `1848` 个结构单元、`1245` 个语义目标、`131` 个包，剩余 `108` 包；`claims_complete=false`，未运行临床语义模型或下游受试者流程。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE99_PREGNANCY_REPORTING_FOLLOWUP_BOUNDARY_ACCEPTED.md`。下一安全动作是第 100 包 `body.p1168-p1170`、`body.p1173-p1177`、`body.p1179`。

## 2026-08-30 Phase 5.8d 第100包统计假设期别边界验收

- 通用阶段语境已修正：明确单一期别且有类型的前向引导语只在最近结构标题内传播；同级/祖先标题关闭，普通叙述、混合期别和交叉引用不扩散。
- 新不可变候选 slice61cm 保持1848个结构单元和131个包，语义目标由1245降至1240；仅 `p1173-p1177` 从Ⅱ期待判定目标移除并改为Ⅲ期，Package 1-99所有权不变。
- 规划器上下文已收敛为45个可解释新增、0个删除：深层临床小节/表格引导36个、期别分支关闭标题9个；无全局广播或附录整章吸收。
- 第100包只拥有 `p1168-p1170`，只读附加 `p1171-p1179`。`p1179` 仍归第101包，模型外提示不包含第99包妊娠流程或第101/102包正文。
- `p1169` 是Ⅱ/Ⅲ期SAP在各期数据库锁定前获批定稿的统计文件管理背景，不是受试者随机、给药、入组或证据义务。
- 验证：模型外准备 `3/9/12`，专项8项、协议层加专项1167项及独立同会话攻击通过；`claims_complete=false`，未调用临床模型或发布控制点。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE100_STATISTICAL_HYPOTHESIS_PHASE_BOUNDARY_ACCEPTED.md`。下一安全动作是第101包 `body.p1179`、`body.p1186-p1196`。

## 2026-08-30 Phase 5.8d 第101包分析集定义边界验收

- 第101包拥有 `body.p1179`、`body.p1186-p1196` 十二个来源，只读附加 `body.p1180-p1185` 六个样本量语境来源；18个来源按 `p1179-p1196` 连续顺序闭合，全部零候选、零工作流绑定。
- Ⅱ期剂量探索、1:1:1和约120例以及Ⅲ期样本量分支均保持研究设计背景，不形成单例受试者入排门槛，Ⅱ/Ⅲ期信息不互相污染。
- ITT、SS、PKCS、PDS保持随机后统计分析集定义；随机、给药、给药后评价及浓度数据不得反向解释为筛选、基线、随机或D1给药前资格条件。
- `p1188` 的“基线”是ITT分析内容域；`p1192` 的“剔除”是统计分析集剔除，并保持盲态数据审核后、数据库锁库和揭盲前时序，均不产生入排或访视义务。
- 第100包和第102包来源未进入提示，`p1198-p1199` 未被宽泛语境吸收。专项8项、独立同会话复核和Hermes正式执行审计通过。
- 两次不合规复核分别因提示预检失败和角色身份不匹配被隔离，不作为验收证据；合规第三次复核才进入正式证据链。
- 正式状态仍为1848个结构单元、1240个语义目标、131个包，剩余106包；`claims_complete=false`，未运行临床语义模型或下游受试者流程。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE101_ANALYSIS_SET_BOUNDARY_ACCEPTED.md`。下一安全动作是第102包 `body.p1197`、`body.p1200-p1205`，只读语境限于 `body.p1198-p1199`、`body.p1206-p1209`，保持统计域与入排域分离。

## 2026-08-30 Phase 5.8d 第102包入组、基线与统计分析语义边界验收

- 第102包拥有 `body.p1197`、`body.p1200-p1205` 七个来源，只读附加 `body.p1198-p1199`、`body.p1206-p1209` 六个语境来源；13个来源按 `p1197-p1209` 闭合并全部零候选。
- 参与者入组/完成和分析集纳入/剔除是事后统计；ITT 基线是描述性统计内容域；WHO Drug/MedDRA 是编码汇总；PASI-75、CMH和缺失值处理是随机后统计方法，均不得倒置为单例入排或证据义务。
- `p1199` 保持Ⅲ期只读语境，局部 `phase_scopes` 优先于顶层选定期别元数据。
- 执行中发现原续作假设与冻结计划不一致：`p1210-p1223` 未被任何包拥有，第103包真实拥有起点是 `p1224`。已修正执行合同和回归，未改写不可变计划。
- 模型外准备 `7 owned / 6 attached / 13 total`；专项8项、第100-102包相邻24项测试通过；Hermes review-gate 与正式执行审计通过。
- 当前仍为1848个结构单元、1240个语义目标、131个包，剩余105包；`claims_complete=false`，未运行临床语义模型或下游受试者流程。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE102_ENROLLMENT_BASELINE_STATISTICAL_BOUNDARY_ACCEPTED.md`。下一安全动作是第103包 `body.p1224`、`body.p1226-p1235`；`body.p1225` 仅作Ⅲ期对照，`body.p1210-p1223` 仅作未拥有统计语境。

## 2026-08-30 Phase 5.8d Package 103 安全性、PK、PopPK与暴露-效应统计边界验收

- 第103包冻结为 `11 owned / 1 attached / 12 total`：拥有 `body.p1224`、`body.p1226-p1235`，只读附加Ⅲ期 `body.p1225`；全部零候选、零规则/程序/动作/访视/预筛选绑定。
- 安全性检查、血妊娠结果和合并治疗均保持治疗后统计列表语义；PKCS、采样时间、血药浓度、PopPK/NONMEM 及条件性暴露-效应探索保持给药后统计/模型分析语义，不反向产生单例入排义务。
- 父级发现并修正初版配置的真实所有权错误：`body.p1237#atom-100-160` 不属于第104包，而是无所有权的只读Ⅱ期期中分析上下文；测试现直接核对配置和冻结 owner map。
- 专项8项、相邻第101-103包24项通过；四路执行使用 `openai-codex/gpt-5.6-luna:max` 主路由，无 fallback；review-gate 和正式执行审计通过。
- 正式计数保持1848个结构单元、1240个语义目标、131个包，剩余104包；`claims_complete=false`，未进入模型发布、受试者、OCR、Patient Profile 或浏览器阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE103_SAFETY_PK_EXPOSURE_STATISTICAL_BOUNDARY_ACCEPTED.md`。下一安全动作是第104包期中分析边界，先核对四个拥有来源与无所有权只读原子的完整条件逻辑。

## 2026-08-30 Phase 5.8d Package 104 期中分析研究治理边界验收

- 第104包冻结为 `4 owned / 2 attached / 6 total`：拥有四个期中分析来源，只读附加研究设计段和无所有权的Ⅱ期50%参与者完成第12周后启动分析原子。
- 50%总体触发、独立统计分析、IDMC建议、申办方Ⅲ期继续/剂量决策和独立期中SAP均保持研究治理语义，不产生单例筛选、基线、随机、D1前、访视或资格控制。
- 初版三个候选会被现有候选 Schema 强制绑定受试者审核节点。父级改为六来源全量零候选，并增加按来源身份拒绝六类无关键词同义改写的真实水合门禁回归。
- 原始覆盖继续保留 `mixed/unknown/phase_ii` 期别范围；共享父级 `body.p1237` 来源跨度不替代原子级结构身份。
- 专项 `11 passed, 5 warnings`、相邻第102-104包 `27 passed, 5 warnings`；四路执行使用 `openai-codex/gpt-5.6-luna:max` 主路由，无 fallback；review-gate 和正式执行审计通过。
- 正式计数保持1848个结构单元、1240个语义目标、131个包，剩余103包；`claims_complete=false`，未进入模型发布、受试者、OCR、Patient Profile 或浏览器阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE104_INTERIM_ANALYSIS_GOVERNANCE_BOUNDARY_ACCEPTED.md`。下一安全动作是第105包冻结来源和语义边界核对。

## 2026-08-30 Phase 5.8d Package 105 数据质量与源数据/源文件边界验收

- 第105包仅拥有 `body.p1238-p1247`，不附加来源；37个冻结语境单元全部保持只读并排除在提示之外。
- EDC、eCRF、数据质疑、培训、签名、源数据定义、核证副本、审核跟踪、保存与直接访问均按研究执行或证据治理处理，不生成单例入排候选、动作或阶段绑定。
- p1245 不再因“采集的数据”触发 `collect_data`；共享回放对明确非入组/支持性处置来源抑制自动受试者动作。
- 共享所有权解析增加新配置显式包身份合同，阻断相邻包、无主语境和覆盖清单伪装；旧版只读配置不被静默重写。
- 专项16项、相邻及共享回放74项、扩展82项测试通过；四路主路由无 fallback，review-gate 与执行审计通过。
- 正式计数保持1848个结构单元、1240个语义目标、131个包，剩余102包；`claims_complete=false`，未进入模型发布、受试者、OCR、Patient Profile 或浏览器阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE105_DATA_QUALITY_SOURCE_DOCUMENT_BOUNDARY_ACCEPTED.md`。下一安全动作是第106包 `body.p1248-p1250` 的记录保存治理边界核对。

## 2026-08-30 Phase 5.8d Package 106 记录保存治理边界验收

- 第106包拥有 `body.p1248-p1250`，只读附加第105包 `body.p1247` 以闭合第9.4节引用；第107包与37个冻结语境单元均未进入提示。
- 两个至少5年的保存期限保持独立并取较晚者；未知锚点不能被已知且更早的锚点替代。
- 研究中心/申办方的保存责任与申办方/研究者/机构的保存地点和条件确认责任保持分离；文件转移、保管人变更和销毁均须申办方书面许可。
- 上述内容属于研究记录与证据治理，不形成单例受试者入排条件、资料缺失、阶段失败或排除结论。
- 独立攻击发现 p1247 摘要和直接字段配对测试不足；父级按原文修正并补强专项回归，未修改无必要的共享解析器。
- 专项27项、相邻第103-106包及共享回放101项通过；四路主路由无 fallback，review-gate 与执行审计通过。
- 正式计数保持1848个结构单元、1240个语义目标、131个包，剩余101包；`claims_complete=false`，未进入模型发布、受试者、OCR、Patient Profile 或浏览器阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE106_RECORD_RETENTION_GOVERNANCE_BOUNDARY_ACCEPTED.md`。下一安全动作是第107包 `body.p1251-p1259`，逐项判断知情同意治理与参与研究前控制，不预设零候选。

## 2026-08-30 Phase 5.8d Package 107 伦理与知情同意边界

- Package107仅拥有 `body.p1251-p1259`，不附加来源；41项context全部只读，其中30项全局无owner、11项由其他包拥有。
- 研究伦理/法规、ICF文件批准和ICF模板内容保持研究治理，不形成单例资格。
- p1257/p1259中的参加研究前过程动作进入筛选期补充控制：口头及书面告知、条件性见证、可理解解释、充分考虑时间、双方签名日期和代签关系。
- 既有 `procedure:d001-icf-screening` 覆盖通用签署；第107包只发布未覆盖动作增量。持续告知、双方留存和重要新资料后的伦理批准/再次同意保留为研究进行期治理。
- 父级拒绝零候选初稿并新增通用动作识别；独立验收误报在同会话撤销。最终回归 `144 passed, 5 warnings`，无fallback。
- 正式计数仍为1848/1240/131，剩余100包；`claims_complete=false`，未调用临床语义模型或下游受试者流程。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE107_INFORMED_CONSENT_GOVERNANCE_CONTROL_BOUNDARY_ACCEPTED.md`。下一安全动作是Package108，从 `body.p1260` 的冻结拥有来源和完整原文重新开始。

## 2026-08-30 Phase 5.8d 第108包伦理审查与保密治理边界

- 当前权威仍是slice61cm不可变候选：1848个结构单元、1240个语义目标、131个包；第108包验收后剩余99包，`claims_complete=false`。
- Package108仅拥有`body.p1260-p1269`；37项语境均只读，其中26项全局无owner、11项属于其他包，第107包止于p1259，第109包从p1270开始。
- IRB/EC启动审批、招募材料审批、持续伦理报告、SAE/安全通信、保密、信息披露授权、编码访问、私人医生披露、探索性结果不返还和监管检查均保持研究、文件或隐私治理，不生成单例入排控制。
- “研究启动前”没有被误解为受试者筛选前；“签署的知情同意书允许”没有被误解为新的知情签署义务。十项来源逐项复核后为零候选。
- 模型外准备`10/0/10`；专项30项、Package103-108及共享语义174项、独立39项不变量通过；四路`cursor/default`无fallback，执行审计通过。
- 未调用临床语义模型、未发布、未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE108_IRB_CONFIDENTIALITY_GOVERNANCE_BOUNDARY_ACCEPTED.md`。下一安全动作是第109包`pap-2101c87c43a5499476169b81`拥有的`body.p1270-p1280`，先从当前冻结计划和源文重新核对，不吸收第108/110包，不预设候选数。

## 2026-08-30 Phase 5.8d 第109包研究文件、方案偏离、监查与管理边界

- 当前权威仍是slice61cm不可变候选：1848个结构单元、1240个语义目标、131个包；第109包验收后剩余98包，`claims_complete=false`。
- Package109仅拥有`body.p1270-p1280`；37项语境均只读，其中26项全局无owner、11项属于Package45/46/47/48/50/75。
- 研究文件/档案、偏离记录、严重偏离评估后在研退出、现场监查和管理基础设施保持研究执行/记录/监查/管理治理，不生成单例入排控制。
- p1275泛化遵从、p1276退出倒置、p1280 IWRS/样本/EDC候选化三类高风险路径均被逐项语义和确定性门禁阻断。
- 模型外准备`11/0/11`；专项31项、Package103-109及共享语义205项通过；四路`cursor/default`无fallback，执行审计通过。
- 未调用临床语义模型、未发布、未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE109_STUDY_RECORDS_DEVIATION_MONITORING_MANAGEMENT_BOUNDARY_ACCEPTED.md`。下一安全动作是Package110 `pap-7358ad349433c3c08aacc5f1`拥有的`body.p1281-p1290`，从当前冻结计划和源文重新核对，不吸收第109/111包，不预设候选数。

## 2026-08-30 Phase 5.8d 第110包数据发布与商业秘密治理边界

- 当前权威仍是slice61cm不可变候选：1848个结构单元、1240个语义目标、131个包；第110包验收后剩余97包，`claims_complete=false`。
- Package110仅拥有`body.p1281-p1290`；37项语境均只读，其中26项全局无owner、11项属于Package45/46/47/48/50/75。
- 临床研究报告、数据所有权与披露、结果公开、完整研究发表偏好、最终报告前发表限制、稿件审核、作者安排、发表费用和专利/保密合作均保持申办者/研究者发表或知识产权治理，不生成单例入排控制。
- “发表前”没有被偷换为“参加研究前”；研究者和中心的义务没有被偷换为受试者资格。Package109的IWRS筛查/随机文字和Package111方案修订均未吸入。
- 模型外准备`10/0/10`；专项34项、Package103-110及共享语义239项通过；四路`cursor/default`无fallback，执行审计通过。
- 未调用临床语义模型、未发布、未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE110_DATA_PUBLICATION_COMMERCIAL_SECRET_GOVERNANCE_BOUNDARY_ACCEPTED.md`。下一安全动作是Package111 `pap-214ce50fd89fb1998521c4c3`拥有的`body.p1291`、`body.p1292`和`body.t15.r0-r1`，从当前冻结计划和源文重新核对，不吸收第110/112包，不预设候选数。

## 2026-08-30 Phase 5.8d 第111包方案修订权威与版本表边界

- 当前权威仍是slice61cm不可变候选：1848个结构单元、1240个语义目标、131个包；第111包验收后剩余96包，`claims_complete=false`。
- Package111只拥有`body.p1291`、`body.p1292`、`body.t15.r0-r1`；37项语境均只读，其中26项全局无owner、11项属于Package45/46/47/48/50/75。
- 必要变更以方案修订、申办者/主要研究者签字和伦理审批或备案建立权威链，保持项目级治理语义，不生成受试者入排控制。
- V1.0行只证明初始版本和2025年12月10日；`NA/NA`及未填写的版本表槽位不代表存在既往修订。表容器、24个空白单元和两个空白段落已精确排除。
- 模型外准备`4/0/4`；专项29项、Package103-111及共享语义268项通过；四路`cursor/default`无fallback。
- 未调用临床语义模型，未发布，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE111_PROTOCOL_AMENDMENT_AUTHORITY_VERSION_TABLE_BOUNDARY_ACCEPTED.md`。下一安全动作是Package112 `pap-fa6b2b871b90b62bbfe81775`拥有的`body.p1295-p1306`，从冻结计划和原文重新核对，不吸收Package111，不预设候选数。

## 2026-08-30 Phase 5.8d 第112包参考文献与方案正文权威边界

- 当前权威仍是slice61cm不可变候选：1848个结构单元、1240个语义目标、131个包；第112包验收后剩余95包，`claims_complete=false`。
- Package112仅拥有 `body.p1295-p1306`。`p1295` 仅为结构标题，`p1296-p1306` 是参考文献题录，非方案执行条款；方案正文仍是执行权威。
- 参考文献题名中的PASI/BSA/PGA、handprint、1%、JAK/STAT、TYK2、Deucravacitinib和诊疗指南不得反向生成受试者阈值、算法、诊断标准或执行程序。
- 38项context均只读，其中26项全局无owner、12项属其他包；Package111/113与 `p1293/p1294/p1309` 无主空白分隔已精确隔离。
- 验证：专项29项、Package103-112及共享语义297项、slice59n共享39项通过；模型外准备 `12/0/12`。
- 执行包首轮缺失Source of Truth/写入授权是编排缺陷；父级修正后沿用原worker会话完成，四路 `cursor/default` 无fallback。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE112_REFERENCE_LIST_EVIDENCE_AUTHORITY_BOUNDARY_ACCEPTED.md`。下一安全动作是审查Package113 `pap-d042355fa4845796808fa256` / `body.p1307-p1308`，不回吸Package112。

## 2026-08-30 Phase 5.8d 第113包参考文献尾部与方案正文权威边界

- 当前权威仍是slice61cm不可变候选：1848个结构单元、1240个语义目标、131个包；第113包验收后剩余94包，`claims_complete=false`。
- Package113仅拥有 `body.p1307-p1308`：DLQI论文题录和《药品注册管理办法》题录，均属非入排执行。
- 真实DLQI执行内容位于Package74 p826-p827、Package125 p1386和Package128 p1417-p1419；题录不得反向生成评分范围、临床重要性切点、问卷细则或受试者资格。
- 来源身份门禁已用似是而非的DLQI/注册管理输出攻击验证；38项context、Package112、无主p1309及Package114均未进入本包。
- 模型外准备 `2/0/2`；专项29项、Package103-113组合279项、slice59n共享39项通过；四路 `cursor/default` 无fallback，执行审计通过。
- 未调用临床语义模型，未发布，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE113_REFERENCE_TAIL_EVIDENCE_AUTHORITY_BOUNDARY_ACCEPTED.md`。下一安全动作是Package114 `pap-cd76207b0f3d157c2eaa66d6` / `body.p1310-p1321`，先逐项核对生育能力定义、手术史、绝经后定义和核查动作，不预设候选数。

## 2026-08-30 Phase 5.8d Package 114 生育能力定义与证据边界

- 当前权威仍是slice61cm不可变候选：1848个结构单元、1240个语义目标、131个包；第114包验收后剩余93包，`claims_complete=false`。
- Package114拥有 `body.p1310-p1321`；Package115拥有的p1322仅以只读附件闭合绝经定义，p1323-p1333避孕条款未进入本包。
- p1313-p1321不是独立新控制点，但它们定义既有IN-06和妊娠/FSH流程的适用人群、OR分支、双侧手术条件和可接受确认方式，均保留为 `supporting_or_supplement`。
- 两层父子OR和病历核查/医学检查/病史询问三选一均由确定性正向及攻击回归保护；不得压平为AND或丢失“双侧”。
- 模型外准备 `12/1/13`；专项29项、Package103-114组合300项、slice59n共享39项通过；四路执行、review-gate和正式执行审计通过。
- 当前处置合同不能在支持性来源上直接挂既有规则标识；本包以known targets保留关系且不伪造重复候选，后续仅按真实需要评估共享合同扩展。
- 未调用临床语义模型、未发布、未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE114_FERTILITY_DEFINITION_EVIDENCE_BOUNDARY_ACCEPTED.md`。下一安全动作是Package115 `pap-9fb70d121e089bc533c21255` / `body.p1322-p1333`，恢复完整绝经与避孕条款逻辑并核对既有控制覆盖，不预设候选数。

## 2026-08-30 Phase 5.8d Package 115 避孕方法与时间锚点边界

- Package115严格拥有`body.p1322-p1333`；p1321/p1334仅作冻结语境，未附加、处置或发布。
- p1323仅作结构；其余十一项明确为既有IN-06、妊娠/FSH和slice60m控制的`supporting_or_supplement`，全部禁止重复候选。
- 筛选血妊娠阴性与ICF日期起点保持分离；高效方法、双侧输卵管术式和避孕套选择保持OR；建议性妊娠检查未升级为强制。
- 模型外准备`12/0/12`；父级专项46、Package103-115组合346、slice59n共享39及独立扩展共享1515项通过；执行审计通过。
- 过拟合审计发现旧版`app/pipeline/reviewer.py`仍含D001/SAR/FEV1/IN-02/EX-11/IL靶点和历史文案正则。新架构不得继续扩展该路线；D001只作回归样本。
- 后续正式方案解构改由独立harness/LLM从用户直接上传的DOCX/PDF完成：全方案结构化读取、高召回定位相关章节、仅对潜在入排控制点及必要上下文深度解构，再由通用合同验证来源、逻辑、时间、模态和去重。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260830_PACKAGE115_CONTRACEPTION_METHOD_AUTHORITY_BOUNDARY_ACCEPTED.md`。下一安全动作是方案解构通用化与过拟合隔离切片，在该机制通过前不继续人工逐段闭合Package116。

## 2026-08-31 通用两阶段方案控制点候选链

- 新架构已把“完整方案结构发现”和“候选控制点深度解构”分开：用户上传的 DOCX/PDF 只做一次结构化读取，后续均复用冻结快照；全清单只进入一次高召回发现，只有候选和不确定项进入深度分析。
- 发现结果严格限制为 `candidate/context_only/non_control/uncertain`，并保留理由与必要上下文；全文闭包由确定性门禁完成，不以关键词穷举替代模型理解。
- 持久化执行、动态深度步骤、失败分类、进程恢复、幂等 API 已完成；“需要核对”不会触发新的模型会话盲重试。
- 当前产物是水合候选控制点包，不是正式控制点目录；候选转正式规则、真实模型运行、D001/SAR 异构回放及前端展示均未完成，`claims_complete=false`。
- 验证：聚焦102项、全仓3295项通过，`py_compile`、`git diff --check` 和正式执行审计通过。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_PROTOCOL_CONTROL_CANDIDATE_CHAIN_ACCEPTED.md`。下一步先做词汇中立的真实独立模型冒烟测试，再以 D001 与 MG-K10-SAR 作为只读异构语料使用同一 harness；不得按任一项目修改共享规则。

## 2026-08-31 D001 II期只读异构回放无损暂停

- 词汇中立真实模型冒烟已完成，仍只生成水合候选包，不是正式控制点目录，`claims_complete=false`。
- D001只读回放的来源冻结完成；控制任务`3259ab5f070447c3938ff2de5f45c9cd`共有39个发现批次，0001-0005完成并留有检查点，0006在暂停时中断，其余批次和确定性闭包未开始。
- D001来源暂停时SHA-256为`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`；未形成D001正式目录或临床验收，SAR回放尚未开始。
- D001/SAR继续只作为只读异构验收语料，不得驱动共享规则硬编码。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_D001_READONLY_REPLAY_PAUSED.md`。下一安全动作是从现有SQLite任务检查点恢复，不重新读取方案、不新建重复全量回放。

## 2026-08-31 D001 发现链性能边界无损暂停

- 既有 SQLite 任务恢复入口、失败步骤粒度重试、严格候选包接受门禁和集合语义引用顺序规范化已完成确定性验证；本轮聚焦 `54 passed`。
- D001 控制任务 `3259ab5f070447c3938ff2de5f45c9cd` 已持久化 `discovery_0001-0019`；第20包中断，其他发现包与闭包未完成，`claims_complete=false`。
- 当前固定 48 结构单元产生 39 个串行发现包；本地 27B Quality medium 最近单包约 6.5–9 分钟，该默认路径不满足真实产品时效。
- 后续需同时修正 token/输出预算分包和有限并发，并评估外部 API 主语义路由；不用项目关键词丢弃全清单覆盖。
- 本地 DeepSeek 配置只做了模型目录探测，未调用语义解构。用户后续可提供其他独立 VLM API，恢复后先分离 VLM 原始文档理解与 LLM 控制点语义责任。
- 当前恢复链源码与测试在工作树中仍是未跟踪文件，未提交、未发布；暂停时不清理它们或回放工件。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_D001_DISCOVERY_PERFORMANCE_PAUSED.md`。下一安全动作不是继续第20包，而是先确定新 VLM/LLM 职责、自适应分包、有限并发、模型路由及耗时/费用验收合同。

## 2026-08-31 GLM-5.3-Flash 独立视觉适配与性能合同复核

- 独立视觉模型默认配置为智谱 BigModel `glm-5.3-flash`、推理强度 `high`；它只负责原始页视觉核验和来源定位，不替换 OCR、方案语义解构、方案控制语义分析、事实规范化或确定性判定。
- 共享视觉适配层、原始页输入、来源标识/页码保真、失败关闭和配置隔离已完成；聚焦回归 `110 passed, 5 warnings`。
- 模型目录与鉴权可用，但最小真实图片请求返回 HTTP 429 / provider code `1113`。因此当前只有离线合同，没有已验收的真实视觉能力，也没有宣称各业务 harness 已完成接入。
- 新方案控制任务使用输入令牌和预计输出预算自适应分包；未接入持久化执行器的并发/指标辅助代码已删除。当前同一任务内仍串行执行，真正并发另行设计。
- worker_03 曾误删并重建 `protocol_control_planning.py`；父级已依据既有合同修复回归并通过聚焦测试，但保留事件记录，不清理执行证据。
- D001 旧任务未恢复，仍保持第19包后无损暂停；新配置不得混入旧正式结果。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_GLM53_VISION_ADAPTER_OFFLINE_ACCEPTED_LIVE_BLOCKED.md`。下一安全动作是账户具备额度后先做一页合成图片和一页脱敏真实方案页面冒烟，再显式接入需要查看原始页的 harness；不得整份方案逐页重复识别。

## 2026-08-31 智谱 Coding Plan 独立视觉模型真实连通验收

- 本机 OMP 的真实接入标识为 `zhipu-coding-plan`，端点为 `https://open.bigmodel.cn/api/coding/paas/v4`。此前应用主 `.env` 仍指向公共 `/api/paas/v4`，这是 HTTP 429 / provider code 1113 的直接原因。
- 共享独立视觉适配器现默认 `zhipu-coding-plan/glm-5.3-flash:high`；旧 `bigmodel` 名称仅为配置兼容。它只负责原始页面视觉理解与来源定位，不替换 OCR、方案语义、控制点深析、事实规范化或确定性判定。
- 应用运行时不查询 OMP 数据库；本地启动 `.env` 已从已有 OMP Coding Plan 凭据安全同步，密钥未写入仓库或执行报告。
- 真实合成图片请求通过：`1 passed in 4.73s`。合同、错误分类、来源保真及相邻路由回归为 `44 passed, 1 skipped`；任何鉴权、余额、限流或远端错误都会使显式 live 验收失败。
- 三执行者并发写同一适配器曾造成文件截断；父级已重新打开完整源码、编译、重跑测试并通过治理审计。后续共享文件执行采用单写者，其余角色只读验证。
- 当前只接受共享适配和真实连通，不宣称全部业务 harness 已启用。下一步按页面风险调用：结构化文本页直接复用冻结文本；只有扫描、复杂表格、结构异常或 OCR 低置信度页进入视觉核验，避免整份方案逐页重复处理。
- D001 控制任务 `3259ab5f070447c3938ff2de5f45c9cd` 保持第19个检查点后的无损暂停。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_ZHIPU_CODING_PLAN_VLM_LIVE_ACCEPTED.md`。

## 2026-08-31 选择性页面视觉核验规划验收

- 原生DOCX/PDF文字仍是主路径；独立视觉模型不对整份方案逐页重识别，只处理扫描/纯图、复杂表格或版面、结构异常、OCR低置信等页级风险。
- 规划输入只包含来源身份、页码、提取路线、结构和质量元数据，不使用项目、疾病、药物、量表或条款关键词，避免对D001/SAR过拟合。
- 视觉结果是来源绑定的观察侧车，不覆盖OCR、不生成坐标、不输出入排结论；来源不一致、计划缺图或远端错误均失败关闭。
- 修复聚合模块急加载传输的问题，确定性方案回放冷启动不再加载OpenAI/httpx。
- 验证：聚焦`56 passed, 1 skipped`；扩展`326 passed, 2 skipped`；严格真实视觉`1 passed in 5.50s`。
- 全库`3425 passed, 4 skipped`，另有一个既存D001只读检查点提示哈希漂移。当前合同仍标为v1.5但生成哈希已变，后续须独立版本化处理，不能修改旧检查点掩盖漂移。
- 尚未接入持久化证据处理服务或前端；D001控制任务继续保持第19个检查点后暂停。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_SELECTIVE_VISION_PAGE_TRIAGE_ACCEPTED.md`。下一安全动作是建立不可变视觉观察侧车及证据服务后处理钩子，保持OCR和方案语义链不变。

## 2026-08-31 选择性视觉观察侧车

- 已建立不可变视觉观察合同、0019持久化、来源闭包仓储和显式后处理服务。成功结果按页图/规划/模型/提示/风险理由组成的身份复用，内容冲突拒绝；失败只保留无模型正文的关闭记录。
- 原生文字充分的页不调用视觉模型；需要视觉核验的页延迟加载传输。服务只消费已落盘页产物和OCR质量，不覆盖OCR原文、缓存、租约或早期阶段结论。
- 验证：聚焦`15 passed`；v2存储、证据与服务`1052 passed, 1 skipped`；正式执行审计通过并已归档。
- 当前仍是显式服务入口，尚未挂入证据修订冻结后的正式编排，也没有前端PDF/图片滚动与红框来源定位。下一步先实现独立、幂等、可恢复的修订后编排，再进入用户界面。
- D001控制任务继续保持第19个检查点后无损暂停；旧D001提示哈希漂移维持独立待处理，不在本切片修改。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_SELECTIVE_VISION_OBSERVATION_SIDECAR_ACCEPTED.md`。

## 2026-08-31 选择性视觉冻结后独立编排

- 证据处理修订冻结后只幂等创建独立视觉后处理任务，不在 OCR、风险定位或修订冻结事务中等待远端模型。
- 视觉处理按短事务准备、无事务远端调用和短事务持久化执行；应用注册独立任务执行器，并支持租约恢复、进程中断恢复和重复提交复用。
- 原生文字充分页继续跳过视觉模型；失败仅形成无模型正文的关闭记录，不覆盖 OCR 原文、哈希、缓存或早期审核结论。
- 创建任务前验证处理修订存在，执行前验证规划版本；旧任务与新合同漂移时在模型调用前停止。
- 聚焦 `45 passed`、相邻 `117 passed`、v2 广泛回归 `1337 passed, 1 skipped`；review gate 与正式执行审计通过。
- 尚未完成用户可见的任务状态、人工重试/取消、原始资料红框下钻和真实项目端到端验收。独立视觉模型仍仅用于扫描、复杂表格或版面、结构异常及 OCR 低置信风险页，不对整份方案逐页重复识别。
- D001 控制任务 `3259ab5f070447c3938ff2de5f45c9cd` 继续保持第19个检查点后无损暂停。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260831_SELECTIVE_VISION_POSTFREEZE_ORCHESTRATION_ACCEPTED.md`。

## 2026-09-01 选择性页面视觉核验用户闭环

- 证据工作台现可直接显示页面视觉核验状态、需核验/跳过/观察/关闭页数、失败范围与恢复动作，并支持人工重试和取消。
- 完整修订与基础修订的任务身份已收敛，避免活动证据快照下面板消失或重复任务。
- 视觉模型继续按 OMP `zhipu-coding-plan/glm-5.3-flash` Coding Plan 合同仅处理页级风险，不对整份方案逐页重识别。
- 验证：后端 services + API `610 passed`，前端全量 `525 passed`，Playwright 1080P/2K/4K 相邻回归 `9 passed`，构建、截图审阅和执行治理门禁通过。
- Phase 5 未完成；下一步只做一页新建隔离风险资料的真实端到端验收。D001 任务仍停在第 19 个已完成发现批次后。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_SELECTIVE_VISION_USER_CONTROL_ACCEPTED.md`。

## 2026-09-01 单页选择性视觉真实端到端闭环

- 在全新隔离数据目录中，一页内容中立风险资料已经完成冻结证据修订、幂等入队、真实智谱 Coding Plan `glm-5.3-flash:high` 调用、不可变观察落库和修订级用户投影。
- 真实请求端点为 `https://open.bigmodel.cn/api/coding/paas/v4`；成功观察正文非空，来源、页码、页图哈希、OCR 哈希、模型与提示词身份闭包完整。
- 调用前后 OCR 原文、OCR 哈希和页图字节不变。视觉结果仍是观察侧车，不覆盖 OCR，不直接发布临床事实或入排结论。
- 独立审阅者提出启动后配置可能丢失；经追踪实际调用者，`app.config` 在导入时会读取应用根目录 `.env`，运行状态文件只冻结本地 MTPLX 路由，不需要也不应复制独立 VLM 密钥。
- 验证：真实闭环 `2 passed in 21.31s`；相邻回归 `109 passed, 2 skipped`；执行审阅、路由审计和过程归档完成。
- Phase 5 仍为 `claims_complete=false`。下一步先建立视觉观察进入事实规范化的候选合同，保证只补充风险信息而不改写 OCR，再进入代表受试者逐事件核对。
- D001 任务 `3259ab5f070447c3938ff2de5f45c9cd` 仍在第 19 个已完成发现批次后暂停。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_SELECTIVE_VISION_SINGLE_PAGE_E2E_ACCEPTED.md`。

## 2026-09-01 视觉观察进入事实规范化候选合同

- 视觉观察现可作为来源绑定的补充材料或 OCR 风险提示进入 Evidence Normalizer，但不覆盖 OCR、有效文本或定位器，也不具备直接发布临床事实或入排结论的权限。
- 运行冻结页产物、资料版本、页码、页图、OCR 原文和观察身份；无观察任务保持旧幂等键兼容，有观察任务在运行级范围加入观察身份集合。
- 来源错配、旧页、OCR 漂移和冻结后观察集变化均无法静默进入任务。提示注入即使形成调用级审计候选，也会被定位与文本哈希门禁和事务发布门禁拒绝。
- 父级修复一个 Pydantic 校验器问题并补齐两条负向回归；聚焦 `14 passed`、受影响层 `105 passed`，执行审阅、路由审计和过程归档完成。
- 当前仍不包含项目特异规则。D001 控制任务 `3259ab5f070447c3938ff2de5f45c9cd` 保持第 19 个已完成发现批次后的暂停状态。
- Phase 5 下一步是使用隔离 D001 II 与 MG-K10-SAR III 代表受试者运行真实 Evidence Normalizer，逐事件核对事实、日期、冲突、资料覆盖和来源回放，而不是继续旧方案控制任务。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_VISUAL_OBSERVATION_NORMALIZER_CONTRACT_ACCEPTED.md`。

## 2026-09-01 方案语义分级路由与 GLM 真实复杂父规则探针

- 复杂方案语义任务首选 `zhipu-coding-plan/glm-5.3-flash:high`，失败后按作业级完整尝试依次回退到 MTPLX medium 和 DeepSeek V4 Flash high；短提示、单规则、单批次任务优先 MTPLX。
- 回退不跨 provider 续会话、不混合候选或缓存。路由分类只依据任务种类、规则数量、批次数和估算 token，不读取项目、疾病、药物、量表、条款编号或时间点。
- 冻结 SAR EX-06 真实 GLM 探针使用原失败任务的只读输入快照，不续写旧任务，也未启动 MTPLX。60,000 输出 token 下两次调用共耗时 803.21 秒，形成完整水合草稿。
- 初始拒绝来自通用门禁假阳性：分支门禁漏读原子条件逐字来源，父规则覆盖门禁误把引导语和例外结局当成原子义务。通用修正后，同一未改动草稿复验 `publishable=true`、零问题。
- 验证为受影响层 `238 passed, 5 warnings`；全 V2 `3360 passed, 3 skipped, 139 warnings, 2 subtests passed`，另有一个既存 D001 v1.5 提示哈希漂移，旧检查点未改。
- 当前性能未接受：单复杂父规则约 13.4 分钟，不能直接扩展为全方案。下一步先做通用父规则结构分段、有限并发和确定性同父规则合并，再新建 SAR V2 作业。
- Phase 5 仍为 `claims_complete=false`；失败 SAR 作业保持 `failed_final`，D001 保持第 19 包后暂停。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_SEMANTIC_MODEL_ROUTING_GLM_PROBE_ACCEPTED.md`。

## 2026-09-01 超大官方父规则结构分段离线验收

- 已建立通用冻结来源块分段、同模型有限并发、确定性同父合并和一次整父回退合同。切分依据只包含输入令牌估算、冻结来源块数量、闭合标点、连接词和括号平衡，不包含研究、疾病、药物、量表、条款号或时间点。
- 默认并发 2、硬上限 3；每段只读继承限定语和自身正文，合并后仍由完整父规则来源与语义门禁决定是否可发布。
- 定向回归 `165 passed`；扩展协议回归 `1284 passed`，仅保留既存 D001 v1.5 提示词哈希漂移；受治理执行审计通过。
- 本轮发生一次执行者截断共享大文件事故；Codex 从 13 份一致历史快照恢复后重新实现并独立验证，未采用损坏产物或执行者自报。
- 尚无真实 GLM 分段时延证据，不能宣称已解决 803.21 秒问题。D001 仍停在第 19 包后，SAR 新作业未创建，`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_LARGE_PARENT_SEGMENTATION_OFFLINE_ACCEPTED_LIVE_PENDING.md`。下一安全动作是对既有只读冻结复杂父规则输入做一次独立真实 GLM 分段探针。

## 2026-09-01 超大官方父规则层级分段离线验收

- 通用规划器现按冻结顺序继承根限定语和嵌套限定语；引用方括号作为版式/引用噪声，不与必须失败关闭的逻辑圆括号混同。
- 相同限定语栈正文按令牌软上限及每段最多 3 个闭合单元聚合。既有只读复杂父规则的 11 个正文来源形成 4 段 `[3,3,3,2]`，来源顺序、覆盖和输入字节均保持不变。
- 完整协议回归 `1286 passed`，唯一失败仍是既存 D001 提示词哈希漂移；治理执行审计通过。共享逻辑未出现研究、疾病、药物、量表、条款或时间点硬编码。
- 当前仍没有真实 GLM 分段后的时延与语义质量证据，不能宣称性能目标达成；D001 继续停在第 19 包后，失败 SAR 作业未恢复，`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_LARGE_PARENT_HIERARCHICAL_SEGMENTATION_ACCEPTED_LIVE_PENDING.md`。下一安全动作是使用既有只读冻结输入新建 GLM 分段探针。

## 2026-09-01 超大父规则 GLM 分段真实探针失败

- 冻结复杂父规则按通用结构形成 4 段 `[3,3,3,2]`；真实调用固定 GLM-5.3-Flash high、并发 2，没有启动 MTPLX、DeepSeek 或整父回退。
- 生产 GLM 传输因 `uses_compact_wire_contract=False` 默认绕过分段，说明“可分段”被错误绑定到 wire 形式。探针只为验证而强制进入分段，未改生产能力声明。
- 三段成功，第 1 段约 600 秒读超时；权威运行 7 次调用、1213.19 秒后失败关闭，没有合并候选、水合草稿或完整发布门结果。
- 独立对照确认当前分段运行不能证明比 803.21 秒整父基线更快或质量更高。生产分段器和运行器未发现 D001/SAR、药物、疾病、量表、条款或时间点硬编码。
- 下一步是通用修复：独立声明分段能力、按来源/提示/模型/分段身份持久化成功段、只恢复失败段，并区分超时与 Schema 错误；随后只补跑缺失段并做完整合并门禁。
- D001 继续停在第 19 个检查点后，失败 SAR 作业和旧探针保持不可变，`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_LARGE_PARENT_SEGMENTED_GLM_PROBE_FAILED_RECOVERY_REQUIRED.md`。

## 2026-09-01 GLM 分段恢复机制验收、局部修订质量拒绝

- 复杂方案语义路由继续采用 `GLM-5.3-Flash high -> MTPLX medium -> DeepSeek V4 Flash high`，短提示和小工作量任务采用 `MTPLX medium -> DeepSeek V4 Flash high`。回退按完整候选隔离，禁止跨 provider 拼接。
- 分段能力已与 compact wire 能力解耦；成功段以方案、提取快照、提示、模型和分段身份形成内容寻址检查点，失败段仅同模型有限恢复。
- 冻结 EX-06 缺失首段恢复复用了 3 个有效检查点，只发起 1 次 GLM 调用并取得 4 个 Schema 有效分段。
- 直接合并候选仍有 6 个完整门禁问题。两次 GLM 局部修订的临床内容离线重放后产生 26 个问题，已失败关闭，未发布或写回。
- 验证为协议 `1305 passed, 1 failed`；唯一失败是既存 D001 v1.5 只读提示词哈希漂移，旧检查点未改。受控执行审计通过。
- Phase 5 仍为 `claims_complete=false`。下一步对同一冻结输入运行全新、隔离的 MTPLX 整候选及完整门禁；D001 继续停在第 19 包后。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_GLM_SEGMENT_RECOVERY_ACCEPTED_REPAIR_QUALITY_REJECTED.md`。

## 2026-09-01 方案语义 fallback 同源对照与耗时边界

- 复杂任务继续使用 `GLM-5.3-Flash high -> MTPLX medium -> DeepSeek V4 Flash high`；短任务使用 `MTPLX medium -> DeepSeek V4 Flash high`。供应商切换只允许新建整候选，不续会话、不拼接缓存。
- 修复路由接受条件：终稿存在但完整门禁未发布时仍是失败候选，必须整次丢弃并继续下一模型。
- 同一冻结 EX-06 当前门禁重放结果：GLM 分段合并 6 个问题；MTPLX 1082.56 秒、12 个问题；DeepSeek 两次分别 374.19 秒/2 个问题和 309.54 秒/9 个问题。四者均不可发布。
- MTPLX 的第二次修订在 600.002 秒超时。复杂任务的 MTPLX fallback 现只运行完整首稿；短任务 MTPLX 和 DeepSeek 各允许一次定向修订，GLM 主路由保留公平修订预算。
- 确定性比较结果为 `evidence_integrity_passed=true`、`semantic_acceptance_passed=false`。这接受证据链和路由设计，不接受任何模型候选。
- 聚焦 `24 passed`；协议与 Agent 扩展 `1373 passed, 1 failed`，唯一失败为既存 D001 历史提示词 SHA 漂移。治理审计通过，过程文件已归档。
- Phase 5 仍为 `claims_complete=false`。D001 停在第 19 包后，下一步改用新的异构冻结父规则验证通用性，不继续针对 EX-06 调提示。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_SEMANTIC_FALLBACK_COMPARISON_ACCEPTED_CANDIDATES_REJECTED.md`。
## 2026-09-01 跨方案方案语义验收状态

- 复杂方案语义路由保持 GLM-5.3-Flash high -> MTPLX medium -> DeepSeek V4 Flash high；短任务保持 MTPLX -> DeepSeek。候选和会话按提供方完整隔离。
- D001 只读 EX-18 的 GLM 整候选证明模型可在另一方案上保留 8 个多分支洗脱期条件，但 8 项资料要求均只落在筛选期。
- 当前通用门禁要求：以基线、随机、首次给药或研究药物给药为锚点的前置条件，至少在基线节点最终复核；筛选期提前关注不能替代。
- 旧存盘候选由新门禁离线重放后不可发布，冻结来源未修改，D001 第 20 包未恢复。
- 先前“异构父规则”选择只按来源规模排序，EX-18 与 EX-06 实为相近的治疗史/洗脱期结构。下一步必须改用项目无关的结构特征距离，不能用篇幅、项目词汇或临床内容硬编码。
- 恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_CROSS_PROTOCOL_GLM_STAGE_GATE_REJECTED.md`；Phase 5 `claims_complete=false`。

## 2026-09-01 异质规则 GLM 验收与局部例外安全边界

- 项目无关结构选择器从两份只读方案快照选择 EX-24；它只使用来源布局、逻辑形态、数值/时间/专业判断等通用特征，不读取项目或临床词汇决定结果。
- GLM-5.3-Flash high 整候选耗时 393.22 秒，两次同会话调用，冻结来源哈希不变；当前完整门禁与独立重放均为零问题。
- Codex 临床复核没有停在门禁阳性结果，而是追踪组件级例外运行语义。共享门禁和提示现要求开放列举中的局部例外仅在“该例外是唯一相关情况”时才能豁免组件，避免同时存在其他触发条件时错误通过。
- EX-24 保留“包括但不限于”、专业判断、局部例外和筛选期资料要求，接受为跨方案异质语义证据；不据此写入正式规则目录。
- 扩展回归 `1377 passed, 1 failed`，唯一失败仍是不可变 D001 历史提示词 SHA。D001 第 20 包和旧 SAR 失败任务均未恢复。
- Phase 5 继续 `claims_complete=false`。下一安全动作是隔离代表受试者的真实事实规范化与 Patient Profile 逐事件核对，不伪装为完整入排判决。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_HETEROGENEOUS_GLM_EX24_ACCEPTED.md`。

## 2026-09-01 代表受试者全新运行与模型路由收敛

- 复杂方案语义任务使用 GLM-5.3-Flash high -> MTPLX medium -> DeepSeek V4 Flash high；短任务使用 MTPLX -> DeepSeek。跨 provider 始终是完整候选切换，不拼接会话、片段或候选。
- 双击启动器和服务入口已与该路由一致；graded 模式不强制预热 MTPLX。
- 旧 `runtime-data/sar31001` 数据库是方案解构失败运行，不是事实或 Patient Profile 结果；只读保留并被通用门禁拒绝。
- 新建 `runtime-data/sar31001-fresh` 为唯一合法下一运行根，已哈希复验一份方案和五份受试者副本，尚无 SQLite 业务状态。
- 验证：启动 UAT 14 项、聚焦 40 项、Agent/工具 145 项通过；扩大回归 1464 通过，仅1个不可变 D001 历史提示词 SHA 漂移失败。
- 本步未启动新 V2，未运行真实 GLM 方案作业或 31001 事实/Profile/浏览器闭环；`claims_complete=false`。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_FRESH_SUBJECT_RUNTIME_ROUTING_ACCEPTED.md`。下一安全动作是在专用端口以 `sar31001-fresh` 启动隔离 V2，先从哈希副本新建 GLM 主路由方案解构，再进入 31001 逐事件事实和 Patient Profile 核对。D001 第 20 包与旧 SAR 失败作业仍禁止恢复。

## 2026-09-01 SAR 全新方案作业无损暂停

- 新建作业 `da944f6e2a504694bbfbc888fa44d184` 已在 `sar31001-fresh` 完成前 6/10 步，冻结方案身份、原文结构、221 页渲染和规则输入。
- 用户要求暂停后，治理执行会话和专用 8910 服务已停止；共享 8000、8001、8900 未变，工作者 03 未启动。
- 当前数据库现场保留 `generate_draft` 第 2 次尝试的 `running / SEMANTIC_DRAFT_MISSING`，并保留 WAL、6 个步骤检查点、17 条事件、8 个批次文件和路由审计；`quick_check=ok`。
- 实际审计表明 GLM 因专用进程未读取到凭据而跳过，MTPLX 连接失败，DeepSeek 候选被来源闭包门禁拒绝。恢复时必须先查清专用 V2 的配置加载边界，不能将本轮误称为 GLM 已执行。
- Phase 5 继续 `claims_complete=false`；31001 事实、Patient Profile、浏览器验收及临床 QC 均未开始。

恢复入口：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260901_SAR_FRESH_PROTOCOL_LIVE_PAUSED.md`。

## 2026-09-02 Phase 5 工程边界收敛

- 当前 worktree 内的 2026-09-01 修订版设计书和实施计划在合并前继续作为本任务的执行依据；不要用主检出目录较旧副本覆盖。
- 方案原文入口正式收敛为 DOCX：用户上传原始 DOCX 后由结构提取和方案语义 harness 处理。方案 PDF 结构识别分支已退役，但受试者原始证据中的 PDF/图片处理与回源展示不受影响。
- 方案语义传输使用供应方中性模块和接口；复杂任务路由仍由模型路由器决定，不把任何供应方名称固化为业务抽象。
- `openai` 与 `pymupdf` 已归入生产依赖，避免无开发依赖安装后运行期缺包。
- Alembic 初始化配置不再禁用已存在的应用日志器；迁移后语义传输的重试和审计日志仍可被捕获。
- 完整协议回归当前仅保留既存 D001 v1.5 提示词 SHA 漂移。旧重放检查点不可改写，后续以显式新提示词版本和新检查点处理。
- SAR 修订 15 仍因 `EX-07` 未命名的 6 个月回溯锚点阻断发布。工程层收口不构成临床授权；规则目录未发布前不得进入 31001，`claims_complete=false`。
## 2026-09-02 节点相对回溯窗口解释

- 对方案只写“N个月内”等回溯范围、但未命名筛选/随机/给药锚点的条款，系统默认继续失败关闭，不得自行猜测。
- 当项目级、来源明确且不违背方案的医学解释明确要求按审核节点回溯时，正式条款的阈值和逻辑保持不变；系统为解释声明的审核节点建立独立评判实例。
- 当前 SAR EX-07 的用户授权解释为：筛选审核按筛选日前 6 个月，基线审核按基线日前 6 个月再次独立评判。筛选节点结果不能替代或覆盖基线节点结果。
- 该机制必须项目无关；共享代码和提示框架不得包含 SAR、EX-07、蠕虫、6个月或任何具体疾病/药物硬编码。

## 2026-09-02 SAR 31001 事实规范化无损暂停

- 用户正在单独测试 MTPLX，构建任务已暂停；仅停止专用 `8910`，共享 MTPLX `8002`、OCR `8001` 和主应用 `8900` 保持原状。
- SAR 修订 16 和筛选期证据处理已完成；事实规范化停在取消请求状态，基线期处理未成功，尚无事实、事件、用药暴露或 Patient Profile。
- 当前 `claims_complete=false`。唯一恢复入口为 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260902_SAR31001_NORMALIZATION_MTPLX_PAUSED.md`；恢复前先确认 MTPLX 测试结束并核对实际模型绑定与 502 根因。

## 2026-09-02 患者原始资料 VLM/OCR 横评终报（Phase 5.5 前置）

- 真实原始资料 71 页（SAR III 4 例 + D001 II 3 例筛败）、7 模型统一 harness；金标 832 事实 + 158 条款，Cursor subAgent 对图首审 + Gemini-3.7-Flash 条款复审 + 机械裁定，争议清零。报告与全部数据在 `~/tmp/ie-vlm-benchmark-20260902/reports/FINAL_REPORT_20260902.md`（仓库外，未读入任何原始资料到仓库）。
- 结论：双 VLM 主链取 GLM-5.3-Flash（事实召回 0.915、证据页 0.907、¥0.016/页）× MiniMax-M3（0 危险漏判）；并集事实召回 0.969，双漏 3.1%，模拟双模型下危险漏判为 0。Qwen3.8-27B oMLX 作离线第三路（条款准确 0.854，106 s/页）；Flash-Next 仅手写专项；DeepSeek 与两个 OCR 模型不进主链。
- 关键发现：单模型两轮事实 Jaccard 仅 ~0.38 且与 temperature 无关，来源于提取粒度自由度 → 双模型 + 确定性归一化对齐是必需项，不是可选项。研究者手写判断（CS/NCS、便签、签字缩写日期）是所有模型最不稳的识别项，需独立强制字段。
- 用户裁定规则：方案无明确阈值的检验异常以研究者书面判断（报告单批注或对应节点病历分析）为准；无记录 → 证据不足，缺口类型 = 研究者判断缺失。
- 设计书 R3 与实施计划已按横评修订（§3.3/§4.2/§5.4/§7.0/§7.2/§7.4/§11/§12；Phase 5.5 工作项 1–2 完成、3–8 重写）：单阶段双 VLM 主链，不采两阶段；页级信号降为证据信号；手写强制结构化三源对账；Flash-Next 手写第三读；Qwen27B 离线/仲裁。
- 进入 Phase 5.5 时须修正的 prompt/harness 系统偏差：EX-08 排除本研究筛选本身；合并用药/既往史类 EX 只出 needs_review 交 ClausePack 确定性判定；跨页算术（洗脱期）交 validator；GLM 内容过滤 1301 与 12k 输出截断需替代路由。

## 2026-09-03 R3 读道边界收窄与 Phase 5 当前现场

- 现行受试者逐页判读只有两个主读：GLM-5.3-Flash:high（zhipu-coding-plan）与 MiniMax-M3:high（cms-smk）。Qwen3.8-Flash-Next 只作 handwriting-C 且只写 `handwriting[]`；它不替代主读、不仲裁普通事实。DeepSeek 不进读道，GLM-OCR 只作侧车。
- 2026-09-02 横评记录中的 Qwen27B 离线第三路及“Flash-Next 降级/仲裁”只保留为历史，不是现行产品路由。普通事实单源候选保持冲突/待确认，失败主读只能由原模型同合同复读。
- R3 设计与计划已对齐，提前实现的读道草稿被拒收；Phase 5.5 仍须等待 Phase 5 收口后从 ClausePack、`determination_mode`、PageReviewRecord/PageReconciliation/SubjectPageCoverage 合同层开始。
- 31001 筛选与基线均已有活动完整证据修订，但 facts/events/exposures/profiles 仍为 0，`claims_complete=false`。旧规范化作业已合法取消，旧 502 是冻结 27B 身份与 8002 实际 Flash-Next 身份错配。
- 本地 Flash-Next 规范化单页历史耗时约 46 分钟，不能直接全量续跑。下一安全动作是先做项目无关的输入合同压缩或采用经批准的独立语义路由，并以单页速度与临床事实质量双闸门决定是否新建全量作业。
- `8900` 当前属于另一 Vibe-Research 服务，不是入排审核主应用；本任务专用 V2 为 `8910`。恢复依据为 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260903_R3_RECONCILIATION_AND_CLEANUP.md`。
