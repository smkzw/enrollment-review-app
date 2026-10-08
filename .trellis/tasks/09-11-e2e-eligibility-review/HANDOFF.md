# HANDOFF｜1006V1｜原生脚注读取与防重复补入已接线，继续执行

2026-10-08，用户已解除暂停；Goal实查active，Trellis in_progress，execution_paused_by_user=false。窗口未达，claims_complete=false。本记录是相连功能包里程碑，不是暂停。只维护本HANDOFF、implement当前表及review_index；历史运行在implement附录和Git保留，不按旧“当前/暂停”恢复。

## 1. 用户动作与身份

真实资料页已改善：能在紧凑抬头下连续查看24页原图、切换文件和原始文字、缩放并返回正确受试者。尚未在完整新官方＋跨章要求下生成该例工作稿，也未完成更正后的新审核报告。

| 身份 | 实际值 |
|---|---|
| 唯一工作树 | /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile |
| 分支/任务 | codex/phase5-clinical-facts-profile；.trellis/tasks/09-11-e2e-eligibility-review |
| 本功能包基础代码 | 4e5edf3c2d25a3bc990711028017c81ebbdf74ca；当前修改清单以Git受限提交为准，不追文档自身hash |
| 当前终态/上游 | e5c95389e6c84bbb944e14302692cfd0，failed_final；声明上游add37084f6704cbc9421e8715f7ee6c6 |
| 末检查点 | d8b1537c971144cbaa27dd2f200e655b；原答、partial_wire、5份来源疑问及14累计attempt记录保留，非14新增调用 |
| 产品模型 | 官方OmniRouter/cms-router/glm-5.3-flash/high；跨章Ollama cloud/deepseek-v4.1-flash/high、65536输出；产品harness直接访问端点 |
| 当前隔离库 | /Users/smkzw/tmp/enrollment-rv1001-official-continuation-20261003/rv1006-relation-field-source-resume-20261007-v2/data/enrollment-review-v2.sqlite3 |
| 最新已执行产物 | 同上根目录/rv1006-source-insert-delta-recovery-api-20261008-v1；12物理调用/509.424768秒/exit3 |
| 私有预检/审计 | 同上根目录/rv1006-native-note-context-preflight-20261008-v1.json、rv1006-native-note-context-audit-20261008-v1.json |
| 外部可复查范围 | Git源码、合成测试、净化工程报告/索引；原件、DB、实际临床提示/原答与截图仅本机可读，不提交，hash不证明临床含义 |

五分钟入口：本HANDOFF → implement当前表 → delivery_1006V1/03_ACCEPTANCE.md → review_index_20261006_1006V1.json → 新合法作业prepare/execute回执。不要重读全部历史，不复活旧失败Job。

## 2. 同一流程的实况

| 用户节点 | 已证 | 未达 |
|---|---|---|
| 完整有源要求包 | 内置DOCX官方Job1153e25b4eba40db964202a1c3ed07c3草稿修订21，23父条/86组件/141谓词，publishable；85发现/90深审计划冻结 | 最新实跑16完成、17失败、73未读，scope/hydrate/gate依赖失败。publishable不是共同发布 |
| 资料与事实 | 继承5文件24页/14组实际保存，458候选→407事实/40事件/11暴露；32资格候选关联30合格事实、426受限 | 不同分母非准确率。手写对象/数字位置仍有具体未决，新完整要求消费未证，不授予自动事实采用 |
| 工作稿与原件 | 既有冻结计算/资格消费者，Ego真实原件导航；已收紧重复抬头及大空白 | 病例准备副本仍旧81组件/0controls；旧REVIEW_SOURCE_POLICY_NOT_READY不证明新141谓词失败；完整新工作稿未生成 |
| 更正与历史 | 正式UI一次有源描述更正、Profile3→4、旧记录hash保持 | 该更正0规则关联；不是新完整审核结果重算，新旧审核报告闭环尚未达 |
| 共享首屏适配 | 184bdb60已提交入排侧来源绑定/返回；共享首页未改 | 合成接入不等于真实跨系统与Q3，不重复派工 |

病例根/准备副本：/Users/smkzw/tmp/enrollment-rv1001-case-source-consumer-20261006-v2/rv1006-prepared-review-current-node-20261008-v1/data；subject rv29-preparation-20261001，筛选episode e8615813d75b452489579ff9606781b4。

## 3. 本功能包首错与修复

1. 已引用动作因时期未证明而没有action_candidate_indexes，原防重复插入条件永远不满足。C最小修复以同单元、原span交集及逐字摘录限定候选引用，进入已有SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED；不把引用当临床已表达，兄弟不能仅凭同单元被拦。
2. 表格引用的真实脚注未送给来源读取。B复用已验证原生snapshot及表后编号解析，将编号→原单元关系冻结于Job，预检和closure共用规划；脚注只读、自己的发现处置不变，不借另一流程项解释，不改覆盖清单/旧原件。
3. 旧新版兼容看实际batch材料，而非新字段导致全量失效。真实只读预检15可复用/75需读取：已完成1–15重验通过，16新增脚注重读，17起未完整。原因14完整材料重验、1受限重验、1规划变化、74未完成；没有整体prompt/component失效。
4. 资料页收紧已读状态/重复抬头/孤立操作空白，保留失败与待核提醒；项目名称省略但完整title可查，没有临床门变更。

具体所有者取舍、残余与调用证据：reviews/rv1006-source-context-loop-owner-disposition-20261008.md。不新增框架、疾病阈值、A/B伪造或采用捷径。

## 4. 同版本验证与独审边界

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

仍未证明：新版真实第16/17组、其余完整深审、同源共同发布、真实新工作稿与更正后新报告、独立留出/Q3/恢复验收。C摘录含相邻动作时可能保守待核；列标题脚注/拆表/缺续行有残余范围缺口。无映射不是“没有脚注”的证明；实际首阻断出现时再作最小修复，不预先新增平台。

## 6. 连续接续（不是暂停点）

1. 冻结受限源码及显式线路，通过既有control-executions API从e5c95389…合法新建；新OUT不得覆盖。1–15仅核合格证明复用，16起按真实新context读取，成功/失败/未读分别记录，沿既有共享账本。
2. 按1006窗口保留局部真实未决和能力缺口，不让独立结果饥饿，但已知错义/未读来源不能换标签发布。失败两次无新信息停止该分支，推进可独立节点；不复活旧Job，不重置历史调用。
3. 同源完整采用合同成立后接当前节点工作稿→确切原件→UI有源更正/补证→相关重算→新旧结果。窗口完成先回交，不扩模型横评/新框架。

规则共同发布/激活、数字正式自动采用、临床签发未授权自动放行。当前0新共同发布/激活/签发；Goal保持active，任务未完成。继承7份旧delivery dirty及大量未跟踪材料不stage/clean，原件/旧报告/失败hash不改。
