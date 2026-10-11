Reading the declared windows (6-read cap; I'll declare the one window the cap forces me to leave unread).

# Conference Output: rv1006-restricted-registration-context-review-20261008 - evidence_single_object

## Output

### 0. 直接回答四问（在已读范围内）

| 问题 | 回答 | 性质 |
|---|---|---|
| 有无“绕过损坏/有效历史回执”的路由？ | **未发现**。该选项的入口条件是三重合取：源步骤**存在**、`state == "failed_final"`、`get_last_checkpoint(...) is None`（`protocol_control_execution.py:2762-2765`，否则抛“不得跳过已有或损坏回执”）；无确认时默认路径仍硬拒绝（测试 `:4830-4836` 三种情形全部 409，且 `deep.start_calls` 不变、旧历史指纹不变） | 确定性（源码 + 测试断言） |
| 有无“猜测来源身份”的路由？ | **未发现**。绑定链：源 Job ID（冻结进新 Job payload）+ 步骤 ID 必须 ∈ **当前**完整分包步骤集（`:2837-2838`）+ 该步骤必须**真实存在于源 Job**（`:2762-2763`，缺失即抛，不会“当作缺失”）；源计划与当前清单/发现计划的身份另行比对（`:2796-2803`）。残留：源↔当前**批次组成的逐批材料比对**在“被显式点名”分支中未执行（见 §3 B1，条件性、非复用风险） | 确定性 + 1 项条件性 |
| 有无“复用该失败输出”的路由？ | **未发现**。证明自带 `reused: False`（`:2769`）；执行期若该证明存在，`decision != "refresh_required"` 直接拒绝（`:3716-3717`，文案“缺记录范围不得复用”）——即**复用不是被劝阻，而是不可达**；被点名分支只写 `refresh_required` 并 `continue`（`:2847-2854`），根本不进入任何复用判定 | 确定性 |
| 有无“在已确认的源状态变化后仍然发起请求”的路由？ | **未发现**。执行期用**新 session**重新派生证明并要求**全等**（`:3714-3723`），不等即 `retryable=False` 的 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`，发生在任何 reader 之前（`:3725-3726`，`checkpoint_id, saved = None, None` 在 `:3727`）。测试 `state_changed` 直接验证：追加回执后新 Job `failed_final`、**0 次额外模型调用**（`:4864-4867`） | 确定性 |
| “正常成功仍能存活、且被选中的缺失失败确实被重读？” | **是（计划级 + 步骤级）**：同一计划中 `deep_0001 = reusable` 与 `deep_0002 = refresh_required` 并存（`:4840-4843`）；新 Job 的 `deep_0002` 落盘新检查点 `stage == "deep"`（`:4870`）且模型调用恰好 +1（`:4871`），旧 Job 保持 `failed_final` 且指纹逐字节不变（`:4863, 4872`） | 确定性；**精度限制见 §5-1** |

**结论：在本次声明的读取窗口内，未确认存在复用/绕过类安全或正确性缺陷。** 仅有两项低危、条件性条目（§3），均不构成复用或身份旁路。

---

### 1. 机制证据（逐点可复核）

**入口与请求面**
- `StartProtocolControlExecutionRequest`：`source_job_id`、`deep_source_job_id`、`recompute_missing_diagnostic_steps: list[str]`（`app/api/v2/protocol_control_schemas.py:14-19`）；schema 只约束字符串元素类型，**真正的范围门在服务层**。
- 路由无旁路：唯一入口把字段原样透传（`app/api/v2/protocol_control.py:39-46`），无第二处写入点；`created=False` 仅改状态码为 200（`:47-48`）。
- 服务层格式与耦合门（`execution.py:487-495`）：去重、长度 9、`deep_` 前缀、`step[5:].isdigit()`、且非空**必须**同时给出 `deep_source_job_id`，否则 422 `PROTOCOL_CONTROL_RECOMPUTE_SCOPE_INVALID`。
- （已考虑并关闭的旁路尝试）`str.isdigit()` 接受 Unicode 数字（如 `deep_٠٠٠١`），但该形态会在**当前分包步骤集**的 ⊆ 判定（`:2837-2838`）被拒；即真正起作用的门是集合包含，不是字符形态——**收敛于拒绝**。

**冻结证明（源侧事实）**
- 字段：`source_job_id / step_id / source_job_payload_sha256 / state / error_code / missing_diagnostic: True / reused: False`（`:2766-2769`），全部来自 `JobStore` 实读，不含任何模型声明。

**计划构建（复用计划冻结）**
- 每批次默认 `refresh_required` / `new_or_incomplete_batch`（`:2842-2843`）；`reusable` 只可能来自其后仍在执行正向校验的分支（如 `:2857-2858` 的 completed 分支）——因为默认值已在循环开头写死。
- 被点名分支：取证明 → 决策 `refresh_required`、原因 `missing_failed_diagnostic_explicit_recompute`、附冻结证明 → `continue`（`:2847-2854`）。
- 旧批次按**批次号**建索引（`:2824-2826`），并在“批次定义缺失”时抛错（`:2855-2856`）。

**执行期复核（任何 reader 之前）**
- 自引用拒绝：`deep_source_job_id == context.job_id` → 拒绝（`:3699-3700`）。
- 逐批绑定：计划条目必须存在且 `entry["step_id"] == context.step_id`（`:3704-3708`）；`decision` 必须 ∈ 四值集合（`:3710-3713`）。
- 证明存在 ⇒ 必须 `refresh_required`（`:3716-3717`）+ 新 session 重派生全等校验（`:3718-3723`），否则 `retryable=False`（`:3725-3726`）。

---

### 2. 正向案例（本轮新增）

1. **被点名不改变其它批次的判定（单调性）**：`acknowledged` 集合**仅在** `:2847` 被读取；所有批次初值均为 `refresh_required`。因此新增选项对复用的影响只能是**收窄**（把一条原本抛错的路径改为 refresh），不可能把任何其它批次翻转为 `reusable`。这是可结构性陈述的反扩宽性质。
2. **“有回执就不能用此选项”以行存在性为准**：测试 `existing_diagnostic` 让失败步骤带一个**内容损坏**的诊断（`{"damaged": True}`，`:4820`），仍被拒（`:4830-4836`）——说明判据是**回执行在**，不是回执可读性。
3. **拒绝路径零副作用**：三种拒绝情形均断言 `deep.start_calls` 不变与旧 Job 检查点指纹不变（`:4834-4835`）。
4. **新版本 Job 隔离**：证明与决策冻结在**新** Job 的 payload（测试经 `deep_reuse_plan.decisions` 读回，`:4838-4843`），旧 Job 保持 `failed_final`（`:4863`）；`retryable=False` 使新 Job 在状态变化时**直接失败**而非半成功（`:4865-4866`）。
5. **不是缓存未命中**：`reused: False` 是**证明内的冻结事实**（`:2769`），并由执行期决策门强制（`:3716-3717`），而不是由“找不到缓存”推导出来的默认。

---

### 3. 具体条目（低危／条件性；均非复用或身份旁路）

**B1（条件性·记录完整性，非阻断）— 被点名分支的证明按**批次号**与源批次对齐，未比对批次材料**
`evidence`：旧批次以 `old_batches_by_number`（`:2824-2826`）按号索引；被点名分支（`:2847-2854`）**不读取** `old_batch`，也不执行材料比对即写出证明。
`可达条件`：当前重建计划的第 N 批与源计划第 N 批拥有不同的原文单元集。前置身份门（`:2796-2803` 的 `coverage_manifest_id` / `discovery_plan_id` 相等，及 `:2782` 的 `_require_compatible_deep_source`）很可能已排除该情形；仅当 `max_deep_units_per_batch` 等**服务端配置**在两轮之间变化时仍可能成立——而该函数体不在我的窗口内，故列为条件性。
`后果`：**不会复用任何失败输出**（该分支恒为 `refresh_required`），但审计记录可能把“源 第N批 的失败状态/载荷哈希”与“当前 第N批 的单元集”配对呈现，形成**来源标注不准**。
`最小修复（1–2 行）`：在被点名分支补一次批次材料一致性判定（源 `old_batch.owned_structure_unit_ids` == 当前 `batch.owned_structure_unit_ids`，不等即抛），或把源批次的 owned IDs 一并写进 `missing_failed_diagnostic_proof` 以便审计核对。
`为何不升级`：无复用、无模型调用、旧历史不变；按此窗口“不为假想问题做通用框架改造”的边界，仅登记为可选加固。

**B2（规则一致性·条件性）— “损坏回执”的判据是 `get_last_checkpoint(...) is not None`，其坏数据的返回语义未在窗口内可证**
`evidence`：`:2764` 的单一判据；`:2765` 的文案却声明“不得跳过**已有或损坏**回执”。
`未证点`：若 `JobStore.get_last_checkpoint` 对**不可读/哈希不符**的行返回 `None`（而非抛错），则该选项会对一个“存在但损坏”的回执放行。注意后果方向是**安全的**：该回执不会被读取，批次走全新实读；受影响的仅是“缺失”这一事实陈述的准确性。
`最小修复（2 行，可选）`：让证明区分“无回执行”与“有行但不可读”（例如用专门的计数/存在性查询），后者抛错。
`定位`：`JobStore` 实现不在我的窗口内 → 见 §4。

---

### 4. 未读限制（精确）

1. `tests/v2/api/test_protocol_control_execution.py:111-139` —— **6 次读上限所限未读**。代价：缺少 HTTP 边界的端到端断言（请求字段被接受/拒绝的线上形态）；我以 `protocol_control.py:39-46` 的接线 + schema `:19` 替代。Owner 报告的 API 6 项通过我**无法核实**。
2. `execution.py:2859-2900+`（`_preflight_deep_source` 决策循环其余部分：completed/reusable 分支与“failed 且无检查点”的默认拒绝实现）—— 我只见默认值（`:2842-2843`）与测试结果（`:4830-4831`），未见拒绝的**代码**。
3. `_require_compatible_deep_source`（`:2782` 调用点）函数体 —— 决定 §3 B1 是否可达（是否比对批次组成与 `max_deep_units_per_batch`）。
4. `JobStore.get_last_checkpoint / list_steps / get_job().payload_sha256` 实现 —— 决定 §3 B2。
5. `execution.py:3730+` 的决策分派（`refresh_required` 分支对新 Job 的实际取数行为）—— 决定“fresh read”在实现层的完整形态（计划级与步骤级已由测试覆盖）。

**Owner 先前四项答复的处理**：Q1/Q2/Q4 属我**本轮未复读窗口**的内容（`_replay_checkpoint`、`_same_deep_batch_material`、`validate_source_interpretation` 均不在本轮读集），我按 owner 报告接受，且与本轮窗口内可见的证据**不冲突**（`reused: False`、`refresh_required` 强制、`state_changed` 零调用）。Q3（两处提示词故意保留同一窄告诫、本窗口不做常量重构）接受，我 pass-2 的去重建议**撤回**。

---

### 5. 证据边界与不认证声明

1. **“正常成功存活”的精度**：测试在 `deep_0002` 步骤后即 `runner.request_stop()`（`:4851-4855`），随后断言 `current.state == "queued"`（`:4869`）。因此已证的是**计划级共存 + 步骤级新检查点 + 恰好一次新模型调用**，**不是**端到端完成的 Job。这与 owner “full connected validation still pending”一致。
2. Owner 的“6 可复用/84 新读、DB 哈希不变、0 模型调用”是**只读预检的所有者报告**；我按报告对待，不作为模型调用证据，也不作为临床准确性。
3. “源原始状态与哈希是**来源事实**，不是声明的 `verified=true`”——与我在窗口内读到的实现一致：证明写的是 `state`/`error_code`/`payload_sha256`/`missing_diagnostic`/`reused=False`，**没有任何 `verified` 断言**（`:2766-2769`）。
4. 我不认证任何测试计数（488 / 6 / 12 / 最终窗口），也不认证临床准确性；本报告仅覆盖来源/回执/重读边界。

---

### 6. 有界问题与建议（均低成本，无框架级要求）

**Q1（唯一会影响 §3 B1 定性的读）** —— `_require_compatible_deep_source` 是否已将“深审批次组成 + `max_deep_units_per_batch`”纳入源↔当前载荷兼容性？若是，B1 关闭（不可达）；若否，建议落 1–2 行批次材料断言或把源批次 owned IDs 写进证明。
**Q2（决定 B2）** —— `JobStore.get_last_checkpoint` 在**行存在但载荷不可读/哈希不符**时是**抛错**还是返回 `None`？若为后者，建议让证明区分“无行”与“有行不可读”。
**Q3（决策记录，非缺陷）** —— 建议在决议中写明：被点名分支**不要求**与源批次材料一致（因恒为 refresh）；这是有意的**成本取舍**还是遗漏？无论哪种，我都**不建议**为此做通用校验框架。
**Q4** —— 建议把“计划级 `reusable` + `refresh_required` 共存”与“步骤级恰好一次新模型调用”作为本窗口的**验收证据**记录在案，并把“未达到端到端 Job 完成”显式写入验收未完成项，避免后续把步骤级证据当成 Job 级通过。

**未新增任何安全/通用框架要求，未要求重跑整包。** 临床采用、完整 Job 成功与最终交付不由本角色裁定。
