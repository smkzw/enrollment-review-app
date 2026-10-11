# Phase 5.5 实施计划

## 0. 恢复与边界

- [x] 重读 R3 设计书、实施计划和 Phase 5 暂停点。
- [x] 记录 Phase 5 仍开放、`claims_complete=false`，以及合同层受控重叠原因。
- [x] 确认产品内调用链不得依赖 Hermes、OMP、ZCode 或其他外部 harness。

## 1. ClausePack 投影

- [x] 新增 ClausePack 合同与 `determination_mode` 枚举。
- [x] 新增通用投影、稳定排序、内容哈希和读取侧完整性校验。
- [x] 覆盖专业判断、数值、日期/时间窗、逻辑和语义类测试。
- [x] 从 SAR III 与 D001 已发布规则生成对照产物；只比较横评 ClausePack 的条款数量和官方编号。

## 2. 页级判读合同

- [x] 新增 PageReviewRecord、PageReconciliation、SubjectPageCoverage 及子合同。
- [x] 强制保存原文、规范值、归一化键和 `handwriting[]`。
- [x] 加入读道权限校验和判定词注入拒绝测试。
- [x] 加入页清单完整性、重复页、舍弃理由和失败复读身份测试。

## 3. 确定性对账

- [x] 迁移横评 `norm_val` 思路，建立 NFKC、单位、数值、日期和字段同义归一化。
- [x] 实现双主读事实对账、确定性方向丢弃和三源手写二取一规则。
- [x] 对关键字段分歧和单源候选保持冲突，不自动择优。

## 4. 产品自有 harness

- [x] 迁移横评 JSON 修复、截断翻倍重试和失败分类，不重写已验证逻辑。
- [x] 接入 main-A GLM-5.3-Flash high 与 main-B MiniMax-M3 high；厂商默认采样，不设置 temperature。
- [x] 接入 handwriting-C Qwen3.8-Flash-Next low，仅允许写 `handwriting[]`。
- [x] 凭据仅从显式项目环境变量读取；加入无凭据、端点故障、429、截断和内容过滤故障注入测试。
- [x] 完成双主读互盲并发、条件手写三读、原读道失败复读身份和每读道并发上限。
- [ ] 完成三端点真实身份预检与最小页面调用；当前显式 env 有 main-A 凭据，缺 main-B `CMS_SMK_API_KEY`。
- [x] 新增页级记录、对账和覆盖持久化，不改写 Phase 4 冻结产物。
- [x] 将已采信页级记录接入 Evidence Normalizer：R3 输入冻结覆盖、对账、双主读/手写读道与 OCR 侧车；旧 Phase 5 作业保持原输入兼容。

## 5. 真实评测与阶段门槛

- [ ] 在隔离 31001 资料上完成逐页覆盖、事实/Profile 回源和临床 QC。
- [ ] 在既有金标集复跑产品 harness，计算双模型并集事实召回和负判定静默漏判。
- [ ] 由独立测试路线执行真实浏览器医学监查员试用；测试模型不得替代产品内模型。
- [ ] 达到阈值后回写实施计划与阶段复盘；未达阈值则保持 Phase 6 阻断。

## 验证命令

```bash
pytest -q tests/v2/projections/test_clause_pack.py tests/v2/domain/test_page_review_contracts.py
pytest -q tests/v2
python3 -m compileall -q app tests/v2
```

## 2026-09-05 合同层证据

- SAR III 已发布规则：23 条官方规则、81 个独立组件；横评 23 个官方编号全部覆盖。
- D001 II 已发布规则：36 条官方规则、67 个独立组件；横评抽样 22 条，发布规则无缺失，另有 14 条未纳入横评。
- 投影分类只读取结构合同：SAR 为 39 个确定性、20 个研究者判断、22 个语义组件；D001 为 34 / 19 / 14。
- 聚焦合同测试 `19 passed`，领域与投影回归 `414 passed, 5 warnings`；编译与定向差异检查通过。环境未安装 Ruff/Black，因此未运行这两个工具。

## 2026-09-05 产品 harness 证据

- 产品调用链只从显式 env 解析直连端点，未读取 Hermes、OMP、ZCode 的模型库、会话或凭据。
- 运行时固定 main-A `GLM-5.3-Flash:high`、main-B `MiniMax-M3:high`、handwriting-C `Qwen3.8-Flash-Next:low`；配置漂移直接拒绝。
- 调用前验证页图像实际字节哈希和 ClausePack 内容哈希；内容过滤仅可转同模型备用端点。
- 双主读失败不相互代笔，可同时保留多个原读道失败；手写专项读缺席记入对账。
- 聚焦 harness/调度测试 `40 passed`；完整 `tests/v2` 回归 `3700 passed, 3 skipped, 2 subtests passed`。

## 2026-09-05 持久化证据

- 新增迁移 `0020`，仅追加页级判读、对账、读道引用、受试者页覆盖和覆盖条目五张表；未改写 Phase 4 表。
- 三类主记录均保存规范列、完整合同正文和内容哈希；跨记录与页清单使用真实外键关联表。
- 写入和回读均核验页产物、资料版本、审核节点、证据快照、处理修订和条款包作用域；关联表被篡改时拒绝还原。
- 两个主读道必须同时存在才能保存对账；手写读不能替代主读。已有不可变历史时迁移拒绝降级。
- 聚焦迁移/仓储/页级流程 `40 passed`；存储层全量回归 `505 passed`；完整 `tests/v2` 回归 `3710 passed, 3 skipped, 2 subtests passed`；编译检查通过。

## 2026-09-05 Evidence Normalizer R3 接线证据

- 新增不可变 `EvidenceNormalizerPageReviewInput`，冻结 SubjectPageCoverage、ClausePack 哈希、PageReviewRecord、PageReconciliation、调用引用和作用域哈希。
- 只允许已采信且闭合的页面进入规范化；失败待复读页、缺失主读/对账、页清单或作用域漂移均失败关闭。
- R3 提示输入以采信页级事实、证据信号、手写对账和冲突为权威；OCR 只保留侧车转录与定位锚点。未指定页覆盖的历史 Phase 5 作业仍生成原有 `pages.effective_text` 输入，避免改写旧作业身份。
- 新 R3 作业的幂等范围包含页覆盖内容身份；同一页由失败复读变为成功采信时生成新的不可变覆盖身份，不与失败记录冲突。
- 聚焦回归最高 `190 passed`；完整 `tests/v2` 回归 `3714 passed, 3 skipped, 2 subtests passed`，无失败；`python -m compileall` 通过。
