# Codex Conference Review: phase5-slice53-independent-check

Date: 2026-08-23

## Verdict

修订后接受；会商意见不能单独构成验收，最终以 Codex 对当前代码、测试、真实传输和持久状态的复核为准。

## Boundary Compliance

两名参与者均保持只读，没有修改应用文件或读取工作区外的临床原始资料。会商审查的是 Evidence Normalizer、持久任务、租约、检查点和确定性门禁，不包含 UI、最终入排结论或真实病例验收。

## Participant Outputs Reviewed

- `general_grok46.md`：重点指出运行级门禁、逐页未解决项持久化、定位真实性和输入哈希可审计性风险。
- `general_pi_qwen38.md`：重点指出非默认分片参数未冻结、运行失败/取消终态、提示词/模型配置裸标签，以及重复身份/哈希定义风险。

## Conference Panel Review

采纳并完成：逐页未解决项持久化；运行门禁拒绝时标记 `PARTIAL`；`max_pages_per_call` 冻结并在重建时复用；失败/取消运行投影与启动恢复；PromptVersion/ModelConfig 内容绑定；检查点回放重新校验权威；删除未使用的第二套调用身份生成器；统一运行输入范围哈希。

保留但明确边界：只有未解决项的调用继续采用保守 `PARTIAL` 语义，表示模型完成但没有形成可发布事实，不等同于系统故障。结构化测试注入路径的 `raw_output_sha256` 与真实文本传输原文哈希语义不同，只用于测试适配，不作为真实模型审计来源。

## Main-Venue Codex Review

在会商后继续追查出更深层缺陷：模型此前只能看到定位编号，无法看到定位局部原文，并且被要求自报系统身份与来源哈希。当前实现已将 Phase 4 定位摘要加入冻结输入，只允许模型输出语义草稿，由系统回填身份、时间与哈希；中文资料类型和来源方也纳入确定性来源强度派生。

## Codex Independent Verification

Codex 检查了合同、来源适配器、Agent 草稿提升、持久执行器、门禁和相关迁移；真实 oMLX 探针先复现遗漏明确数值和从沉默制造缺口，再经共享机制修订后同时抽取否定病史与收缩压数值，且断言哈希与 Phase 4 来源一致。UI 未改动，因此本切片不以浏览器视觉检查作为验收项。

最终 fresh-context 独立复核曾再次拒绝：定位摘要内容未进入幂等哈希、终败任务重试未恢复领域运行、提交回调异常需等待租约。三处均在共享规划/运行层修复并添加回归；同一检查者重跑原复现后无剩余问题。

验证证据：聚焦扩展回归 348 项通过；`tests/v2` 全量 1972 项通过、1 项跳过、2 个子测试通过；`compileall`、`git diff --check` 与 Trellis task validate 通过。唯一跳过为既有 Phase 4 真实 oMLX 探针工件缺失，不是本切片新增失败。

## Final Decision

Slice 5.3 接受。Phase 5.4 才允许事务发布事实、建立 FactRuleLink 和资料期望投影；本切片不得提前生成 Patient Profile 或入排结论。
