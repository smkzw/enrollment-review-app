# Phase 5.8d 模型无关重放基础设施验收，临床重放仍暂缓

日期：2026-08-29  
分支：`codex/phase5-clinical-facts-profile`  
状态：工程切片已验收；Phase 5.8d 继续进行，`claims_complete=false`

## 本轮完成

- 建立通用、项目无关的模型无关重放包：从原始 DOCX 经正式结构化链生成冻结快照、完整清单、指定来源批次、Agent 输入与提示词，默认不创建传输层、不调用模型。
- 固化全局串行修订预算：默认传输尝试 1 次、全局结构修订最多 2 轮；错误类别采用结构化代码，不再从错误文案猜测；相同输出无进展时立即终止。
- 重放包校验现在交叉核对 summary、replay input、manifest、snapshot、batch、agent input 和每个来源单元，拒绝重复 `source_ref`、路径泄漏、身份漂移及内容不一致。
- 记录 Python、Pydantic、解析器名称和版本；真实冷导入测试证明模型无关路径不会载入 LLM/HTTP 传输模块。
- D001 p803-p805 仅作为测试锚点，配置与外部指纹已提交；产品代码中没有 D001、p803-p805 或人工矩阵特异规则。

## 决定性证据

- 聚焦回归：`73 passed in 1.32s`。
- 完整协议回归：`1033 passed, 58 warnings in 129.12s`；警告为既有 SWIG 与 Python 3.12 SQLite 弃用提示。
- `compileall`、JSON 解析和 `git diff --check` 通过。
- 两次从同一只读 D001 DOCX 构建到不同临时目录，均得到：
  - 外部指纹 `cdb75fbc9812940acf2048a44ef28455a3b3111af57611ed81ac055db21d61d3`
  - batch `pcb-b29b96bc4f027b4340ab9773`
  - manifest `su-8f734878638f87bf9ed0a23f`
  - snapshot `snp-e3e8befcbf4a63c89665aad9`
  - prompt SHA-256 `dd284765a40d24a3cb7eaf567831388cb1efee5d62d2ee9151b4cd574c75f05d`
  - 3 个 owned refs、7 个 attached refs、3581 个 blocks、1848 个 manifest units
- CodeBuddy DeepSeek V4 Flash max 同会话独立复审先提出 F1-F6，修复后第 4 轮逐项确认全部关闭；未 fallback。Codex 自行执行了测试和双构建，不以复审者无法运行 Bash 的声明替代运行证据。

## 不可越界边界

- 未调用临床 LLM/VLM，未形成新的 p803-p805 语义结果，未发布控制点；v8 仍是不可变拒绝反例。
- 当前结构化方案入口仍只支持 DOCX。PDF 可渲染不等于 PDF 可结构化解构，PDF 原始上传要求尚未完成。
- D001 检查点只用于工程回归，不是共享临床规则，也不代表临床接受。
- 工具链升级会有意触发指纹失败；只有完成两次独立构建、来源与身份核对后，才可按同目录 `REANCHOR_MODEL_FREE_REPLAY.md` 再锚定。
- 受试者、OCR、病例审核、Patient Profile、前端和浏览器均未在本轮运行。

## 下一安全动作

先在新的有界切片中实现 PDF 到统一结构单元的产品入口，使用户可直接上传原始 DOCX 或 PDF，且两种格式都进入同一来源定位与版本化合同。该切片通过确定性回归和独立审查前，不启动新的 p803-p805 临床模型重放。
