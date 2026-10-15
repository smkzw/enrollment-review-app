I'll read the dual-lineage contracts, migration, and repository checks in full, then look for payload, FK, and old-path defects.# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读审阅已落地的双谱系存储修订。未跑迁移/测试；运行时与 `PRAGMA` 实测标为不可用，不当作通过。正式 V2 装配/发布/HTTP 未做，不记为本切片缺陷。旧门控仍只认 legacy 快照。

### Evidence

合同用显式 `review/v2`，`fixture/v1` 序列化省略新键（`review_evidence_scope.py:11-40`；`ReviewRun` 再省略 `episode_revision`，`review.py:173-178`；`ActionRequest` 省略 `trigger_locator_id`，314-318；`ActionTransition` 省略 `locator_ids`，281-286；`AgentCallContract` 同，`agents.py:76-82`）。Gate 指纹走 `model_dump`（`review.py:243-254,344-354`）。所有者称 63 个既有 fixture 对象哈希未变；本角色未复跑。

物理 CHECK：正式四表 XOR 谱系（`models.py:41-46`）；`agent_calls` 另允许三指针全空（48-57）。`action_requests` 另有触发定位 XOR（287-290）。V2 关联表有真实父 FK（1538-1567）。迁移 0023 拷贝旧列、新列写 NULL，降级在出现 V2 指针/空 legacy（AgentCall 除外）或新关联有行时拒绝（`0023_…py:33-36,606-645`）。

`AppendRepository._decode` 对 `AssocSpec.schema_version is None` **直接跳过**读回核对（`repositories.py:361-362`）。未版本化的关联仍包括：`evidence_snapshot_documents`、`clinical_fact_spans`、`agent_call_sources`、`agent_call_gate_results`（1074-1079,1107,1382-1383）。写入侧对 `schema_version is None` **仍写入**（304-306）。

`ActionRequest.get` 只对转换 **id 集合**（2309-2321），不核对 `action_transition_spans` / `action_transition_locators`。空 `transitions` 合法。

`require_registered_review_scope` 仍强制 `evidence_snapshot_id` 并 `registry.require("evidence_snapshot")`（`scope.py:60-76,104-110`）。`expected_schema_version` 仍比对 **PromptVersion.schema_version_id**（147-148），现传入 `candidate.schema_version`（`assessment.py:114-118`）。legacy 候选仍是 `fixture/v1`。

`validate_review_references` 核 `FactAuthority` 与 locator 是否属于**传入权威**的快照成员/处理修订清单（`review_reference_validation.py:28-50`；`fact_authority.py:204-278`）。不是谓词语义证明。读路径 `_decode` **不**再跑该函数。

`env.py`：`transaction_per_migration=False`，无外层 `begin_transaction`（40-58）。失败由 `MigrationManager` 备份恢复（`migrate.py:231-240,335-358`）。0023 在 raw 连接上若 `in_transaction` 则 `commit`，再切 `PRAGMA foreign_keys` 并读回校验（`0023_…py:394-409`）。0010 是 `COMMIT` 失败吞掉且不读回 PRAGMA（0010:694-710）。本切片迁移**未执行**。

### Inference

旧路径哈希能保住，是因为 v1 dump 丢掉新键，且 `payload_get` 缺键当 `None`，与新列 NULL 镜像（`codecs.py:160-184`）。这不证明关联读回仍完整。

`schema_version is None → continue` 会让快照成员、legacy 事实 span、AgentCall 来源/验收 **写入仍发生、读取不再交叉验证**。这是本切片对旧路径的静默削弱，不是 V2 未接线。

AgentCall 库 CHECK 允许 `review_run_id` 有值而三资料指针全空；合同对受试者调用仍要求快照（`agents.py:125-138`）。领域 `save` 先 `encode_contract`，不经合同的 SQL 仍能插入。协议-only 全空仍合法。

V2 写 `ReviewRun` 用 **当前** `episode.active_*` 且 `FactAuthorityValidator.validate()` 要求活动指针与当前 `episode.revision`（`repositories.py:434-457`；`fact_authority.py:111-148`）。历史 **GET 不跑 scope_check**，新激活/新修订不会让旧 run/assessment 读失败。之后若把当前活动事实写进旧 run，`fact.authority != 冻结权威` 会拒写。处理修订清单是冻结 id，不是活动指针；校正新增修订不会改写旧评估行。`validate_locators` 文案写「当前活动快照」（`fact_authority.py:207,265`）易误导，实现用的是传入的 `authority`。

旧门控遇到 `review/v2` 会因缺 legacy `evidence_snapshot_id` 失败；不要说现门控已接受 V2。

### Findings（严重度）

1. **高：未版本化关联读回被跳过。** `repositories.py:361-362` 使 legacy 快照文档、`clinical_facts` span、AgentCall `source_ids`/`gate_result_ids` 不再与 payload 对账，坏行可被读出。  
   **改法：** `schema_version is None` 时按旧逻辑始终核对；仅当 `schema_version` 有值且与 payload 不符时把 expected 视为 `[]`（表必须为空）。写入侧保持「谱系不符则不写」。

2. **中：`ActionRequest.get` 不核对转换定位关联。** 空转换没问题；非空 v1 span / v2 locator 与 payload 漂移不会被发现。  
   **改法：** 按转换 `schema_version` 对 `action_transition_spans` 或 `action_transition_locators` 做与 `_decode` 相同的 `(ref, position)` 比对。

3. **中：`agent_calls` CHECK 弱于受试者合同。** 有 `review_run_id` 仍允许三指针全空（`models.py:50-57`）。  
   **改法：** CHECK 改为：三指针全空 **仅当** `review_run_id IS NULL`；一旦有 run，必须 XOR 一条谱系。协议-only 继续全空。

4. **低：`validate_locators` 错误信息写「当前活动」。** 实现按冻结 `authority`（`fact_authority.py:246-278`）。  
   **改法：** 改文案为「指定权威快照/处理修订」，避免以后有人改成活动指针而弄坏历史读。

5. **低：V2 `ReviewRun` 只能钉当前活动指针。** 不能为已停用快照新建 run。GET 旧 run 不受影响。本切片可接受；正式发布若要「钉历史快照」需另比冻结列，而不是 `episode.active_*`。

迁移：0023 比 0010 多了 PRAGMA 读回；`env.py` 无外层事务，半截重建靠管理器整库恢复。迁移/FK 实测 **未做**，不得写成已通过。失败恢复路径存在于 `migrate.py`，不是本文件已验证。

未削弱：v1 合同仍强制 legacy 快照；XOR CHECK 禁止混列；v1 序列化省略新键；旧门控仍拒 V2。不要把 V2 预备仓储当成已暴露的正式入口。

`validate_review_references` = 权威 + locator 成员，**不是**谓词证明。谓词自动采信仍关。

### Uncertainty

未执行 0023、未读库、未跑套件。63 个 fixture 哈希为所有者陈述。`prompt_version.schema_version_id` 与 `review/v2` 的关系要等正式发布分支，现在 legacy 候选仍是 `fixture/v1`。
