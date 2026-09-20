# Codex Main-Venue Plan: medication-component-review-20260909

Date: 2026-09-09
Objective: 独立审阅用药分项隔离扩测v2的来源保真、时间角色、残缺药名与正式接入边界；找出必要修订，不作临床验收

## Task Decomposition

单一只读审阅隔离分项合同、原始模型回执和测试。所有者负责原图核对、修订和最终集成，不授权产品自动采信。

## Source Packet

scripts/medication_component_experiment.py、对应测试、medication-components-v2-*；第二轮核v3及targeted结果。原图未交由审阅者判读，不将其结论称为独立临床QC。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/medication-component-review-20260909/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

两轮自然终态，同一会话sess_3a8e0968-ac42-4d50-aa58-c63438929c90，无fallback。首轮411.302秒，第二轮272.405秒（runner回执）；120分钟外部等待限额未触发。第二轮针对必要修订核验，不是新模型意见。

## Codex Verification Checklist

核验实际模型GLM-5.3:max、原文子串与药物归属的区别、区间/非法日期/遗漏处理。42项复核基础测试，后续所有者补区间前后文字反例到44项；新增诊断输入及产品读页合计104项通过。没有临床库写入；正式接入保持未批准。
