# 2026-09-01 超大父规则 GLM 分段真实探针失败与恢复检查点

## 状态

- 本检查点接受失败证据，不接受分段方案的性能或语义质量结论。
- Phase 5 仍为 `claims_complete=false`。
- D001 控制任务 `3259ab5f070447c3938ff2de5f45c9cd` 继续停在第 19 个检查点后；失败 SAR 作业 `1653540a54c747e4bc60d94ae65b0b18` 保持不可变。

## 已确认

- 冻结 EX-06 输入按通用层级规划形成 4 段，正文单元为 `[3,3,3,2]`；源包 SHA 为 `c7c038e38cdf3ce887bab8f8dc2ed8cc57b1cc100d7c8853be1dd118178e3b67`，前后未变。
- 真实调用固定为 `zhipu-coding-plan/glm-5.3-flash:high`，并发不超过 2，没有启动 MTPLX、DeepSeek 或同模型整父回退。
- GLM 生产传输当前 `uses_compact_wire_contract=False`，因此默认绕过父规则分段；探针强制能力后才进入真实四段路径。这是通用能力建模缺陷，不是项目特异问题。
- 四段中 3 段成功；第 1 段在约 600 秒发生读超时。权威分段运行共 7 次调用、1213.19 秒，随后失败关闭，没有合并候选、水合草稿或完整发布门结果。
- 独立对照未发现生产分段器或运行器包含 D001、SAR、疾病、药物、量表、条款号或时间点硬编码。EX-06 只用于隔离探针选定冻结输入。
- 现有整父基线 803.21 秒并形成完整草稿；同一草稿在通用门禁修复后可发布。因此当前分段路径既未证明更快，也未证明质量不低于整父路径。

## 不得误读

- 顶层 `summary.json` 的 `completed` 只表示探针脚本完成收尾，不代表业务成功。`segmentation-failure.json` 与 `runner-result.json` 才是本轮结论依据。
- `run-whole-parent-skipped-segmentation` 是能力门错误形成的负向对照，不是分段结果。
- 三段部分输出不得发布，也不得与其他 provider 的候选拼接。

## 下一安全动作

1. 将“支持父规则分段”从 `compact wire` 能力中独立出来，使 GLM 可按自身结构化输出合同进入分段。
2. 为每个分段建立来源哈希、提示版本、模型身份和分段身份组成的确定性检查点；成功段可复用，失败后只恢复缺失段。
3. 将远端读超时与输出 Schema 错误分开记录；超时重试仍限同一模型、同一分段、有限次数，不触发跨 provider 拼接。
4. 只补跑第 1 段，再执行确定性同父合并、水合和完整门禁；成功后才与整父草稿进行逐义务、逻辑、时间锚点、例外、证据要求和耗时对照。

## 证据入口

- `artifacts/phase5-acceptance/20260901/glm-segmented-parent-probe-ex06-20260901/`
- `reviews/codex_execution_phase5-large-parent-segmented-glm-live-probe-20260901_review.md`
- `runs/execution/phase5-large-parent-segmented-glm-live-probe-20260901/worker_01.md`
- `runs/execution/phase5-large-parent-segmented-glm-live-probe-20260901/worker_02.md`
- `runs/execution/phase5-large-parent-segmented-glm-live-probe-20260901/worker_03.md`
