# Codex Conference Review: phase5-slice61aq-native-pdf-structure-entry-audit-20260829

Date: 2026-08-29

## Verdict

accept_with_followup：原生文字 PDF 结构入口在补齐可复现验收证据后接受；PDF 标题、表格、多栏阅读顺序和空白/扫描页精细分流仍是下一质量切片，不宣称与 DOCX 等价。

## Boundary Compliance

参与者仅对代码、测试与工程记录做只读审查，未调用临床模型、未读取工作区外原始病例、未发布控制点。CodeBuddy 计划模式自动产生了自身本地计划记录，但没有修改项目源码或临床资料。

Hermes 治理边界：会商由 `hermes_workflow_guard.py` 生成冻结路线和只读角色提示，参与者未替换模型、未使用备选路由；Codex 独立持有最终验证与接受权。

## Participant Outputs Reviewed

审阅 `general_single_object` 的全部输出。其确认源文件哈希、物理页号、精确文本区间和坐标框的代码合同成立，也确认 DOCX 无 PDF 字段时的序列化兼容策略成立。

## Conference Panel Review

参与者提出两项阻断：真实 120 页 PDF 和 D001 终态回归当时只有汇总结论，没有可检查的持久记录。同时指出多栏页可能交错装配以及任一短页导致整份失败的产品边界。这些意见均有效。

## Main-Venue Codex Review

已补齐两项阻断证据，并把加密、损坏、零页、混合原生/扫描页固化为回归。新测试暴露 `pdfplumber` 包装密码异常的真实根因，共享打开点已修复为沿异常链识别加密文件。

多栏问题不采用单一水平间距启发式当场修补：真实方案的表格、表单字段和并排说明会共用同一特征，高误报规则会使原始 PDF 不可用。下一切片应以版面分区、栏顺序和表格结构一体处理，并独立验收。

## Codex Independent Verification

- 聚焦验证：`12 passed, 5 warnings`，包括 D001 p803-p805 终态指纹、加密、损坏、零页和混合文本层。
- 真实 SAR V2.1 PDF：两次均为 120 页、285 块，`content_sha256=7843e5e55966da24044b224e2221418d3d838bcf819cf557824702ca4ad726c3`，285/285 为直接 bbox 定位，无降级或未对齐，源文件字节与 mtime 未变。
- 持久证据：`runs/verification/phase5-slice61aq-native-pdf-structure-entry-20260829/`。
- 后端全量：`2977 passed, 1 skipped, 139 warnings, 2 subtests passed`；跳过项为既有 oMLX 探针工件不存在。
- `git diff --check` 与验证 JSON 校验通过。
- 本轮无前端逻辑新变更，先前的方案上传文案与构建验证仍有效；不重复做无实质改变的视觉测试。

## Final Decision

接受本轮“原生文字 PDF 可进入统一冻结结构链”的有限结论。不接受“PDF 与 DOCX 结构质量等价”，不启动临床模型回放，不发布新控制点。下一安全步骤是 PDF 版面分区、标题/表格恢复、多栏阅读顺序和空白/扫描页分流的独立质量切片。
