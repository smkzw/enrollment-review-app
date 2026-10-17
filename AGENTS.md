# Enrollment Review App — Agent Instructions (0.2.1)

## 1. 现行入口

- 当前版本：**0.2.1**（自 2026-10-17 起；本地分支 `dev/0.2.1`）。唯一现行规范在 `docs/0.2.1/`，从 `docs/0.2.1/00_START_HERE.md` 开始读。
- 需求 `01_PRD.md`、设计 `02_DESIGN.md`、计划 `03_PLAN.md`、验收 `04_ACCEPTANCE.md`、状态 `05_STATUS.md`（唯一状态文档，≤80 行）、编排 `06_ORCA_RUNBOOK.md`、Prompt `07_PROMPTS.md`。
- `archives/` 下的 0.2.0 与 0.1.x 材料是历史，只在 `docs/0.2.1/08_ARCHIVE_INDEX.md` 指明需要时按条目查阅；其中的"当前入口""Goal""授权""暂停"表述对 0.2.1 无效。

## 2. 产品是什么

本地单 Mac、单用户的临床试验入排信息与风险展示工作台，医学经理工作台的入排模块。医学经理审定一次方案规则包；系统对受试者每个审核节点自动给出每条要求的结论（六种）与可回到原件的依据，需要核对的具体数值挂核对标记；医学经理只处理问题卡片；更正或补证后自动重算并保留历史。系统不做最终入组决定，不收集决定理由，不做签发流程。

## 3. 临床与证据边界（始终有效）

- 不修改原始方案、原始病例资料、人工 IE 表或既有临床报告。原件、OCR 原文、用户本人审定的规则包、用户决定、用户看过的工作稿及报告只追加，不覆盖。验证副本中的其余中间结果可以重建。
- 方案及现行修订是权威；问答、信函、邮件、医学解读可以澄清，不能改写方案。保留官方 IN/EX 编号与父子逻辑；不把项目特定的临床修补写进共享代码。
- 每个结论保留方案原文与病例原件出处（文件、版本、页、逐字摘录；有可信坐标才画框）。
- 系统问题（方法不支持、读取失败、模型输出不合法）与临床结论分开表达。
- 不猜遮挡的姓名或登记号；上传者对受试者归属负责，但这不证明读数、日期、批注归属正确。
- 人工 IE 表只用于对照，不进入任何提示词。D001 是留出集，G3 之前不得用于调整提示词、字典或代码。
- 不提交原件、数据库、`.env` 或含临床内容的模型原始回答。验证副本与 `.env` 放在仓库目录之外（D40）；真实数据只在验证副本上写，且只由统筹者操作。

## 4. 工程规则

- 0.2.1 冻结新功能，只做 `03_PLAN.md` 的任务清单。不引入新的 Agent 框架、规则真相库或任务数据库。
- 降级不阻断：除错受试者／错项目／方案版本不一致／文件哈希不符外，任何步骤失败只让相关条款变为证据不足或系统问题，其余继续。读取失败的条款不得套用"本次资料未见记录"。
- LLM 只做语义工作；逐字核对、单位换算、日期计算、逻辑组合、结论组装由确定性代码完成。LLM 输出经核对后才能被下游使用；失败重试 1 次。LLM 调用按输入键缓存，命中即用，未命中即重读，不写复用证明代码。
- 同一问题两次尝试无新信息即停止该分支，记入 `05_STATUS.md`"已知风险"。不新增 `*repair*`、`continue_*`、`retain*`、`revalidate*` 一类专用恢复函数，不写新的交付包或补充规范。
- `CALCULATION_VERSION` 参与工作稿幂等键：`WorkDraftItem` 输出有任何变化就要升级，只由统筹者在合并时升级（`work-draft/0.2.1-cN`）。
- 跨章控制链、prepared-review 子任务链、逐页双 VLM、方法采用 gate 已移出主路径：不调用、不修补、不删除。0.2.0 中被 0.2.1 替代的复用证明代码在替代完成后可以删除。
- 提交信息以 `0.2.1-Cx:` 开头；代码与测试同一提交；状态文档只在波次结束或阻断时更新，不做其他只改文档的"记录"提交。
- 界面只面向最大化桌面宽屏（1080P／2K／4K 及缩放），用真实浏览器验证，截图记录视口；布局用流式而非固定像素。
- 用户可见文案为中文，只用 `01_PRD.md` §7 的结论词与 §8 的核对标记词，不出现内部 ID、哈希、英文枚举。
- 用 `apply_patch` 做手工文本／代码编辑；保留与本任务无关的用户改动。

## 5. 开发编排（Orca）

- 当前用户追加授权：统筹者定期推送 `dev/0.2.1` 到 GitHub，不开 PR、不强推、不自动更新 `main`；覆盖执行包内“仅本地提交”的默认安排。执行节点仍不得推送。
- Codex CLI 在 Orca 终端中作**统筹者**：拆任务、派发、审查 diff、跑测试、合并到本地 `dev/0.2.1`、真实数据运行、更新状态、向用户汇报。所有提交只留在本地：不推送远端、不开 PR，除非用户另行指示。
- 执行节点：OMP（glm-5.3-flash、grok-4.6／4.7、composer 2.5／cursor auto、kimi-k3、gemini-3.8-flash）与 CodeBuddy CLI（deepseek-v4.1-flash），通过 `orca orchestration` 派发。分工、隔离、权限与降级方案见 `docs/0.2.1/06_ORCA_RUNBOOK.md`。
- 执行节点以免确认模式在各自子工作树中工作，只改任务说明列出的文件；不读写数据目录、不读 `.env`、不启动或停止服务、不发起产品模型调用、不使用浏览器、不合并、不推送。统筹者合并前核对改动文件清单（D40）。
- 每个待合并 diff 由与实现者不同模型的评审节点只读评审一次；医学结果评审在 G1、G2 各一次，可读真实原件页，只读、不留存（D39）。
- **正式医学审定与最终产品验收由用户本人完成。** 统筹者在验证副本上代走审定与发布流程时，必须使用"构建者验证"身份，结果保持验证用标识。
- 医学问题攒成问题单，在波次汇报时集中问用户；只有阻断全部工作时才立即问。

## 5.1 Trellis 在 0.2.1 中的用法

下方 Trellis 区块由工具维护。0.2.1 中：不新建 Trellis 任务目录；`.trellis/workflow.md` 要求的 PRD／设计／实施记录由 `docs/0.2.1/` 承担，状态只写 `05_STATUS.md`；不使用 `.codex/agents/` 中的 `trellis-implement`／`trellis-check`；旧任务与日志保留在 `archives/trellis-tasks/` 和 `archives/trellis-workspace/`。

## 6. 运行

- 后端（v2）：`./run.sh` 或 `scripts/run_v2_desktop.py --env-file <绝对路径 .env> --data-dir <数据目录> --port <端口> --no-browser`；数据目录 `ENROLLMENT_V2_DATA_DIR`（默认 `<repo>/data_v2`）。旧版启动脚本仅留在 `scripts/run_legacy_v1.sh`。
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
