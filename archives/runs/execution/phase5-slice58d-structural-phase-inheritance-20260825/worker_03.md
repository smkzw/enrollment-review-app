# Execution Output: phase5-slice58d-structural-phase-inheritance-20260825 - worker_03

## Boundary And Context Check

- 已读取指定 context 与 plan。
- 仅使用工作区内 D001 内容地址化快照；未读取外部原始路径、未联网、未调用真实 Agent。
- 未修改文件；当前实现与测试改动均为既有工作树状态。
- 前值采用既有冻结工件的 1,433/235，不采用已知存在跨同级泄漏的旧 HEAD 口径 802。

## Work Performed

只读重建同一份 D001 II 结构快照，并按 `source_ref` 逐单元比较：

- 结构块：3,581
- 覆盖单元：1,689
- 冻结参数：每批最多 12 个 owned units，context radius=1
- 修复前：1,433 个模糊单元，235 批
- 当前实现重建：1,355 个模糊单元，225 批
- 改善：78 个单元转为确定期别，其中 II 期 70 个、III 期 8 个；未发现确定单元反向变模糊。
- 当前仍需真实 Agent 的计划范围上限为 1,355 个单元/225 批；当前未执行 Agent。

当前模糊单元类型：

- paragraph 730
- list item 335
- table row 255
- table header 22
- footnote/annotation 12
- table note 1
- 表格相关合计 278

## Artifacts And Evidence

读取并验证：

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/coverage_manifest.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/frozen_phase_plan.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/freeze_metadata.json`
- `structure/blobs/protocol_blocks/...json`
- `source-input/blobs/protocol_sources/...docx`

证据：

- D001 快照源文件 SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 文件大小：405,567 bytes
- 与 manifest 声明哈希一致。
- 既有执行状态仍为 `needs_review`，已接受批次和单元均为 0；不能视为已完成语义闭包。
- 当前重建仅在内存中完成，未覆盖既有冻结 manifest/plan 文件。

发现的残余结构缺陷：

- 仍有 38 个模糊单元位于明确的“Ⅲ期临床研究阶段”标题链下：
  - `body.p938`
  - `body.p940`–`body.p955`
  - `body.p957`–`body.p976`
  - `body.p978`
- 其中 34 个为 list item、4 个为 paragraph，均非表格。
- 触发点是 `body.p937` 的“与Ⅱ期临床研究试验一致，详见…”正文被标为 II 期并关闭了活动中的 III 期上下文；后续同级标题和正文变为 UNKNOWN。
- 表 5 共 13 个单元（1 个表头、12 个表行），当前仍为 UNKNOWN，继续保留在语义 Agent 范围内。

## Commands And Observations

- `.venv/bin/python3`：Python 3.12.13，可正常加载项目。
- `/usr/bin/python3`：Python 3.9.6，导入项目时因 `date | None` 注解失败；未安装或改动环境。
- 聚焦 pytest：

  `89 passed in 0.18s`

  覆盖 metadata/phase、DOCX structure、full coverage、phase applicability contract 和 Agent planner。
- `git diff --check`：通过。
- `shasum -a 256`：源快照哈希通过。

## Blockers Or Missing Environment

- 当前 1,355/225 是只读重建结果，尚未写回新的冻结清单和计划。
- 残余 38 个结构可确定单元仍会被当前 planner 错误交给 Agent，因此当前结果不宜作为最终冻结计划。
- 未运行真实 Agent；没有语义结果或最终临床闭包证据。

## Rerun Requests Or Next Step

1. 修复通用逻辑：非标题型显式期别交叉引用不得关闭已有结构期别上下文。
2. 增加“III 期标题 → 正文提及 II 期 → 后续同级标题/正文仍继承 III 期”的回归测试。
3. 使用同一 D001 工作区快照重新生成 manifest/plan，确认上述 38 个不再进入 Agent。
4. 再运行聚焦回归、源哈希检查和真实 Agent 批次。
