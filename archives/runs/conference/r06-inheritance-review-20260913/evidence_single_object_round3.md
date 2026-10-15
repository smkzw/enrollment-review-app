I’ll re-read the current successor, repository, publication, contract, design, and test files rather than reuse the last summary.The successor helper is now single-hop. Next I’ll read expectation `project`, publication/replay, design §17.5, and the new tests.# Conference Output: r06-inheritance-review-20260913 - evidence_single_object

## Output

只读续审（同一 session）。未改文件、未跑套件、未读库/原件。231 项聚焦测试与独立全量回归 **不是** 临床/产品接受。Codex 终裁。本窄路径 **可支持为同权威下的确定性追加**，不等于 R06 或累计档案规格关闭。

对照源：`app/storage/source_reference_successors.py`、`app/services/source_reference_successors.py`、`app/storage/fact_repositories.py`、`app/storage/evidence_expectation_repository.py`、`app/services/fact_publication_service.py`、`app/domain/contracts/facts.py`、`app/domain/contracts/evidence_expectations_v2.py`、`tests/v2/services/test_fact_publication_service.py`、`tests/v2/domain/test_phase5_fact_contracts.py`、`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17.5。

---

### Evidence

**E1. 单跳事实衔接（仓储）。**  
`validate_source_fact_references`（`source_reference_successors.py` 32–62）：每个新 ID 要么已在 prior 集合，要么 `inherited_from_fact_id` **直接**落在 prior 集合；校验权威、同 `stable_identity`、`revision+1`、locator/候选/门禁超集；落地 prior 成员不得在 `superseded_entity_ids`。隔代（F3 对 F1）、无关 ID、已更正目标/父、未换版本均拒绝。

**E2. 事件/暴露后继。**  
`source_successor_origin_run`（6–29）：除 `id/source_revision_of/run_id/revision/created_at/fact_ids` 外 dump 必须等于 prior；跨 run；`revision==prior+1`；prior 未更正；候选与门禁非空；当前 run 权威一致；然后走 E1。`create()` 用 **prior.gate_id 的 origin_run** 做原接受门禁/语义/locator，再 `_require_revision_chain_head`（`fact_repositories.py` 1457–1517、1730–1798）。服务只改上述可变字段，locator/剂量/类型/候选/门禁保持原值（`source_reference_successors.py` 服务 23–39）。

**E3. 期望后继。**  
`project()` 在 `source_revision_of` 时冻结 status/gap/权威/模板/`input_gap_signals` 等，仅允许改 `expectation_id/source_revision_of/revision/created_at/coverage_fact_ids/locator_ids`（`evidence_expectation_repository.py` 142–157）。服务把 locator 设为新覆盖事实的并集（服务 57–62）；`_require_locators_within_coverage` 要求与覆盖闭包 **全等**（235–250）。链头由 `(episode, template_id)` 的 latest+1 约束（166–178）。无 `run_id`，哈希不含 `run_id`（服务 48–51，对比事件 28–31）。

**E4. 发布与失败关闭。**  
有 `inherited_from` 的事实发布后追加事件/暴露/期望，再跑 Profile 引用闭包；失败则 `FactPublicationError("新增来源尚未与既有病史…")`（`fact_publication_service.py` 305–330）。服务仍不 commit。冲突不追加。`_published_conflicts` 仍是全部未 superseded 组，无链头（Profile 服务既有行为）。

**E5. 更正与 replay。**  
事实 prior 取全表 max revision，若该头已更正则拒绝复活（442–449）。Replay 在过滤前跑，且不计 `source_revision_of` 行的候选（344–375）。测试：更正后 `publish(run3)` 仍 replay；再发旧值拒绝（934–947）。

**E6. 测试覆盖（已有）。**  
三跑：事件/暴露 `source_revision_of` 指向上一后继、期望链、locator 并集、`generate()` succeeded、replay 的 event/exposure id（869–898）。临床字段：`create`/`project` 改 `event_type`/`dose`/`input_gap_signals` 拒绝（794–805）。未和解冲突：`begin_nested` 下整笔失败，事实与冲突 ID 仍为第一次发布（1186–1236）。旧 payload 缺 `inherited_from` / 事件暴露 `source_revision_of` 可 decode（`test_phase5_fact_contracts.py` 226–242）。**无** 期望缺字段 decode 测试。

**E7. §17.5。**  
Profile ≠ 最后一次 run；先链头再排除校正目标；`inherited_from` 保留旧候选+本 run 主记录；事件/暴露/期望 `source_revision_of` 只引用 **直接上一版** 事实；保留临床字段/状态/缺口/原始发布依据；期望定位随事实来源并集更新；冲突等不闭合则整笔拒绝；三版档案测试不能替代原件 QC。另有尚未接入的“独立累计来源投影”规格（禁止按 identity 改号、禁止无候选拼旧定位）。

---

### Inference（按严重度）

**P1 — 部分事务：仓储行已写入，整笔拒绝不在 `publish()` 内原子化。不是引用规则被绕过，是失败关闭依赖调用方事务。**  
闭包检查在事实、冲突、后继 `create`/`project` **之后**（305–330）。`test_source_append_with_unreconciled_conflict_rolls_back` 用 **测试侧** `begin_nested`（1224–1226）才看到事实/冲突未变。无 savepoint 的调用方若只 `except FactPublicationError`，会话里会留下新事实链头与后继行，Profile 仍坏。  
分类：**调用方契约缺口 / 服务未自带 savepoint**，不是 E1 规则失效。最小修：仅在 `inherited_from` 分支用 nested savepoint，闭包失败则 rollback 该 savepoint。

**P2 — 冲突失败关闭是故意且已测；不是缺陷。未做 source-only 冲突修订时，有冲突的节点无法追加来源。**  
旧组成员仍是活引用（无链头）。追加新组而不改 `_published_conflicts` **不能**修复闭包。见下方最小合同。不要把失败关闭理解成“应删成员或标已解决”。

**P3 — stale / 无关 / 重复：产品 `create`/`project` 路径不能绕过仓储；若干负例只有 helper 或未写测试。**

| 情况 | 强制点 | 判定 |
|---|---|---|
| 过期事件/暴露 prior（非链头） | `revision==prior+1` **且** `_require_revision_chain_head`；仅当 prior 已是头 | **未绕过** `create`。`origin_run` 单独不查链头 → **缺测试**，非缺陷 |
| 过期期望 prior | `revision==prior+1` 对 latest 失败（166–178） | **未绕过** |
| 无关 `fact_id` / 隔代 F3←F1 | `inherited_from not in unmatched`（41–45） | **未绕过**。**缺** `create`/`project` 反例 |
| 已更正 prior 事件或落地事实 | 19 行 prior excluded；58–59 行落地 excluded | **未绕过**。事件 prior 更正 **缺测试**（事实侧有 patch/旧值测） |
| 重复 `fact_ids` | 合同有序唯一；重复会第二次把 parent 移出 unmatched | **未绕过**。缺测试 |
| 同时保留旧 ID + 新后继 | 先摘 prior，第二 ID 的 parent 已不在 unmatched | **未绕过**。缺测试 |
| 改临床/缺口 | dump 冻结；794–805 已测 create/project | **未绕过** |

**P4 — 期望后继弱于事件后继（漏检，不是已证绕过）。**  
`project()` 不查 prior 是否更正目标（期望本不是 `FactCorrection` kind）、不查跨 run、哈希无 `run_id`。链头 + dump 冻结仍挡住改 status/gap。缺：期望旧 payload decode、错误 locator 并集、隔代 coverage。

**P5 — 事件后继不并入新 locator，期望并入。**  
与 §17.5「期望定位随事实来源更新」vs「事件保留原始发布依据」一致。事件 `_require_locators_within_facts` 是子集，旧 locator ⊆ 新事实并集。**不是缺陷。**

---

### Recommendation

1. **最小原子性：** `publish()` 在 305–330 外包 `begin_nested()`，Profile 失败 rollback nested。保留现有冲突测试，并加「无测试侧 savepoint、只 catch」的反例，证明服务自己能清掉 F2/后继。  
2. **冲突：维持失败关闭**，直到有链头选择。不要在现合同上改写旧 `conflict_group_id` 或丢掉成员。  
3. **必要反例（测试，非新架构）：**  
   - `create`：事件 `fact_ids=[无关]`、`[隔代 F3]`、`source_revision_of=已更正事件`、`source_revision_of=非链头`。  
   - `project`：coverage 隔代、locator ≠ 事实并集、缺 `source_revision_of` 的旧 JSON decode。  
   - 冲突+事件依赖同时存在时 nested 回滚后无后继行。  
4. **不要**为绿测去解析/丢冲突成员。

**最小 source-only 冲突修订合同（建议，非实施授权）：**

- 字段：`source_revision_of: str | None`、`revision: int >= 1`。  
- **不要**用 `resolution_revision`（合同强制未解决为 0，`facts.py` 606–609）。  
- 可变：`conflict_group_id`、`source_revision_of`、`revision`、`created_at`、`run_id`、对应成员 ID 列表、`locator_ids`（成员闭包并集）。  
- 冻结：`authority`、`member_kind`、`gate_id`、原门禁/候选依据、`resolution_revision==0`。  
- 成员：基数不变；每个 ID 经同一 `validate_source_fact_references` 单跳替换或保持；**禁止删成员、禁止标已解决**。  
- Profile：按 `(authority, member_kind, 稳定语义键)` **先链头再排除 superseded**；否则旧组仍悬挂。稳定键需新增（当前 id 含 run+member 哈希，不能当链）。  
- 旧组只读历史。无语义键就继续整笔拒绝（现状）。

---

### Uncertainty

- 未在本 session 重跑 231 项或全量回归；测试结论来自源码与测试正文。  
- 生产执行器是否一律在事务/savepoint 中调 `publish()` 未读。  
- §17.5 后半「独立累计来源投影」仍标明未接入；本窄路径不满足那份待审规格（按版本展示旧 fact 引用而不改号）。  
- 期望 `source_revision_of` 与幂等 `_coverage_content`（不含该字段）在「内容碰巧相同」时会返回已有行；产品路径因 coverage 变化不会撞上。

---

### 窄路径是否可支持

**可以支持**，条件与 §17.5「2026-09-13 实现边界」一致：同权威；事实 `inherited_from` 并集旧候选+本 run 主门禁；事件/暴露/期望 `source_revision_of` 单跳；临床字段/缺口/原门禁冻结；期望 locator 并集；已更正链头不复活；历史行不覆盖；冲突不闭合则整笔拒绝（须事务真正回滚）；三跑 `generate()` 只证明该夹具，不能代替原件 QC。

**不可支持为：** R06 关闭、冲突已衔接、累计来源投影、临床接受。P1 在调用方无事务时会让“拒绝提交”落空，应视为本窄路径落地前的最小补强，而不是推翻追加模型。
