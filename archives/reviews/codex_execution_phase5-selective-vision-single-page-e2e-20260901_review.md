# Codex Execution Review: phase5-selective-vision-single-page-e2e-20260901

## Verdict

**Accept after Codex parent repair and live verification.** 已在全新隔离数据目录中完成一页内容中立资料从冻结证据修订、幂等入队、真实智谱 Coding Plan 视觉请求、不可变观察落库到用户查询投影的闭环。这一结论只接受选择性页级视觉工程合同，不构成 OCR 正文、临床事实或入排判定的医学接受。

## Worker Outputs

- `worker_01` 只读梳理了现有选择性视觉链路，识别出旧编排夹具的伪 PNG 不能用于真实视觉验收，并提出“必须存在成功观察”而非仅任务完成的失败判据。
- `worker_02` 新增可显式启用的单页真实视觉端到端测试，复用真实执行器、持久任务、不可变观察仓储与修订级投影，没有修改生产代码或临床来源。
- `worker_03` 独立攻击核对了 Coding Plan 端点、来源保真、OCR 不变、失败关闭和投影一致性；其提出的启动配置风险经 Codex 追踪实际调用者后被证伪。
- 三个工作者均使用声明的 `zcode/GLM-5.3-Flash:max` 主路由完成，未发生路由替换。工作者报告只是实施与审阅输入，不是验收证据。

## Manager Assessment

此受控执行包明确不设独立执行经理，由 Codex 直接验收。实现保持了三个关键边界：不读取 D001/SAR 旧结果，不引入项目特异规则，不让视觉观察覆盖 OCR 或替代语义/确定性判定。

## Boundary Compliance

- 仅新增隔离的合成单页端到端测试，未修改临床来源、旧项目结果或生产业务规则。
- D001 暂停任务保持原状，未启动第 20 批，也未混入新的视觉模型配置。
- 合成页面不含疾病、药物、评分、访视时点或项目编号；通用实现未因真实项目样本而过拟合。

## Hermes Route Evidence

受控执行包由 `hermes_workflow_guard.py` 生成，三个工作者都在声明的夜间主路由 `zcode/GLM-5.3-Flash:max` 建立可恢复会话并以 `returncode=0` 完成，未使用 fallback。Codex 另行重开产物、运行真实端点与相邻回归，没有将工作者自报当作完成证据。

## Codex Independent Verification

- Codex 将合成页图从 Pillow 传递依赖改为 Python 标准库生成的有效 PNG，没有新增依赖或改变生产逻辑。
- 真实端到端：`2 passed in 21.31s`。真实模型为 `glm-5.3-flash`，成功观察正文 859 字符，用量字段非空，来源标识、提示词哈希、观察身份哈希和模型身份全部通过。
- 同一流程证明：两次入队只有一个任务；只有一条 `succeeded` 不可变观察；观察来源、页码、页图哈希与 OCR 哈希闭包一致；OCR 原文、OCR 哈希和页图字节前后不变；用户查询投影与落库计数一致。
- 相邻选择性视觉回归：`109 passed, 2 skipped in 18.58s`；两个 skip 都是未显式启用的真实计费测试。目标 Python 编译、启动脚本 zsh 语法与目标 `git diff --check` 通过。
- 启动配置追踪：`app.config` 在导入时读取应用根目录 `.env`，而 `run_enrollment_review_service.sh` 的运行状态文件只冻结启动器已验证的 MTPLX 路由。因此无需也不应再复制独立 VLM 密钥到运行状态文件。

## Cleanup Decision

在 `review-gate` 和执行审计通过后，只由 workflow guard 清理可替代的 runner 过程文件。保留审阅、指标、路由记录、真实端到端测试和 Trellis 检查点；不清理临床来源、冻结证据或 D001 暂停检查点。
