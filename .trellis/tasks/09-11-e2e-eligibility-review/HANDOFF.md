# HANDOFF｜1006V1｜来源范围已核，已有候选对应接线，继续执行

2026-10-08，用户已解除暂停；Goal实查active，Trellis in_progress，execution_paused_by_user=false。窗口未达，claims_complete=false。本记录是相连功能包里程碑，不是暂停。只维护本HANDOFF、implement当前表及review_index；历史运行在implement附录和Git保留，不按旧“当前/暂停”恢复。

## 1. 用户动作与身份

真实资料页已改善：能在紧凑抬头下连续查看24页原图、切换文件和原始文字、缩放并返回正确受试者。尚未在完整新官方＋跨章要求下生成该例工作稿，也未完成更正后的新审核报告。

| 身份 | 实际值 |
|---|---|
| 唯一工作树 | /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile |
| 分支/任务 | codex/phase5-clinical-facts-profile；.trellis/tasks/09-11-e2e-eligibility-review |
| 本功能包基础代码 | 5876dea9；原生单列访视/分格原文对应、既有候选核对及proof身份，末版见所有者取舍，旧独审不当本增量证据 |
| 当前终态/上游 | 442ede7a902548d885e6a01bf82f0ef0，failed_final/PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED；声明上游b9d2b85f853d4e6a9c2b61388f683826 |
| 失败检查点 | 17=31a0f863234344568d90628fe5b7d04b；累计attempt不等于3新调用。上游21=328f986fdeba472c9009f457bd1bd269；原答/来源/草稿/累计账本保留，不改旧终态 |
| 产品模型 | 官方OmniRouter/cms-router/glm-5.3-flash/high；跨章Ollama cloud/deepseek-v4.1-flash/high、65536输出；产品harness直接访问端点 |
| 当前隔离库 | /Users/smkzw/tmp/enrollment-rv1001-official-continuation-20261003/rv1006-relation-field-source-resume-20261007-v2/data/enrollment-review-v2.sqlite3 |
| 最新已执行产物 | 同上根目录/rv1006-scope-json-api-20261008-v1；3新物理调用/152.314000秒/exit3，源码5876dea9；来源补核成功，未运行后续对应补丁 |
| 私有当前预检 | 同上根目录/rv1006-native-visit-correspondence-preflight-20261008-v3.json；19reusable/2resume_partial/69refresh，3时间组成词对应true、action候选[1]但accepted空，0调用/0写/DBhash保持 |
| 外部可复查范围 | Git源码、合成测试、净化工程报告/索引；原件、DB、实际临床提示/原答与截图仅本机可读，不提交，hash不证明临床含义 |

五分钟入口：本HANDOFF → implement当前表 → delivery_1006V1/03_ACCEPTANCE.md → review_index_20261006_1006V1.json → 新合法作业prepare/execute回执。不要重读全部历史，不复活旧失败Job。

## 2. 同一流程的实况

| 用户节点 | 已证 | 未达 |
|---|---|---|
| 完整有源要求包 | 内置DOCX官方Job1153e25b4eba40db964202a1c3ed07c3草稿修订21，23父条/86组件/141谓词，publishable；85发现/90深审计划冻结 | 最新实跑16完成、17失败、73未执行，18–20仅在来源计划已证可复用；scope/hydrate/gate依赖失败。上游19完成不冒充当前完整采用。publishable不是共同发布 |
| 资料与事实 | 继承5文件24页/14组实际保存，458候选→407事实/40事件/11暴露；32资格候选关联30合格事实、426受限 | 不同分母非准确率。手写对象/数字位置仍有具体未决，新完整要求消费未证，不授予自动事实采用 |
| 工作稿与原件 | 既有冻结计算/资格消费者，Ego真实原件导航；已收紧重复抬头及大空白 | 病例准备副本仍旧81组件/0controls；旧REVIEW_SOURCE_POLICY_NOT_READY不证明新141谓词失败；完整新工作稿未生成 |
| 更正与历史 | 正式UI一次有源描述更正、Profile3→4、旧记录hash保持 | 该更正0规则关联；不是新完整审核结果重算，新旧审核报告闭环尚未达 |
| 共享首屏适配 | 184bdb60已提交入排侧来源绑定/返回；共享首页未改 | 合成接入不等于真实跨系统与Q3，不重复派工 |

病例根/准备副本：/Users/smkzw/tmp/enrollment-rv1001-case-source-consumer-20261006-v2/rv1006-prepared-review-current-node-20261008-v1/data；subject rv29-preparation-20261001，筛选episode e8615813d75b452489579ff9606781b4。

## 3. 当前首错与最小修复

442实际范围補核已成功，目标对应修正也合法：不是模型无响应/JSON坏格式。旧候选引用了同一行，但time_words多个组成词未被识别为一次有源访视，导致未选择已有alignment。现在以整行、唯一标记列、全部物理表头和决定节点证明对应；分格摘录不伪装成整行出处。仅填action候选，不直接expressed；已有alignment还要核资料限制/关联/脚注含义。原文数字逐字保留，比较词仍须数值predicate。1250pass/108.29秒相连三模块；末比较词/政策族32pass/1.17秒，不累加。C03首/续只读293.349/117.301秒、exit0/no fallback，首17工具超8，无测试/临床，末增量由所有者验证。取舍reviews/rv1006-native-visit-correspondence-owner-disposition-20261008.md。同行多个候选仍不自动选择，表头脚注全局含义未证明；真实候选可能真的不完整，不能为变绿改政策。新合法恢复尚未执行。

### 以下为之前局部恢复的历史证据

最新b9实际执行scope纠正，但模型在JSON字段间插入自我修改文字；未应用来源。只对json_invalid重交一次原范围，扣同source_repairs，错误ID/来源/字段/传输不借此扩读；最后仍技术失败，新码贯通实际服务，受限消费者拒绝。有效后才能过原来源及一次目标门。v4恢复身份，旧成功重验/旧终态保持。全历史scope计数完备性仍是既有残余，不称已修。三模块1224pass/1fail102.85秒，旧v3断言修v4后单项1pass2秒；不冒称末版全三模块。C03同会话8静态读取/exit0/no fallback，无必须修，未读临床/跑测试。取舍reviews/rv1006-scope-json-recovery-owner-disposition-20261008.md。新产品恢复尚待从b9合法入队；以下为原v3及更早快照。

a7de实际初答缺unresolved_aspects且未写时间，局部格式纠正才提真实原生时点。v2仍依赖模型先说时间，未运行scope修正。v3只依据冻结结构中的有源共同标题和尚未解释的来源范围选择既有scope修正；不依赖核对者措辞或错误顺序。旧一次目标纠正/source_repairs预算保持，原句/用途/例外/兄弟不改，错误目标仍完整拒绝。已有scope/stage/time任何一个不空不由此扩写。

1220passed/100.75秒/exit0/5SWIG集中三模块；17窄窗是选择断言前快照，末集中窗覆盖新增断言。不累加。C03同CodeBuddy/DeepSeek/max会话91.262秒/exit0/no fallback、120min静默完成等待，9次只读，未测试/未临床。source_scope修复不能证明脚注完整含义：所有者只读核完整冻结清单有相关表头脚注原单元，但未进入此行局部上下文；完整包及依赖门仍不可绕过。合法未决首答不触发这条失败恢复，是明确残余，不宣称上游解释已全面修复。报告/取舍见reviews/rv1006-native-dependency-order-owner-disposition-20261008.md。validator v3，只升级局部恢复身份，不反算历史。

以下v1/v2为历史反证，按各快照理解“现/未执行”，不覆盖本节：

065e实际运行揭示前一修复未执行：初答先报UNRESOLVED_ASPECTS_MISSING，同答已有真实标题格时点；一次目标纠正后才报SOURCE_TIME_UNGROUNDED，同条机会已用完。只按错误代码选择scope修正错误地依赖校验顺序。现来源scope/stage/time均缺且核对时点恰为原生完整标题格/列时，先以原有scope修正核依赖，再使用原来的一次目标修正；既有范围不改写、假时点不送此路，不加调用上限/重试次数，不放宽源/目标门。15项窄窗包含这个真实顺序的合成复现及非原生时间反例通过，集中检查按implement记录。控制流修订由所有者直接做，先前C03报告仍仅覆盖当时版本。validator标记升v2，旧来源、Schema和编译器身份不反算。

以下v1功能包结果为历史，不能据其“未执行”重跑原目录：

9d91真实运行已送达原生表格位置，出现新的明确首错：17第5条来源解释scope/stage/time_words全空，但唯一标记格的完整原生表头明确给出时点。核对者保留该时间被SOURCE_TIME_UNGROUNDED正确拒绝；不能删时间让错误解释通过。native_schedule_time_excerpt_is_grounded仅定位已有scope修正入口，要求整行摘录、全部标记列有源且无访视/标记脚注未决，完整原生标题格/整列标题等值，不从“期”等子串推断范围。模型仍须单条提出范围/阶段/时间、通过原来源门、再核目标；兄弟/动作/用途/例外不改。共享source_repairs限制与同条一次修正不清零，故障/重复错误保留草稿，不自动采用。

当前三相连模块1215passed/100.45秒/exit0；末整格等值加固13passed/1.06秒/exit0。前窄窗夹具必填/恢复参数/恢复权限错误单列implement，不累加。C03同会话79.969秒/exit0/no fallback，静默120min完成等待；只读工程未测试/未临床。采纳子串风险，以真实格对应修，未照抄按空白拆词。先前全局source prompt已有表格context但缺逐成员关系，不能照顾问文字说完全无表头。validator追加native-table-scope-recovery/v1；基础提示/Schema/旧历史摘要不反算。新合法接续尚未执行，先现场前置重验，保留上游来源链。

下列为前一功能包已证成果（不归到本次新修订）：

17原生行标签/X/表头已在batch，但reviewer仅收到平面摘录，无法核位置；补只读native_table_source，含真实source_ref/span/member refs/格路径，不把位置当覆盖证明。21合法候选各引用不同标记格而候选级整行来源缺失；精确原子引用验证后宿主补所属整行完整出处，sorted-unique、复制输入、幂等，原子/逻辑/时点/政策不动，越界/伪造原文仍拒。无需关闭TABLE_ROW_SOURCE_CLOSURE_PARTIAL。

先前草案两项compiler标记会使全部成功结果失效，已撤回未提交设计。当前只升级结构validator identity；原采用门本来要求同一整行闭包，不改语义编译。18份真实已完成partial_wire按当前编译重放与旧final_output完全相同，1受限结果当前重推相同；旧compiler/schema/source/route拒复用反例保留，不加白名单。当前预检19/2/69。关闭既有可选continue-after-unresolved才能让17实际复核；若保持True，预检会preserve_unresolved，已识别，不静默继承。

最终三相连原模块1203passed/96.30秒/exit0/5SWIG，JUnit artifacts/rv1006-native-table-consumer-connected-20261008-v4.xml。v3为1202pass/1fail109.71秒，新增非首span正例夹具内部来源错误；其后两个5pass1fail窗口暴露冻结赋值及候选原子闭包不一致，修夹具不松门。6个最终局部例0.76秒exit0，不累加。首v2为1198pass4fail新增构造问题，文件名诊断exit4无测试。独审CodeBuddy/DeepSeek/max/session01a11c53-1d24-71c2-8a28-568da7aaea2e，首194.256秒、续86.082秒/exit0/no fallback，120min静默完成等待。采纳排序缺陷；末审未见必修，不等于已运行测试/临床。首审约13读超10预算，续审实际hash落点未读到，所有者原请求/回执继续私有保留。详见同名reviews/metrics。

### 上一功能包（历史证据）

1. 已引用动作因时期未证明而没有action_candidate_indexes，原防重复插入条件永远不满足。C最小修复以同单元、原span交集及逐字摘录限定候选引用，进入已有SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED；不把引用当临床已表达，兄弟不能仅凭同单元被拦。
2. 表格引用的真实脚注未送给来源读取。B复用已验证原生snapshot及表后编号解析，将编号→原单元关系冻结于Job，预检和closure共用规划；脚注只读、自己的发现处置不变，不借另一流程项解释，不改覆盖清单/旧原件。
3. 旧新版兼容看实际batch材料，而非新字段导致全量失效。真实只读预检15可复用/75需读取：已完成1–15重验通过，16新增脚注重读，17起未完整。原因14完整材料重验、1受限重验、1规划变化、74未完成；没有整体prompt/component失效。
4. 资料页收紧已读状态/重复抬头/孤立操作空白，保留失败与待核提醒；项目名称省略但完整title可查，没有临床门变更。

具体所有者取舍、残余与调用证据：reviews/rv1006-source-context-loop-owner-disposition-20261008.md。不新增框架、疾病阈值、A/B伪造或采用捷径。

## 4. 上一功能包验证与独审边界（非当前补丁快照）

| 验证 | 实际结果 | 范围 |
|---|---|---|
| C三原模块 | 1125passed/101.66秒/exit0，5SWIG，artifacts/rv1006-source-citation-stop-connected-20261008-v1.xml | 在B之前，不冒称B末版 |
| B五相连模块 | 1135passed/116.31秒/exit0，5SWIG，artifacts/rv1006-native-note-context-connected-20261008-v2.xml | 编号/续行/科学计数/背景/越界、实际payload→closure→preflight同hash及历史不变；不是全临床验收 |
| 末说明修订 | test_protocol_control_generalization.py 31passed/0.46秒/exit0 | 改脚注归属说明，未无谓重跑全库 |
| B首窗 | 1130pass/3fail/114.40秒 | 两测试尾断言误放、桥接合同未接context，修断言位置和合同，危险反例未删 |
| 前端 | 四组件模块60passed/10.86秒；TS+正式Vite build exit0 | 既有chunk警告，非全部前端或Q3 |
| 真实预检/审计 | 0模型/0写，DBhash保持；6763/9997来源提示字符、10885/14973 UTF-8字节，token未知 | 不以字符估算代用量，不宣称新版已执行 |
| 独审 | CodeBuddy/codebuddy-cli/deepseek-v4.1-flash/max，session01a11c13-8595-7ee1-b8cf-9efb0e066a4e，初158.46秒、续228.167秒/exit0/no fallback | 120min完成等待，主线程静默；仅源码、无临床/测试。续轮18工具/解析结果0，不能称医学批准 |
| Ego Lite | space147真实非Mock资料页，1920×1080/2560×1440/3840×2160，顶323px，均无横向溢出；选择来源、全文开关、缩放、返回正确个例 | 临床截图仅本机；旧规则准备库，不代表完整新链/签发。专用只读63305已TERM、session66572 exit143，共享服务不动 |

首次B预检contract错误、私有脚本PYTHONPATH/import错误、Ego过时元素/不支持选项单列工程诊断，不归因模型。有效历史测试不删除，重叠结果不相加。

## 5. 反思与残余

支持的解释：来源未完整送达与宿主补入条件相互放大，重试不等于更多医学信息；先无调用复现、补实际来源，再局部重验，比反复整本新作业更有据。替代解释：模型仍可能在新增上下文后遗漏临床时期，不能以此次软件测试断言模型已解决。

仍未证明：v3修订后17/21实际恢复、完整90组、同源共同发布、真实新工作稿与更正后新报告、独立留出/Q3/恢复验收。上游完成19和当前完成16分开。协议库尚无project/subject，病例准备副本是旧81组件项目；最终须经合法首次发布/新个例上传或既有有据迁移入口汇合，不能SQL拼身份/借旧规则验收。C摘录含相邻动作时可能保守待核；列标题脚注/拆表/缺续行有残余范围缺口。原答及位置不得以schema通过代替医学核实。

## 6. 连续接续（不是暂停点）

1. 当前原生对应、相连验证及C03已完成，真实终态源改为442ede7a…；通过既有control-executions API合法新建前核已保存19/2/69计划与当前组成，新OUT不得覆盖。1–16/18–20须当前门重验后复用，17已核完整范围/旧草稿及21解释接续；不复活失败Job、不重置原账本。已有候选须真实alignment，已知政策/关系差额不能标签采用。
2. 按1006窗口保留局部真实未决和能力缺口，不让独立结果饥饿，但已知错义/未读来源不能换标签发布。失败两次无新信息停止该分支，推进可独立节点；不复活旧Job，不重置历史调用。
3. 同源完整采用合同成立后接当前节点工作稿→确切原件→UI有源更正/补证→相关重算→新旧结果。窗口完成先回交，不扩模型横评/新框架。

规则共同发布/激活、数字正式自动采用、临床签发未授权自动放行。当前0新共同发布/激活/签发；Goal保持active，任务未完成。继承7份旧delivery dirty及大量未跟踪材料不stage/clean，原件/旧报告/失败hash不改。
