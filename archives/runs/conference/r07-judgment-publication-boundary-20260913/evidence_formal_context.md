I'll inspect the formal snapshot, publication gates, and the new latest-summary accessor, then pin a minimal consumption plan without reopening source-type applicability.# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读。本题只钉**正式上下文如何消费 V2 期望 + 检索回执**，不重复 source-type 适用性，不改已发布布尔/ClausePack，不跑测试。

### Evidence

**正式入口仍是 V1 快照，现场不是。**

- `ReviewContextSnapshot`（`context.py:10-18`）字段是 `list[EvidenceExpectation]`（fixture/v1）。`context_sha256` 对 `model_dump` 除自身外的全部键做内容寻址（22-32）。
- `build_review_context_snapshot`（`assessment.py:67-76`）只收 V1 期望。夹具重放同样（`integrity.py:99-106`）。
- `publish_assessment` 取 `review_context.expectations`（`assessment.py:501-502`）送进 `derive_gate_gap_types`（593-598）。注册表实体名是 `review_context`（478），不是 V2 期望仓储。
- `RequirementGapState` 文档写明「计算视图，不是发布证明」（`assessment.py:42-48`）。现场 `_expectation_views` 用它把 V2 转成门控输入（`eligibility_review_projection.py:269-278`），**从未写入快照**。
- 现场 `project()`：`current_fact_heads` + `_latest_expectations` + `latest_for_authority`，再 `derive_gate_gap_types` 后 **`gaps.update(_summary_gaps(...))`**（648-730）。摘要仍二次并入。正式路径没有这一步。

因此：现场能画 V2/PJ，不能据此声称正式发布已接受 V2。

**V1/V2 错位是结构错位，不只期望。**

| 层 | 现场 | 正式门控 |
|---|---|---|
| 资料版本 | `FactAuthority.evidence_snapshot_v2_id` + `complete_processing_revision_id`（`facts.py:101-109`） | `ReviewEpisode.evidence_snapshot_id` 为 Phase2/3 legacy，活动权威是 `active_*` 指针（`review.py:87-96,109-114`）；`ReviewRun.evidence_snapshot_id` 仍是单字符串（149-154） |
| 事实 | V2 链头经 `adapt_clinical_facts_v2` | `evidence_candidate.clinical_fact_candidates`（V1，`assessment.py:576-588`） |
| 期望 | `EvidenceExpectationV2`（`schema_version=phase5/v1`，可带 PJ） | 内嵌 V1；`ABSENT` 不能带 `professional_judgment` |
| 检索 | 仓储最新摘要 | 快照无检索字段 |

`ReviewEpisode` 已用 omit-null 序列化保住旧哈希（`review.py:118-136`）。上下文合同没有同等 omit，**不能**直接加带默认值的新键：`model_dump` 会带上 `"consumption": null`，旧 `context_sha256` 会在重算时失败。

**可复用的既有存储/门控（不要第二套 JobRunner）：**

- 期望：`EvidenceExpectationV2Repository.get` / `list_for_authority`；行上 `payload_json`+`payload_sha256`（`evidence_expectation_repository.py:184-193,255-260,268-284`）。
- 检索摘要：`JudgmentSearchSummaryRepository.save_summary` / `get_summary` / **`latest_entries_for_authority`**（`judgment_search_repository.py:42-48,62-154`）。Entry 含 `summary_id`/`job_id`/`payload_sha256`/`summary`，注释写明不是临床缺失或适用性证明。
- 回执：既有 `ArtifactStore` `raw_response`；`save/load_judgment_search_receipt`（`judgment_search_artifacts.py:1-28`）。作业 `_summary_step` 已对每个 requirement 再跑 `prepare_judgment_search_target`，scope/target 漂移则 `JUDGMENT_SEARCH_SCOPE_CHANGED`，再 `assemble_judgment_search_coverage` 后 `save_summary(..., job_id=context.job_id)`（`judgment_search_job_executor.py:193-245`）。
- 权威：`FactAuthorityValidator`（执行器 `apply` 已调用）。
- 求值/缺口：现有 `evaluate_component` + `derive_gate_gap_types` + `derive_component_decision` + `publish_assessment`。T1/T5 要求实时与正式共用这一套（计划 T1 条 2、T5 条 1），不要新编排器。
- 登记：`require_registered_review_scope`（`scope.py:45-76`）冻结 project/protocol/rule_set/subject/episode/snapshot/run。

**`latest_entries_for_authority` 正确性（算法与原先 latest 相同，外加 entry）：**

SQL 过滤：`review_episode_id` + `evidence_processing_revision_id` + `rule_set_id` + `rule_set_revision`，可选 `job_id`；按 `requirement_id, created_at, summary_id` 排序后每要求留最后一行（120-154）。身份再用调用方**完整** `FactAuthority` 重算 `_summary_identity`（含 project/subject/`episode_revision`/protocol/`evidence_snapshot_v2_id`），v1（无 job）与 v2（有 job）两种 ID 都认（51-55,143-147）。不匹配则 `continue`，不抛错。

缺口（用作冻结引用之前必须正视）：

1. **未传 `job_id` 时跨作业取最新**——现场 `latest_for_authority(authority)` 如此。正式若在发布时再调 latest，后到作业会换掉摘要。冻结必须钉 `summary_id`（及当时的 `job_id`），不能钉「再查一次 latest」。
2. **身份失败静默跳过**——错绑行看起来像「该要求无摘要」→ OU，而不是装配失败。正式装配应对「SQL 命中但 identity 失败」拒绝，或至少与「无行」区分。
3. **SQL 未过滤 `subject_id`/`evidence_snapshot_id` 列/`episode_revision`**——靠哈希丢掉；列镜像不完整。
4. **不重算当前 `prepare_judgment_search_target`**——accessor 不证明 scope 仍等于当前供给域。执行器在**写入当时**证明过；读时必须再比 `summary.scope_sha256`（或从作业 checkpoint 的 frozen scope + 当前 prepare）。
5. **不验证 job 存在、类型、完成、权威**——`job_id` 只是字符串。名字不构成核验。
6. **摘要合同恒 `source_scope_verified=False` / `professional_judgment_absence_proven=False`**——entry 不能升级这些字面量。

### Inference

最小闭合是：**给快照加可省略的消费引用（身份+哈希），发布时重载并重验，再生成计算用 `RequirementGapState`。** 不要把 V2 正文、页图、逐页回执复制进每个组件快照；不要全局缓存。

旧 fixture/V1 路径保持：`consumption is None` 时行为与现在完全一致（含 V1 校验）。新正式审核节点在装配时写入 `consumption`。

不能称为书面判断证明的：摘要 status、entry、`RequirementGapState`、未重验的 latest。P2 只是「该要求在钉住的 job/scope 上双读供给页无候选，且同要求不是缺文件、不是 OBSERVED」。

未决项合法：`INDETERMINATE` / `PROFESSIONAL_JUDGMENT` / 未核实缺口 + 开放 Action；T5 写明完成链含未决报告。不要为凑明确入排结论发明绑定或阳性判断。

谓词级「已核实判断解除无法判定」仍等 §17.1.1 隔离评测与用户接入；本切片只按**要求级** V2 状态消费（OBSERVED 则该要求不报缺失；摘要不得盖过）。

### Recommendation

**1. 合同（`app/domain/contracts/context.py`）**

仿 `ReviewEpisode._serialize_omit_null_pointers`：

```python
class ExpectationConsumptionRef(ContractModel):
    expectation_id: str
    template_id: str
    requirement_id: str
    revision: int
    payload_sha256: str  # 行 payload_sha256

class SearchConsumptionRef(ContractModel):
    requirement_id: str
    summary_id: str
    job_id: str
    payload_sha256: str
    scope_sha256: str
    receipt_storage_refs: tuple[str, ...] = ()  # 作业 checkpoint 的 storage_ref，不是页字节

class ReviewContextConsumption(ContractModel):
    authority: FactAuthority
    expectation_refs: tuple[ExpectationConsumptionRef, ...]
    search_refs: tuple[SearchConsumptionRef, ...]

# ReviewContextSnapshot 增加：
consumption: ReviewContextConsumption | None = None
```

`model_serializer`：`consumption is None` 时 `pop("consumption")`。旧字节/哈希不变。`extra=forbid` 仍拒绝未知键。不要改 `schema_version`（仍 `fixture/v1`），以免所有旧夹具 schema 断言无故失败。

**2. 装配（现仓储，无新表/无新 JobRunner）**

```python
# app/domain/gates/assessment.py 或紧邻 app/services/review_context_consumption.py

def assemble_review_context_consumption(
    session,
    authority: FactAuthority,
    *,
    search_job_id: str | None,
) -> ReviewContextConsumption: ...

def load_requirement_gap_states(
    session,
    consumption: ReviewContextConsumption,
) -> list[RequirementGapState]: ...
```

装配顺序：

1. `FactAuthorityValidator(session).validate(authority)`。
2. `EvidenceExpectationV2Repository.list_for_authority(authority)` → 每模板最新 revision；记录 `expectation_id/template_id/requirement_id/revision/payload_sha256`。权威字段必须 `== authority`。
3. 检索：正式必须传入**该审核运行钉住的** `search_job_id`。`latest_entries_for_authority(authority, job_id=search_job_id)`。无作业则 `search_refs=()`（全部判断要求保持未检索=OU，不报 PJ）。
4. 对每条 entry：`summary_id` 必须等于 `_summary_identity(authority, payload, job_id=job_id)`（不允许再靠 v1 无 job 身份混入正式钉住集）；`payload_sha256` 等于行；`prepare_judgment_search_target(session, authority, requirement_id)` 的 `scope.scope_sha256` 必须等于 `summary.scope_sha256`，否则拒绝装配（与执行器 SCOPE_CHANGED 同类，不静默当无摘要）。
5. `receipt_storage_refs` 从该 `job_id` 的 summary/read checkpoint 拷贝引用；不把 raw JSON 嵌进上下文。
6. SQL 命中但 identity 失败 → 装配错误，不当成「未检索」。

**3. 统一缺口（现场与正式同一函数）**

`load_requirement_gap_states`：按 `requirement_id` 取 V2。缺文件（`REFERENCED_FILE_MISSING`）保留。`OBSERVED`/`OBSERVED_WEAK` 用期望 gap（或无阻断缺口）。仅当该要求有 `search_ref` 且期望不是 OBSERVED、也不是缺文件时，才把摘要态映到 OU/PJ（与现期望生产者规则一致：不完整/候选/无摘要=OU；`ALL_SUPPLIED…`=PJ）。

然后 **只**把该 `list[RequirementGapState]` 交给 `derive_gate_gap_types`。现场删除 `gaps.update(_summary_gaps)`（730 行附近），否则正式钉住的期望仍会被「再 latest 一次的摘要」覆盖。`_summary_gaps` 可留作单测/对照，不再是产品并集。

求值器 `professional_judgment_unverified` 仍可进入组件缺口；不要组件级丢掉 OU。本切片不做谓词归属证明。

**4. 发布**

`build_review_context_snapshot(..., consumption=None)`。`publish_assessment`：若 `review_context.consumption` 非空，按 refs `get()` 重载 V2/摘要，重比哈希与当前 `prepare` 的 scope；失败则拒发。用 `load_requirement_gap_states` 替代 V1 `expectations` 做 `derive_gate_gap_types`。`input_payload` 增加 `consumption` 的 dump（身份+哈希），以便 gate `input_scope_hash` 钉住引用而非页数据。

`consumption is None`：现 V1 行为，夹具继续。

不把 V2 登记进现有 `evidence_expectations` 注册表键（那是 V1）。消费时按 ref 读 V2 仓储即可。

**5. 未决与缺失**

- 无检索作业 / 覆盖不全 / 有候选：OU，审核可完成，Action 开着。
- 钉住的供给域双读无候选 + 非缺文件 + 非 OBSERVED：PJ + 研究者补充；不暂停、不要求用户确认缺失、不编造成立/排除。
- 同要求缺文件：只报缺文件。
- 禁止用摘要发明阳性判断或未核实谓词绑定。

**6. 实现顺序（所有者可做完的切片）**

1. `context.py` 引用类型 + omit 序列化；`build_review_context_snapshot` 透传。  
2. `assemble_review_context_consumption` + `load_requirement_gap_states`。  
3. 现场 `project()` 改走 2，去掉摘要二次并集。  
4. `publish_assessment` 的 consumption 分支。  
5. T5 以后：创建 `ReviewRun` 时写入当时的 `consumption`（含 `search_job_id`）；发布不得再调无 job 的 latest。本切片不必新作业类型。

**现在不要做：** 改 V1 `EvidenceExpectation` 接受集；把 V2 塞进 V1 列表；用 `fact_type` 当谓词证明；改 ClausePack/`requires_professional_judgment`；回写历史夹具；新 JobRunner；把 latest entry 当作 PJ 证明；谓词级自动采信（仍等隔离评测+用户接入）。

事实层正式仍用 `evidence_candidate`（V1）。期望/检索消费对齐不冒充 T1 绑定已完成。

### Uncertainty

未读 `jobs` 表里判断检索 payload 的完整 JSON 键集；`receipt_storage_refs` 以 executor checkpoint `receipt_refs[].storage_ref` 为准，装配时应对着读而不是猜。生产库无正式 ReviewRun 实例（计划 Phase6）。`list_by_episode` 全表扫描再过滤（286-298）不是本切片要修的范围，但正式装配应优先 `list_for_authority`。未跑测试、未做视觉验收。
