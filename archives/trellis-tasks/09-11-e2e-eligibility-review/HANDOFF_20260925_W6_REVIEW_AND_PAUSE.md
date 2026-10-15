# W6 无损暂停与方向复盘（2026-09-25）

## 接手入口与不变边界

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`，分支 `codex/phase5-clinical-facts-profile`；本轮起点 `942c68df50f64cab56fe2a0bcff05939d5141da2`。先核实际 HEAD、dirty、进程/端口与数据归属，不 reset/clean，不恢复旧作业。
- 现行任务：本目录 `prd.md`、`design.md`、`implement.md`；执行规则和工作包在 `delivery_20260922/00_START_HERE.md`、`02_EXECUTION_RULES.md`、`03_PLAN.md`，0924V1 专家资料为 `/Users/smkzw/Downloads/enrollment_review_0924V1_35459c6.zip`。总设计 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、计划 `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`；只读相关章节，不重读全部旧记录。现场全局/项目 `AGENTS.md` 与 `.trellis/workflow.md` 优先。
- 目标：用户上传原始 DOCX/PDF，**产品内置方案 Agent** 解构官方入排和跨章的当前阶段控制并同源核对/发布；原始病例以可靠文字和必要局部视觉进入来源化事实，形成当前节点工作稿、经授权报告、更正/补证后的新结果和宽屏原件定位。不得硬编码 SAR、某药、某病、某模型；模型不代替研究者判断。`claims_complete=false`。
- 用户此刻明确要求暂停并交接。**本文件不是恢复真实模型或临床作业的授权。** 原方案、病例、已发布规则、失败作业、隔离数据库和原始回执均不修改/删除。GitHub 仅提交代码、测试、无临床全文的任务记录；`.env`、原件、DB 和完整模型回执保持本地。

## 当前工作与证据

1. 方案来源目录以前把访视表“缩略语…”后的脚注漏掉，导致临床上有用的时间/节点信息在后续多轮都不可见。通用表格脚注提取已改为处理前言、无编号续行及嵌套编号；访视表逐列范围也保留。通过产品原始 DOCX 入口在隔离库重新冻结：作业 `f05217cc62924d4d9d2ce73968fdc8d5`，检查点 `700f06d24e72402c80dad6e55ad0054b`；原件 SHA-256 `075c93b45414dcb4bb33ef1cf623d295a9d8f029d7560ca484a0c0267c4fdabd`，新目录 41 项、目录摘要前缀 `32aaa354`，旧目录 `bd27fd7` 不能作为同源深审批次复用。隔离库：`/Users/smkzw/tmp/enrollment-review-w6-20260924-v102-isolated-data/enrollment-review-v2.sqlite3`；本地收据：`artifacts/0924v1-w6-v3-source-freeze.json`。
2. 新目录上的真实产品作业 v123 `90230ec872a24d1fb3d9ddc7f8996431`、v124 `36a611661bb94470ad5b134d760ea028`、v125 `a55cb91663b94e1284b040224c7dcf7a`、v126 `d46943fffe4643e6855e38123616b615`、v127 `1ba2fec2bc3f43c9b6ccd42de9424335` 均为 `failed_final`。先后暴露未来义务的空值/冻结值修订、标题/范围证据的校验口径、模型宣称“所有访视已覆盖”却只引出部分时间、同批两条要求交叉修坏、旧批次复用身份不一致等。没有 hydrate/gate 或共同发布。v127 在 86/181、第一个深审批次即失败，属于**复用预检**，没有新的医学判读；事件 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`，细节为“已完成的来源批次提示或模型回执身份不一致”。旧 v126 首批所存提示摘要 `327fed0132fb9612d9567b78d111d76e73d97ac2ecf909d27dbe77d32513771e`；当前仅用旧版本号重算出的摘要不相同，说明不能只加一个白名单版本号宣称兼容。具体是提示正文、Schema、来源核对版本还是模型回执哪个子项变化，尚需逐字段只读比对；**不应跳过检验强行复用**。
3. 当前代码包含有限局部修订：冻结既有持续义务、核验同源复合时间、对一个失败目标单项再核一次、对一个来源单元校正范围且不改动作/强度/出处。它们继续经过原批次完整校验，不是人工填入医学答案。身份提示 v2.76、执行 v127。核心代码 `app/protocols/procedure_catalog.py`、`app/agents/protocol_control_source_interpretation.py`、`app/agents/protocol_control_stage_compiler.py`、`app/agents/protocol_control_deconstructor.py`、`app/agents/protocol_control_agent_transport.py`、`app/protocols/protocol_control_gate.py`、`app/services/protocol_control_execution.py`。
4. 本轮集中工程检查：`.venv/bin/python -m pytest tests/v2/protocols/test_procedure_catalog_slice3.py tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/protocols/test_protocol_control_agent_transport.py tests/v2/services/test_protocol_control_execution.py -q`，`209 passed`、5 个第三方 SWIG 弃用警告、退出码 0。不是全库检查，不是医学正确率，不是完整工作流成功。旧发布门禁夹具还有若干缺当前求值规格的已知失败；没有据此放松正式门禁。最近一次受控独立会商在 `runs/conference/enrollment-w6-schedule-column-scope-20260925/evidence_single_object.md`，只支持保留逐列来源，不是临床发布批准。

## 为什么检测这么多轮仍有大量错漏

| 层次 | 已见实情 | 机制的必要性与问题 |
| --- | --- | --- |
| 原件进入系统 | 访视表脚注曾被结构提取漏掉；其后数轮只是在不完整输入上核对。 | 来源、页码、表格列和脚注闭包必需；输入缺失不能靠后段再多问模型补出。优先检查原文覆盖，再谈模型质量。 |
| 控制点选择 | 全文被拆成约 1,927 来源单元，398 个候选、85 个发现批次及约 94 个深审批次；当前阶段要求与给药后事项同段。 | 跨章搜索必需，但让近乎全文进入多轮深审，可能偏离“找当前入排审核控制点”的产品目标；候选/背景/后续义务分母和误筛率还缺独立临床核对。不能只按批次数证明完整。 |
| 临床语义 | 模型会把导入期、基线与给药后时间互借，也会把局部访视摘录称为全访视覆盖。 | 双向来源核对和时间锚点校验确实阻止错误入排结论，应保留。单次模型自信、JSON 合法或二次改写均不等于临床正确。 |
| 产物合同 | 一次输出同时承担原句、适用期、候选关系、义务、资料选择和复杂 Schema；局部错误触发整批再答，可能改坏已核内容。 | 严格来源与发布门禁需要保留，但模型应仅回答未定的局部语义，结构/身份用既有确定性程序装配；新增每一种专用补答都加大系统维护面。 |
| 恢复与验收 | 每次校验/提示微调后换版本、又启动多达 181 步作业；一些成功批次不能因提示/模型身份变化合法复用。v127 在调用模型前就失败。 | 版本隔离保护历史，必要；但过细版本变化和宽作业拓扑会让“验证修复”变成重复长跑。只测最小受影响片段并证明其余批次确实兼容，然后才有价值重跑完整链。 |

**方向判断：**多轮核对本身不是错误；对不能让研究者替代系统或让模型臆断的入排审核，它是必要的护栏。可能的方向性错误是把质量主要寄托于“越多轮、越长输出、越完整全方案重答”，而没有先证明来源提取闭包与当前阶段控制点的召回/误筛，也没有把确定性装配同局部语义判读清楚分工。现有 `protocol_control_deconstructor.py` 约 6,966 行、局部恢复分支不断增长，是需要审视的工程信号，不等于应推倒重写。不能通过删门禁、强行复用旧批次、调宽正则或填项目特例来换一个绿报告。

## 仍未完成与安全接续

- W6：尚无新目录对应的完整官方+跨章同源规则发布；`publishable=true` 的草稿也不能冒充正式发布。W7：真实病例当前节点工作稿/签发、一次更正/补证后新结果未完成。Q3：第二结构留出、真实宽屏原件滚动与标注交互、Ego Lite、启动停止/备份恢复和集中验收未完成。没有本轮 `claims_complete=true` 证据。
- 恢复时先只读核 Git/数据库/服务归属，再逐字段比对 v126 首批回执和 v127 期望提示/传输身份；若 Schema 或合同确有变化，旧深审不复用，保留已核发现的合法范围并新建版本化作业。不要再用只有“版本号已放行”的假设。
- 随后用同一真实方案原件做**抽样覆盖审核**：官方原编号、跨章当前控制、上下文、治疗后义务、表格/脚注分别计数并人工检查少量高风险反例。明确当前阶段候选选择的召回/误筛，再决定是小包语义补缺、装配职责调整，还是确需改分包；不要以模型输出条数当真值。
- 对已知同段多控制点，在一条真实冻结来源上完成“逐动作/逐时点解释→既有结构装配→双向来源核对→原门禁”的闭环。比较总耗时、原文控制点遗漏和不实控制，连续同类失败两次即换假设。证据通过后再跑完整 W6；随后才做病例 W7 与 Q3。不为让绿色覆盖率好看而改动患者资料或手填临床结果。
- 本地收据和隔离 DB 包含临床摘录，留在原位置；GitHub 交接仅留 hash、ID、命令及结论。没有活动作业需要继续等待；暂停期间不新发模型调用。
