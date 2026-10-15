# Phase 5 方案语义模型路由与 GLM 真实探针检查点

日期：2026-09-01  
状态：当前切片已接受；Phase 5 仍在进行，`claims_complete=false`

## 已完成

- 方案语义复杂任务首选 `zhipu-coding-plan/glm-5.3-flash:high`。
- 显式回退顺序为 GLM -> MTPLX medium -> DeepSeek V4 Flash high。
- 单规则且短提示、单批次的小任务默认 MTPLX -> DeepSeek，不消耗 GLM 主路由。
- 固定配置模式继续支持单模型钉住；所有回退均有作业级审计，不跨 provider 延续
  会话、拼接候选或复用不匹配缓存。
- GLM 语义传输复用本地 OMP Coding Plan 接入合同，并兼容应用既有独立视觉凭据，
  但视觉与方案语义职责、配置和审计仍相互隔离。
- 冻结 SAR EX-06 真实探针在 60,000 输出 token 下生成完整草稿；通用门禁的两个
  假阳性根因已修复，同一未修改草稿复验 `publishable=true`、零问题。
- 受影响回归 `238 passed, 5 warnings`；全 V2 回归 `3360 passed, 3 skipped,
  139 warnings, 2 subtests passed`，仅保留一个既存 D001 v1.5 提示哈希漂移。

## 未完成与边界

- 单个复杂父规则真实耗时 803.21 秒，当前性能不可作为全方案运行接受证据。
- 尚未创建新的 SAR V2 全量语义作业，也未运行 31001 Evidence Normalizer、
  Patient Profile 或浏览器端来源回放。
- SAR 失败作业 `1653540a54c747e4bc60d94ae65b0b18` 保持不可变 `failed_final`。
- D001 作业 `3259ab5f070447c3938ff2de5f45c9cd` 保持第 19 包后暂停，禁止恢复第 20 包。
- 路由与门禁没有项目、疾病、药物、量表、条款编号或时间点特异硬编码。

## 下一安全动作

建立超大父规则的通用结构分段合同：保留官方父子编号、例外和跨段依赖，把模型调用
限制在可独立理解的结构片段，允许有限并发，并在同一父规则身份下确定性合并与完整性
门禁。通过跨项目合成/真实只读回归和时延门槛后，才创建新的 SAR V2 全流程作业。
