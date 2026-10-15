# Phase 5.8d 结构期别继承修复执行上下文

## 目标

修复 D001 全文期别图中已由真实标题层级明确限定为 II 期或 III 期的正文、子标题和表格仍被标为 UNKNOWN/MIXED 的共享根因，减少不必要的语义 Agent 调用，同时不把无明确结构依据的内容默认成共享或选定期别。

## 已观察事实

- 只读 D001 II 覆盖清单有 1,689 个结构单元；当前 1,433 个需语义处置。
- 其中至少 116 个单元位于明确的“II期临床研究阶段”或“III期临床研究阶段”标题链下，却仍为 UNKNOWN/MIXED。
- `_body_contexts` 在继承一个子标题后把 `context_heading_level` 更新为子标题层级，导致后续同级子标题错误关闭原阶段上下文。
- `_table_heading_scopes` 只按表前有限距离查找特定措辞，没有复用正文已经证明的上位阶段标题上下文。
- 修复证据索引后，首个 12 单元真实本地 Agent 批次已接受，耗时约 194 秒；不能用直接硬跑 1,433 单元掩盖确定性结构错误。

## 边界

- 仅修改通用结构期别检测、相邻确定性规划及对应测试/只读验收脚本，不硬编码 D001 文案、编号或结构身份。
- 未知不能默认共享；普通叙述中的 II/III 字样不能扩散到后续章节。
- 同级或上级标题离开明确阶段标题分支时必须关闭阶段上下文；阶段标题之下的任意深层子标题和正文应继承阶段范围。
- 表格只在其真实上位标题链或紧邻明确表题能证明期别时继承；不得按纯文本距离猜测。
- D001 源 DOCX 只读且哈希不得改变。

## 允许修改

- `app/protocols/phase_detection.py`
- `app/protocols/full_protocol_coverage.py`（仅在确有必要时）
- `app/protocols/phase_applicability_planning.py`（仅在确有必要时）
- `tests/v2/protocols/test_metadata_phase_slice2.py`
- `tests/v2/protocols/test_slice58c1_docx_heading_recovery.py`
- `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py`
- `scripts/run_phase_applicability_acceptance.py`（只读验收输出需要时）
- 当前 Trellis 任务研究、检查点与执行记录。

## 完成证据

1. 通用合成测试证明：阶段标题下多层/同级子标题、正文和表格正确继承；同级/上级离开分支后不泄漏；普通叙述不建立上下文。
2. 相关协议测试通过。
3. 从真实 D001 只读重建覆盖清单与计划，报告修复前后明确期别/模糊单元和批次数；源哈希不变。
4. 任何仍模糊内容继续进入语义 Agent，不因性能目的伪造确定性。

