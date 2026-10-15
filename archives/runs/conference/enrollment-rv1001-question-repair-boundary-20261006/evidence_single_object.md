# Conference Output: enrollment-rv1001-question-repair-boundary-20261006 - evidence_single_object

## Output

### 结论与角色边界

**建议：有条件采用 A；不能证明分类语义时退回 C。B 不应作为默认恢复。** 不支持的 `GapType` 不是临床资料缺失的证据；换成允许枚举也不等于分类正确。

本轮按声明的 fallback **`pi / openai-codex / gpt-6.1-sol`** 完成独立只读 advisory pass。主角色在可恢复 session 建立前不可用，是任务提供的路由记录，本轮未独立验证；没有调用 Grok Build，也不将本报告表述为 Grok 意见。

工具观察：2 次初始文件读取、12 次授权源码读取/搜索；另依高优先级要求读取一次 `memory://root/memory_summary.md`，未将记忆作为当前源码证据。未运行 shell、测试、数据库、网络或浏览器；未读取病例、凭据或其他生产路径；未修改源码、报告或创建兄弟文件。**本轮证据仅为源码与现有测试内容，不是运行通过证明或最终临床、监管、视觉验收。** 报告由 runner 持久化，Codex 保留最终决策权。

### 证据

| 编号 | 已观察事实 | 来源 |
|---|---|---|
| E1 | Author Schema 已有三分支 `oneOf`：无要求绑定且分类为空、要求绑定且分类属于限定集合、已引用文件缺失且携带文件身份。不能以“新增已有 oneOf”作为修复。 | `app/agents/evidence_normalizer.py:719–795` |
| E2 | Runtime 要求 `affected_requirement_ids` 与 `gap_type` 同时存在或同时为空；允许九种分类，拒绝其他类型。仅 `REFERENCED_FILE_MISSING` 可携带 `referenced_file_id`。 | `app/domain/contracts/evidence_normalizer.py:448–480` |
| E3 | Draft 的 Pydantic 错误被转成普通 `ValueError`；runner 仅对既有 source/context/prospective 类型建立专门冻结修复对象，其他错误进入通用 schema repair 路径。所读路径未见问题分类专用错误或冻结器。 | `app/agents/evidence_normalizer.py:1731–1744, 2468–2519` |
| E4 | Terminal partition 使用**初始答复**，而不是失败修复答复；原疑问保留进入余项验证，捕获的局部错误类型不包括问题分类错误。因此当前 partition 不是此类分类错误的恢复器。 | `app/agents/evidence_normalizer.py:2378–2405`；`app/agents/evidence_candidate_partition.py:225–254` |
| E5 | Executor 在 `final_output is None` 时，仅使用最后一次 attempt 的错误作为 `StepFailure`；本分支不呈现已记录的 `candidate_partition_failure`。成功 partition 则有工件、检查点和重建验证。 | `app/services/fact_normalization_executor.py:1263–1283, 811–865` |
| E6 | Finalize 将 persisted unresolved 输入 `_expectation_gap_signals`，随后投影 EvidenceExpectation、生成 PatientProfile；partitioned calls 强制运行状态为 `PARTIAL`。**进入 unresolved 主合同，并不等于只进入诊断通道。** | `app/services/fact_normalization_executor.py:1485–1512, 1569–1575` |
| E7 | 现有 partition 测试包含兄弟保留、事件完整依赖隔离、用药暴露闭包隔离，以及全局错误不得被删除掩盖的行为断言；本轮只读，未执行。 | `tests/v2/agents/test_evidence_candidate_partition.py:26–69, 101–125, 258–278, 291–337` |

上下文所述“44 facts、8 events、4 exposures、10 questions，以及通用修复改变三个对象”属于**任务提供的 synthetic failure 描述**，不是本轮复现结果。数量不能证明内容保真。

### 推断与主要异议

**最高影响风险：A 能封住字段越权，却不能单靠现有验证证明临床分类正确。**

- 已读要求绑定校验检查的是 requirement 身份是否属于冻结输入，并未在该函数证明新分类与原 `reason` 的语义相符（`app/agents/evidence_normalizer.py:1843–1863`）。
- 因而，`professional_judgment → required_procedure_not_done` 即使只改一个字段，也可能把“研究者已写但读不清”变成“未执行”。字段冻结不能阻止这个错误。
- **反例〔假设，非病例观察〕：** 原说明为“研究者判断已有书面记录，但关键字迹无法确认”。它不支持“判断未记录”或“程序未做”；只有原说明明确支持读取风险时，`OCR_OR_PARSE_RISK` 才有候选语义基础。
- `interpretation_conflict` 也不能机械映射为 `DESCRIPTION_INSUFFICIENT` 或 `OCR_OR_PARSE_RISK`。允许集合可能没有忠实等价类别，此时应该保留未恢复，而不是追求枚举合法。

**B 的技术隔离成立与否，取决于消费者隔离，而非命名。**

1. 若保留主 unresolved 的要求绑定、改成 `OCR_OR_PARSE_RISK`，该条仍进入 E6 的业务投影链；本轮不能证明其仅产生技术待核。
2. 若保留要求绑定、将 `gap_type` 置空，直接违反 E2。
3. 若清空要求绑定、仅在 receipt 保留原身份，则改变了业务问题的结构化绑定，不符合本轮“仅修改分类”的原约束。
4. 若同时重写 `code/message/reason` 以描述宿主处理错误，则不是“仅分类修复”，而是新增/替换技术事项，须由 Codex 明确授权。

因此，**将不支持的临床类别改名为 OCR，并把原类别留在工件里，不足以证明这是诚实隔离**。工件保真不能抵消下游业务语义改变。

### A / B / C 建议

| 方案 | 建议 | 必要边界 |
|---|---|---|
| **A** | 首选，但仅适用于原有说明足以支持某个允许分类的情形。 | 模型只提交目标索引对应的分类提案；宿主从初始原答构造结果，只替换目标 `gap_type`。无法忠实分类可以明确“不恢复”。 |
| **B** | 暂不采用为默认路径。 | 若 Codex 要独立事实恢复，需明确授权技术隔离，并证明技术事项不被解释为临床缺失、不满足研究者判断、不解除既有待核。不能直接复用现有 partition 并假定它已支持此错误。 |
| **C** | A 无法忠实分类、冻结身份不足或验证发现其他错误时采用。 | 保留初始/修复/partition 分阶段错误；保留已成功独立组的可复用身份，但不得宣称已交付该失败组中的合法事实。 |

**更安全的替代：A 使用“小补丁提案 + 宿主合成”，而不是要求模型重发整答再比较。** 沿用现有 typed error、原答 hash、host-owned 冻结和 replay 的模式；不需要新框架、新 GapType 权限或放宽门禁。

### 建议的结构化错误与保真前置条件

以下是**建议接口，不是现有符号**：

- `QuestionClassificationError`：包含准确 `unresolved_items` 索引、字段路径、原分类、允许集合及 `bounded_repair`。
- 只识别“已知但不属于 normalizer 子集”的错误族；未知枚举、绑定缺损、外部 requirement、来源越界、其他字段错误不能混作分类修复。
- 前置身份至少绑定：初始原答 SHA256、冻结输入 scope、run/call、修复策略版本。问题无独立 ID 时，使用**原答 hash + 索引 + 原问题内容 hash**，不能只靠索引。
- 提案只能包含目标及新分类/明确不恢复；拒绝重复、遗漏、额外目标、整答替换和重复 JSON key。
- 宿主冻结所有其他属性，包括 `reason/message/code`、要求/观察/定位引用、源文字范围、文件身份，以及全部事实、事件、暴露、药物分类、日期、数组数量和顺序。不能用集合归一化掩盖本轮未授权变化。
- `referenced_file_id` 也冻结：不能为选择文件缺失类型新增文件身份，不能为离开该类型删除身份。
- 宿主合成后仍走原 decoder、语义校验、页闭合及 publication gates；出现其他错误，不得降级为整答修复，也不得由本轮更改事实对象。
- Receipt 保留原答、补丁、修改前后目标、验证结果和前置身份，并明确 replay 规则。不能仅保存补丁 hash 而无法重建最终候选。

**日期边界需要显式区分：** 现有 decoder 本来执行日期/持续状态归一处理（`app/agents/evidence_normalizer.py:1702–1710`），现有测试也保留 unknown-date fallback（`tests/v2/agents/test_evidence_candidate_partition.py:281–288`）。A 的“保真”应首先证明**原始草稿除目标分类外完全未变**；不得把既有 decoder 的处理误称为本轮授权日期修改，也不得静默新增日期恢复行为。

### Codex 后续必须验证的行为

这些是验证要求，**本轮没有运行或新增测试**：

1. 两个不支持分类与多个合法兄弟并存：恢复后仅目标分类变化；事实、事件、暴露和用药依赖保留；compact aliases 与展开身份一致。
2. 原说明明确“已有书面判断但不可读”：不得产生“未做/未记录/缺少判断”、不得升级为缺失资料动作，也不得把研究者判断自动视为已确认。
3. 原说明仅支持冲突、不支持任何允许类别：明确不恢复，不能强行映射。
4. 错误同时包含外部 requirement/locator/observation、重复身份或破损结构：分类恢复不能隐藏其他错误。
5. 模型尝试改兄弟、事实对象、摘录、日期、文件身份或数组顺序：拒绝提案；禁止通用整答 repair 兜底。
6. Patch/receipt 重放遭遇原答、输入、策略版本或目标篡改：拒绝复用；初始、修复、partition 错误分别可见。
7. 若选择 B：实际覆盖 Expectation、Action 与 PatientProfile 消费结果，并保留未恢复状态；不能只断言 `gap_type == OCR_OR_PARSE_RISK`。

### 不确定性与需 Codex 决定的问题

- **消费者未证实：** `expectation_gap_signals` 的具体实现、书面判断三态判定及后续 Action/UI 不在本轮允许读集；不能据此批准 B，或宣称 A 已满足下游语义安全。
- **路由元数据有差异：** 初始 plan 的角色表仍写 `grok-build / grok-4.7`，并含 TODO（`plans/codex_main_venue_enrollment-rv1001-question-repair-boundary-20261006.md:3–18, 29–35`）。本轮以显式 fallback 指令为准；runner/Codex 应记录实际身份，本 worker 不修改该文件。

请 Codex 明确以下 bounded decision：

1. **是否允许 A 在“没有忠实允许类别”时明确不恢复，而不是强制返回合法分类？** 安全暂定：允许不恢复，走 C。
2. **是否允许把 B 的宿主技术事项纳入主 unresolved 业务流？** 这影响 Expectation/Action 语义；安全暂定：不允许默认转换，仅保留结构化技术诊断。
3. **A 的 precondition 是否必须锚定初始答复，且分类恢复后其他错误禁止转入通用整答 repair？** 安全暂定：必须；否则本轮保护的兄弟仍可能在后续阶段被重写。

本轮限定 advisory pass 完成；不代表方案已实现、测试已通过或 Codex 最终接受。
