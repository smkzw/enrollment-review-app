I'll start with the assigned read set and independently audit inheritance, source closure, correction exclusion, and downstream citations.The assigned sources are frozen for a read-only inheritance review. Next I’ll inspect the fact contract, publication, repositories, and tests.The inheritance field is concentrated in four source files. I’ll read those contracts, publish/replay paths, repository checks, and tests next.Inheritance is implemented in publish, repository, and tests. I’ll read those three paths in full next, plus correction and downstream reference checks.Several inheritance branches look inconsistent. I’ll read correction exclusion, revision chaining, event/exposure resolution, and payload decode next.# Conference Output: r06-inheritance-review-20260913 - evidence_single_object

## Output

只读审阅。未改源码、未跑测试、未读生产库/临床原件。Codex 仍是终裁。

已读：`context/r06-inheritance-review-20260913_conference_context.md`、`plans/codex_main_venue_r06-inheritance-review-20260913.md`、`app/domain/contracts/facts.py`、`app/services/fact_publication_service.py`、`app/storage/fact_repositories.py`、`app/storage/fact_correction_repository.py`、`app/storage/active_facts.py`、`app/services/fact_correction_service.py`、`app/services/patient_profile_service.py`、`app/storage/codecs.py`、`app/domain/contracts/common.py`、`tests/v2/services/test_fact_publication_service.py`、`tests/v2/services/test_patient_profile_service.py`。因下游引用闭包必须对照链头折叠规则，额外读了 Profile / 修订活跃集，不属于改范围。

---

### Evidence

**E1. 继承只发生在事实上，且生成新 `fact_id`。**  
`ClinicalFactV2.inherited_from_fact_id` 有默认 `None`（`facts.py` 378）。`ClinicalEventV2` / `MedicationExposureV2` 无对等字段。`_publish_facts` 按 `stable_identity` 取 `existing` 中 `revision` 最大者为本，并集 `source_candidate_ids` / `gate_ids` / locator，写入新实体（`fact_publication_service.py` 419–458）。事件/暴露只按当前运行候选 `_next_revision`，不并集旧溯源（同文件 534–556、593–618）。

**E2. 仓储对继承做了当前运行闭包，但信任“所选 prior”。**  
`ClinicalFactV2Repository._publication_candidates`（`fact_repositories.py` 1174–1223）：无 `inherited_from` 时整组按当前 `run_id` 校验；有则要求 prior 同权威、同 `stable_identity`、跨 run、`revision+1`、prior 不在 `superseded_entity_ids`，且 prior 的候选/门禁为子集、prior locator 与继承候选 locator 一致、并集 locator 等于发布 locator。当前增量门禁/候选必须属于本 run。`create()` 再对 **current∪inherited** 做语义/资料要求/记录时间/断言依据/`_require_revision_chain_head`（全表链头，含已被修订目标）。

**E3. 发布服务与链头选择方向相反。**  
`publish()` 先按 `list_by_authority` 的 `target_id` 滤掉修订目标，再在剩余集合上取 max revision（`fact_publication_service.py` 201–207、419–423）。  
`current_fact_heads` 先取链头，再排除修订目标，注释写明“removal must not resurrect an older value”（`active_facts.py` 19–39）。

**E4. Replay 也建立在“已滤修订目标”的 existing 上。**  
`_replay_if_published` 用滤后 `facts` 里 `run_id` 匹配的行；若该 run 的事实已被修订目标滤掉，则 `run_facts` 为空，函数返回 `None`，随后走新发布（`fact_publication_service.py` 233–245、322–361）。减去的是 **直接父事实** 的 `source_candidate_ids`，不是递归闭包。

**E5. 下游按精确 `fact_id` 闭包，禁止改写历史 ID。**  
Profile：`_published_facts` = `current_fact_heads`；事件/暴露取自身链头且不要求 `fact_ids ⊆` 链头；随后 `_validate_referential_closure` 对悬挂引用抛错，并写明“绝不静默并入任意历史实体，也不改写任何 ID”（`patient_profile_service.py` 277–351）。  
已有测试：事件/暴露/冲突/期望仍指向非链头事实时，`generate()` 失败（`test_patient_profile_service.py` 540–594）。  
修订活跃集则是另一策略：悬挂事件/暴露/冲突/期望被静默丢掉（`fact_correction_service.py` 227–274）。

**E6. 修订新实体不是继承边。**  
`_build_new_fact` 初始 `source_candidate_ids=[]`、`inherited_from_fact_id` 缺省；prepare 时改成仅 `[fcorr-cand]` 且新 `run_id`（`fact_correction_service.py` 603–610、758–784）。谱系在 `FactCorrectionRecord.target_id → new_entity_id`，不在 `inherited_from_fact_id`。

**E7. 现有继承测试只覆盖“纯事实、无下游、无真修订”。**  
`test_later_run_preserves_fact_identity_and_sources`（`test_fact_publication_service.py` 625–781）：二次/三次发布只断言 identity、revision、子集关系、`inherited_from`、同 run replay。三次运行的候选是二次候选的拷贝，locator 相同，故 `latest.locator_ids == current.locator_ids`（777）不能证明三跑 locator 并集。修订排除用 `patch superseded_entity_ids` 打在 **已建成的** `_publication_candidates` 上，不经 `publish()` 选 prior。无事件/暴露/冲突/期望/Profile。

**E8. 遗留载荷。**  
`inherited_from_fact_id` 默认 `None`，`decode_contract` → `model_validate`，缺字段可还原。`source_candidate_ids`/`gate_ids` 默认 `[]`。`_validate_publication_group` 把空列表当旧调用方，回退主门禁单候选（`fact_repositories.py` 878–885：`candidate_ids or [primary]`）。继承路径遇到空 prior 溯源直接拒绝（1197–1202）。

**E9. 当前运行事件可通过 `candidate_to_fact` 绑到新事实。**  
`_publish_facts` 把 **并集后的全部** `candidate_ids`（含父事实旧候选）映射到新 `fact_id`（458–460）。`_resolved_fact_ids` 只查这张表（627–633）。仓储闭包允许引用事实的 `source_candidate_ids` 为超集（1015–1040）。**已持久化的旧事件行不会被更新。**

---

### Inference

**I1. P0 反例：跨运行继承事实会弄断 Profile。**  
Run1 发布 F1 + 事件 E1（`fact_ids=[F1]`）。Run2 对同一 `stable_identity` 再发现来源，只发布继承事实 F2（`inherited_from=F1`，新 `fact_id`）。`current_fact_heads` 选 F2。E1 仍是事件链头且仍指向 F1。`_validate_referential_closure` 与 `test_patient_profile_service` 的悬挂用例同构，投影应失败。暴露、冲突成员、期望 `coverage_fact_ids` 同理。  
这不是边角：继承的产品含义就是“同一事实追加来源”，临床上事件/用药常常不再次抽出。现有继承测试恰好避开了这条路径，因此“测试通过”不能当作产品接受。

**I2. P0/P1 反例：更正排除与链头选择不一致，会指向更旧未更正版本。**  
设 F1 rev1 → F2 rev2（继承），再把 F2 更正为不同 `stable_identity` 的 G。`superseded={F2}`，F1 仍在 existing。后来 run 再抽出旧身份：`publish()` 的 prior=F1（更旧、未更正）。仓储只拒绝 prior 自身在 superseded 中，因此 `_publication_candidates` 会接受“继承 F1”。随后 `_next_revision(filtered)=2`，而 `_require_revision_chain_head` 看见全表头仍是 F2，要求 3。结果是失败关闭，但错误是“revision 必须链头+1”，不是“禁止继承已更正谱系的旧版”。与 `current_fact_heads` 的“去掉链头不得复活旧值”直接冲突。

同身份更正（F1→F1′ rev2）后再对 **原 run_id** 调 `publish()`：原事实被滤掉，replay 判定“未发布”，会从 F1′ 再追加一版，并把原 run 候选并回更正后的溯源。这是重复发布，不是 replay。

**I3. 溯源并集在“纯事实、prior 未更正、候选 ID 不碰撞”下是闭合的。**  
服务层并集 + 仓储子集/当前 run 门禁一一对应 + locator 等式，能挡住：去掉 `inherited_from`、自指、跳号、换权威、丢掉父候选/门禁/locator、把旧门禁当主门禁。这是现有单测真正覆盖的范围。

**I4. 空列表在继承增量上是假值漏洞。**  
若 `source_candidate_ids == prior.source_candidate_ids`（无新候选）或 `gate_ids - inherited` 为空，`_validate_publication_group` 会把空列表当成遗留单候选。`_publish_facts` 只对当前非空 group 发事实，正常路径不易触发；仓储 API / 构造 payload 可以。

**I5. 两次下游策略互相矛盾。**  
Profile：悬挂 → 硬失败。修订活跃集：悬挂 → 丢弃。继承实现两者都不做级联改写，所以同一数据在 Profile 生成失败，在修订影响集里事件消失。

---

### Recommendation

优先修复（实现须 Codex 授权；本角色只建议）：

1. **继承与下游引用必须同事务闭合。** 二选一，不可并存：  
   - **A（与 Profile 现有不变量一致）**：追加事实链头时，对所有 `fact_ids`/`coverage_fact_ids` 含 prior 的事件/暴露/冲突/期望追加新 revision，指向新 `fact_id`，并带明确继承/级联边；做不到则拒绝本 run 发布。  
   - **B**：改 Profile/活跃集，允许沿 `inherited_from_fact_id` 或同 `stable_identity` 解析旧 `fact_id`。这与 `patient_profile_service.py` 288–291 的明文禁令冲突，需 Codex 先改合同。  
   默认建议 A。不建议修订活跃集那种静默丢事件。

2. **继承 prior 的选择必须与 `current_fact_heads` 同构。** 先取该 `stable_identity` 的全表链头；若链头在 `superseded_entity_ids` 中，则 **没有** inherit source（不要用更旧 revision）。`_next_revision` 必须看全表，不能看滤后集合。仓储除“prior 本身被更正”外，还应拒绝“prior 不是全表链头”。

3. **Replay 必须按 run 的持久化行，而不是滤掉修订目标后的 existing。** 原 run 的事实被更正后，再 `publish(run_id)` 应 replay 或显式冲突，不得追加新 revision、不得把已更正候选并回新链头。

4. **补测试（当前缺口即反例）。** 不要把已绿的 `test_later_run_preserves_fact_identity_and_sources` 当接受证明。最小集：  
   - 事实+事件（及暴露/冲突/期望）→ 次 run 只继承事实 → 在修复前应红：Profile `generate` 失败；修复后应绿：下游 ID 指向新链头且旧行不变。  
   - 三跑 **新 locator** 的精确并集，而非子集、而非拷贝同一 locator。  
   - 真 `FactCorrectionRepository.create`（不要只 patch）：更正链头后选 prior；更正后原 `run_id` 必须 replay/冲突。  
   - 身份变更更正后禁止复活旧 revision。  
   - 缺 `inherited_from_fact_id` 的旧 payload 能 decode；空 `source_candidate_ids` 的 prior 不能继承。  
   - `current_ids`/`gate_ids` 空列表不得走遗留单候选回退。

5. 事件/暴露若也要跨 run 并来源，应有对等 `inherited_from_*` 与闭包；现在只有事实，文档/测试不得暗示“实体级继承”。

---

### Uncertainty

- 未跑测试；反例由源码路径与已有悬挂 Profile 测试对齐推出，不是运行日志。  
- 规范化器是否会把 **旧 run 的 `fact_candidate_ids`** 写进新事件未知。若会，`candidate_to_fact` 会把旧候选 ID 静默绑到新事实；若不会，旧事件仍悬挂。  
- 更正后原 run 再 publish 在调度上是否会发生：代码允许，测试当幂等目标，但是否有作业重试未查执行器。  
- 身份变更更正后，新 run 再次抽出“旧错误值”应永久禁止还是允许开新链，属产品决策。  
- 断言依据取 `min(candidate_id)`（含继承候选），新来源的 assertion 可能被旧 ID 压过；未看到合同要求“最新依据”。  
- 未读 `AGENTS.md`（不在初始读集）。未把 artifacts 副本当真相源。

---

### 对计划的质疑

主场计划写“Codex verifies concrete findings and implements only supported fixes”，但冻结实现把 **不可变新 `fact_id` 链头** 与 **Profile 精确 ID 闭包** 同时当作不变量，二者在“只并来源、不级联下游”时互斥。把 passing tests 当安全网是错的：唯一继承测试没有下游实体，而悬挂失败测试已存在于另一文件。  
`exact provenance union` 在仓储对事实候选/locator 基本成立；缺口在 **更正后的 prior 选择、replay 集合、以及事件/暴露/冲突/期望引用**。  
修订排除若只打 `prior.fact_id in superseded`，覆盖的是“不要继承已被替换的那一行”，覆盖不了“不要继承那一行的祖先”。

---

### 给 Codex 的决策点

1. 继承事实时，下游引用是 **级联追加新 revision（建议 A）** 还是 **改读时解析（B）**？B 要先改 Profile 合同。  
2. 继承 prior 是否必须与 `current_fact_heads` 一致（先链头后排除）？不一致则 I2 会继续存在。  
3. 某 run 的已发布事实被更正后，原 `run_id` 的 `publish()` 是 replay 还是硬冲突？当前会变成第三次追加。  
4. 事件/暴露是否纳入本冻结的继承范围？若否，A 仍要级联改 `fact_ids`，否则 Profile 在“只补事实来源”时不可用。

---

### 给 Codex 的有界问题

- 次 run 只追加同一生命体征/检验事实、不重新抽出诊断事件或用药暴露，是否为必须存活的产品路径？若是，I1 就是发布门禁缺陷，不是 Profile 过严。  
- 更正若改变 `stable_identity`，旧身份是否应在该权威下永久不可再发布？这决定 I2 修复是“拒绝复活”还是“允许新链头但不继承祖先”。

未决前的安全暂定路径：不要把当前继承实现当成已关闭来源闭包；不要扩到更多调用方；落地修复前以 I1+I2 的确定性测试为准。本输出不是临床/监管/视觉/现网接受。
