# Codex Conference Review: phase3-slice1-acceptance

Date: 2026-08-14

## Verdict

`Pass after revision`。允许进入切片 2；页级召回不足作为显式已知限制，不允许以降低
精确性门槛换取通过率。

## Boundary Compliance

参与者均只读。Pi 实际路线为 `cms-smk/deepseek-v4-flash:max`；Grok Build 使用
`grok-4.6`。两者未修改产品文件。Grok 的不完整输出不计最终放行证据。

## Hermes Workflow Record

会议由 `hermes_workflow_guard.py` 初始化、预检并保存路由与会话证据；Hermes 不是会议
参与者。Pi 与 Grok Build 使用各自真实通道，未通过 Hermes 替换模型。最终裁决由 Codex
基于完整参与者意见和确定性回归作出。

## Participant Outputs Reviewed

- Pi 首轮复现表格/重复文本假页、源哈希分叉、CJK 字距漏配和可变 PDF。
- Grok 完整轮独立发现同方向问题，并补充 `w:basedOn`、`w:sdt`、长 span id 与页眉语义。
- Pi 修复后复验发现跨 span 共享物理范围；Codex 修复后，Pi 同会话再次独立复测两份真实方案，确认碰撞归零并给出放行结论。

## Conference Panel Review

采纳有确定性证据的问题；未采纳用总对齐率代替精确性、或把降级页当权威来源的路线。
剩余 C2 是诚实拒绝造成的页定位覆盖限制，不是错误定位：切片 3 前做受限插值 spike，
插值页只作提示。

## Main-Venue Codex Review

Codex 逐条检查实现与测试，新增/修正回归；两份真实方案剩余 `TEXT_RANGE` 范围
全局唯一、页面摘录回验失败为 0。原方案及其目录无写入。

## Codex Independent Verification

最终全仓 `514 passed, 1 skipped, 18 subtests passed`；真实方案聚焦测试通过；迁移、
契约、运行依赖、内容寻址副本与哈希绑定通过。当前切片无前端，故无需浏览器视觉验收。

## Final Decision

切片 1 通过。切片 2 必须区分“身份来源权威性”和“规则正文定位精度”；切片 3
只能把全局唯一精确范围/唯一表格页作为权威页，降级或插值页不得单独满足发布门槛。
