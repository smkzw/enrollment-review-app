# RETURN_B.md — Agent B 回交记录（V3 分工B：真实读取来源→事实发布→整例资料）

- **角色/时间**：Agent B（同一 ZCode 会话 zcode-20260917-agent-abc 内接管），2026-09-18 凌晨勘查，同日冻结。
- **接手来源**：RETURN_A.md 增量节 + V3 第 4–7 章 + design 短图。
- **工作树/branch/HEAD**：同 A（见 RETURN_A）；无其他写者。
- **P1/P2 状态：未开始实施（被依赖阻塞），勘查已完成**。

## 勘查结论（真实证据）
1. **真实资料已定位**：`artifacts/phase5-acceptance/20260901/isolated-inputs/sar/subjects/31001/31001/` 共 5 份 PDF（病历 9 页、筛选期检查报告单 8 页、基线血常规 1 页、乙肝DNA 1 页、入组审核邮件 5 页）。此为验收工具创建的隔离副本；原始目录未触碰。全部为**扫描件（原生文字 0 字符）**——首读必须 OCR，pdf_native 不可用（已逐份实测 pymupdf get_text）。
2. **OCR 服务已就绪（本包现场动作）**：`omlx start` 已启动 oMLX（127.0.0.1:8001，服务进程常驻），实际提供 `GLM-OCR-bf16`（与 `~/.codex/tools/omlx_workload_gate.py` 的权威 OCR 模型一致；.env 中 PaddleOCR 条目已过期，门禁覆盖模型选择，调用方不得传模型）。跨进程 OCR 并发门禁可用。下一位接手：oMLX 若已停，`omlx start --timeout 120` 即可；勿动 8002（MTPLX.app 共享 FlashNext）。
3. **硬依赖确认（P1 无法在 A 发布前从正式入口进行）**：`POST /projects/{id}/subjects` → `evidence_api_command_service.create_subject` → `list_workflow_stages_for_rule_set`（需要**已发布** rule_set）；审核节点由发布规则的 workflow stages 实例化。当前 rule_sets 空、SAR 草稿 6 项阻止发布（见 RETURN_A 最终增量）。**B 的第一动作是协助 A 清零/走解释材料通道，而非资料侧改造。**
4. 资料链代码入口核对（只读）：`evidence.py`（upload-previews/commit/snapshots）→ `evidence_upload_service`（DIRECT_VISION_PREPARATION）→ `evidence_processing_executor`（original-page-images/v1）→ page_review/fact_normalization → `fact_publication_service` 均在位；具体新读取策略改动点按 V3 4.3（先查 ReadingManifest 等价对象：`evidence_sidecar_preparation.py`/`page_review_runtime.py` 一带最接近）。

## 本次实际修改
- 无产品代码改动（勘查+服务启动+依赖验证）。
- 新增仅诊断/工具性文件：无（B 段未写代码）。

## 未决与下一安全动作（完整步骤）
1. 等 A 的 6 项清零或解释材料登记后发布（A 侧记录：`TIME_ANCHOR_UNRESOLVED` 类在门禁中天然阻塞，EX-07x 原文确无锚点日期，属真临床未决，应走 `register_interpretation_sources` 由用户登记澄清）。
2. 发布后：`POST /api/v2/projects/{project_id}/subjects`（subject_code=31001）→ 得默认筛选/基线审核节点 → `POST /subjects/{id}/evidence-upload-previews`（multipart，首份 `31001-基线血常规.pdf`）→ commit → 观察 original-page-images/v1 准备 → 接 OCR 主读取（经 omlx_gate，GLM-OCR-bf16）→ 事实发布 → `GET` 快照/Profile/原件视图验证可回源。
3. 预期观察：previews→commit→snapshot 状态流转、页图准备完成、OCR 文本+输入图身份存档、事实带页级来源、原件查看器可打开（UI /subjects）。
- **临床待澄清**：无新增（EX-07x/EX-04 锚点属 A 侧方案解释问题，已记录）。
- **技术阻塞**：A 的发布闸门（全局关键路径）。
- **普通剩余**：新读取策略代码（V3 4.4 判别联合来源、读取清单）尚未设计实施——待 P1 实跑观察现有链行为后做最小增量，避免预先平台化。

## 对其他包的影响
- 无（未改任何共享文件）。
- C：P3 依赖 A 发布 + B 事实，二者均未就绪；C 未开始（本会话未接管 C，无 RETURN_C）。

## 回滚/恢复
- oMLX 服务：`omlx stop` 可停（我启动的）；其余无改动。
- 任务未完成不 archive；B 段无 DB 写入。
