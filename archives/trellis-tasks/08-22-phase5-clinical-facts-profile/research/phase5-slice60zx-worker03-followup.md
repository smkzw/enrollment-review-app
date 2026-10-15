继续同一执行会话。你上一轮因 worker_02 产物尚未落盘，未能审查本次干跑包。现在只读审查已存在的实际产物：

- `artifacts/phase5-slice60zx-virology-source-closure-20260828/`
- `runs/execution/phase5-slice60zx-virology-source-closure-20260828/worker_01.md`
- `runs/execution/phase5-slice60zx-virology-source-closure-20260828/worker_02.md`

请核对实际 `source_rows.json`、`freeze_provenance.json`、`execution/batch.json`、`execution/prompt.txt`、`prompt-audit.json`和 `dryrun-review.json`，不要以历史 V10 代替本次产物。重点验证：

1. owned 仅为 `body.p803-p805`，attached 完整包含流程第14项与 `body.p328`、EX-22 `body.p685-p689`，未借用结核等旁支源。
2. HBsAg 阴性且 HBcAb 阳性才触发 HBV-DNA；HCVAb 阳性触发 HCV-RNA；不得将抗体阳性直接当作排除。
3. 梅毒检测方向必须是“特异性抗体阳性 -> 非特异性抗体检查”；例外必须同时保留“非特异性阴性 + 研究者判断既往感染已治愈”。
4. `body.p804` 的8项筛选面板、首次给药前28天有效窗及“筛选期/基线期无需再次检查”完整；“无需再次检查”不得被解释为免除首次必要检测。
5. 28天窗只是结果有效期，不是排除标准阳性的豁免。
6. 提示层是否足以支持一次 MTPLX medium 调用，或必须停止。

保持只读，不调用模型，不发布，不修改应用。返回紧凑的补充审查报告，明确 `ACCEPT_FOR_ONE_MODEL_CALL` 或 `STOP`，并列出支撑证据与任何剩余风险。
