# 2026-09-23 W6 无损暂停与接手说明

## 先看这里

- 唯一工作树：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`。暂停前分支 `codex/phase5-clinical-facts-profile`，本轮起点 `bc5d1cb815bf512c964784cda92914689ef1ce11`。接手先核 `git status`、HEAD、数据库作业终态和服务归属，不为对齐旧基线 reset/clean。
- 当前权威入口：本任务 `delivery_20260922/00_START_HERE.md`、`02_EXECUTION_RULES.md`、`03_PLAN.md`、`prd.md`、`design.md`、`implement.md`，以及仓库 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`。`HANDOFF_0923V1_RETURN.md` 记录增量审阅的早期状态，其“未授权模型调用/提交”句已被后续用户授权覆盖；不要把它当当前禁令。
- 用户目标仍是 W0–W7 与 Q3 完整交付：内置方案 Agent 从原始 DOCX 得到官方条款和跨章要求，经有源草稿核对后共同发布；真实病例经来源化事实/Profile、当前节点工作稿/报告，再完成一次更正或补证闭环。W0–W5/Q1/Q2 的先前记录不等于本轮真实临床验收。当前 W6 未收口，W7/Q3 未做，`claims_complete=false`。
- 本轮受控方式：单一工作树和隔离数据目录；产品 harness 直连独立模型，不用个人 CLI 代替。临床原件、正式数据库、已取消作业、草稿修订21均未改；结构通过不等于医学正确或规则发布。

## 本轮用户变更与实际动作

1. 用户授权从合法入口新建隔离 W6 真实作业，后将产品模型改为 OmniRouter `cms-router/deepseek-latest-cloud`，并仅授权给现有产品密钥增加此模型权限，保留原权限。OmniRouter 备份：`/Users/smkzw/.omniroute/backups/storage.sqlite.bak.enrollment-key-scope-20260923`。官方权限命令返回404后，按授权仅更新本机该密钥一行记录；非临床请求证明新模型和原有模型可访问。受限密钥 `/v1/models` 仍返回空清单，产品身份预检改为仅对 cms-router 用非临床小请求核对**实际返回模型名**；其余供应商不放宽。密钥只在本机 `.env`，未入库。
2. 当前模型配置在本工作树 `.env`（ignored），示例配置在 `.env.example`。进程中已有 `CMS_ROUTER_API_KEY` 会覆盖 `.env` 的同名值；曾因此用错密钥并在身份预检时停下，未发送方案。接手不得打印密钥；从显式目标配置启动，核路由回执，不向错误端点送原件。
3. v25 OpenCode 旧隔离作业 `6f5f55bcd9dd43fc8fb11dfa607609a7` 在变更模型后取消。v26 `44501a44e0df4f39b7872f9a18dc2632` 的发现阶段完成，深审第8批失败；失败顺序为计算方法、时间锚点、访视流程关系。按通用语义修提示后，对同一冻结批次的产品 runner 一次返回合格结构，但无候选；这不证明整个方案正确。
4. v27 `293815d0aa0249b99f2e3157de368d60` 在发现第52批 `failed_final`。已沿用产品原有跨批规则，对**被当前候选明确引用**的同批 `non_control` 单元仅提升为 `context_only`，来源与原分类理由保留，不生造控制点；原失败响应离线重放24单元通过。
5. v28 `f6ad8965200c4089bb28f5e20a4cfb01` 在发现第53批 `failed_final`（55/86）。原始响应在实际决策 JSON 前回显 `$defs` 结构，原修订提示再次贴入完整结构，故失败循环。现仅删去**修订提示**里的 Schema 重发，加“只返回一个对象”；首次提示及服务端严格 Schema 仍保留，提示版本 v3、执行版本 v27。同一冻结第53批用产品传输、同一端点、原校验器重新调用，约37秒、1次、24条决策、“已解析”。这是隔离单批诊断，**没有写回 v28，也没有启动 v29 或发布规则**。

## 来源和验收边界

- v27 SQLite：`/Users/smkzw/tmp/enrollment-review-w6-20260923-v27-cms-deepseek-01/data/enrollment-review-v2.sqlite3`；v28 SQLite：`/Users/smkzw/tmp/enrollment-review-w6-20260923-v28-cms-deepseek-01/data/enrollment-review-v2.sqlite3`。均保留原失败状态和来源。相应原始 OmniRouter 回执在本机 `~/.omniroute/call_logs/2026-09-23/`；含临床内容，不加入 GitHub。索引可用末尾 `-26ef5e.json`（v27第52批）、`-dcf233.json`（v28第53批）。
- 原研究方案的访视表中，V1/V2 时间窗为空，±1/±3 天只位于后续访视列；原文扁平化容易左移。`member_source_refs` 保留行列定位，不应把后续时间窗安到 V1/V2。v26 单批无候选可能是正确的访视背景处置，也须独立对原件复核。
- 本轮聚焦检查：`.venv/bin/python -m pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/protocols/test_protocol_control_anti_overfit_chain_wide.py -q --tb=short` 为77 passed，仅有第三方 SWIG 弃用提示；cms-router 身份3项 passed。完整身份套件另有13项旧 MTPLX 夹具失败，原因是产品装卸清单缺失，不能称全绿。`git diff --check` 通过。未做全库回归、完整方案医学QC、正式规则发布、病例端到端、真实浏览器 Q3。
- 现存已知效率债务：深审提示约5万字符，包含大量重复结构；发现/深审多批重试费用高。缩短发现修订提示解决了**一个**实际失败，不证明整体速度和准确率达标。模型原始输出异常要分别查结构、源锚点和临床语义，不能把失败改成研究者判断。

## 接手后的安全顺序

1. 先核当前 HEAD/dirty、v27/v28 终态、是否存在新活跃作业；核当前配置模型和身份回执。不要恢复旧 `failed_final` 或 `cancelled` 任务，也不要靠旧 `publishable=true` 草稿绕过跨章发布。
2. 针对本轮代码共享合同做一次有界回归，特别核同批上下文提升、发现修订提示与版本身份、深审访视时间语义；确认跨章真实来源被完整而不过宽地处理。之后从合法入口建**新版本**隔离 W6 作业，定期看原始回执和中止原因，不复用旧版本失败步骤。
3. W6 完成后先做有来源的医学核查、官方+跨章同源发布；再使用五份24页病例建立事实、事件、用药暴露和 Profile，形成真正有依据的当前节点工作稿/报告。已知缺失单列，未提供记录不等于不存在。更正/补证后局部失效与新结果对照，历史和原件 hash 保留。
4. 最后完成第二结构留出、工作台原件定位与宽屏 Ego Lite 操作、启动/停止/备份恢复及 Q3。不能用绿色结构测试、全 UNKNOWN 报告或空状态截图宣布交付。

## 交接纪律与复盘

- 本轮反复停在不同批次，根本原因不是“方案无控制点”，而是完整方案的复杂来源在模型输出合同中暴露了不同类型问题：时间锚点与计算语义、候选所需上下文的分类冲突、以及 Schema 被回显。每次修复需保留前一失败证据并换新版本隔离尝试；不能自动相信模型的结构通过代表医学正确。
- 当前暂停是用户明确要求的无损暂停。所有原始资料和失败回执留存；无继续运行的本轮 Python 执行会话。接手不需要用户重复决定模型方向，但若要正式发布或对外承担医学结论，按现行授权和验收门槛处理。
