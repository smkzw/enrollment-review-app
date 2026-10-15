# 2026-09-24 W6 无损暂停与接手说明

## 先读与当前边界

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`，分支 `codex/phase5-clinical-facts-profile`。暂停前 HEAD 为 `f77bc71da3f12ec466c13f88199da17e2317efc4`；交 GitHub 后以本节末的实际提交为准。接手先核 HEAD、dirty、隔离库作业终态及服务归属，不 reset、clean 或覆盖本地过程文件。
- 本次 Goal 原文：基于 0923V1 全面任务计划、执行规范、资料包、PRD、Plan、分步执行包和验收包，持续实现至完全交付；约束过程中过度设计与“改一处测一次”。用户最新指令要求**完成手头工作后无损暂停、记录复盘并递交 GitHub**，因此本文件不是完成声明。
- 最短权威阅读顺序：本任务 `delivery_20260922/00_START_HERE.md`、`02_EXECUTION_RULES.md`、`03_PLAN.md`，然后 `prd.md`、`design.md`、`implement.md` 文头及状态表。0923V1 增量要求见 `HANDOFF_0923V1_RETURN.md` 与 `HANDOFF_20260923_W6_PAUSED.md`；仅按实际改动再读 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` 的相关章节。当前实现状态以工作树和隔离作业为准，历史 handoff 不是更高授权。
- 产品仍须保留内置前置方案 Agent、DOCX 原件入口、官方与跨章同源共同发布；病例以可靠文字主读和必要局部视觉核实进入来源化事实、Profile、当前节点工作稿和报告。不是让外部个人 CLI/Hermes/OMP 代产品识别，也不恢复全页强制双 VLM。不允许按 SAR、某药、某阈值或模型专有输出过拟合。
- `claims_complete=false`。结构校验通过、模型端点连通、草稿可预览、历史 Q1/Q2 通过均不等于临床验收或正式发布。工作稿和签发授权保持分层；不能用失败作业或旧事实冒充新结果。

## 完成与未完成

| 阶段 | 当前可核证状态 | 仍欠什么 |
|---|---|---|
| W0–W2/Q1 | 先前有产品合同与构建通过记录；W2 保留技术失败、同源草稿和共同发布门禁 | 新 DOCX 的本轮完整跨章深审尚未完成，不能将草稿修订21视为正式发布 |
| W3–W5/Q2 | 先前有文字主读、风险页局部核实、工作台、更正失效合同回归 | 尚未用本轮新项目的真实病例闭合逐页来源、事实/Profile、资格、报告与补证 |
| W6 | 完成隔离原 DOCX 发现阶段并尝试不同版本有界深审；新增当前阶段禁止性来源缺漏拦截；病例模型入口完成非临床图片能力预检 | 三个最近合法深审作业均 `failed_final`；官方+跨章目录未发布，五份24页原件及当前节点整例未验收 |
| W7/Q3 | 未开始正式验收 | 第二结构留出、Ego Lite宽屏交互、启动恢复/备份、交付检查 |

本轮最新工作树中的实质改动：

1. `app/agents/protocol_control_deconstructor.py`、`app/protocols/protocol_control_gate.py`、`app/services/protocol_control_execution.py` 及相关合同/测试：扩充来源与期别/时间关系诊断、授权局部候选修订，并对当前入排阶段明确的禁止性原文若未形成候选且未被同段来源的已知目标覆盖时保守拦截。执行身份现为 `protocol-control-execution/v50`，深审提示 `v2.44`，门禁 `v22`。这些修改只防止部分静默遗漏，不解决一次产出复杂求值结构的根问题。
2. `app/config.py`、`app/llm/page_review_harness.py`、`app/agents/deepseek_evidence_normalizer_transport.py`：病例第二读道与事实整理的默认角色从旧 OpenCode Go 路线对齐 `cms-router/deepseek-latest-cloud:high`；CMS 自身凭据/地址在该路线下优先于遗留角色变量，其他供应商的显式配置不改。工作树本机忽略的 `.env` 只改非密钥角色值；密钥不提交、不打印。
3. 同一产品页级 `direct_completion` 对生成的 32×32 红色 PNG 做过非临床连通测试：A 请求 `cms-router/glm-5.3-flash:high`，B 请求 `cms-router/deepseek-latest-cloud:high`；均返回 `stop` 并正确读出颜色。B 回执模型名是 `deepseek-flash`，与请求别名不同，不能据此宣称上游精确权重。此项不代表病例事实识别通过。

## W6 失败现场与停滞原因

- 隔离库：`/Users/smkzw/tmp/enrollment-review-w6-20260923-v35-deep4-01/data/enrollment-review-v2.sqlite3`。原 DOCX 在同根 `blobs/blobs/protocol_sources/`，原件不改。最近作业及当前终态：v41 `b55a6c4b11ba4daeada43c5352eefb29` 为 `failed_final`（深审第31批）；v48 `7914ce8306304f39b69837e6fe854754` 为 `failed_final`（第24批）；v49 `1dad32380f22478ca6d657d4331c19b0` 为 `failed_final`（第2批）。三者均未共同发布目录。它们有不同版本身份，不能用当前 v50 对旧检查点越版续跑或把失败步骤标成功。
- v49 第2批含当前筛选/导入背景用药限制与治疗后安排。隔离的 GLM 产品直读虽结构通过，但对明确限制给出**零候选**；仅凭结构通过会造成临床漏项。本轮缺漏拦截可阻止这种特定静默遗漏，但不能代模型产生医学条款。
- 同一来源再缩为单段、使用产品 DeepSeek 进行一次隔离诊断，约145秒、三次输出，依次遇到求值/观察字段缺失、把未来义务过早判定、禁止要求被写成建议强度；最终仍为“需要核对”，未写入正式任务。不要再对同一输入无新假设重复调用，或通过放宽门禁让错误输出通过。
- 核心原因是一次深审要求模型同时理解来源、条件/例外、节点时间、复查、观察选择和几十个嵌套必填字段；固定提示和 Schema 较大，错误后的两轮修订又在同一复杂结构内纠错。降低批量数、加一般性提示和换随机输出只把失败转移到不同批次。下一次必须改变**既有方案 Agent 内部的输出成形负担**，保留来源闭包与原文语义；先离线核函数级生产/保存/消费和失败回执，再做一个有边界的产品小样，不另造通用 Agent 平台或第二套规则真相表。
- 只读工程会商材料位于本工作树 `runs/conference/enrollment-w6-schema-rescue-20260924/` 等未跟踪目录；其输出含相互矛盾的历史断言，不能当临床事实或可靠当前代码证明。以当前源码、SQLite 事件和原件为准。

## 验证账本与运行环境

- 暂停前合并定向命令：`.venv/bin/python -m pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/services/test_protocol_control_execution.py tests/v2/agents/test_evidence_normalizer_transport_config.py -q --tb=short`，退出码0，116 passed、5项第三方 SWIG 弃用提醒；另有路由/凭据优先级 6 passed、新增来源拦截 6 项通过。`git diff --check` 通过。旧门禁宽套件停在 91 passed/8 failed，旧页级套件停在 25 passed/5 failed；多为当前必填求值字段或流式客户端与旧夹具不一致。不得说“全套通过”，也不以追逐旧夹具绿灯替代 W6 实跑。Q3 未执行。
- 端口只读检查：`20128` 为 OmniRouter，`8001/8002` 为本机其他模型服务；`8910` 的进程命令指向**医学经理工作台**的 uvicorn，不是本入排系统专用实例。归属未知/共享服务不得关停或复用。上述 PID 只作历史线索，接手需重新核对。当前没有本轮正在运行的临床模型执行会话。
- `.env` 被 Git 忽略且保留本地；产品配置取显式实际值，不读取聊天/示例文件当密钥。供应商服务返回的模型别名和用户配置的模型名应分别保存，不把服务声明当精确权重证明。
- 未清理隔离 SQLite、模型回执、会商过程目录或原文。未提交的大量文件不能用 `reset`/`clean` 简化；只按本任务核实范围提交，过程目录保留本机供审计。

## 接手后的具体安全动作

1. 先核 HEAD/dirty、上列三个作业终态和真实配置；读 `implement.md` 文头最新记录与现行版本常量。不要恢复失败旧作业，也不要误启 8910 的工作台服务。
2. 围绕 `ProtocolControlAgentRunner.run`、`build_protocol_control_agent_prompt`、`OpenAICompatibleProtocolControlAgentTransport.start/continue_session` 和 `_execute_deep`，把复杂来源的**解释**与完整机器结构的**装配**分担到既有内置方案 Agent 的受控步骤；中间产物有源、有版本、可恢复，不能把错误格式转为研究者判断，不能由代码虚构医学语义。先用冻结单段含当前禁止与未来义务的来源小样证明不漏项且结构通过，再考虑合法新版本作业；当前 v50 尚未解决该障碍。
3. 完成所有深审批次后按原件复核官方编号、父子/否定、跨章限制、节点和时间锚点；正式共同发布同源目录。之后再按 W6 路径读取真实病例，形成事实/事件/用药/Profile、当前节点完整工作稿和有依据的未决；一次真实更正或补证必须使相关旧结果失效并生成新结果，历史 hash 保持。
4. 最后做 W7/Q3：第二结构留出、Ego Lite 在 1080P/2K/4K 上真实点击与原件红框核对、启动/备份恢复。验证尽量按完整功能包集中执行，避免每改一行重跑所有测试；但高风险写入和新模型路线首次调用仍做最小预检。

本次明确的暂停点：**没有继续运行的 W6 作业；不启动新作业，不修改原件。** 如接手者需要恢复，先完成上述代码/证据核对，然后从合法入口新建当前版本的隔离尝试，而不是接续 `failed_final`。正式临床签发仍需独立授权，本轮没有代用户批准。
