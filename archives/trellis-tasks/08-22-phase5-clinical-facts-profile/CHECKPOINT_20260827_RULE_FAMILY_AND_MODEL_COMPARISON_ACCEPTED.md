# Phase 5.8d 规则家族门禁与模型对照检查点

日期：2026-08-27

## 当前任务边界

- Trellis 任务仍为 `in_progress`，当前处于 5.8d。
- D001 II 当前冻结结构基线仍为 1,848 个全文单元、1,301 个语义目标、137 个包。
- `claims_complete=false`；不得启动其余 131 包全跑、受试者审核、浏览器/视觉或三路独立测试者。

## 根因与共享修复

真实异质包 36/60/78 的首轮 MTPLX 运行暴露门禁在两种错误间反复：`PAIRED_RULE_FAMILY_SOURCE_IGNORED` 与 `SHARED_POSITIVE_SOURCE_MISSING`。根因不是单个项目术语，而是 `_same_rule_family` 曾把相同末级章节标题当成同一原子义务：实验室章节中的不同检查、流程表中的不同注释会被错误互相传播期别范围。

`app/protocols/phase_applicability.py` 现将隐式同族关系限定为：相同非通用末级标题、非空且空白规范化后逐字相同的原子义务。标题直接引用、明确交叉引用和期别特异交叉引用继续由原有独立合同处理。新增回归证明同章节不同子义务不会形成配对范围，而两期逐字重复的同一原子义务仍可构成配对来源。

## 真实运行与临床核对

- 修复后 MTPLX 异质包 36/60/78：3/3 包、36/36 单元接受；5 次尝试，2 个中间门禁问题，最终 0 个未决。
- DeepSeek V4 Flash max 同源对照：包 60/78 在 8192 完成；包 36 因长度上限在 16384 重试后完成。组合结果为 36/36，和 MTPLX 的最终处置差异为 0。
- Codex 逐条核对 36 个目标、原文、证据和理由，未发现当前有边界样本中的已知临床/来源错误。
- 受修复影响的旧源包 67 已重新生成：11/11 为“选定期适用”。随机化两条不再将 II/III 不同分组比例视为同一义务；源包 79、110 在新门禁下继续通过。
- 源包 67 首轮长度终止诊断保留在 `phase5-slice58z-*`；成功重试保留在名称含 `16k` 的 `phase5-slice58z2-*`，但实际传输身份仍明确记录 `max_tokens=8192`，因为本地后端按产品上限截断。不得把目录名解释为实际 16K 运行。

## 决定性验证

- 聚焦门禁回归：`60 passed, 5 warnings`。
- 完整 `tests/v2/protocols`：`781 passed, 58 warnings`。
- 当前门禁重新校验：源包 67、79、110 均接受；旧包 67 的两项过度共享结果按预期不再通过新门禁。
- `git diff --check` 在本检查点收尾时执行。

## 工件

- 失败前对照：`artifacts/phase5-slice58v-d001-three-package-mtplx-20260827/`
- 修复后 MTPLX：`artifacts/phase5-slice58w-d001-three-package-mtplx-rule-family-fix-20260827/`
- DeepSeek 主运行：`artifacts/phase5-slice58x-d001-three-package-deepseek-v4-flash-20260827/`
- DeepSeek 包 36 重试：`artifacts/phase5-slice58y-d001-package36-deepseek-v4-flash-16k-20260827/`
- 源包 67 首轮长度终止：`artifacts/phase5-slice58z-d001-package67-mtplx-rule-family-fix-20260827/`
- 源包 67 成功重试：`artifacts/phase5-slice58z2-d001-package67-mtplx-rule-family-fix-16k-20260827/`
- 对照汇总：`artifacts/phase5-slice59a-d001-mtplx-deepseek-comparison-20260827/`

## 下一安全动作

继续 5.8d，选择下一组此前未运行、结构风险不同的少量代表包；先完成真实语义结果、父级来源和临床逐条核对，再决定是否继续扩大。默认语义路线保持 MTPLX medium，DeepSeek V4 Flash 不替换默认路线。
