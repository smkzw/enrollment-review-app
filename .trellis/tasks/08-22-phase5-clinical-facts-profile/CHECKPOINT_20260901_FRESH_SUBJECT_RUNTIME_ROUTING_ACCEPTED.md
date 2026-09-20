# 2026-09-01 代表受试者全新运行与语义路由检查点

## 当前结论

- 复杂方案语义解构顺序为 `zhipu-coding-plan/glm-5.3-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> deepseek/deepseek-v4-flash:high`。
- 短提示、单规则、单批次新会话为 `MTPLX medium -> DeepSeek V4 Flash high`；跨供应方时丢弃失败候选并新建传输和会话，不拼接。
- 双击启动器不再把 MTPLX 表述为复杂语义主模型。graded 模式不强制加载 MTPLX；已在线或显式设置 `ENROLLMENT_START_MTPLX=1` 时才预热。
- 旧 `runtime-data/sar31001` SQLite 库只是方案解构的 `failed_final / SEMANTIC_DRAFT_MISSING` 失败运行，不是 31001 事实或 Patient Profile 成果；已冻结为反例，不得迁移、重试或当作新作业。
- 唯一合法的下一运行根目录是 `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh`。它已绑定哈希复验的一份方案副本和五份受试者资料副本，有全新标记但没有 SQLite 业务状态。
- 全新运行只使用 `tools/phase5_acceptance/fresh_runtime.py` 一个门禁入口；重复门禁已删除，对抗测试已重新绑定正式入口。

## 验证

- V2 启动器真实 Bash UAT：`14 passed`。早先强制用 zsh 运行 Bash 验收脚本的假失败已查明，产品启动逻辑未误改。
- 聚焦路由和全新运行回归 `40 passed`；Agent/工具层 `145 passed`。
- 协议、Agent、工具扩大回归 `1464 passed, 1 failed`；唯一失败仍是不可变 D001 历史提示词 SHA，未改写旧检查点掩盖漂移。
- `zsh -n`、`bash -n`、`py_compile`、`git diff --check` 通过；生产路由、执行器、启动器和门禁无 D001/SAR/受试者/疾病/药物/特定条款硬编码。
- 正式执行审计、同会话续跑身份、review gate 通过；过程文件已归档。

## 未完成边界

- 本步没有启动新 V2 服务，没有对全新作业发起真实 GLM/MTPLX/DeepSeek 请求。
- SAR 方案尚未在新库中完成解构；31001 尚未进入 Evidence Normalizer、临床事实、Patient Profile、浏览器回源或临床 QC。
- Phase 5 继续 `claims_complete=false`。D001 第 20 包与旧 SAR 失败作业继续禁止恢复。

## 下一安全动作

1. 以 `ENROLLMENT_V2_DATA_DIR=.../sar31001-fresh` 在专用端口启动隔离 V2，启动前和创建作业前均运行全新运行门禁。
2. 从哈希验证的原始 DOCX 副本新建方案作业，复杂语义必须先走 GLM-5.3-Flash high 并落 `protocol-semantic-route-audit/v1`。
3. 只读取一次整份方案结构并冻结快照；全文用于高召回控制点发现，仅候选和不确定项进入深度语义分析，不对整份方案逐页重复 OCR/VLM。
4. 方案候选与门禁通过后，再处理 31001 资料，逐事件核对事实、日期、否认/沉默、冲突、资料覆盖和原始位置，再进入 Patient Profile 与浏览器验收。
