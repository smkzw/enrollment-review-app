# 0.2.0 当前交接

更新：2026-10-15。Goal实际active，**不是暂停、正式验收或全产品完成**。源码cd18a4d3已部署；真实31001最新工作稿v36，沿已存125关系复验复用，新增临床模型调用0。M1集中自查仍有时间范围问题：24页处理完成，但按8/8筛选开始锚点只将22页交给关系核对，8/15复查被排除；已提请一次范围裁定，不能靠重读解决。完整后端回归1970.04秒exit1，相对WP0新增失败0，既有249失败/错误ID保持；完整前端911通过。claims_complete=false。

## 1. 五分钟入口

- 唯一树：/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0，dev/0.2.0；主checkout及phase5旧树不能替代。
- 源码HEAD：cd18a4d3e9f0c8382f0d5544fe613fd2e793d2aa；前一源码734998ee7d0e5396cb449d226872bf629792d8fb；前一已核远端94f06949517e1594f105d560e7dd4d4cc850a0cc。文档提交身份看git log；本轮push与远端读回保存output/wp4-consumer-push.log及wp4-consumer-remote-head.txt，接续时仍须现场核对；不要将文档HEAD称运行源码。
- 只读本树AGENTS、01_PRD／02_DESIGN／03_PLAN／04_ACCEPTANCE／05_PROGRESS。archives是0.1.x历史，不注入旧授权、Phase、预算或长链。
- 从05的当前WP接续，不重跑方案、变量建议、既往53次抽取、已处理24页、125成功关系、已终态v32–36。历史调用、错误和原答均保留，不筛选有利回答。
- 构建者自主走验证流程，用builder_verification；正式医学经理审定及最终验收不代签。用户已经真实批准规则7，未改条目不重复请求批准。

## 2. 当前现场与精确身份

| 层 | 实际状态 |
|---|---|
| 产品 | 医学人员／监察人员的信息和风险展示，不是最终入组决定、反馈或事无巨细留痕平台 |
| 服务 | 61134，PID84383／exec16038，cd18源码；显式本树.env／data_v2；output/wp4-consumer-integration-server.log |
| 服务历史 | 自有68998／21622、76651／66568已TERM并收回143；共享8001/8900等不操作。旧查询串build=03d0a84f不代表当前服务器版本 |
| 数据 | WP0验证副本data_v2/enrollment-review-v2.sqlite3，约16GB；没再复制大型库、没有修改原临床库或原件 |
| 项目 | draft-project-1153e25b4eba |
| 规则 | ruleset:draft-version-1153e25b4eba:phase_iii revision7；64有效medical_manager审定；verification_only=false；原草稿rev21及旧发布保留 |
| 个例 | subject58ff71df0cff4a2c9107be743d82584b，31001，中心31 |
| 节点 | b843b2c07d6d4318a6df741eb7902eb3 revision8，筛选／导入期，screening_date2025-08-08；尚无独立结果截止字段 |
| 资料 | snapshot c69c297a3ea84c57a8fa953e07567b1d；complete-ad2f258d2aff46a98affc99dfac3ea78；5份24页、125物理事实／122冻结当前事实，0结构化事件／暴露 |
| 档案 | Profile7 profile:72808cf0f4a7f6310e17f66952a4b537；原事实ID、旧Profile不改 |
| 最新工作稿 | review-run:8883771dcba54ec7a1f13b572fc59d65（保存v36）；Job9074748dac864d7ca509ffbc82ab8c1c completed3/3；计算work-draft/0.2.0-v33 |
| 上一工作稿 | review-run:64af84b9a5b84cc395c3daa5a0984bc0（v35）；Jobd96410bba8f14692afb4cf85b4c1ba26 completed11/11；最新supersedes它 |
| 再前版本 | review-run:1c2b83e3c17d43769516b951a09bb0d3（v34），Job18bb37c1e29041b69515efd54a523148；旧v33 review-run:03754ec576c04698b9e2997e87fb1db2。全部保留，不重跑 |
| 结果 | 64父／85子＝149项；5入选满足、9排除未触发、21操作满足、15未到期、5不适用、8未决、1系统问题；待处理仍9 |
| 其他来源提示 | 28未采用原件提示独立于1规则系统问题；ReviewRun内29系统／来源记录，不与UI的1混分母 |
| 新核实 | 仅IN01父项高置信及builder_verification。看到原图51岁／生日再选“仅作试用核实”；仅4元数据字段改变，148无关项与所有结论／来源不变 |
| 当前Job | 最近只读62completed／139failed_final／6cancelled／3waiting_user，0queued/running/retryable；旧终态保持 |
| 模型角色 | 病历关系cms-router/glm-5.3-flash high65536流式经OmniRouter；规范化ollama-cloud/deepseek-v4.1-flash high65536，本月额度失败保留。默认角色及.env未改 |

用户最新允许生图造测试源：只作明确虚构的工程材料，独立TEST001／离线期望，不进入真实31001、IE或D001。不能把“生成成功”“图像好看”“来源文字可读”称临床批准或医学金标。

## 3. 这轮实际修改与首错

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

| 窗口 | 真实结果／证据 |
|---|---|
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

已经一次提请：按本次完整筛选／导入期资料（含8/15复查），8/8继续作时间窗开始锚点；或严格8/8当日。该问题**替代**先前仅一次GLM重核HBV页的提请。未答前不凭旧请求的回复启动新调用，不扩大真实资料范围、不自动激活规则或签发。

若确认全筛选资料：先以现有冻结范围／节点合同区分时间窗锚点和审核资料范围，保护真实基线／另一节点；仅重算／取证受到新增来源影响的要求，先证明旧成功源可复用。普通结构表示错误离线修，不用整例重读。若维持当日：准确显示该截止、保留复查供对应后续结果，不能把已有资料说成整例缺失。

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

1. exec61117终态已收回，当前源码及WP0失败ID delta新增0；当前前端911无需又测未改文件。先核服务及Job归属，沿v36接续；原v34/v35/核实Job均completed，不重复运行。
2. 审查两源码提交和仅两份当前文档的diff，git diff --check；显式stage，正常commit/push dev/0.2.0并核远端，不能提交output／.env／临床库／原件／原答。push不等于医学采用。
3. 若范围答案到达，按上述分支继续现有产品链；健康已completed Job不重派。若外部条件仅阻断某支，继续独立工作，不自行pause/complete Goal。
4. 真实更正／补证仍沿正式UI，保存→受影响重算→新稿→旧稿回看；不依赖手写JSON或人工补模型答案。Profile、签发、工作稿核实、临床采用与验收各分层。

战略判断：这轮没有证据支持再换框架或增加Agent。首因集中在范围和消费者：未消费的参数被误计入身份、未知标签被当患者矛盾、独立要求被藏进一句“尚不足”、筛选开始锚点被兼作截止。先修真实用户动作的生产→保存→消费→UI，比一处提示补丁后整例重跑有效。

反证和局限：零模型更新仍需54–93秒，保全和现有16GB库查询不是瞬时；一次短写锁后正常完成，不应重启健康任务。两次完整测试窗口中首窗出现4旧fixture实参问题，属于构建检查成本，不能归因患者或推成模型不可靠。技术系统项减少而待处理仍9，说明这轮主要改善表达和分类，不证明医学判定已完善。当前时间范围问题需明确业务含义，而不是继续堆恢复逻辑；M1未验，不能用新文档代替真实临床闭环。
