# 入排审核系统 V2：GPT-6 完整接管文档

> 生成时间：2026-09-05 CST
>
> 接管范围：Phase 5 收口与 Phase 5.5 R3 双 VLM 逐页判读
>
> 当前状态：无损暂停；Phase 5、Phase 5.5 均未完成；`claims_complete=false`

## 1. 接管入口与权威顺序

接管后不要从旧对话继续猜测，按以下顺序重新锚定：

1. 最新全局与项目 `AGENTS.md`，尤其 Ponytail 最小改动、Trellis、执行/会商和产品内 harness 边界。
2. `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`：当前 R3 设计权威，重点是文头、§3.3、§4.2、§5.4、§7.0、§7.2、§7.4、§11 第 19–21 条、§12 的 2026-09-02/03 裁决。
3. `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`：阶段状态与 Phase 5/5.5 退出门槛。
4. 当前任务：`.trellis/tasks/09-05-phase55-dual-vlm-page-review/`，优先读本文件、`CHECKPOINT_20260905_R3_NORMALIZER_WIRING_PAUSED.md`、`implement.md`。
5. Phase 5 历史：`.trellis/tasks/08-22-phase5-clinical-facts-profile/`。旧 checkpoint 是证据和演进记录；最新恢复结论优先于早期恢复动作。

工作位置固定为：

```text
/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile
branch: codex/phase5-clinical-facts-profile
HEAD at pause: 411832d
```

不要误在主检出目录实现，也不要重建另一工作树。

## 2. 用户的最终目标与目标用户

产品是医学经理工作台中的“入排审核”子系统，面向：懒于重复操作、视觉敏感、不熟悉计算机和 AI，但临床判断经验很强的原生中文资深医学监查人员。

最终产品必须做到：

- 用户直接上传未经预处理的研究方案和受试者原始资料，由系统内置独立 Agent/harness 完成结构化处理。
- 方案解构不是只抄入选/排除标准，而是从整个方案找齐筛选期、导入期、基线期等审核节点的所有控制点，包括合并用药、洗脱期、访视窗、必做检查、评分细则、复测、例外和跨章节约束。
- 受试者审核从原始资料逐页形成可回源事实、事件、用药暴露和 Patient Profile，再进入结构化入排判断；系统不是最终入组决策人。
- 每一项材料事实和规则判断都能回到文件、版本、页码、原文摘录和图像/文本位置。
- 右侧原始证据区显示 PDF/图片/文档原页滚动，并对当前证据做红框重点标注；无真实坐标时必须降级说明，不能伪造红框。
- 所有用户可见文字使用原生中文临床试验表达，清除工程术语、后端标签、日志式语言和无必要英文。
- 仅面向 1080P 到 4K 最大化宽屏桌面，不做手机或窄屏变体；仍需适配桌面 DPI、浏览器缩放和 1080P/2K/4K。
- 视觉需精炼、专业、信息密度和层级协调，参考 `kangzhe-design`；按钮、弹窗、卡片、图表、表格、阴影和动效保持一致，但功能与临床可读性优先。
- 不做安全测试；聚焦用户功能、临床正确性、来源闭包、交互与视觉验收。

## 3. 长期不变量

### 3.1 临床与来源

- 方案及当前修订案是规则权威。问答、邮件、函件和医学解释可澄清，但不能改写方案。
- 保留官方 IN/EX 编号和父子逻辑；不把 D001、SAR、某个评分、药物、疾病或日期写进共享代码。
- 真实项目只用于发现通用合同缺口和回归，不是硬编码模板。
- 沉默不是阴性；缺文件、未检查、记录不全、专业判断缺失、来源冲突、OCR 风险和未来节点要求必须分开。
- 后续节点资料不能静默回写早期节点结果；快照、处理修订和历史判断保持不可变。
- 类似“6 个月内存在或疑似蠕虫感染”的相对窗口，若方案要求在多个节点判断，筛选期按筛选节点回溯，基线期按基线节点重新回溯；不能固定成某个项目日期。

### 3.2 产品内模型与外部测试角色

- 产品运行链只能使用仓库内代码、显式环境变量和独立模型端点。
- 严禁产品识别、测试或运行依赖本机 Hermes、OMP、ZCode 或其他外部 harness 的模型库、会话、凭据和路由。
- 用户点名的 ZCode/Pi/Gemini/Cursor 等是后续独立会商或真实浏览器 UAT 角色，不是产品内 transport，不能替代产品模型。
- 产品内模型和测试者模型的职责不可交换。Codex/GPT-6 对实际代码、数据库、运行态、浏览器和临床验收负最终责任。

### 3.3 数据与完成声明

- 不修改源方案、受试者原始资料、手工入排表和既有临床报告。
- 不复用失败、取消或 `cancel_requested` 的作业；新尝试从正式入口创建新的不可变内容身份。
- 失败快照不得激活，部分完成不得伪装完整。
- 机械完成数量、测试通过、页面能打开、模型有输出都不等于临床验收。
- 31001 的事实、事件、用药暴露、Profile、期望覆盖和逐项原始证据临床 QC 全部通过前，`claims_complete` 必须保持 `false`。

## 4. 阶段总览

| 阶段 | 当前状态 | 关键结果与边界 |
|---|---|---|
| Phase 0 / 0.5 | 完成并归档 | 冻结旧系统、建立 V2 领域/交互合同、Schema、fixture、设计 token 与 UAT 基线。 |
| Phase 1 / 1.5 | 完成 | React/TypeScript 宽屏原型、工作台/Profile/行动/证据交互；用户批准以多模型角色 UAT 替代真人医学经理试用。 |
| Phase 2 | 完成并归档 | SQLite/SQLAlchemy/Alembic、持久 Job/Checkpoint/租约/取消/恢复/SSE/幂等/乐观并发。 |
| Phase 3 | 完成并归档 | docx 方案导入、方案结构/期别/全文控制解构、RuleModelRevision 发布、重解构与来源闭包。 |
| Phase 4 | 完成并归档 | 增量/全量证据快照、去重、OCR、校对、EvidenceSpan 和原始证据工作台。扫描页历史能力为 text-only 时不画伪红框。 |
| Phase 5 | 进行中 | ClinicalFact/Event/MedicationExposure、发布门禁、双向规则索引、EvidenceExpectation、Patient Profile 和事实修订已建；31001 多轮真实规范化仍未通过最终临床 QC。 |
| Phase 5.5 | 进行中 | 金标/历史横评、ClausePack、页级 Schema、对账、产品自有 R3 harness、迁移 0020 持久化、R3 Normalizer 离线接线已完成；真实模型复跑、31001 R3 运行和浏览器验收未完成。 |
| Phase 6–9 | 未开始 | Phase 5/5.5 门槛未通过前不得启动。 |

## 5. 重要演进与重构记录

### 5.1 Phase 0–4

- 从旧 Markdown/报告驱动页面转为领域合同、SQLite 权威存储和真实 API。
- 前端逐步完成项目看板、Patient Profile、入排工作台、行动中心、任务恢复、证据原页定位和宽屏布局。
- 方案解构从只看入排章节扩展为全文结构单元覆盖；正式方案入口最终冻结为 docx，受试者资料仍支持 PDF/图片。
- Phase 4 建立不可变证据快照、处理修订、OCR 原文/校对分离和定位精度降级。

### 5.2 Phase 5 规则与方案解构演进

- 先后补齐结构化输出、DNF/AND/OR、父子规则、混合表格/段落原子化、期别适用性、全局章节、规则家族、流程表与多访视控制。
- D001 曾形成 1840 级结构单元、1300 级目标和百余语义包的实验路线；该路线暴露了“大范围重新识别整个方案、串行本地模型、耗时数小时”的产品问题。后续裁决是围绕入排审核控制点做结构化检索与语义理解，不把整份方案无差别重识别，也不把 D001 特征写入工程。
- 本地 Qwen3.8-27B 单包曾约 409 秒，全量不可接受；GLM/MTPLX/DeepSeek 候选比较也出现质量或性能不足。历史指标只能用于决策，不能转移为当前模型验收。
- 方案语义解构当前独立路线为 `GLM-5.3-Flash:high -> Qwen3.8-Flash-Next:medium -> DeepSeek V4 Flash:high` 的整候选隔离降级链；这与受试者逐页判读路线不同。

### 5.3 Phase 5 事实与 Profile 演进

- 已实现 ClinicalFact/Event/MedicationExposure 合同、候选 Gate、来源闭包、不可变发布、规则组件双向索引、资料期望、Profile 投影、人工事实修订和影响范围重算。
- 真实 31001 运行曾得到“223 事实、19 事件、10 暴露、130 期望、1 Profile”，但临床 QC 发现事实类型/资料要求绑定错位、`UK` 日期展示、药名推测和邮件讨论误成暴露，因此数量不被接受。
- 随后通用修复包括：资料要求显式绑定、药名逐字来源门禁、讨论/建议不视为实际暴露、未知极性语义保持、数值字符串规范化、日期范围等价、合并事实对事件/暴露引用闭包等。
- 多轮新鲜运行分别暴露部分输出、transport、Schema 修复、来源标签和候选引用问题。每一轮都保留为不可变诊断，不可拼接成“完整结果”。
- v9 低推理运行技术上 25/25 完成，但临床 QC 仍发现奥马珠单抗已形成事实/事件却没有 MedicationExposure，故未通过。
- 2026-09-05 最近运行 `b7e401c614ab4c5089a740b2fba9357b` 因引用不存在的资料要求失败关闭，触发 Phase 5/5.5 受控重叠：OCR 丢手写 CS/NCS 必须由 R3 页级 VLM 解决，不能人工补事实或放宽 Gate。

### 5.4 R2 到 R3 的核心重构

- 早期“选择性视觉观察 + OCR 文本规范化”属于 Phase 5 R2 兼容链，只作为历史作业回放，不再是新 R3 权威输入。
- R3 将受试者资料改为单阶段对称双 VLM 逐页盲读，同一次调用产生结构化事实、证据信号和手写观察，再确定性对账。
- 曾出现 `page_review_lanes.py` 草稿：把 Qwen 当主读降级/普通事实仲裁、写死身份并静默修配置；已明确拒收和清理。当前实现为独立 `app/llm/page_review_harness.py` 等模块。
- Qwen3.8-27B 已退出当前产品路由；Qwen3.8-Flash-Next 只保留手写专项第三读。
- 产品调用链曾被误解为可参考 OMP/Hermes transport。最终纠偏：可以参考端点协议事实，但代码、凭据、会话、模型路由必须由产品自己拥有。

## 6. R3 最终模型与判读合同

### 6.1 三条读道

- `main-A`：`GLM-5.3-Flash:high`，智谱 Coding Plan，`INDEPENDENT_VLM_PROVIDER=zhipu-coding-plan`。
- `main-B`：`MiniMax-M3:high`，cms-smk，`https://new-api.mediportal.com.cn/v1`，显式 `CMS_SMK_API_KEY`。
- `handwriting-C`：`Qwen3.8-Flash-Next:low`，MTPLX.app GUI；只有 A/B 任一发现手写或 A/B 手写分歧时触发，只能写 `handwriting[]`。
- DeepSeek 不进入任何受试者读道；GLM-OCR 只作 OCR 侧车。

### 6.2 页级 Schema

- 不允许 `exclusion_triggered`、`supports_not_met`、`eligible` 等判定词。
- 条款方向只有 `evidence_for | evidence_against | mentions | none`，并保存逐字摘录与来源定位。
- `handwriting[]` 强制存在，分类至少覆盖：签字/缩写+日期、CS/NCS 判断、便签、手写表格单元、其他。
- 保存归一化前原文、规范值和归一化键；NFKC、单位剥离、数值/日期和字段同义归一化先于对账。
- 手写三源任二一致才采信；不一致保留冲突，不自动择优。

### 6.3 条款与确定性边界

- ClausePack 从已发布 RuleModelRevision 投影，内容寻址、版本化、紧凑，不以横评手抽条款为权威。
- 每个 RuleComponent 标注 `determination_mode`：`deterministic | semantic | investigator_judgment`。
- deterministic 条款的 VLM 方向信号在 Reconciler 丢弃，最终方向只能由确定性代码根据事实、数值、单位、日期、锚点和逻辑计算。
- investigator_judgment 条款不由 VLM 自行判断临床意义。
- 方案没有明确阈值的检验异常，仅承认报告单研究者批注或对应节点病历分析；箭头/圈画不算判断。无记录时必须形成 `professional_judgment` 缺口和研究者 ActionRequest，不能落满足/未触发。

### 6.4 失败路由

- `finish_reason=length`：同模型输出预算翻倍，仅重试一次。
- 429：等待，不计入尝试次数；云端每模型并发 2–3。
- 内容过滤：只允许同模型备用端点；端点仍失败则记录原读道待复读。
- 一个主读不能替另一个主读代笔，handwriting-C 也不能代主读。
- 任一页失败、舍弃、降级、第三读缺席都进入 SubjectPageCoverage，不得静默丢页。
- 不设置 temperature，沿用厂商默认采样。

## 7. Phase 5.5 已完成工程

### 7.1 金标与历史横评

- 仓库外隔离目录：`~/tmp/ie-vlm-benchmark-20260902/`。
- 71 页真实资料：SAR III 4 例 44 页，D001 II 3 例筛败 27 页。
- SAR 页面/事实级金标 832 条；7 例条款金标 158 条。
- 报告：`reports/FINAL_REPORT_20260902.md`。
- 横评显示 GLM × MiniMax 历史并集事实召回 0.969、危险漏判 0；这是历史基线，产品 harness 必须在同一金标集重跑。
- 原始页图不能迁入仓库；可迁 harness/ClausePack/评分脚本。旧评分脚本含判定词时不得原样进入产品。

### 7.2 ClausePack 与合同层

- `app/domain/contracts/clause_pack.py`
- `app/projections/clause_pack.py`
- `scripts/export_clause_pack.py`
- SAR III 发布规则投影：23 条官方规则、81 组件，39 deterministic / 20 investigator_judgment / 22 semantic。
- D001 II 发布规则投影：36 条官方规则、67 组件，34 / 19 / 14；横评只含 22 条，不能反向删掉另外 14 条。

### 7.3 页级合同、对账与 harness

- `app/domain/contracts/page_review.py`
- `app/llm/page_review_harness.py`
- `app/services/page_review_execution.py`
- 已实现严格 Schema、归一化、双主读对账、确定性信号丢弃、三源手写二取一、双盲并发、同读道并发限制、失败复读身份、配置漂移拒绝、页图和 ClausePack 哈希核验。
- 产品 transport 直接使用自己的 HTTP 客户端和显式 env，不读取外部 harness。

### 7.4 持久化

- `app/storage/migrations/versions/0020_page_review_persistence.py`
- `app/storage/page_review_models.py`
- `app/storage/page_review_repository.py`
- 五张追加写窄表保存页级判读、对账、读道引用、受试者覆盖和覆盖条目；不改 Phase 4 表。
- 写入/回读校验完整合同哈希、规范列、真实外键和临床作用域闭包；两个主读缺一不能持久化对账，手写读不能替代。

### 7.5 本轮完成：R3 进入 Evidence Normalizer

本轮改动集中在：

- `app/domain/contracts/evidence_normalizer.py`
- `app/services/fact_normalization_source_adapter.py`
- `app/agents/evidence_normalizer.py`
- `app/services/fact_normalization_job_service.py`
- `app/services/fact_normalization_executor.py`
- `app/domain/contracts/page_review.py`
- `app/services/page_review_execution.py`
- `tests/v2/services/test_r3_page_review_normalizer_wiring.py` 及相邻测试

行为：

1. 新增 `EvidenceNormalizerPageReviewInput`，冻结 coverage id、ClausePack 哈希、读道调用、PageReviewRecord、PageReconciliation 和作用域哈希。
2. 只有 accepted 且闭合的页面进入 R3 规范化；失败待复读页、页/包/快照/修订漂移、缺记录和缺对账均拒绝。
3. R3 模型输入含 `ocr_sidecar_pages`、采信事实/信号/手写/冲突和页面处置；OCR 文本不再是事实权威。
4. 未指定 `page_review_coverage_id` 的历史 Phase 5 作业保持旧 `pages.effective_text` 输入，确保旧运行可回放。
5. 新作业幂等哈希包含页级覆盖内容；成功复读会得到新的 coverage id，不与失败 coverage 冲突。
6. `has_eligibility_value=true` 但事实、信号和手写全空的页级记录现在在持久合同层也被拒绝。

## 8. 当前机械验证

本轮最终验证：

```text
3714 passed, 3 skipped, 139 warnings, 2 subtests passed
elapsed: 846.28 s
```

跳过项：

1. Phase 4 真实 OCR 探针产物不存在。
2. Coding Plan 真实连通测试未设置 `INDEPENDENT_VLM_LIVE=1`。
3. 真实单页选择性视觉 E2E 未设置 `SELECTIVE_VISION_LIVE_E2E=1`。

它们是显式 live gate，不是失败。本轮没有调用真实模型，没有用外部 harness。

已执行的聚焦回归包括 97、103、153、190 个测试规模，均通过；编译通过。项目环境没有 Ruff/Black，未临时安装。

## 9. 当前运行与凭据现场

2026-09-05 暂停时：

- `8001`：关闭。
- `8002`：关闭。
- `8910`：关闭。
- `8900`：监听进程 PID 8502，命令为 Xcode Python `uvicorn app:app --port 8900`，属于 `/Users/smkzw/Vibe-Research/backend`，不是本项目；禁止停止或修改。
- 工作树 `.env`：不存在。
- 主检出目录 `.env`：权限 600；确认存在 oMLX、独立 GLM/Coding Plan 和 `DECONSTRUCT_GLM_API_KEY` 变量名；未发现 `CMS_SMK_API_KEY` / `PAGE_REVIEW_MAIN_B_API_KEY`。不得在 handoff 或日志打印值。
- 因 main-B 凭据缺失，产品三端点身份预检必须失败关闭；在补齐前不得发送真实页面。
- MTPLX 未来启用时只能通过 GUI 绑定 Qwen3.8-Flash-Next、显示参数并将 effort 设为 low；不是 Qwen3.8-27B。

## 10. 31001 当前数据库现场

权威候选库：

```text
artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3
size: 153088000 bytes
sha256 at pause: 3ba0604e18e86abe390f942d46d0c47f52bd6b17c2c1fa2e154b8c57398f8903
PRAGMA quick_check: ok
```

现场只读计数反映多轮历史而非当前采信结果：59 jobs、45 normalization runs、2847 版事实、291 版事件、97 版暴露、956 版期望、12 个 Profile 修订。不要拿累计表计数当当前病例结果。

最新运行：

- run `b7e401c614ab4c5089a740b2fba9357b`
- job `844036a5dccd40e8ae0c7892c4966ec3`
- job `failed_final`，13/25，`PARTIAL_OUTPUT`
- run `failed`
- 根因记录：引用不存在的资料要求。
- 不得复用、发布、拼接或计入验收。

当前没有 queued/running/retrying/cancel_requested 作业，也没有活动 lease。Phase 5.5 的 0020 表尚未迁入这份历史运行库并形成真实页级记录；后续必须通过新的受控处理修订运行。

## 11. 已知问题与风险

### 11.1 硬阻塞

- main-B MiniMax 显式凭据缺失，三路预检和真实产品 harness 不能合法运行。
- 金标集尚未用产品 harness 重跑，不能声称达到 0.95 召回或静默漏判 0。
- 31001 尚无 R3 双主读逐页覆盖、对账和基于采信页记录的新规范化结果。
- 31001 原始证据临床 QC 与浏览器验收未完成。

### 11.2 工程风险

- 工作树非常脏：暂停时约 modified 192、added 1、deleted 116、untracked 1310，总计 1619 条。它包含多个阶段积累、用户改动、历史 checkpoint、已批准清理后的删除记录和当前新代码。绝不能 `reset --hard`、`checkout --`、批量删未跟踪文件或把整个状态视为本轮噪声。
- 大量 Phase 5 新模块仍是 untracked，包括 Evidence Normalizer、事实规范化服务/API、ClausePack、page review、迁移 0015/0020 和测试。这是当前功能主体，不是缓存。
- 当前 HEAD 很旧，单凭 `git diff` 无法区分所有历史来源；应以 checkpoint、Trellis 任务和实际测试为恢复依据。
- 旧 R2 selective vision 路线仍需保留历史作业兼容，但新的 R3 作业不能与它混用输入。
- `implement.md` 和 task `design.md` 可能有局部陈述滞后；本 handoff、R3 设计书和实际代码优先，接管后用小改动修正文档，不做大重写。

### 11.3 临床风险

- 用药暴露完整性仍是 Phase 5 核心缺口：模型可能读到给药事实/事件但漏生成 MedicationExposure。
- 邮件中“讨论/建议”不构成暴露，但邮件中对实际用药状态的直接转述是否可作为弱来源，需要形成通用来源等级规则，不能按某封邮件硬编码。
- 无阈值异常、手写 CS/NCS 和病历分析必须按 investigator_judgment 规则呈现，不能由 VLM 或确定性阈值越权判断。
- 来源标签采样漂移不能通过静默改标签解决；失败候选必须可见、可复读或形成缺口。

## 12. 下一步详细执行顺序

### Step 1：只读恢复与差异审查

1. 重读本 handoff、最新 checkpoint、R3 设计书和实施计划。
2. 核对分支/HEAD、数据库 SHA/quick_check、端口、活动 lease 和 env 变量名。
3. 审查本轮 7 个源文件及新增测试，重点确认历史输入兼容、R3 作用域哈希和失败复读 coverage identity。
4. 跑最小决定性测试；不要一开始再跑 14 分钟全量，除非代码发生共享合同修改。

### Step 2：显式 env 与三端点预检

1. 建立 worktree 独立 `.env` 或明确 `ENROLLMENT_ENV_FILE`；不得隐式借主检出目录或外部 harness 凭据。
2. 补齐 `CMS_SMK_API_KEY`；不打印值。
3. 启动产品内预检，核对 main-A/main-B/handwriting-C 的实际模型标识、端点和响应格式。
4. 先做最小合成页，不使用真实临床页；验证 reasoning effort、无 temperature、读道写权限、429/length/content-filter 记录。
5. 任一路由身份不匹配就停止，不 fallback 到 Hermes/OMP/ZCode。

### Step 3：金标复跑

1. 从 `~/tmp/ie-vlm-benchmark-20260902/` 只读加载 71 页清单、金标、ClausePack 对照和可迁移 harness 逻辑。
2. 用产品 harness 生成 PageReviewRecord、PageReconciliation 和 SubjectPageCoverage；不直接运行旧 bench 作为产品结果。
3. 计算：双模型并集事实召回、金标负判定静默漏判、主读分歧率、手写采信召回、冲突呈现率、失败/缺席页数、时延和调用数。
4. 硬门槛：并集事实召回 >= 0.95；金标负判定静默漏判 = 0。
5. 把数字和差异落 artifacts，先报用户批准；未达标先分析提示框架/合同，不调低阈值。

### Step 4：31001 R3 端到端

1. 只读确认 SAR 修订 16、审核节点、冻结证据快照/完整处理修订和 ClausePack。
2. 创建新的内容寻址 page review 运行，不复用任何 Phase 5 旧 normalization run。
3. 每页双主读、必要时手写第三读、确定性对账、覆盖闭包；失败页必须同主读复读或显式阻断。
4. 以 `page_review_coverage_id` 从正式 API 新建 Evidence Normalizer 作业，使 R3 页级记录成为权威、OCR 为侧车。
5. 长轮询到明确终态；不得把 partial/failed 拼接。
6. 生成事实、事件、用药暴露、期望与 Profile，再逐条回到原页核对。
7. 专项核对：知情同意、心电图/检验数值、蠕虫感染的节点相对窗口、实际给药完整性、药名逐字、邮件/讨论边界、手写 CS/NCS、日期精度、冲突并列、未记录不伪阴性。

### Step 5：临床与浏览器验收

1. 完成原始证据临床 QC，记录每个问题的事实、来源、分类和是否阻断。
2. 以独立测试路线做真实登录/点击/创建删除隔离项目/方案解构/上传/页级判读/对账/Profile/入排工作台/证据红框/任务恢复的端到端试用。
3. 测试者可以自由探索，但必须使用系统内置 harness 和产品独立模型，不由测试者自己代做识别或判断。
4. 在 1080P、2K、4K 宽屏检查信息密度、字体、间距、配色、中文临床语言、弹窗/动效、下钻一致性和证据可达性。
5. 外部测试意见是证据，Codex/GPT-6 复核实际页面、数据库和原始资料后决定是否采纳。

### Step 6：阶段收口

1. 金标门槛、31001 临床 QC、浏览器 UAT 均通过后，才回写 Phase 5 与 Phase 5.5 状态。
2. 只有完整结果可把 `claims_complete=true`。
3. 做 Phase 5/5.5 大阶段复盘、剩余风险和 Phase 6 详细计划，提交用户批准。
4. 用户批准前不启动 Phase 6。

## 13. 不要做的事

- 不要把整个方案无差别重新识别当成入排解构。
- 不要为 D001、SAR、31001、具体药物、评分、疾病或日期写特例。
- 不要让 Qwen3.8-Flash-Next 写普通事实或替代主读。
- 不要让 DeepSeek 或 OCR 进入受试者读道。
- 不要在页级 Schema 使用满足/触发/排除等最终判定词。
- 不要让 VLM 决定 deterministic 条款方向或无阈值异常的临床意义。
- 不要设置 temperature。
- 不要静默丢失败页、单源采信、自动解决冲突或激活失败快照。
- 不要调用 Hermes、OMP、ZCode 作为产品 harness。
- 不要触碰 8900 的外部 Vibe-Research 服务。
- 不要清理未归因的未提交文件、历史 checkpoint、数据库、原始资料或审计证据。
- 不要用测试数、模型输出数或任务 25/25 代替临床验收。

## 14. 推荐首轮恢复命令

这些命令只读或运行聚焦测试，不含凭据值：

```bash
pwd
git rev-parse --abbrev-ref HEAD
git status --short
sed -n '1,240p' .trellis/tasks/09-05-phase55-dual-vlm-page-review/CHECKPOINT_20260905_R3_NORMALIZER_WIRING_PAUSED.md
sed -n '1,260p' .trellis/tasks/09-05-phase55-dual-vlm-page-review/implement.md
rg -n 'EvidenceNormalizerPageReviewInput|page_review_coverage_id|ocr_sidecar_pages' app tests/v2
.venv/bin/python -m pytest -q tests/v2/services/test_r3_page_review_normalizer_wiring.py tests/v2/services/test_page_review_execution.py tests/v2/storage/test_page_review_repository.py
```

在凭据补齐前，不执行 live 开关，不启动真实临床页面调用。

## 15. 暂停结论

当前活动任务“将 R3 采信页级记录接入 Evidence Normalizer 并保持旧 Phase 5 兼容”已完成离线实现和全量回归。产品真实三读道、金标复跑、31001 R3 端到端、临床 QC、宽屏浏览器验收和 Phase 5/5.5 收口均未完成。系统已无本工作树活动服务或作业租约，可从上述下一安全动作继续。
