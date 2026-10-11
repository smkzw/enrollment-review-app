I'll run an independent read-only evidence pass on the control-save and history-to-report wiring, starting from the assigned source list and recording line-level findings.Context files are mostly placeholders, so I’ll inspect the design spec and the actual save/history/report source next.I’ve got the core contracts. Next I’ll trace save/publish, history load, and UI mapping for source-binding and “not complete” gaps.# Conference Output: r05-control-history-source-20260914 - evidence_single_object
## Output

只读源码审阅。未运行测试、未 import 应用、未调用产品模型、未写库、未改文件。本角色无最终临床/监管/视觉/现网接受权。

最高影响缺陷：**读侧已把「有目录的已完成运行必须有控制快照」做成硬失败，但仓库里没有整批发布器去写入该快照；同时列表仍按 `completed_at` 显示「已完成」。** 在 `clause-pack/v2` 已进入新冻结上下文的前提下，这会让官方 IN/EX 报告也无法打开，而不是只把跨章结果标成未完成。

---

### Evidence

**读路径不重算（成立）**

- `app/services/review_history_service.py:481-544`：`get_run` 只读 `ReviewControlRepository.get_or_none`，把 `control_snapshot.outcomes` 原样放入 `ReviewHistoryRunDetail`。未调用 `calculate_frozen_review` / `project_control_review_outcomes`。
- 同文件 `1-26`、`515-526`：控制目录取自**本次冻结** `context.clause_pack.control_publication`，不读项目当前指针。
- `app/api/v2/review_history.py:441-466`：HTTP 只做 DTO 投影，注释写明不重算、不发布。
- `frontend/src/api/review-history/reviewHistoryHttp.ts:17-18,715-831`：解码拒绝未知字段/未知枚举；`completed` 且 `missing_protocol_control_ids.length > 0` 则拒绝展示。

**来源绑定（部分成立，有洞）**

- `app/storage/review_control_repository.py:47-109`：读/写都 `_verify`：run/context 互指、`context_sha256`、`created_at == run.completed_at`、目录控制 ID 全集、`control_sha256`、义务原文/身份/span/摘录、`used_fact_ids ⊆ context.facts`、locator 属于所引事实、门禁名 `review-control-publication` 且 `output_hash == canonical_hash(snapshot)`。
- `app/domain/contracts/control_review_outcome.py:54,75-83`：`accepted` 固定 `False`；快照校验禁止重复 `protocol_control_id`，并禁止 outcomes **彼此**混用不同 `(frozen_input_sha256, selections_sha256)`。
- **未交叉绑定**：`ReviewControlSnapshot.selections_sha256`（69）与各 `ControlReviewOutcome.selections_sha256`（53）没有相等检查；`frozen_input_sha256` 也不对 `context_sha256` 或可重放的 `ControlBindingFrozenInput` 做核验。`_verify`（47-109）同样不读这两项哈希。
- `app/services/review_context_assembly.py:39`：新冻结上下文经 `project_published_clause_pack` 装配；有已发布目录时 `control_publication` 会进入冻结包。

**缺项不冒充完成（详情硬失败；列表仍标完成）**

- `review_history_service.py:519-526`：有期望控制且无快照 → `missing_protocol_control_ids = expected_controls`；`completed_at is not None` 则 `ReviewHistoryIncompleteError`（500，「暂不能展示为完整报告」）。
- 同文件 `184-185,445-478`：列表状态只由 `started_at`/`completed_at` 推导，**不**预检控制快照。
- `frontend/src/pages/ReportsPage.tsx:224`：下拉显示 `completed` →「已完成」。
- 不完整信封只带 `missing_rule_component_ids`（`review_history_service.py:111-128`）。缺控制快照的抛出（522-526）不带 `missing_protocol_control_ids`。
- 快照存在但 `_verify` 失败 → `ScopeViolationError` → `AppScopeMismatchError` 409（`evidence_app_errors.py:132-136,788-789`），文案是写侧「作用域不一致 / 本次操作没有生效」，不是「记录不完整、拒绝展示」。

**界面未写成 IN/EX，但独立身份与强度被丢掉**

- `app/domain/contracts/protocol_controls.py:17-18,263-274,1616-1620`：跨章身份必须是「方案控制 NN」，禁止伪造成 `IN/EX/REQ/CTRL`。
- `app/domain/contracts/clause_pack.py:69-70`：官方 `clause_id` 与 `protocol_control_id` 不得碰撞。
- `app/api/v2/review_history.py:216-224,460-465`：`ReviewHistoryControlDTO` 只剩 `protocol_control_id, obligation_id, statement, status, protocol_excerpts, locator_ids`。丢掉 `title`/`display_ordinal`/`kind`/`modality`/`reason_codes`/`activation`/`accepted=false`。`protocol_control_id` 无 `min_length`。
- `FrozenReviewReport.tsx:48,99-111`：独立表「方案其他章节的审核要求」；行标题是 `statement`；状态映射为「已满足/未满足/尚无法判定/本次不适用」。不展示「方案控制 NN」或 `title`。页眉完成态仍是「入排审核报告」（54）。
- `frontend/src/domain/labels.ts:74-75`：官方 `requirement_met/requirement_not_met` 同为「已满足/未满足」。
- 控制证据标题为「补充审核要求 · 原始资料」（148-149），未套官方 `ruleDisplayCode`。

**开放范围：整批发布器、控制行动（源码中不存在，不得记成已完成）**

- `ReviewControlRepository.save` 的唯一生产定义在 `review_control_repository.py:36-45`。全库无其他 `ReviewControlRepository(` / `ReviewControlSnapshot(` 调用方。
- `frozen_review_calculation.py:37-47,266-267`：可算出 `control_outcomes` 且 `accepted=False`，但不持久化、不入历史 API。
- `review_action_publication.py:20-68`：行动只从 `FinalAssessment` 派生，键是 `rule_component_id`。`app/domain/contracts/review.py` 无 `protocol_control_id`。
- `FrozenReviewReport.tsx:113-116`：无行动时写「本次审核未记录补充事项。」关闭行动不等于改结论（115），但控制 `unfulfilled`/`unverified` 不会出现在该表。
- 迁移 `0026_review_control_snapshots.py:11-23` 只建表，无回填。

**额外只读文件（为判断发布器/身份/错误信封，不在初始清单内）**

`frozen_review_calculation.py`，`review_action_publication.py`，`clause_pack.py`，`protocol_controls.py`，`control_atom_binding.py`，`control_atom_binding_input.py`，`control_binding_input.py`，`published_clause_pack.py`，`review_context_assembly.py`，`review_context_v2.py`，`evidence_app_errors.py`，`ReportsPage.tsx`，`labels.ts`。

---

### Inference

1. 历史读取合同的意图是对的：冻结快照、门禁回执、目录全集、原文/事实归属；完成态缺快照则整份报告拒绝展示。这符合 17.3「不能报告全方案审核完成」，也符合「历史不重算」。
2. 该硬失败在发布器落地前是断路器，不是功能完成。新上下文已经会带上已发布目录（`review_context_assembly.py:39`）。一旦存在「已发布目录 + `completed_at` 已写 + 无 `review_control_snapshots` 行」的运行，官方 IN/EX 详情也会 500。列表仍显示「已完成」，属于**用运行时间戳冒充可展示的完整报告**。
3. 即便快照以后能写入，当前 API/UI 仍无法满足 17.3 的身份与强度：读者只看到义务 `statement` 和与 REQ 相同的「已满足/未满足」，看不到「方案控制 NN」/`title`/`mandatory|recommended`。这不是伪造 `IN-01`，但是把跨章义务读成入组/必做条款结论的高风险展示。
4. `selections_sha256` 双层字段未钉死，意味着未来发布器只要 outcomes 内部自洽，就可以让快照头上的核对批次哈希与真正计算批次不一致；读侧不会发现。这是来源绑定漏洞，不是开放范围本身。
5. `_verify` 失败走 409「作用域不一致」，会把「冻结记录损坏」伪装成操作范围错误，和官方结论缺失的 500 `REVIEW_HISTORY_INCOMPLETE` 不一致。

---

### Recommendation（最小修订，按优先级）

1. **在写发布器之前，先钉死读侧失败模式（Codex 需二选一）**
   - 推荐：详情保持 fail-closed；**列表不得把不可展示运行标成「已完成」**（缺控制快照时列表给明确「记录不完整/不可展示」，或根本不进可选完成项）。
   - 不要在无快照时静默返回空 `controls` 还让 `status=completed` 出完整报告。

2. **补 `selections_sha256` 交叉不变量**（合同 + `_verify`，各约数行）  
   `ReviewControlSnapshot.validate_snapshot`：非空 outcomes 时，`self.selections_sha256` 必须等于唯一的 `outcome.selections_sha256`；读侧 `_verify` 重复该检查。不要在读侧重算 status。

3. **DTO/解码/界面补冻结身份与强度，不补官方编号**  
   从冻结目录投影 `display_ordinal`（或现成 `display_label`）和 `title`，以及义务 `kind`/`modality`/`observation_reason_codes`。界面渲染「方案控制 NN」+ 标题 + 义务原文；禁止任何 `IN|EX|REQ|CTRL` 生成。状态文案与 `requirement_met` 分离（例如「该项保存结果为成立/不成立」，推荐项标明「方案建议」）。后端 DTO 补 `min_length=1` 与完成态/缺失/重复校验，与前端 `reviewHistoryHttp.ts:808-814` 对齐。

4. **读侧仓储失败改走 `ReviewHistoryIncompleteError`**  
   `get_or_none` 的 `ScopeViolationError` 包成 500 不完整信封，并在 `context()` 中列出 `missing_protocol_control_ids`。不要用写侧 409。

5. **明确开放项，不要在本接线里假装已完成**
   - 整批发布器：同一事务写入 `GateResult(review-control-publication)` + `ReviewControlSnapshot`；outcomes 来自已冻结计算而非读历史时现算；`created_at == run.completed_at`。
   - 控制行动：现有 `ActionRequest` 不能表达 `protocol_control_id`。在发布器存在之前，界面不要用「未记录补充事项」覆盖控制区的未满足/未核实。

---

### Uncertainty

- 未查库，不知道现网/本地是否已有 `clause-pack/v2` 且 `completed_at` 非空的运行。有则当前读接线会立刻阻断官方报告；无则风险限于新装配上下文。
- `control_sha256` / `project_control_atom_identities` 在读时按**当前**投影器重放。投影器若加默认字段，历史快照会从可展示变成 `_verify` 失败。本任务未评投影器稳定性。
- 禁止类义务的 `fulfilled` 是否等于「禁令被遵守」，取决于计算投影（`control_review_outcome.py:54-55` 声明不按 kind 取反）。本任务只评历史接线；DTO 丢掉 `kind` 后界面无法消歧。
- 空目录的 v2 包（`controls=[]`）会让 `expected_controls` 为假值而跳过快照（`review_history_service.py:519`）。是否应在范围说明中暴露「目录为空 ≠ 全方案已覆盖」，属 17.3 上游发布问题，不是本读路径能单独证明的。

---

### Objections / 对当前接线的反对

- 反对把「详情 fail-closed」当成发布器已存在的证据。`save()` 无调用方，计算路径 `accepted=False` 且不落库。
- 反对仅凭「没有写成 IN-01」宣布界面合规。17.3 要求独立身份和章节名称可见；当前只有 `statement`。
- 反对用「补充事项为空」暗示跨章问题已闭环。那是控制行动未建，不是已办理完毕。
- 反对读路径用 `SCOPE_MISMATCH` 409 表达冻结记录损坏。

---

### Decision points（请 Codex 裁断）

1. 有目录的已完成运行缺控制快照：整份详情 500（现状）还是官方条款可展示、跨章区显式不完整？我建议维持整份拒绝，但必须改列表文案，并在发布器落地前把该行为当作已知阻断而非验收通过。
2. 身份/强度字段是否在发布器之前就加进历史 DTO？我建议加：这是读合同，不依赖写路径，能避免发布器一接上就用错展示。
3. `selections_sha256` 头字段与 outcome 字段不一致时：合同拒绝（推荐）还是等发布器再保证？

---

### Bounded questions for Codex

1. 当前授权工作区或任何已冻结 `review/v2` 上下文里，是否已有 `control_publication.catalog.controls` 非空且 `completed_at` 已写的运行？若有，本读接线在发布器之前不可作为可发布行为。
2. 控制义务状态是否允许继续与官方 `requirement_met` 共用「已满足/未满足」？若不允许，需要产品文案，不只是加字段。
3. 未来发布器是否规定 `calculate_frozen_review.control_outcomes` 为唯一写入来源，且快照 `selections_sha256` 必须等于该次计算的 `selections_sha256`？若是，应把该等式写入合同，而不是只写在发布器里。

---

**Open scope（不得标完成）**：整批 `review-control-publication` 发布器；控制义务的 `ActionRequest`/办理闭环。  
**本轮未做**：测试、浏览器、现网、临床采信判断。
