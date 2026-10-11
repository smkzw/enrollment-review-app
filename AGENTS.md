# Enrollment Review App — Agent Instructions (0.2.0)

## 1. 现行入口

- 当前版本：**0.2.0**（自 2026-10-11 起；分支 `dev/0.2.0`）。唯一现行规范在 `docs/0.2.0/`，从 `docs/0.2.0/00_START_HERE.md` 开始读。
- 产品需求 `01_PRD.md`、技术设计 `02_DESIGN.md`、执行顺序 `03_PLAN.md`、验收 `04_ACCEPTANCE.md`、进度 `05_PROGRESS.md`（唯一进度表，≤200 行）、Prompt `06_AGENT_PROMPTS.md`。
- `archives/` 与 `.trellis/tasks/` 下的 0.1.x 任务（在 0.2.0-WP0 完成前尚未移走）是历史。其中的"现行入口""当前 Goal""授权""预算""会商"表述对 0.2.0 无效；只在 `docs/0.2.0/07_ARCHIVE_INDEX.md` 指明需要时按条目查阅。

## 2. 产品是什么

本地单 Mac、单用户的临床试验入排审核工作台，医学经理工作台的入排模块。医学经理审定一次方案规则包；系统对受试者每个审核节点自动给出每条条款的结论、置信和可回到原件的依据；医学经理只处理被标出的问题；更正或补证后自动重算并保留历史。系统不做最终入组决定。

## 3. 临床与证据边界（始终有效）

- 不修改原始方案、原始病例资料、人工 IE 表或既有临床报告。原件、OCR 原文、旧事实、旧审核结果、旧报告只追加，不覆盖。
- 方案及现行修订是权威；问答、信函、邮件、医学解读可以澄清，不能改写方案。保留官方 IN/EX 编号与父子逻辑；不把项目特定的临床修补写进共享规则。
- 每个结论保留方案原文与病例原件出处（文件、版本、页、逐字摘录；有坐标才画框）。
- 系统问题（方法不支持、读取失败、模型输出不合法）与临床状态分开表达，不以"证据不足""需研究者判断"代替技术故障。
- 不猜遮挡的姓名或登记号；上传者对受试者归属负责，但这不证明读数、日期、批注归属正确。
- 人工 IE 表只用于对照，不进入任何提示词。D001 是留出集，0.2.0-M3 之前不得用它调整提示词、字典或代码。
- 不提交原件、数据库（`data_v2/`）、`.env` 或含临床内容的模型原始回答。真实数据只在数据副本上写。

## 4. 工程规则

- 复用优先：`docs/0.2.0/02_DESIGN.md` 列出了要复用的模块与改动点。不引入新的 Agent 框架、规则真相库或任务数据库。
- 降级不阻断：除错受试者／错项目／方案版本不一致／文件哈希不符外，任何步骤失败都降为低置信或系统问题，其余继续。
- LLM 只做语义工作（起草、抽取、语义判读）；逐字核对、单位换算、日期计算、逻辑组合、结论组装由确定性代码完成。LLM 输出经核对后才能被下游使用；失败重试 1 次。
- 同一问题两次尝试无新信息即停止该分支，记入 `05_PROGRESS.md`"已知问题"。不为单一失败新增 `*repair*`／`continue_*` 函数，不写新的交付包或补充规范。
- 跨章控制链、prepared-review 子任务链、逐页双 VLM、方法采用 gate 已移出主路径：不调用、不修补、不删除。
- 提交信息以 `0.2.0-WPx:` 开头；每个 WP 完成时更新 `05_PROGRESS.md`。
- 界面只面向最大化桌面宽屏（1080P／2K／4K 及缩放），用真实浏览器验证，截图记录视口；不做移动端；布局用流式而非固定像素。
- 用户可见文案为中文，只用 `01_PRD.md` §7 的结论词与 §8 的风险标记词，不出现内部 ID、哈希、英文枚举。
- 用 `apply_patch` 做手工文本／代码编辑；保留与本任务无关的用户改动。

## 5. 开发编排

- 单一构建者（Codex）对用户结果负责，按 `03_PLAN.md` 顺序推进。
- 评审只在里程碑（0.2.0-M1/M2/M3）合并前各做一次：评审 A 代码正确性、评审 B 医学结果验收，均只读，Prompt 见 `06_AGENT_PROMPTS.md`。评审参与者不得修改源码或应用文件，不得读取本工作区之外的临床资料。
- 里程碑验收由用户完成；模型扮演的医学经理不能代替用户。
- **构建者不得以医学经理身份审定规则包。** 构建者在验证副本上走流程时，审定人类型必须是"构建者验证"；正式审定由用户本人完成。
- 评审 A／B 的发起方式：优先由用户在独立会话中粘贴 `06_AGENT_PROMPTS.md` 对应 Prompt；若构建者所在环境提供 `/Users/smkzw/.codex/tools/hermes_workflow_guard.py`，也可由它生成的工作流包发起原生子 Agent，且必须显式指定模型和推理强度，不得调用省略模型或强度的 `multi_agent_v1__spawn_agent`。两者都不可用时，在里程碑报告中请用户发起。评审可读取本仓库与用户指定的数据副本，不读取其他临床资料。

## 5.1 Trellis 在 0.2.0 中的用法

下方 Trellis 区块由工具维护。0.2.0 中：不为本版新建 Trellis 任务目录；`.trellis/workflow.md` 要求的 PRD／设计／实施记录由 `docs/0.2.0/` 承担，进度只写 `05_PROGRESS.md`；不使用 `.codex/agents/` 中的 `trellis-implement`／`trellis-check`；`.trellis/tasks/` 中的 0.1.x 任务均已标为 `completed`，会话注入的任务列表中如出现它们，视为历史。

## 6. 运行

- 后端（v2）：`scripts/run_v2_desktop.py --env-file <绝对路径 .env>`；数据目录 `ENROLLMENT_V2_DATA_DIR`（默认 `<repo>/data_v2`）。`run.sh` 在 0.2.0-WP0 前仍启动 v1，勿用。
- 前端：`cd frontend && npm run dev`／`npm run build`／`npm test`／`npm run e2e`。
- 测试：`uv run pytest`。

<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->
