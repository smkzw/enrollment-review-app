/**
 * 中文标签映射测试：验证与交互合同固定中文词一致、穷尽无遗漏、
 * 无重复值、且可见文案不含内部实现词。
 */

import { describe, expect, it } from "vitest";
import {
  actionStateLabel,
  actionTargetLabel,
  blockingLevelBadge,
  blockingLevelLabel,
  comparatorLabel,
  datePrecisionLabel,
  decisionLabel,
  expectationStatusLabel,
  gapTypeLabel,
  jobEventTypeLabel,
  laneLabel,
  logicalOperatorLabel,
  mainStatusLabel,
  polarityLabel,
  precisionLabel,
  ruleKindLabel,
  stageLabel,
  taskStateLabel,
  UI_PHRASES,
} from "../domain/labels";
import type {
  ActionState,
  ActionTarget,
  BlockingLevel,
  Comparator,
  ComponentDecision,
  DatePrecision,
  EpisodeMainStatus,
  ExpectationStatus,
  FactPolarity,
  GapType,
  JobEventType,
  LocatorPrecision,
  LogicalOperator,
  ProfileLane,
  ReviewStage,
  RuleKind,
  TaskState,
} from "../domain/enums";

const ALL_LABEL_MAPS = {
  stageLabel,
  mainStatusLabel,
  decisionLabel,
  gapTypeLabel,
  blockingLevelLabel,
  blockingLevelBadge,
  actionTargetLabel,
  actionStateLabel,
  precisionLabel,
  expectationStatusLabel,
  laneLabel,
  logicalOperatorLabel,
  ruleKindLabel,
  comparatorLabel,
  polarityLabel,
  datePrecisionLabel,
  taskStateLabel,
  jobEventTypeLabel,
} as const;

/** 内部实现词：可见中文文案不得出现（合同 1.1/1.2/10 节） */
const FORBIDDEN_WORDS = [
  "stub",
  "gate",
  "schema",
  "hash",
  "agent",
  "pipeline",
  "job",
  "span",
  "fixture",
  "api",
  "log",
  "stale",
  "revision",
  "bbox",
  "uuid",
  "prompt",
  "model",
  "token",
  "key",
];

describe("中文标签：合同词核对", () => {
  it("主状态词与交互合同 1.1 节一致", () => {
    expect(mainStatusLabel.clear_barrier).toBe("明确障碍");
    expect(mainStatusLabel.current_gap).toBe("当前节点缺口");
    expect(mainStatusLabel.conflict).toBe("存在冲突");
    expect(mainStatusLabel.professional_judgment).toBe("需专业判断");
    expect(mainStatusLabel.future_attention).toBe("后续节点关注");
    expect(mainStatusLabel.no_clear_barrier).toBe("未发现明确障碍");
  });

  it("判断词与交互合同 1.1 节一致", () => {
    expect(decisionLabel.inclusion_met).toBe("满足");
    expect(decisionLabel.inclusion_not_met).toBe("不满足");
    expect(decisionLabel.exclusion_not_triggered).toBe("未触发");
    expect(decisionLabel.exclusion_triggered).toBe("已触发");
    expect(decisionLabel.indeterminate).toBe("无法判定");
    expect(decisionLabel.not_due).toBe("尚未到期");
    expect(decisionLabel.not_applicable).toBe("不适用");
    expect(decisionLabel.requirement_met).toBe("已满足");
    expect(decisionLabel.requirement_not_met).toBe("未满足");
  });

  it("缺口词与交互合同 1.2 节一致（14 类）", () => {
    expect(gapTypeLabel.record_incomplete).toBe("记录不完整");
    expect(gapTypeLabel.description_insufficient).toBe("描述不充分");
    expect(gapTypeLabel.historical_source_unavailable).toBe("既往来源无法取得");
    expect(gapTypeLabel.referenced_file_missing).toBe("引用资料未提供");
    expect(gapTypeLabel.required_procedure_not_done).toBe("必做检查未完成");
    expect(gapTypeLabel.result_fields_missing).toBe("结果字段缺失");
    expect(gapTypeLabel.date_or_anchor_missing).toBe("日期或时间锚点缺失");
    expect(gapTypeLabel.professional_judgment).toBe("待研究者判断");
    expect(gapTypeLabel.observation_unverified).toBe("待研究者判断");
    expect(gapTypeLabel.source_conflict).toBe("来源存在冲突");
    expect(gapTypeLabel.interpretation_conflict).toBe("解释材料与方案不一致");
    expect(gapTypeLabel.ocr_or_parse_risk).toBe("文字或数值需要核对");
    expect(gapTypeLabel.future_stage_not_due).toBe("后续节点尚未到期");
    expect(gapTypeLabel.provenance_followup).toBe("来源待补充核实");
  });

  it("定位精度词与交互合同 6.1 节一致", () => {
    expect(precisionLabel.bbox).toBe("坐标区域");
    expect(precisionLabel.text_range).toBe("文本范围");
    expect(precisionLabel.page_excerpt).toBe("页内摘录");
    expect(precisionLabel.page_only).toBe("仅页码");
  });

  it("任务词与交互合同 1.3 节一致", () => {
    expect(taskStateLabel.queued).toBe("准备中");
    expect(taskStateLabel.running).toBe("正在整理资料");
    expect(taskStateLabel.completed).toBe("已完成");
    expect(taskStateLabel.partial).toBe("部分资料尚未处理");
    expect(taskStateLabel.failed).toBe("处理失败，可重试");
    expect(taskStateLabel.resumable).toBe("已保存进度，可继续");
    expect(taskStateLabel.cancelled).toBe("已取消");
    expect(taskStateLabel.stale).toBe("资料发生变化，当前结果需要重新核对");
  });

  it("责任方只用合同允许的中文（研究者方/CRC/CRA/申办方医学或项目组）", () => {
    expect(actionTargetLabel.investigator).toBe("研究者方");
    expect(actionTargetLabel.crc).toBe("CRC");
    expect(actionTargetLabel.cra).toBe("CRA");
    expect(actionTargetLabel.sponsor_medical_or_project).toBe("申办方医学或项目组");
  });

  it("溯源待办/后续关注不称为阻断（阻断语义分离）", () => {
    expect(blockingLevelLabel.blocking).toBe("阻断当前节点");
    expect(blockingLevelLabel.attention).toBe("不阻断，需后续关注");
    expect(blockingLevelLabel.none).toBe("不阻断");
    expect(blockingLevelBadge.attention).not.toBe("阻断");
    expect(blockingLevelBadge.none).not.toBe("阻断");
  });

  it("逻辑词与交互合同 5.1 节一致", () => {
    expect(logicalOperatorLabel.all).toBe("全部满足");
    expect(logicalOperatorLabel.any).toBe("任一满足");
    expect(logicalOperatorLabel.not).toBe("不满足以下条件");
  });

  it("固定界面短语可用", () => {
    expect(UI_PHRASES.precisionPrefix).toBe("定位精度");
    expect(UI_PHRASES.degradationPrefix).toBe("定位范围说明");
    expect(UI_PHRASES.evidenceMissing).toBe("资料中提到这份文件，但当前尚未提供");
    expect(UI_PHRASES.prototypeOnly).toBe("界面试用");
    expect(UI_PHRASES.noTodos).toBe("当前没有待处理事项");
  });
});

describe("中文标签：穷尽与卫生", () => {
  it("每个枚举值都有非空中文标签（穷尽映射）", () => {
    const enumValues: Record<string, readonly string[]> = {
      ReviewStage: Object.keys(stageLabel),
      EpisodeMainStatus: Object.keys(mainStatusLabel),
      ComponentDecision: Object.keys(decisionLabel),
      GapType: Object.keys(gapTypeLabel),
      BlockingLevel: Object.keys(blockingLevelLabel),
      ActionTarget: Object.keys(actionTargetLabel),
      ActionState: Object.keys(actionStateLabel),
      LocatorPrecision: Object.keys(precisionLabel),
      ExpectationStatus: Object.keys(expectationStatusLabel),
      ProfileLane: Object.keys(laneLabel),
      LogicalOperator: Object.keys(logicalOperatorLabel),
      RuleKind: Object.keys(ruleKindLabel),
      Comparator: Object.keys(comparatorLabel),
      FactPolarity: Object.keys(polarityLabel),
      DatePrecision: Object.keys(datePrecisionLabel),
      TaskState: Object.keys(taskStateLabel),
      JobEventType: Object.keys(jobEventTypeLabel),
    };
    const schemas: Record<string, readonly string[]> = {
      ReviewStage: ["pre_screening", "screening", "run_in", "baseline"],
      EpisodeMainStatus: [
        "clear_barrier",
        "current_gap",
        "conflict",
        "professional_judgment",
        "future_attention",
        "no_clear_barrier",
      ],
      ComponentDecision: [
        "inclusion_met",
        "inclusion_not_met",
        "exclusion_not_triggered",
        "exclusion_triggered",
        "indeterminate",
        "professional_judgment",
        "conflict",
        "not_due",
        "not_applicable",
        "requirement_met",
        "requirement_not_met",
      ],
      GapType: [
        "observation_unverified",
        "record_incomplete",
        "description_insufficient",
        "historical_source_unavailable",
        "referenced_file_missing",
        "required_procedure_not_done",
        "result_fields_missing",
        "date_or_anchor_missing",
        "professional_judgment",
        "source_conflict",
        "interpretation_conflict",
        "ocr_or_parse_risk",
        "future_stage_not_due",
        "provenance_followup",
      ],
      BlockingLevel: ["none", "attention", "blocking"],
      ActionTarget: [
        "investigator",
        "crc",
        "cra",
        "sponsor_medical_or_project",
      ],
      ActionState: ["open", "closed_system", "closed_manual", "reopened", "superseded"],
      LocatorPrecision: ["bbox", "text_range", "page_excerpt", "page_only"],
      ExpectationStatus: ["observed", "observed_weak", "referenced_missing", "absent", "not_due"],
      ProfileLane: [
        "study_milestone",
        "demographics",
        "target_disease",
        "symptoms_signs",
        "medical_history",
        "medication",
        "non_drug_treatment",
        "test_exam_score",
        "allergy_infection_immune",
        "reproductive",
        "social_environmental",
        "special_history",
        "evidence_quality",
      ],
      LogicalOperator: ["all", "any", "not"],
      RuleKind: ["inclusion", "exclusion", "required_procedure"],
      Comparator: ["eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "exists"],
      FactPolarity: ["affirmed", "negated", "unknown"],
      DatePrecision: ["day", "month", "year", "unknown"],
      TaskState: [
        "queued",
        "running",
        "completed",
        "partial",
        "failed",
        "resumable",
        "cancelled",
        "stale",
      ],
      JobEventType: [
        "created",
        "step_started",
        "step_completed",
        "step_failed",
        "retry_scheduled",
        "cancel_requested",
        "cancelled",
        "completed",
      ],
    };
    for (const [name, values] of Object.entries(schemas)) {
      expect(enumValues[name], `${name} 映射键与 schema 枚举一致`).toEqual(
        expect.arrayContaining([...values]),
      );
      expect(enumValues[name], `${name} 映射无多余键`).toHaveLength(values.length);
    }
  });

  it("映射无空值、无重复值", () => {
    for (const [name, map] of Object.entries(ALL_LABEL_MAPS)) {
      const entries = Object.entries(map as Record<string, string>);
      for (const [key, label] of entries) {
        expect(label.trim().length, `${name}.${key} 非空`).toBeGreaterThan(0);
      }
      const values = entries.map(([, label]) => label);
      // observation_unverified 与 professional_judgment 都表示需研究者判断，
      // 按前端契约使用同一中文标签，允许这一组有意别名。
      const expectedUniqueCount =
        name === "gapTypeLabel" ? values.length - 1 : values.length;
      expect(new Set(values).size, `${name} 无意外重复标签`).toBe(
        expectedUniqueCount,
      );
    }
  });

  it("可见文案不含内部实现词", () => {
    for (const [name, map] of Object.entries(ALL_LABEL_MAPS)) {
      for (const [key, label] of Object.entries(map as Record<string, string>)) {
        for (const word of FORBIDDEN_WORDS) {
          expect(
            label.toLowerCase(),
            `${name}.${key} 的标签不得包含实现词 ${word}`,
          ).not.toContain(word);
        }
      }
    }
  });

  it("任务状态词不含内部 job/checkpoint 术语", () => {
    for (const label of Object.values(taskStateLabel)) {
      expect(label).not.toMatch(/job|checkpoint|stale|queue|retry/i);
    }
  });
});

describe("中文标签：类型穷尽守卫", () => {
  it("标签映射类型与枚举联合一一对应（编译期检查）", () => {
    const check = <K extends string>(_map: Record<K, string>) => undefined;
    check<ReviewStage>(stageLabel);
    check<EpisodeMainStatus>(mainStatusLabel);
    check<ComponentDecision>(decisionLabel);
    check<GapType>(gapTypeLabel);
    check<BlockingLevel>(blockingLevelLabel);
    check<ActionTarget>(actionTargetLabel);
    check<ActionState>(actionStateLabel);
    check<LocatorPrecision>(precisionLabel);
    check<ExpectationStatus>(expectationStatusLabel);
    check<ProfileLane>(laneLabel);
    check<LogicalOperator>(logicalOperatorLabel);
    check<RuleKind>(ruleKindLabel);
    check<Comparator>(comparatorLabel);
    check<FactPolarity>(polarityLabel);
    check<DatePrecision>(datePrecisionLabel);
    check<TaskState>(taskStateLabel);
    check<JobEventType>(jobEventTypeLabel);
  });
});
