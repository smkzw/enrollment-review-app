# 工程 Review 与专家意见裁决

## 1. 审阅依据与边界

本地目标工作树和 GitHub 目标分支均为 `e7f34d0508c05481164cf13569f66ddf64e2e74f`；开始时 clean。GitHub open PR 列表为空。通过 GitHub API 核实远端提交，不对旧主分支作实现结论。
全局盘点：app/scripts 共592个Python文件、211151行，AST语法扫描无失败；app与frontend/src文件共817个。相对原交接基线4caf392c，app/frontend/scripts/tests有494文件变更，约49747行增加。大文件不等于必须拆分，但说明逐处补丁且缺消费者追踪的成本很高。
本轮逐函数核查核心生产/读取/选择/求值/更正/呈现链与专家S01–S16；不是对21万行逐行证明，也不是完整运行验收。追加授权后执行最小端点诊断（见10），未打开临床库作写入、未做浏览器视觉验收。专家离线片段不是产品全链测试，本轮不重跑其转录函数冒充产品证据。

## 2. 优先发现

### P1 / C01：工作稿的资格语义仍不等同正式计算
`app/services/eligibility_review_projection.py:865` loader只用pair拒绝检查取fact_id，未保留属性和整条件选择；同文件754–767又删除空映射。`app/services/qualified_binding_selection.py:224`实际已有value/date资格、多观察policy及287处ordering/accounting逻辑；正式路径还处理命题、频次、复查等。
`app/domain/expression.py:513`在无observation_policy且传None时进入旧类型/别名匹配。故“配对被拒→None→类别候选重入”成立，不能称F02完全闭合。尚无本轮真实个例最终误判证据，正式冻结发布有其他保护，不扩大为所有报告已错。
解决：复用完整无授权副作用计算/选择内核，工作稿与正式报告同语义，授权另层；显式空选择和未核状态不可折叠。W1。

### P1 / C02：V3新来源合同存在，但正式主路径仍强制全页双读
`page_review_job_service.py:51–74,161`总是计划A/B；`app/api/v2/app.py:273`设置require_page_review=True。`contracts/source_policy.py`已声明主OCR等政策，但全文检索未见该模块的生产消费者；page_review中新增的两个可选字符串字段不构成来源贯通。
不能宣布“主OCR+局部核实已完成”，也不能仅改False。应让真实政策贯穿计划、保存、覆盖、规范化、locator、事实发布、恢复和UI；已有selective_vision/targeted复用。W3。

### P1 / C03：前端真实构建不通过，不止一个未用变量
`npm run build`实际失败6项：labels.ts:142 ExpectationStatus、mappers.ts:164 GapCountsWire、EligibilityWorkbenchPage.test.tsx:3/250/267、EligibilityWorkbenchPage.tsx:365。不要关闭noUnused或排除测试文件掩盖接口失配。追字段的API/生成合同源头，集中修一次。W0。

### P1 / C04：宿主将生成错误改成“研究者判断”可能混淆技术与医学缺口
`app/agents/protocol_control_deconstructor.py:902–941`对非法或缺失evaluation递归补`determination_mode=investigator_judgment`，945解析入口调用它。格式不合格不证明方案要求研究者判断，最小proposition来自attribute也不等于原方案临床含义。
保留失败原文，技术未解析应是候选技术未决/待局部修复，不能通过伪造人审规格消除方案错误。已发布数据需查实际来源与影响范围后出新修订，不能全库重写或认定全部污染。W2。

### P1 / C05：资料规模和全链完成指标不可信
`scripts/build_scale_validation_set.py:52`os作用域错误；仅PDF计页。`run_scale_validation.py`并未执行新事实后的binding/qualification，仍可将200空clauses报告成功，还未比对完整身份/页处置分母。脚本文头“全链”不是证据。
修媒体可解码/帧数/输出目录及逐阶段合同，规模驱动只调用产品入口，不能维护另一套临床链。W0/W6。

### P1 / C06：当前配置及会话标识有明确缺陷，历史“大图限制”结论撤销
实际`page_review_transport_options.py`对opencode-go返回空options；`page_review_harness.py:695–752`未注入handoff声称的json_object/session头。追加实测：原客户端三模型文字/合成图均400 MissingSessionID，隔离补头后MiMo与DeepSeek文字/图片成功，Muse文本503。当前.env又将main-A设为Ollama却回退GLM密钥；未向错误端点发送。详见10_MODEL_AVAILABILITY与原回执。历史25次请求无完整证据仍不能归因，完整病例质量未验收。W0封堵错凭据、W3接供应商会话合同，不能直接重跑25页或宣布模型全部不可用。

### P2 / C07：工作稿与冻结报告要求范围并不统一
`eligibility_review_projection.py:700`使用`project_clause_pack(rule_set)`并只循环clauses；`published_clause_pack.py`另有带control_publication的入口；`frozen_review_calculation.py:60`有完整control计算。至少已证实时读工作台和完整冻结计算走不同装配，不能称当前工作台覆盖全部跨章要求。
W1/W4应复用同一冻结要求/计算投影，跨章要求有明确处置；不要简单把控制伪装成官方编号。

### P2 / C08：更正预览只有同页启发式，不是同观察闭环
`fact_correction_service.py:496`只比asserted_object及locator交集，不区分属性/时间，未知对象也可相等。现有只是预览，不声称已经发生批量误改。应先给“相关来源候选”，真实观察/派生身份确认后更新依赖；新补证还影响“未找到”检索范围。W5。

### P2 / C09：历史进度、状态和当前目标互相冲突
task.json仍写9月17“仅规划/暂停”，implement叠加多份“最终根因”，旧计划状态表停在9月12；9月22handoff又把模型400、用户金标签字当全面阻塞。新入口必须只有一份当前进度，历史保留可查、不反复堆记录；构建者不能将自身适配问题交给用户完成。W0和本轮文档整合。

### P1 / C10：新来源可用状态不能只凭字符串标记
`app/domain/contracts/page_review.py:429–443`允许非空source_policy_kind和self_consistent等verification字符串绕过ACCEPTED必须含reconciliation_id的约束；尚未证实正式事实发布会接受任意伪造来源，但合同本身不能证明核实依据。新的source_policy合同未接生产消费者，不能用字段存在代替真实核实。
W3须使用现有类型化政策和明确原件/读数/核实产物引用；self_consistent最多表示内部一致，不等于独立核实或研究者判断。发布处核验政策要求及实际产物，不以布尔或自由字符串放行。

## 3. 专家 R2-01–12 逐条裁决

| 条目 | 现场裁决 | 后续包/验证边界 |
|---|---|---|
| 01 整条件资格选择 | 成立，选择函数与调用路径可见 | W1；复查/日期/频次正反例，不能只复用pair检查 |
| 02 全拒绝折None | 成立，特定无policy分支可回退 | W1；保留空映射与unverified，不把未决当FALSE |
| 03 400根因 | 旧结论不成立；本轮确认缺会话头，两个模型补头后可用，Muse本次上游503 | W0/W3；另有Ollama误用GLM密钥，见10 |
| 04 编译/死代码 | 成立且真实build扩展为6项 | W0；实际锁定依赖构建，不削严格检查 |
| 05 路径/os | 成立 | W0；所有源树/软链/回退统一检查，不静默搬入源码 |
| 06 媒体/全链分母 | 成立 | W6；实际输入页帧和阶段身份，空要求不得成功 |
| 07 模型身份 | 成立，response_model or route.model遮蔽缺失 | W3；请求/声明/解析身份分别记录，别名有据 |
| 08 组成员排序 | 成立，组max但成员保持输入顺序 | W4；稳定排序、深链优先，不把同类当同问题 |
| 09 栏宽/卡片 | CSS和DOM意见成立；美学未浏览器实测 | W4；宽屏原件优先、短分点；不新增手机布局 |
| 10 版本/浏览态 | 成立，episode revision冒充资料版本；首页当reference | W4；引用/候选/浏览分离，真实快照身份 |
| 11 同观察更正 | 预览启发式风险成立；自动批量改写未证实 | W5；观察identity与派生链；不按同页自动改值 |
| 12 守望/终态 | 成立，cwd、finish_reason键、最终echo | W0；优先退役该专用脚本并转既有持久工作流，不另建守望 |

保留前轮确已改善的pair拒绝、取消任意5任务窗口、HTTP错误信封拒绝、组最高严重性、原件浏览能力。专家包中的待选Envelope/IssueKey不强制原样全部造实体；现有合同能表达就复用。
专家建议窄视口降级限定为桌面缩放下可用，不扩展移动端。凭据历史暴露是配置运维依赖，只阻止该凭据网络调用，不启动与当前交付无关的安全测试或历史重写。

## 4. 为什么一直耗时

1. 症状驱动修补：模型失败→放大额度/换模型→重跑整例；未先核真实请求与阶段输出，重复付出成本。
2. 文档决策与运行链分离：主OCR方向已写，但旧双读条件仍控制正常化/发布，形成两套相互冲突的承诺。
3. 复用停在局部：配对检查、siblings DTO、UI分点都做了，但整条件选择、更正重算、真实呈现未贯通。
4. 用“绿色/产出条数”替代范围正确性：143事实、20/25页、candidate_ready均不回答当前来源是否完整、控制是否发布、结论是否消费正确证据。
5. 记录堆叠和测试追绿：缺唯一当前状态，改动后反复小测而未完成一个用户动作。结构本身已有可复用骨架，不应再开框架重构。

## 5. 审阅覆盖地图

方案解析/草稿/发布、摄入/原图/OCR、页级计划/传输/身份、来源政策/规范化/发布、资格/表达式/冻结计算、纠错/影响、前端正式路由/工作台、规模驱动/启动守望/进度文档均已做源码链路核查。重点函数深读见上述路径及专家S索引。
其他模块通过文件/差异/结构盘点纳入工程范围，但未声称逐函数穷尽；全库测试、端点稳定性、原始病例事实准确性、浏览器美学、跨方案泛化、迁移与备份恢复均列W6/W7验收，不在本轮伪造完成。
