# 0922V2 请求、资格、前端与更正规格

## A. 请求诊断与图式/循环设计

### A1. 请求合同最小记录
request_contract包含：run_id、step_id、role、provider、endpoint路径、requested_model、
header_presence（不含值）、stream、response_format、max_output_tokens、reasoning参数、
messages数量、text_chars、image_count、每图bytes/width/height/mime/hash、serialized_request_bytes、
prompt/schema/transport版本、request_fingerprint。若token用量服务没给，记null，不以字符伪造精确token。

response记录HTTP状态、净化error.code/message/param、request_id、reported_model、finish_reason、
stream完整性、content字符数、usage、阶段失败分类。模型回执中的名称称“服务声明”，不是权重证明。
主记录同时保留requested/reported/canonical和别名策略；缺失身份不可被request身份遮掩。

### A2. 控制变量矩阵（是方案，尚未执行）
| 组 | 保持不变 | 唯一变化 | 要回答的问题 |
|---|---|---|---|
| C0 | 同一provider/model/产品客户端 | 无图、最小文本 | 路由和基本传输是否可用 |
| C1 | C0合同 | 必要session header有/无（仅已批准场景） | 产品与独立探针的header是否一致 |
| C2 | 成功合同、短输出 | 真实受控图像替代小图 | 图像格式/内容/尺寸是否改变结果 |
| C3 | 同一图、同一提示 | 逐档max_tokens | 请求额度是兼容问题还是输出实际不足 |
| C4 | 同图/预算 | reasoning参数有/无或官方允许值 | provider模型是否接受实际参数 |
| C5 | 同图/提示/预算 | format/stream分别单独改变 | 格式和流式合同是否支持 |
| C6 | 已验证参数 | 完整临床读取prompt与schema | 长上下文/输出或验证发生在哪阶段 |

每次同时改多个变量不能定位原因。测试一张页完整通过后再3–5页；保留成功页工件并按同一
证据政策验证可复用范围。400不得自动统称schema错误，也不得仅凭一个status断言大图限制。
不建议无边界模型横评；发现明确限制后才制定可验证的适配或替代路线。
诊断调用采用最小必要材料及次数。上游不可用时，队列进入blocked_endpoint，不转化为病例缺证。

### A3. Graph+loop
图节点按不可变工件和输入scope衔接：原图准备→主读取/覆盖→局部核实→规范化→
完整资格选择→确定性计算→工作稿/例外队列。方案解构是独立内置前置图。
循环分开request_invalid、rate_limit、stream_incomplete、format_invalid、source_ambiguous、
new_evidence等原因；每轮有新增证据/输入变化或明确修复，不原地无限重试。
图中不存在“一定两个模型才能有Agent协作”的要求。保留双读策略但不得作为全页默认。

## B. 完整资格选择

建议的内部结果Envelope（候选设计，非声称现有API已支持）：
- state: not_run | stale | rejected | incomplete | failed | ready
- authority/context/input_digest：绑定当前事实、定位、元数据、规则、节点和资料
- per_identity：value_pair_ids、date_pair_ids、selected_fact_ids、selection_policy、
  source/date qualification、ordering audit、unresolved_reasons、provenance_refs
- computed evaluations：proposition/repeat/frequency等显式结果，不静默变成普通fact值

ready并不要求每一条临床条件都有确定真值；它要求本轮处理完整且每个条件有真实处置。
rejected不等于临床FALSE，not_run不等于资料缺失，unresolved不等于研究者没写判断。
分支短路允许存在不影响结论的未决，但必须保存为何不影响；不按“有绑定”全局抹掉缺口。

## C. 例外工作台

### C1. 分类不替代根因
第一级为类别（资料待核实、来源冲突、检查未提供等）；第二级为独立Issue实例。
IssueKey至少考虑authority、要求/条件身份、观察/事件、时点/窗口、来源或缺件身份、动作范围。
共享gapType只可同类展示；未证明是同一根因，不合并问题关闭、不宣称一次动作必解全部。
组severity=max(member severity)；成员按severity及确定性辅助键排序，默认/上一项/下一项共用此序。
深链到筛选外项时明确标示并保留可返回上下文；普通筛选变更则选有效首项或明确无结果。

### C2. 正式宽屏
建议作为起始参数，不是已验证数据：
- 左侧“待处理/全部条款”在同一容器切换，宽280–360 CSS px，可调整。
- 中栏用于短依据/影响/动作与按需原文；右侧原件在宽屏优先获得新增宽度，可展开并列源。
- 总体使用min-width:0和明确容器滚动；不能用body overflow:hidden掩盖被挤掉的内容。
- 视口不足时两栏或标签降级，不让三个窄条列继续并排。
- 行式问题摘要正文14–16px，行高1.35–1.45；较长原文1.45–1.55。
- 控件保持可点、键盘焦点可见；200%缩放和间距覆盖不丢内容，不能靠强行字体缩放完成验收。

### C3. 真正的bullet而不是卡片堆叠
短标题保留对象和风险；三个条目分别“依据/影响/动作”。原文独立展开，不默认整段染色卡片。
列表局部恢复disc/适当缩进，不能全局给导航树加marker。对文字只做来源化结构投影，
不让自由总结LLM删除否定、时间、单位、不确定性或创造新事实。无实际影响依据时明确未确定。

### C4. 来源导航/版本
受试者入口必须含project/subject/episode；问题入口加issue/component；原件入口绑定
snapshot/document_version/page_artifact/locator。历史报告不可静默跳最新证据。
return state保留筛选、搜索、排序、分页、选中项和可恢复滚动；不靠浏览器Back碰运气。
referencePage仅对已声明的引用存在；普通浏览默认页与待核实候选不进入引用确认逻辑。
版本分别命名规则修订、节点修订、资料快照、处理修订、档案修订；没有字段就标明暂不可得，
不可用一个看似可用的整数补另一个实体的版本。

## D. 单观察更正闭环

同对象+共享locator是candidate_relation，而不是same_observation的充分条件。
ObservationIdentity需有同一测量/事件/属性和源位置/时间的依据，派生关系应记录generation lineage。
保留不同来源同值和不同时间重复测量，严禁按value或整页位置合并。

一次更正事务：预览影响与确定关联→版本/幂等检查→原观察修订与派生变更→明确失效→
只重算受影响图节点→重新资格→新工作稿。不同派生属性可能需要重新推导而非复制同一个新值。
旧记录/旧报告保留，处理中向用户解释何处在更新。新补证还使证据范围依赖的“未发现”检索失效。
已核实页面能否复用按source/read/verification合同判定；不得因模型换名就无条件重跑全页，
也不得把旧全规则提示生成的语义观察未经资格核实直接视为方案无关缓存。

## E. 人工边界
工作稿可查看和处理真实未决，不先强制逐项金标/签字。方法评测与正式采用属于独立治理层，
不伪造标注或签名；正式发布满足对应门禁。让用户介入真实临床歧义，而非替系统处理
解析错误、HTTP参数不兼容或内部fact通道重复。用户已有路线决定不重新提问。
