Trellis SessionStart 已加载。正在读取执行上下文并审查 `protocol_control_deconstructor.py` 中的同源多候选有界修订逻辑。
定位到问题：`_restore_bounded_wire_repair` 在按 wire 位置恢复后会重新排序，破坏了同源多候选的身份。正在应用最小修复并补充测试。
# Execution Output: phase5-slice61ag-conditional-waiver-scope-20260828 - worker_02

## Boundary And Context Check

- **Role**: `worker_02` — bounded first-line executor for item 2 (同源多候选有界修订身份保持审查与最小测试).
- **Workspace**: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`
- **Initial read set consumed**: `context/phase5-slice61ag-conditional-waiver-scope-20260828_execution_context.md`, `plans/codex_execution_phase5-slice61ag-conditional-waiver-scope-20260828.md`
- **Authorized edits**: `app/agents/protocol_control_deconstructor.py`, `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`
- **Out of scope**: 真实模型调用、控制点发布、临床来源修改、`protocol_control_gate.py`（worker_01）、v6 p804 重评（worker_03）
- **No report file written** — runner persists from this response.

## Work Performed

### Code review: `_restore_bounded_wire_repair` (同源多候选路径)

审查焦点为 `mutable_candidate_indexes` 分支（约 L2143–2217）及 runner 如何把 gate 错误映射到 `mutable_candidate_indexes`（约 L2499–2587）。

| 场景 | 机制 | 结论 |
|---|---|---|
| **乱序返回** | 非 mutable 索引先在 `remaining_current` 中做 `==` 精确匹配并移除；mutable 索引按 `source_structure_unit_ids` 从剩余池取替换 | **正确** — 已有 `test_same_source_candidate_repair_uses_bounded_wire_position` |
| **兄弟候选被改写** | 非 mutable 索引要求 `len(exact_matches)==1` 且内容完全一致 | **正确** — 已有 `test_same_source_candidate_repair_rejects_modified_sibling` |
| **重复/增删候选** | 候选数变化直接拒绝；frozen 重复导致 `exact_matches!=1` | **正确** — 新增反例测试 |
| **wire 位置身份** | 修复后原先**无条件**按 `(source, title, json)` 排序 | **缺陷** — 同源兄弟 title 字典序与 wire 序不一致时互换位置，破坏 `candidate_indexes` 身份 |

### 最小修复

在 `_restore_bounded_wire_repair` 末尾：当 `mutable_candidate_indexes` 非空时**跳过**最终排序，保留 wire 位置键控修复后的顺序。非 position-keyed 路径仍排序以保证确定性。

### 测试补充

- 新增 `_two_same_source_candidates_wire()` 辅助构造两个同 `su-02` 来源、不同 wire 位置的候选。
- 新增 3 个回归测试（乱序+title 陷阱、重复 frozen、乱序+计数膨胀）。
- 重构 2 个已有测试复用 helper。

## Artifacts And Evidence

### 修改文件

1. **`app/agents/protocol_control_deconstructor.py`** (~L2288–2298)  
   - 条件化最终 `candidates` 排序：`if not mutable_candidate_indexes:`

2. **`tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`**  
   - `_two_same_source_candidates_wire()`
   - `test_same_source_position_repair_preserves_wire_order_when_titles_sort_differently`
   - `test_same_source_position_repair_rejects_duplicate_frozen_candidate`
   - `test_same_source_position_repair_rejects_out_of_order_count_change`

### 关键逻辑（修复后）

```2288:2298:app/agents/protocol_control_deconstructor.py
    # ponytail: skip sort when repair scope is wire-position keyed; title/json
    # sort would swap same-source siblings and break candidate_indexes identity.
    if not mutable_candidate_indexes:
        candidates = sorted(
            candidates,
            key=lambda item: (
                tuple(item.source_structure_unit_ids),
                item.title,
                _stable_json(item.model_dump(mode="json")),
            ),
        )
```

### 缺陷证据（修复前）

交互探测：两个同 `("su-02",)` 候选，wire 序 `[Z-冻结, A-待修订]`，乱序返回 `[A-已修订, Z-冻结]`，`mutable_candidate_indexes={1}`。修复前排序后变为 `[A-已修订, Z-冻结]` — wire index 0 不再是冻结候选。

## Commands And Observations

| Command | Result |
|---|---|
| `pytest tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py -q` | **20 passed** |
| `pytest tests/v2/protocols/test_slice61ab -k "same_source or position"` | **8 passed** |
| `pytest test_slice58c::test_post_hydration_repairs_roll_forward_without_cross_candidate_regression` | **FAILED（修复前亦失败）** |

**环境**: 系统 `python3` 缺 `sqlalchemy`；使用主仓库 venv  
`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.venv/bin/python3`

**审查推断（非本次修复范围）**:

1. **`_candidate_ids_from_wire` 恒用 `candidate_ordinal=0`**（L2331）— 若 wire 上存在语义指纹相同的同源重复候选，`candidate_id → wire_index` 映射可能歧义；当前 gate 在 wire 层拒绝 `DUPLICATE_CANDIDATE`，风险边界可控。
2. **`test_post_hydration_repairs_roll_forward_without_cross_candidate_regression`** 在**不同来源**（`su-01`/`su-02`）跨轮修复场景下，`mutable_candidate_indexes` 路径先处理非 mutable 索引时，若响应中含已改写的 frozen 兄弟，会在 `exact_matches` 阶段触发 `REPAIR_SCOPE_ESCAPE` — 为**既有失败**，与本次同源修复无关；建议 worker_01/后续 slice 单独处理跨源 roll-forward。

## Blockers Or Missing Environment

- 无阻塞。测试需项目 venv，非 workspace 内 `.venv`。
- 未运行真实模型或完整方案层回归（assignment 禁止）。

## Rerun Requests Or Next Step

**Codex 验收建议**:

1. 确认 position-keyed 修复跳过排序的行为符合产品契约（wire index 优先于 title 字典序）。
2. 评估是否将 roll-forward 测试失败纳入 slice61ag 后续工单（跨源 sequential repair，非同源）。
3. 可选：为 `_candidate_ids_from_wire` 增加与 hydration 一致的 ordinal 分配，覆盖极端同源重复指纹场景。

**Resume point**: 无 — worker_02 分配项已完成；待 Codex 合并审查与 peer worker 输出。
