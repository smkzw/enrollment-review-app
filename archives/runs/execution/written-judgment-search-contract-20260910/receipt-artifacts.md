# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 本轮仅新增两个文件：`app/services/judgment_search_artifacts.py`、`tests/v2/services/test_judgment_search_artifacts.py`；`git status` 确认无其他改动。v4 读器、results 绑定装配、ArtifactStore 全部只读复用。
- 无临床/源数据库、网络/模型调用、凭据、本地服务、安装、子委派、共享文件修改。工具披露：`apply_patch` 不可用，新文件经 ZCode Write 创建，不声明等价。
- 勘察依据（只读）：`app/evidence/artifacts.py`（`ARTIFACT_KINDS` 含 `raw_response`；`put` 内容寻址幂等去重；`read` 按内容哈希完整性复核，缺失/漂移抛 `ArtifactStoreError`/`ArtifactIntegrityError`；`StoredArtifact(kind, sha256, byte_size, storage_ref)`）、`tests/v2/conftest.py` 的 `data_paths` fixture（tmp_path V2 布局）。

## Work Performed

**两个最小助手，完全复用既有 `raw_response` 工件类别（无新框架/表/工件种类）：**

- **`save_judgment_search_receipt(store, scope, target_text, receipt) -> StoredArtifact`**：回执先经当前合同重验证，再以 `assemble_judgment_search_coverage(scope, target_text, [receipt])` 做**保存前绑定核验**（原始回答、页/目标/模型/提示身份与调用方准备的当前来源一致；单条回执覆盖不完整是合法存储状态，不检查覆盖状态），然后以 `sort_keys` 规范化 JSON 字节（完整保留内嵌原始 `PageCompletion`、逐字摘录含首尾空格、`uncertainty_note`、`coordinate_convention="unverified"`、usage/messages 哈希等元数据）走 `store.put("raw_response", ...)`。同字节 → 同 sha → 同 storage_ref。
- **`load_judgment_search_receipt(store, scope, target_text, storage_ref)`**：先拒绝非 `artifacts/raw_response/` 前缀引用（外来类别不读不猜）→ `store.read` 完整性复核（缺失/漂移包装为域错误并保留 cause）→ 复用现行读器解析器严格解析一个完整 JSON 对象（重复键/截断拒绝，无引文修复）→ 当前合同验证 → **装载后再次经 assemble 与当前 scope/target 绑定核验** → 返回已验证回执。
- **错误语义**：新增单一 `JudgmentSearchArtifactError(ValueError)` 仅覆盖存储/解码/解析/合同失败并保留 `__cause__`；与当前 scope/target 的绑定失败原样传播既有 `JudgmentSearchResultsError`（同为 ValueError 域，不再发明新分类）。损坏/外来/过时回执一律显式报错——绝不静默消失、绝不折叠成 not_found、不重标不迁移；`product_acceptance` 保存与装载后恒 False；无接受/缺口生产者/重试/作业接线。调用方负责当前 scope/target，绝不从保存的 scope 重建信任。

## Artifacts And Evidence

11 项测试（tmp_path 真实 ArtifactStore；回执经真实 v4 读器注入 fake completion 产生；复用 results 测试中真正可导入的助手）：
- 往返等值：4 条回执（含 found 首尾空格摘录、ambiguous `uncertainty_note="作者与日期不可辨"` + `coordinate_convention="unverified"`、内嵌原始 completion 全文/usage/response_id）保存→装载后与原件全字段相等；`kind=="raw_response"`。
- 同回执两次保存 → `StoredArtifact` 全等（同 ref/sha）；不同回答 → 不同 sha/ref，旧 ref 仍可装载且保持原内容（not_found 与 found 并存互不覆盖）。
- 过时目标 / 过时 scope（可重验证的不同页域）/ 过时提示版本 v3 → 拒绝（v3 在保存前即被绑定核验拒绝，且无任何字节落盘）。
- 原始回答 vs 绑定页结果不一致（合法漂移候选）→ 保存前拒绝。
- 非 raw_response 引用（真实存在的 page_image 工件 + 非法格式 ref）→ 前缀拒绝；缺失工件 → 域错误且 `__cause__` 为 `ArtifactStoreError`；篡改盘上字节 → `__cause__` 为 `ArtifactIntegrityError`；手工构造重复 JSON 键字节经既有 `put` 落盘 → 解析期拒绝（cause 为解析错误）。

## Commands And Observations

- 首跑 1 failed/10 passed：失败为测试脚手架的字典按页工件 ID 键控导致 pa-1 双读道回执互相覆盖（装配模块无缺陷）；改为逐回执 (receipt, artifact) 配对后 **11 passed**。
- 另用独立脚本确认回执 `model_dump(mode="json")` → `model_validate` 往返全等（含 completion 数据类字段），排除序列化疑点。
- 要求套件：artifacts(11) + results(14) + reader(17) + source(24) + coverage(31) → **113 passed**。`git status` 仅两个新增文件。

## Blockers Or Missing Environment

- 无阻断。工具披露：`apply_patch` 不可用（如实声明，不主张合规等价）。

## Rerun Requests Or Next Step

- 无需重跑。**仍未实现/待集成（如实申报）**：真实模型调用与路由预检、scope/target 的正式仓储调用点接线（当前由调用方准备传入）、回执引用的持久化目录/索引（本模块只做内容寻址字节存取，无登记表）、重试/限流/失败路由编排、独立双读路由回执汇总、语义核实与适用性、professional_judgment 缺失生产者。本存储层是纯工程工件存取：非持久编排、非临床验证、无任何采信或批准声明。
