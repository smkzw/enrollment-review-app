# 0.2.0 当前交接

更新：2026-10-15。**Goal实际active**。源码93808b44已提交、推送及部署，含1f8d783e来源输入衔接、aa2b38de校对重建入口。353来源后台／60显示消费者后台通过，最终9文件175前端9.17秒exit0（前113/62窗口不累加），build exit0。合成购药单在Ego核类别及13OCR片段后，仅1新页GLM调用201.865秒，保存2购药事实＋1单次事件、0实际暴露；Profile3保留旧6事实，新149项稿supersedes正确。来源仍未知，未造服药起止或疗效；真实31001 v33／Profile7及旧hash不变。不是暂停、M1／M2、自动核实采用或全产品完成；claims_complete=false。

## 1. 五分钟接手

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0`，分支`dev/0.2.0`。旧主checkout及phase5工作树不能代替本树。
- 本轮源码`93808b44`；1f8d783e修文件名分类、未知类别整例阻断及结构类别未进模型；aa2b38de让当前待启用校对可从原入口生成范围性资料版；93808b44用原事实类型展示购药性质、单次事件不画持续条。前fa444cc7／b87db1da成果保留，不重做；旧271／907不归本轮全量证明。
- 现行入口仅本树AGENTS及`docs/0.2.0/01_PRD.md`、`02_DESIGN.md`、`03_PLAN.md`、`04_ACCEPTANCE.md`、`05_PROGRESS.md`。0.1.x档案仅按07索引查必要证据，不重新启动旧链。
- 当前完成的是WP7几个衔接子包，不是WP7全包、M1验收或全产品交付。**不要重跑已终态方案解构、变量建议、53次既往抽取、24页成功证明、生化局部读取或v32/v33。**
- 构建期自主验证，不逐条要求用户批准。验证副本内模拟规则审定／发布须标`builder_verification`，正式本人批准和旧签名不变；未改条款沿实际内容哈希继承。评审A/B前次各一次完成，不把当前代码称再次独立通过。

## 2. 当前现场

### 当前功能与独立试用

| 项 | 当前事实与恢复要求 |
|---|---|
| 用户产品方向 | 信息与风险展示，不是留痕平台；不收集最终入组选择、评估理由或反馈。后台原件／出处／旧版本保持，界面只突出风险、不满足、需补证、满足与必要回源。正式方案审定不受此删除 |
| 个例最新要求 | 病史／用药是交互图，不列全部识别项；检验仅异常，正常完整明细保留按类型查询。点击点再看详情／原件。当前原文强调对应项目，可靠坐标不足则定位页，不为红框重跑OCR |
| 已实现 | 沿bd12e49f图标导航／按需原件／备选确认。时间图同对象一行、各记录单独点选；明确日为点、日期范围为虚线、明确事件起止才是持续条；近一年可恢复旧记录。真实用药6点、近一年5点；病史6记录无日期、不造时间轴坐标。33检验主层2项同排有据偏高。全部122记录仍按类型可达，风险／冲突入口不删 |
| 日期与事实边界 | `fact_display_metadata`按精确保存事实核同范围、修订、日期、对象、值／类型／单位／极性／定位，批量补date_role及同排参考比较；不改Profile hash／资格／入排。参考区间未知不能当正常，偏高不等同CS或排除。事实的月范围不当疗程；未新增事件／暴露、没有把图点数当独立采集 |
| 备选确认 | radio选择本身不写批准；保留现状须显式确认，改变方向进入原编辑器预览／保存，暂不审定仍待审。未存选择在切换条目后也阻断包含它的批量批准，无关条目可继续。组件验证实际URL／身份／哈希及POST语义；本轮未向正式v7重复写批准或另发新包 |
| 所属项目更正 | 只读加载当前已发布字典、精确事实及修订；选项不自动清空原读数／类型／单位，不直接选择派生倍数。服务核身份／类型／单位、重建相关资料要求；新旧快照同时保留变更关联，默认历史格式不变。清除关联只留档案，不暗称临床否认。预览／历史用冻结中文名称，不露内部ID |
| 独立试用 | guard C02 pi/google-antigravity/gemini-3.8-flash high，930.52秒，健康预检成功、真实身份匹配、无fallback，session01a13ab0-b226-7000-9122-88e3b1fd43e6。实际110工具开始、71Ego、29PNG查看；在旧部署97984d0c上操作Ego42/p2，主线程未抢浏览器／重部署。原报告、图与回执受控本机output/wp7-ego-conference，未提交，非医学批准 |
| 试用处置 | 确认并修复重复月份刻度、所有真正未决组默认展开、编号与数字标题分隔、报告UI／HTML／MD空标题。自身预览发现未知节点影响不能显示全零，现只留真实已知数量与整节点核对说明，不铺Profile索引术语。未采纳常驻三栏、来源未知改可信、猜姓名正则改原文；会商把3840CSS/DPR2当1920CSS的解释不成立，不据此改字号 |
| 精确文件 | `git show --stat`为当前清单；后台fact_corrections合同／API／service／repository，前端相连HTTP／解码／编辑／历史；ProfileTimeline、EligibilityWorkbenchPage、FrozenReviewReport／frozenReviewExport及相关测试；02/03/05及本Handoff。未新增依赖、DB或模型路线；旧SourceExcerpt等97984d0c成果沿用 |
| 结论核实 | 当前完整低置信确定父项可显式核实，不改变值或结论，不收集理由；未决／矛盾／系统问题、未完成子项及未核来源拒绝。先核整例来源及原稿完整性，沿既有3步Job保存新版，无模型／OCR。普通更新及整理后自动工作稿冻结核实集合，内容或计算方式变化不沿用；报告／导出保留构建者与医学经理身份 |
| 集中验证 | 本轮353来源包72.91秒、60显示/消费者89.31秒；113资料UI8.96秒、62档案UI3.34秒；build exit0。新配置带分类、旧请求原布局复验、新页故障/取消/损坏、真实Profile/API旧hash及购药类型反例通过。旧271/907及366为历史窗口，不混成当前全库证明 |
| 真实核实 | Ego42/p2看IN01原图51岁及18~75要求，以builder_verification保存。Job44d64fd…completed3/3、39.667秒；v33仅IN01父项4个核实元数据字段变，其他148项、全部结论／引用、30系统／来源提示不变；新旧报告可切换。三宽屏DPR1无横溢，不替代M2数值更正／补证 |
| 保全与服务 | 当前61134 PID68998／exec21622，本树.env／data_v2，output/wp3-source-metadata-final-server.log，运行93808b44；58131／65658已TERM收回143。0活动Job，3waiting_user原状态保留，包括单页核对生成的旧strict候选，不自动改成功。真实31001不写，原125事实／29稿等旧hash保持；未新增医学批准 |
| 下一功能包 | 合成来源分类→读取→保存→档案→新稿已接通；回到真实v33的2系统项首因只读核查，先辨来源／规则／消费者而非再读病例。真实数值更正／补证仍无新依据，不制造演示或重读24页；完整范围／禁用药及M1自查未完成 |

### 临床状态（仅追加结论核实版本，临床原值及决定不改）

| 项 | 实际状态 |
|---|---|
| Goal | 本轮工具实际active；未标complete或paused |
| 自有服务 | 当前68998／61134，exec21622，日志output/wp3-source-metadata-final-server.log，运行93808b44；58131/65658/44794/13685已结束，旧日志保留，共享8001/8900等不动 |
| 数据 | 本树`data_v2/enrollment-review-v2.sqlite3`及`.env`；WP0验证副本，非原临床库。没有重造16GB备份、改原件或旧终态 |
| 项目／规则 | project `draft-project-1153e25b4eba`；ruleset `ruleset:draft-version-1153e25b4eba:phase_iii`，正式revision7，verification_only=false，64/64本人medical_manager。原草稿rev21保留 |
| 个例／节点 | subject `58ff71df0cff4a2c9107be743d82584b`，31001，中心31；筛选episode `b843b2c07d6d4318a6df741eb7902eb3`，revision8，日期2025-08-08。基线节点未借用后续结果 |
| 资料 | snapshot `c69c297a3ea84c57a8fa953e07567b1d`；complete `complete-ad2f258d2aff46a98affc99dfac3ea78`；5文件24页，125物理事实、122当前冻结事实，0事件／暴露 |
| 当前工作稿 | Job `44d64fd9f2184938b57237177e9ab426` completed3/3；run `review-run:03754ec576c04698b9e2997e87fb1db2`，保存v33／计算方式work-draft/0.2.0-v31。supersedes旧v32 `review-run:3703b7a371644a6891dbd910dc3863c8`；原v32 Job f77d4d66…仍completed11/11，不重跑 |
| 结果 | 64父／85子、7资料或含义未决＋2系统问题不变；5入选满足、9排除未触发、21操作满足、15未到期、5不适用、7indeterminate、2system_issue。IN01父项高置信且builder_verification，仅试用核实，不是本人验收、模型金标或准确率100% |
| 新档案 | Profile7 `profile:72808cf0f4a7f6310e17f66952a4b537` succeeded，当前规则7／节点8；122原事实ID不变。旧Profile1–6不改。档案0单列问题不等于入排0问题，118来源提示不被伪装已核 |
| 更正 | 真实记录0；Ego已真实加载195可选项目，并将现有关联改为“仅保留在档案”做只读预览，中文两侧关联／原值／日期／来源均保留，随后关闭未提交。此前无变化422记录保留；都不是M2真实更正 |
| 浏览器 | Ego Lite原空间42，p1保留已发布规则，p2沿原工作台／个例。三图实际CSS1920/2560/3840、DPR1，原件交互为1920/DPR2；以对应viewports.json为准，物理屏及浏览器缩放未验 |

## 3. 已收口的衔接与证据边界

### 历史工作稿，不伪造正式报告

旧历史入口要求FinalAssessment，读取仅有WorkDraftItem的保存稿会500。现按run_kind分流，共用当前显示映射，核自身冻结规则、完整父子／REQ、真实事实定位和逐字页面引用；不读当前指针重算旧稿。API／解码／报告／原件／HTML与MD导出贯通，标工作稿未签发，不补造签发结果。

实际v31、v32各64父85子读回与存储的结论、置信、原文和来源逐项一致；Ego切旧版、IN01检验／EX01病历回源及HTML下载完成。原件无准确坐标时只定位页面，不画假框。保存结果、签发授权和医学验收分开。

### 更正保存与后续结果分开恢复

新0.2.0更正沿既有Job，冻结`work_draft_recompute`，plan→apply→work_draft。apply先保存更正及提交证明；第三步再核当前规则／节点，调用既有WorkDraftReviewService，保存子Job关联。后续失败不回滚、更正不重复发布；只重试失败第三步或子Job。旧两步任务及旧幂等身份保持。

API `fact-corrections/jobs/{job_id}/work-draft`核路径个例／节点、提交证明及子Job类型／作用域。界面等待子Job实际保存，不能用父Job3/3假称新稿完成。故障注入只证明真实存储／派发／重试，不代表已完成真实病例更正。

### 规则单独更新不要求病例整例重读

首因果错误：事实与Profile仍绑定规则3／节点3或4，当前已规则7／节点8；快照与处理修订完全相同。工作稿已经使用旧源记录，档案／更正入口却以整个authority相等拒绝，造成用户流程断层。

现在复用现有`clinical_source_scope_is_compatible`，核真实方案文件哈希、同项目／个例／节点／快照／处理修订、期别及旧变量完整定义；冻结来源损坏不能降为缓存未命中。工作稿与更正路径显式启用，**默认正式事实选择仍保持严格同authority**。档案保存真实原事实ID及原来源身份，不复制事实、不改来源强度、已核标志或原批准。

更正对已证明可复用的事实保存完整旧快照、当前新事实及追加谱系；事件／暴露不借此放宽。Profile来源读数按事实自身run／candidate定位闭包核验。成功前置读取尽量放在写入前，避免档案更新长占SQLite写锁；一次维护锁冲突已保留日志，未丢失或重跑作业。

真实UI“更新工作稿”只追加Profile7，仍复用同一completed v32 Job：0新模型调用、0新事实／工作稿，29旧ReviewRun／4369旧工作项／125事实／5资料版本及旧6Profile哈希保持。哈希只证明身份，不证明所有医学含义正确。

## 4. 当前验证与可获得材料

| 项 | 本轮结果 | 本机证据 |
|---|---|---|
| 当前来源分类与输入 | 353 passed72.91秒exit0；旧配置不变、新配置include_source_categories=true进入实际请求；未知类型可读而来源不升格，错来源/损坏仍拒。新fixture前三次失败先因相同断言合并、后揭示模型输入漏类别；没有改去重或放宽源门槛来变绿 | output/wp3-source-metadata-package.log，实际8文件pytest命令在日志与提交；早期family/release失败日志保留。1f8d783e源码／测试已推送，旧真实请求无改写 |
| 当前合成分类更正 | 原UI核类别为购药、出具方未知，原图逐项核13OCR片段，原入口生成complete-47aecc…；公开API启用evt-673340…（非普通UI启用），显式产品GLM high65536读取1新页、1旧页实际证明沿用，201.865秒/30010输入12217输出42227总量，39290思考字符与上游零思考计数不一致；费用未知 | output/synthetic-sources-20261015/source-metadata-{corrected-revision,product-read,result-audit}.json及实际工件请求hash6981574…；Job51aee8…/run48acc257…completed/partial，2事实1事件0暴露，不能把partial标全资料医学核清 |
| 当前实际消费 | Profile3 profile:749024…含旧6事实＋新2事实及1单次事件；新稿review-run:f7f9bc…149项，子Jobaf1b73…completed，supersedes475034…；没有实际服药/停药/疗效，来源unverifiable_source。Ego购药点→详情→正确购药原件→关闭回同点；三CSS1920/2560/3840、DPR1无横溢，药名加重、无伪造坐标 | purchase-timeline-1920.png、purchase-source-{1920,2560,3840}.png及purchase-source-viewports.json均已实际看；wp3-source-metadata-preservation-final.json旧hash保持。纯测试身份，不混31001、D001或M2；原合成旧稿/元数据/失败留存 |
| 当前显示接线 | 60后台89.31秒、113资料UI8.96秒、62档案UI3.34秒exit0；build exit0既有chunk提醒。按精确保存事实读回类型标签，kind/source/值/事实资格不变；泛药物暴露分区改用药与治疗，单次事件保留日期点 | wp3-purchase-meaning-{backend,frontend-accepted,release-build}.log、wp3-source-metadata-ui.log；初次前端失败是新购药fixture仍带mmHg，已按图片量单位null修，不放宽产品单位校验。2K/4K最后页完整可见时贴顶条件不可实现，图与几何证明后修验收条件，未改产品或隐藏旧页 |
| 本轮增量来源／更正消费者 | 最终366 passed208.15秒exit0、5第三方SWIG警告；涵盖原请求／回执、同／异模型历史身份、损坏拒绝、新页失败一重试、取消、零新增调用、累计档案／期望、旧来源更正与派生引用、同页不误合并。不是完整临床补证或全库回归 | `output/wp7-incremental-consumers-accepted.log`；实际命令与早期失败日志在本机output，测试源码已随本提交。前序375／142／64通过属于重叠不同窗口，不累加 |
| 本轮真实只读检查 | query_only；v33冻结上下文重新装配逐字段相同，122事实、24/24页、122档案项，0模型、0临床写入。31001给定目录5份均已上传；实际入组不证明资料完整或符合 | `output/wp7-incremental-current-context-final.json`、`wp7-source-folder-inventory.json`及对应只读脚本；不重复上传相同hash |
| 本轮合成图片 | 实际生成2图、模型身份／费用未知；不喂生成提示／离线期望。OCR两页均可读，首图GLM流式1请求561.425秒、30223输入／36667输出，保存年龄／性别／4检验；血糖不在151目标，NCS作者未知。购药1请求314.304秒、29996输入／17687输出，3候选因来源核实未完成被拦、0新事实，不造实际服药日／疗效；候选来源语义误称病历转述也不可无条件采用。旧429／timeout不改，用量未知不填0 | 本机output/synthetic-sources-20261015/expectations.json、product-results.json、原图及回执。首图6e0c472…、补图79178f0…均completed／run partial；complete-9e67ccf4b6ba427c94aeff2c0bc1f1e5公开API启用，不称普通UI全闭环。旧成功call_cac42c5342d97bffc99e692e保持；Profile1→2相同6事实，新稿475034…supersedes42148…，149项。不是31001补证、临床验收或局部视觉能力证明 |
| 本轮源码／显示回归 | 86后台43.27秒；18文件153前端12.59秒；tsc/Vite exit0，既有chunk警告。文字原句从已有source_text_range读取，其他文字折叠、不删除；0/1/101/250项、旧页失败、范围失配及原件resize相连反例保留；旧失败原答无改写 | `output/wp7-synthetic-gateway-release.log`、`wp7-synthetic-source-ui-release.log`、`wp7-synthetic-fa444cc7-build.log`；本轮首个UI失败是jsdom角色查询含折叠节点，改查实际可见性／可访问来源，不是降低分页或来源边界 |
| 本轮Ego与保全 | 实际展开／收起14条其他文字、点击购药来源回到对应文件第1页；1920/2560/3840 CSS、DPR1，均无横溢、版本操作按钮不压文字；选中页与视区顶部误差小于1px。resize前截图暴露标题／可见原件脱节，已接既有定位序列，不造坐标 | 本机output/synthetic-sources-20261015/source-final-{1920,2560,3840}.png及viewports.json；图均实际看过。设备指标仿真不是物理屏或浏览器缩放验收；`output/wp7-synthetic-preservation-final.json`核原125事实／29旧稿及4369旧项等hash保持，未提交临床原答 |
| 本轮状态文案 | 56相连前端测试9.29秒、tsc/Vite exit0；真实p3刷新后中性“查看本次资料整理结果”，未完成内容仍独立可见。去掉失实“入排匹配下一阶段开放”。未改变临床状态、底层失败或页覆盖 | `output/wp7-incremental-status-ui-tests.log`、`wp7-incremental-status-ui-build.log`；新当前UI不是前轮907完整证明 |
| 本轮结论核实 | 271 passed69.33秒exit0、5SWIG警告；完整前端102文件907 passed42.66秒exit0；tsc/Vite成功。空语义批次仍排semantic已修；合成旧来源夹具以明确typed装配边界隔离，不放宽产品发布保护；未知旧规则身份保守只作验证 | `output/wp7-confirm-backend-accepted.log`、`wp7-confirm-frontend-release.log`、`wp7-confirm-build.log`；早期夹具／排序／路径失败日志保留，不冒称临床失败 |
| 本轮真实核实／保全 | 0模型；原件→builder确认→v33→新／旧报告，148无关项及全部结论／来源不变，30系统／来源提示不丢；旧125事实／29运行／4369项／36调用／5版本hash保持 | `output/wp7-confirm-{before,after,result-audit,history-new}.json`、`wp7_confirmation_audit.py`、`wp7_confirmation_result.py`；`wp7-confirm-age-source.png`、`-dialog.png`、`-report-new.png`、`-workbench-{1920,2560,3840}.png`及viewports.json。私有材料不提交 |
| 前轮更正／历史／资格消费者 | 299 passed，91.26秒exit0、5 SWIG警告；含显式关联／旧快照、未知项目／类型／单位／派生值／错节点拒绝、实际保存／读回／资格选择及既有自动子Job恢复 | `output/wp7-variable-backend-accepted.log`；初轮缺json导入／新测试非法双fixture失败已修，旧日志保留，不能称旧产品问题 |
| 前轮完整前端 | 102文件902 passed，44.22秒exit0、2workers；曾暴露来源默认选择异步时序，新测试改为等待实际选择而不放宽断言／超时 | `output/wp7-variable-frontend-release.log`；旧894及中间901／902窗不混为当前最终 |
| 前轮正式构建 | tsc＋Vite exit0；既有chunk提示，未新增依赖 | `output/wp7-variable-build-release.log` |
| 当前独立Ego及主线程复核 | 原部署只读试用完成，报告建议逐项核实；最终实际5不同日期刻度、9未决可见，195项目与只读前后预览成功取消，三宽屏DPR1无溢出 | `output/wp7-ego-conference/`；`output/wp7-variable-{timeline-1920,timeline-2560,timeline-3840,workbench-groups-1920,preview-initial}.png`；初稿图不是最终节点范围文字证明 |
| 前轮日期／参考范围与Profile | 90 passed，78.08秒；旧Projection hash不变 | `output/wp6-chart-backend-final.log`，当前未重复跑该独立窗口 |
| 当前真实界面 | 时间图6点、近一年5可恢复，点选→详情→原件4页且药名加重，Esc回焦点；三宽屏无横溢或图点越界，图实际看过。原图无坐标不造框；无字面对应的摘录不强行标重点 | `output/wp6-chart-delivered-{1920,2560,3840}.png`、`wp6-chart-viewports.json`、`wp6-chart-source-highlight.png` |
| 当前只读保全 | 125事实、29运行、4369项、36调用、5资料版本、1快照旧hash不变；无活动临床任务 | `output/wp6-timeline-identity-audit.json`、`wp6_timeline_identity_audit.py` |
| 前轮来源／更正／档案／API及相连规则消费者 | 384 passed，142.74秒，exit0，5第三方SWIG警告；本轮未全量重跑该窗口 | `output/wp7-rule-source-pausing-final.log` |
| 前序历史消费者 | 303 passed、完整前端872；旧稿实际回源及导出 | `output/wp7-history-*` |
| 前序更正派发 | 67 passed，50.88秒；前端875，故障后只重试子任务 | `output/wp7-correction-recompute-*` |
| 最终原件／历史保全 | 125事实、29运行、4369工作项、36抽取调用、5资料版本、1快照、旧6档案全部不变，仅追加Profile1条 | `output/wp7-rule-source-before.json`、`-after.json`、`wp7_rule_source_audit.py` |
| 真实界面 | 更正打开／无变化预览拒绝／关闭；长名称收紧、档案空态不再宣称入排无问题，三视口无横溢 | `output/wp7-profile-final-{1920,2560,3840}.png`、`-viewports.json`；1920图实际看过 |

本轮实际后台命令（唯一工作树根目录，均exit0；353/60是不同、有重叠窗口，不合计）：
```sh
.venv/bin/python -m pytest tests/v2/services/test_evidence_upload_service.py tests/v2/services/test_incremental_fact_sources.py tests/v2/services/test_fact_normalization_command_service.py tests/v2/services/test_fact_normalization_source_adapter.py tests/v2/services/test_fact_normalization_executor_profile.py tests/v2/agents/test_evidence_normalizer_adapter.py tests/v2/agents/test_evidence_normalizer_transport_config.py tests/v2/api/test_fact_normalization.py -q
.venv/bin/python -m pytest tests/v2/services/test_patient_profile_service.py tests/v2/api/test_patient_profiles.py tests/v2/services/test_incremental_fact_sources.py -q
```
前端在frontend运行npm test --具体测试文件 --maxWorkers=2及npm run build；最终将五文件资料包与四文件档案包合并为9文件175通过9.17秒exit0，output/wp3-source-purchase-ui-release.log包含实际命令和文件清单，代码已推送。实际Ego沿42/p3，新当前稿显示44未决／20系统＋1未采用来源，不拿合成小样冒充正常完整个例。确认回源关闭后仍停同一购药点；原件只页级定位，药名逐字加重，无位置核实则不画红框。

上述output／原件／数据库／原答是受控本机材料，**外部审阅不可仅凭路径取得**，未提交。前序窗口不是本轮全库证明，后端全库未重跑，249基线失败只是历史。本轮初次失败分别为旧首屏／常驻原件／移动导航断言、测试夹具错误身份／分区及按钮名称定位；均保留日志，不删来源反例。实际审查另补跨条目未存选择的批量批准保护和来源选择测试。Ego截图曾因应用未在前台超时、旧ref因视口变化失效；激活原应用窗口及重新取定位解决，未新建空间或改用别的浏览器。

## 5. 未完成与不重跑清单

- WP7所属项目、结论核实、增量来源消费者子包已收口；真实数值更正和补证两次新旧稿仍未验。没有已确认真实数字错读，给定31001目录也没有新文件，不改正确值或重传相同文件制造M2；IN01试用核实、合成图片都不替代真实临床验收。
- IN03按本人D20保留对应季节治疗及疗效不足；不能拼接不同月份或节点后研究治疗反推满足。EX06/10随机锚点、筛选ANC遮挡单位、FEV1用药前关系、HBV-DNA等真实未决仍保留。EX07读取意见不一致不宣称患者记录矛盾；EX13范围、EX14流程表人群关系仍需来源核清。不要按问题减少叫准确率提升。
- WP5完整范围／禁用药能力、M1本人验收、M2/M3、人工IE对照、实际缩放及备份恢复尚未完成。D001在M3前保持留出，IE表不进提示。
- 当前是既有事实的交互时间图，不宣称已重建未提取事件；病史6项缺日期，因此紧凑列入未明确区域，不强画时间点。已存33检验只2有同排异常依据，未知项不冒充正常。文字路线不带可信坐标，页定位可用，红框渲染测试保留；不为坐标新启OCR。书面判断检索仍下钻；完整更正／实际缩放未验，不宣称全站UX／M2完成。
- 不重跑旧方案、变量建议、已成功24页与生化首读、v31/v32、已终态失败／取消Job；不重放output中旧`--save`修订脚本；不新造16GB备份或清理保全回执。

## 6. 恢复步骤

1. Goal实际active；核HEAD／dirty、61134归属及活动Job。当前68998／exec21622运行93808b44，本轮合成读取及子工作稿均终态，勿重跑。先读source-metadata-result-audit.json；来源分类子包已完成，下一包核真实v33剩余系统项的当前有源规则及实际消费首因，不换默认角色或先重开读取。新布局仅由冻结ModelConfig决定，旧请求以原参数重建。服务失去时核租约和原答，用本树venv／显式.env/data_v2恢复，不停共享服务。
2. 打开现有workbench路径，读取v33与Profile7；核实Job已completed，不重复点IN01或重开原稿。旧v32及历史保留，旧只读审计脚本会因新增run而拒绝，改用本轮wp7_confirmation_audit.py，不覆盖旧基线。
3. 时间图、原文重点、备选和所属审核项目选择已实现验证，勿重新从原型开始。部署本轮增量修订前先核自有服务和Job空闲；沿用v33，不新建病例读取。合成图片以单独标识的测试受试者走产品入口，原件／离线期望分开；不得挂31001或当D001留出。真实补证仅在有新原件时进行，不在正式v7重复批准演示。
4. 更正保存后核真实子Job、新run、supersedes、受影响结果与无关项不变、旧hash保持；失败仅重试失败范围。不要为了消除未决删来源、放宽已核或冒用用户签名。
5. 同功能包集中验证，里程碑按04与06处理，不重开全库追绿／模型横评／跨章长链。M1/M2仍须真实用户流程证据，不以文档、HTTP200或测试数量代替。

已经只读核实v33的当前首因而非凭历史估计：EX07组件25是两份读取意见不一致，保存7来源关系＋1事实引用；EX13组件03是忠实未结构化，子项0来源关系但父项仍保留10项。work_draft_review.py约417及502分别产生两类问题，不混成病例本身矛盾。output/wp4-current-system-first-causes.json为净化数量/分类记录，0新模型/写入。接续时读取这些完整消费分支和对应保存请求/原答，在来源边界内决定是否局部修复；此诊断没有核准新医学结论、删除时间限定或批准重试。

启动（仅当前自有服务已结束且端口归属核清时）：
```sh
.venv/bin/python -m scripts.run_v2_desktop --env-file "$PWD/.env" --data-dir "$PWD/data_v2" --port 61134 --no-browser
```

## 7. 本节点复盘

主要卡点已经不是“模型再读一次”，而是保存的事实、规则修订、档案与报告消费者使用不同身份和完成定义。正确解法是复用有证明的原记录、保持历史，再接通下游；不是取消身份保护、复制批准、重抽整例或增加读道。

界面不能把某一层“0问题”宣传成临床无问题。前轮虽按分类排列，仍把82条记录平铺，未实现用户要的交互图，是呈现目标理解不足；本轮按对象与真实日期绘图，异常主层收敛，完整记录下钻。没有日期就是显示边界，不借报告日推断。实际Ego又发现首个来源只是孤立日期，现保留真实框优先，其次选含当前对象的字面摘录，避免无重点长页；不改变来源资格。只有当前项目能在原文逐字对应时才着重，无对应不编造关联。

本轮产品模型调用0；工程独立试用1会话，不能写成零外部模型使用，也不能将其当产品病例读取。实屏复核发现月份刻度碰撞、默认收起待处理及报告空标题，修消费者而非换模型。最终报告30个系统／未采用记录标题0空，仍标未签发。换构建后旧页懒加载chunk404导致空页，日志核因后只刷新原p2恢复，非读病例失败、不新建空间。一个重要反证是：有文件可打开不代表来源级别已核；不要为视觉“变绿”改资格。DPR不等于缩放。测试缺导入及异步时序是本轮构建成本，不称医学遗漏、不删失败记录。

生产／保存／消费应优先接线后核真实动作；故障模拟、工程通过、来源资格与正式医学验收分别记录。当前实质进步包括可选并保存所属项目、旧格式兼容和相连资格选择；真正更正／补证闭环仍需完成。无需重开第二轮会商验证可确定性检查的显示修正。

本轮首错集中在资料身份改变后消费者只认当前修订，导致未变来源的事实／覆盖和其派生引用断开；不是再让模型读全例。修复以实际来源和请求证明为边界，旧记录不改。零新增调用反例又暴露把完整计划裁成空计划、以及同快照新处理修订未提供来源链的问题，已修并纳入正式消费者；未放宽全局计划或资格。期间几次猜测试路径导致exit4、只得到通用EXECUTOR_ERROR而缺原始异常，均是工程操作成本；后续先发现路径、捕获合成事务的首个实际异常，再集中验证，不归因病例或模型。用户实际入组不是真值，生成的好看图片也不是临床证据；必须分别报告。

真实试用的反证：OCR读出5行不证明事实提取完成；Ollama月额度耗尽后Job completed／run partial，原页面仍说“整理已完成”。现只说结果已保存；失败信息用中文展示但不改旧回执，未核文字折叠而不删除。GLM非流式2次600秒timeout后，显式流式1次561.425秒成功；仍有瞬时服务状态这一替代解释，不声称独立因果对照。单页输入84823字符／30223 token、输出36667，另报113496思考字符但思考token未可靠拆分。冻结输入151目标中无血糖，不能称模型漏读；源文字373字符、目标22446、两类条款上下文33766、前导含Schema26262字符，首先是提取范围与请求负担问题。不在增量验证途中换提示使旧证明失配，不加某检验／病例特例；真实来源、准确提取、工程采用和临床验收分别记录。

本轮把预留的结论核实表接到真实动作，不把显式核实变成必填意见或入组决定。已有原文足够的年龄条款只提升试用置信，不重新判读病史；真实剩余7未决和2系统问题不减少。前期成本还包括使用旧Phase夹具启动现行完整装配，接连暴露缺目录、节点、范围证明；改用明确typed装配边界＋实际持久化／来源闭包／Job／历史测试，不能将此称全链方案发布验证，也不放宽生产保护。Ego截图前台状态与Node绝对输出路径亦曾出错，修运行方法、保留现场，不新建空间或换浏览器。实际3步仍耗39.667秒，不能说零模型就瞬时；后续若优化，先量出来源复验与保存成本，不为性能跳过历史／身份检查。

本轮有可复查的第一因果错误：购药filename被裸record分类为病历，结构类别虽保存却未进模型输入，模型随后按病历转述写来源；宿主仍按真实元数据校验，没有证据证明其来源强度被偷偷升级。新配置明确携带既有类别、保留旧布局复验历史，避免为表示修复重读全例。实际核对后发现strict页核对候选阻断了范围性新版本入口，修的是可操作入口，不是删除风险保护。最后API泛分区把购药事实显示成药物暴露，现用精确事实类型和单次性质呈现；没有改业务值或资格。性能201.865秒比前次314.304秒短，但输入仍约3万token、无单因素对照，不能断言加速来自本次修复。生成图片是可控工程素材，不是临床金标；首图异常显示及全核心检验覆盖仍未证，真实M1/M2/IE仍需实际材料与产品流程。
