# 模型无关重放检查点再锚定

本目录的 `p803-p805-model-free-replay-config.v1.json` 与
`p803-p805-model-free-replay-checkpoint.v1.json` 共同构成只读回归锚点。
它只证明同一原始 DOCX 经当前产品结构化链可重现，不授权模型调用，
也不代表任何控制点或临床结论已被接受。

## 何时允许再锚定

仅当 Python、Pydantic、DOCX 结构解析器或确定性产品链发生有意变更，
并且现有检查点因此失败时，才允许再锚定。普通代码失败、来源哈希变化、
单次构建漂移或临床输出变化不得通过更新检查点绕过。

## 操作步骤

在仓库工作树根目录执行：

```bash
CONFIG=.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/checkpoints/p803-p805-model-free-replay-config.v1.json
PACK_A="$(mktemp -d)/pack"
PACK_B="$(mktemp -d)/pack"

.venv/bin/python scripts/run_protocol_replay_harness.py \
  --config "$CONFIG" --out-dir "$PACK_A" --verify
.venv/bin/python scripts/run_protocol_replay_harness.py \
  --config "$CONFIG" --out-dir "$PACK_B" --verify

.venv/bin/python scripts/run_protocol_replay_harness.py \
  --verify-pack "$PACK_A" --expected-fingerprint '<旧检查点指纹>'
.venv/bin/python scripts/run_protocol_replay_harness.py \
  --verify-pack "$PACK_B" --expected-fingerprint '<旧检查点指纹>'
```

如果旧指纹因预期中的工具链变更而失效，应先分别读取两次构建输出中的
新指纹，确认两者完全一致，再人工核对以下内容后更新检查点：

- 原始方案 SHA-256 未变化；
- owned/attached source refs 未变化；
- batch、manifest、snapshot、prompt 身份稳定；
- 两个重放包的外部指纹完全一致；
- `model_invoked=false`、`clinical_acceptance=false`；
- 聚焦测试和完整协议回归通过。

更新后再次以新指纹运行两次 `--verify-pack`。不得将临时重放包提交到仓库，
不得把再锚定写成临床验收或 PDF 结构化解析已完成。
