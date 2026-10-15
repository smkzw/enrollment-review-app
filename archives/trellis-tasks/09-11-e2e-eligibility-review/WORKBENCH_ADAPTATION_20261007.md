# 医学经理工作台接入：入排侧已实施、共享侧待接线

## 已核事实

共享工作台拥有新建项目一次性交接与统一配置面板；保持选项A，入排侧不重复消费handoff或新建另一套表单。所有者在Ego空间114实际打开并取消面板，未提交建项。E03执行节点进一步映射，所有者核对生产/消费源码：用户项目虽保存eligibility_review意图，manifest不产出对应route binding；实际共享入排页调用旧/api/projects/.../eligibility，只接受固定历史项目原件入口。独立入排产品走/api/v2与方案上传确认→共同发布的真实创建路径。两个project_id不能假定相同。

本轮没有修改共享工作台首屏或后端。入排侧已实施持久入口，独立产品1006V1主线继续，不因共享侧尚未接线而暂停。以下仅证明入排侧能力，不宣布跨产品接入完成。

## 已实施的入排侧合同

- 来源键为`workbench:<共享项目编号>`，只作项目入口归属，不证明方案身份或临床采用。上传、再解构、正式反馈均保存于原Job payload，无第二映射库。
- GET `/api/v2/protocol/projects/workbench-origins/{origin}`按实际创建顺序解析Job、检查点和项目；hash损坏/归属改写/错项目明确拒绝，不退回旧成功冒充当前。
- 入排入口`/#/protocols?mode=workbench&workbench_origin=workbench%3A<id>`显示未上传、当前处理、正式已发布状态；发布以实际publish步骤及项目实体为依据。终态失败保留原因和处理记录，可同时进入既有基线项目或新版本上传。
- first/redo/feedback的重复检查在原SQLite写事务与原幂等合同内执行，活动任务不得再建；取消后的首次上传可重新创建。无来源键时保留原行为。
- `return`仅接受本产品本地相对路由，外部共享首屏地址当前不接受；不开放任意外部跳转。共享入口/返回责任仍需两侧明确接线，不能声称已返回共享首屏。
- 前端沿原上传表单、进度页和看板；不重复统一建项面板或handoff消费。入口和新版操作传递来源与返回上下文，不用共享project_id直接查询本产品正式project。

## 共享侧仍需完成的最小接线（未实施）

1. 共享用户项目按原意图显式声明入排待配置状态；若仅有intent而无真实产品身份，不能展示成已接入。
2. 按上述来源键与入排侧持久入口查询真实状态，明确创建责任。不得将共享proj_user编号直接当成本产品正式身份，不借既有D001/MY009数据。
3. 由映射进入本产品现有正式方案入口，上传/解构/核对/共同发布仍沿原workflow；共享基本信息是metadata，不替代方案身份或允许改方案。
4. 已有项目及多模块建项使用同一映射/返回上下文；不要重做首页选择、handoff键或重复建项面板。
5. 跨产品验收：仅选入排建项后从共享首屏进入正确入排空状态；入排+监查从实际首模块创建后进入正确入排项目；旧项目不混来源。此三项未执行。入排侧合成入口上传与恢复已执行，不能替代跨产品验收。

## 实施、独审与验证边界

基于32ced805的明确源码补丁。E03终态ZCode/zcode/GLM-5.3-Flash/max，session sess_d855c1c7-3715-4b1f-b78c-81e73c652bf2，1161.148s/64工具/exit0；CodeBuddy主执行曾编辑源码后转runner fallback，不是主模型完全不可用。C03 Grok/grok-build/grok-4.7/high，session1ea47f9a-deba-4c26-b4eb-ecb131be26fd，412.141s/exit0/no fallback；120min静默完成等待，冻结在最终所有者事务与发布证明补丁前，非末版独立批准。

所有者采纳失败任务不能藏基线、反馈不能丢来源、检查点不能换项目及原子重复检查意见。没有采纳“退回最近成功”或让失败记录变成unbound；失败状态保留，基线仅另列可操作入口。真实发布测试进一步发现publish步骤已完成但Job generic尚非completed，已按实际发布消费者修正。

集中后端3模块114passed107.15s/exit0/5SWIG；前端3模块44passed2.70s/exit0；正式TypeScript/Vite build0，已有chunk警告。前窗分别暴露来源损坏异常没有本地化、发布投影与活动门错误；时间时区/actor/fixture错误为测试问题，未放宽产品门禁。相互重叠结果不累计。JUnit`/Users/smkzw/tmp/rv1006-workbench-origin-connected-20261007-final.xml`仅本机可读。

Ego空间147，所有者专用5198空合成库、Runner关闭、0模型：从真实上传表单提交合成DOCX→Job9ab727deb3dd418581a61df7e83762d4→返回项目入口→持久恢复同Job→再进进度；来源及本地返回保持。1920×1080、2560×1440、3840×2160无横向溢出；截图本机`/Users/smkzw/tmp/enrollment-rv1006-workbench-entry-ui-20261007-v1/`。观察到按钮拉满后局部修CSS。非临床、正式签发、共享首屏贯通或完整Q3证据。正式发布/失败等状态的软件消费者测试不冒称均已浏览器实跑。

## 可检查来源

本机共享根：/Users/smkzw/Documents/康哲项目资料/AI/医学经理工作台/implementation/workbench/。外部审阅不可直接读这些本机路径，需共享所有者提供源码快照。

- scripts/frontend_refactor_20261006/ADAPTATION_PROMPT_ELIGIBILITY.md：授权边界与A/B选择。
- frontend/src/App.jsx：统一建项交接、NewProjectConfigPanel及eligibilityRouteProjectId/EligibilityPage消费。
- services/api/app/project_source_manifest.py381-433：用户项目模块绑定。
- services/api/app/eligibility.py66-102：legacy raw-intake配置；main.py中来源准入和create_project需共享所有者复核。
- 本产品frontend/src/app/routes.tsx60-110、协议API客户端：formal项目入口与/api/v2。

E03回执在本工作树runs/execution/rv1006-workbench-adaptation-boundary-20261007/worker_01.md；实际pi/cursor/default，底层模型未知，107.806s/exit0/no fallback，88工具调用。仅来源映射，不是浏览器接入验收或独立医学批准。不得照抄顾问建议的一行binding即声称接通。
