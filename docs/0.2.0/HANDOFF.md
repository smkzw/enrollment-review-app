# 0.2.0 当前交接

更新：2026-10-15，Goal现场active，**不是暂停、正式验收或全产品完成**。本轮服务／完整测试源码b18f85a9；API断言及交接基线922d9256已推送并读回。节点10为8/8开始、8/15资料截至。病历5页Job9be916d14ea6433baf80c818231918a4已completed2/2，1调用610.753秒，10事实／44拒候选／Profile10；其余23页不重读。自动子Job e360a34668194952a4886a8219670a08 completed4/4，保存run192ec274d74d4280ad911d81bb04f74e／计算v37、136冻结事实／24页／149项，123证明复用、2目标1新调用468.029秒。血压分项已消费，严重疱疹不再假矛盾；其他独立未决保留。542来源引用逐字／身份0失配，旧事实与报告不改。临床及集中测试均已终态，完整窗口及唯一新增断言的修复分开见§6；Ego实际交互可读但新截图CDP超时。S4发布／用药消费、M1/M2/M3未完成，claims_complete=false。

## 1. 五分钟入口

D27已实际入工作稿：IN01满足／低置信，按8/8有日期来源51岁核对，不借后续年龄反推，不写出生日期。A提出的四项日期缺陷已修，393相连检查通过。无日期且仅旧年龄跨阈值的现龄适用仍需明确，当前例不靠该例外。B发现8/8内镜页眉52岁未成为事实，保留低置信与原件差异，不称全部原始年龄文字一致。原14次范围核查、失败和旧稿保留；当前两次调用分别为真实单页整理和2目标关系核对，123相容兄弟不重读。血压原图及事实分项、阈值消费、明确严重疱疹否认与基础疱疹事件的差别均由owner核过；不把模型字段当医学金标。接收完整后端终态、精确对照失败ID及现有UI原件导航，然后报告M1证据与未决，继续S4消费者；不重开方案／变量建议／24页抽取。

- 唯一树：/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0，dev/0.2.0；主checkout及phase5旧树不能替代。
- 当前服务源码b18f85a9a18730ff80569a6a629a0e1b9c568d58，远端读回相同；前端产物仍31dc，未改UI时不重复build。每次只在0活动时切自有服务，不用查询串证明运行版本。
- 只读本树AGENTS、01_PRD／02_DESIGN／03_PLAN／04_ACCEPTANCE／05_PROGRESS。archives是0.1.x历史，不注入旧授权、Phase、预算或长链。
- 从05当前WP接续，不重跑方案、变量建议、既往53次抽取、已处理24页、已终态v32–37。旧22页关系证明仍保留，但不能证明新增8/15两页已核查；当前24页关系核查是资料范围变更后的新任务，不是重启旧失败。历史原答不筛选或改写。
- 构建者自主走验证流程，用builder_verification；正式医学经理审定及最终验收不代签。用户已经真实批准规则7，未改条目不重复请求批准。

## 2. 当前现场与精确身份

| 层 | 实际状态 |
|---|---|
| 产品 | 医学人员／监察人员的信息和风险展示，不是最终入组决定、反馈或事无巨细留痕平台 |
| 服务 | 61134，PID59717／exec20790，后端b18／前端产物31dc；显式本树.env／data_v2；output/wp4-source-dimensions-server.log；旧54173／42020、48535／19122、27870／54329均0活动时TERM收回143；当前健康单页任务不重启 |
| 服务历史 | 自有84383／16038、97209／38678已TERM并收回143；更早68998／76651同样终态。共享8001/8900不操作，旧build查询串不代表代码 |
| 数据 | WP0验证副本data_v2/enrollment-review-v2.sqlite3，约16GB；没再复制大型库、没有修改原临床库或原件 |
| 项目 | draft-project-1153e25b4eba |
| 规则 | ruleset:draft-version-1153e25b4eba:phase_iii revision7；64有效medical_manager审定；verification_only=false；原草稿rev21及旧发布保留 |
| 个例 | subject58ff71df0cff4a2c9107be743d82584b，31001，中心31 |
| 节点 | b843b2c07d6d4318a6df741eb7902eb3 revision10，screening_date2025-08-08、evidence_cutoff_date2025-08-15；原Ego保存并读回，不直接改库 |
| 资料 | snapshot c69c297a3ea84c57a8fa953e07567b1d；complete-ad2f258d2aff46a98affc99dfac3ea78；5份24页、136冻结当前事实，单页新增10，0新事件／暴露；原件不改 |
| 档案 | 单页生成Profile10 profile:8a73f15951098ad090e200bd5ecdd13b；旧Profile8及事实不改 |
| 最新已存工作稿 | review-run:192ec274d74d4280ad911d81bb04f74e／计算v37，自动Job e360a34668194952a4886a8219670a08 completed4/4；123证明复验复用、2目标1新调用，149项。前run1e0918ff…／计算v36及Jobfbc…的0调用版本保留。计算版本与UI稿序号不同 |
| 上一工作稿 | review-run:f653ab4d06ef4b9ea0a2f01123bb2c5d／计算v35，Jobc91b2b995a36410ba04e7f1b6981d983 completed11/11；仅16失败目标2次补核712.699秒、109相容证明复用。再前run2c904864…／Job9ab…为12调用6990.130秒、16失败，原答及坏JSON不补写 |
| 再前版本 | review-run:1c2b83e3c17d43769516b951a09bb0d3（v34），Job18bb37c1e29041b69515efd54a523148；旧v33 review-run:03754ec576c04698b9e2997e87fb1db2。全部保留，不重跑 |
| 结果 | 当前64父／85子；34父项确定、15未到期、5不适用、9证据不足、1系统项；高置信父项0。EX07:14血压阈值与EX07:25严重疱疹否认均未触发，EX07父项仍因其他条件不足而未知，不再假conflict。HBV用于EX09:02，活动性肝炎判断未闭合 |
| 其他来源提示 | 28未采用原件提示独立于1规则系统问题；ReviewRun内29系统／来源记录，不与UI的1混分母 |
| 旧核实 | 先前run8883771d…的IN01构建者试用核实保留在旧版；资料范围改变后不继承为新稿高置信。当前51岁源及后续52岁按日期核，不回填事实生日 |
| 当前Job | 9ab／c91／fbc均completed11/11；9be916d1…completed2/2，e360a346…completed4/4；无活动临床Job，旧终态不改。S4草稿afe79035d4e04d1b9b8f4778dbc0e54e修订3保留；完整后端exec96491及API复核31867均终态 |
| 模型角色 | 病历关系cms-router/glm-5.3-flash high65536流式经OmniRouter；规范化ollama-cloud/deepseek-v4.1-flash high65536，本月额度失败保留。默认角色及.env未改 |

用户最新允许生图造测试源：只作明确虚构的工程材料，独立TEST001／离线期望，不进入真实31001、IE或D001。不能把“生成成功”“图像好看”“来源文字可读”称临床批准或医学金标。

## 3. 这轮实际修改与首错

### 本次日期／对立范围及数值分项收口

4cd年龄v35、07b年龄v36、b18相反表述v37均已提交推送，源页及旧事实不改。07b修复A提出的宽闰日容差、采样／报告跨角色误冲突、条款窗外年龄时序及空截至回显KeyError；393相连检查51.27秒通过。b18在既有SourceRelation内增加可选SourceOpposition，不新增Agent／队列：肯定／否定摘录分别定位，对象、覆盖期间和限定不能证明一致就保留unclear，不强行称患者矛盾。旧非矛盾结果按实际请求／Schema有界兼容复验，旧矛盾缺完整对立范围只失效相应目标。分量数值提示要求一个变量一个原始数值，保留整句及共同单位，不增加项目特例。638相连规范化／发布／Profile／源码复用／工作稿／历史／API测试62.76秒通过，原始日志wp4-source-dimensions-package.log/xml；完整后端仍在集中窗口，不能沿用旧全量结果称新版本完成。

BP诊断：旧候选有合值但未映射到两数值变量。旧失败页续读预检证实页5本来已成功、只页8待核，故不扩pending来制造资格；自己的跨规则pending补丁保存在output/wp3-pending-revision-deferred.patch后精确撤出生产。复用公开create_or_reuse_job，以当前真实FactNormalizationCallSpec选择页5，明确新切片而非失败恢复。Job9be已completed2/2，不再提交。1调用610.753秒、30952输入／49357输出／80309报告token，思考拆分未知；10新事实、44拒候选、0事件／暴露。原图确认两血压分量与单位，风险标记仍低置信，未冒称正式医学核实。自动子稿仅2目标1调用468.029秒（16263／22976／39239），123证明复用，EX07:14／25均未触发，9其他未知与1系统项保留。run460b仍partial，因为是1页范围，不表示其余23旧成功失效或被新读覆盖。一次子稿租约短写锁后正常终态，没有重派。output/wp3-bp-page5-{preflight,submitted}.json、wp4-current-scope-workdraft-audit.json及m1-review-review-run-192ec274…目录为本机受控证据。

本轮A／B均当前live C03 Grok Build grok-4.7 high，无fallback，非先前CodeBuddy路线。A鲜会话0ed4d29d…713.641秒，B鲜会话a7bc45aa…935.216秒；仅上下文独立，不称不同模型意见。B读64父／149项／24页有效文字／126事实／125语义输出及规则7，未读原像素、IE或源码。两报告等20文件已移入ignored output/wp4-age-screening-conference-20261015/并保留路径／SHA清单；runtime receipt仍在ignored logs/conference对应任务。A初次preflight把带连字符的说明误当路径，已校正文案后通过；runner实际冻结的是原等价读集，不能伪称它首次preflight成功。

### S4补充要求：ed039及当前核对补丁

生产路径：`protocol_medication_author`经现有DECONSTRUCT直连GLM→既有ArtifactStore→`ProtocolWorkbenchService`建议／保存→`ProtocolDraftService`追加修订→已有`RuleReviewRecord`列表→`ProtocolMedicationRestrictions`编辑。无新表／队列；不冒造官方编号。模型提案用纯语义对象，host生成med条目ID；旧无补充字段的内容哈希保持。

实际Ego42/p1在afe79035…范围修订2点击一次，原生S4取41唯一位置／1459原文字符；模型返回34条限制。两次报告输入10266、输出59151、总69417token；思考拆分字段0与可见思考长度冲突，拆分未知。首答请求21933da1…／原答1fbeb66c…，第二请求29ab2166…／原答f047fc9e…；失败manifest660c3614…保留，不覆盖、不挑第二答。旧请求没有端点身份冻结字段，复验不追填当前身份。

首答把同段允许／例外原文和限制共同引用，这是合法来源关系；原检查却把所有“除外”套给同段每个药，并拒绝permission兼作例外依据。重试重发整答，使随机前“窗口内禁用”变为“距随机至少该时间范围”，不能因第二答更完整就采用。补丁用原始位置识别对象自己的已知例外，保留允许段的例外引用；结构化单项错误只重发该项并冻结兄弟，仍总共两次。失败点击只复验原始首答，实际提示／Schema／来源／路线不相容即保留问题，不偷偷新调用。模型失败仍提供原文手工整理入口；类别成员冻结入草稿及审定hash。

首答的“整个研究期间”却仅选基线，且把背景治疗剂量／频率限制记成背景。原Ego实际勾选筛选／导入／基线，保留原有随机前窗口；长效与一般SCS不直接等同整个全身激素类别，清空这两项类别并写明待核；两段剂量／调整约束明确未决，不当纯背景略过。保存追加修订3，原官方及变量逐字段未变，3类别表冻结；34药物、1范围处置、原64合计99审定项，62沿用有效、37待审。不是全部重新批准，也未自动批准。发布保护仍保留，规则7、38报告及125真实事实不改，尚未完成共同发布、患者用药消费或M2。

实际读回：output/wp5-medication-revalidation-audit.json／wp5_medication_revalidation_audit.py（只读）与-draft-saved-1920.png（已看）。raw_request139→139，原失败／两原答hash核验，7规则／38报告保存payload完整性核验，官方／变量与原发布相同；不把hash完整性称医学正确。保存时内层面板收起令可见文案等待超时，实际PUT200且修订3已存；展开核实后未重复保存。一次Ego指针被视口边缘拦截，改用真实聚焦／空格勾选，未注入React状态或手写临床JSON。

ed039作者包相连185passed104.27秒／完整前端928passed11.72秒；当前最终补丁相连237passed112.17秒exit0，完整前端104文件930passed46.02秒exit0，正式构建exit0。日志wp5-medication-revalidation-connected-final.log、-frontend-final.log、-build-verified.log。未重跑全后端。路径误写test_protocols.py导致exit4未运行，保留日志，真实文件为test_protocols_api.py。

### 734998ee：未知分类不等于患者资料矛盾

文件：app/services/work_draft_semantics.py、work_draft_review.py及test_work_draft_source_relations.py。

EX07组件25两份原答均truth=UNKNOWN、applicable=yes、policy=false，对象／时间核实一致；只是conflict／unclear分类不同。原严格对账把它当读取意见不一致，再被消费者显示技术系统项。现在仅在两份已逐字核实、同页集合、共享摘录、非真实方向分歧的未知答之间保留忠实未知；双方原理由／原答引用仍在proof，未将其合成false或患者矛盾。真实方向相反、对象／时段不同、无共享来源仍拒兼容。持续第三答须沿同一证明边界，不靠当前标签白名单。

include_source_categories是规范化专用参数，直接propose_question_classifications请求不消费它；继承这个非操作参数使125旧请求身份全部假失效。仅在该产品语义角色剔除无效参数，保存实际请求／Schema／来源／模型参数核验，不能据此忽略真正语义或来源变化。

EX13保留restricted状态，沿现有投影显示limitation_kind及unresolved_dimensions；不填时间窗、不新增“仅负判定即可通过”的消费者，不改变PRD R-C8授权边界。

### cd18a4d3：沿正式消费链保存分层原因

文件：work_draft_calculation.py、work_draft_review.py、work_draft_semantics.py及相连测试。

- “未见事件记录”仅可作用于逻辑正极性的EXISTS／EQ True事件叶；NOT、EQ False及例外叶不借缺记录变false／true。正事件叶与独立例外可共存，各自政策不同；原始source_results不改。
- REQ失败按冻结procedure_catalog实际item_id关联到工作稿，不用假IN/EX编号或模糊字符串；失配目录是身份失败，独立正常／未来结果不拖掉。
- calculate保存的source_issues经SystemIssue验证后带入compose，不能丢掉影响置信的来源故障。
- TB筛查结果仍是独立未关联要求；理由逐项列该要求及严重程度未知，不把病历否认当已完成检查。已绑定的同义资料说明不重复铺陈，但独立要求不删除。
- 同源UNKNOWN当前理由不再拼接旧“故标conflict”文字；旧理由只留在可复查证明与原答中。
- 4个旧fact_context_consumers夹具补必需fact.authority实参；旧临床断言不放宽。

计算版本v33、来源校验v28；没有增加框架、数据库、队列、模型读道或项目阈值特例，没有删除旧失败回执。

## 4. 真实用户动作及证据边界

当前范围选择子包（0ae/0fd）：在原Ego42/p1从正式项目“不上传文件，按反馈修订”合法建立afe79035…，未起草／建议模型；勾选范围、EX12具体待定位引用、实际章节及一句理由，保存为外层草稿修订2。41原文位置及对应引用读回，刷新仍在；未改旧规则／事实／38报告，UI发布按钮禁用并说明补充要求未完成。选择仅为位置提案，S4和定义依据未采用；正常手工编辑、绑定、历史恢复及过期／跨来源反例有服务测试。原无选择payload不改变；未新增表或16GB备份。相连168后端通过，完整925前端通过；第一次夹具重复消费同一个Response导致单例失败，已改为每次真实新响应，不改产品断言。Ego截图wp5-scope-selection-saved-1920.png已实际查看，无横向溢出；未再次做全宽屏／真实缩放。readback为wp5-scope-selection-audit.json，模型0／临床采用写入0，作者草稿写入独立记录。保存后面板曾自动收起，已由宿主保留展开状态；后台/前台版本分别记录，源码提交不等于医学验收。

范围查看子包（f935）：`review_scope.py`生产→现有原任务已保存的结构／来源→`ProtocolWorkbenchService.get_review_scope`→`GET .../{job}/draft/review-scope`→草稿及已发布任务“查看审核范围”。不是新增临床保存／采用；范围选择持久化及禁用药仍待做。3280原生块哈希核验，221来源身份一致；表格根复用已有`native_source_text`拼接，889空／片段摘录不误称损坏。23官方／1已定位引用／41必做／3用药章节；3用药章节有重叠，后续按来源身份取并集，不按59引用重复送读。EX12“参照6.5”此前漏识别，现通用写法已发现，但Word自动编号不猜，准确列待指定。界面仅在展开时GET，按类别／章节下钻，页码变化才显示，不重复标题；错任务／修订及伪造采用身份拒绝。真实GET、三宽屏、状态／数量读回在output/wp5-scope-product-final-readback.json、wp5-scope-product-final-{1920,2560,3840}.png。均CSS仿真，不称物理4K／实际缩放。真实病例原件／旧稿／规则7不改，整个库133事实（含合成）／38报告／5710项／7规则及Job状态前后一致；31001仍125物理事实。

本包相连120后端／920完整前端／构建通过；未重跑全后端。E03节点实际CodeBuddy/DeepSeek max、493.406秒exit0、37工具、无fallback，主线程读完整源码后修表格归属、逐字数值、几何身份及新增反例；guard审计通过，非医学评审。初始packet路径错误、新API夹具漏建Job、Ego相对保存路径及不可见option等待错误保留日志，不借失败掩盖结果。保留code、API、UI及源核对同版本证据，不将纯定位成功称四块临床覆盖完整。

1. 在原Ego42/p2“更新工作稿”得到v34：93.402秒，125关系／证明全复用，0模型，11/11completed。
2. 整合修改后同入口得到v35：54.303秒，125关系／证明全复用，0模型；9待处理仍9。系统2→1只是更忠实的分类，不叫准确率提高。
3. 原件看邮件4页51岁／生日，关闭后用“仅作试用核实”得到v36：58.653秒，0模型；IN01高置信试用核实，148其他项和29来源／系统提示不变。
4. 原报告入口实际切v35和v36，旧稿低置信、新稿明确“构建者试用核实，非正式医学核实”；两版API均200、64父85子逐字段对应保存记录，原hash保持。
5. 654引用逐项核页／文档／逐字范围0失配；固定抽样REQ18、EX12、REQ11、REQ17、EX05可回源。8既有纯数值组件、27事实字段、16原图hash及对应规则表达与先前原图核查一致，本轮没有假称重新看完所有图片。
6. 1920/2560/3840 CSS截图已实际看，DPR1、无横溢；是设备指标仿真，不是物理4K或实际缩放。无可靠坐标时页定位，未伪造红框。

本机证据：output/wp4-current-age-confirmation-audit.json、wp4-current-history-readback.json、wp4-current-source-selfcheck.json、wp4-current-age-preservation-audit.json、wp4-current-report-v36.png、wp4-consumer-integration-ex07-{1920,2560,3840}.png。受控本机可读，外部审阅不可仅凭这些路径取得；未提交临床全文或原答。

## 5. 本次评审及主线程处置

approved runner C03和M1 A/B实际单轮完成，均codebuddy/codebuddy-cli/deepseek-v4.1-flash max，无fallback；120min静默完成等待。两A/B是鲜会话，但同一模型，仅上下文独立，不称模型多样性、临床金标或医学经理批准。

| 评审 | 时间／范围 | 采纳／不采纳 |
|---|---|---|
| C03 wp4-source-uncertainty-review-20261015 | 466.931秒，真实原答、来源和当前代码只读 | 采纳保留未知／源归属核验；不采纳conflict=OR，因为会无源断言患者记录矛盾 |
| A m1-current-code-review-20261015 | 485.502秒，冻结734998ee；Read/Grep/Glob可用、Bash/git拒绝；session01a13c1e-8d5f-7ef0-809c-de57dcb3c876 | 极性、REQ身份、source_issues保存已修并集中验证。未用完整当前Prompt hash不等即125全重读替代现有实际请求核验；真正语义变更仍须范围性失效。未采纳损坏缓存catch-all当未命中 |
| B m1-current-medical-review-20261015 | 505.195秒，v34／规则7／149项及冻结材料，约25深读、9REQ抽查；session01a13c1e-8d3c-7803-911d-47129c8239aa | 采纳具体待缺要求、UNKNOWN理由分层及HBV首因追查；不按男性删除EX14末项，原第三子项无该限定。未把“工作稿未验收”推成“规则7未本人发布”，64真实批准是反证 |

报告原位文件精确搬入被忽略output/wp4-conference-20261015/runs/conference/<task>/evidence_single_object.md；30文件原路径及SHA在output/wp4-conference-relocation.json。runner日志output/<task>-runner.log。没有删除会话历史、原答、旧临床库。A/B对象不是最终cd18/v36，当前整合由主线程受影响合同及消费者验证，不能称最终再次独立通过。

## 6. 测试：当前窗口与旧结果分开

当前b18完整后端已终态：10712通过、244失败、6错误、20跳过、8预期失败、18子测试通过，2487.04秒exit1。与WP0逐ID比，原249项保持、只新增test_subjects_api::test_list_review_episodes_returns_labeled_dtos，首错是EPISODE_KEYS漏新增evidence_cutoff_date。仅补显式字段和默认null断言，subjects API＋真实截至日保存／过期拒绝回归24通过25.86秒exit0；没有改生产或放松源资格，也没有再跑41分钟全库。output/wp4-m1-source-final-backend-delta.json区分完整失败窗口与后续24通过，不能写成同一次全库无新增或全绿。exec96491／31867均终态已收回。

当前v37只读审计：542来源引用0身份／逐字失配；133旧事实、38旧报告、5710项、7规则缺失／变化0、存储hash失配0。计数和hash不是临床金标。Ego42/p2实际载入新稿，低置信正常34项在折叠分组内，假疱疹conflict已消失；截图多次CDP超时，1920指标无横溢只属DOM检查，不宣称新视觉验收。未关闭／修改其他工作空间。新A/B包20文件已在review-gate通过后精确移至output/wp4-age-screening-conference-20261015/，manifest为output/wp4-age-screening-conference-relocation.json，原答不改、内容删除0。

| 窗口 | 真实结果／证据 |
|---|---|
| 0ae范围保存包 | 相连168passed92.07秒，含API／原API／草稿服务／发布／Schema；log为wp5-scope-selection-consumers-final.log；完整前端103文件925passed11.66秒exit0、构建exit0，wp5-scope-selection-ui-verified-2.log及-ui-build-verified.log。未重跑全后端 |
| 734未知／复用子包 | 最终369passed，72.91秒exit0；output/wp4-uncertainty-source-package-tests.log，5SWIG警告。此前365及路径错误日志保留，不累加 |
| 734完整后端 | 10569pass／247fail／6error／20skip／8xfail／18subtests，2157.17秒exit1；253失败／错误ID比WP0多4个历史夹具漏authority，不冒称全库无新增；原XML／log保留 |
| cd18相连消费包 | 最终393passed，46.48秒exit0、5SWIG；output/wp4-consumer-review-integration-final.log。首轮391pass/2fail是独立资料理由重复，修真实依赖去重，未放宽断言 |
| cd18完整前端 | 102文件911passed，43.67秒exit0；output/wp4-consumer-integration-frontend.log；本轮前端产物未改，没有重复无意义build |
| cd18完整后端 | 10588pass/243fail/6error/20skip/8xfail/18subtests，1970.04秒exit1、60warnings；exec61117终态已收回。与WP0相同249失败/错误ID，新增0/关闭0；output/wp4-consumer-integration-backend.log/xml及-delta.json |
| 本轮只读保全 | 旧事实／原件／报告hash保持；v35/v36接口逐项一致；0活动临床Job；654摘录0失配。身份相同不证明全部医学含义正确 |

本轮集中功能包实际命令见对应log；完整窗口：
```sh
.venv/bin/python -m pytest tests -q --junitxml=output/wp4-consumer-integration-backend.xml
# frontend目录：
npm test -- --maxWorkers=2
```

只读脚本需本树venv及PYTHONPATH=.；不猜路径或字段，不将诊断ModuleNotFoundError／错误AtomicPredicate字段当产品临床失败。早期诊断／夹具／路径错误不删除。当前Python3.12.13、pytest9.0.2、pydantic2.13.3、SQLAlchemy2.0.52、httpx0.28.1、SQLite3.53.4。M1-9相对基线检查通过，不代表完整医学验收或全库通过。

## 7. 当前首个阻断及恢复选择

### 筛选开始日期不一定是本次资料审核截止

完整定义已读：source_pages_for_review按“就诊时间／采样时间”排除anchor之后的文档；select_by_variable对数值也保护较晚结果。ReviewEpisode只有anchor_dates，无独立as_of/cutoff。

本例24页处理完整，但关系范围22页：8/15复查已有HBV-DNA报告，现值只有待结果邮件事实。先前以为要重抽一页的假设已被反证。不能把邮件待结果事实更正成另一采集报告；也不能简单删除日期保护，已有异节点／后续访视反例必须保持。

用户已确认完整筛选／导入期资料，8/8仍为开始锚点（D26）。日期合同、选择、来源复验、冻结报告和Ego保存已经完成；节点10明确8/15截止。仅HBV页走合法父作业范围选择重读，原待结果邮件不改；1调用stop354.080秒，prompt30774／completion18243／total49017，上游思考拆分未知。4事实、2拒候选、0事件／暴露，run3639750b…仍partial，不能称全页抽取。原始请求2bcbc5f3…、回执d434652a…受控本地保留；原图核实结果与定量下限是两项，不以数值阈值猜阴性。

历史9ab6c76d…及后续c91／fbc均已终态；24页125关系齐备后，当前单页更新与新稿见文头，**不再等待或重派这些历史任务**。旧22页证明不冒充24页，成功旧观察不删。批量投影按原事务实现，241相连消费者通过；临时一致性副本3投影结果哈希相同，13.685→5.122秒，不外推整个Job提速。首版savepoint触发Runner保护的24失败已修、不改保护，日志保留。

### 其他真实未决

- IN03：按用户批准的季节／对应治疗疗效边界，仍不足；研究背景治疗或不同月份不能拼满足。
- EX13：器械／疫苗时间范围忠实未决；EX14末项妊娠范围未明确。不要删条件或增加无授权快捷消费者。
- TB独立筛查结果未建立消费关联，虽已有病历否认，仍须区分资料要求；不能用“无记录”覆盖未读范围。
- 随机锚点、半衰期、遮挡单位、FEV1用药前关系仍未补齐；没有源不编临床值。
- 实际M2数字更正／新资料补证、M3／IE／D001、真实缩放和备份恢复未完成。指定31001目录5文件均已上传，无新增文件；正确数字不得为了演示改错。
- 118原事实来源提示不因类别或模型信心升格；合成不进入临床评分。未验者如实未验，不按卡片变少、HTTP200或测试数报全产品完成。

## 8. 前轮合成材料与已实现界面（不重跑）

- 原合成图片output/synthetic-sources-20261015/，明确TEST001：实验室异常图与购药单，实际生成模型身份／token／费用未知；离线期望不入任何产品提示。图片不是31001补证或金标。
- 本轮前一GLM显式测试1新页201.865秒，30010输入／12217输出／42227总token；39290思考字符与上游思考token占位0不一致，拆分未知。来源类别更正后2购药事实＋1单次事件、0实际暴露，Profile3含旧6事实，新149项稿保留历史；来源强度仍未知。
- 先前生化图血糖不在151目标、NCS作者未核，异常主层未全验；不得称模型漏读或所有检验覆盖成功。未猜服药日期／疗程／疗效。
- 个例病史／用药是分类交互图，异常检验主层，完整122记录按类型可下钻；没有日期不强造点，处方／购药不画成已服药持续暴露条。
- 图标导航、按需原件、关键原文加重、其余文字折叠、备选选择确认已接。原件无可信坐标仅页定位，未为红框重开OCR。不要恢复常驻三栏或增加审阅理由入口。
- 前Gemini/Ego独立只读试用发生在97984d0c，930.52秒；不归本轮A/B。历史完整结果与已修月份刻度／标题／重点展开在Git和output，当前不重复实现。

## 9. 接续与复盘

1. 核05记录的实际服务／源码与归属，沿已终态v37及afe79035补充草稿修订3接续；无活动临床Job，原读取、变量建议及34项作者不重跑。S4两次及237／930集中窗口已结束；首答复验和UI保存已完成，原失败manifest不变。M1集中检查、两次独立评审及owner修复结果见文头／§6，正式验收未代签。
2. 接共同发布和真实用药消费者：实际`ProtocolPublicationService._publish_in_transaction`尚总拦有范围选择者；`_build_rule_set`尚未携带scope_supplement。须以有源完整处置、真实审定及可消费资格替代临时拦截，同时把补充要求实际带到工作稿／API／UI，不能只删保护或搬一个字段。`WorkDraftAcknowledgement`与前端解码目前仅识别IN/EX/REQ，药物项须明确类型、不造官方编号；例外、类别、处方证据、日期未知分别消费。2制剂类别与2剂量范围未决保留具体影响，未改兄弟审定继承。复用现有草稿／规则，不新表、不重开全方案链。
   当前只读前置诊断：病历5页54候选里44在locator_and_text_hash被阻断，其中11事件因带日期尚无逐项来源证明；两个单次用药的相关事实日期已入档，不等于整事件／剂量／持续状态已认证。下一功能包从已存候选的同对象、日期角色、引用事实及原文范围验证开始，不用新模型重读来替代这个消费者缺口，也不取消保护。补充包冻结3类成员表，不能当作全部药物类别覆盖。上述只是诊断，尚未新增派生资格或发布补充包。
3. 若范围答案到达，按上述分支继续现有产品链；健康已completed Job不重派。若外部条件仅阻断某支，继续独立工作，不自行pause/complete Goal。
4. 真实更正／补证仍沿正式UI，保存→受影响重算→新稿→旧稿回看；不依赖手写JSON或人工补模型答案。Profile、签发、工作稿核实、临床采用与验收各分层。

战略判断：这轮没有证据支持再换框架或增加Agent。首因集中在范围和消费者：未消费的参数被误计入身份、未知标签被当患者矛盾、独立要求被藏进一句“尚不足”、筛选开始锚点被兼作截止。先修真实用户动作的生产→保存→消费→UI，比一处提示补丁后整例重跑有效。

反证和局限：零模型更新仍需54–93秒，保全和现有16GB库查询不是瞬时；一次短写锁后正常完成，不应重启健康任务。两次完整测试窗口中首窗出现4旧fixture实参问题，属于构建检查成本，不能归因患者或推成模型不可靠。技术系统项减少而待处理仍9，说明这轮主要改善表达和分类，不证明医学判定已完善。当前时间范围问题需明确业务含义，而不是继续堆恢复逻辑；M1未验，不能用新文档代替真实临床闭环。
