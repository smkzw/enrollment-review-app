# 医学经理工作台接入：现行接口缺口

## 已核事实

共享工作台拥有新建项目一次性交接与统一配置面板；保持选项A，入排侧不重复消费handoff或新建另一套表单。所有者在Ego空间114实际打开并取消面板，未提交建项。E03执行节点进一步映射，所有者核对生产/消费源码：用户项目虽保存eligibility_review意图，manifest不产出对应route binding；实际共享入排页调用旧/api/projects/.../eligibility，只接受固定历史项目原件入口。独立入排产品走/api/v2与方案上传确认→共同发布的真实创建路径。两个project_id不能假定相同。

本轮没有修改共享工作台首屏、后端或本子系统前端。所谓“没有前端补丁”是有据边界，不是宣布接入完成。独立产品的1006V1主线继续，不因本项等待而暂停。

## 两侧需共同实现的最小接入合同（建议，未实现）

1. 共享用户项目按原意图显式声明入排待配置状态；若仅有intent而无真实产品身份，不能展示成已接入。
2. 明确共享项目与本产品project/protocol version的持久映射、创建责任与来源归属。不得将共享proj_user编号直接当成本产品正式身份，不借既有D001/MY009数据。
3. 由映射进入本产品现有正式方案入口，上传/解构/核对/共同发布仍沿原workflow；共享基本信息是metadata，不替代方案身份或允许改方案。
4. 已有项目及多模块建项使用同一映射/返回上下文；不要重做首页选择、handoff键或重复建项面板。
5. 真正验收：仅选入排建项后到可操作空状态并上传方案；入排+监查从实际首模块创建后进入正确入排项目；旧项目不混来源。当前均未执行。

## 可检查来源

本机共享根：/Users/smkzw/Documents/康哲项目资料/AI/医学经理工作台/implementation/workbench/。外部审阅不可直接读这些本机路径，需共享所有者提供源码快照。

- scripts/frontend_refactor_20261006/ADAPTATION_PROMPT_ELIGIBILITY.md：授权边界与A/B选择。
- frontend/src/App.jsx：统一建项交接、NewProjectConfigPanel及eligibilityRouteProjectId/EligibilityPage消费。
- services/api/app/project_source_manifest.py381-433：用户项目模块绑定。
- services/api/app/eligibility.py66-102：legacy raw-intake配置；main.py中来源准入和create_project需共享所有者复核。
- 本产品frontend/src/app/routes.tsx60-110、协议API客户端：formal项目入口与/api/v2。

E03回执在本工作树runs/execution/rv1006-workbench-adaptation-boundary-20261007/worker_01.md；实际pi/cursor/default，底层模型未知，107.806s/exit0/no fallback，88工具调用。仅来源映射，不是浏览器接入验收或独立医学批准。不得照抄顾问建议的一行binding即声称接通。
