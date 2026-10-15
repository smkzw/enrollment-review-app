# Codex Execution Review: phase4-evidence-ocr-v2-slice43

## Verdict

**ACCEPT — Slice 4.3 已通过，可进入 Slice 4.4。**

本裁决只覆盖页产物、来源保留 OCR、共享 8 路准入、持久任务恢复和只读进度。
它不表示定位、风险核对、校对、活动指针、证据红框或用户完整工作台已经完成。

## Worker Outputs

- worker 01 完成 `0009_ocr_artifacts`、追加写仓储、单成功缓存、租约代次和不可激活基础处理修订；两次同会话修订关闭了失败页伪几何、同快照多修订和 OCR 输入闭包问题。
- worker 02 完成 PDF、图片、多帧 TIFF、TXT、DOCX、DOC 的确定性分页/渲染、原生 PDF 文字坐标和纯文字识别适配；两次同会话修订关闭了转换身份漂移、重复渲染和用户文案泄漏。
- worker 03 完成页级执行、共享 oMLX 门禁、渲染背压、晚到拒绝、取消/重试/恢复和只读进度；同会话修订补齐两类租约心跳、永久失败门禁、重试统计和进程死亡反例。
- 三名执行者均使用声明的 `Pi/cms-smk/deepseek-v4-flash:max` 路由，未触发 fallback。报告为证据，不单独构成验收。

## Manager Assessment

本执行模块无 manager，由 Codex 直接复核。独立新鲜上下文 `trellis-check`
（`gpt-5.6-luna:max`，会话 `01a01a0a-7136-7891-80ac-ac6f133a5a8c`）发现并修复：

- 完成/失败与取消同时发生时的最终状态竞争；
- 通用 Job 取消后证据候选状态未同步收敛；
- 门禁模型在排队期间漂移、心跳退出窗口丢失和错误响应未保存；
- Slice 4.3 提前运行风险扫描，越过 4.4 边界；
- Job API/SSE 将未知内部状态原样暴露给用户。

检查者终局为接受；Codex 对实际 diff 逐项审阅后保留上述修复。

## Codex Independent Verification

- 聚焦回归：`172 passed`，覆盖门禁、执行器、进度、Job API、OCR 回放、仓储、迁移、取消/恢复与 runner 竞态。
- V2 全量：`1233 passed, 58 warnings, 2 subtests passed`。
- 限定变更面 Ruff：通过；生产代码 Pyright：`0 errors, 0 warnings`；启动脚本 `zsh -n` 与 `git diff --check`：通过。
- 真实去标识化顺序探针：2/2 页逐字完全一致，响应模型均为 `GLM-OCR-bf16`，没有机器坐标，因此不画红框。
- 真实多进程探针：12/12 请求成功且逐字一致，门禁峰值为 8，完成后 OCR/翻译租约均为 0；服务日志对应 12 次真实 GLM-OCR 调用。
- 生产适配器拒绝错模型、空文本、缺少结果和格式错误响应；收到的错误响应字节进入内容寻址工件，不进入成功缓存。
- `0009` 基础修订保持不可激活，活动指针未改变，未读取仓库外临床原始资料。

剩余边界：若 provider 根本没有返回响应，或进程在收到响应后、持久化前真实死亡，进程内响应字节无法凭空重建；恢复机制会拒绝伪成功并重跑未完成页。桌面脚本仍按既定阶段边界启动 legacy 入口，V2 使用独立 `app.api.v2.app:create_app` factory，本裁决不声称桌面入口已切换。

## Cleanup Decision

保留本审查、执行者紧凑报告、两份真实探针 JSON 和任务研究记录。通过 guard 将 Slice 4.3 的 prompts/runs 归档到 `archives/execution/`；删除仓库内可再生 Python/pytest/Ruff 缓存，不删除虚拟环境、金标准、临床源文件或任何正式验收证据。
