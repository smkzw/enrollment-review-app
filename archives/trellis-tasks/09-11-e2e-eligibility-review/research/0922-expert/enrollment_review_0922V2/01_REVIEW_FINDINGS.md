# 0922V2 代码审阅与纠偏

## 一、已经改好，应保留

- F02：投影已调用 `pair_direct_selection_rejection_reasons`，不再只凭 structurally_valid + dual_agreement 放行。（S02）
- F03：不再从全库最近5条挑任务，开始比较完整authority字段；原“其他病例新增5任务使结果消失”缺陷已移除。（S02）
- F06：投影HTTP非200或返回error信封现在明确失败，且创建受试者冲突不再静默复用。（S08）
- F07：增加混合媒体清单、哈希副本及源码树外默认意图，但实现仍有本轮发现的运行错误。（S07）
- F08：组级严重性已取最高档，交换成员顺序不再改变组严重性。（S10）
- F09：有分点DOM、建议动作，无已采用事实时能浏览原件；默认选择开始考虑问题组。（S10）
- F10：响应声明的模型名进入主记录，较只记请求名改善，但未完成身份验证。（S05）
- 当前watch脚本已不硬编码旧明文密钥。控制台撤销/轮换未有独立证据，安全项不可关单。（S09/S01）

## 二、发现登记

### R2-01 / P1：单配对可用不等于整条条件可计算
证据：S02、S03；离线P04–P07。

投影调用单配对拒绝检查后，直接以fact_id填入映射，丢弃配对的fact_attribute、配对身份与
整条条件选择语义。没有调用正式路径中的 `_select_facts_for_identity`、
`_select_with_ordering` 或与之等价的整条件内核。

对照复现：
- 只有date_range配对可用：投影得到f1；完整选择返回no_usable_qualified_pair。
- value可用，但该条件的event date未获得资格：投影得到f1；完整选择返回
  event_date_not_qualified_for_selected_value。
- single政策下两个可用观察：投影得到两条；完整选择返回multiple_usable_pairs_without_selection_policy。
- 同一观察的value与date均通过且single：完整选择正常得到f1，这是必须保留的正例。

风险：只核实了日期却使用数值、未核实日期却用它算时间窗、未完成多观察选择却混入求值。
这是选择层可复现差异，不是已证明真实个例最终误判；最终计算/发布可能另有保护。

修复：抽出或复用完整的、无授权副作用的选择内核；草稿与正式结果在证据语义上共用，
发布权限分层。输出保留selected pairs、fact attributes、qualified date links、selection policy、
accounting scope、ordering/repeat/frequency/proposition结果及未决理由。不要直接绕过正式采用授权。

### R2-02 / P1：全部拒绝被折叠为None，可回落旧类别匹配
证据：S02、S04；P08–P09。

loader在所有配对拒绝/没有值时返回None；调用方又过滤掉空映射并折叠为None。
`_evaluate_atomic` 在未配置observation_policy的条件中，收到None仍走旧fact_type/alias路径。
因此明确被资格检查拒绝的事实，在这个条件分支仍可能再次成为值比较候选。

P08只复现到“被拒事实重新到达matching集合”，不宣称穿过所有门禁形成了最终临床结论。
有observation_policy的条件会受其早期检查保护，不应把漏洞扩大为所有条件必然错误。

修复：用显式状态区分not_run、stale、rejected、incomplete、failed、ready。
拒绝/未决不回落旧类别匹配；保留显式空选择和unverified_predicate_ids。
迁移中的旧记录可读，但不能被新资格结果的缺失偷偷激活。

### R2-03 / P1：HANDOFF的400根因尚未建立，描述的请求与源码不一致
证据：S01、S05、S06；P10。

HANDOFF把完整请求描述为包含response_format=json_object，并称小图/文本成功已排除
参数格式问题。但当前 `page_completion_options('opencode-go',...)` 返回{}；已读
`_direct_openai_completion`没有为该provider增加response_format，也未注入watch脚本使用的
x-opencode-session头。无法据此知道本机实际运行是否有未提交适配、代理注入或不同实验脚本。

这不是证明少一个header就是400根因，也不是证明服务有/没有大图限制。
400仅是失败现象；HTTP定义不把它限定为图像超限。模型、字段组合、思考参数、预算、
图片编码/尺寸、stream、端点协议、会话头等需要同一产品客户端下控制变量。

修复：先保存净化后的实际请求合同与错误code/message/param/request_id，再做单页矩阵。
一页稳定通过实际合同后才扩到3–5页、25页。禁止为同一确定性400不停重跑整例。
保留当前用户已配置模型；只有能力确实不支持/服务不可用并有证据时才提出替代。

### R2-04 / P1：前端未使用变量违反构建配置
证据：S10/S12/S13；P18、evidence/tsc_no_unused.txt。

`buildEligibilityIssueGroups` 新增的 `severityOf` 定义后未使用。
项目noUnusedLocals=true，build先tsc -b。独立TS片段在相同检查开关下报TS6133。
使用编译器是5.8.3而非仓库声明7.0.2；不是本轮实际跑完整npm build。

修复：删除死变量或实际统一使用严重性函数；不得关闭noUnusedLocals/noUnusedParameters。
同时删除loader return后遗留的旧双一致选择死代码，避免接手者误认为有两种生效策略。

### R2-05 / P1：规模集默认路径会NameError，回退路径也未二次校验
证据：S07；P01/P02。

`import os`只在main函数局部，但 `_escape_repo_path` 用全局os。默认out位于repo下时
触发NameError，恰好阻断F07声称的默认安全路径。
把os加入正确作用域后仍有第二个问题：SCALE_SET_DIR若指向repo内，函数直接返回该
替代路径，不再次验证，仍可能把真实资料放回源码树。这个第二复现专门注入os以排除首错。

修复：模块级导入；所有入口/回退路径resolve后统一验证，兼顾symlink、绝对/相对路径与
.git worktree公共源码位置；不静默选择危险目的地。输出应为独立run目录。

### R2-06 / P1：混合媒体只被列入清单，未进入完整验收分母
证据：S07/S08；P03/P16。

图片pages保持None，total_pages仅加PDF页数；纯图片病例可以显示0页。TIFF多帧没统计，
图片也没有实际解码检查。媒体类型由扩展名机械拼接，需规范JPEG/TIFF MIME并按解码器能力
处理HEIC等，而不是文件被列入清单就声称已支持。

规模驱动虽拒绝错误信封，仍接受HTTP200且clauses=[]；未核对expected clauses/controls、
实际处理页/可用页/失败页，也未核对返回subject/episode/rule/snapshot完整身份。
脚本明确没跑binding/qualification/publication，不能称完整入排审核验收；新患者的绑定
更不可能是上传新事实之前已完成的前置条件。

修复：输入页/帧数与状态分开记录；未知写unknown，不遗漏或伪造。检查所有API响应合同。
在持久作业中确认完整修订构建/激活、资料核实、规范化、审核上下文、资格与投影的依赖；
未实际验证的阶段标not_run。技术阶段成功和医学结果完整性分别验收。

### R2-07 / P1：记录返回模型名仍不等于验证身份
证据：S05；P11。

`model=result.response_model or route.model`把缺失响应模型悄悄补成请求模型。
任意不一致响应直接存入model，而没有声明允许的别名/模型改变策略；requested_model只进入
identity hash材料，没有成为主记录的独立显式字段。API模型字段本身也只是服务声明。

修复：分别保存requested_model、reported_model(允许null)、resolved_identity、
alias_policy_version和verification状态；合法登记别名可通过，未知或未批准差异不得冒充
核实完成。补齐流内身份变化、回执、恢复、覆盖选择、序列化兼容与执行合同版本。
不以字符串相似度或or回填证明双读独立。

### R2-08 / P2：组严重性修了，成员排序与真正根因仍未修
证据：S10；P17。

组严重性现在取max，但组内clauses保持输入顺序；默认`groups[0].clauses[0]`可能选中
同一高风险组的低优先成员。调换顺序会改变默认项，独立Node复现。
按gapType分类仍被叫“根因聚合”，不能证明两个不同日期/来源的缺口可由一个动作解决。

修复：同一确定性排序同时用于组、成员、默认项、上一/下一项；gap类别与issue occurrence
两层区分。真实问题根因需绑定对象、观察、时间、来源和动作范围，未证明同根因不合并关闭。

### R2-09 / P2：宽屏分配方向反了，分点仍变成三张卡片
证据：S10/S11；纯CSS比例计算，不是浏览器实测。

三栏从0.9:1.1:1.2变成1:1.1:1.1：左列表份额28.125%→31.25%，原件37.5%→34.375%。
这与限制列表宽度、把宽屏空间让给原件的方向相反。问题队列与全部条款仍上下重复放置。
新ul仍list-style:none，li各自加padding/border/radius，语义分点改善但视觉上还是多卡片；
长reason与全文规则仍可能撑高详情。

修复：同一左栏“待处理/全部条款”切换、有界宽度、可拖拽分隔；证据区优先扩展。
真正的短bullet分别表达依据/影响/动作，原文独立可展开；不要缩小全局根字号或隐藏内容。

### R2-10 / P2：版本只改对一半；无事实浏览仍与引用态混合
证据：S10。

规则修订现在标对，但“资料版本”仍使用selectedEpisode.revision，而非证据快照revision。
缺已采用事实时把pages[0]赋为referencePage，使浏览首页也进入isReferencePage分支。
这可能出现“返回引用原文/已定位引用”等不恰当文字，不是证明假红框已显示。

修复：版本来自真实实体；没有数字可展示完整/短ID及含义，不借用其他revision。
分开accepted reference、unverified candidate source、generic browsing，后两者不可冒充引用证据。

### R2-11 / P2：兄弟事实预览不是同观察证明，更不是一次更正闭环
证据：S14；P12。

当前用asserted_object相同、locator_id集合相交认定siblings。页级定位可能被年龄、身高等
不同观察共用；两个asserted_object均未知时也可相等。提示候选尚可，不能直接称同一观察，
下一步更不能据此批量改值。本轮只确认preview风险，没有证据表明现在已自动联动写入。

修复：明确observation identity/属性/时间/区域/派生关系；有据联动才批量更正。
一次用户操作产生源观察修订、派生事实重建、影响闭包、必要资格重算、新审核，旧历史保留。
前端实际消费sibling_facts也须举证，不能只增加DTO就认定用户可见。

### R2-12 / P2：守望修了凭据，健康判定和终态仍未修
证据：S09；P13–P15。

KEY在cd到应用目录之前从当前cwd的.env读取：从别处启动会错读/漏读。
恢复仍仅grep finish_reason键，null/length均可能成功；规范化失败仍echo后正常退出。
长时间后台自动提交还需冻结预期的病例、资料/规则修订、路由合同，避免恢复时消费新状态。

修复：明确应用根/安全配置读取，不依赖调用者cwd；复用产品持久作业，保留失败码、
暂停/取消/续跑状态，禁止把最后一行日志当业务完成。不要因日志说它仍运行就声称已验证其存活。

## 三、不应误报

1. 冻结输入全局检查predicate_id唯一（S15），本轮不报告短ID跨组件碰撞。
2. F02单配对拒绝语义是真修复，不能再说“只看两路一致”；本轮指出的是后续整条件选择。
3. F03任意5条窗口已移除；现存全库fetchall是性能/接口边界问题，不是原bug原封未动。
4. F06的HTTP错误信封已拒绝，剩余是有效200内容的范围/完整性和未运行阶段。
5. 明文移除已做，不应再指控当前脚本仍含该值；轮换是否完成是不同证据。
6. 回执/工件读取正常不证明模型权重身份真实，模型名只能作为服务声明保留。

## 四、完成度口径

S01中的143事实、69未决、20/25成功与所有真实模型调用均是开发Agent陈述，本轮没有复跑。
P01–P18是独立片段/合成输入观察，不是仓库全量测试或临床验收。源码下载DNS失败不影响
连接器读取，但限制了完整环境构建。本轮无浏览器截图，UI结论为静态结构/CSS与排序复现。
