# Phase 5.8d 当前小批量方案适用性修复检查点

日期：2026-08-27

## 当前任务边界

- Trellis 任务仍为 `in_progress`，当前处于 5.8d。
- D001 II 当前冻结结构基线仍为 1,848 个全文单元、1,301 个语义目标、137 个包；本批五次运行共享同一源计划 `papl-a1b37e552acf8e0f60916c2e`、快照 `d001-ii-phase-closure-20260825-slice58e-snapshot`、源文档 SHA-256 `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98` 和提示模板 `2c0b97d0288891a9b066b8acf7a744471701f27c0438fd425ae5e4a1d3fec8c5`。
- `claims_complete=false`；未启动其余 128 包全跑、受试者审核、浏览器/视觉或三路独立测试者；无生产写入。
- 默认语义路线保持 MTPLX medium，DeepSeek 不替换默认路线。

## 真实源包运行链

本批真实运行源包 57、61、121（各 12 个冻结单元）。三次运行的接受输出分别来自不同运行：

| 运行 | 源包 | 传输预算 | 批次状态 | 未决单元 |
|---|---|---:|---|---:|
| slice59b（3 包） | 57 | 8192 | needs_review | 12 |
| slice59b（3 包） | 61 | 8192 | needs_review | 12 |
| slice59b（3 包） | 121 | 8192 | accepted | 0 |
| slice59c（2 包） | 57 | 8192 | accepted | 0 |
| slice59c（2 包） | 61 | 8192 | needs_review | 12 |
| slice59d | 61 | 16384 | needs_review | 12 |
| slice59e | 61 | 16384 | needs_review | 12 |
| slice59f（r3） | 61 | 16384 | completed | 0 |

正位（canonical）接受输出已按源包序号取各包最终被接受的一次运行，并由 worker_03 对当前 `phase5/phase-applicability-gate/v2` 第一方重放复核：

| 源包 | 正位工件 | 预算 | 单元 | 门禁 v2 重放 | 最终处置 |
|---|---|---:|---:|---|---|
| 57 | slice59c | 8192 | 12/12 | accepted，0 问题 | 1× 选定期适用 + 11× 跨期共用 |
| 61 | slice59f r3 | 16384 | 12/12 | accepted，0 问题 | 12× 跨期共用 |
| 121 | slice59b | 8192 | 12/12 | accepted，0 问题 | 12× 选定期适用 |

## 失败根因

- 包 57 首轮失败（slice59b）：3 个单元命中 `PAIRED_RULE_FAMILY_SOURCE_IGNORED`（原始出现 6 次）——冻结来源已分别显示两期均指向同一规则标题，模型单列本期且未提供对侧不适用的反证；修复后在 slice59c 以 8192 接受。
- 包 61 在 8192 首轮中先命中成对来源门禁，紧接的修复响应连续两次达到长度上限。16384 消除该截断后，59d/59e/59f 的 9 次同会话尝试又暴露独立的语义收敛循环：
  1. `TARGET_GROUP_HETEROGENEOUS`：异质目标被归入同一 v2 分组（59e-a1、59f-a1，各拒 9 单元）；
  2. `PAIRED_RULE_FAMILY_SOURCE_IGNORED`：成对来源下仅列本期（slice59b、slice59c ×13、59e-a2 ×13、59f-a2 ×13）；
  3. `SHARED_POSITIVE_SOURCE_MISSING`：声明跨期共用但未提供共用正向来源（59d-a2 ×12、59e-a3 ×13）；
  4. `CONTRADICTORY_FINAL_DISPOSITION`：相关单元共享/本期处置互相冲突（slice59b、59d-a1 ×12、59d-a2 ×10）；59d-a3 另有 1 次 `WIRE_SCHEMA_INVALID`。
- 仅 59f-a3 以 0 问题解析通过：12 单元全部判为跨期共用，每条均引用Ⅱ期与Ⅲ期设计段对同一“入选标准/排除标准”规则标题的成对来源，且无期别特异例外。
- 准确因果边界：16384 是包 61 避免 8192 修复响应截断的必要工程修复，但它不能单独解决异质分组、候选处置和成对来源闭包问题。包 57 在 8192 下接受，说明不应对所有包一概扩大输出；当前将更高预算仅保留给 MTPLX 方案批处理。
- 不确定性：59d-a3 的 `WIRE_SCHEMA_INVALID` 无法从存储工件区分是截断还是无效 JSON（只存 `raw_output_sha256`，未存原始文本）。

## 16K 输出预算独立验证

- 配置默认：`OMLX_PROTOCOL_BATCH_MAX_TOKENS=8192`、`MTPLX_PROTOCOL_BATCH_MAX_TOKENS=16384`（`app/config.py:96-101`），均可被环境变量覆盖。
- 两条传输路径独立钳制：构造参数 `max_tokens=60000` 时 MTPLX 得 16384、OMLX 得 8192。
- 聚焦预算测试 `test_mtplx_transport_has_its_own_quality_output_budget` 与 `test_mtplx_phase_transport_uses_quality_output_budget` 均通过。
- 预算测试现按导入的配置常量断言两条传输使用各自上限，不再将可通过环境变量调整的 16384 写死为不可变协议。

## Codex 逐条临床与来源核对

- 包 57：`body.p627` 为研究人群父级全局结构，按选定期适用保留；`body.p628`–`body.p638` 为官方入选标准标题、总述及全部子条目。两期设计段均明确要求“符合所有入选标准”，无期别例外，因此 11 项共用处置与来源一致。筛选和基线同时需满足 PASI/PGA/BSA、光疗或系统治疗资格以及避孕时窗均保持原文。
- 包 61：12 项均属官方排除标准，两期设计段均以“不符合任何排除标准”指向同一规则标题，共用处置可接受。阈值和逻辑未被改写：`body.p682` 仍为 ALT 或 AST 或总胆红素任一达 1.5×ULN；`body.p683`、`body.p684` 仍同时需要异常有临床意义且研究者评估可能构成不可接受风险；`body.p686` 仍为 HBsAg 阳性，或 HBcAb 阳性且 HBV-DNA 阳性。
- 包 121：12 项均位于无期别专属限定的避孕附录，对当前已固定的Ⅱ期项目按选定期适用纳入。绝经定义、筛选血妊娠试验、知情同意至末次给药后 3 个月、禁用激素避孕、研究者沟通记录及可接受/不可接受方法均保留原文。本包未提供对侧期直接来源，因此不外推为两期共用。

## 测试结构修正

- 缺陷：新用例 `test_mtplx_phase_transport_uses_quality_output_budget` 被误插入 `test_real_transport_uses_phase_schema_and_restorable_same_session_history` 中段，吞掉其 restore-history 断言尾部（引用 `first`，原 213–229 行），触发 NameError 并使原测试失去自身后半段。
- 修复：原测试恢复自包含（现 174–218 行），新预算测试独立成例（现 221–229 行）；仅改 `tests/v2/protocols/test_phase_applicability_live_execution.py`。worker_03 第一方复读确认重构区域结构完整。

## 决定性验证

- worker_03 第一方聚焦：`tests/v2/protocols/test_phase_applicability_live_execution.py` = `7 passed`。
- worker_03 第一方收集：`tests/v2/protocols --collect-only` = `785 tests collected`（基线 781 + 4 个新 live-execution 测试）。
- worker_03 第一方门禁重放：包 57/61/121 正位工件在当前 gate v2 下 3/3 accepted、0 问题。
- Codex 最终全量：`tests/v2/protocols` = `786 passed, 58 warnings in 179.99s`。
- 告警均为既有 `SwigPy*`/SQLite datetime 弃用告警，与本次无关。

## 工件

- slice59b：`artifacts/phase5-slice59b-d001-three-package-mtplx-20260827/`
- slice59c：`artifacts/phase5-slice59c-d001-two-package-mtplx-aggregate-repair-20260827/`
- slice59d：`artifacts/phase5-slice59d-d001-package61-mtplx-16k-20260827/`
- slice59e：`artifacts/phase5-slice59e-d001-package61-mtplx-candidate-alignment-20260827/`
- slice59f：`artifacts/phase5-slice59f-d001-package61-mtplx-three-repairs-20260827/`
- 执行报告：`runs/execution/phase5-slice59g-20260827/worker_01.md`、`worker_02.md`、`worker_03.md`

## 剩余边界

- `claims_complete=false`；剩余 128 包未运行；受试者、浏览器、视觉与独立测试者未启动；无生产写入。
- Codex 已对包 57/61/121 共 36 个目标的冻结原文、处置、来源和中文理由逐条核对，未发现当前期别适用性错误或 AND/OR 逻辑改写。
- 尚无编码源包 57/61/121 门禁重放的持久 pytest；当前验收基于不可变工件重放与第一方复核。

## 下一安全动作

1. 选择下一组结构风险不同的少量代表包继续有边界语义验证；不得直接全跑 128 包。
2. 不为特定源包序号增加依赖临时工件的持久 pytest；继续由通用门禁回归保护共享逻辑，小批正位工件作为临床验收证据。
3. 默认语义路线保持 MTPLX medium。
