# Codex Execution Review: phase5-visual-observation-normalizer-contract-20260901

## Verdict

accept

## Worker Outputs

- `worker_01` 完成只读合同审阅，提出以冻结页身份、OCR 身份、资料版本与观察身份哈希为边界的最小接线方案。
- `worker_02` 作为唯一写者完成观察附件合同、运行级范围冻结、执行期漂移复核、候选提示接线与聚焦测试。
- `worker_03` 独立攻击缺失、关闭、来源错配、OCR 漂移、旧修订、重复观察与提示注入七类场景，未发现可越过正式事实发布边界的路径；同时指出一个校验器实现问题与两个测试缺口。

## Manager Assessment

本执行包按计划不设执行经理，由 Codex 直接验收。采纳运行级范围缝合方案：调用级有效文本输入哈希保持不变；只有存在合法视觉观察时，观察身份集合才进入运行级范围与幂等键。该方案保持旧任务兼容，又能阻止不同观察集合误复用。

观察仍是来源绑定的辅助材料，不是 OCR 原文、EvidenceLocator、临床事实或入排结论。正式事实必须继续通过当前修订的定位、原文文本哈希与事务发布门禁。未增加 D001、具体药物、疾病、评分或时间点硬编码；D001 暂停任务未恢复。

Codex 修正 `SelectiveVisionObservationAttachment` 的 after-validator：原实现返回 `model_copy`，会触发 Pydantic 警告且可能不应用正文去空白；现改为对冻结模型使用 `object.__setattr__` 后返回 `self`。同时补齐两条独立审阅指出的回归锚：跨资料版本观察在收集边界排除；结构合法的视觉提示注入候选虽进入审计候选层，但在定位与文本哈希门禁和事务发布门禁均被拒绝，未进入正式事实或个例档案正文。

## Boundary

- 只接通选择性视觉观察到事实规范化的候选提示输入，不改 OCR、有效文本、定位器、正式事实、个例档案或入排结论合同。
- 观察按冻结页、资料版本、OCR 原文与观察身份精确绑定；不匹配即排除，冻结后漂移即失败关闭。
- 未运行或恢复 D001 第 20 批，未把旧暂停结果与新提供方配置混合；未加入项目特异临床规则。

## Hermes

本执行包由 `hermes_workflow_guard.py` 初始化和审计，实际执行平台为计划记录的 `zcode`，三名执行者均使用 `GLM-5.3-Flash:max` 主路由完成。没有通过 Hermes 传输其他模型，也没有静默替换或 fallback；计划明确本包不设执行经理，由 Codex 直接验收。

## Codex Independent Verification

- 聚焦合同与接线测试：`14 passed`；仅有既有 SWIG 依赖弃用提示，校验器告警已消失。
- 受影响层回归：`105 passed in 28.51s`，覆盖来源适配、命令服务、持久化、执行器、观察仓储和 Evidence Normalizer 适配器。
- 目标 Python 文件 `py_compile` 通过；目标文件 `git diff --check` 通过。
- 写者此前全量 `tests/v2` 结果为 `3336 passed, 3 skipped, 1 failed`；唯一失败是早于本执行包存在的 D001 只读 checkpoint 提示词哈希漂移。本包未修改旧 checkpoint，也未以该失败冒充通过。
- 三名执行者均由计划中的夜间主路由 `zcode/GLM-5.3-Flash:max` 完成，return code 均为 0，无超时、无 fallback。

## Cleanup Decision

`review-gate` 与 `audit-execution` 已通过；workflow guard 已归档可替代的 prompt、worker 报告与 stdout 过程文件。保留审阅、指标、路由清单、代码、测试与 Trellis 检查点；未清理临床来源、冻结证据或 D001 暂停记录。
