# Phase 5.8d Package 111 方案修订权威与版本表边界验收检查点

## 当前状态

- 当前不可变计划为 `papl-e17d498106b6f71f440ff2be`：1848个结构单元、1240个语义目标、131个包。
- Package111 `pap-214ce50fd89fb1998521c4c3` 已验收；剩余96包，`claims_complete=false`。
- 未调用临床语义模型，未发布，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

## 来源与语义边界

- 只拥有 `body.p1291`、`body.p1292`、`body.t15.r0`、`body.t15.r1`；37项语境全部只读，第110包止于 `body.p1290`，第112包从 `body.p1295` 开始。
- `body.p1292` 保留方案修订的唯一授权链：必要变更须形成方案修订，经申办者和主要研究者签字，并提交伦理委员会审批或备案。这是项目级权威与版本治理，不是受试者级入排条件。
- 版本表头只表达列结构；V1.0行只证明初始版本及2025年12月10日。`NA/NA` 不证明既往修订、变更内容或理由。
- `body.t15`、`body.t15.r2.c0.p0` 至 `body.t15.r7.c3.p0` 的24个空白单元及 `body.p1293-p1294` 均以精确来源身份排除，防止把版本表预留空槽虚构为修订历史。
- 四项拥有来源经逐项原文判断后为零受试者级候选，不是根据章节名或预设数量自动归零。

## 工件与验证

- 配置：`representative_group_package111_protocol_amendment_authority_version_table_boundary.v1.json`，SHA-256 `41d0e1cdaa419aefa36fd078dd2086c95152c6d550636e73943d307f0f4b96a6`。
- 清单：`slice61cx-package111-protocol-amendment-authority-version-table-boundary-parent-checklist.md`，SHA-256 `2dec320a826f9dd3dfba8b23598cff603ad319e03ec0fd0308cefe6e3e3edc52`。
- 测试：`test_slice61cx_package111_protocol_amendment_authority_version_table_boundary.py`，SHA-256 `44895ba04a7da57f02b58602f08a847faaf0a872e41ad4b9de0082dd9565f33b`。
- 模型外准备 `4 owned / 0 attached / 4 total`；专项 `29 passed, 5 warnings`；Package103-111及共享语义 `268 passed, 5 warnings`。警告仅为既有 SWIG/PyMuPDF 弃用提示。
- 四路 `cursor/default` 均 return code 0、`fallback=null`；父级修正后的实际工件已由独立第四路复跑验收。
- 正式 `review-gate --require-verification` 与 `audit-execution` 均返回 `ok=true`。

## 下一安全动作

从冻结计划重新核对 Package112 `pap-fa6b2b871b90b62bbfe81775` 拥有的 `body.p1295-p1306`，保持Package111边界，不预设候选数。
