# 0924V1 W6 无损暂停交接

日期：2026-09-24。状态：用户要求暂停；本文件不授权自动恢复临床作业。`claims_complete=false`。

## 一、接手入口与权限

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`；分支 `codex/phase5-clinical-facts-profile`。暂停前起点 HEAD 为 `18e88ef4d57bb712f0443179c9764fab636c88c1`；交付后的提交以实际 Git 历史为准。先看 `git status --short`、HEAD、服务/数据库归属，不 reset/clean。
- 当前任务：本目录 `prd.md`、`design.md`、`implement.md`、`delivery_20260922/00_START_HERE.md`、`02_EXECUTION_RULES.md`、`03_PLAN.md`。当前专家包：`/Users/smkzw/Downloads/enrollment_review_0924V1_35459c6.zip`，优先阅读其中 `03_HARNESS_RESCUE_0924V1.md` 的相关节。全局/项目 AGENTS 与 `.trellis/workflow.md` 仍需现场核对。设计书 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、实施计划 `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` 为总体边界，不必首次接手全篇重读。
- 原方案、病例、已发布规则和旧报告不修改；已有失败/取消作业不越版本续跑。内置产品 Agent 直连独立模型，个人工程 CLI 不能替产品解构或读病例。隔离诊断不等于正式临床验收。不得提交 `.env`、原始临床材料或完整模型回执。

## 二、目标与进度

总目标是用户上传 DOCX/PDF 后，由内置方案 Agent 解构官方入排及跨章控制，统一有源发布；真实病例以可靠文字/必要局部视觉读入事实，按节点形成可追溯工作稿、正式授权报告、更正/补证后新结果，并完成宽屏原件联动的真实浏览器与恢复验收。不能针对 SAR、某个药、时间阈值或模型硬编码。

0922/0923 已完成的源码与合同部分详见 `implement.md` 和 `delivery_20260922`，其中 W0–W5、Q1/Q2 的先前通过仅是各自范围内工程证据，不是本轮临床交付。当前主要阻塞在 W6 方案跨章深审/共同发布；W7 单例完整链与 Q3 正式验收未完成。方案草稿或结构通过不等于已发布；尚无本轮新的正式规则集、病例工作稿/签发、更正补证闭环。保持 `claims_complete=false`。

## 三、本轮做了什么

- 冻结首批的有源陈述、官方/流程逐项核对、失败原始回执保存、局部修订范围限制已接入内置方案 Agent。核对发现同段含多项不同阶段要求：不能因为一个候选引用整段就宣称每项均已覆盖。真实表格行/列标题属于同来源单元；早先把14处共享范围判成“无来源”是误判，已纠正。
- 对纯粹缺少日期属性的同原子修订，只有原文位置、时间、义务类型等确实不变且唯一匹配时才保留已核字段；改临床含义就拒绝继承。给药后持续义务不能提前当作筛选/基线当前判定。
- v95 为给药后范围问题加入短格式修订：模型仅提议移出的原子和对应来源处置，程序冻结未授权原子，再走原有完整门禁。真实短答约30秒，但一个原文单元同时被另一候选引用，模型却试图把整单元改作给药后事项；来源闭包以 `CANDIDATE_DISPOSITION_MISMATCH` 拒绝。v96 新增保守保护：目标候选与任何其他候选共享来源单元时，不进入此单候选短修订。不以速度换错误发布。
- 旧名称双击启动入口改接正式 V2 桌面服务，并完成隔离空库状态/前端构建/路由合同检查；未完成正式 Ego Lite 操作、启动停止/备份恢复或临床原件呈现验收。
- 最后集中检查：`159 passed`、5 项第三方 SWIG 弃用警告；`git diff --check` 通过。命令：`.venv/bin/python -m pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/protocols/test_protocol_control_agent_transport.py tests/v2/services/test_protocol_control_execution.py tests/v2/api/test_desktop_launch_contract.py -q --tb=short`。这不是全库检查，也不证明真实方案质量。

## 四、真实诊断与停滞原因

隔离诊断都使用内置产品传输、冻结首批及真实来源；只读或隔离运行，无规则/病例发布。原始回执保存在本地忽略的 `artifacts/0924v1-w6-v*/result.json`，不入 GitHub。原失败作业 `fba86f5c8e65480a8009802ccd949220` 位于 `/Users/smkzw/tmp/enrollment-review-w6-20260923-v35-deep4-01/data/enrollment-review-v2.sqlite3`，此前仍为 `failed_final`；不得按新版本复用。

| 诊断 | 实际结果 |
| --- | --- |
| v91 DeepSeek 完整冻结批 | 约280秒；时间字段短修订后，候选把给药后事项混进当前审核，失败。 |
| v92 原回执只读重放 | 日期字段能有界保留，但来源单元移走没有新处置，`REPAIR_SCOPE_ESCAPE`。 |
| v93 DeepSeek 完整重分 | 约200秒的现场修订改动义务类型、时间与摘录，旧日期不可继承，失败。 |
| 同源 GLM 对照 | 约1426秒；13条有源陈述，结构/日期/持续义务问题仍未通过。单次小样不足以排名。 |
| v95 DeepSeek 短范围修订 | 约30秒；回复格式有效，但将另一候选仍使用的同一来源单元整段重分类，完整来源门禁拒绝。 |

真正的困难不是端口或 JSON：一个方案段落同时讲基线随机分组、导入期和后续治疗期间的限制，而现有来源单元归属与单候选修订粒度不一致。模型多轮完整重答又会改动先前正确内容，代价高且不稳定。只增加输出额度、随机重试、换模型、放宽门禁或按句词形猜临床阶段，都不能证明质量。时间字段缺失与临床时间语义错位是不同问题。快速路径应保留，但不能把整段背景事项误认成当前入排条件。

## 五、下次安全工作

1. 先只读确认 HEAD/dirty、v96 实际代码、正式模型路由与数据/服务所有者；不要恢复旧失败作业或启动未知服务。查看本交接及 `implement.md` 文头，不逐份重读历史。
2. 在一小段真实冻结来源上定义**同一来源单元内逐动作/逐时间的有源分解**，保留原位置和完整出处；再由确定性装配投影到既有候选、义务、来源处置，并作双向来源核对。不要新造第二套发布规则库，也不要把模型的治疗期归类直接当作程序真相。
3. 同一真实小样做正反例：筛选/导入当前控制、基线流程、后续持续义务均保留；共享段落不重复也不整段丢弃；无证据的时间等价仍未核。比较语义完整性与总耗时。重复同类失败两次无新证据，应改变假设，不再盲重试。
4. 证明方案 Agent 可从合法隔离 DOCX 入口产出完整官方+跨章同源目录且通过原发布门禁后，才推进 W7 一例真实当前节点、原件定位、报告与更正/补证；再做第二结构留出和 Q3 浏览器/启动/恢复集中验收。研究者判断缺失要如实列未决与行动，不让模型代填。
5. 按工作包集中验证，不每改一处跑全套；关键消费者与最终真实 UI 必须检查。更新 `implement.md` 的唯一进度入口与 `docs/PROJECT_CONTEXT.md`，附实际命令、来源/产物/消费和未决，不以全 UNKNOWN、绿色单测或任务终态宣布交付。

## 六、代码和资料定位

- 核心方案 Agent：`app/agents/protocol_control_deconstructor.py`（`_PostTreatmentScopeRepair`、`_restore_bounded_wire_repair`、`post_treatment_only`），`app/agents/protocol_control_agent_transport.py`，`app/agents/protocol_control_source_interpretation.py`，`app/protocols/protocol_control_repair_errors.py`。
- 执行身份与保存：`app/services/protocol_control_execution.py`，`app/workflow/jobstore.py`；当前身份 `phase5/protocol-control-execution/v96`。针对性检查在 `tests/v2/protocols/test_slice58c_control_deconstructor.py` 等上一节测试命令所列文件。
- 用户入口：`scripts/start_enrollment_review.command`、`scripts/run_v2_desktop.py`、`app/api/v2/desktop.py`。0900/0923 的大量会议记录和本地诊断仍保留于工作树/忽略目录，未清理；不把它们当已发布临床资料。前次诊断 `artifacts/0924v1-w6-v95-narrow-source-repair/result.json` 含原文，仅读取必要字段，不上传或提交全文。

交付原则：保留全部未提交的他人/既有改动，不清理原件、测试资料或历史回执；暂停后任何新真实调用需按用户后续授权和当前任务合同重新确认。
