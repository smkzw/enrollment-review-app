I'll inspect the new isolated written-judgment module against the existing accepted visual/fact source contracts, and only then judge whether it can be integrated.The new module is a parallel contract, not a projection from accepted visual sources. I’ll check identity fields, scope claims, and whether absence can be proven without real dual-read receipts.# Conference Output: r3-judgment-review-scope-20260909 - evidence_single_object

## Output

同会话只读复核。未改代码、未跑模型、未读库/病例/其它工人报告。对象是隔离模块 `written_judgment_evidence` 与既有已采信视觉来源/投影，不是临床结论。

### 总判

该模块做的是**调用方声明的结构一致性**，不是读道/对账/覆盖的溯源认证。按现接口接入投影，可以在没有已采信手写、没有真实双读范围的情况下得到 `written_judgment_verified` 或 `absence_verified`。

抽象**过重，应先收薄再接线**。不要再增加一套平行来源本体。最小路径：从已有 `VisualHandwritingSource` + `SubjectPageCoverage` + `PageReviewRecord` 派生，而不是让集成者手填 `WrittenJudgmentPositiveReading` / `WrittenJudgmentPrimaryReadScope`。

---

### 结构校验 vs 仍缺的语义/溯源认证

| 本模块已做（结构） | 接入前仍缺（认证） |
|---|---|
| 双主读道、两份 `page_review_id`、`(provider, model)` 不同 | 这些字符串未绑到真实 `PageReviewRecord`（无 `response_sha256` / `prompt_version` / `reasoning_effort` / 条款包） |
| 同一页四元组、摘录字节一致、哈希自洽 | 摘录未证明来自该 receipt 的 `region.excerpt` 或已采信手写 |
| `context_known` 默认 False | 未要求 `ObservationContext.target_text`，布尔可手填 True |
| `source_form` 仅批注/节点病历分析 | 形式由调用方枚举，可把箭头、数值、文件类别包装成批注 |
| 缺席需两条显式 `no_written_judgment` + 范围集合相等 | `actual_page_scope` / `expected_page_scope` 都是调用方名单，可缩范围伪造“读全了” |
| 肯/否并存 → `unverified` | 未区分冲突手写 vs 未采信 vs 读失败（那些状态根本进不来，除非调用方再声明） |

模块自己也写了：存储侧来源真实性仍是集成者义务（`written_judgment_evidence.py:16-17`）。当前类型把这项义务变成了可伪造输入。

---

### 阻断接入的缺陷

#### P0 — 读道身份是自由字符串，不是视觉来源那种从记录拷贝的身份

**证据**

- 视觉来源从 `PageReviewRecord` 拷贝 `lane/page_review_id/provider/model/reasoning_effort/prompt_version/response_sha256`，并核对对账、覆盖已采信（`page_review_evidence_sources.py:529-560, 581-635`）。
- 书面判断读道只有 `page_review_id` + `provider` + `model`（`written_judgment_evidence.py:140-152, 227, 271-283`）。`evaluate_written_judgment_evidence` 不接收 `PageReviewRecord` / `PageReconciliation` / `PageVisualEvidenceSourceSet`。
- 测试用 `SimpleNamespace` 风格的合成 ID（`test_written_judgment_evidence.py:128-141, 194-210`），从不构造真实页审记录。兼容测试只断言版本号未改（`858-868`）。

**后果：** 任意两个不同 `(provider, model, page_review_id)` 即可“双读验证”。同页异图、过期条款包、未采信/冲突手写、辅助复核记录，结构上都过。

**下一步：** 禁止手填 Positive/Absence reading。从 `VisualHandwritingReading`（或 `PageReviewRecord` + `accepted_handwriting`）投影；身份字段必须等于记录上的值。缺席用同一对 `page_review_id` 对应的覆盖处置，不要新 receipt DTO。

#### P0 — 范围证明可伪造（适用页名单 + 实际已读名单均由调用方提供）

**证据**

- 请求的 `expected_page_scope` 是调用方元组（`299-319`）。
- 缺席范围 `actual_page_scope` + `scope_known` + `ownership_known` 也是调用方声明；`success` 且集合相等即 `ABSENCE_VERIFIED`（`382-415, 507-515`）。
- 失败/未知/子集有测试（`422-481`），**没有**测试“期望范围必须来自覆盖清单/模板适用页”。缩小 `expected_page_scope` 到已成功的一页，再配两条 `no_written_judgment`，即可证实缺席。

**后果：** 部分读、漏页、失败页只要不写进期望名单，就不存在。这正是“假范围证明”。

**下一步：** 期望范围只能从当前权威下的适用资料页推导（覆盖 `expected_page_artifact_ids` ∩ 该 `requirement_id` 的适用来源），不得另传。实际范围只能是 `SubjectPageCoverage.entries` 中 `ACCEPTED` 且 `reconciliation_id` 绑定输入对账的页。任一 `FAILED_PENDING_REREAD` / 缺对账 → 不得 `ABSENCE_VERIFIED`。

#### P0 — 对象/节点适用性是手填布尔和字符串，不是已有 context

**证据**

- 已有 `ObservationContext.target_text` 是“原文所指对象，不是推断”（`page_review.py:61-67`）。已采信手写把它编进 `normalization_key`。
- 本模块用独立的 `asserted_object` + `context_known`（`149-152, 171-172`）。默认未知（`300-309` 测试好），但 `context_known=True` 无需非空 `target_text`，也无需等于手写 context。
- `source_form` 与 `HandwritingKind` 无映射。`lab_arrow` 被拒（`777-783`），但数值事实摘录可标成 `report_annotation`。
- 投影仍用文件类别，且刻意不把 `investigator_assessment` 文件类型当判断（`evidence_expectation_projection_service.py:132-137`；`evidence_expectations.py:144-146`）。本模块也**没有**接到 `CoverageObservation`。

**后果：** 同页批注可被标到任意 `requirement_id`/`asserted_object`。箭头/文件类别禁令只存在于枚举上，输入层可绕过。

**下一步：** `asserted_object` 必须等于已采信手写 `context.target_text`（normalize 后）；无 context 或空对象 → 未核实，不是已验证。`requirement_id` 只能来自显式条款绑定（事实的 `supported_requirement_ids` 或同等确定性索引），禁止集成器猜绑。只允许 `HandwritingKind.cs_ncs_judgment` / `note`（及明确的节点病历分析手写）；禁止从 `PageFactObservation`（含箭头）生成肯定来源。

#### P1 — 同模型别名只比 `(provider, model)`，比视觉来源还弱

**证据**

- 两处都是 `{(provider, model)}`（`written_judgment_evidence.py:235-236, 361-362`；`page_review_evidence_sources.py:152-154, 529-532`）。
- 视觉来源至少落下 `reasoning_effort`/`prompt_version`/`response_sha256` 供事后审计。书面判断没有。
- 测试只打完全相同的 `provider-a/model-a`（`649-665`）。`model-a` vs `model-a`+不同 effort/endpoint/prompt 可通过。产品主读是 GLM/Gemini；同厂商 high/low 或 fallback URL 不会被拒绝。

**下一步：** 独立双读身份与页审记录对齐：`(provider, model, reasoning_effort, prompt_version, endpoint_base_url)`，并要求 `response_sha256` 不同。不要在本模块发明第三套身份。

#### P1 — 未知/冲突处理不完整，且会把“半套声明”当冲突或当通过

**证据**

- 任一 `written_judgment_seen ∧ context_known` 与任一 `no_written_judgment ∧ context_known` 即冲突（`476-503`）。单侧缺席也阻断肯定（`611-620`）——方向对。
- 同一 `PositiveSource` 一读 `seen`、一读 `unknown` → 不能 `verifying`，无缺席则 `unknown_context`（`276-297`）——方向对。
- 两个 PositiveSource：一个双读 `seen`，另一个 `unknown`：`verifying` 非空则 **VERIFIED**，忽略未知兄源（`485-506`）。
- 缺席 `outcome=unknown` 且 `context_known=True`：不算 `absence_claim`，也不算 `explicit_absence`；若同时有完整肯定源 → **VERIFIED**。未知缺席被丢掉。
- 缺席读没有摘录/页。无法表达“本页未见”vs“整范围未见”，范围全靠平行 DTO。

**下一步：** 评价函数只吃已物化来源 + 覆盖，不要平行的 seen/unknown 枚举。未知 = 该对象无已采信手写且覆盖未全成功。冲突 = 已采信手写存在 vs 其它读声称缺席，或手写对账冲突。不要让调用方同时塞肯定源和缺席声明。

#### P1 — 与生产投影不兼容；`ABSENCE_VERIFIED` 也不是“非阻断可报告缺口”

**证据**

- `EvidenceExpectationProjectionService` 不 import 本模块。覆盖仍看已发布事实 + 文件类型。
- `GapType.PROFESSIONAL_JUDGMENT` 的行动是研究者补写判断（`policies.py:108-112`）；`derive_expectation_blocking_level` 对非 `PROVENANCE_FOLLOWUP` 的弱/缺失一律 `BLOCKING`（`254-264`）。本模块结论没有 blocking 字段；若把 `absence_verified` 直接映射成 `PROFESSIONAL_JUDGMENT`，会变成阻断缺口，违反“非阻断可报告”。
- 肯定结论 `written_judgment_verified` 也不是 `CoverageObservation`，进不了 `_matching_observations`（仍要 `supported_requirement_ids`）。

**下一步：** 接线表只能是：

- `VERIFIED` → 已发布 `fact_type=investigator_assessment`（或等价）且 `supported_requirement_ids` 含该要求，**来源类型来自手写视觉来源而非文件类别**；或给 `CoverageObservation` 增加非文件类别的判断来源标记（最小补丁，不要新投影器）。
- `ABSENCE_VERIFIED` → `CoverageGapSignal(kind=PROFESSIONAL_JUDGMENT)` 且政策上 **ATTENTION/非阻断**（需改 `derive_expectation_blocking_level`，否则与准则冲突）。
- 其它 → 现有 `OBSERVATION_UNVERIFIED`，禁止升格为 PJ。

#### P2 — 兼容性测试是假保证

`test_existing_source_schemas_are_unchanged` 只比较三个版本字符串并 `PageReviewRecord.model_validate(_review_payload())`。它不证明书面判断类型能由 `VisualHandwritingSource` 构造，也不证明投影仍拒绝文件类别冒充判断。

---

### 现有抽象是否值得保留

**不值得按现状接入。** 约 10 个模型重复了视觉来源已有的页身份、双读、摘录哈希，但绑得更松。

可保留的薄层：

- 三态 `written_judgment_verified | absence_verified | unverified` 及原因码（冲突/范围未知/读失败）。
- 规则：无对象不成判断；部分/失败/未知/冲突不成缺席；文件类别与箭头不是判断。

应删或改为内部实现细节：

- `WrittenJudgmentPageRef` / `WrittenJudgmentLocator`（用页审/视觉定位的页四元组 + `VisualPageExcerptLocator`）
- `WrittenJudgmentPositiveReading` / `AbsenceReading` / `PrimaryReadScope`（从记录派生）
- 调用方填写的 `source_form`（从 `HandwritingKind` + 是否节点病历分析资料推导，推导不出则未核实）

`written_judgment_source_id` 若保留，应哈希 **视觉手写 source_id + requirement_id + asserted_object + episode**，不要哈希一套平行 readings。

---

### 最小完整接线（只用现有已采信合同）

不要新框架。建议单函数，例如 `judgment_signals_from_accepted_sources(...)`，输入：

1. `FactAuthority` + 该要求的 `requirement_id` / `asserted_object` / `workflow_stage_id`
2. 适用页：覆盖的预期页 ∩ 该要求适用来源（不是文件类别=`investigator_assessment`）
3. 每页 `PageVisualEvidenceSourceSet`（或临时：`reviews` + `reconciliation` + `coverage`，即 `materialize_page_visual_evidence_sources` 的输入）
4. 已发布事实（可选），仅当其 locator 指向上述手写视觉来源且 `fact_type`/`supported_requirement_ids` 已绑定

算法：

1. 肯定：已采信手写，`context.target_text` 对应该对象，双读身份独立（记录级），摘录非空。→ 覆盖观察 / 可发布判断事实。同页其它批注不传播。
2. 缺席：适用页全部 `ACCEPTED`、两主读记录均在、无该对象已采信手写、无该对象未核实/冲突手写。→ 非阻断 `professional_judgment` 信号。
3. 否则：`observation_unverified`（失败页、范围不等、未知对象、冲突、单源）。

先写这个投影函数的合成测试（用 `_review_payload` / 已有 visual source 夹具），再考虑是否保留 `evaluate_written_judgment_evidence` 当内部实现。

---

### 按文件的具体动作

| 文件 | 动作 |
|---|---|
| `app/domain/written_judgment_evidence.py` | 不要接线。要么删平行 DTO，要么改成只接受 `VisualHandwritingSource`+`SubjectPageCoverage` 的纯函数。 |
| `app/domain/page_review_evidence_sources.py` | 保持物化器为肯定判断的唯一已采信入口；不在此做条款判定。 |
| `app/services/evidence_expectation_projection_service.py` | `_observations` 继续拒绝文件类别冒充判断；判断覆盖来自手写视觉来源绑定的事实，或显式判断观察，不来自本模块手填源。 |
| `app/projections/evidence_expectations.py` / `app/domain/policies.py` | 仅在缺席已认证后允许 PJ；该 gap 改为非阻断；未核实不得变 PJ。 |
| `tests/v2/domain/test_written_judgment_evidence.py` | 现测试锁的是声明一致性，不能当接入门槛。补：无 `PageReviewRecord` 则失败；缩范围不能证实缺席；`context_known` 无 `target_text` 则失败；箭头事实不能当判断。 |

---

### 类别

- **证据：** 上述行号与测试夹具形态。模块标明未集成。
- **推断：** 若按当前签名接入 `_expectation_gap_signals` / `project_expectation`，缺席可被缩范围伪造，肯定可被未采信摘录伪造。
- **建议：** 从已采信视觉手写 + 覆盖闭包投影；收薄本模块。
- **不确定：** 适用页如何从模板/资料类型（非 `investigator_assessment` 文件名）确定性算出——那是接线时的产品输入，本模块没有提供。`ABSENCE_VERIFIED` 与现政策 `BLOCKING` 的冲突需 Codex 改政策，不是改枚举名能解决。

未做临床验收，未声称运行时行为。
