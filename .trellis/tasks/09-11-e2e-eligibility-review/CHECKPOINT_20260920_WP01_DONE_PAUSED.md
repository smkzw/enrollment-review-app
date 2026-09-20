# CHECKPOINT 2026-09-20 v2：WP01完成，C链绑定通过真实模型运行，无损暂停

## 已完成
- WP00：V4包入档、R01-R14处置表、R13探针复现。
- WP01：predicate_binding_candidates v2合同已通过真实双模型运行（137条件全量覆盖）。
  - candidate-fact-accounting/v2 分组处置 + default_group
  - 包内短别名 (f1/L1/p01/a01)
  - 围栏剥离 × 3处
  - 控制期望模板级处置 PENDING_CONTROL_APPLICABILITY（R05修复）
  - 结构化账目即有效未决说明（不强制散文）
  - 比较层v1+v2兼容、默认处置按全集展开
  - qualification围栏剥离+unresolved_reasons格式修复
  - 预算统一 MIN/MAX_SEMANTIC_OUTPUT_TOKENS(65536-262144)
  - 前端labels/types同步
  - 34/34谓词候选测试通过

## C链真实运行进度
- 第7次尝试：predicate binding COMPLETED（双道通过，7候选、130默认处置）
- 第7次尝试：control binding COMPLETED
- 第7次尝试：predicate qualification COMPLETED
- 第7次尝试：control qualification FAILED（围栏+uncertainty空 → 已修复，第8次运行中）
- 第8次workflow 58241b3a：predicate COMPLETED, control运行中
- 下一步：control完成后 → workflow自动进verification → ready → qualified review publish

## 未完成/剩余
- 第8次workflow完成后：qualified review publish → eligibility review → 确认非全UNKNOWN
- WP02-WP08（新来源政策、低清读取、角色路由、规范化、工作台、增量、验收）

## 运行环境
- 后端8902 pid 14568+，前端5173
- 环境变量同CHECKPOINT_20260920（本轮无变化）
- commit: 4ed4c1c6
