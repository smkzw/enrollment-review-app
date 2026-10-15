# Phase 5.8d 期别语义紧凑输出执行上下文

## 目标

在不改变逐结构单元最终处置、来源证据和发布门禁的前提下，允许期别语义 Agent 将同一冻结包内“处置、候选证据和理由完全相同”的多个目标分组返回，由系统确定性展开为现有逐单元结果，消除重复 JSON 生成造成的数小时运行成本。

## 已确认现状

- D001 II 结构修复后：1,689 个单元，1,284 个仍需语义处置，217 批。
- 首个 12 单元批次通过真实本地模型和全部 gate，但模型输出约 13,893 字符，即每单元约 1,158 字符，耗时约 194 秒；12 个结果全部是相同的跨期共用处置。
- 最终领域合同、稳定身份、EvidenceSpan 归属和每单元 publication gate 必须保持不变。
- 旧 v1 provider wire 和既有失败/验收工件应可读；新真实调用应使用紧凑 v2 schema。旧 checkpoint 因 prompt/schema hash 变化必须失效，不得静默续跑。

## 设计边界

- 分组只是一种 provider 输出压缩，不是批量裁决捷径。系统展开后，每个 owned unit 仍有唯一 `PhaseApplicabilityUnitResolution`、稳定 resolution/evidence/candidate 身份和完整 gate。
- 一个分组必须显式列出排序唯一的 `unit_indexes` 及逐项对应的 `structure_unit_ids`，并通过系统冻结身份逐字核对。
- 分组证据仍只能引用冻结包内真实 source unit/span index，摘录仍须逐字回源。
- 同一包内不同处置、不同证据或不同未决原因必须分组；不能为了压缩把异质目标混在一起。
- v2 解析后在进入现有 hydration/gate 前展开为逐目标 v1 内部形状，避免改动领域发布合同。
- 不硬编码 D001、章节名、结果或模型。

## 允许修改

- `app/agents/phase_applicability.py`
- `app/protocols/phase_applicability.py`（仅确有必要）
- `app/domain/contracts/phase_applicability.py`（仅确有必要）
- `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py`
- `tests/v2/protocols/test_phase_applicability_live_execution.py`
- `tests/v2/protocols/test_phase_applicability_contract.py`
- `scripts/run_phase_applicability_acceptance.py`
- 当前执行记录、Trellis 研究与检查点。

## 完成证据

1. v2 严格 schema、解析、身份回显和分组展开测试通过；v1 历史输出仍可解析或有明确受控迁移。
2. 分组展开后的现有 hydration/gate 对每个 owned unit 逐项通过，伪造/漏项/重复/异质分组被拒绝。
3. 使用修复后的真实 D001 首批 12 单元运行本地系统 Agent；与既有逐项路线结论一致，输出字符数与耗时显著下降。
4. 再选至少一个非纯元数据批次验证分组不会掩盖异质处置；失败必须保留为未接受状态。

