# Execution Output: phase5-slice58e-phase-reference-vs-applicability-20260825 - worker_03

## Boundary And Context Check

仅修改合成/真实回归测试；未修改生产实现、D001 或 MG-K10 源文件。所有重建均使用 workspace 内隔离副本和临时目录。

## Work Performed

- 更新期别上下文合成回归：普通对侧期别引用不再切换外层章节范围。
- 更新 D001 只读重建断言：
  - 结构块：3581
  - 期别图块：3405
  - 全文单元：1840
  - 计划待处置单元：1306
  - 批次：218
- 固定 D001：
  - `body.p839` 为Ⅱ期；
  - `body.p937/p938/p940/p978` 在Ⅲ期章节上下文中均为Ⅲ期。
- 核对表5：39行、241个成员、无成员重复。
- 使用隔离 MG-K10 副本运行等价真实回归。

## Artifacts And Evidence

修改文件：

- `tests/v2/protocols/test_metadata_phase_slice2.py`
- `tests/v2/protocols/test_real_protocols_slice2.py`

D001 隔离源哈希：

`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`

MG-K10 隔离源哈希：

`075c93b45414dcb4bb33ef1cf623d295a9d8f029d7560ca484a0c0267c4fdabd`

两份源文件均保持哈希、大小、mtime 和目录项不变。

## Commands And Observations

- `.venv/bin/pytest ...`：相关期别、全文覆盖、D001 回归共 `85 passed`。
- D001 定向回归：`26 passed`。
- MG-K10 隔离副本精确回归：`PASS`；期别投影、共享排除项、9个流程聚合项和源只读检查均通过。
- `git diff --check`：通过。
- 定向 `compileall`：通过。
- 系统 Python 缺少 SQLAlchemy；未安装依赖，改用项目 `.venv` 完成验证。

## Blockers Or Missing Environment

当前执行无代码阻塞。

任务中的 `p9/p20/p24/p28/p33` 不是当前 D001 结构图中的直接 `body.p9` 等语义节点；其中部分为空段落或未标期别。未强行赋予期别，改用可回源的 `body.p839`、`body.p937` 等锚点完成回归。

## Rerun Requests Or Next Step

Codex 需结合 worker_01 的页码/结构别名审计，确认 `p9/p20/p24/p28/p33` 的具体映射后再做最终临床语义接受。
