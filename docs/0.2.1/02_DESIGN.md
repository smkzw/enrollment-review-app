# 0.2.1 DESIGN：现状架构与收敛改动

本文件分两部分：§1 说明已经建成的系统（改代码前的地图）；§2–§4 说明 0.2.1 的设计规则与具体改动。所有 `文件:行号` 以 `8761370a` 为准，行号漂移时以函数名为准。0.2.0 设计原文（含计算 v31–v55 的逐版补丁说明）在 `archives/0.2.0-docs/02_DESIGN.md`，只在追溯某段代码的来由时查阅。

---

## 1. 已建成的主链

```
方案侧（每个方案版本一次）
  DOCX结构快照 → 官方IN/EX解构(rev21) → 范围解析 review_scope.py → 变量绑定 protocol_variable_binder.py
  → 禁用药条目 protocol_medication_author.py → 审定页（分类/疑点/集中批准）protocol_rule_review.py → 发布 RuleSet

受试者侧（每例每节点，上传或更正触发）
  资料快照+OCR → 需求清单 → 定向抽取 evidence_normalizer.py → 逐字核对/采用 fact_publication_service.py
  → 工作稿 Job work_draft_review.py
       ├ 上下文冻结 review_context_assembly.py（经 review_preparation_command.prepare_review）
       ├ 语义/研究者判断读取 work_draft_semantics.py（LLM，每批 16 个目标）
       ├ 计算 work_draft_calculation.py（select_by_variable → calculate_component_review）
       ├ 父规则汇总 compose_parent，之后计算用药 work_draft_medications.py
       └ 保存 ReviewRun(run_kind=work_draft) + work_draft_items(payload_json) + system_issues
  → 投影 work_draft_projection.py → API eligibility_review.py → 工作台 / 时间图 / 报告

更正与补证：fact_correction_executor → 自动排队工作稿；增量上传 → 自动整理 → 自动出稿；supersedes_review_run_id 已写入
```

### 1.1 模块清单（0.2.0 新增或大改）

| 模块 | 行数 | 作用 | 0.2.1 处理 |
|---|---|---|---|
| `app/domain/variables/`（dictionary.py、core_variables.yaml、drug_classes.yaml） | ~180 | 变量字典与药物类别（类别表目前只有 3 类） | C3 需要类别成员清单 |
| `app/services/protocol_variable_binding.py`、`app/agents/protocol_variable_binder.py` | ~300 | 规则侧变量绑定 | 冻结 |
| `app/protocols/review_scope.py`、`app/services/protocol_review_scope_service.py` | ~1000 | 范围解析 | 冻结 |
| `app/agents/protocol_medication_author.py`、`app/protocols/medication_restrictions.py` | ~315 | 禁用药条目 | C3 |
| `app/services/protocol_rule_review.py` | 192 | 逐条审定 | 冻结 |
| `app/agents/evidence_normalizer.py` | 大改 | 定向抽取 | C6b |
| `app/domain/risk_flags.py` | 146 | 风险标记 | C1a |
| `app/services/fact_publication_service.py` | 大改 | 逐字核对与采用 | C1a |
| `app/domain/gates/fact_evidence_closure.py` | 大改 | 采用门禁 | C1a（C4 第 1 项） |
| `app/services/work_draft_review.py` | 716 | 工作稿 Job、复用证明、已核 | C2、C5、C6a、C3（用药调用处） |
| `app/services/work_draft_calculation.py` | 1059 | 计算、置信、组装 | C2、C1b＋C4 |
| `app/services/work_draft_semantics.py` | 763 | 语义读取 | C5、C6a |
| `app/services/work_draft_medications.py`、`app/domain/medication_timing.py` | ~310 | 用药判定 | C3 |
| `app/services/review_context_assembly.py` | 496 | 上下文冻结与页覆盖 | C6a、C6b |
| `app/services/fact_normalization_revalidation.py` | 180 | 旧原答复验 | C5 由缓存替代 |
| `app/services/work_draft_projection.py`、`app/api/v2/eligibility_review.py` | — | 投影与 API | C7a |
| `app/graph/subject_graph.py` | 23 | 受试者图节点名表 | 保留 |
| 前端 `EligibilityWorkbenchPage.tsx`、`labels.ts`、`api/eligibility-review/*` | — | 工作台 | C7b |

评测脚本 `scripts/import_manual_ie.py`、`scripts/compare_with_manual_ie.py` **尚不存在**（C8 新建）。

---

## 2. 设计规则（落到代码上的判断标准）

1. **降级优先**：除身份类错误（受试者、节点、方案版本、资料哈希不一致）外，任何节点失败只影响依赖它的条款；`ScopeViolationError` 只用于身份类错误。
2. **读取失败不得产生满足／未触发**：某条款的任何读取目标失败时，正向发现（不满足／已触发）保留，其余显示为系统问题（C2）。
3. **LLM 输出须经确定性核对**；失败重试 1 次，仍失败记系统问题。
4. **缓存替代证明**：LLM 调用按"角色＋模型＋提示版本＋规范化输入"缓存，键一致即用，不一致即重读。不再写"旧原答在新上下文中仍有效"的证明代码。
5. **计算版本**：`CALCULATION_VERSION`（`work_draft_review.py:26`）参与工作稿 Job 的幂等键（`work_draft_review.py:363-375`），投影在版本不一致时显示"方法已变"（`work_draft_projection.py:51`）。因此：**`WorkDraftItem` 输出的任何变化都要升版本；只由统筹者在合并时升级**，格式 `work-draft/0.2.1-cN`（N 从 1 递增）。执行节点不改这个常量。
6. **不新增专用恢复函数**；同一类失败出现两次，先找第一因果错误。

---

## 3. 开发编排

Codex 在 Orca 终端中作统筹，OMP（多模型）与 CodeBuddy 作执行节点。分工、隔离、合并与真实数据规则见 `06_ORCA_RUNBOOK.md`；任务拆分、文件归属与依赖见 `03_PLAN.md`。

---

## 4. 收敛改动

### C2 读取失败不得判满足／未触发（安全修复，G1 必过）

**现状**：
- `work_draft_calculation.py:501-512` 只要 `source_results` 中没有该条款的键，就走 `absence_policy`，可得到"未触发"。
- `needs_source`（`work_draft_calculation.py:533-536`）不含病史类谓词，但读取目标 `targets_for_review`（`work_draft_semantics.py:363-368`）包含病史、用药、布尔、暴露、操作类谓词——正是 `absence_policy` 覆盖的条款（约 420–458 行）。
- `work_draft_review.py` 约 600–656 行汇总了 `failed_components`，但只把"非确定"的结论改为系统问题（约 649–653 行），按政策得出的"未触发"会保留；`failed_components` 也没有传进 `calculate_work_component`。
- 其他读取缺失路径：服务商拦截（约 566 行）、无可读页（`work_draft_semantics.py` 约 688 行）、提示超过 20 万字符（约 721 行）。

**改动**：
1. 以该条款在 `targets_for_review` 中的**全部目标 ID**为准判断读取是否完整；任何目标失败、缺失、被拦截、无可读页或超长，都记入 `failed_components`。
2. 把 `failed_components` 传入计算，或在 `work_draft_review.py` 汇总处统一处理：失败条款中，不满足／已触发保留；满足／未触发及其他结论一律改为 `SystemIssue(extraction_failed)`，写明影响条款。去掉约 649–653 行"确定结论豁免"。
3. `absence_policy` 只在该条款全部目标都成功返回且结果为"未找到"时使用。

**验证**：合成测试覆盖：读取失败的病史类排除条款不得为未触发；读取成功且未找到→按政策未触发；部分失败→系统问题；有正向发现时读取失败仍显示已触发。

### C1 核对标记取代置信（D33）

**现状**：
- `app/evidence/risk.py:27-36` 把 NUMERIC_VALUE、DECIMAL_POINT、UNIT、DATE、NEGATION_POLARITY 都定为 BLOCKING；扫描器从不产生 LOW_CONFIDENCE（只有矩阵中有这一项）。
- `fact_publication_service.py:523-524` 以"该事实所在页有任何未解决阻断风险"计算 `low_ocr`；`handwritten` 参数从未传入。
- `work_draft_calculation.py` 约 746–792 行的置信链在以下情况判低：有风险标记、依赖 LLM 关系（749–750）、日期不清的记录被排除（753–758）、部分页未读完（784–787）、条款出现在系统问题中（788–789）；父项任一子项低即低（约 928 行）。
- 契约 `WorkDraftItem`（`app/domain/contracts/work_draft.py`）的校验要求确定结论必须有置信、只允许对"high"做已核；`confirmation_allowed`（`work_draft_review.py:29-37`）只对"low"开放；已核哈希含评估版本。
- 前端 `EligibilityWorkbenchPage.tsx:399-402` 把低置信条款都列为卡片。

**改动（C1a：契约与事实级标记）**：
1. `WorkDraftItem` 新增 `review_marks: list[ReviewMark]`（`kind`、`label_zh`、`level`=`fact`｜`conclusion`、`fact_id | null`、`detail`）。工作稿条目存在 `payload_json` 中，**不需要迁移**。新工作稿 `confidence`、`confidence_reason` 写 null；放宽校验：确定结论不再要求置信。旧稿照常可读。
2. 已核：`acknowledgement_input_hash` 改为（条款编号、结论、所用事实修订号有序集合、规则内容哈希），去掉评估版本与 `reason_text`；已核对象为"带标记的确定结论"。
3. `app/domain/risk_flags.py` 按 PRD §8.1 产生事实级标记。`LOW_OCR_CONFIDENCE` 的来源改为：该页有 `OUTPUT_REPETITION`；或（经确认存在时）OCR 低置信片段与数值位置重叠。类别风险不产生标记。
4. 新增 `DECIMAL_SENSITIVE`：数值 ×10 或 ÷10 会翻转该条结论时挂标记（需要阈值，故在计算阶段判定，C1a 提供函数，C1b 调用）。
5. `fact_publication_service.py` 传入抽取输出的 `handwritten`，产生 `HANDWRITTEN`；不再按整页风险计算 `low_ocr`。
6. 枚举沿用现有 `RiskFlag` 名称，新增值追加（PRD §8 开头）。
7. C4 第 1 项（见下表）在本任务中完成。

**改动（C1b：结论级标记与去掉置信链，与 C4 同一任务）**：
1. 删除置信链，改为产生 PRD §8.2 的结论级标记：`PAGES_NOT_FULLY_READ`（原 784–787 的条件）、`UNDATED_RECORDS_EXCLUDED`（原 753–758）、`LLM_READING_ONLY`（满足／未触发只由语义读取支持）、`NO_HISTORY_SOURCE`。原"条款出现在系统问题中"的情形由系统问题本身表达。
2. 事实级标记汇总到条款：所用事实上的标记复制到 `review_marks`（`level=fact`，带 `fact_id`）。
3. 父项：任一被组合进结论的子项带标记，父项带结论级标记"子项需核对"。
4. 调用 `DECIMAL_SENSITIVE` 判定。

**验证**：单元测试覆盖"类别风险不产生标记""OUTPUT_REPETITION 产生标记""四种结论级标记各自产生""已核跨版本保留（事实修订不变时）"。

### C4 阻断改降级

| # | 位置 | 现在 | 改为 | 任务 |
|---|---|---|---|---|
| 1 | `fact_evidence_closure.py:717-723`、`757-763` | 用药记录有极性／重复风险即阻断；整页风险只对临床事实和来源绑定用药降为警告，事件与用药暴露仍被拦 | 事件与暴露与临床事实一致：采用，按 C1 规则挂标记 | C1a |
| 2 | `work_draft_calculation.py:540-545` | 判断／语义／人群／前瞻／暴露类谓词的通用事实一律丢弃，等 LLM 关系 | 通用事实可以确立"成立"（正向发现）；只有该谓词**没有限定条件**（严重程度、频次、因果、期间、人群）时，通用事实才可确立"不成立"；其余仍等语义读取 | C1b＋C4 |
| 3 | 同文件约 668–676 行 | 带时间窗的正向关系还要求同一摘录处另有一条按采样／就诊日期采用的事实 | 关系自身的日期必须逐字出现在其摘录中并由程序解析，满足即可；否则为未知并挂 `DATE_ROLE_UNCLEAR` | C1b＋C4 |
| 4 | 同文件 `calculate_procedures` 约 994–997 行（组件侧同类处理一并检查） | 有效期窗口一律记系统问题 | 计算有效期；超窗→不满足；日期不全→挂 `PARTIAL_DATE` | C1b＋C4 |
| 5 | 同文件约 547 行 | 参考范围未核实即记系统问题 | 按已读到的参考范围计算并挂 `ATTRIBUTION_UNCERTAIN`；读不到参考范围才证据不足 | C1b＋C4 |
| 6 | `work_draft_review.py` 约 581 行 | 复用证明丢失超过 16 条即记系统问题 | 随 C5 删除 | C5 |
| 7 | `work_draft_review.py:82,85,99` 等 | 历史自动任务缺回执即 `ScopeViolationError`，拦住后续所有工作稿 | 跳过该历史任务的复用，不中止 | C5 |

每处一条正例、一条反例测试。

### C5 缓存替代复用证明（D36）

**现状**：`_reusable_source_reads`（`work_draft_review.py:54-173`）、`revalidate_saved_source_read`（`work_draft_semantics.py:106-257`）、`app/services/fact_normalization_revalidation.py`（调用方：`fact_normalization_executor.py` 约 435／902／1472 行、`fact_normalization_job_service.py` 约 347 行、`evidence_api_read_service.py`）。`app/storage/fact_authority.py` 的 `retained_*` 被约 15 个文件使用。

**改动**：
1. 新表 `llm_call_cache`（`app/storage/models.py`，迁移 `0031_llm_call_cache.py`）：`cache_key`（sha256：角色、模型标识、提示版本、规范化输入）、`artifact_path`、`created_at`、`usage`。新模块 `app/services/llm_call_cache.py` 提供 `get_or_call`。
   - 抽取的输入＝页图哈希＋该页有效文字哈希＋该页需求清单哈希（C6b 接入）。
   - 语义读取的输入＝目标定义哈希＋实际送入的各页文字哈希（一次读取包含多页时，任一页文字变化都会让该读取的键失效）。
2. 工作稿路径（`work_draft_review.py`、`work_draft_semantics.py`）改用缓存，删除复用证明调用；整理路径中 `fact_normalization_revalidation` 的调用改为缓存（在 C6b 的文件里，C5 先改调用点，C6b 之后再改提示）。
3. `retained_*` 等被广泛使用的函数**不删除**，只是不再由工作稿路径调用；`fact_normalization_revalidation.py` 在没有调用方后删除。
4. C4 第 6、7 项。
5. 已核：`confirmation_allowed`（`work_draft_review.py:29-37`）与 `_apply_confirmations` 改为基于 `review_marks`，配合 C1a 的新哈希。
6. **新验证副本**：新增 `scripts/new_validation_copy.py`：用 SQLite backup 把当前验证副本（含工件目录）完整复制到仓库外的新目录（D40），之后在新副本中以新的处理修订重算；旧结果作为历史保留，不再被复用。不做选择性删除（数据库按哈希链只追加，删一部分会让保留记录指向已删内容）。

**验证**：缓存命中／失效单元测试；在新副本上完整重算一次，记录耗时与命中率。

### C6a 工作稿 Job 与页面性能

1. 每个工作稿 Job 只组装一次上下文：现有 Job 内的 `assemble_review_context`（约 353 行）与 `prepare_review` 中的第二次组装（`review_preparation_command.py:54`）合并；去掉对该节点全部历史 Job 的扫描；`_fact_refs` 只算一次。
2. 投影（`work_draft_projection.py:57`）在每次打开页面时都重新组装上下文以判断是否陈旧；改为比较已保存的输入哈希（资料快照、事实修订集合、规则哈希），不重组。这是 G1-5（页面 ≤3 秒）的前提。
3. 语义读取只送与目标相关的页（病历类全部页＋关键词命中页），不再每批附全节点全文（`work_draft_semantics.py:697-701`）。

### C6b 抽取提示精简与并行

1. 现有单页提示约 86,116 字符（255 条需求行、151 个变量），受 `_MAX_PROMPT_CHARS = 100_000`（`evidence_normalizer.py:467`）所限只能一页一调。按现有资料类型 `DocumentCategory`（`app/domain/contracts/evidence_ingestion.py:53`：`objective_report`、`historical_record`、`study_chart`、`screening_transcription`、`other`、`unknown`）只带相关变量与要求行：

   | 资料类型 | 带入的变量领域 |
   |---|---|
   | objective_report | lab、vital、score、procedure |
   | historical_record、study_chart | history、medication、score、demographic、procedure |
   | screening_transcription、other、unknown | 全部（不分片） |

   目标单次提示 ≤20,000 字符，允许 2–5 页一批。
2. **页覆盖**：`review_context_assembly.py` 约 358–360 行按"实际请求过的变量"计算页覆盖。分片后，覆盖只按"该页资料类型适用的变量"计算；R-C6 的原因列出实际读过、且适用于该条款变量领域的页。（本项在 C6a 合并后做，同一文件。）
3. 抽取输出增加：每条事实的 `handwritten`；用药事实的记录类型 `record_kind`（`prescription`｜`order`｜`purchase`｜`administration`｜`history_narrative`）。
4. 页批次并行，并发数用配置项（默认 4），失败批次单独重试一次。
5. 接入 C5 的缓存。
6. 推理强度对照由统筹者执行（PLAN 第 3 波），不在本任务中调用模型。

### C3 禁用药归入排除条款（D34）

**现状**：34 条用药项单列，全部无法判定；`work_draft_medications.py:64-70` 要求整例无系统问题、无冲突组、全部页覆盖、全部用药已归类才可能判未触发；类别来自 `scope_supplement.drug_classes`（约 67 行），而 `drug_classes.yaml` 只有 3 类、缺常见别名（如"强的松"、商品名）；`PRESCRIPTION_ONLY` 从未赋值；没有"未能归类的用药"卡片。用药在 `compose_parent` 之后才计算（`work_draft_review.py:672-678`），不进入父项汇总；API 校验（`app/api/v2/eligibility_review.py:100-103`）拒绝带父条款的用药行。

**改动**：
1. 关联字段用已有的 `MedicationRestriction.applies_to_rule`（`app/domain/contracts/rules.py:194`，可空）。未关联的条目归入"未关联排除条款的用药限制"组。
2. 判定按 PRD R-C3 的七种情形。"未触发"前提只看与用药有关的问题。
3. 类别成员清单：只有经用户确认的类别才能使用情形①（未提及→未触发）；未确认的类别，对应排除父项出一张"用药类别成员待确认"卡片。统筹者把 31001、26002 中出现的药名与各类别现有成员整理成清单，**交用户确认**后写入项目补充表（随规则包保存）。构建方不得自行把药名归入类别。
4. 用药子项在 `compose_parent` 之前计算，作为对应排除父项的子项参与汇总（改 `work_draft_review.py:672-678`）。
5. `PRESCRIPTION_ONLY` 由 C6b 输出的 `record_kind` 判定。

**验证**：合成病例覆盖七种情形、"类别未确认→待确认卡片"，以及"其他系统问题存在时仍可判未触发"。

### C7a 投影与 API

- `work_draft_projection.py`、`app/services/eligibility_review_projection.py`、`app/api/v2/eligibility_review.py`：DTO 增加 `review_marks`；去掉置信字段的输出；允许用药行带父条款（改 `eligibility_review.py:100-103` 的校验）；系统问题条款单独标识。

### C7b 前端收敛

- 卡片规则按 PRD §7.3；去掉置信文案与徽标；标记显示在对应事实旁，结论级标记显示在结论旁。
- 用药子项显示在对应排除条款下；"未能归类的用药""需确认停药时间""用药类别成员待确认"卡片。
- 审定页：未关联排除条款的用药限制给出提示，并在现有编辑入口中可选关联条款。
- 系统问题组放在卡片末尾。不新增页面和交互（D35）。

### C8 评测脚本（R-F1、R-F2）

- `scripts/import_manual_ie.py`：读 CSV／Excel（`subject_id, stage, official_code, manual_conclusion, note`；`manual_conclusion` 取 满足／不满足／未触发／已触发／不确定），保存为数据目录下的 `evaluation/manual_ie/*.json`（文件，不建数据库表），不进入任何提示词。
- `scripts/compare_with_manual_ie.py`：按受试者×节点×条款对齐最新工作稿（通过 API 或导出文件读取），以 `review_marks` 是否为空判断"无标记"，输出 PRD §9 的指标与差异清单（CSV＋Markdown，每行带系统依据与页码）。
- 判定逻辑改动后，在已有人工结论的受试者上跑一次，结果写进状态表。

---

## 5. 冻结的部分

审定页（除 C7b 的用药关联提示）、范围解析、变量绑定、时间图、打印排版、更正／补证界面、版本对比：0.2.1 只修影响 G1／G2 的缺陷，不加功能。0.1.x 的跨章控制链、prepared-review 子任务链、逐页双 VLM、方法采用 gate 仍不调用、不修补、不删除。
