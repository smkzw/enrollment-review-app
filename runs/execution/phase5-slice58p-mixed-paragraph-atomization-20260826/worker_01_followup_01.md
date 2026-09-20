# Execution Output: phase5-slice58p-mixed-paragraph-atomization-20260826 - worker_01

## Boundary And Context Check

继续同一 bounded worker session。仅修改 `app/protocols/full_protocol_coverage.py`；未修改测试、artifacts、任务记录、源方案、受试者数据、浏览器内容或 runner report。

## Work Performed

修正原子化逻辑：

- 移除 soft-punctuation 与 phase-marker interval 拆分。
- 仅按 `。！？!?；;` 和换行切分。
- 每个完整强边界片段独立调用现有 `_scope_from_text` 分类。
- 相邻同 scope 片段合并。
- 仅当 graph scope 为 `MIXED`、存在至少两个合并片段且 scope signature 不同才原子化。
- 单个混合强句保持一个 `MIXED` 单元。
- 派生身份使用 source start/end；非原子化单元保持原有 ID。
- 保留父级 `member_source_refs`、`source_span_ids` 和有序来源回放。

## Artifacts And Evidence

仅涉及：

- `app/protocols/full_protocol_coverage.py`

本地 D001 只读重建观察：

- 总单元数：1,846。
- `body.p729`：2 个单元，比例与剂量组合完整保留。
- `body.p801`：保持单个混合单元。
- `body.p815`：3 个单元，混合访视句完整保留，后续中性句合并为一个单元。
- `body.p1237`：4 个单元，II/III 混合推荐句保持完整。
- 共 9 个派生原子，较旧 1,840 基线增加 6 个。

## Commands And Observations

- 58p 与 58a focused tests：`36 passed`。
- 58b 与 58h adjacent tests：`25 passed, 5 warnings`。
- 合并编译与 focused/adjacent 回归：`61 passed, 5 warnings`。
- 本地 D001 full-protocol regression 未通过旧数量断言：期望 `1840`，实际 `1846`；未修改该测试。
- 强边界异常输入探测确认不会产生 punctuation-only clause。
- 未运行浏览器、渲染或临床最终验收。

## Blockers Or Missing Environment

实现本身无环境阻塞。D001 回归中的旧数量断言需要由 Codex/记录工作流判断并更新；测试文件按边界未修改。

## Rerun Requests Or Next Step

请 Codex/worker-03 基于 1,846 单元继续完成真实 D001 差异核查、package 复核和 Phase 5.8d 持久记录更新。若旧测试要求在一个强句内部拆出三个 phase atom，应保留该失败并标记为过时契约，不应回退到软标点拆分。
