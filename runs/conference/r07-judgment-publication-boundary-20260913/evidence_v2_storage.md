I'll inspect the physical FK and scope checks on the existing review chain, then choose a storage approach that can actually publish V2 without faking a legacy snapshot.# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读。本题只定**正式审核的物理存储谱系**：现链双快照 vs 另开 V2 正式链。上下文修订必要但不够。不跑测试、不改产品模型。

### Evidence

**现正式链把资料身份钉在 legacy `evidence_snapshots`。**

| 表/合同 | 列 | FK |
|---|---|---|
| `ReviewRunRecord` `models.py:957-959` | `evidence_snapshot_id` NOT NULL | `evidence_snapshots` |
| `AssessmentCandidateRecord` `993-995` | 同上 | 同上 |
| `FinalAssessmentRecord` `1034-1036` | 同上 | 同上 |
| `ActionRequestRecord` `219-221` | 同上 | 同上 |
| `AgentCallRecord` `1146-1148` | 可空 | 同上 |
| 合同 `ReviewRun`/`AssessmentCandidate`/`FinalAssessment`/`ActionRequest` | `evidence_snapshot_id: str` 必填 | `review.py:154,181,204,255` |

仓储作用域同样只认 legacy：

- `_check_run_scope`：`episode.evidence_snapshot_id != run.evidence_snapshot_id`（`repositories.py:399-402`）
- `_check_assessment_scope`：`run.evidence_snapshot_id != assessment.evidence_snapshot_id`（438-441）
- `_check_action_scope`：run vs action 同一比较（464-465）
- `_check_agent_call_scope`：run vs call（492-496）
- `REVIEW_RUN_CONFIG` / candidate / assessment / action 镜像列都是该字段（1088-1170, 2158）
- `_action_columns` 写入 `payload["evidence_snapshot_id"]`（2058），V2 payload 若无此键会 KeyError

门控登记同样：`require_registered_review_scope` 要求 `agent_call.evidence_snapshot_id`，`registry.require("evidence_snapshot", …)`，并令 `episode.evidence_snapshot_id`、`review_run.evidence_snapshot_id`、V1 snapshot 三者相等（`scope.py:60-76,104-110`）。`publish_assessment` 用 `candidate.evidence_snapshot_id` 对 episode/agent_call（`assessment.py:127,491-492,582`）。

**V2 资料已经在另一张表。** `evidence_snapshots_v2`（`evidence_models.py:149-158`）。审核节点活动权威是 `active_evidence_snapshot_id` + `active_evidence_processing_revision_id`，FK 到 V2/修订，与 legacy 列成对可空（`models.py:126-166`；迁移 0010）。现场投影用 `FactAuthority.evidence_snapshot_v2_id`。判断检索摘要 FK 已是 V2（`judgment_search_models.py:25-26`）。

**事实/定位也是两套父表。** `final_assessment_facts` → `clinical_facts.fact_id`（`models.py:1406-1411`）；`final_assessment_spans` / `action_transition_spans` / `ActionRequest.trigger_evidence_span_id` → `evidence_spans`。V2 事实在 `clinical_facts_v2`。把 V2 id 写入这些关联会物理失败或伪造 legacy 行。

**`get_entry`（`judgment_search_repository.py:102-139`）** 按钉住的 `summary_id` 读，校验身份哈希与列镜像（含 `evidence_snapshot_id == authority.evidence_snapshot_v2_id`）。文档写明不重建作业回执。正式不得改调 `latest_for_authority`。

规范：不可原地覆盖 ReviewRun；不可删旧列；SQLite 重建被引用父表须保留子行并 `PRAGMA foreign_key_check`；类型判别须独立可空父 FK + CHECK，禁止无 FK 的 kind+id；禁止单一 overall 入排结论（`.trellis/spec/backend/database-guidelines.md` 10-40, 49-51）。`ReviewEpisode` 已用 omit-null 保住旧字节（`review.py:118-136`）。

### Inference

只改 `ReviewContextSnapshot` 无法 INSERT 任何 V2 `review_runs`/`final_assessments`/`action_requests`：NOT NULL legacy FK 仍在。把 V2 snapshot id 填进 `evidence_snapshot_id` 会指向错误父表或迫使插入假 `evidence_snapshots` 行，违反「不伪造 legacy 证据」。

另开 `review_runs_v2` / `final_assessments_v2` / `action_requests_v2` 会复制 Action 状态机、transition、rollup、历史读者，等于第二套正式链，也不是更小。

**应采用：现链上的版本化双谱系**（0010 节点指针的延伸）。同一 `review_runs` → `assessment_*` → `action_requests` → `action_transitions`。每行 **恰好一条** 资料谱系：legacy XOR V2。V2 行的 `evidence_snapshot_id` 为 NULL，**绝不**把 V2 id 写入该列。

这也迫使同一迁移族处理 `used_fact_ids` / locator：否则评估能建 run 却不能挂 V2 事实。不复制求值器；V2 发布的 `EvaluationContext.facts` 来自已发布 V2 事实头，不是 `clinical_facts` 占位表。

`ReviewRun.completed_at` 可在缺口仍在时写入。`EpisodeRollup.CURRENT_GAP` / `PROFESSIONAL_JUDGMENT`（`projections.py:19-34`）= **未决但已完成的审核**。入排批准不是本表上的单一 verdict。

### Recommendation

**选定：现审核链双快照（+双事实/定位关联）。不做平行 V2 正式链。不做上下文-only。**

**合同判别（`review.py`，schema_version 仍 `fixture/v1`）**

对 `ReviewRun`、`AssessmentCandidate`、`FinalAssessment`、`ActionRequest`、`AgentCallContract`（及随后的 `ReviewContextSnapshot` 消费引用）：

- 保留 `evidence_snapshot_id: str | None = None`（仅 legacy）
- 新增 `evidence_snapshot_v2_id`、`complete_processing_revision_id`，缺省 None
- `model_serializer` omit None（照 `ReviewEpisode` 118-136）
- 校验 XOR：legacy 非空且 V2 对空，或 legacy 空且 V2 对均非空；禁止两套都填
- 旧 JSON 仍含非空 `evidence_snapshot_id`、无新键 → dump 与指纹不变
- **禁止** 一个字段两种父表

V2 `FinalAssessment`：`used_fact_ids` 为 `clinical_facts_v2` id；定位用可省略 `locator_ids`，不要把 locator 写入 `evidence_span_ids`。旧行继续用 span。`ActionRequest.trigger_evidence_span_id` 旁加可空 `trigger_locator_id`，XOR。

**物理迁移（下一 Alembic，模板 `0010_evidence_locator_corrections.py`）**

重建被引用的 `review_runs`（及 candidate/assessment/action/agent_calls 若 SQLite 不能 in-place 把 NOT NULL 改为可空）：

1. `evidence_snapshot_id` 改为可空，FK 仍 `evidence_snapshots`（不删列）
2. `evidence_snapshot_v2_id` 可空 FK `evidence_snapshots_v2.evidence_snapshot_id`
3. `complete_processing_revision_id` 可空 FK `evidence_processing_revisions`
4. CHECK（节点成对指针的 XOR 版）：
   - legacy 行：`evidence_snapshot_id IS NOT NULL AND v2 id IS NULL AND revision IS NULL`
   - V2 行：`evidence_snapshot_id IS NULL AND v2 id IS NOT NULL AND revision IS NOT NULL`
5. 拷贝旧行：新列 NULL；子行保留；`PRAGMA foreign_key_check`
6. 新关联：`final_assessment_facts_v2(assessment_id, fact_id→clinical_facts_v2)`；`final_assessment_locators`；禁止把 V2 id 插入旧 `final_assessment_facts` / `final_assessment_spans`
7. 有真实业务行时禁止有损降级（0010 同文）

仓储（`repositories.py`，领域层零 SQLAlchemy）：

- `_check_run_scope`：legacy 比 `episode.evidence_snapshot_id`；V2 比 `episode.active_evidence_snapshot_id` **和** `active_evidence_processing_revision_id`。混谱系拒绝。
- assessment/action/agent_call：与 **run 的同一谱系** 比，不再假设 episode.legacy 非空
- CONFIG 镜像含新列；缺键当 NULL（与 omit 一致）
- `_action_columns` 用 `payload.get("evidence_snapshot_id")` 等
- `ActionRequestRepository.get` 镜像表同步

门控：`RegisteredReviewScope` 增加 V2 snapshot/revision（或按 run 谱系分支）。`registry.require("evidence_snapshot")` 只用于 legacy。V2 用已有 snapshot_v2 领域对象登记，不经 `evidence_snapshots` 表。`publish_assessment` 按候选谱系选 V1 证据候选或 V2 事实头；`derive_*` 不变。

正式上下文：钉住 `get_entry(summary_id, authority=…)` + job checkpoint `receipt_refs` + 当前 `prepare` 的 `scope_sha256`。发布路径禁止 `latest_for_authority`。entry 不是 PJ 证明。

**实现顺序（可做完）**

1. 合同 omit-null + XOR（`review.py`；agent_call 合同若独立则一并）
2. Alembic：run/candidate/assessment/action/agent_call 列 + CHECK + V2 事实/定位关联
3. ORM `models.py` 对齐
4. `_check_*_scope`、CONFIG、`_action_columns`、Action 仓储
5. `scope.py` + `assessment.py` 登记/比较
6. 然后才是上下文消费引用（前轮）；否则 V2 引用无处落库
7. 现场投影仍读活动 V2 指针；不改 ClausePack/布尔

**不要：** 新 JobRunner；复制 evaluator；V2 id 写入 `evidence_snapshots`；删 legacy 列；把 latest 摘要当冻结；谓词自动采信；用明确符合/入排批准填未决缺口。

**未决 vs 批准：** `completed_at` + rollup `CURRENT_GAP`/`PROFESSIONAL_JUDGMENT` + 开放 Action = 审核完成且未决。入排批准不是这些行上的字段；规范禁止单一 overall_verdict。

### Uncertainty

未打开生产库点行数；迁移是否绿地可重建 vs 必须追加，以当时是否已有真实审核行为准（规范 28-29）。`jobs.payload` 里判断检索 `receipt_refs` 键以执行器 checkpoint 为准，装配时对照读取。V2 评估是否仍要 V1 `EvidenceNormalizationCandidate` 行：正式 V2 应消费已发布事实头；该候选表不是 V2 事实父表。未跑测试。
