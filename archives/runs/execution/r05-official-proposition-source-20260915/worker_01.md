# Execution Output: r05-official-proposition-source-20260915 - worker_01

## Boundary And Context Check

**Fallback declaration（必须声明）**: 主角色 `codebuddy/codebuddy-cli/deepseek-v4.1-flash` 在可恢复会话建立前不可用。本会话按 packet 声明以 `zcode` / `GLM-5.3-Flash` 接替同一 bounded worker_01 角色，保留同一任务合同、文件范围、输出路径与协议。能力差异：(1) 运行时身份为 ZCode 而非 CodeBuddy CLI；(2) 本会话未执行任何代码修改，因此"apply_patch 强制"条款未被触发（ZCode 的 Edit 工具为 apply_patch 等价物，如需修改将按字符串精确补丁执行）；(3) 遵守静态边界，未运行任何编译/测试/导入/DB/浏览器。

**读取清单**（全部只读）:
- 指定 read set：`context/r05-..._execution_context.md`、`plans/codex_execution_r05-...md`
- 四个授权文件全文或关键段：`app/domain/contracts/rules.py`（全文 738 行）、`app/services/protocol_draft_service.py`（全文 1573 行）、`app/agents/protocol_deconstructor.py`（wire 解析/身份/水合/缓存/草稿往返段）、`app/protocols/deconstruction_gate.py`（版本常量、`_issue`、source_coverage 新检查段）
- 只读相邻验证：`app/domain/contracts/agent_io.py`（SemanticRuleComponent/SemanticEvidenceRequirement/candidate 契约）、`app/storage/repositories.py`（revision 仓储）、`app/api/v2/protocols.py`（grep 级确认）、`app/agents/protocol_generation_schema.py`
- 命令：`git diff`/`git diff --stat`/`git status --porcelain`、`rg`/`wc`/`sed`（仅源码读取）

**关键边界事实（影响结论）**: 到达本会话时，工作树（`codex/phase5-clinical-facts-profile`，HEAD=4caf392，167 文件脏）中**已存在本工作项的完整未提交实现**（rules.py、deconstructor、gate 三文件；同一脏区还混有 observation_policy 与 predicate_refs 两个无关特性）。本会话逐条核对了任务合同的每一款，**未发现需要修复的缺陷，因此未做任何编辑**。`app/services/protocol_draft_service.py` 在当前实现下无需修改（见下文论证）。我不声称该实现代码为本会话所写；本会话的产出是穷尽式静态溯源审计与缺陷排查。

## Work Performed

对任务合同逐款核对实现现状，全部通过：

| 合同条款 | 实现位置与结论 |
|---|---|
| AtomicPredicate 可选 `semantic_proposition: str` 非空 | `rules.py:203`（`default=None, min_length=1`）+ validator 内 `strip()` 空白拒收 |
| 旧 None 序列化省略、保留旧内容身份 | `rules.py:214-222` `model_serializer(mode="wrap")` 对 None `pop` 该键；`canonical_hash(model_dump)` 与旧内容完全一致 |
| 仅 comparator=exists / value=None / unit=None | 契约层 `validate_semantic_proposition`（rules.py:266-291）；wire 层 `_wire_atom`：existence shape 强制 exists 且无 value 键，命题存在时 `unit is not None` 即 `DNF_WIRE_PROPOSITION_SHAPE` 拒绝 |
| 不与 `requires_professional_judgment` 混用 | 契约层与 wire 层（deconstructor.py:2022-2027）双重拒绝 |
| 不与 `occurrence_window` 混用 | 契约层与 wire 层（deconstructor.py:2028-2033）双重拒绝 |
| 允许 `prospective_period`/`prospective_window` | 两个 validator 均不禁止；系统提示要求未来命题同时用这两个字段保留原文期间 |
| 不得从旧字段自动补命题 | 全链路无推断：`_wire_atom` 原样透传（None 保持 None），水合/草稿/恢复均为 `model_copy(deep=True)`，全 app 无任何 `AtomicPredicate(...)` 逐字段重建点（rg 确认仅类定义一处） |
| 生产 wire 必填可空字段 | `_wire_atom_schema` required 列表含该键；缺失时 `_wire_atom` 抛专用 `DNF_WIRE_MISSING_SEMANTIC_PROPOSITION`（deconstructor.py:1905-1912），不默认补 null；schema `"type": ["string","null"], minLength:1, pattern:^\s*\S` 与既有 wire 方言一致 |
| 解析完整保存 | `_wire_atom` 结果 dict → `ProtocolSemanticDeconstructionCandidate.model_validate` → AtomicPredicate，字段全程保留 |
| 草稿编辑白名单完整保存 | `protocol_draft_service.py` 的 `_strip_expression` 用**排除清单**（denlist），`semantic_proposition` 不在排除集 → 进入 logic 差异快照，命题增改会被判定为语义变化（澄清反馈被 `CLARIFICATION_ALTERS_SEMANTICS` 拦截，手工纠错允许）——语义正确。API 层对 predicate 字段零引用（整模型 model_validate），无丢弃点 |
| 持久化映射完整保存 | revision 仓储整模型 JSON 存储，无字段级映射；恢复/链校验不触碰 predicate 内容 |
| 系统提示四要点 | `_COMPACT_WIRE_COMPONENT_CONTRACT`（deconstructor.py:419-446）逐条覆盖：原方向不反转、与数值/日期/频次/单位计算分离、按方案原文保留限定条件不补写、计划/意愿保留为未来陈述不得写成已履行（已发生也不得改写为计划）；与 `_SYSTEM_CONTRACT` 一同进入 `protocol_prompt_template_sha256`，全部 compact 生产调用可见。无项目疾病/药物硬编码 |
| 研究者判断不改含义、不借字段跳过 | 提示文本"不表示命题已被核实，也不能用它替代…研究者专业判断的既有处理"；gate `SEMANTIC_PROPOSITION_NOT_VERIFIED` action 明示"不得据此跳过研究者判断或复杂复查的既有处理" |
| wire 版本与发布门版本更新 | `DNF_WIRE_VERSION = "dnf-v3"`（deconstructor.py:132），全部 schema const/prompt 文案经常量引用；`DECONSTRUCTION_GATE_VERSION = "protocol-deconstruction-gate/2026-09-15.2"`。旧 wire payload 被 version 检查拒绝；批量缓存键含 prompt 哈希（合同文本已变 → 旧缓存必失配，且 `_validate_cached_semantic_batch` 异常即返回 None 重跑，fail-closed） |
| 历史读取保留 | 旧草稿 revision 存量内容按原样读取（AtomicPredicate 默认 None 合法）；gate 版本提升使旧检查点不能冒充新结论 |
| 稳定系统 ID 种子不改 | `_system_predicate_id` 种子字面量 `"dnf-v1\n"`（deconstructor.py:2144）原样保留，全 app 仅此一处残留 dnf-v1 字符串 |
| wire→RuleComponent 不丢字段 | 追踪全链：wire dict → candidate（pydantic 校验）→ `_hydrate_semantic_candidate`（`model_copy(deep=True)`，仅重映射 predicate_id/source fragments）→ draft → revision 持久化 → diff/restore → `semantic_candidate_from_draft`（深拷贝重建）——字段无丢失点 |
| 草稿编辑不丢字段 | 见上"草稿编辑白名单"行；`compute_draft_diff`/`_draft_diff_as_field_changes` 均整模型 dump |
| 门拒缺字段/来源不闭合 | wire 缺字段专用错误码；gate 新增 `SEMANTIC_PROPOSITION_SOURCE_NOT_CLOSED`（组件无可逐字核对摘录时，把命题条件的 `exact_source_clauses` 对所引 `source_refs` 材料逐字闭合核对；`materials` 变量在该 check 作用域内已由既有检查使用） |
| 不把机械 substring 当语义真实性 | 子串核对只证明逐字来源绑定；`SEMANTIC_PROPOSITION_NOT_VERIFIED`（`level="提醒"`）同时输出，明示命题真假未核实、门禁只确认来源闭合。`_issue` 签名支持所用 kwargs |

**`protocol_draft_service.py` 无需修改的论证**: 该文件对原子条件字段的全部处理要么是整模型 dump（component_state、FieldChange 信封），要么是排除式快照（`_strip_expression`）——新字段默认随行且语义归类正确（命题属判定内容而非时间窗或原文定位，进入 logic 类别）。唯一涉及它的"必改点"假设（字段会被白名单丢弃）经逐函数核对不成立。

## Artifacts And Evidence

- **本会话新建/修改文件：无**。四个授权文件中三个带既有未提交修改（非本会话所写，到达前已存在），`app/services/protocol_draft_service.py` 无修改（`git status --porcelain` 确认不在脏清单）。
- 证据锚点（行号基于当前工作树）：rules.py:203/214-222/266-291；deconstructor.py:132/149-150/419-446/483-497/1905-1912/2009-2033/2144/2168-2277/2378-2396；gate.py:66/3367-3446；draft_service.py:452-475/936-942。
- 全 app 无 `AtomicPredicate(` 逐字段构造点、无其他 `dnf-v1` 字符串残留、API 层无 predicate 字段白名单。

## Commands And Observations

- `git diff`（rules.py/deconstructor/gate）、`git diff --stat`、`git status --porcelain`、`git log -1`：确认实现为到达前已存在的未提交状态；HEAD=4caf392。
- `rg` 定位：`semantic_proposition` 仅出现在三个授权文件；tests/ 目录**无任何** `semantic_proposition` 引用（任务禁止写测试；此为所有者覆盖盲区提示）。
- `_wire_dnf_expression` 两处调用点均已解构二元组返回；`_wire_semantic_rule` 的 `verify_policy_sources`/`allowed_requirement_keys` 属同脏区无关特性（observation_policy / predicate_refs），保持原样未动。

## Blockers Or Missing Environment

无环境阻塞。**明确静态未运行边界**：按任务禁令，未运行编译、pytest、应用导入、DB、模型或浏览器；所有结论来自源码阅读与 git diff。语法与运行时行为（含 pydantic validator 实际触发）未经执行验证，由所有者统一编译验证。

## Rerun Requests Or Next Step

无 rerun 请求。留给所有者的相邻必改点/确认项：

1. **谓词 ID 身份语义确认（建议所有者知晓）**: v3 规范化 atom 载荷新增 `"semantic_proposition": null` 键，同一内容在 v3 下新铸的 predicate_id 与 v1 不同（种子字面量未动，属"旧工件不能假冒新生产方法"的预期效果；存量草稿 ID 不受影响，重解构本来即重铸）。
2. **非 compact 遗留路径**: `predicate_generation_schema` 走完整 pydantic schema，`semantic_proposition` 为可选（无缺字段拒绝）；shape 规则仍由契约 validator 强制。若非 compact 传输仍属受支持生产方法，需所有者决定是否收紧。
3. **消费者未实现**（任务明确由所有者整合后统一审阅）：入排评审/判断端对 `semantic_proposition` 的消费、以及 tests/ 目录对该特性的覆盖（当前为零），均未包含在本单元，不能宣布端到端完成。
4. 建议对所有者有用的一处措辞核对：gate `SEMANTIC_PROPOSITION_NOT_VERIFIED` 每稿固定输出一条全局提醒（`affected_refs=["protocol_draft"]`），属有意设计，若嫌噪音可后续收敛。

完整报告以本消息为最终输出，由 runner 持久化至 `runs/execution/r05-official-proposition-source-20260915/worker_01.md`（本会话未直接写该文件）。
