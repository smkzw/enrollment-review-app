# Phase 5.8d 实验室来源闭包已验收，模型动作遗失已拒绝

## 本轮结论

- 接受通用来源闭包修复：流程表注、完整权威原文、访视合并策略和同小节条件上下文均能进入第 70–71 包语义提示。
- 不接受本次 MTPLX 输出：`body.p799` 中“采集样品”与“按标准实验室程序执行”被降为普通说明。
- 本次未发布方案控制点，`claims_complete=false`。

## 系统级根因与修复

原有发布门已支持“必备动作被丢弃”拒绝，但真实产品规划器没有填充 `owned_required_action_kinds_by_structure_unit_id`。因此，合同结构正确的模型输出仍可以在语义上遗失独立动作。

共享规划器现从拥有原文冻结项目无关的动作类型，当前包含：

- `collect_biospecimen`：采集/收集/留取样品、样本、标本、血样或尿样。
- `follow_specified_procedure`：明确应/须/需/必须按标准或规定程序执行。

这些元数据只供确定性门控使用，不进入 Agent 提示，不把验收期望泄露给模型。使用新元数据重放原始模型结果后，稳定得到：

`REQUIRED_ACTION_DISCARDED [pcb-9417eacd3086535b3808bea6]`

## 不可变运行证据

- 原始 DOCX SHA-256：`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`
- 计划：`papl-40b1237a22e538a278b4fd5e`
- 已验收干跑：`artifacts/phase5-slice60zs-laboratory-cross-chapter-closure-20260828`
- 已拒绝模型运行：`artifacts/phase5-slice60zt-laboratory-single-mtplx-20260828`
- 正式 MTPLX 调用：1 次，`121.617064s`，无重试、无 fallback。
- 原始结果：7 个处置、0 个候选；作为反例保留，不覆盖。

## 验证

- 动作/规划/发布门/来源闭包聚焦回归：`158 passed in 19.85s`。
- 完整方案模块：`944 passed, 58 warnings in 128.71s`。
- Python 编译、JSON 解析、`git diff --check` 通过。
- 工作区未安装 `ruff`，未为本轮临时增加依赖。
- Hermes 执行审计与 review gate 通过；三个工作者均为 `cursor-cli/auto`，无路线漂移。

## 未完成边界

- D001 II 仍为 `1848/1245/131`，剩余 128 包，`claims_complete=false`。
- 第 68 包保持未接受，本轮没有改动。
- 未进入受试者、OCR、病例审核、浏览器、视觉或独立试用。

## 下一安全动作

建立新的不可变修复切片，使用已填充动作元数据的产品批次执行一次新语义运行。先通过发布门，再做父级临床复核；不得将本次期望候选内容写回提示，不得覆写 60zt 反例。
