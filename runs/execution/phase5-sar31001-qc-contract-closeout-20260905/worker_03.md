# Execution Output: phase5-sar31001-qc-contract-closeout-20260905 - worker_03

Status: COMPLETED

## Boundary And Context Check

- 工作目录:`.worktrees/phase5-clinical-facts-profile`(分支 `codex/phase5-clinical-facts-profile`),未越界；审查型任务，未修改任何源临床资料或应用文件，全部命令为只读(grep/读取/pytest/只读 Python 探针)。
- 初始读取集两份文件已读；兄弟报告读取时均为“当时尚未完成”状态，故未依赖其结论，改从 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260904_FRESH_RUN_FIX_VERIFIED_QC_GAPS.md` 与 `CHECKPOINT_20260904_PHASE5_HIGH_REASONING_BEFORE_JOB_PAUSED.md` 独立还原“拟议最小修复”的定义。
- 过程发现：首轮审查期间兄弟 worker 正在同一工作树并行修改 `app/agents/evidence_normalizer.py`(提示版本 v11→v12);本轮续跑复验时文件已静默约 35 分钟，以下结论以复验后的稳定状态为准。

## Work Performed

**1. 拟议修复现状(对照 20260904 检查点三项建议)**

| 建议项 | 状态 | 位置 |
|---|---|---|
| gap-1 数值字符串确定性还原 | 已实现、已测试，且审查期间被进一步完善 | `app/agents/evidence_normalizer.py:828`(`_normalize_numeric_scalar`);复验时已放宽为“字符串可解析即转数值、无论单位有无” |
| gap-2a 向模型公布来源语义词表 | 已实现 | `_SYSTEM_CONTRACT` 逐字公布五个中文标签;`_align_source_semantics`(1329 行)按冻结元数据确定性重对齐，测试覆盖“既往原始资料→筛选病历转述”(即家族史漏项案例类) |
| gap-2b 被门禁拒绝候选生成未解决项(损失可见) | 仍未实现 | 未解决项仅来自模型输出;`fact_gate_results` 无 API/读取服务暴露；发布服务不处理拒绝 |

**2. 跨项目泛化性——通过。** 硬编码扫描唯一命中是遗留 `app/pipeline/reviewer.py:823` 正则中的 "SAR",该文件自 V2 冻结基线 commit `a02b833` 后未动，不在 Phase 5 事实链内，与本修复无关；修复本身无 SAR/31001/药名/日期硬编码。数值还原为纯 regex+NFKC,项目无关(全角符号可处理，`1e999` 溢出被 `isfinite` 守卫挡回)；来源词表单一事实来源在 `fact_evidence_closure.py:629,644`,normalizer 复用同一派生函数。注记：① 文档类型闭集对未登记类型落“无法确认来源”，对新项目偏严但属 fail-closed,泛化靠集中扩词表；② 遗留 "SAR" 正则建议登记为收口后清理项。

**3. 不可变历史——通过。** 注册层追加式且内容寻址(`_ensure_immutable_registration`:"never update a row",内容漂移即拒绝启动)，防住 09-03 旧进程旧模板类事故；发布链全部为 create/append,09-04 日期一致性修复在位(`fact_repositories.py:244` 仅比较精度与上下界)；修复仅在新运行解析时生效，旧不可变运行及其冻结提示 SHA 不受影响；被拒候选连同原因持久化于 `fact_gate_results`,历史可追溯。

**4. fail-closed——首轮发现的 fail-open 边缘已被兄弟堵住并加回归测试；可见性缺口仍在。**
- 实锤 fail-closed(探针输出):`">100.00"`、`"QT 346 ms; QTc 413 ms"` 复合结果、`"1e999"` 溢出均保持字符串被门禁拒绝；未知来源标签映射得 None 即拒绝；持续状态矛盾降为 unknown 并生成未解决项。
- 首轮实锤 fail-open:字符串 `"85"`+`unit=null` 曾静默作为文本事实通过门禁。复验确认已按我建议路径修复：转换不再要求单位存在(`scalar('85', None) → 85`),转换后无单位数值被合同层拒绝进入修复提示，严格 fail-closed;新增回归测试 `test_decoder_does_not_let_numeric_string_without_unit_bypass_numeric_gate`(用例恰为“心率 85”)。残余缺口(低优先级，不阻塞重跑)：门禁函数自身仍不拒绝数值形态字符串，直接构造合同对象可绕过；实际管线均先经规范化，仅为纵深防御问题。
- 可见性缺口(仍在)：若重跑再现比较符/复合数值或来源语义漂移，损失对复核者不可见，与证据保存合同冲突。

## Artifacts And Evidence

- 无新建/修改文件(报告由 runner 落盘)。关键证据(行号为复验快照)：修复定义见 20260904 检查点“最小修复建议”节；gap-1 实现 `evidence_normalizer.py:828-839, 868-875`;gap-2 `evidence_normalizer.py:471-478, 1329` 与 `fact_evidence_closure.py:629, 644-697, 744-782`;不可变注册 `fact_normalization_command_service.py:275-296, 142-163`;日期一致性 `fact_repositories.py:244-247`;拒绝仅存库 `fact_normalization_executor.py:322-386`;闭环测试 `test_evidence_normalizer_adapter.py` 约 971/1009 行。

## Commands And Observations

- `grep -rn "31001\|SAR" app/`:唯一命中遗留 reviewer.py:823。
- pytest 聚焦套件：首轮 111+96 项通过；复验后 6 文件 **290 项全部通过、0 失败**(30.9s,较首轮新增 83 项，含兄弟新增回归)。
- 只读探针：数值还原 12 组用例(首轮 `"85"|None→'85'`,复验 `→85` 证明修复生效)；合同构造+门禁 5 组(解析路径端到端 `{"canonical_value":"85","unit":null}` → `{"canonical_value":85}`,进入合同层拒绝；直构字符串仍过门禁，即纵深防御残余)。
- `stat` 采样:normalizer/executor 已静默约 35 分钟，提示版本 v12 稳定。

## Blockers Or Missing Environment

- 无环境缺失，无不可恢复阻塞；并行编辑风险已缓解并经复验收敛。
- 待 Codex 裁决(非我职权)：① gap-2b 可见性是否纳入重跑前修复——建议纳入，否则残余损失仍不可见；② flag-1(邮件内“实际使用直述”是否构成暴露)属临床/产品裁决；③ v9 发现的“奥马珠单抗给药完全未生成暴露候选”属语义完整性问题，本修复类不解决，高推理重跑即其测试，若仍缺失应走通用语义完整性回路，禁止硬编码。

## Rerun Requests Or Next Step

无重跑请求。重跑前退出门槛(全部确定性，不代行临床验收)：

1. **冻结确认**：Codex 确认兄弟编辑收口(已静默约 35 分钟)，固化提示版本 v12 与模板 SHA。
2. **回归绿**：290 项已全绿(本报告复验)；若实施 gap-2b,补“每条发布门禁拒绝恰好产生一条复核可见未解决项(含原因与受影响定位)、重试幂等”回归。
3. **注册探针**：显式 env 合同启动专用进程，核对实际注册 `prompt_version_id.template_sha256` 等于当前模板哈希、模型身份与 R3 读道一致。
4. **新鲜运行纪律**：仅经正式 API 新建不可变运行，不复用取消作业；输入范围与冻结权威同既往基线逐字节一致。
5. **机械验收**：25/25 步或逐项记录失败；零逐字对象/修复耗尽失败；记录门禁拒绝计数。
6. **gap-1 度量**：心电图面板、胆红素三项、肌酐、尿素、电解质、白蛋白、ALP、部分 IgE 以带单位数值事实发布；残余比较符/复合类被拒且(若可见性已补)未解决项计数与门禁拒绝数一致。
7. **gap-2 度量**：家族史类事实按“筛选病历转述”发布；来源语义拒绝数≈0 且逐条可见。
8. **边界不变**:`claims_complete=false`;Phase 5 不收口、Phase 5.5 不启动；纵深防御残余与遗留 "SAR" 正则登记为收口后清理项。
