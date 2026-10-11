Codex asked for a same-session read-only follow-up on the frozen successor path. I’ll inspect the new source-reference modules against publication, repositories, and tests.The successor path is in place. Next I’ll read the contract, publish/replay, repository gates, and the updated tests.# Conference Output: r06-inheritance-review-20260913 - evidence_single_object

## Output

只读续审（同一 session，round 2）。未改源码、未跑测试、未读库/原件、无网络。Codex 仍是终裁。本轮不把 R06 当已关闭。

已读（本轮冻结集）：`app/storage/source_reference_successors.py`、`app/services/source_reference_successors.py`，以及更新后的 `app/domain/contracts/facts.py`、`app/services/fact_publication_service.py`、`app/storage/fact_repositories.py`、`tests/v2/services/test_fact_publication_service.py`；对照 `app/services/patient_profile_service.py`、`app/storage/active_facts.py`、`app/domain/contracts/evidence_expectations_v2.py`、`tests/v2/domain/test_phase5_fact_contracts.py`。

对 round 1 的订正：I1（事件/暴露悬挂）已被 source-only 后继部分覆盖；I2（滤完再取 prior / 更正后原 run 当新发）已被“全表链头 + 更正则拒绝 + replay 用未过滤 existing”部分覆盖；空 `current_ids` 假值回退已关掉。下列是对 **窄实现** 的新反例与漏检，不是再要一套架构。

---

### Evidence

**E1. 合同。**  
`ClinicalEventV2` / `MedicationExposureV2` 增加 `source_revision_of`（默认 `None`）。`ClinicalFactV2` 仍只有 `inherited_from_fact_id`。冲突组无 revision / `source_revision_of`（`facts.py` 447、502、572–610）。期望有 `revision` + `coverage_fact_ids`，走 template 链头（`evidence_expectations_v2.py` 187–194）。旧事实缺 `inherited_from_fact_id` 可 decode（`test_phase5_fact_contracts.py` 226–236）。事件/暴露缺 `source_revision_of` 无对等测试。

**E2. 发布顺序。**  
`publish()` 先对 **未按更正过滤** 的 existing 做 replay；replay 之后只从 existing 事件/暴露去掉 `superseded_entity_ids`，**事实不清**（`fact_publication_service.py` 198–240）。有 `inherited_from_fact_id` 的事实发布完后调用 `append_source_reference_successors`，再用 Profile `_validate_referential_closure`；失败则 `FactPublicationError("新增来源尚未与既有病史、用药及审核记录衔接，拒绝发布")`（305–330）。冲突/期望不在后继函数里。

**E3. 后继写入。**  
`append_source_reference_successors` 用 **当前 Profile 事件/暴露链头**（先链头再排除更正），把 `inherited_from → 新 fact_id` 套到 `fact_ids`；无变化则跳过。新行只改 `id/run_id/revision/created_at/source_revision_of/fact_ids`，其余从 prior `model_dump` 拷贝，含原 `gate_id` / `source_candidate_ids` / locator / 临床字段（`source_reference_successors.py` 服务 9–41）。

**E4. 仓储校验 `source_successor_origin_run`。**  
`mutable = {id, source_revision_of, run_id, revision, created_at, fact_ids}`。其余 dump 必须等于 prior；跨 run；`revision == prior+1`；prior 不在 superseded；`source_candidate_ids`/`gate_ids` 非空；当前 run 权威一致。然后对每个新 `fact_id` 沿 `inherited_from_fact_id` 走到 prior 的 `fact_ids`：环、更正、无继承边、权威/身份/非 +1 revision、locator/候选/门禁非超集一律拒绝。落地事实不得已更正/跨权威。必须用尽 prior 引用且 `fact_ids` 列表不能相同。返回 **`prior.gate_id` 所属 run**，不是后继的 `run_id`（`storage/source_reference_successors.py` 6–55）。  
`create()` 仍用该 origin_run 做原接受门禁/语义/locator 闭包，并做 `_require_revision_chain_head`（`fact_repositories.py` 1457–1517、1730–1798）。

**E5. 事实继承。**  
prior = 全表同身份 max revision；若该头在 superseded 则 `FactPublicationError("该事实最新版本已经更正，不能从旧版本恢复来源")`（442–449）。仓储要求本 run 必须有非空新候选和新门禁（1205–1206），不再把空列表当遗留单候选。

**E6. Replay。**  
`source_revision_of is None` 的实体才把 `source_candidate_ids` 计入已发布候选；再减去直接父事实的候选后与本 run accepted 比较（353–375）。后继行的旧候选不进入“新模型候选”。

**E7. 测试。**  
`test_later_run_preserves_fact_identity_and_sources` 现参数化 `has_dependent_event`：二次发布断言后继 `source_revision_of`、事实 ID、locator/候选未改、旧行不变；对暴露 `source_successor_origin_run` 负例仅 `dose` / 空候选 / 空 `fact_ids` / 相同 `fact_ids` / 改 locator。三次发布只断言事实并集与 replay，**不断言** 第三次后继边。更正后 `run3` replay 仍成功；再发旧值 120/80 期望“最新版本已经更正”。无冲突、无期望、无 `PatientProfileService.generate()`、无环、无更正 prior、无无关 `fact_id`、无同 run、无事件侧负例、无 `create()` 路径负例。

**E8. Profile 选择不对称。**  
事实/事件/暴露：链头后排除更正。冲突：**全部** 未 superseded 组（无链头）。期望：按 `template_id` 链头（`patient_profile_service.py` 333–398）。

---

### Inference

**I1. Round 1 的事件/暴露悬挂，在“无冲突、无期望”真空里已被这条窄路径接上。**  
后继冻结临床字段与原门禁，只改 `fact_ids`；origin_run 让仓储按 **原 run 已接受门禁** 复核，而不是伪造本 run 候选。新事实因继承并集仍包含旧 `source_candidate_ids`，故 `_require_fact_candidate_reference_closure` 仍能过。这与“source-only、不发明规范化调用”一致。二次依赖测试覆盖的是这条真空路径。

**I2. 冲突/期望未级联 + 事务末 Profile 闭包 = 有档案的受试者上，来源继承会整笔拒绝。**  
这不是隐藏行为，是 313–330 的明示策略。但 `_published_conflicts` 把旧组成员 ID 全部视为活引用；即便另写一个新冲突组，旧组仍在集合里，闭包照样失败。期望则不同：已有 `revision` 链头，**可以用与事件相同的追加方式** 改 `coverage_fact_ids`。  
反例：Run1 发布 F1，并已有 OBSERVED 期望 `coverage_fact_ids=[F1]`（或冲突成员含 F1）。Run2 只给 F1 追加来源 → 事件/暴露后继写完 → `_latest_expectations` / `_published_conflicts` 仍指向 F1 → 整笔 `FactPublicationError`。现有测试从未建期望/冲突，所以绿不能证明“有 Profile 的节点也能追加来源”。

**I3. 仓储对 prior/target 的 stale/corrected/unrelated/empty/cyclic 覆盖不齐。**  
| 情况 | 实际 | 缺口 |
|---|---|---|
| 更正的 prior 事件/暴露 | `prior id in excluded` | 无测试 |
| 更正的目标/中间事实 | walk / 落地检查 `excluded` | 无测试 |
| 无关 `fact_id`（无 `inherited_from`） | 走到 `None` 拒绝 | 无测试 |
| 身份被改的继承边 | `stable_identity` 不一致拒绝 | 无测试 |
| 空候选/门禁 | 拒绝 | 只测了空候选，空 `gate_ids` 未测 |
| 空/相同 `fact_ids` | 拒绝 | 有（暴露、且绕过 `create`） |
| 改临床字段 | dump 不等 | 只测暴露 `dose`；事件字段未测 |
| 同 run | `run_id` 相等拒绝 | 无测试 |
| 环状 `inherited_from` | `seen` | 无测试 |
| stale 非链头 prior | 函数本身不查链头；`create` 的 `_require_revision_chain_head` 会因 revision 碰撞失败 | 无直接断言；错误信息不是“必须是链头” |
| 多跳继承（F3→F2→F1 一次后继） | walk **允许** | 服务每 run 只换一跳；仓储比服务松。未测是否应禁止跳步 |
| 后继 `fact_ids` 同时保留旧 ID 和新 ID | 先摘走 unmatched，第二 ID 会继续走到已移除节点后失败 | 无测试 |

**I4. 三跑 replay 对后继是代码上说得通、测试上没钉住。**  
Run3 服务会把链头 E2 换成 E3（`source_revision_of=E2`，`fact_ids=[F3]`）。Replay 排除 `source_revision_of` 行后只剩 F3 的新候选。逻辑闭合。测试在 `has_dependent_event=True` 时仍会走到 run3，但只查事实 `inherited_from` 与 `is_replay`，不查 E3 边、不查 replay 的 `event_ids` 是否含后继、不调 `generate()`。

**I5. 负例打在 `source_successor_origin_run` 上，不经过 `create()`。**  
因此不行使：原门禁语义、`_require_locators_within_facts`、`_require_fact_candidate_reference_closure`、链头追加。`fact_ids=[]` 若 `model_copy` 触发合同 `min_length=1`，可能变成 `ValidationError` 而不是 `Phase5RepositoryError`（取决于是否 revalidate）。

**I6. 事实侧更正排除已与 `current_fact_heads` 对齐，round 1 的复活路径在服务层被关掉。**  
existing 含已更正头 → max 仍是该头 → 449 行拒绝，而不是落到 F1。`old-value` 分支是这条的正反例。Replay 在过滤前跑，故更正 `latest` 后 `publish(run3)` 仍 replay，不再把原 run 追加成新 revision。这点 round 1 应收回。

**I7. 窄实现没有“不支持的临床语义”写入路径。**  
后继 dump 冻结事件类型/起止/持续/剂量/强度/`referenced_fact_objects` 等。想改语义必须走普通候选发布或人工修订。风险是 **漏检**（测试少）和 **冲突/期望把合法来源追加整笔打死**，不是后继能改诊断。

---

### Recommendation

不要重做架构。按现有追加模型补边界：

1. **期望：同样做 source-only 后继。** `EvidenceExpectationV2` 已有 revision + template 链头。冻结除 `expectation_id/revision/created_at/coverage_fact_ids`（及如需要的 `source_revision_of`）外的字段，按同一 `inherited_from` 映射改覆盖事实，走链头 +1。这是与事件后继同构的有界补丁，能解开 I2 里最常见的 OBSERVED 覆盖。

2. **冲突：先保持失败关闭，但必须有测试。** `_published_conflicts` 不是链头模型，只追加新组不够。在改选择规则或 superseded 之前，继承若碰到旧冲突成员，应继续整笔拒绝，并加回归，防止有人删掉 313–330 的闭包检查。

3. **仓储漏检（有界）：**  
   - prior 必须是该 `stable_identity` 的全表链头（不要只靠 revision 碰撞）。  
   - 每个新 `fact_id` 的 `inherited_from_fact_id` 必须落在 **未匹配的 prior.fact_ids 上（单跳）**，与服务每 run 一跳一致；若 Codex 明确允许一次走完多跳，则写进合同并测 F3→F1。  
   - 负例走 `repository.create()`：更正 prior、更正目标事实、无关/空/环、同 run、事件临床字段、空 `gate_ids`、权威不一致。

4. **测试钉三跑依赖链：** `has_dependent_event=True` 时，第三次后继 `source_revision_of` 必须是第二次后继 ID（不是原始 E1）；第三次 replay 的 `event_ids`/`exposure_ids` 含后继且 `is_replay`；`PatientProfileService.generate()` 在无冲突/期望时成功。另：继承冲突成员或 OBSERVED 期望时，断言现有拒绝文案。

5. 事件/暴露缺 `source_revision_of` 的旧 payload decode 应与事实 `inherited_from` 测试对称。

未做完 1+4 前，不要把跨 run 来源继承接到“已有期望/冲突的正式节点”上。真空里的事实+事件+暴露可以视为窄路径的暂定行为，不是 R06 关闭。

---

### Uncertainty

- 未跑测试；三跑后继与 Profile `generate()` 是源码路径推论。  
- Pydantic `model_copy(update={"fact_ids": []})` 是否在本仓库版本上 revalidate，未执行确认。  
- 多跳 walk 是有意（一次对齐已存在的较新事实）还是疏漏，合同未写。  
- 执行器是否在 `FactPublicationError` 后 rollback：服务声明不 commit，但是否所有调用方都回滚未核。  
- 更正服务是否已级联事件 `fact_ids`：本轮后继不替代那条谱系；更正后的悬挂不在本窄实现声明范围内。

---

### 对上一轮与本窄实现的异议

- Round 1 把事件/暴露悬挂当成 P0 实现洞。本轮用 source-only 后继 + 事务内闭包，在无冲突/期望时成立；再要求“全面级联所有下游”过宽。  
- 反过来：用 Profile 闭包当安全网、却不测期望/冲突，会把 **最常见的已投影节点** 变成整笔失败，而测试全绿。这是本轮最高影响缺口。  
- 负例只打 helper、三跑不断言后继边，审查者可以认为“来源闭包已测完”；实际只测了二次暴露 dump 冻结。

---

### 给 Codex 的决策点

1. 期望是否按事件同构追加（建议：是，有界）？  
2. 冲突在选择规则改之前是否 **必须** 失败关闭（建议：是，加测试锁住）？  
3. `inherited_from` 路径允许一跳还是多跳（建议：与服务一致，单跳）？

---

### 给 Codex 的有界问题

- 已生成过 Patient Profile、存在 OBSERVED 期望的节点，是否必须能只追加来源而不重抽事件？若必须，I2 就是发布缺陷，补期望后继即可，不必重做。  
- 一次后继是否允许 `fact_ids` 直接指向隔代继承事实（F1→F3）？允许则补测试；不允许则仓储改单跳。

未决前的安全暂定：把当前实现当作“无冲突、无期望、事件/暴露链头可追加”的窄门禁；不要宣称严格来源闭包或 R06 完成。本输出不是临床/监管/视觉/现网接受。
