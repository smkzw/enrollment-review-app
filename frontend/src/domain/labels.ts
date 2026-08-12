/**
 * 中文显示词映射：值与 `contracts/v1/interaction/DESIGN_CONTRACT.md`
 * 1.1/1.2/1.3 节与 6.1 节固定中文词一致。内部枚举永不出现在可见文案。
 * 映射必须穷尽：新增枚举值若未在此登记，编译期即失败。
 */

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
} from "./enums";

/** 穷尽检查辅助：switch 缺分支或映射缺键时编译失败。 */
export function assertNever(value: never): never {
  throw new Error(`未登记的枚举值：${String(value)}`);
}

export const stageLabel: Record<ReviewStage, string> = {
  pre_screening: "预筛期",
  screening: "筛选期",
  run_in: "导入/洗脱期",
  baseline: "基线/随机前",
};

export const stageOrder: readonly ReviewStage[] = [
  "pre_screening",
  "screening",
  "run_in",
  "baseline",
];

export const mainStatusLabel: Record<EpisodeMainStatus, string> = {
  clear_barrier: "明确障碍",
  current_gap: "当前节点缺口",
  conflict: "存在冲突",
  professional_judgment: "需专业判断",
  future_attention: "后续节点关注",
  no_clear_barrier: "未发现明确障碍",
};

export const decisionLabel: Record<ComponentDecision, string> = {
  inclusion_met: "满足",
  inclusion_not_met: "不满足",
  exclusion_not_triggered: "未触发",
  exclusion_triggered: "已触发",
  indeterminate: "暂不能明确",
  professional_judgment: "需专业判断",
  conflict: "存在冲突",
  not_due: "尚未到期",
  not_applicable: "不适用",
  requirement_met: "已满足",
  requirement_not_met: "未满足",
};

export const gapTypeLabel: Record<GapType, string> = {
  record_incomplete: "记录不完整",
  description_insufficient: "描述不充分",
  historical_source_unavailable: "既往来源无法取得",
  referenced_file_missing: "引用资料未提供",
  required_procedure_not_done: "必做检查未完成",
  result_fields_missing: "结果字段缺失",
  date_or_anchor_missing: "日期或时间锚点缺失",
  professional_judgment: "待研究者判断",
  source_conflict: "来源存在冲突",
  interpretation_conflict: "解释材料与方案不一致",
  ocr_or_parse_risk: "文字或数值需要核对",
  future_stage_not_due: "后续节点尚未到期",
  provenance_followup: "溯源待办",
};

/** 阻断程度：长说明 + 短徽标词。溯源待办/关注类一律不称为“阻断”。 */
export const blockingLevelLabel: Record<BlockingLevel, string> = {
  blocking: "阻断当前节点",
  attention: "不阻断，需后续关注",
  none: "不阻断",
};

export const blockingLevelBadge: Record<BlockingLevel, string> = {
  blocking: "阻断",
  attention: "关注",
  none: "无",
};

export const actionTargetLabel: Record<ActionTarget, string> = {
  investigator: "研究者方",
  crc: "CRC",
  cra: "CRA",
  sponsor_medical_or_project: "申办方医学或项目组",
};

export const actionStateLabel: Record<ActionState, string> = {
  open: "待处理",
  closed_system: "已由系统关闭",
  closed_manual: "已人工确认关闭",
  reopened: "已重新打开",
  superseded: "已被新资料取代",
};

export const precisionLabel: Record<LocatorPrecision, string> = {
  bbox: "坐标区域",
  text_range: "文本范围",
  page_excerpt: "页内摘录",
  page_only: "仅页码",
};

export const expectationStatusLabel: Record<ExpectationStatus, string> = {
  observed: "已找到",
  observed_weak: "证据较弱",
  referenced_missing: "已引用但资料未提供",
  absent: "尚未见到",
  not_due: "后续节点尚未到期",
};

export const laneLabel: Record<ProfileLane, string> = {
  study_milestone: "研究节点",
  demographics: "人口学",
  target_disease: "目标疾病",
  symptoms_signs: "症状体征",
  medical_history: "既往史",
  medication: "用药",
  non_drug_treatment: "非药物处理",
  test_exam_score: "检查与评分",
  allergy_infection_immune: "过敏/感染/免疫",
  reproductive: "生育相关",
  social_environmental: "社会环境",
  special_history: "特殊经历",
  evidence_quality: "资料质量",
};

export const logicalOperatorLabel: Record<LogicalOperator, string> = {
  all: "全部满足",
  any: "任一满足",
  not: "不满足以下条件",
};

export const ruleKindLabel: Record<RuleKind, string> = {
  inclusion: "入选条件",
  exclusion: "排除条件",
  required_procedure: "必做检查",
};

export const comparatorLabel: Record<Comparator, string> = {
  eq: "等于",
  ne: "不等于",
  gt: "大于",
  gte: "大于等于",
  lt: "小于",
  lte: "小于等于",
  in: "属于",
  not_in: "不属于",
  exists: "存在",
};

export const polarityLabel: Record<FactPolarity, string> = {
  affirmed: "明确记载",
  negated: "明确否认",
  unknown: "未记录",
};

export const datePrecisionLabel: Record<DatePrecision, string> = {
  day: "日",
  month: "月",
  year: "年",
  unknown: "未记录",
};

/** 任务可见状态词（交互合同 1.3 节）。 */
export const taskStateLabel: Record<TaskState, string> = {
  queued: "准备中",
  running: "正在整理资料",
  completed: "已完成",
  partial: "部分资料尚未处理",
  failed: "处理失败，可重试",
  resumable: "已保存进度，可继续",
  cancelled: "已取消",
  stale: "资料发生变化，当前结果需要重新核对",
};

export const jobEventTypeLabel: Record<JobEventType, string> = {
  created: "已建立",
  step_started: "开始整理资料",
  step_completed: "完成一项资料整理",
  step_failed: "一项资料整理失败",
  retry_scheduled: "已安排重试",
  cancel_requested: "已请求停止",
  cancelled: "已取消",
  completed: "已完成",
};

/** 固定界面短语（交互合同 6.2/8 节），供 UI 与测试共用，避免散落复制。 */
export const UI_PHRASES = {
  /** 证据缺失：资料中提到这份文件，但当前尚未提供 */
  evidenceMissing: "资料中提到这份文件，但当前尚未提供",
  /** 正在加载 */
  loading: "正在整理资料，请稍候",
  /** 空集合 */
  empty: "当前没有符合条件的资料",
  /** 无待办 */
  noTodos: "当前没有待处理事项",
  /** 暂时失败 */
  temporarilyUnavailable: "这部分资料暂时打不开。已经保存目前进度。请稍后再试；如果仍无法打开，请记录页面上的事项编号并联系系统支持人员。",
  /** 界面试用标记：避免让用户误以为示例操作已保存到项目资料 */
  prototypeOnly: "界面试用",
  /** 定位精度前缀 */
  precisionPrefix: "定位精度",
  /** 定位降级原因前缀 */
  degradationPrefix: "定位降级原因",
} as const;
