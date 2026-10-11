# 0.2.0 PLAN：工作包与执行顺序

本文件是 0.2.0 唯一的执行排序。每个工作包（WP）写明目标、对应需求、改动点、完成定义、验证方式和不做的事。进度只记在 `05_PROGRESS.md`。

## 0. 执行规则

1. **顺序执行**，单一构建者。0.2.0-WP3 与 0.2.0-WP4 可交错，但同一时刻只有一个 WP 处于"进行中"。
2. **每个 WP 结束时**：相关测试通过；更新 `05_PROGRESS.md` 一行；一次提交（提交信息以 `0.2.0-WPx:` 开头）。
3. **里程碑**（M1/M2/M3）结束时：跑 `04_ACCEPTANCE.md` 对应检查；触发评审 A 与评审 B 各一次（Prompt 见 `06_AGENT_PROMPTS.md`）；向用户提交里程碑报告，等待用户验收后再进入下一里程碑。
4. **停止规则**：同一问题两次尝试无新信息→停止该分支，写进 `05_PROGRESS.md`"已知问题"，按降级原则（PRD P3）继续其他工作。不得为单一失败新增 `*repair*`／`continue_*` 类函数，不得新增交付包或版本化的补充规范；需求变化只改 `01_PRD.md` 对应条目并在其 §12 追加决策。
5. **真实数据与模型调用**：开发期在本机 `data_v2` 的**新副本**上运行。数据库用 SQLite backup API 复制（参照 `app/storage/migrate.py` 中的做法），不在 WAL 活跃时直接拷贝文件；同时复制数据目录下的工件文件（原件、页图、模型原答）。模型路由沿用 `.env` 现有配置，不做模型横评。不设调用次数硬上限，但每个 Job 在 `05_PROGRESS.md` 记录调用次数与耗时。
6. **时间盒**：一个 WP 连续 3 个工作会话仍未达到完成定义，或同一阻断出现第 2 次，停止并向用户报告：现状、首个阻断、已尝试的办法、建议的取舍。
7. **测试**：改哪层跑哪层；里程碑前跑一次全量 `uv run pytest` 与前端 `npm test`，结果记入进度表。已有失败测试先查明是否与本 WP 相关，不相关的记入"已知问题"，不借机重开旧功能。

## 1. 总览

| WP | 名称 | 需求 | 里程碑 |
|---|---|---|---|
| 0.2.0-WP0 | 仓库收口与基线 | — | M1 |
| 0.2.0-WP1 | 规则包：解除跨章前置＋逐条审定机制（含 REQ 排除）＋发布 | R-A1, R-A3, R-A6–A9 | M1 |
| 0.2.0-WP2 | 变量字典＋规则侧变量绑定＋用户审定发布 | R-A5 | M1 |
| 0.2.0-WP3 | 定向抽取＋逐字核对＋风险标记＋自动采用 | R-B1–B7 | M1 |
| 0.2.0-WP4 | 工作稿判定引擎（确定性＋REQ）＋结论与置信 | R-C1, R-C2, R-C6, R-C8, R-C9 | M1 |
| 0.2.0-WP5 | 范围解析＋禁用药＋语义与研究者判断 | R-A2, R-A4, R-C3–C5, R-C7 | M2 |
| 0.2.0-WP6 | 工作台：问题卡片＋三栏＋文案 | R-D1–D5 | M2 |
| 0.2.0-WP7 | 更正／补证／已核→自动重算→版本链＋报告 | R-E1–E6 | M2 |
| 0.2.0-WP8 | 金标准对照评测＋留出集 | R-F1–F3 | M3 |

```
WP0 → WP1 → WP2 → WP3 ⇄ WP4 ──► M1 ──► WP5 → WP6 → WP7 ──► M2 ──► WP8 ──► M3
```

---

## 0.2.0-WP0 仓库收口与基线

**目标**：让构建者在一个干净、只指向 0.2.0 的仓库里工作，并记录可复现的起点。

**改动点**
1. 已由审阅会话完成（在分支 `dev/0.2.0` 首个提交中）：`context/ reviews/ metrics/ prompts/ conference/ docs/`（旧）与根目录 `SYSTEM_REVIEW_REPORT.md DOCUMENTS_MAP.md WP00_BASELINE_20260920.txt` 及旧 `AGENTS.md` 已移入 `archives/`；新 `AGENTS.md` 与 `docs/0.2.0/` 已写好；`.trellis/tasks/` 下 0.1.x 的 4 个 `in_progress` 任务的 `task.json` 已改为 `completed`。
2. 本 WP 继续完成剩余归档（这几处有代码依赖，需同时修路径）：
   - `.trellis/tasks/{08-12-enrollment-review-v2,08-13-phase1-frontend-shell,08-22-phase5-clinical-facts-profile,09-05-phase55-dual-vlm-page-review,09-11-e2e-eligibility-review,archive}` → `archives/trellis-tasks/`（用这个名字保持目录深度，`slice59n_representative_group_control_replay.py` 中 `parents[5]` 不受影响）；`.trellis/workspace/{codex,smkzw}` → `archives/trellis-workspace/`。
   - 修复依赖：`tests/v2/protocols/test_slice61aw_replay_acceptance.py:12`、`tests/v2/protocols/test_protocol_replay_harness.py:458,496`、`tests/v2/protocols/test_slice58g_phase_rationale_quality.py:34-43,419`、`tests/v2/protocols/test_slice58h_cross_heading_packing.py:44-52`、`frontend/e2e/uat-chinese-native.spec.ts:22-30` 改指向新位置（或把所需的约 650KB 固定件复制进 `tests/fixtures/`）。
   - `plans/ runs/` 及 `artifacts/` 中已跟踪文件 → `archives/`；同步修 `scripts/run_isolated_page_revision.py:119`、`scripts/run_frozen_product_reader.py:75`、`scripts/freeze_0926_source_tasks.py:23`、`scripts/run_protocol_control_smoke.py:1280`（默认输出改到 `output/`）；`.gitignore` 中 `artifacts/` 白名单相应删除（`artifacts/*` 继续忽略）。
   - `.trellis/spec/frontend/directory-structure.md:49-50` 去掉对旧 docs/plans 的引用；`.trellis/spec/backend/quality-guidelines.md` 中"跨章节方案控制点的语义增量"一节（约 `:162` 起）与 `:195`、`.trellis/spec/backend/persistent-jobs.md:48` 前后关于跨章预算账本的条目，标注为"0.1.x 跨章控制链专用，0.2.0 主路径不适用"。
   - 不使用 `.codex/agents/` 中的 `trellis-implement`／`trellis-check` 子 Agent，也不为 0.2.0 新建 Trellis 任务目录；`.trellis/workflow.md` 要求的 prd/design/implement 由 `docs/0.2.0/` 承担。
3. `run.sh` 改为启动 v2（`scripts/run_v2_desktop.py`），v1 启动方式移到 `scripts/run_legacy_v1.sh`。
4. `.env.example` 增加 `ENROLLMENT_V2_DATA_DIR`、`ENROLLMENT_OPERATOR_NAME`。
5. 版本号：`pyproject.toml` 与 `frontend/package.json` 改为 `0.2.0`。
6. 记录基线：`uv run pytest -q` 与 `npm test` 的通过／失败数、失败测试清单（只记录，不修）；本机 `data_v2` 中 SAR 方案、31001 资料、草稿 rev21 是否存在（读回 ID 与修订号）。

**完成定义**：`git grep -n -E "delivery_1006V1|0927V1|1001V1|1006V1" -- . ':!archives' ':!docs/0.2.0'` 无结果（WP0 起点时命中在 `plans/`、`runs/`、`.trellis/tasks/`，随归档消失）；基线测试结果写入 `05_PROGRESS.md`；Trellis 会话启动注入的 ACTIVE TASKS 中不再出现旧任务。

**验证**：先保存一次全量基线；归档后集中运行受影响的历史材料读取、启动及配置测试，与基线相比无新增失败；`./run.sh` 能打开 v2 界面。全量前后比较并入 M1-9 的统一窗口，不为纯路径迁移重复跑全库。WP0 完成不代表 M1-9 已通过。

**不做**：不删除任何代码；不修旧失败测试。

---

## 0.2.0-WP1 规则包：解除跨章前置＋逐条审定＋发布

**目标**：具备"逐条审定→发布"的完整机制，SAR 草稿 rev21 能在不依赖跨章控制链的情况下发布（本 WP 只做验证用发布，正式审定在 WP2 末由用户完成）。

**改动点**（详见 DESIGN §5.1、§5.3、§5.4、§5.5）
0. **只读诊断**（先做，结果写进度表）：rev21 的 `session_kind`；SAR 是否已有已发布项目；应走 `publish_first_project` 还是 `publish_re_deconstruction`；新分级下 rev21 的结构性问题清单。
1. 后端：`_require_control_publication_references` 不再在主流程调用（`protocol_workbench_service.py:3304, 3398`）；门禁 `publishable` 按检查名只看结构性检查（`deconstruction_gate.py:2018-2022`），其余作为每条规则的提示返回；**提升 `DECONSTRUCTION_GATE_VERSION`**（门禁结果有缓存）。
2. 新表 `rule_review_records` 与 API：审定／撤销审定（含 `reviewer_kind`）；按内容哈希判断有效；发布前校验全部条目已审定；含构建者验证审定的发布标 `verification_only`。
3. REQ 审定：排除项与必需结果变量（PRD R-A3）。
4. 前端：`ProtocolJobFlow.tsx:92` 去掉控制目录条件；规则旁显示提示与"审定通过"；发布按钮按 R-A8；`actor` 改为本机用户名；验证用规则包有明显标识。
5. 从本机已有 SAR 草稿 rev21 继续（不重跑起草）。rev21 的结构性问题能通过界面编辑解决的，用界面解决。

**完成定义**：在新数据副本上，构建者以"构建者（验证）"身份逐条审定 rev21 并发布为 `verification_only` 的 `RuleSet`；数据库读回审定记录、内容哈希与规则修订号一致；未跑任何跨章控制 Job。

**验证**：单元测试覆盖"未审定不能发布""该条内容改动后审定失效、其他条保留""结构性错误阻止发布、提示级不阻止""门禁版本提升后不读旧缓存"；一次真实界面操作（截图＋读回）。

**不做**：不改起草提示词；不跑跨章控制 Job。

---

## 0.2.0-WP2 变量字典＋规则侧变量绑定

**目标**：规则包中每个需要病例数据的条件都绑定到一个 `variable_id`。

**改动点**（DESIGN §4.1、§4.2）
1. `app/domain/variables/`：`dictionary.py`、`core_variables.yaml`（先覆盖 SAR 与 D001 共性：年龄、性别、身高体重 BMI、血常规主要项、肝肾功能、妊娠检测、血清特异性 IgE、症状评分、生命体征、心电图结论等；D001 专有变量不得在 M3 前加入，以免污染留出集）、`drug_classes.yaml`。
2. `EvidenceRequirement.variable_id` 字段；P4 绑定步骤：一次 LLM 调用为草稿中各谓词建议变量，程序校验类型与单位兼容。
3. 审定界面：谓词的 subject/attribute 自由输入改为变量下拉；可新增项目变量（随规则包保存）。
4. 发布校验：确定性谓词必须有 `variable_id` 且有对应 `EvidenceRequirement.predicate_ids`。

5. 凡含 `requires_professional_judgment` 谓词的组件，确保有一条 `required_source_types` 含 `investigator_assessment` 的 `EvidenceRequirement`（DESIGN §7.4）。
6. **用户审定发布**：绑定完成后通知用户，由用户本人在界面中逐条审定（`reviewer_kind=medical_manager`）并发布。等待期间构建者用验证用规则包继续 WP3。

**完成定义**：用户审定发布的 SAR 规则包中，所有确定性谓词都有 `variable_id`；读回验证；`verification_only=false`。

**验证**：字典加载与校验测试；绑定校验正反例（类型不符、单位不可换算被拒）。

**不做**：不引入 LOINC／ATC；不做自动匹配别名到事实（别名只给抽取提示用）。

---

## 0.2.0-WP3 定向抽取＋逐字核对＋风险标记＋自动采用

**目标**：31001 的资料按需求清单抽出带 `variable_id` 的事实，经逐字核对后自动采用，风险以标记表达。

**改动点**（DESIGN §6）
1. S2 需求清单生成（纯函数，按节点过滤规则包）。
2. `evidence_normalizer` 输入需求清单、输出 `variable_id`／`date_role`；Schema 用枚举限定。
0. 确认 31001 现有资料快照与 OCR 状态可直接复用（R-B1，不改代码），记录每页状态。
3. `_validate_assertion_text_closure` 对肯定事实同样核 `assertion_text` 与数值；归属核对与参考范围排除（`ATTRIBUTION_UNCERTAIN`）；`IMPLAUSIBLE_VALUE`；整页阻断改为 `LOW_OCR_CONFIDENCE`；页覆盖改为逐页（`validate_page_coverage`）；新增 `app/domain/risk_flags.py`；`fact_rule_index.py:177` 去掉 fact_type 相等。
4. 被拒候选与缺失页写 `SystemIssue`。
5. 抽取缓存（文件版本哈希＋需求清单哈希＋提示版本），供补证与规则包再发布时只处理新增部分（DESIGN §4.5）。

**完成定义**：在新数据副本上对 31001 的 24 页跑一次定向抽取，已采用事实中年龄、EOS 等关键变量存在且带页码与摘录；被拒候选数及原因分布记录在进度表。

**验证**：核对函数正反例（编造摘录被拒、数值不在摘录中被拒、手写区域打标记）；真实运行的调用次数、耗时、采用数、拒绝数。

**不做**：不恢复双 VLM；不新增局部视觉复核类型。

---

## 0.2.0-WP4 工作稿判定引擎＋结论与置信

**目标**：对 31001 筛选期生成第一份含真实结论的工作稿（0.2.0-M1 的核心）。

**改动点**（DESIGN §7）
1. `app/services/work_draft_review.py`（Job 类型 `work_draft_review`）：`prepare_review` → `select_by_variable` → `calculate_component_review` → `review_conclusions.compose` → 写 `ReviewRun(run_kind="work_draft")`。
2. `ReviewRun.run_kind` 迁移；`WorkDraftItem`、`SystemIssue` 契约（见第 7 项）。
3. REQ 判定映射（DESIGN §5.5）；"本次资料未见记录"政策（PRD R-C6）。
4. 投影读取最新工作稿（`eligibility_review_projection.py:874` 起）；后端 `_DECISION_LABELS` 统一为六结论。
5. `app/graph/subject_graph.py` 声明表（DESIGN §2.1）：覆盖受试者图 S1–S8，测试断言节点集合与文档中 S 开头的行一致。S6 在本 WP 中为占位节点（输出空结果），WP5 实现。
6. 事实与规则包版本解耦（DESIGN §4.5）：`select_by_variable` 不按 `rule_set_revision` 过滤事实。
7. 工作稿存储：`work_draft_items`、`work_draft_acknowledgements`、`ReviewRun.system_issues`（DESIGN §4.4），不写 `FinalAssessment`。

**完成定义**：31001 筛选期工作稿中，IN-01 年龄等确定性条款有"满足／不满足"类真实结论；每条结论在 API 中带依据（事实 ID→页码→摘录）；系统问题单列。

**验证**：`select_by_variable`、置信规则、REQ 映射的单元测试；一份真实工作稿的读回与人工抽查（构建者对照原件逐条检查确定性条款，记入进度表）。

**不做**：不实现语义条款与禁用药（留给 WP5）；不改前端布局（留给 WP6，M1 用现有工作台查看）。

### 0.2.0-M1 里程碑检查

按 `04_ACCEPTANCE.md` §2 执行；评审 A＋评审 B 各一次；向用户报告并等待验收。

---

## 0.2.0-WP5 范围解析＋禁用药＋语义与研究者判断

**目标**：四块范围全部进入规则包，语义类与研究者判断类条款能给出带引用的结论。

**改动点**
1. `app/protocols/review_scope.py`（DESIGN §5.2）＋范围清单确认界面（方案页新步骤）。
2. `ProhibitedMedicationItem` 抽取（一次 LLM 调用，读 S4 章节）＋审定界面＋发布。
3. 用药暴露适配与禁用药判定（DESIGN §6.3）。
4. 语义命题检索与研究者判断摘录核对（DESIGN §7.4）。

**完成定义**：SAR 规则包含范围清单、REQ、禁用药条目，均经审定发布；31001 工作稿中语义／判断类条款有引用或明确的"需研究者判断"；禁用药条款有结论。

**验证**：引用识别正则的正反例（含中文数字章节号）；禁用药时间窗正反例（持续使用、只有开始日期、半衰期）；真实运行读回。

---

## 0.2.0-WP6 工作台：问题卡片＋三栏＋文案

**目标**：MM 进入受试者节点先看到问题卡片，点入三栏核对，文案只用六结论与风险标记词。

**改动点**（DESIGN §9）：`IssueCardList`；三栏联动与返回保留状态；置信显示；系统问题抽屉；`labels.ts` 统一；文案检查（无内部 ID、哈希、英文枚举）。

**完成定义**：31001 筛选期在真实浏览器中走通"卡片→三栏→原件页→返回"；1080P／2K／4K 三张截图哈希互不相同且记录视口。

**验证**：组件测试＋Playwright 真实后端测试；截图。

---

## 0.2.0-WP7 更正／补证／已核→自动重算→版本链＋报告

**目标**：完成一次真实更正与一次补证，系统自动生成新版工作稿，旧版可查。

**改动点**（DESIGN §8）：更正对话框支持 `variable_id`；`fact_correction_executor` 成功后排队 `work_draft_review`；增量上传与"标记已核"同样触发；`supersedes_review_run_id` 写入；版本切换与对比；打印版报告。

**完成定义**：在 31001 上完成：①更正一个数值→受影响条款结论或置信变化、无关条款不变；②补传一份资料→相应"证据不足"变为真实结论；两次操作各生成新版工作稿，旧版可打开且引用旧来源。

**验证**：重算范围的单元测试（无关条款不变）；真实界面操作截图＋数据库读回。

### 0.2.0-M2 里程碑检查

按 `04_ACCEPTANCE.md` §3；评审 A＋B；用户验收，并确认 PRD §9 指标阈值。

---

## 0.2.0-WP8 金标准对照评测＋留出集

**目标**：用人工 IE 表衡量系统，并在未调参的 D001 上验证换方案流程。

**改动点**（DESIGN §10）：`scripts/import_manual_ie.py`、`scripts/compare_with_manual_ie.py`；中心 31 其余受试者批量运行；D001 从 F1（上传方案→起草→审定→发布）走到 F3。

**完成定义**：对照报告（指标＋差异清单）交付用户；D001 运行记录（代码快照、规则包审定耗时、工作稿、问题清单）写入进度表。

**验证**：对照脚本单元测试；报告抽样核对。

**不做**：在 D001 上发现问题后，先记录、交用户，不立即针对 D001 调提示词（否则 D001 不再是留出集）。

### 0.2.0-M3 里程碑检查

按 `04_ACCEPTANCE.md` §4；评审 A＋B；用户验收。
