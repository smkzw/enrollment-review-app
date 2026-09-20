I'll start with the assigned conference context and plan, then audit the listed protocol-deconstructor files against the source-span constraints.The conference packet is thin, so I’ll inspect the four assigned sources next and map how `source_span_ids` are generated versus validated.I'll search the deconstructor, contracts, and review artifact for `source_span_ids` generation, validation, and cache-identity handling.The generation and validation paths are concentrated in a few deconstructor functions; I’ll read those next, plus the input contract and cache-identity handling.I’ve got the generation-schema shape; next I’ll check post-parse validation, cache keys, and whether nested observation-policy IDs are actually constrained.I have enough sourced evidence to write the independent review: generation enums, post-parse closure, cache keys, and the frozen IN-01 body.

# Conference Output: acceptance-source-scope-20260916 - evidence_single_object

## Output

只读独立审核。不构成临床/监管/全方案签收，也不构成 Codex 终审。未读 `reasoning_content`，未调用产品模型，未改源代码。

补充只读（任务四文件不足以闭合 provider schema 落地与缓存身份）：`app/agents/protocol_semantic_transport.py:340-426`（`configure_output_scope` / `semantic_cache_identity` / `response_format`）、`app/protocols/deconstruction_gate.py:1266-1286,2845-2880,3374-3416,3501-3518`（后期来源门）、`tests/v2/protocols/test_deconstruction_gate_slice3.py:152-251`（测试夹具中父规则 vs 流程来源）、`tests/v2/agents/test_protocol_semantic_model_routing.py:549-595`（缓存键测试未传 `source_input`）。

---

### Evidence（观察）

**1. 组件级 `source_span_ids` 有枚举；嵌套来源字段没有**

`_semantic_generation_schema` 仅给 `$defs.SemanticRuleComponent.properties.source_span_ids.items` 写入 `enum`：

```536:553:app/agents/protocol_deconstructor.py
def _semantic_generation_schema(
    model, allowed_source_span_ids: Sequence[str] = ()
) -> dict[str, object]:
    ...
    if allowed_source_span_ids:
        source_ids = schema["$defs"]["SemanticRuleComponent"]["properties"]["source_span_ids"]
        source_ids["items"]["enum"] = list(allowed_source_span_ids)
    return schema
```

实测（本工作树 `.venv`，`allowed=["snap::p1","snap::p2"]`）：

| Schema | `SemanticRuleComponent.source_span_ids` | `ObservationPolicy.source_span_ids` | `RepeatScheme.source_span_ids` | `HalfLifeEvidence.source_span_id` | `UnresolvedItem.source_refs` |
|---|---|---|---|---|---|
| `_compact_schema` / `_compact_repair_schema` | 有 enum | 无 | 无 | 无 | 无 |
| `protocol_output_response_format(..., compact=False)` candidate/repair | 有 enum | 无 | 无 | 无 | 无 |
| `protocol_output_response_format(..., compact=True)` | 组件 `source_span_ids` 有 enum | 无（`items.type=string`） | 无 | `minLength:1` only | **有** enum（`structural_warnings` / `unresolved_items`） |

Compact wire 的 enum 只出现三处：`proposed_rules.components.source_span_ids`、`structural_warnings.source_refs`、`unresolved_items.source_refs`。`_wire_observation_policy_schema` 直接用 `ObservationPolicy.model_json_schema()`，不注入 allowed 列表（`protocol_deconstructor.py:724-732`）。`half_life_evidence.source_span_id` 为任意非空字符串（`:628-639`）。

**2. 实际来源校验与生成约束不对齐**

`_validate_batch_source_closure` 只并集「组件 `source_span_ids` + warning/unresolved 的 `source_refs`」，再减去本批父规则所有权闭包：

```3586:3614:app/agents/protocol_deconstructor.py
component_source_ids = {
    source_span_id
    for rule in rules
    for component in rule.components
    for source_span_id in component.source_span_ids
}
issue_source_ids = { ... item.source_refs ... }
invalid_source_ids = (component_source_ids | issue_source_ids) - selected_source_ids
```

不检查 `observation_policy.source_span_ids`、`repeat_scheme.source_span_ids`、`half_life_evidence.source_span_id`。

Wire 解析层对观察政策做了「必须 ⊆ 本组件 `source_span_ids`」检查（`:2640-2665`），非 compact / Pydantic 路径没有同等检查。后期门 `deconstruction_gate.py:3374-3416` 才把观察政策/复查/半衰期来源对到组件 `source_refs`；`COMPONENT_SOURCE_OUTSIDE_PARENT`（`:3501-3518`）只看组件 `source_refs`，不看嵌套字段。门不核对 `observation_policy.scope` 正文是否被摘录支撑。

**3. 首批 / 后续 / 结构纠错 / 局部修订的 allowed 列表来源**

- 所有权函数 `_batch_source_span_ids`（`:1310-1341`）：按选定父规则 catalog 条目的 `source_span_ids` 与 `allowed_source_span_ids` 求交，显式丢掉流程-only / 无主 span。测试 `test_structure_and_semantic_repairs_preserve_selected_source_scope` 断言 `set(allowed) < set(source.allowed_source_span_ids)`（`test_protocol_source_policy_generation.py:44-46`），夹具中多出的是 `span-proc-screen` / `span-proc-base`（`test_deconstruction_gate_slice3.py:171-189,232`）。
- 首批与后续生产路径都走 `scoped_source=True` → `_batch_prompt_payload`（`:1518-1519,4676,4805`）。payload 含 `allowed_source_span_ids`、父规则目录、`source_materials`，**不含** `required_procedure_catalog`（`:1449-1486`）。
- 非 compact 首批/后续提示嵌入 `_compact_schema(payload['allowed_source_span_ids'])`（`:1556`）。
- 后续 `_next_batch_prompt` 在传入 `source_input` 时会重建 scoped schema；`source_input is None` 的回退分支使用无 enum 的 `_compact_schema()`（`:1609-1614`）。生产收集循环传入 `source_input`（`:4803`）。
- 结构纠错 `_batch_schema_repair_prompt`：非 compact 嵌入 `_compact_schema(allowed_source_span_ids)`（`:1650`）；compact 只写 wire 文字、不嵌入 enum，依赖此前 `_configure_transport_output_scope`（`:4757-4766,4126-4166`）。
- 运行器局部修订：会 `configure_output_scope`（`:5232-5239`）；非 compact 提示用 `_compact_repair_schema(_batch_source_span_ids(...))`（`:1716-1718`）。但 `_validate_semantic_repair(..., source_input=source_input if compact else None)`（`:5043-5048` 与反馈路径 `:3477-3482`）——**非 compact 局部修订不做来源闭包校验**。
- `revise_protocol_draft_from_feedback` **不调用** `_configure_transport_output_scope`（`:3380-3466`）。Compact 传输若 `_output_scope=={}`，`protocol_output_response_format` 得到空 `allowed_source_span_ids`，provider schema 无 enum（`protocol_semantic_transport.py:351-353,422-426`）。

**4. 缓存身份**

`_semantic_batch_cache_key` 设计了可选 `source_input`（写入 `protocol_file_sha256`、`extraction_snapshot_id`）和 `prompt_template`（写入 `prompt_template_sha256`）（`:4232-4265`）。

| 调用点 | 是否传 `source_input` / `prompt_template` |
|---|---|
| 父规则分段 `:4345-4353`、重试 `:4405-4412` | 传 |
| 首批 `:4678-4684` | **不传** |
| 后续批 `:4807-4813` | **不传** |

`semantic_cache_identity` 哈希的是 `_completion_kwargs` 的 `response_format`（`protocol_semantic_transport.py:360-387`）。本地 structured 后端会把 `_output_scope`（含 allowed enum）编进 schema；`json_object` 后端（DeepSeek/GLM 等）`response_format` 仅为 `{"type":"json_object"}`，**请求合同里没有来源枚举**。此时首批/后续缓存身份只靠完整 prompt 字符串间接带上冻结输入。`test_semantic_cache_identity_and_batch_keys_do_not_reuse_across_models` 同样不传 `source_input`（`:582-587`）。

**5. 指定测试未覆盖上述缺口**

`tests/v2/agents/test_protocol_source_policy_generation.py`：

- 只断言 `SemanticRuleComponent.source_span_ids` 的 enum（`:22-36`）。
- `protocol_output_response_format(kind, allowed_source_span_ids=allowed)` 未传 `compact=True`（`:27`），测的不是生产 compact wire。
- 结构/语义修复测试只解析提示里的 `_compact_schema` / `_compact_repair_schema`（`:39-58`），不测 `_next_batch_prompt` 无输入回退、不测 compact 结构纠错、不测缓存键、不测嵌套字段。
- 来源政策测试覆盖的是 `allows_screening_record_transcription` / `requires_contemporaneous_objective_source` 必须显式出现（`:61-116`）。Wire 解析仍对缺省字段回填历史默认值 `True`/`False`（`:2714-2718`）。

**6. 冻结原文 vs 单条模型正文（artifact）**

冻结原文仅一句（`artifacts/acceptance-20260916/source-scope-review-input.json:38-46`）：

> 年龄18~75周岁（包括边界值），男女不限；

`allowed_source_span_ids` / catalog / material 均为 `7a8d2d702f864e689566cd1490c2294e-snapshot::body.p548`。payload 无 `required_procedure_catalog`。未读 reasoning。

模型正文有来源支撑的部分：

- 年龄 18–75（含边界）拆成 `gte 18` / `lte 75`，单位「周岁」，`source_clauses` 为「年龄18~75周岁（包括边界值）」；组件 `source_excerpts` 与冻结句逐字一致（`:57-139`）。
- 未把「男女不限」做成性别原子，符合系统合同 `:343-344`。

无冻结原文支撑、被写成资料义务/时点/政策的部分：

| 字段 | 模型正文 | 冻结原文 |
|---|---|---|
| `due_stage` | `"screening"`（`:120`） | 无「筛选/基线/随机/知情」 |
| `required_source_types` | `["identity_document"]`（`:124-126`） | 无身份证件 |
| `description` | 收集出生日期（身份证明或筛选访视誊写），计算筛选时年龄（`:121`） | 无出生日期、无访视誊写、无筛选时点 |
| `allows_screening_record_transcription` | `true`（`:122`） | 无誊写许可 |
| `requires_contemporaneous_objective_source` | `false`（`:123`） | 无来源政策 |
| `observation_policy.scope` | 「资格审核时……（按出生日期计算）」（`:77,103`） | 无资格审核时点、无出生日期算法 |

观察政策 `source_span_ids` 与摘录「年龄18~75周岁（包括边界值）」身份合法，但 `scope` 正文超出摘录。系统合同要求来源政策不可确认时保留未解决项、不猜测（`:250-253`），`due_stage` 须依据条款逐字时点或冻结流程（`:370-376`）。本批提示未给出冻结流程。

**7. 读模型与领域合同默认值**

`SemanticEvidenceRequirement` 读侧默认 `allows_screening_record_transcription=True`、`requires_contemporaneous_objective_source=False`（`agent_io.py:118-119`）；仅当 `predicate_ids` 非空时强制显式填写（`:132-141`）。生成 schema 去掉 default 并加入 required（`protocol_deconstructor.py:542-549`）。历史无关联记录仍可读（测试 `:90-97`）。

---

### Inference（推论）

1. **组件级 identity 与「本批父规则所有权」大体一致，不是把合法父规则 span 误踢出 enum。** `_batch_source_span_ids` 丢掉的是流程-only span；后期门 `COMPONENT_SOURCE_OUTSIDE_PARENT` 也不允许组件引用父规则目录之外的 span。把流程 span 放进组件 enum 会与门冲突。未见本 artifact 误排父规则自有 span。

2. **真正的生成/校验不一致在嵌套来源字段和非 compact 修订闭包。** 生成合同只锁组件 ID；模型仍可在 `observation_policy` / `repeat_scheme` / `half_life_evidence` 写入任意字符串。Compact wire 解析会拦「观察政策 ID ⊄ 组件 ID」；非 compact 要等到 gate。非 compact 局部修订连 `_validate_batch_source_closure` 都跳过，外来组件 ID 只能靠后续 hydrate/gate。反馈修订 compact 路径若未 `configure_output_scope`，provider 端甚至不会枚举本批 ID。

3. **「误排合法来源」更准确的落点是 due_stage 的冻结流程，而不是组件 span enum。** 系统合同允许用冻结必做项目确定 `due_stage`，但 scoped 首批/后续 payload 不发送 `required_procedure_catalog`，又不把流程 span 列入可引用 enum。模型无法引用合法流程来源，只能猜测 `screening`。IN-01 单句没有时点，正确合同行为应是未解决项或仅在提示中只读展示流程目录（且仍禁止写入组件 `source_span_ids`）。

4. **缓存身份遗漏是调用点遗漏，不是函数未实现。** 分段路径已证明 `source_input`+`prompt_template` 是一等身份字段；首批/后续故意不传。当前 prompt 全文仍含 `protocol_file_sha256` 等，**今日不一定造成跨方案误命中**；`json_object` 后端没有 schema 侧二次绑定，prompt 一旦精简或复用模板，键会静默丢失方案身份。这与分段路径不对称，属于可被利用的身份缺口。

5. **IN-01 模型正文的年龄阈值有来源；筛选时点、身份证明、出生日期、誊写许可是增造的资料义务/时点/政策。** 不能用「年龄当然要算周岁」做临床签收。合同明文禁止在来源政策不明时猜测。

---

### Recommendation（最小通用修复，不代写代码）

按严重度：

1. **高 — 嵌套来源 ID 与组件 ID 使用同一 allowed 列表（或 ⊆ 该组件 `source_span_ids`）**  
   证据：`protocol_deconstructor.py:550-552`、`:724-732`、`:628-639`、`:3586-3614`；compact wire 实测 enum 仅 3 处。  
   最小修复：`_semantic_generation_schema` 同时给 `ObservationPolicy` / `RepeatScheme` / `HalfLifeEvidence` / `UnresolvedItem.source_refs` 写 enum；`_omlx_wire_schema` 把同一 enum 传入 observation/repeat/half_life；`_validate_batch_source_closure` 递归收集这些字段。测试需覆盖 `compact=True` 与非法嵌套 ID。

2. **高 — 非 compact 局部修订与反馈修订的校验/provider 范围与 compact 对齐**  
   证据：`:5043-5048`、`:3477-3482`、`:3380-3466` 无 `configure_output_scope`。  
   最小修复：`_validate_semantic_repair` 只要有 `source_input` 就做闭包校验，不要用 `if compact`；反馈修订在 `transport.start` 前对目标父规则调用 `_configure_transport_output_scope`。

3. **高 — 首批/后续缓存键补上与分段路径相同的方案身份字段**  
   证据：`:4232-4265` vs `:4678-4684`、`:4807-4813` vs `:4345-4353`。  
   最小修复：两处 `_semantic_batch_cache_key(...)` 传入 `source_input=` 与 `prompt_template=`；测试断言缺 `protocol_file_sha256`/`extraction_snapshot_id` 时键变化。不要只依赖 prompt 字符串。

4. **中 — scoped 提示只读提供冻结流程，或禁止无逐字时点时填写 `due_stage`**  
   证据：`:1449-1486` 无 procedure catalog；系统合同 `:370-376`；artifact `:120-126`。  
   最小修复（二选一，不要把流程 span 放进组件 enum）：(a) `_batch_prompt_payload` 增加只读 `required_procedure_catalog` 供 due_stage 对照，并写明不得写入组件 `source_span_ids`；(b) 条款无审核时点且本批无流程上下文时，要求 `unresolved_items`，禁止自填 `screening` + `identity_document`。扩展 `test_protocol_source_policy_generation.py` 覆盖 `_next_batch_prompt` 与 compact provider schema。

5. **中 — Wire 解析不要在 schema 已 required 的来源政策字段上回填历史默认值**  
   证据：schema `:976-982` vs 解析 `:2714-2718`。  
   最小修复：缺字段时失败，与生成测试 `test_compact_wire_also_requires_explicit_source_policy` 一致。

6. **低 — `_next_batch_prompt` / `_repair_prompt` 在 `source_input is None` 时不要输出无 enum 的 schema**  
   证据：`:1609-1614`、`:1716-1718`。生产主路径有 `source_input`；诊断脚本仍走该分支。最小修复：无 `source_input` 则拒绝生成 schema 或显式失败，避免「看起来像合同、实际未锁定来源」。

IN-01 单条正文：不要把 `due_stage=screening`、`identity_document`、出生日期、筛选誊写、`observation_policy.scope` 中的「资格审核时/按出生日期计算」当作已有原文。年龄 18–75 与「男女不限不作限制」可保留。这是该批次的内容缺陷，不是全方案结论。

---

### Uncertainty（未核实 / 边界）

- 未跑产品模型、未重放解构、未读工作树外临床资料、未读 `reasoning_content`。
- 未核实后期 gate 是否另有「无逐字时点则禁止 `due_stage=screening`」规则；已核实 `REQUIREMENT_DUE_STAGE_MISMATCH` 只检查 due_stage 与 workflow 节点一致（`deconstruction_gate.py:2845-2880`），不检查时点是否写在方案句内。
- 未核实当前 prompt 全文哈希是否已足够防止跨 `protocol_file_sha256` 缓存误命中；只核实键生成**未把**这些字段列为一等输入。
- 未核实 GLM/DeepSeek `json_object` 线上是否启用 batch cache；缺陷是身份字段遗漏，不是已观察到的误命中事件。
- `_configure_transport_output_scope` 按 catalog 条目顺序构建 owned spans，`_batch_source_span_ids` 按 `allowed_source_span_ids` 顺序过滤；集合应相同（输入校验 `catalog_spans <= allowed`，`agent_io.py:268-272`），enum **顺序**是否影响 provider 未核实。
- 本 artifact 只有 IN-01 一批，不能外推其他父规则。
- 会议 context/plan 仍为 TODO，不作为来源。

---

### 对 Codex 的异议、决策点与有界问题

**最高影响缺陷：** 生成/provider schema 与 `_validate_batch_source_closure` 只锁定组件级 `source_span_ids`，嵌套观察政策/复查/半衰期来源未进入同一 allowed 集合；同时首批/后续缓存键漏掉已实现的 `source_input` 身份字段。指定测试还把 compact wire 和嵌套字段留在覆盖外。IN-01 正文在合法 span 上增造了筛选时点、身份证明和出生日期政策。

**不要接受的隐含假设：** 「组件 enum 已 scoped ⇒ 全部来源字段已 scoped」；「prompt 里有 sha256 ⇒ 缓存身份完整」；「年龄条款默认筛选 + 身份证」有方案依据。

**请 Codex 裁决：**

1. 嵌套 `source_span_ids` 生成时是 enum 到本批 allowed 列表，还是只校验 ⊆ 本组件已声明 ID？推荐两者都做：生成 enum 用本批 allowed，解析/闭包再要求 ⊆ 组件 ID。
2. 非 compact 局部修订是否应与 compact 一样强制 `source_input` 闭包？推荐是。
3. 首批/后续 cache key 是否必须与分段路径一样传入 `source_input`+`prompt_template`？推荐是，即使 prompt 暂时已包含这些字段。
4. scoped 批次要不要只读下发 `required_procedure_catalog` 作为 due_stage 依据，同时仍禁止把流程 span 写入组件 `source_span_ids`？若否，应把系统合同改成「无逐字时点则 unresolved」，否则模型会继续猜 `screening`。
5. 本 artifact 的 IN-01 增造项是否纳入本轮验收失败，还是只记生成合同、另开内容缺陷？推荐：合同缺口与该条正文增造都记，但不做全方案临床失败。

**安全暂定路径：** 在 Codex 答复前，把嵌套 ID 未枚举、非 compact 修订跳过闭包、首批/后续 cache 漏 `source_input`、IN-01 增造筛选/身份证/出生日期列为有来源的缺陷；不要把流程 span 排除出组件 enum 写成误排；不要签收该条资料政策。

本角色输出为顾问意见，pending Codex 综合。
