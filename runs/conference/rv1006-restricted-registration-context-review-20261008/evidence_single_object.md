Trellis SessionStart context loaded.

# Conference Output: rv1006-restricted-registration-context-review-20261008 - evidence_single_object

## Output

### 0. 结论摘要

**未发现可在声明窗口内确定性证明的“错误采用/越权签入”缺陷。** 但我找到 **1 个高风险边界缺口（失败诊断与完成回执同标）、1 个契约层未落地的“同单元/有界”约束、以及 3 个可加固的绑定/证明缺口**，并确认了 **7 条正向反例（补丁宣称的保护在代码里确实成立）**。

同时必须如实说明：本会议包声明窗口**恰好切掉了实现“等式保护/时间证明”的核心函数**（`_coexisting_statement_proofs`、`_temporal_restriction_indexes`、`_preserved_temporal_restriction_proof`、`_same_deep_batch_material`、重放接收路径、`RestrictedProtocolControlStatement` 本体）。因此“注册不能放宽保留范围”与“陈旧来源/配置不能重放”这两条**只能部分裁定**，剩余部分属于未读依赖，不是“已确认无缺陷”。

最高影响缺陷：`_restricted_deep_checkpoint` 对**成功**与**注册失败**四种调用点统一写入 `"stage": "deep"`（`app/services/protocol_control_execution.py:3449`），且失败态仍携带完整 `restricted_batch`。同一模块另一条深审失败诊断则使用 `stage == "deep_failure_diagnostic"`（由 `tests/v2/services/test_protocol_control_execution.py:1373` 断言）。这意味着**“失败诊断不是完成证据”这条质量门在产物结构上未被区分，只能靠读 `run_result.status`/`final_output` 反推——而这两个字段在“成功保留受限原文”的常态下同样是 `需要核对`/`None`**。这是本窗口内我能给出的最具体、最可能被下游消费者踩中的缺陷。

---

### 1. 证据轨道与范围（可复核）

| # | 读取对象 | 行窗 | 用途 |
|---|---|---|---|
| 1 | `context/..._conference_context.md` | 全文 | 任务/边界/窗口 |
| 2 | `app/services/protocol_control_restricted_source.py` | 318–756 | 受限保留主逻辑、登记再校验、公开入口 |
| 3 | `app/services/protocol_control_execution.py` | 1961–2056 | 组件身份、当前门豁免、素材门函数头 |
| 4 | `app/services/protocol_control_execution.py` | 3440–3550 | 受限检查点、定义登记编排、`_execute_deep` 头 |
| 5 | `app/protocols/protocol_control_planning.py` | 948–1088 | 分块、表格前置/同行上下文、同单元续读 |
| 6 | `app/domain/contracts/protocol_controls.py` | 2780–2960 | 深析桥、上下文闭合校验 |
| 7 | `app/agents/protocol_control_source_interpretation.py` | 1855–2025 | 定义消费登记校验、受限消费者绑定 |
| 8 | `tests/v2/services/test_protocol_control_execution.py` | 588–720 | 私有保存/回读/来源复校；时间运行器（**截断**） |
| 9 | `tests/v2/services/test_protocol_control_execution.py` | 1160–1380 | fixture、时间证明、检查点重放、诊断断言 |
| 10 | `tests/v2/protocols/test_slice58b_control_planning.py` | 108–192 | 同单元边界矩阵 |
| 11 | `tests/v2/domain/test_control_catalog_restricted_contract.py` | 87–174 | 未决保留、错误拒绝 |

**已用读取：11/12；写入：0；shell/测试/网络：0。** 余下 1 次预算未用于越窗读取，改为记录未读依赖（§6）。

**对源清单本身的两点审计（应先于技术结论）**
1. **没有提供补丁差分**，shell 被禁止，因此我**无法验证“冻结的五文件补丁”确实是全部改动**。我只审了这 10 个窗口；窗口外的任何同批改动对我不可见。若 Codex 的“五文件”来自 `git diff --stat`，请把差分本身列为会议材料。
2. 窗口选择存在**系统性偏移**：`restricted_source.py` 从 318 开始，恰好排除全部证明辅助函数；`protocol_controls.py` 窗口不含 `RestrictedProtocolControlStatement` 本体（承载 `independent_scope_proof` / `limitation_kind` / `unresolved_dimensions` 的类型）；`test_protocol_control_execution.py` 588–720 在**测试体中间截断**（最后一行 720 仍是函数实参）。这三处正好压在本次会议的两个核心主张上。

---

### 2. 确定性发现（可在窗口内逐行复核）

#### F1【高·边界】失败诊断与完成回执共用 `stage="deep"`，且失败态携带完整 `restricted_batch`
`evidence`

- `_restricted_deep_checkpoint` 固定写入 `"stage": "deep"`（`protocol_control_execution.py:3449`），并被**四个**调用点复用：成功返回 `3526-3529`，以及三条失败路径 `3499-3503`（登记未产生 `declaration`）、`3511-3515`（再校验抛 `ValueError`）、`3521-3525`（再派生不一致）。
- 失败检查点仍包含 `restricted_batch`（`3460`），测试**明文断言**这一点：`assert saved["restricted_batch"] == output.model_dump(mode="json")`（`tests/.../test_protocol_control_execution.py:660`）、`saved["run_result"]["status"] == "需要核对"`、`final_output is None`（`:662-663`）、`attempt_raw_outputs[-1]["raw_output_text"] == raw`（`:664`）。
- 同一模块另一条深审失败诊断使用**不同**约定：`assert diagnostic["stage"] == "deep_failure_diagnostic"`、`assert "restricted_batch" not in diagnostic`（`:1373-1374`）。

**危害性反例 HC-1（推断，取决于未读的重放接收码）**：某作业深审步登记失败 → 运行器持久化该诊断检查点 → 作业恢复时 `_same_deep_components_with_current_gate`（`2036-2050`）在载荷未变时**通过**，`_same_deep_batch_material`（`2053`，函数体未读）在批次未变时**通过**，`validator_version` 本就被豁免（`2041-2049`）。随后若接收逻辑按“再派生并与保存值相等”判定（**该机制由测试反推**：篡改 `restricted_batch.restricted_statements[0].source_quote` 会得到 `PROTOCOL_CONTROL_CHECKPOINT_INVALID`，`:1336-1341`），则对失败诊断会出现：`source_definition_consumers is None` → `_validate_restricted_definition_registration` 立即返回、**不检查那次失败尝试**（`restricted_source.py:484`）→ 再派生结果与保存值相等 → **通过**。于是“拒绝被篡改的成功检查点”的同一条码路，会**接受一次登记失败的诊断**为完成态深审结果。注意：**成功**的受限保留同样以 `status=需要核对` + `final_output=None` 为常态（`:1301-1302`），所以这两字段无法作判别位。

**最小修复（2–4 行）**：给 `_restricted_deep_checkpoint` 增加 `failure_code: str | None = None`，失败三处传 `PROTOCOL_CONTROL_SOURCE_DEFINITION_CONSUMER_INVALID` 并写 `"stage": "deep_failure_diagnostic"`（或保留 stage，另加 `"restricted_registration_failed": True` / `"completed": False`）；同步把 `:1373` 同款断言补到 `:623-666` 的失败测试上。**在未读重放码前，安全临时路径**：任何消费者/投影一律不得从 `stage=="deep"` 诊断检查点取 `restricted_batch` 作为可消费保留结果。

#### F2【中高·契约】“同单元 + 有界”只实现在分块器，契约层未强制
`evidence`

分块器（`protocol_control_planning.py:1049-1069`）确实实现同单元续读：`prefix` 由 `.p` 右分割得到（含 `r/c` 坐标），逐条要求 `following.source_ref == f"{prefix}.p{next}"`（`1059`）、`heading_path` 相等（`1060`）、`table_context` **模型整体相等**（`1061`）、字符预算 `_MAX_SCHEDULE_ROW_CONTEXT_CHARS`（`1062`）与条数 `MAX_SOURCE_LIST_GROUP_UNITS`（`1058`）；任一不符即 `break`，**不落任何前缀**。测试矩阵覆盖 `gap/other_cell/heading/next_intro/plain_paragraph/no_intro`（`test_slice58b_control_planning.py:124-151`）。

但契约层 `ProtocolControlDiscoveryToDeepPlan.validate_bridge` 的表上下文放行口（`protocol_controls.py:2938-2947`）只要求：单元 id ∈ 清单、单元自身 `source_ref` 的行号与其 `table_context.row_index` 自洽、`row_key[0] ∈ owned_tables`、且 `row_key ∈ owned_rows or 0 <= row_key[1] < 5`。**没有列（cell）约束，没有条数/字符预算**。两条闭合式（`2948-2951`）因此等价于：`actual ⊇ expected` 且 `actual ⊆ expected ∪ table_context_ids`。

**危害性反例 HC-2（确定性可达于“被编辑/陈旧计划”）**：同一行左单元格“包括以下事项：”，右单元格是**另一访视**的并列要求；若计划侧写入右单元格单元为上下文，契约**接受**（同 `table_ref` 同行）。深析提示词将得到跨单元格文本，模型可把邻列要求读成同一条清单的续项。同理，行 0–4 的**全部**单元格可被无上限注入（`0 <= row_key[1] < 5`），与“bounded”主张不相符。
另注：错误文案仍写“必须精确闭合到发现阶段声明”（`2951`），与放宽后的实际语义不符，会误导审计。

**最小修复（3–6 行）**：在 `validate_bridge` 对仅经 `table_context_ids` 入场的单元追加**同单元格判定**（`(table_path, row_index, column_index)` 与所属 owned 单元一致或为前置行）并镜像分块器的条数/字符常量（**import 常量，不要复制字面量**）；同时把两份近乎重复的 `table_row_key`（`protocol_control_planning.py:965-973` 与 `protocol_controls.py:2923-2931`）抽成 `protocol_controls` 里的单一 `table_cell_key` 并反向 import，避免构建器/校验器漂移。

#### F3【中·绑定】受限消费者的“逐字绑定”只做规范化子串包含
`evidence`

`validate_restricted_definition_consumers`（`protocol_control_source_interpretation.py:1988-2019`）对 `restricted_statement` 消费者要求：目标可解析、目标单元 ∈ 本批 owned、索引在界内且与目标单元一致、**非自引用**（`2007-2008`）、引文逐字相等（`2009`）、span 集合相等（`2010-2011`）、`normalize_source_excerpt(consumer_excerpt) in normalize_source_excerpt(target.source_quote)`（`2012-2013`）。

**危害性反例 HC-3（确定性）**：`consumer_excerpt="的"` 且目标 id 合法 → 通过。暴露给下游的“消费原子原文”可以是一个无意义片段，而登记回执看起来是“已逐字绑定”。

**次要点**：同一函数直接用 `interpretation.statements[item.statement_index]`（`2002`），却对 `target.source_statement_index` 做了显式上界检查（`2004`）——**不对称**。当前两个在窗调用点（`1980`→`1984`、`498`→`499`）都先跑 `validate_source_definition_consumers`，所以不可达；但该函数是公开 API，单独调用会以 `IndexError` 逃逸而非 `SourceTargetReviewValidationError`（推断，低概率）。

**最小修复（2–3 行）**：为 `consumer_excerpt` 增加最小规范化长度，并用 `locate_source_quote_offsets(units[target.source_structure_unit_id].excerpt, consumer.consumer_excerpt)` 在**冻结原文**上定位（而非在引文上做子串包含）；为 `item.statement_index` 复用同样的上界拒绝。

#### F4【中·证明】受限再校验跳过“冻结官方条件身份”
`evidence`

声明创建侧会调用 `require_frozen_official_predicate_identities`（`source_interpretation.py:1925-1964`，注释明确“absent or empty index rejects every official declaration”），但受限登记再校验只调用 `validate_source_definition_consumers` + `validate_restricted_definition_consumers`（`restricted_source.py:498-501`），**不传身份索引**；而 `validate_source_definition_consumers` 对官方消费者只证明 `official_code ∈ batch.known_official_targets`（`source_interpretation.py:1915-1922`）。docstring 自述“发布层会再证同一身份”（`:1938-1939`）。

**结论分级**：这是**纵深防御缺口**而非已证可危害缺陷——伪造的 `(rule_component_id, predicate_id)` 会被发布层拦下，但**受限登记回执所声明的“已证明范围”被夸大**。调用点 `protocol_control_execution.py:3470-3471` 手上就有 `official_predicate_identities/sources`，却没有沿链路传下去。

**最小修复（3–5 行）**：给 `restricted_batch_from_review` / `_validate_restricted_definition_registration` 增加可选身份索引参数，在声明含 `official_predicate` 消费者时**必须**提供并调用该证明；重放路径若拿不到索引则**拒绝官方消费者（fail closed）**，而不是静默接受。

#### F5【中·状态坍缩】整单元保留会吞掉同胞陈述“已核覆盖”的结论，且无撤回记录
`evidence`

整单元分支（`restricted_source.py:367-399`）只校验该单元 `disposition == OTHER_CONTROL_CANDIDATE`（`369-370`）与**原文范围全覆盖**（`371-398`），**完全不读取** `reviewed[index].decision`。而对**非**受限单元，代码会显式校验 `covered_by_official` 必须对应 `OFFICIAL_ELIGIBILITY` 且 `linked_official_code` 匹配（`627-631`）、`covered_by_procedure` 必须对应程序目录项（`631-636`）。`reviewed` 仅在 `else` 分支被使用（`400-421`），说明**单元处置与陈述裁决的一致性不是全局校验器强制的**（否则该分支的重复校验是死代码）。

**推断（中置信）**：某单元含 S1（review: `covered_by_official`→IN03）与 S2（`unresolved`），整体处置为 `OTHER_CONTROL_CANDIDATE` 时，整单元被判 `RESTRICTED_SOURCE`，S1 已被核出的官方对应被**静默撤回**，输出只留 `unresolved_dimensions`（`450-455`）与单元级理由，没有任何字段记录“曾核出什么”。这正与项目规则“Separate rule judgment from gap reason / 不把判断坍缩进缺口理由”相冲突，并会误导操作者重做映射或让入排面对一个“看起来从未被核过”的条目。

**最小修复（择一，属需 Codex/用户裁定的取舍）**：
(a) 记录型（信息量最大）：在受限陈述上追加 `withheld_review_decisions`（沿用 `decision`/`target_id`），保留“已核但被整体撤回”的可审计性；
(b) 收紧型：当受限单元内任一陈述 decision ∈ {`covered_by_official`,`covered_by_procedure`} 时**不进入整单元保留**（返回 `None`，落到显式失败）。注意 (b) 会**增加**“无存活输出”的类别，是否可接受需用户裁定（见 §7 Q3）。

#### F6【中高·可审计】同单元上下文没有任何“被截断/停止原因”标记
`evidence`

`_deep_batch_chunks` 在五处 `break`（`1058/1059/1060/1061/1062`）后返回一个**纯 tuple**（`1076`）；停止原因（缺号 gap / 换行 heading / 换列 other_cell / 字符预算 / 条数上限 / 正常遇到冒号结尾）**未被记录**，也不进入 `ProtocolControlDispositionBatch` 或桥计划。文档口径只存在于 Python 注释（`1045-1048`：“does not assert that the list is complete”）。

**危害性反例 HC-4（确定性）**：某单元格清单共 40 项，预算先命中，上下文只含前 13 项。提示词里的“包括以下事项：”后跟一段**看起来完整**的枚举；语义 Agent 据此可判定“未被列出者不属于该清单”，把截断当成完成。这正是本次质量门“context truncation is not completion”所禁止的，但**当前没有任何机器可读位可以验证或阻断**。

**最小修复（1 字段 + 1 断言）**：让分块器返回每 owned 单元的 `context_stop_reason`（`gap|heading|cell|char_budget|unit_budget|terminator|end_of_source`）与 `context_truncated: bool`，随批次/计划落盘；提示词组装处据此显式声明“以下为**有界前缀**，不代表清单完整”。测试改为断言停止原因，而不是只断言“和 ≤ 6000”。

#### F7【低-中·加固】组件身份允许“空对空”匹配
`evidence`

`_deep_component_identity` 直接 `payload.get(...)`：`source_content_sha256`、`draft_revision_id`、`draft_content_sha256`（`protocol_control_execution.py:1973-1974`）、`discovery_plan`/`coverage_manifest` 走 `digest(payload.get(...))`（`1975-1976`）、`frozen_model_routes.deep`（`2030-2032`）。缺键时两侧同为 `None`，`_same_deep_components_with_current_gate` 的 `saved == current` 便**真空成立**。

**推断**：仅当某类载荷合法地缺少这些键时才可危害；若上游强制存在，则仅为加固。**最小修复（1–2 行）**：身份计算时对 `source_content_sha256/draft_revision_id/draft_content_sha256/wire_schema` 做非空断言（fail closed），或在比较时拒绝任何 `None` 身份字段。

#### F8【低-中·可读性/误导】`3516` 的“登记后范围不变”断言在当前实现下是恒真式
`evidence`

`revalidated = restricted_batch_from_review(batch, result)`（`3505`）与 `restricted_batch` 的比较（`3516`）中，`result` 仅被追加 `source_definition_consumers` 与 `restricted_source_definition_consumer_attempts`（`3488-3491`），而受限派生完全不读这两个字段（`_restricted_statement_batch_from_review` 全窗内无引用；`_validate_restricted_definition_registration` 只做校验、不改变输出，`478-501`）。**结论**：真实的反放宽保障来自“消费者 id 必须解析到既有受限陈述”（`1995-2001`），而不是这条等式；该等式只是确定性/一致性守卫，failure-3（`3516-3525`）**当前不可达**。

**建议（不改行为）**：改写注释说明其性质；若要保留可执行断言，改为显式检查“声明未引入任何不在 `restricted_batch.restricted_statements` 中的 id”。**反面提示**：不要把它当成“注册不能放宽”的证据——这会掩盖 F4 才是真正的未证面。

#### F9【低·健壮性】两处 `units[unit_id]` 依赖未读校验器的成员资格保证
`evidence`：`_whole_unit_restriction`（`371/380`）与 `_restricted_statement_batch_from_review`（`605`）都用**陈述派生**的 `structure_unit_id` 索引 `units`（仅由 `batch.owned_units` 构建，`344/567`）。若 `validate_source_interpretation`（未读）不证明“陈述单元 ⊆ owned”，畸形/陈旧保存结果会抛 `KeyError` 而不是 `SourceTargetReviewValidationError`。**最小修复**：在索引前加成员判定并拒绝。

#### F10【测试质量】三处硬编码/未覆盖
1. `test_slice58b_control_planning.py:152` 断言 `<= 6000` 字面量，而条数用了 import 的 `MAX_SOURCE_LIST_GROUP_UNITS`（`:111`）——常量变更会静默漂移。
2. **条数上限从未被触发**：32 个 ~404 字单元在 6000 字符预算下先停（≈14 项 < `MAX_SOURCE_LIST_GROUP_UNITS`），`1058` 的条数分支无覆盖。
3. `other_cell` 用例同时改了 `source_ref` 与 `table_context`（`:131-132`），因此**只由 `table_context` 相等守住**的路径（只改 `column_index` 或只改 `member_cell_paths`，保留 `source_ref` 前缀）未被证明。建议补 2 个最小用例。

#### F11【超窗·决策点，不作为本轮修复】仍存在“无存活输出”的一个类别
`inference`

若某单元含 ≥2 条陈述、其中一条只有 `review` 级 `unresolved`（`interpretation.unresolved == []`）、且 `_coexisting_statement_proofs` 证不出独立范围，则单条救援条件（`600-607`：`len(indexes) != 1` → `return None`）不成立 → **整批返回 `None` → 无受限输出**。依据：代码自己在 `610-611` 允许“`reviewed[index].unresolved` 为真而 `interpretation.statements[index].unresolved` 为空”的组合存在，说明该组合可达（否则该判定为死代码）。这与补丁要修的原始症状同类（有源陈述在有效登记后无存活输出），但修复它需要“范围补集证明”，属 **AGENTS 明确限制的“扩展恢复/通用能力”**——**默认不做**，仅登记为决策点（§7 Q4）。

---

### 3. 正向反例 / 补丁主张成立的部分（避免只报缺陷）

| 主张 | 落地证据 |
|---|---|
| **注册不能扩宽保留范围（结构性）** | 受限语句只能由**派生**产生（`653-686`），声明只能**引用既有** `restricted_statement_id`（`1995-2001`），且要求单元 ∈ 本批 owned（`2003`）、索引/单元自洽（`2004-2006`）、非自引用（`2007-2008`）、引文与 span 逐字相等（`2009-2011`）。引用解析式绑定使“新增/扩宽”在结构上不可能。 |
| **自引用与旧合同不能通过** | 测试 `:669-687` 明确覆盖：改写为自引用抛错；把 `version` 改为 `.../v2` 在模型层拒绝。合同版本硬校验见 `source_interpretation.py:1978-1979`。 |
| **私有原答不受运行结果快照污染** | `run_result` 中**不含** `raw_output_text`（测试 `:596` 断言），原始回答另存 `attempt_raw_outputs`（`:664`）；缺失/重复/改文/改哈希/`None` 列表**全部**抛错（`:597-611`），且正常路径再派生必须与首次输出**相等**（`:612-614`）。 |
| **不暗示完整覆盖** | 登记记录 `scope_complete == False` 且带 `unresolved_reasons`（测试 `:618-620`），与 F6 的“上下文无标记”形成对照（后者应学此处）。 |
| **gap/换列/换标题不能成为上下文；不转移所有权** | 构建器五处 `break`（`1058-1062`）；种子只来自 `owned`（`1049`），上下文不递归扩散；上下文单元 id 与 owned 去重（`1066-1067`）；测试断言全部单元恰被拥有一次（`:144`）与输入未被修改（`:154`）。 |
| **子集/过滤输入不会伪造相邻性** | 强校验 `following.source_ref == f"{prefix}.p{n+1}"`（`1059`）使用**绝对**段号，因此即使 `all_units` 缺省且 `units` 为子集，被跳过的段落号会立刻 break（我原先怀疑的伪相邻不成立——这是对构建器的一处正向反例）。 |
| **覆盖清单不可伪造** | 再派生必须等于保存的 `source_statement_coverage`（`340-343`、`554-556`），索引集合必须恰为 `range(n)`（`533-536`、`734-737`），整单元保留还要求 `source_statement_ranges_cover_unit` 覆盖整段原文（`394-398`）。 |
| **陈源/改配置重放被拒（部分可证）** | 组件身份含 source/draft/plan/manifest/prompt/wire schema/编译版本（`1972-2029`）；篡改 `batch_id/prompt_template_sha256/transport_identity/component_identity` 或 `restricted_batch` 引文均得 `PROTOCOL_CONTROL_CHECKPOINT_INVALID`（测试 `:1329-1341`）；仅 `validator_version` 被豁免（`2041-2049`），语义上等于“用当前门重建”。**但这依赖未读的重放接收码**（§6）。 |
| **时间受限证明是“有类型、绑来源、不采用”的** | 测试侧证明：`proof["statement_ids"] == [1]`、`source_refs == ["span:01"]`、`adopted is False`；缺字段/缺 id/布尔 id/外来 ref 全部 fail closed；输入在调用前后字节不变（`:1214-1250`）。实现函数未读，故仅记测试级证据。 |
| **失败不产生“完成”假象（部分）** | 失败检查点 `final_output is None`、`status == "需要核对"`（`:662-663`）、能力类失败显式 `stage="deep_failure_diagnostic"` 且**不含** `restricted_batch`（`:1373-1374`）。——正是这条与 F1 的不一致构成了最高影响缺口。 |

---

### 4. 危害性反例汇总（按严重度）

| 编号 | 场景 | 后果 | 是否已在窗口内确定 |
|---|---|---|---|
| HC-1 | 注册失败诊断被当作完成深审重放/投影（F1） | 无有效定义登记的受限原文被当作可消费证据 | 结构缺口确定；是否被消费取决于未读重放/投影码（**阻断性问题**） |
| HC-2 | 计划侧写入跨单元格同行单元或超量前置行（F2） | 深析提示词把邻列/无关前置文本读成同一清单 | 契约层确认为“接受” |
| HC-4 | 字符/条数预算截断后无标记（F6） | 语义 Agent 把截断当完整清单，得出“未列出=不要求” | 确定（无标记字段） |
| HC-3 | 退化子串 `consumer_excerpt`（F3） | 登记回执夸大“逐字绑定” | 确定 |
| HC-5 | 整单元保留吞掉同胞已核覆盖（F5） | 已核判断静默撤回，形成“看起来从未核过”的条目 | 条件确定（取决于未读校验器是否全局强制处置↔裁决一致） |
| HC-6 | 伪造官方 `(component,predicate)` 身份（F4） | 受限登记回执范围夸大（发布层仍会拦） | 确定（纵深防御） |
| HC-7 | 空对空身份匹配（F7） | 某类载荷下身份门真空通过 | 条件（取决于未读载荷契约） |

---

### 5. 最小修复清单（按性价比排序；均为“直接阻断/防误用”类，不属扩展能力）

| # | 目标 | 位置 | 规模 |
|---|---|---|---|
| M1 | 失败诊断显式标记，禁止被当作完成态 | `protocol_control_execution.py:3442-3461` + 三个失败调用点 `3499-3525` + 测试 `:623-666` | 2–4 行 + 1 断言 |
| M2 | 上下文停止原因/截断标记落盘，提示词声明“有界前缀” | `protocol_control_planning.py:1049-1076` → 批次/计划字段；测试 `:152` | 1 字段 + 1 断言 |
| M3 | 契约层补“同单元格 + 预算”，合并两份 `table_row_key` | `protocol_controls.py:2923-2951`、`protocol_control_planning.py:965-973` | 3–6 行 |
| M4 | 消费者原文最小长度 + 冻结原文定位；`item.statement_index` 上界 | `protocol_control_source_interpretation.py:1988-2019` | 2–3 行 |
| M5 | 受限再校验接入冻结官方身份（缺索引即拒官方消费者） | `protocol_control_restricted_source.py:478-501`、`protocol_control_execution.py:3470-3505` | 3–5 行 |
| M6 | 整单元保留记录/拒绝“已核同胞” | `protocol_control_restricted_source.py:367-399, 440-460` | 2–4 行（**需先裁定 §7 Q3**） |
| M7 | 身份字段非空断言 | `protocol_control_execution.py:1972-1976, 2030-2032` | 1–2 行 |
| M8 | 注释校正 `3516` 的真实性质 | `protocol_control_execution.py:3516` | 注释 |
| M9 | 测试补齐（column_index 单改、member_cell_paths 单改、条数上限、常量替换、失败 stage） | 三个测试文件 | 5 个小用例 |

---

### 6. 未读依赖与证据限制（精确到行）

**A. 阻断“等式保护/时间证明”完整裁定**
1. `app/services/protocol_control_restricted_source.py:1-317` —— 含 `_coexisting_statement_proofs`、`_temporal_restriction_indexes`、`_restricted_capability_batch`、`RestrictedStatementScopeProof` 的构造、以及 `locate_source_quote_offsets` / `source_statement_ranges_cover_unit`（含 `allow_joining_punctuation` 的真实宽松度）。
2. `app/domain/contracts/protocol_controls.py` **2780 之前**（`ProtocolControlDispositionBatch` 的 `context_units` 是否有条数/字符上限；`MAX_SOURCE_LIST_GROUP_UNITS` 定义）与 **2960 之后**（`RestrictedProtocolControlStatement` 的字段/校验、`ProtocolControlBatchDispositionHydrated` 校验器、`check_protocol_control_batch_candidates` 位置与强度）。
3. `app/protocols/protocol_control_planning.py` **948 之前 / 1088 之后**（`_heading_runs`、`is_source_list_continuation_group`、`_MAX_SCHEDULE_ROW_CONTEXT_UNITS/CHARS` 实际值）。

**B. 阻断“陈旧来源/配置不可重放”与 HC-1 的最终裁定**
4. `app/services/protocol_control_execution.py:2053-3440`（`_same_deep_batch_material` 全体、`_saved_deep_run_result`、`_deep_attempt_raw_outputs`、检查点接收/`create_protocol_control_executor` 重放分支、`_preserved_temporal_restriction_proof`、能力对角线）。
5. `tests/v2/services/test_protocol_control_execution.py:721+`（`test_actual_temporal_runner_...` 的断言体**在窗口边界被截断**，该测试正是“时间运行器保留独立要求”的证据）。窗口 `588-720` 的右端**切在函数实参中间**。

**C. 阻断“失败诊断是否会被投影/消费”**
6. `_restricted_control_projections`（`app/services/eligibility_review_projection.py`，测试 `:696` 引用其存在）——诊断态 `restricted_batch` 是否进入用户可见面。
7. 深析提示词模板与组装处（文件名未在窗口内出现）——是否声明表格/单元格上下文为**有界前缀**。

**D. 阻断若干条件性结论**
8. `validate_source_interpretation`、`validate_source_target_review`、`source_statement_coverage`、`hydrate_protocol_control_agent_output`（）——决定 F5/F9/F11 是否可达。
9. `declare_source_definition_consumers`（`app/agents/protocol_control_deconstructor.py`）——是否透传 `restricted_batch.restricted_statements` 与身份索引。

**E. 环境限制（按提示自述）**
10. 无 shell：**无法确认补丁边界**（`git diff`）、常量真值（6000 为测试推断）、`MAX_SOURCE_LIST_GROUP_UNITS` 数值。
11. 所有者自述的“六次真实产品请求/响应离线重放”**不在读集内**，我按“所有者报告的证据”对待，未作为确定性证明。其结论（注册前后源处置一致）**与我在 F8 的结构性分析方向一致**，但该重放本身无法在本窗口内被复核。

---

### 7. 对 Codex 的裁定点、有界问题与建议方案

**Q1（阻断性，最高优先）** —— `_restricted_deep_checkpoint` 产出的失败诊断（`stage="deep"`、含 `restricted_batch`、`run_result.status="需要核对"`、`source_definition_consumers=None` 且 `restricted_source_definition_consumer_attempts` 非空）**是否会被检查点重放接收路径或任何投影当作完成态消费**？
*为何重要*：若会，本次补丁要解决的症状会以“从失败诊断采用无登记保留原文”的形式复现，且 F1 使其在结构上不可判别。
*需要读*：`protocol_control_execution.py:2053-3440` 的接收/重放分支、`eligibility_review_projection._restricted_control_projections`。
*安全临时路径（无需读取即可先做）*：M1 立即落地，并在文档/接口层声明“诊断检查点不可消费”。

**Q2** —— `validate_source_interpretation` 是否证明：(a) 每条陈述的 `structure_unit_id` 必属 `batch.owned_units`？(b) `review` 裁决为 `unresolved` 时是否强制 `interpretation.statements[i].unresolved` 非空（或反之）？
*为何重要*：直接决定 F9（`KeyError`）与 F11（仍存在无存活输出类别）是否可达。当前代码在 `610-611` 与 `072` 的行为暗示 (b) 不成立。

**Q3（产品/边界裁定）** —— 整单元保留时，单元内**已被 review 核定为 `covered_by_official`/`covered_by_procedure`** 的同胞陈述，应当：(a) 记录为“已核但整体撤回”（可审计、不改判定），还是 (b) 阻止整单元保留、改为显式失败？(b) 会增加“无存活输出”类别，按 AGENTS 的“不默认扩展恢复”应慎用。请裁定，并明确该项选择是否会改变本窗口的验收语义。

**Q4（超窗裁定）** —— F11 的“多陈述单元 + 仅 review 级 unresolved + 无独立证明 → 整批无存活输出”是否属于本窗口“直接阻断”范畴需要修复？若属于，最小方案是范围**补集**证明（受限陈述覆盖单元内非已覆盖部分），但它触及“扩展恢复/通用能力”，按现行 AGENTS 边界**默认不做**。请给出是/否与依据。

**Q5** —— 深析桥计划与覆盖清单的绑定在何处被证成？`validate_bridge` 只证明 `manifest_structure_unit_ids_sha256 == stable_...sha256(expected_structure_unit_ids)`（`2836-2842`），属**自洽**，未与当前活动清单对象比对。*为何重要*：这是“陈旧来源/配置不能重放”的另一半。

**Q6** —— 真实冻结文档中，表格单元格内的清单项是否**确实**以 `.p<n>` 连续编号的段落形态原子化（测试 `:113-123` 的假设），且同一单元格各成员的 `table_context`（含 `member_cell_paths`）是否**完全相等**（`1061` 用模型整体相等）？若实际并非如此，同单元续读会**静默降级为无上下文**（回到补丁前的缺口形态），F2/HC-2 的优先级需重排。

**Q7（对会议目标本身的挑战）** —— 本会议把两条成熟度不同的主张打包在一个对象里：“注册保留不变”（有代码级 + 测试级证据）与“同单元只读上下文有界”（**契约层无证据**，只有构建器与一个被截断的测试）。建议 Codex **拆成两条独立决议记录**，不要让前者的通过掩盖后者的未证。

---

### 8. 预期最强的反对意见（我主动列出并给出回应）

1. **“失败检查点仍带 `restricted_batch` 是有意的——失败时必须保住原文，否则用户丢失证据。”**
   回应：我同意保留原文；F1 的诉求**不是删除数据**，而是让“失败态”在产物里**可判别**（M1 只加标记，不删数据）。同一模块的 `deep_failure_diagnostic` 已经证明该做法可行且被采用。
2. **“`stage="deep"` 是阶段名，不是完成标志；完成应由 `final_output`/status 判定。”**
   回应：该论据在本补丁里自相矛盾——**成功**的受限保留同样是 `status="需要核对"`、`final_output=None`（测试 `:1301-1302`）。因此不能同时用“看 status”和“看 stage”来自证。
3. **“契约只需要结构约束，尺寸由构建器保证，两层各司其职。”**
   回应：那为何契约要复制一份与构建器**逐字相同**的 `table_row_key`（`2923-2931` vs `965-973`）？重复的镜像逻辑意味着契约**意图**做语义校验；既然如此，同单元格与预算也应镜像（M3），否则应在契约里删除该段并改由计划构造方强制。
4. **“F5 不可能发生，因为校验器不允许处置↔裁决不一致。”**
   回应：若如此，`627-636` 对**非**受限单元逐一重复校验同一不变式就是死代码。请用 Q2 的读数证实或推翻；我在报告中将 F5 明确标注为“条件确定”。
5. **“同单元续读只覆盖 `.p` 编号是可见的取舍，够用。”**
   回应：取舍本身可接受，但**它没有被记录**：当形态不匹配时，行为退化为“无上下文”，与补丁前症状同形，且没有 surface 出“本单元未取到后续清单”。建议至少记录 `context_stop_reason`（M2 顺带解决）。

---

### 9. 裁定与不确定性分级

- **可在窗口内确定性认定**：F1（标记缺失）、F2（契约未强制同单元格/预算）、F3、F4、F6、F7、F9、F10；正向保护 P2/P3/P4/P5/P6/P7/B 类。
- **条件性认定（取决于未读校验器）**：F5（需 Q2）、F11（需 Q2）、HC-1 的“是否会被消费”（需 Q1）。
- **无法认定（明确未证）**：`_coexisting_statement_proofs` 独立范围证明的真实强度；`source_statement_ranges_cover_unit(allow_joining_punctuation=True)` 的宽松边界；重放接收分支对诊断态的处置；提示词是否声明上下文有界；真实文档的单元格原子形态。
- **我的建议等级**：M1/M2 应视为**本窗口内直接阻断类**（防误用/防误读），建议在本轮落地；M3/M4/M5 为低成本加固，可在同一轮或紧随；（F11 的范围补集证明）**不建议**在未获用户明确授权前实施。

**不声称最终验收。** 临床采用、完整 Job 成功与最终交付不由本角色裁定；以上均为有界咨询意见与可复核证据。
