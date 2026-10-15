# 执行输出：fact-correction-gap-replay-20260910 - worker_01 (修复轮次 2)

## 边界与上下文检查

- 已写入的路径严格限于九个已授权的路径；对产品代码的编辑使用了运行时原生的编辑工具进行精准替换。**字面工具限制（未由替代方案满足）：** `apply_patch` 在此运行时中并非可用工具；仅在本轮次中未使用 uvx/网络/安装（仅基于 stdlib 进行了 lint-skip 和 `py_compile`）。
- 按照指示进行了文件名验证：`tests/v2/storage/test_evidence_expectation_repository.py` **不存在**。V2 期望存储库由 `tests/v2/projections/test_evidence_expectations.py`（可写）执行，因此存储库级测试都放在那里。**所有者需确认此位置。**

## 执行的工作（对照所需的修复）

1. **针对每个活动实体进行源选择。** `app/services/fact_expectation_gaps.py::select_reprojection_source_runs` 现在针对当前权威（authority）下每个未被取代的活动事实/事件/暴露（event/exposure）以及该目标，遍历 `trace_correction_lineage`，并合并所有可达的祖先实体运行。循环、收敛分支、类型不匹配、缺失记录/运行以及每个实体/运行的权威相等性检查均已保留。已丢弃的分支（其新实体已自身被取代且非活动实体祖先的更正）永远不会被遍历；历史运行永远不会被批量收集。已进行区分验证：新测试会在仅针对目标遍历的实现下失败（旧的遍历无法到达另一条链的原始运行，因此特定的 OCR 缺口会退化为通用的 `observation_unverified` 填充）。
2. **拒绝候选者抑制。** `expectation_gap_signals` 增加了可选的 `accepted_requirements`；`None` 完全保留了终结器（finalizer）派生的行为（相同的代码路径，执行器未更改）。重投影传入当前未被取代的已发布事实所支持的需求集（可能为空），因此如果接受证据随后被取代/解除绑定，历史“曾经接受”的候选者不能再抑制被拒绝的候选者的 `ocr_or_parse_risk`。测试锁定了完整弧：终结模式抑制 → `observed`；接受事实的需求绑定被移除 → `absent` + `ocr_or_parse_risk`，且 `gap_detail` 携带特定的拒绝原因，而不是通用的无记录回退。
3. **输入来源已冻结。** `EvidenceExpectationV2.input_gap_signals: list[CoverageGapSignal] | None` — `None` = 旧版/来源未知，`[]` = 已知无信号，否则为确切适用的信号，包括 `fallback_only`。`canonical_input_gap_signals(template_id, signals)` 拒绝绑定到其他模板的信号，并通过规范哈希进行排序和去重；契约验证器强制执行这两种行为。`project_expectation` 在**所有六个返回路径上填充它，包括 `not_due`**，仅使用适用于该模板的信号。`_coverage_content` 现在包含来源（None 与 [] 不同），因此可见状态相同但来源不同会追加一个修订版，而相同内容则重用。存储在现有的 `payload_json`/`payload_sha256` 中 — 无新表/迁移；旧行从不重写。
4. **先前风险策略（删除启发式规则）。** 删除了 `gap_type`/`source_coverage` 推理；`_prior_unreconfirmed_signals` 现在精确读取 `input_gap_signals`：先前观察到/未到期 → 无填充；先前为纯来源强度弱（`provenance_followup`） → 无填充；具有重放无法重现的具体（非回退）输入的先前状态 → 非默认 `observation_unverified`，其细节链接到该先前相同权威的期望 ID（而非复制的临床缺口）；明确的 `[]`/仅回退输入 → 允许在完整证据下清除；旧版 `None` → 保守地视为未解决（从不猜测为回退）。由于填充信号本身是具体的且被冻结到新行的输入中，弱/缺失的不确定性在后续更正中持续存在，直到源重放或明确的处置 — 未发明任何决议机制。策略记录在模块和函数的文档字符串（docstrings）中。

## 工件与证据

- 产品：`app/domain/contracts/evidence_expectations_v2.py`, `app/projections/evidence_expectations.py`, `app/storage/evidence_expectation_repository.py`, `app/services/fact_expectation_gaps.py`（服务/执行器连接相对于上一轮未更改）。
- 测试：`tests/v2/services/test_fact_correction_gap_reprojection.py` 现在有 11 个测试 — 原始的 D1 回归和源运行种子生成被保留，加上 `test_correction_of_unrelated_fact_keeps_other_chain_source_risk`, `test_rejected_candidate_risk_survives_accepted_binding_removal`, `test_concrete_absent_becoming_complete_stays_unverified`, `test_fallback_only_absence_clears_when_complete_evidence_arrives`，以及填充测试现在还断言链接的填充信号作为具体输入被冻结到新的期望中。`tests/v2/projections/test_evidence_expectations.py` 增加了 4 个测试：所有路径上的来源冻结（排序/去重确定性与顺序无关，过滤了外部模板信号），契约级外部模板拒绝（带有 None/[]/列表的三态表达），没有新字段的旧版负载在不重写的情况下解码（通过生产编解码器解码为 None，读取时行哈希未更改），以及相同可见状态/不同来源追加修订版 2，相同内容则幂等重用。
- 所需的观察行为均已锁定：具体缺失和具体弱状态在更正后保持未验证，没有处置；仅回退的缺失在完整证据下清除；孤立排除测试未更改且为绿色（通过）。

## 命令与观察

- `python -m pytest tests/v2/services/test_fact_correction_gap_reprojection.py tests/v2/services/test_fact_correction_job.py tests/v2/services/test_fact_normalization_persistence.py tests/v2/projections/test_evidence_expectations.py -q` → **123 个通过** (11 + 27 + 39 + 46)，包括原始 D1/更正作业/持久化套件不变。
- `python -m py_compile` 在所有八个已更改文件上 → 正常。本轮未使用 ruff/uvx（超出范围）。
- Schema 快照检查：在任何架构导出、API 或 LLM 表面中 `grep` `EvidenceExpectationV2`/`input_gap_signals` → 无引用；`app/llm` 中的 `model_json_schema` 用法属于不相关的 LLM I/O 契约。**无需重新生成导出的 JSON 架构快照。**

## 阻碍或缺失环境

- 无阻塞性问题。报告的限制：此处无字面上的 `apply_patch` 工具（使用了运行时编辑器，仅限于授权路径）；`tests/v2/storage/test_evidence_expectation_repository.py` 不存在（已使用投影套件位置 — 待所有者确认）；本轮禁止使用 ruff/uvx，因此 my-file lint 仅通过手动审查 + 编译。

## 重运行请求或下一步

- 本轮无需重运行。尚未验证（在授权测试范围之外）：由于契约在响应中是序列化的，API/v2 响应负载现在可能会包含 `input_gap_signals`（附加，向后兼容）；分析/读取期望负载的消费者从未读取过此字段，因此预计是安全的，但 Codex 可能需要运行 API 套件。根据授权，临床/监管验收仍归 Codex 所有。
