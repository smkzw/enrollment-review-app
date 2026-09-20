Trellis SessionStart 已加载。正在读取执行上下文并追踪 `MIXED_DECISION_STAGE_CONTROL` 的完整链路。
# Execution Output: phase5-slice61ab-candidate-repartition-contract-20260828 - worker_01

## Boundary And Context Check

- **Role**: `worker_01` — read-only chain trace; no source edits authorized.
- **Workspace**: bound to `.worktrees/phase5-clinical-facts-profile`.
- **Initial read set consumed**: `context/phase5-slice61ab-candidate-repartition-contract-20260828_execution_context.md`, `plans/codex_execution_phase5-slice61ab-candidate-repartition-contract-20260828.md`.
- **Additional reads** (required to complete trace): gate/deconstructor implementation, saved virology replay artifact, existing tests, prior slice60zz worker report.
- **Hard boundaries respected**: no production writes, no runner report file write, no final acceptance claim.

---

## Work Performed

独立追踪了 `MIXED_DECISION_STAGE_CONTROL` 从发布门禁 → 错误机器范围 → 修复提示 → bounded restore 的完整链路，并用保存的真实病毒学 replay（slice61aa）与代码模拟确认最小通用根因。

### 链路 1 — 发布门禁（检测）

**位置**: `app/protocols/protocol_control_gate.py`

```1918:1954:app/protocols/protocol_control_gate.py
def _check_mixed_decision_stage_control(
    *,
    entity_id: str,
    obligation_expression: object,
) -> None:
    """Split current-stage procedures from future-anchor validity decisions."""
    ...
    if has_future_anchor and has_unanchored_routine_action:
        _fail(
            "MIXED_DECISION_STAGE_CONTROL",
            "筛选期应完成的无锚点操作与基线/随机/首次给药前有效性判定必须拆成不同候选",
            entity_id=entity_id,
        )
```

- **触发条件（证据）**: 同一候选的义务 DNF 中同时存在
  - `time_constraint.anchor_type ∈ {baseline_date, randomization_date, first_dose_date, study_drug_administration_date}` 的原子，且
  - `time_constraint is None` 且 `_ROUTINE_ACTION_RE` 匹配的无锚点常规操作原子（如 `complete_or_verify` + 「将根据标准实验室程序进行…」）。
- **调用点**: `_validate_candidate`（约 L3235）及 catalog 路径（约 L3448）。
- **错误形态**: `ProtocolControlGateError(code=MIXED_DECISION_STAGE_CONTROL, entity_id=<candidate_id>)`；**不携带** `structure_unit_ids` / `candidate_ids` / `allow_candidate_repartition`。
- **测试覆盖**: `tests/v2/protocols/test_slice58c_protocol_control_gate.py`（L1246–1276）、`tests/v2/protocols/test_slice60zz_cross_stage_supplement_contract.py`（L466–470）。

**推断**: 门禁语义正确——要求按「最终决定阶段」拆候选；问题不在检测层。

---

### 链路 2 — 错误机器范围（repair scope 映射）

**位置**: `.trellis/.../slice59n_representative_group_control_replay.py` → `_publication_repair_error` / `_combined_repair_error`（产品 replay 与 `ProtocolControlAgentRunner` 共用此 validator 模式）

```621:629:.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice59n_representative_group_control_replay.py
    return ProtocolControlAgentWireValidationError(
        "PUBLICATION_GATE_REJECTED",
        "\n".join(messages),
        structure_unit_ids=structure_unit_ids,
        candidate_ids=candidate_ids,
        obligation_source_span_ids=obligation_source_span_ids,
        allow_candidate_repartition=any(
            issue.code == "ACTION_TARGET_SCOPE_MISMATCH" for issue in issues
        ),
    )
```

对 `MIXED_DECISION_STAGE_CONTROL`：

| 字段 | 映射结果 |
|------|----------|
| `candidate_ids` | 由 `issue.entity_id` → hydrated `control_candidate_id`（如 `pcc-e8f9d1fedc33e028a6271fad`） |
| `structure_unit_ids` | 来自该候选的 `frozen_structure_unit_ids`（如 `su-3de4633dd1cb5721547f0bb2`, `su-86389bb90acd044a0835089c`） |
| `allow_candidate_repartition` | **`False`**（仅 `ACTION_TARGET_SCOPE_MISMATCH` 为 `True`） |

Runner 收到错误后（`protocol_control_deconstructor.py` L2417–2466）设置：
- `mutable_candidate_source_keys = {(su-3de, su-86389)}`（1:1 来源键替换模式）
- `allow_candidate_repartition = False`

**推断**: 错误机器正确识别了「哪一个候选错了」，但**未授权**「1→N 候选重分区」——与门禁要求的修复动作不匹配。

---

### 链路 3 — 修复提示（Agent 引导）

**位置**: `app/agents/protocol_control_deconstructor.py`

```983:988:app/agents/protocol_control_deconstructor.py
    if "MIXED_DECISION_STAGE_CONTROL" in problem:
        return (
            "本轮重点：按最终决定阶段拆成两个独立候选；当前节点完成的检查/操作与后续节点核对的"
            "结果有效期不得留在同一候选中。不得因此重复建立已由已知目标覆盖的操作候选。"
            ...
        )
```

**证据**（slice61aa attempt 2 repair prompt）: 含「拆成两个独立候选」及完整 MIXED 错误文本。

**推断**: 提示层与门禁意图一致；Agent **确实**按提示拆成两个候选（见下文 artifact 证据）。提示不是瓶颈。

---

### 链路 4 — Bounded restore（静默丢候选）

**位置**: `app/agents/protocol_control_deconstructor.py` → `_restore_bounded_wire_repair`

当 `allow_candidate_repartition=False` 且 `mutable_candidate_source_keys` 非空时，走 **1:1 来源键替换** 分支（L2129–2155）：

```2147:2155:app/agents/protocol_control_deconstructor.py
        candidates = [
            (
                current_by_key[key][0]
                if key in mutable_candidate_source_keys
                else candidate
            )
            for candidate in previous.candidate_drafts
            for key in [tuple(candidate.source_structure_unit_ids)]
        ]
```

**关键机制（证据 + 模拟）**:
- 循环**仅遍历 `previous.candidate_drafts`**，对每个旧来源键最多替换为 `current_by_key[key][0]`。
- Agent 新增的、来源键**不在** `previous` 中的候选（如 `(su-86389,)` 单独 screening 候选）**永远不会进入** `candidates`。
- 若 Agent 对同一来源键产出 2 个候选 → `len(current_by_key[key]) != 1` → `REPAIR_SCOPE_ESCAPE`（fail-closed，非静默）。
- 若 Agent 拆成**不同来源键**（slice61aa 实际路径）→ 唯一性检查通过 → **第二个候选被静默丢弃**。

**保存 artifact 证据**（`artifacts/phase5-slice61aa-virology-cross-stage-contract-20260828/execution/`）:

| 轮次 | 结果 | 候选数（Agent raw / final） |
|------|------|------------------------------|
| Attempt 2 | `MIXED_DECISION_STAGE_CONTROL` on `pcc-e8f9d1fedc33e028a6271fad` | 1 mixed |
| Attempt 3 raw | Agent 返回 **2** 候选 | `(su-86389)` screening + `(su-3de,su-86389)` validity |
| Attempt 3 final | `parsed` + bounded restore | **1** 候选（仅 validity）；issue: 「已由系统原样保留…」 |

Attempt 3 raw 结构（`raw-responses.json[2]`，工具解析）:
- Candidate 0: `source_units=['su-86389bb90acd044a0835089c']`, kinds=`complete_or_verify`
- Candidate 1: `source_units=['su-3de4633dd1cb5721547f0bb2','su-86389bb90acd044a0835089c']`, kinds=`verify_result_validity`

**Python 模拟**（复现 restore 逻辑）:
- `allow_candidate_repartition=False` → restored count **1**, title `validity`; screening **dropped**.
- `allow_candidate_repartition=True` + union `{su-3de, su-86389}` → **both** kept.

**推断**: 最终 `parsed` 是因为剩余单候选仅含 `verify_result_validity`，不再触发 MIXED；**并非**修复成功，而是 screening 义务被 restore 丢弃后 gate 误通过。

---

## Artifacts And Evidence

| 类型 | 路径 / 观察 |
|------|-------------|
| 真实失败→误通过 replay | `artifacts/phase5-slice61aa-virology-cross-stage-contract-20260828/execution/runner-result.json`（attempt 2 FAIL → attempt 3 PASS，final 仅 1 候选） |
| Agent 双候选 raw | `.../raw-responses.json` index 2 |
| 修复 prompt | `.../conversation-history.json` attempt 2 repair message |
| 门禁实现 | `app/protocols/protocol_control_gate.py` `_check_mixed_decision_stage_control` |
| Restore 实现 | `app/agents/protocol_control_deconstructor.py` `_restore_bounded_wire_repair` L2087–2155 vs L2129–2155 |
| 错误映射 | `slice59n_representative_group_control_replay.py` `_publication_repair_error` L627–629 |
| 已有 repartition 测试（不同 gate） | `tests/v2/protocols/test_slice58c_control_deconstructor.py` `test_explicit_candidate_repartition_preserves_authorized_source_union` |
| 修复提示测试 | `tests/v2/protocols/test_slice60zz_cross_stage_supplement_contract.py` L481–486 |

---

## Commands And Observations

```bash
# 解析 attempt 3 raw wire
python3 -c "..."  # artifacts/.../raw-responses.json → 2 candidates, different source keys

# 模拟 bounded restore（False → 丢 screening；True → 保留两者）
python3 <<'PY' ... PY
```

**观察摘要**:
1. Gate、prompt、Agent 行为三方一致要求「拆成两个候选」。
2. Error machine 未设 `allow_candidate_repartition=True`。
3. Restore 1:1 键替换路径只覆盖 `previous.candidate_drafts` 中的键，新增键候选被丢弃。
4. `_validate_bounded_output_repair` 主要比较 **frozen** 候选；mutable 候选数量减少不被其捕获。
5. 发布后二次 gate 只对 restore 后输出校验，故误通过。

---

## Blockers Or Missing Environment

- **无环境阻塞**；分析所需 artifact 与源码均在 workspace。
- **worker_01 范围外**: 实际修复需在共享错误映射中授权 repartition（worker_02）并加回归（worker_03）；当前 `_publication_repair_error` 仅存在于 replay 脚本，若生产路径另有副本需 Codex 确认是否同步（`app/` 内 grep 未发现同名函数，replay 脚本是当前唯一映射点）。

---

## Rerun Requests Or Next Step

### 最小通用根因（证据 + 推断）

**合同冲突**: 发布门禁要求 **1→N 按决定阶段拆分候选**，但 bounded restore 在 `allow_candidate_repartition=False` 时只允许 **1→1 同来源键替换**；Agent 按不同 `source_structure_unit_ids` 拆分时，新增候选被 restore 静默丢弃，剩余单候选可通过 MIXED 复检 → **假阳性 `parsed`**。

### 推荐修复方向（供 worker_02/03，非本 worker 实施）

1. 在 `_publication_repair_error`（或提升到共享模块）中，对 `MIXED_DECISION_STAGE_CONTROL` 设置 `allow_candidate_repartition=True`（与 `ACTION_TARGET_SCOPE_MISMATCH` 同级，不硬编码病毒学词）。
2. Runner 已有 repartition 分支（L2087–2128）可保留 `{su-3de, su-86389}` 全集的两个候选；模拟已验证。
3. 考虑同等授权 **`MIXED_TRIGGER_DECISION_STAGES`**（L989 有类似「拆成不同候选」提示，同一 restore 风险）。

### 相邻风险

| 风险 | 说明 |
|------|------|
| **同键 1→2 拆分** | Agent 若两候选共享完全相同 `source_structure_unit_ids` → `REPAIR_SCOPE_ESCAPE`（fail-closed，非静默，但 repair 仍失败） |
| **MIXED_TRIGGER_DECISION_STAGES** | 触发层跨阶段混合，同样需拆候选，当前亦无 repartition 授权 |
| **REQUIRED_ACTION_DISCARDED 未兜底** | 被丢 screening 候选中的 `complete_or_verify` 可能被视为已被 `required_procedure` 覆盖，不会二次拒绝 |
| **`_validate_bounded_output_repair` 盲区** | 不检测 mutable 域内候选**计数**变化；依赖 gate 复检，而 gate 对「只剩 validity」会通过 |
| **Disposition 链接** | slice61aa attempt 3 raw 中 disposition `linked_control_candidate_ids` 为 null；若双候选保留，需 hydration/链接一致性（worker_03 应覆盖） |

### worker_03 回归建议

- 合成 runner：`MIXED_DECISION_STAGE_CONTROL` + repartition 授权 → 2 候选 hydrated + gate PASS。
- 负例：无 repartition 授权 → 2 候选 raw 输入 → 最终仅 1 候选（复现 slice61aa 静默丢）。
- Artifact replay：`artifacts/phase5-slice61aa-.../raw-responses.json[2]` 作为 golden split 输入。

**Resume point**: worker_02 可在 `_publication_repair_error` L627–629 扩展 `allow_candidate_repartition` 条件；worker_03 加测试与 slice61aa 重放验证。
