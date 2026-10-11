I'll re-read only the listed repair sites and their immediate dependencies, then score D1–D4 as SOURCE PASS/FAIL/UNVERIFIED without repeating the first-pass audit.# Conference Output: r05-formal-publication-actions-20260914 - evidence_single_object

## Output

Same-session source follow-up only. No tests, no runtime, no edits. Not product acceptance.

Owner boundaries vs this code: **not contradicted**. `unfulfilled` still has no ActionRequest; mandatory unresolved still uses existing BLOCKING; `accepted=false` remains on the calculation object; publication still requires a stored `review-method-adoption` gate and is still unregistered/uninvoked. Do not open that HTTP path for demonstration.

### SOURCE scores

| Concern | Score |
|---|---|
| D1 争议组成员 ≠ `SOURCE_CONFLICT` 待办 | **PASS** |
| D2 未知 activation → 一组一条 | **PASS** |
| 义务/组身份在字符串相同时可区分 | **PASS** |
| D3 嵌套 rollback 不吞失败 | **PASS**（仍 raise） |
| 同键回执 | **PASS**（提交后重试）；嵌套内 unique 竞态见残缺 |
| 历史 gate 核对 | **PASS**（本修复后新写入） |
| D4 前端条件/状态 + 期望待办 | **PASS**（身份覆盖；gap_type 未纳入键） |
| 迁移/组列 DDL | **UNVERIFIED**（按边界未跑） |

### Evidence（仅本轮改动）

- `control_action_targets`：同组 `activation` 必须一致；`UNKNOWN` 只发 `(obligation_id=None, obligation_group_id=group_id)` 一条然后 `continue`；其余仅 `status=="unverified"` 发义务级目标；`gap_type` 固定 `OBSERVATION_UNVERIFIED`，不再读 `source_conflict`。
- `ControlActionOrigin`：`obligation_id` 与 `obligation_group_id` 恰好一个非空。待办 `action_id` / `gap_key` / 列镜像都带这一对。
- 发布与历史期望共用 `control_action_targets`。历史在读当前 action 时核 `gate.output_hash == canonical_hash(action.model_dump())`。
- `publish_frozen_review.prior_result()` 在入口和 `run` 已存在时都会重读同键回执；`status` 必须已完成。
- `_flush_guarded`：有 nested 则 `savepoint.rollback()`，否则 `session.rollback()`，随后 **总是** 转成 `DuplicateRecordError` / `InvalidReferenceError` / `RepositoryError`。
- 前端：组内 activation 一致、status 由 activation/observation_truth 重算；完成态 `expectedControlActions` 对 unknown activation 收成 `[controlId, null, groupId]`。

### 残缺（有行号）

1. **同键、双方都已越过 `get_or_none(run)` 进入 `begin_nested`：** unique 冲突走 `_flush_guarded` → `DuplicateRecordError`，**不会**再调 `prior_result()`（`frozen_review_publication.py` 110–169 vs 91–95）。不是静默成功，但是同键并发仍不能回到已有回执。
2. **`_flush_guarded` 回滚的是当前 innermost nested**（`repositories.py` 187–198）。若该 savepoint 就是发布用的 `begin_nested`，失败会拆掉整批发布后再 raise。`with begin_nested()` 退出时是否二次 rollback：**UNVERIFIED**。
3. 前端期望待办键不含 `gap_type`（`reviewHistoryHttp.ts` 853–863）。与当前指令（只产 `observation_unverified`）一致；篡改后的 `source_conflict` 控制待办不会在解码层被拒。
4. `ControlActionOrigin` 不会省略空的那一侧字段。本修复之后的首次写入两边都有键，历史 gate 对得上。若存在**修复前**只含 `obligation_id` 的控制待办，decode 后再 dump 会多 `obligation_group_id: null`，历史 gate 会 fail-closed。是否有这种行：**UNVERIFIED**。条款待办仍 `pop("control_origin")`，不受影响。
5. 组列/CHECK 已出现在 `models.py` / `_action_columns`；迁移未跑：**UNVERIFIED**。

### Inference

D1–D4 在源码上是同一套目标函数贯穿发布、校验、历史闭包和前端期望，方向一致。未发现「组目标与义务目标因同名 ID 撞车」或「unfulfilled 被编成缺证待办」。

### Recommendation

保持发布入口关闭。残缺 1 不是演示理由。迁移只在隔离库做。

本角色不宣布最终接受。
