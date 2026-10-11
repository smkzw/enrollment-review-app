All checks complete. Final focused verdict:

# Conference Participant Output: phase3-slice1-acceptance - general_pi_qwen38

**(Continuation round 4 — focused C1 closure check. Prior rounds: P1 defects, P2 remediation verification + C1–C4, R2 513+18 baseline + N1/N2, R3 C1 closed + N1 anomaly.)**

## Boundary Check

- 仅审查，未修改任何文件；探针写 OS 临时目录，源文件只读（哈希/大小/mtime 前后一致）。未读取其他参与者输出；探针仅结构统计，未接触临床内容。
- 本轮聚焦范围按 Codex 要求：C1 是否关闭、修复是否引入新 P0/P1、C2 作为显式非权威页限制下切片 1 → 2 是否可放行。

## Independent Work Product

### 1. C1 关闭确认（独立复测，非仅依赖测试）

对两份真实方案独立重跑完整提取→渲染→对齐→碰撞后处理，并复核 Codex 声称的三层防护：

| 检查项 | MG-K10-SAR | CMS-D001 | 结论 |
|---|---|---|---|
| TEXT_RANGE span 数 | 808 | 860 | — |
| 剩余 TEXT_RANGE 中共享 (artifact,page,start,end) 的碰撞组 | **0** | **0** | ✅ 无残留 |
| 碰撞降级 span 数 | 48 | 64 | 与 R2 修复前碰撞 span 数**完全一致**（48/64）→ 降级精确命中、无多无少 |
| 降级后仍带 render_page/text range | **0** | **0** | ✅ 降级彻底（BLOCK/UNALIGNED/无页） |
| 剩余 TEXT_RANGE 页级核验失败数 | **0** | **0** | ✅ 每页可核验 |
| 降级 span 构成 | 26 表格格 + 22 其他 | 39 表格格 + 25 其他 | 表格格占多数，符合 R2 碰撞样本分布 |

三层防护逐项确认：① `align_blocks` 内 `range_counts → collision_keys → model_copy` 确定性降级（`app/protocols/source_alignment.py`，读取核对）；② 合成回归 `test_two_blocks_cannot_claim_the_same_physical_text_range`（两块同文本×渲染单实例 → 均非 TEXT_RANGE）；③ 真实方案回归 `test_real_protocols.py` 新增断言：所有 `text_range` span 必须页级可核验 + `claimed_ranges` 唯一（读取核对）。

套件复跑：`tests/v2/protocols` = **47 passed**；全仓 = **514 passed + 18 subtests + 1 skip**（skip 仍为遗留 OCR 缓存夹具）— 与 Codex 声明逐项一致。

### 2. 修复是否引入新 P0/P1：未发现

针对降级后处理的潜在副作用逐项核查：

- **误降级**：碰撞键仅含四字段全非空的精确 span（guard `render_artifact_id and render_page is not None …`）；降级循环用 `or ""`/`or 0` 对非精确 span 生成的键不可能与真实键重合（render_page ≥ 1，0 不可达）— 无 None 折叠误伤。实测降级数 == 修复前碰撞 span 数，证实无多降。
- **页级核验一致性**：降级 span 的 `text_start/text_end/render_page` 置 None 后 `verify_excerpt_against_page` 按设计返回 False，与真实回归的断言范围（仅精确 span）不冲突。
- **切片 2 影响**：页眉/页脚 span 为 `PAGE_EXCERPT/DEGRADED`（无字符范围），不进入碰撞键 → 身份提取来源不受影响。
- **性能/确定性**：O(n) 字典遍历、纯函数、无随机 — 与既有确定性门禁原则一致。
- 代价面（非缺陷）：48/64 个 span 由"精确"转为"无页 BLOCK"，并入 C2 覆盖率缺口 — 这是精度优先于召回的正确取舍，方向安全（诚实拒绝，不产生虚假精确）。

### 3. C2 作为显式非权威页限制：切片 1 → 2 可以放行

判定：**可以放行**，附三个条件。理由：

- C2 是**覆盖率（召回）限制**而非正确性缺陷：1954/2120（MG/D001）非空正文段落无页定位，全部为诚实拒绝（重复文本/未命中），无任何 span 携带未经验证的页。方向安全：宁缺勿假。
- C2 已被量化（R2/R3 实测：unaligned 2451/2690 中非空段 1954/2120；插值可行 1952/2119，邻居页差 median=1/p90=8）且**不扩散**：修复后碰撞归零，剩余无页块均为单块语义（多命中或未找到），非系统错配。
- 放行条件：
  1. **显式记录**：把 C2 写入切片 1 验收记录与 `context/` Source Of Truth（"对齐层页级定位覆盖缺口：~60% 非空正文段落无页，全部为诚实拒绝；页定位仅对全局唯一 TEXT_RANGE/唯一 PAGE_ONLY 声称精确"），避免切片 3 误当缺陷排查。
  2. **切片 3 门禁前置约束**（安全暂定路径，零代码即可）：目录构建器只信任"全局唯一 TEXT_RANGE / 表格唯一 PAGE_ONLY"为权威页；其余（DEGRADED 候选页、插值页）仅作提示，不构成 `source_coverage` 发布门槛依据。
  3. **插值 spike 列为切片 3 开工条件（P1）**：带门槛邻块插值（邻居页差 ≤ p90 才插值，标 DEGRADED）——已实测可行性，但需实现后验证恢复率与误差带；R3 的 N1 约束（block_order 非页序代理，缩略语表逆序可达 182 页）必须作为插值门槛的硬约束，禁止无条件插值。

### 4. 遗留项最终清单

| 项 | 状态 | 分级 |
|---|---|---|
| C1 共享范围碰撞 | ✅ 关闭（本轮独立复测 + 三层防护确认） | — |
| R1–R5（猜页/哈希/字距/页核验/渲染覆盖） | ✅ 关闭 | — |
| C2 无页块覆盖率 | 🔶 显式已知限制，放行切片 1→2 | P1（切片 3 前置） |
| C3 页级核验器接入真实回归 | ✅ 关闭（本轮确认已接入 `test_real_protocols.py`，即 R4 的接线缺口） | — |
| C4 页眉 DEGRADED vs 切片 2 身份来源 | 🔶 开（切片 2 契约文字） | P2 |
| N1 block_order 非页序代理 | 🔶 开（作为 C2 插值门槛约束） | P1（随 C2） |

## Evidence And Assumptions

**直接观察（本轮）**：
- 探针 MG/D001：TEXT_RANGE 808/860、碰撞 0/0、降级 48/64（与 R2 碰撞 span 数一致）、降级后带页 0/0、页级核验失败 0/0。
- 套件：47 protocol passed；全仓 514 passed + 18 subtests + 1 skipped（41.3s）。
- 代码：`align_blocks` 碰撞后处理（读取核对）；`test_real_protocols.py` 新增唯一范围 + 页级核验断言（读取核对）；`test_source_alignment.py` 含 `test_two_blocks_cannot_claim_the_same_physical_text_range`。

**推断（未直接观察）**：
- [INFERENCE] 降级 span 的真实物理实例被渲染或提取管线丢弃（未逐对归因到具体层）— 但降级正确性不依赖归因：任一实例被丢弃即意味着至少一个块定位是借用的，降级两者是唯一无错答案。
- [INFERENCE] 全仓 514 = R2 的 513 + C1 回归测试 1 项；无其他新测试（文件集未变）。

**不确定性**：C2 插值在实现后的实际恢复率与误差带未实测（建议切片 3 spike）；降级 48/64 个 span 中"被丢实例"的真实页未逐对读取（避免接触临床内容）。

## Risks, Gaps, And Verification Needs

| # | 缺口 | 影响 | 建议 | 分级 |
|---|---|---|---|---|
| C2 | 1954/2120 非空段无页（诚实拒绝） | 切片 3 目录页级来源覆盖率缺口；重复必做项无页 | 显式记录 + 门禁只信权威页 + 门槛化插值 spike | P1（不阻断 1→2） |
| N1 | block_order 非页序代理（逆序 ≤182 页） | 无条件插值会错配页 | 插值门槛（≤p90 页差）+ 逆序检测 | P1（C2 前置） |
| C4 | 页眉 DEGRADED vs 切片 2 身份来源 | 身份候选来源被误读 | 切片 2 契约显式区分身份来源与规则级来源 | P2 |

## Recommended Next Step

**裁决结论**：C1 **关闭**；修复**未引入新 P0/P1**；切片 1 **可放行至切片 2**，以 C2 为显式非权威页限制并满足三个放行条件（显式记录、切片 3 门禁只信权威页、插值 spike 列为切片 3 开工条件）。

**给 Codex 的有界问题**：
- Q1：是否接受将 C2 显式写入切片 1 验收记录（含 1954/2120 数字与"诚实拒绝"语义），并以此作为切片 3 `source_coverage` 门禁"权威页 vs 提示页"分级依据？
- Q2：门槛化插值 spike（恢复率 + 误差带，纯结构统计）是否授权在切片 3 开工时执行，并将 N1 的逆序检测作为插值硬门槛？
- Q3：C4（页眉身份来源语义）是否随切片 2 契约一并落文字，还是由 Codex 直接裁决？

**安全暂定路径**（若 Q1/Q2 未答即继续）：切片 3 构建器对 span 分级信任——全局唯一 TEXT_RANGE / 唯一 PAGE_ONLY 为权威页；其余页定位一律 DEGRADED 提示、不构成发布门槛依据；插值默认关闭直至 spike 验证通过。
