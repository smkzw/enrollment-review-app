Trellis SessionStart ✓

Starting the bounded read pass with the two files in the initial read set.

Context and plan loaded. Now gaining structural orientation on the source set before targeted reads.

Bash denied (non-interactive, no approval prompt) — noted as a tool-availability fact; I'll proceed with Read/Grep only. Next targeted reads.

Now reading the draft types/schema and locating the runner's recovery helpers.

Reading the runner core and getting the transport file outline.

Reading the parse/hydration path and locating source-verbatim checks on `assertion_text`.

Key finding: the preflight that refuses is `EvidenceDraftScopeError` (bounded_repair=False) at `evidence_normalizer.py:1670`. Now checking the transport proposal hook, semantic validator, and repair contracts.

Checking the source-binding validator, executor wiring, and the repair contract.

Reading the executor's runner wiring, receipt persistence, and rehydration consumer.

Verifying the persisted call contract and the existing recovery/persistence tests.

# Conference Output: enrollment-rv1001-structural-key-recovery-20261006 - evidence_single_object

## Output

**边界与工具记录**：已完成 2 次 orientation 读取（context、plan）＋ 20 次 material 读取/检索，达到上限即停。Bash 在非交互模式被拒绝（无权限提示），所有结论来自 Read/Grep；未访问数据库、临床原件、.env、网络、产品模型端点，未写任何文件（含 runner 报告路径）。未读取 P1 脏区或任务外文件。

---

### 1. 结论摘要

- **推荐：有据支持的最小恢复设计 A**（新增一类“唯一未声明键 → 唯一缺失必需键”的短提案；宿主冻结、确定性合成、全链复验、新证明落盘）。但必须先接受一个由证据迫出的现实：**A 不能回溯修复当前已冻结的失败调用**——job 身份在创建时冻结修复策略（测试证据：`tests/v2/services/test_evidence_question_repair_persistence.py:69-72`，开启策略产生新 job_id；`143-157` 证明事后注入策略被“未进入冻结身份”硬拒）。当前阻塞 run 若要在本 run 内解锁，只能重执行该页组或接受 B；A 是该重跑的护栏与后续同类失败的兜底。
- **最高影响缺陷（与既定叙述的偏差）**：这不是“schema 修复路径存在但拒绝”的问题，而是**两处故意闸门叠加**：
  1. `app/agents/evidence_normalizer.py:1668-1670` 在 pydantic 之前 raise `EvidenceDraftScopeError`（`app/agents/evidence_normalizer_repair.py:48-52`，`bounded_repair=False`）；
  2. runner `evidence_normalizer.py:2539-2546` 判 `scope_unavailable=True` → `terminal_schema_failure()`（从未进入 `_schema_repair_prompt` 整答修复路径）；
  3. 兜底 partition 被 `app/agents/evidence_candidate_partition.py:74-79` 的结构完整性闸门拒绝（`assertion_text` 缺失即 structural error）。
  本包 Source of Truth 明确“partition 严格边界不得放宽”，因此“隔离坏候选”这一看似最小的替代**在授权上已被排除**；真正的选择只有 A 或 B。
- **A 的合法性核心（独立验证）**：我 grep 了 `evidence_normalizer.py` 与 `app/projections/page_review_sources.py`，`assertion_text` **没有任何对 locator 原文的逐字校验**；当前对它的约束是：非空字符串（1668）、`asserted_object ⊆ assertion_text`（1478）、context 摘录 ⊆ `assertion_text`（1678，经 `validate_context_excerpt`）、locator 属于冻结集合（1762）。因此“把冻结原答中某个未声明键下的**字节相同值**改名到 `assertion_text`”不构成“从修复回答补造依据”——补造禁令针对的是**修复回答新造内容**，而重命名不新增任何模型内容，只是对同一模型同一原答中既有值的结构重标。

---

### 2. 第一因果失败（全部有行号证据）

1. executor 以 `require_current_draft=True` 调 runner（`app/services/fact_normalization_executor.py:1318`），`allow_candidate_partition`、`allow_question_classification_repair` 由冻结 payload 策略决定（`1319-1320`）。
2. parse 在 pydantic 之前先跑 preflight（`evidence_normalizer.py:1652-1701`）；对每个候选：`basis` 为 dict 时，`assertion_text` 缺失或非非空字符串 → `EvidenceDraftScopeError("断言原文缺失或不是文字，不能从修复回答补造依据")`（`1668-1670`）。
3. `EvidenceDraftScopeError` 继承 `EvidenceSourceObjectError` 但 `bounded_repair=False`、refs 为空（`evidence_normalizer_repair.py:48-52`）。
4. runner：`scope_unavailable = not exc.bounded_repair or …` → True → 直接 `terminal_schema_failure()`（`2539-2546`），**未消耗任何修复预算、未发起任何补答**。
5. terminal 尝试 `recover_source_local_candidates(initial_raw_text, …)`（`2398`）；partition 首步用 `Draft202012Validator(EvidenceNormalizerDraftOutput.model_json_schema())` 检查整份原答（`evidence_candidate_partition.py:74-79`）；缺必需属性即 structural error → `ValueError("原答结构不完整，不能通过局部隔离绕过输出合同")`。
6. runner 记录 `candidate_partition_failure` 并返回 `需要核对`（`2400-2404`）；executor 以非重试 `PARTIAL_OUTPUT` 抛 `StepFailure`（`1341-1352`）。该页组被整体阻断，已保存组不受影响。

**诊断结论**：老板描述的“preflight 正确拒绝修复前补造”得到精确定位；`assertion文本` 只是触发样例，**不得**作为别名写入代码、提示词或 schema。

---

### 3. 评估 A：最小可行通用有界恢复

**宿主前置条件（形状规则，全部确定性、与具体键名无关）**
- 仅当某候选 `assertion_basis` 为 dict、且 `assertion_text` 校验失败时进入判定；
- 用 `EvidenceAssertionDraft.model_fields` 求 `unknown = keys − declared`、`missing_required = 必需字段 − keys`；
- **全答内所有触发候选都必须满足 `|unknown|==1 且 |missing_required|==1`，且该 unknown 值为非空 str**；否则原样 raise 当前的非可修复 `EvidenceDraftScopeError`（整组维持今日结果，fail-closed，全有或全无）；
- 目标属性名由宿主从 schema introspection 得出；模型只能“确认/放弃”，不能返回新名字、不能返回内容。

**提案契约（镜像 `QuestionClassificationRepair`，`app/agents/evidence_question_repair.py:42-139`）**
- `policy` 常量、`precondition_sha256`（原答全文）、`input_scope_sha256`；
- `targets`: 每项 `{path, candidate_ref, object_sha256, unknown_key, missing_required_property, frozen_object}`（冻结对象含该候选完整既有字段，供模型判断键义；不包含整份 88 候选草稿）；
- 输出 schema：`additionalProperties:false`，`changes` 数必须恰等于 targets 数，每项只允许 `target_property == 宿主给定缺失名` 或 `null`；`null` → 保留待核（镜像 `130-131`）；
- 提示词显式声明：不重读整页、不新增/改写/删除任何值、不改变父子关系与来源、值非原句摘录/为译文批注/不确定时返回 null、只返回小提案对象。

**合成与复验（宿主，零模型自由度）**
- 用 `_unique_object`（拒绝重复键，`evidence_normalizer_repair.py:55-70`）解析原答与提案；
- 校验 object_sha256、target 覆盖无重复遗漏后，仅执行 `composed[path][target] = frozen[path][unknown]; del composed[path][unknown]`，其余深拷贝保持；
- 复验 = 与 `replay_question_repair` 完全同链：`parse_evidence_normalizer_output(require_current_draft=True)` → `_validate_normalizer_semantics`（`1821-1833`）；若复验出现既有可隔离错误（`EvidenceSourceObjectError`/`EvidenceDerivedSourceError`/`EvidenceNumericUnitError`）且 `allow_candidate_partition`，先对**合成后文本**跑既有 partition，再带 `partition_receipt` 重放（镜像 `2496-2536`，含 `partition.raw_output_sha256 == composed_sha256` 的链式校验，测试 `161-181`）。
- 证明：`{policy, input_scope_sha256, original_response, raw_output_sha256, proposal_response, proposal_sha256, targets(path/key/value sha), composed_sha256}`；`compose_*` 重放必须逐字段等于 receipt（镜像 `142-149`）。

**runner 接入与首要实现风险**
- 新异常必须在 `2539` 的通用 `EvidenceSourceObjectError` 分支**之前**分流；否则会被当作 object-repair 走 `continue_session` 整答修复——正是本包要避免的“恢复整答”。
- 门禁：新增 `allow_structural_key_rename`（默认 False）；为假时该异常必须直接 `terminal_schema_failure()`，保持今日行为；为真时仅当 `schema_repairs == 0 且 raw_text == initial_raw_text` 才发起（镜像 `2499-2500`），成功即直接返回（不回到解析循环）。

**保存/恢复/消费者最小改动面**
1. 新增短提案模块（~100 行，镜像问题修复）。
2. `evidence_normalizer.py`：preflight 收集判定 + runner 标志/分支。
3. transport：把 `propose_question_classifications` 泛化为 `propose_bounded_repair(prompt, output_schema, tool_name)`（`deepseek_evidence_normalizer_transport.py:504-509, 571-579`；`response_format` 严格 schema 保持不变），或零改动复用它但 provider 侧 tool 名会误导审计——建议泛化。
4. `app/domain/contracts/facts.py`：新增可选 `structural_key_rename_sha256`，沿用 `837-846` 的 None-pop 序列化模式（旧行编码不变，无需迁移——**推断，须 Codex 验证存储层**），并在 `848-861` 加 `reading_method == "model_response"` 校验。
5. executor：策略旗标、receipt 持久化（镜像 `1355-1366`）、`817-820` 的 replay 分发加一个分支、新增消费者（镜像 `823-858`，含 call/run/raw_output 身份校验与 `861-866` 的逐候选精确比对）。**建议镜像而非重构**既有 problem 路径，保护已证测试；重复约 25 行。
6. Job 服务：`allow_structural_key_rename` + `structural_key_rename_policy` + 预热 scope sha，冻结进 job 身份（镜像测试 `69-72, 143-157`；**本 pass 未读 job 服务，须 Codex 核**）。
7. 测试：镜像 `test_evidence_question_repair_persistence.py`（首消费、restart 零重读、篡改拒绝、legacy 注入拒绝、与 partition 双证明链）。

**预算核算**
- 提案共享 `max_schema_repairs`（executor 配置；测试用 1；runner 默认 2，`evidence_normalizer.py:2293`）；先在调用前 `+1`（镜像 `2508`），失败也计入。
- 提案传输失败：记 `transport_failed` attempt、立即 terminal，不耗 `max_transport_retries`（镜像 `2523-2530`）。
- 恢复/重放零模型调用（测试 `104` 断言 restart 后 `(calls, proposals)==(1,1)`）。
- 同一调用内只允许一次短提案（first-only），故**新证明与疑问证明不会共存**；partition 可与任一共存（链式证明）。重命名→（可选）partition→采用门禁，顺序确定。

**与分类/隔离证明的组合**：重命名发生在 partition 之前（合成后文本才是 partition 输入），否则 74-79 结构闸门必然拒绝；这正是与 `candidate_partition_sha256` 的兼容点，也是“旧 proof 拒复用”边界的延续——旧调用缺新字段/新策略，分发不变、不可事后注入。

---

### 4. 评估 B：有据拒绝（诚实备选）

- B 的即时动作：接受该页组本 run 失败为终态；复用六个已保存组；对新 job 重执行该页组（或经许可的替代输入结构）。
- 代价：该页组当前无该 run 的证据覆盖，须重执行并以新 run/call 审计；收益：零新增证明面、零契约变更、零回归风险。
- **关键权衡**：由于策略冻结进 job 身份，**A 与 B 对“当前失败调用”的操作路径相同（都要重执行）**；A 的增量价值 = 重执行及未来调用中同类形状不再整组阻断。若该键性畸形是一次性采样伪影（须核 Q2），B 更成比例；若是系统性混合语言键倾向，A 才有稳定回报。

---

### 5. 反例清单（正常/危险）

正常：① 单候选单 unknown→单 missing、值为断言原句 → 恢复；② 多候选同形状 → 提案须全覆盖、全合成，all-or-nothing；③ 值为空白/非 str → 不可恢复，维持拒绝。
危险：① 两个 unknown 键 → 映射歧义，拒绝；② 单 unknown 但两个必需缺失 → 目标歧义，拒绝；③ 值为批注/译文/转述 → 宿主无法逐字核验（无 assertion_text↔原文校验），缓解=提示词要求 null + 合成后一致性（`asserted_object⊆assertion_text`、限定摘录⊆、locator 属集合）+ 证明保留原答与提案；残余风险与“键名本来就正确”的草稿相同，不因重命名放大；④ 提案增删/重排/改兄弟/加别名 → schema `additionalProperties:false` + 宿主只做单值移动，整体拒绝；⑤ 原答重复 JSON 键 → `_unique_object` 拒绝，不得静默取尾值；⑥ 提案 null → 保留待核；⑦ 重放期原答/提案/目标/合成 sha 不符 → 拒绝（镜像 `142-149`、消费端身份校验）；⑧ 跨调用 receipt 复用 → call/run 身份校验拒绝；⑨ 保存候选被篡改 → `861-866` 精确比对拒绝；⑩ legacy job 事后注入策略 → 必须拒绝（镜像 `143-157`）。

---

### 6. 歧义与技术/临床边界

- 技术侧：键身份、路径、形状唯一性、值字节冻结、类型/枚举由合成后的现行校验器决定；模型唯一自由度是“该冻结值是否就是缺失属性的忠实内容”的确认/放弃。
- 临床侧：不改动任何临床值、分类、枚举、值域、极性、scope、来源或采用标准；`_validate_normalizer_semantics` 与自动采用门禁原样运行。重命名只能让**同一冻结候选**变得可解析，不产生新事实、不改变是否被采用。
- 泛化边界（必须写清）：该机制只覆盖“未声明键↔唯一缺失必需属性”。声明键混淆（如值放在错误但已声明的字段）、类型错误、多键缺失/多键未知 **不在** 覆盖内，维持拒绝。`assertion_text` 之外字段（如可选 `contextual_qualifiers` 缺失）走既有 context 修复族，本 pass 建议不并入 v1。

---

### 7. 异议、决策点与给 Codex 的有界问题

**异议 1（最重要）**：本包把任务设定为“审阅通用有界恢复”，但证据显示真正的堵点包含 job 身份冻结策略——**A 不是当前 run 的解锁器**。请先确认目标是“解锁当前 run”还是“防未来同类失败”；若为前者，方案空间里 A 与 B 无差别地要求重执行，应把决策重心移到重执行审计与提示/输出合同加固。
**异议 2**：把本异常改为 `bounded_repair=True` 的任何实现，若不显式在 runner `2539` 前分流，会被现有 object-repair 路径吞掉并触发整答补答——这是最可能被实现者踩中的回归点，应写进 implement 清单与测试。
**异议 3**：不要复用 `question_classification_sha256` 列做策略分发（省一个字段但混淆审计语义）；也不要放宽 partition 结构闸门（本包已排除）。
**有界问题 Q1**：当前失败 job 的 `max_schema_repairs` 实际值与是否已启用 partition？（决定重跑配置）
**Q2**：owner 观察到的该值是否为原句摘录而非译文/批注？该畸形是否在其它已存原答/失败工件中重复出现（系统性 vs 一次性）？这直接决定 A 的性价比。
**Q3**：transport 方法泛化（触及 fake transport/测试）可接受，还是零改动复用问句命名方法？
**Q4**：生产是否希望新 job 默认开启重命名修复与 partition，还是仅显式 opt-in？

---

### 8. 不确定与缺失证据（明确区分）

- 未读（超预算，标记推断）：job 服务的策略冻结机制；`FactNormalizationCall` 新字段是否真无迁移（由 `facts.py:837-846` 的 None-pop 先例推断）；executor `:1114` runner 构造与预算参数；是否有其它消费者枚举 call 字段；失败原答是否已作为 transport receipt 持久化（若可在不新调模型的情况下取回原答，A 的操作含义会改变）。
- 未能核验 owner 的“88 候选 / 六组已存 / 一组阻断”清单（无 DB 访问，符合边界）。
- 未读 `ContractModel` 的 extra 配置：对第一因果失败无影响（preflight 先于 pydantic），若未来把机制扩展到 pydantic 阶段需补。
- Bash 被拒导致无法核 HEAD 5dd6fc49 与工作区一致性，依赖 context 的声明。
- 采用与否属 Codex 权限；以上不构成最终接受。

---

### 9. 最小实现清单（供 Codex 决策后落地）

`app/agents/evidence_*_repair.py`（新增提案/合成/重放）→ `app/agents/evidence_normalizer.py`（preflight 判定 + runner 分流/门禁）→ `app/agents/deepseek_evidence_normalizer_transport.py`（提案方法泛化）→ `app/domain/contracts/facts.py`（新可选证明字段）→ `app/services/fact_normalization_executor.py`（持久化 + replay 分发/消费者）→ job 服务（策略冻结）→ 镜像持久化测试。若 Q1/Q2 判定为一次性伪影，则采用 B：维持拒绝、复用已存组、重执行该页组并单独记录审计。
