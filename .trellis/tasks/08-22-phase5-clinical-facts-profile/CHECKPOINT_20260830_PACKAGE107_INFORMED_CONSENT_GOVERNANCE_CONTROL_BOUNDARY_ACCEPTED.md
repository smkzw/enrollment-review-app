# Phase 5.8d 第107包伦理与知情同意治理/控制边界验收检查点

## 当前结论

- 已接受不可变候选计划 `papl-e17d498106b6f71f440ff2be` 第107包 `pap-b119517783facd407b628e1e` 的模型外来源与语义边界。
- 本包仅拥有 `body.p1251-p1259`，不附加来源。第106包止于 `body.p1250`；第108包从 `body.p1260` 开始，均未进入本包提示。
- 41项冻结语境全部只读且不进入执行批次：其中30项全局无owner，11项由Package45/46/47/48/50/75拥有。配置中的 `unowned_context_source_refs` 精确记录前30项，而不是全部语境。
- `claims_complete=false`；未水合临床Agent输出、未发布控制点、未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

## 父级临床与产品判断

- `p1251/p1252/p1255` 仅为结构标题；`p1253/p1254` 是研究级伦理与法规治理；`p1256` 是ICF文件伦理审查治理；`p1258` 是ICF模板内容治理。这些内容不得改写为单例入排条件。
- `p1257` 同时含参加研究前和研究进行期语义。参加研究前必须保留口头及书面告知、参与者或监护人无阅读能力时的公正见证、可理解方式与措词；后续新信息告知与记录继续作为研究进行期治理。
- `p1259` 参加研究前必须保留充分考虑时间、参与者或监护人与执行知情同意研究者分别签名并注明日期、非本人签署注明关系。双方各留存一份，以及重要新资料经伦理批准后再次同意，保留为研究进行期治理。
- 第67包既有 `procedure:d001-icf-screening` 已覆盖通用 `obtain_signature`。第107包保留该动作作为源文义务元数据并关联既有流程，但候选只承担未覆盖增量，不生成第二条通用签署/解释控制。

## 执行中修正

- Worker02初稿把p1257/p1259整体设为 `non_enrollment_execution`，并允许零候选通过。父级依据源文和两路独立攻击拒绝该处置。
- 父级将p1257/p1259设为筛选期 `other_control_candidate`，关联 `informed_consent` 家族与既有ICF流程；新增通用动作识别 `witness_consent`、`allow_informed_decision_time`、`record_signature_date`、`record_signer_relationship`，并扩展ICF解释/签名识别。
- 独立验收首轮把30项 `unowned_context_source_refs` 误解为41项语境的不完整清单。父级复核确认所谓缺少的11项均由其他包拥有，修复专项测试变量遮蔽并增加精确owner分区断言；原验收会话复核后撤销误报。

## 验证证据

- 模型外准备：`9 owned / 0 attached / 9 total`；p1251/p1252/p1255为结构来源，p1257/p1259为pre-enrollment，required procedure仅既有ICF流程，official rules为空。
- 专项、相邻Package103-107及既有动作/候选重分配回归最终 `144 passed, 5 warnings`；`git diff --check`通过。警告仅为既有SWIG/PyMuPDF弃用提示。
- 配置 SHA-256 `38783a0af0dc3654fa4044624e29cc6c47550143e2e512abdaf02f8a8656ebe4`；父级清单 `478469d0e7b19ca5e7f9bf6f2f332d9f4bb50a95bafc14355f16d03970c446de`；专项测试 `3b7e5f2958abab51d9e060be56f9f57440c9d9fcc8759d0486f486a7bdb67f71`；生成提示 `4fa3ab20e8aa0a4f780644aa73613102b3edfa855fe6b34f1384887993f35d57`。
- 四路受控执行均使用 `cursor/default` 主路由，无fallback；耗时 `180.4s / 589.2s / 216.2s / 140.7s`，工具调用 `73 / 156 / 566 / 25`。Worker04两轮沿用同一会话并撤销误报。

## 正式状态与下一步

- 正式候选仍为1848个结构单元、1240个语义目标、131个包；按当前逐包闭合记录剩余100包。
- 下一安全动作：第108包 `pap-f3fa399755a65a5a57ba306c`，从 `body.p1260` 开始。须重新读取冻结拥有来源和完整原文，区分IRB/伦理委员会研究治理与任何真实受试者前置控制，不回吸第107包，也不预设候选数量。
