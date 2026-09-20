# Execution Output: phase5-slice58d-table-cell-phase-context-20260825 - worker_03

## Boundary And Context Check

- 仅使用工作区内 D001 隔离只读副本；未修改外部原始 DOCX、生产路径或 runner report。
- 系统 Python 3.9 不兼容项目类型注解，改用已有 `.venv/bin/python`（3.12.13），未安装依赖。

## Work Performed

- 增加表格单元格合成反例：
  - `PGA评分 3/4级；访视周数 2/3` → `unknown`
  - `2/3期临床研究`、`II/III期` → `mixed`
  - 普通数字斜杠在明确 `Ⅱ期` 单元格标题后仅继承 `phase_ii`。
- 增加 D001 隔离副本只读重建测试，核对单元、批次32、表5及源文件完整性。

## Artifacts And Evidence

修改文件：

- `tests/v2/protocols/test_metadata_phase_slice2.py:914`
- `tests/v2/protocols/test_real_protocols_slice2.py:249`

D001 当前重建结果：

- 结构块：3581
- 期别图块：3405
- 覆盖单元：1840
- 待语义处置单元：1313
- 批次：220
- `claims_full_coverage=false`

冻结旧结果对比：1689 单元、1433 待处置、235 批；当前变化为 `+151 / -120 / -15`。

批次32：

- 12 个 owned units
- 12 个唯一 `structure_unit_id`
- 当前已按更细粒度表格成员拆分，来源引用序列与旧冻结批次不同。

表5：

- 保留 `body.t5.r0`–`body.t5.r38` 共39行
- 241个成员来源引用，全部唯一
- 39个行聚合、10个列聚合
- II期投影保留10列 `body.t5.c0`–`body.t5.c9`
- 39行均为 `phase_ii`

源文件：

- SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 大小：405567 bytes
- 前后哈希、大小、mtime 完全一致
- 与工作区冻结元数据中的源哈希和大小一致。

## Commands And Observations

```text
.venv/bin/pytest -q tests/v2/protocols/test_metadata_phase_slice2.py
25 passed

.venv/bin/pytest -q tests/v2/protocols/test_metadata_phase_slice2.py \
  -k 'numeric_slashes_stay_neutral or same_table_cell'
4 passed, 21 deselected

.venv/bin/pytest -q tests/v2/protocols/test_real_protocols_slice2.py \
  -k 'local_d001_rebuild'
1 passed, 2 deselected

git diff --check -- tests/v2/protocols/test_metadata_phase_slice2.py \
  tests/v2/protocols/test_real_protocols_slice2.py
passed
```

## Blockers Or Missing Environment

- 相邻既有 MG-K10 真实回归失败：III期投影仍含对侧期别标记。D001新增只读测试通过；该问题属于 parent/Codex 后续整体回归范围。
- 未直接读取外部原始 D001 路径，核对基于工作区内同哈希隔离副本及冻结元数据。

## Rerun Requests Or Next Step

- Codex 应复核当前 D001 数量变化是否符合本轮期别原子化预期。
- Codex 应单独调查 MG-K10 对侧期别投影失败，再进行整体协议回归。
