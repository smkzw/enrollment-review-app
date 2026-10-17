# 0.2.1 PLAN：收敛冲刺的任务、波次与编排

本文件是 0.2.1 唯一的执行排序。统筹者（Codex，在 Orca 终端中运行）按这里拆任务、派给执行节点、审查合并、跑真实数据并向用户汇报。Orca 的命令见 `06_ORCA_RUNBOOK.md`。

## 0. 执行规则

### 0.1 角色

| 角色 | 谁 | 负责 | 不做 |
|---|---|---|---|
| 统筹者 | Codex CLI（Orca 终端） | 拆任务、写任务说明、派发、审查 diff、跑测试、合并到本地 `dev/0.2.1`、升 `CALCULATION_VERSION`；**唯一**启动服务、写验证副本、发起产品模型调用、使用浏览器的人；向用户汇报与提问 | 不长时间亲自写大段功能代码（小修小补可以） |
| 实现节点 | OMP（grok-4.7、kimi-k3、composer 2.5／cursor auto、glm-5.3-flash、gemini-3.8-flash）、CodeBuddy（deepseek-v4.1-flash） | 在自己的子工作树里完成一个任务说明，跑任务指定的测试，回报 | 不碰验证副本、`.env`、服务；不发起产品模型调用；不合并、不推送；不改任务说明以外的文件；不改 `CALCULATION_VERSION` |
| 代码评审节点 | 与该任务实现者**不同模型**的一个节点（默认 CodeBuddy deepseek-v4.1-flash） | 对每个待合并 diff 做一次只读评审 | 不改代码 |
| 医学结果评审节点 | 指定的 OMP 模型（默认 gemini-3.8-flash 或 grok-4.6），G1、G2 各一次 | 只读工作稿导出与真实原件页（D39），按 `07_PROMPTS.md` 输出问题清单 | 不代替用户验收；不留存病例内容 |
| 用户 | 医学经理 | 正式审定规则包、确认药物类别成员清单、回答医学问题单、做 G1 现场验收、确认 G2 差异归类 | — |

### 0.2 节奏与停止规则

1. 按波次推进（§2）。同一时刻最多 3 个实现节点＋1 个评审节点。同一文件同一时刻只派给一个节点。
2. **每个任务**：派发 → 节点回报 → 统筹者核对改动文件清单（`git diff --name-only` 必须在任务说明的文件列表内）→ 审 diff → 跑任务测试 → 评审节点评审 → 合并到本地 `dev/0.2.1`（Orca 的 base ref 指向本地 `dev/0.2.1`，后续任务的新工作树自动基于最新代码）。
3. 同一任务两次回报都不合格：统筹者收回任务，重写任务说明或亲自处理，并在状态表"已知风险"记一行。不第三次原样重派。
4. **第 1 波（基础设施）**各子波结束只跑测试和代码评审，不要求临床指标变化。**从第 2 波结束起**，每个波次结束都要在验证副本上真实重算 31001 与 26002，填写结果对比表，按 §0.4 向用户汇报。
5. **结果没动就停**（从第 2 波起适用）：一个波次结束后目标指标（卡片数、可判定数、系统问题数、重算时长）都没变化、也没有新信息，停止并向用户报告原因和建议，不自行开启下一轮修补。
6. **不新增**：新功能、新页面、新交付包、补充规范、专用恢复函数（`*repair*`、`continue_*`、`retain*`、`revalidate*` 一类）。需求变化只改 `01_PRD.md` 对应条目，并在 §12 追加决定。

### 0.3 文档与提交

- 只有一份状态文档 `05_STATUS.md`，**≤80 行**，写给医学经理看；只在波次结束或遇到阻断时更新。任务进度的实时看板用 `orca orchestration task-list`，不写进状态表。不再单独写交接文档。
- 证据（日志、回执、截图、测量 JSON、任务说明）放本机 `output/0.2.1/`，不入库；状态表只写结论和文件名。
- 提交信息格式 `0.2.1-Cx: <做了什么>`。代码与测试同一提交；状态表在波次结束时单独提交一次。
- 所有提交只留在构建机本地仓库：不推送远端、不开 PR，除非用户另行指示。
- `02_DESIGN.md` 只在设计决定改变时修改，不写逐版补丁说明。

### 0.4 给用户的汇报格式（第 0 波、第 1 波整体结束各一次简报；第 2 波起每波一次，≤20 行）

```
0.2.1 第 N 波完成（日期）
1. 结果对比：31001 卡片 a→b，可判定 c→d，系统问题 e→f；26002 …；首次处理 x 分钟，重算 y 秒
2. 这一波改了什么（≤5 条，用户能理解的话）
3. 需要你决定的事（医学问题单；每条：条款、原文、两种理解、对结论的影响、建议）
4. 已知风险或没做成的事
5. 下一波计划
```

### 0.5 真实数据与模型

- **数据与密钥在仓库外**（D40）：第 0 波把验证副本与 `.env` 放到仓库目录之外（例如 `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-data/0.2.1/`），服务用绝对路径与 `ENROLLMENT_V2_DATA_DIR` 启动。执行节点的工作树里没有这些文件。
- 真实数据只由统筹者串行操作。执行节点只用合成夹具和单元测试。
- 产品模型路由沿用现有配置（cms-router／glm-5.3-flash；D30 已授权持续使用）。
- 每次真实运行记录：页数、调用次数、缓存命中数、墙钟时间、模型时间（上游没有返回的写"未知"，不写 0）。

---

## 1. 任务清单与依赖

| 任务 | 内容（DESIGN 章节） | 只能改这些文件（测试可新增） | 依赖 | 完成定义 |
|---|---|---|---|---|
| **C0** 接手与基线 | 统筹者 | — | — | 见 §2 第 0 波 |
| **C2** 读取失败不判满足／未触发 | DESIGN C2 | `app/services/work_draft_calculation.py`（`absence_policy` 及其调用处）、`app/services/work_draft_review.py`（约 600–656 行的失败汇总）、`app/services/work_draft_semantics.py`（失败上报路径） | — | DESIGN C2 的四条合成测试通过 |
| **C1a** 标记契约与事实级标记 | DESIGN C1a、C4 第 1 项 | `app/domain/contracts/work_draft.py`、`app/domain/contracts/facts.py`（只加 `handwritten`、`record_kind` 字段）、`app/domain/risk_flags.py`、`app/services/fact_publication_service.py`、`app/domain/gates/fact_evidence_closure.py` | — | 类别风险不产生标记；`ReviewMark` 契约就绪、旧稿可读；新已核哈希；事件／暴露不再整页阻断；`DECIMAL_SENSITIVE` 判定函数有测试 |
| **C8** 评测脚本 | DESIGN C8 | 新增 `scripts/import_manual_ie.py`、`scripts/compare_with_manual_ie.py` | 任务说明给出 `review_marks` 字段形状 | 合成工作稿与合成人工表跑通导入、对齐、指标、差异清单 |
| **C1b＋C4** 去掉置信链、阻断改降级 | DESIGN C1b、C4 第 2–5 项 | `app/services/work_draft_calculation.py` | C1a、C2 | 新工作稿 `confidence` 为 null、`review_marks` 有值；四种结论级标记与 C4 第 2–5 项各有正反例测试 |
| **C5** 缓存替代复用证明 | DESIGN C5、C4 第 6–7 项 | `app/services/work_draft_review.py`、`app/services/work_draft_semantics.py`、新增 `app/services/llm_call_cache.py`、`app/storage/models.py`、迁移 `0031_llm_call_cache.py`、`app/services/fact_normalization_revalidation.py`、`app/services/fact_normalization_executor.py` 与 `app/services/fact_normalization_job_service.py`、`app/services/evidence_api_read_service.py`（只改复验调用点）、新增 `scripts/new_validation_copy.py` | C1a、C2 | 工作稿路径不再调用复用证明；缓存命中／失效测试；`ScopeViolationError` 只用于身份类错误；已核基于标记 |
| **C6a** 工作稿 Job 与页面性能 | DESIGN C6a | `app/services/work_draft_review.py`、`app/services/review_preparation_command.py`、`app/services/work_draft_projection.py`、`app/services/work_draft_semantics.py`、`app/services/review_context_assembly.py` | C5 | 每个 Job 只组装一次上下文；投影不重组上下文；语义读取只送相关页 |
| **C6b** 抽取提示精简与并行 | DESIGN C6b | `app/agents/evidence_normalizer.py`、`app/services/fact_normalization_executor.py`、`app/services/fact_normalization_job_service.py`、`app/services/review_context_assembly.py`（页覆盖） | C5、C6a | 用 31001 的需求清单离线计算，各资料类型提示 ≤20,000 字符；输出 `handwritten`、`record_kind`；并发可配置；接入缓存；现有抽取测试通过 |
| **C3** 禁用药归入排除条款 | DESIGN C3 | `app/services/work_draft_medications.py`、`app/domain/medication_timing.py`、`app/services/work_draft_review.py`（只改用药计算位置，约 672–678 行）、`app/protocols/medication_restrictions.py`、`app/agents/protocol_medication_author.py`（只加关联校验）、`app/domain/variables/drug_classes.yaml`（只加"是否已确认"结构，不加药名） | C1b＋C4、C6a | 七种情形、类别未确认、其他系统问题存在仍可判未触发的合成测试通过；用药子项进入排除父项汇总 |
| **C7a** 投影与 API | DESIGN C7a | `app/services/work_draft_projection.py`、`app/services/eligibility_review_projection.py`、`app/api/v2/eligibility_review.py` | C1b＋C4、C3、C6a | API 返回 `review_marks`、用药子项带父条款、无置信字段；API 测试通过 |
| **C7b** 前端收敛 | DESIGN C7b | `frontend/src/pages/EligibilityWorkbenchPage.tsx`、`frontend/src/domain/labels.ts`、`frontend/src/api/eligibility-review/*`、工作台与审定页相关组件 | C7a | 卡片规则按 PRD §7.3；无置信文案；标记显示到位；用药子项与三种用药卡片；`npm test` 与构建通过 |
| **C9** 验证与修正循环 | 统筹者主导，按失败家族派修正任务 | 视家族而定 | 第 2 波完成 | 见 §2 第 3 波 |
| **C10** 人工 IE 对照 | 统筹者主导 | — | G1 通过 | 见 §2 第 4 波 |
| **C11** D001 留出 | 统筹者主导 | — | G2 完成 | 见 §2 第 5 波 |

迁移编号：只有 C5 新建迁移 `0031_llm_call_cache.py`（工作稿条目存在 `payload_json` 中，C1a 不需要迁移）。

建议节点分配（统筹者可调整）：C2、C5、C6a、C6b 交给同一个"管道"节点顺序完成（熟悉 `work_draft_review.py`）；C1a 一个节点；C1b＋C4、C3、C7a 交给同一个"计算"节点顺序完成；C8 一个节点；C7b 一个前端节点。

---

## 2. 波次

```
第0波 C0（统筹者）
  ─► 第1a波  C2 ｜ C1a ｜ C8
  ─► 第1b波  C5（依赖 C1a、C2） ｜ C1b＋C4（依赖 C1a、C2）
  ─► 第1c波  C6a（依赖 C5）
  ─► 第2波   C6b（依赖 C6a） ｜ C3（依赖 C1b＋C4、C6a） → C7a → C7b
  ─► 第3波   新验证副本＋真实重算＋修正循环＋用户审定＋G1
  ─► 第4波   G2 人工 IE 对照
  ─► 第5波   G3 D001
```

### 第 0 波：接手与基线（统筹者，不派节点）

1. 核对构建机：工作树 `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/build-0.2.0`（或新建 `.worktrees/build-0.2.1`）；确认 `git status` 干净、当前为 `dev/0.2.0`（`8761370a` 或其后续）、专用服务未在运行。从 `dev/0.2.0` 创建本地分支 `dev/0.2.1`，按执行包 `README.md` 应用规范包（归档 `docs/0.2.0`、复制 overlay 文件），提交 `0.2.1-C0: 应用 0.2.1 规范包`。
2. **数据与密钥移出仓库**（D40）：用 SQLite backup（参照 `app/storage/migrate.py`）把当前验证副本连同工件目录复制到仓库外目录，`.env` 也放到仓库外；用新路径启动服务（`scripts/run_v2_desktop.py --env-file <仓库外 .env> --data-dir <仓库外数据目录> --port 61134 --no-browser`），确认能读到 31001、26002。原工作树中的 `data_v2` 保留不动（作历史），之后不再使用。
3. 按 `06_ORCA_RUNBOOK.md` 完成 Orca 安装检查、`orca repo set-base-ref` 指向本地 `dev/0.2.1`、冒烟测试（≤1 小时，失败按降级方案）。
4. 读取 31001 当前工作稿 `47c7939e…` 与 26002 当前工作稿 `9cc63d17…`，填写结果对比表的**基线行**（卡片数按现行界面规则、可判定数、证据不足数、系统问题数、最近一次重算耗时）。
5. 把 31001、26002 中出现的药名与各药物类别现有成员整理成"类别成员确认表"，放进状态表的医学问题单（供用户在第 3 波前确认，见 DESIGN C3）。
6. 确认 `.trellis/workflow.md` 中 `[workflow-state:no_task]` 一段（每轮注入的提示）已是 0.2.1 版本（规范提交已改为"不使用 Trellis 任务、不询问是否创建"）；若 `trellis update` 把它改回，重新改。
7. 向用户发第 0 波简报（编排是否就绪、基线、类别成员确认表）。

### 第 1 波：基础设施（并行实现，只跑测试）

- 1a：派发 C2、C1a、C8（3 个节点）。合并顺序：C2 → C1a → C8。
- 1b：C2、C1a 合并后派 C5（管道节点）与 C1b＋C4（计算节点）。
- 1c：C5 合并后派 C6a（管道节点）。
- 每次合并统筹者按 DESIGN §2 第 5 条升 `CALCULATION_VERSION`（`WorkDraftItem` 输出有变化时）。
- 第 1 波整体结束：全量后端测试与前端测试各跑一次，记录与起点相比新增的失败 ID；向用户发简报。

### 第 2 波：抽取、用药、API、前端

- 派发 C6b（管道节点）与 C3（计算节点）。C3 合并后派 C7a（计算节点），C7a 合并后派 C7b（前端节点）。
- 任务说明里由统筹者写明 API 中 `review_marks` 与用药子项的字段形状。
- 第 2 波结束：在验证副本上对 31001、26002 做一次**不调模型**的工作稿重算（语义读取首次会因缓存为空而调用模型，计入记录），填写结果对比表，向用户汇报。

### 第 3 波：新副本、真实重算、修正循环、G1

1. 用 `scripts/new_validation_copy.py` 生成新的验证副本（仓库外），以新的处理修订重算。
2. **抽取推理强度对照**：统筹者在 31001 的 24 页上分别以 high、medium 跑一次抽取，比较被采用事实的差异和耗时；差异只在格式上时改用 medium。31001 这次完整首次处理的耗时用于 G1-4。
3. 对 31001、26002 做完整重算，记录耗时与结果。
4. 把剩余的系统问题与证据不足按原因家族分组（来源读取、字段未形成、计算方法、真实方案歧义），每个家族派一个修正任务，修完再重算。真实方案歧义写入医学问题单，不靠代码绕过。
5. **用户确认与正式审定**：用户确认药物类别成员清单；C3 让用药条目带上了关联排除条款，统筹者请用户在审定页正式审定 S2–S4 的条目并发布（构建方不得代签）。之后用新的正式规则包重算一次。
6. 统筹者按 `04_ACCEPTANCE.md` G1 自查；医学结果评审节点做一次（D39）；然后请用户做 G1 现场验收。

### 第 4 波：G2 人工 IE 对照

1. 请用户提供中心 31 人工 IE 表的位置（或确认构建机上的路径），用 `import_manual_ie.py` 导入。
2. 统筹者通过正式上传入口逐例接入中心 31 其余受试者的原始资料，生成工作稿。
3. 运行 `compare_with_manual_ie.py`，差异按 PRD R-F2 归类。系统错判与系统漏提示按家族派修正任务；每次修正后重跑对照。
4. 差异清单与归类交用户确认；医学结果评审节点做一次（D39）。

### 第 5 波：G3 D001 留出

D001 从上传方案到工作稿走一次（规则包由用户审定，或在用户同意时以构建者验证身份走流程并标明）。G3 之前不得用 D001 调提示、字典或代码；发现的问题先记录、交用户，再决定是否修。
