/**
 * 前端领域 ViewModel：组件只消费这些可显示模型，不接触 API wire 结构。
 * 结构由 `contracts/v1/fixtures` 经 mappers.ts 转换而来，转换逻辑有单元测试。
 */

import type {
  ActionState,
  ActionTarget,
  BlockingLevel,
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
import type {
  ActionId,
  AssessmentId,
  ConflictGroupId,
  EvidenceSnapshotId,
  EvidenceSpanId,
  ExpectationId,
  FactId,
  JobId,
  ProfileEventId,
  ProjectId,
  RequirementId,
  ReviewEpisodeId,
  ReviewRunId,
  RuleComponentId,
  RuleId,
  RuleSetId,
  SourceDocumentVersionId,
  SubjectId,
  WorkflowStageId,
} from "./ids";

export interface DateValueView {
  value: string;
  precision: DatePrecision;
  precisionLabel: string;
  sourceText: string | null;
}

export interface ProjectSummaryView {
  projectId: ProjectId;
  projectCode: string;
  projectName: string;
  studyPhase: string;
  protocolVersion: string;
  protocolOfficialDate: string;
  ruleSetId: RuleSetId;
  primarySubjectCount: number;
  episodeCount: number;
}

export interface SubjectSummaryView {
  subjectId: SubjectId;
  subjectCode: string;
  centerCode: string;
  centerName: string;
  ageYears: number | null;
  sex: string | null;
}

export interface StageInfoView {
  stage: ReviewStage;
  stageLabel: string;
  visitWindow: string;
  reviewRequired: boolean;
  workflowStageId: WorkflowStageId;
}

export interface EpisodeCountsView {
  barrier: number;
  conflict: number;
  currentGap: number;
  professionalJudgment: number;
  provenanceFollowup: number;
  futureAttention: number;
  /** 按缺口类型计数（含后续节点缺口），用于看板分类显示 */
  gapCounts: ReadonlyArray<GapCountItemView>;
}

export interface GapCountItemView {
  gapType: GapType;
  label: string;
  count: number;
}

/** 看板行：受试者 × 独立审核节点。阶段永不合并为一个总状态。 */
export interface EpisodeSummaryView {
  episodeId: ReviewEpisodeId;
  subjectId: SubjectId;
  subjectCode: string;
  stage: ReviewStage;
  stageLabel: string;
  mainStatus: EpisodeMainStatus;
  mainStatusLabel: string;
  sortRank: number;
  counts: EpisodeCountsView;
  evidenceSnapshotId: EvidenceSnapshotId;
  revision: number;
  /** 从摘要进入工作台时优先打开的风险子项；仅用于导航，不改变审核结论。 */
  focusComponentId: RuleComponentId | null;
}

export interface BoardView {
  project: ProjectSummaryView;
  subjects: ReadonlyArray<SubjectSummaryView>;
  episodes: ReadonlyArray<EpisodeSummaryView>;
  stages: ReadonlyArray<StageInfoView>;
  primarySubjectIds: ReadonlyArray<SubjectId>;
  templateEpisodeIds: ReadonlyArray<ReviewEpisodeId>;
}

export interface EvidenceLocatorView {
  spanId: EvidenceSpanId;
  documentVersionId: SourceDocumentVersionId;
  fileName: string;
  documentType: string;
  pageNumber: number;
  precision: LocatorPrecision;
  precisionLabel: string;
  /** 定位降级原因；无降级为 null */
  degradationReason: string | null;
  excerpt: string | null;
  /** text_range 定位的字符区间 */
  textRange: { start: number; end: number } | null;
  /** bbox 坐标区域；非 bbox 恒为 null，禁止伪造高亮 */
  bbox: { x0: number; y0: number; x1: number; y1: number } | null;
}

export interface ProfileEventView {
  eventId: ProfileEventId;
  lane: ProfileLane;
  laneLabel: string;
  eventType: string;
  title: string;
  riskLabels: ReadonlyArray<string>;
  isAbnormal: boolean;
  isCritical: boolean;
  hasTrendChange: boolean;
  startDate: DateValueView | null;
  endDate: DateValueView | null;
  relatedRuleComponentIds: ReadonlyArray<RuleComponentId>;
  factIds: ReadonlyArray<FactId>;
  evidence: ReadonlyArray<EvidenceLocatorView>;
}

export interface ProfileLaneView {
  lane: ProfileLane;
  laneLabel: string;
  events: ReadonlyArray<ProfileEventView>;
}

export interface EvidenceExpectationView {
  expectationId: ExpectationId;
  requirementId: RequirementId;
  gapType: GapType;
  gapLabel: string;
  status: ExpectationStatus;
  statusLabel: string;
  evidenceSpanIds: ReadonlyArray<EvidenceSpanId>;
}

export interface PatientProfileView {
  patientProfileId: string;
  subjectId: SubjectId;
  reviewEpisodeId: ReviewEpisodeId;
  stale: boolean;
  highlightedEventIds: ReadonlyArray<ProfileEventId>;
  missingExpectationIds: ReadonlyArray<ExpectationId>;
  lanes: ReadonlyArray<ProfileLaneView>;
  expectations: ReadonlyArray<EvidenceExpectationView>;
}

export interface ConflictGroupView {
  conflictGroupId: ConflictGroupId;
  factIds: ReadonlyArray<FactId>;
  affectedRuleComponentIds: ReadonlyArray<RuleComponentId>;
  resolved: boolean;
  /** 冲突来源并列展示，不隐藏为“系统选择” */
  facts: ReadonlyArray<FactView>;
}

export interface FactView {
  factId: FactId;
  factType: string;
  polarity: FactPolarity;
  polarityLabel: string;
  certainty: number | null;
  value: boolean | number | string | null;
  evidenceSpanIds: ReadonlyArray<EvidenceSpanId>;
}

export interface ActionView {
  actionId: ActionId;
  episodeId: ReviewEpisodeId;
  subjectCode: string;
  assessmentId: AssessmentId | null;
  ruleComponentId: RuleComponentId;
  displayCode: string;
  gapType: GapType;
  gapLabel: string;
  blockingLevel: BlockingLevel;
  blockingLabel: string;
  blockingBadge: string;
  targetParty: ActionTarget;
  targetPartyLabel: string;
  requestedAction: string;
  acceptableEvidence: string;
  dueStage: ReviewStage;
  dueStageLabel: string;
  state: ActionState;
  stateLabel: string;
  reviewRunId: ReviewRunId;
  revision: number;
}

export interface JobEventView {
  jobEventId: string;
  eventType: JobEventType;
  eventTypeLabel: string;
  occurredAt: string;
  attempt: number;
  stepId: string | null;
  progressCompleted: number;
  progressTotal: number;
  retryable: boolean;
}

export interface JobView {
  jobId: JobId;
  reviewEpisodeId: ReviewEpisodeId;
  subjectCode: string;
  stage: ReviewStage;
  stageLabel: string;
  state: TaskState;
  stateLabel: string;
  progressCompleted: number;
  progressTotal: number;
  retryable: boolean;
  checkpointId: string | null;
  lastEventAt: string;
  events: ReadonlyArray<JobEventView>;
}

export interface ComponentDecisionView {
  componentId: RuleComponentId;
  displayCode: string;
  decision: ComponentDecision;
  decisionLabel: string;
  blockingLevel: BlockingLevel;
  gapTypes: ReadonlyArray<GapType>;
  gapLabels: ReadonlyArray<string>;
}

export interface PredicateNodeView {
  kind: "predicate";
  predicateId: string;
  subject: string;
  attribute: string;
  comparator: string;
  comparatorLabel: string;
  value: boolean | number | string | null;
  unit: string | null;
  requiresProfessionalJudgment: boolean;
  timeConstraint: string | null;
}

export interface LogicNodeView {
  kind: "logic";
  operator: LogicalOperator;
  operatorLabel: string;
  children: ReadonlyArray<ExpressionNodeView>;
}

export type ExpressionNodeView = PredicateNodeView | LogicNodeView;

export interface RuleComponentView {
  componentId: RuleComponentId;
  parentRuleId: RuleId;
  displayCode: string;
  title: string;
  expression: ExpressionNodeView;
  exceptionExpression: ExpressionNodeView | null;
  evidenceRequirements: ReadonlyArray<{
    requirementId: RequirementId;
    factType: string;
    dueStage: ReviewStage;
    dueStageLabel: string;
    description: string;
  }>;
  decision: ComponentDecisionView | null;
  actions: ReadonlyArray<ActionView>;
  evidence: ReadonlyArray<EvidenceLocatorView>;
}

export interface RuleNodeView {
  ruleId: RuleId;
  officialCode: string;
  kind: RuleKind;
  kindLabel: string;
  sourceText: string;
  components: ReadonlyArray<RuleComponentView>;
}

export interface EpisodeDetailView {
  episode: EpisodeSummaryView;
  subject: SubjectSummaryView;
  project: ProjectSummaryView;
  rules: ReadonlyArray<RuleNodeView>;
  conflicts: ReadonlyArray<ConflictGroupView>;
  facts: ReadonlyArray<FactView>;
  expectations: ReadonlyArray<EvidenceExpectationView>;
  sourceDocuments: ReadonlyArray<{
    documentVersionId: SourceDocumentVersionId;
    fileName: string;
    documentType: string;
    sourceParty: string;
  }>;
  reviewRunId: ReviewRunId | null;
}

export interface ProtocolDiffView {
  currentProtocolVersionId: string;
  proposedProtocolVersionId: string;
  addedRuleCodes: ReadonlyArray<string>;
  deletedRuleCodes: ReadonlyArray<string>;
  changedRuleCodes: ReadonlyArray<string>;
  sourceRefs: ReadonlyArray<string>;
  currentRuleSetId: RuleSetId;
  proposedRuleSetRevision: number;
}

export interface ReviewRunDiffItemView {
  componentId: RuleComponentId;
  displayCode: string;
  priorDecision: ComponentDecision | null;
  currentDecision: ComponentDecision | null;
  priorLabel: string;
  currentLabel: string;
}

export interface ReviewDiffView {
  priorRunId: ReviewRunId;
  currentRunId: ReviewRunId;
  ruleSetRevision: number | null;
  diffs: ReadonlyArray<ReviewRunDiffItemView>;
}

export interface TodayChangeView {
  kind: "protocol_change" | "data_change";
  title: string;
  detail: string;
  sourceRefs: ReadonlyArray<string>;
}

export interface TodayWorkView {
  /** 当前节点到期行动（待处理；阻断/关注分开显示） */
  dueActions: ReadonlyArray<ActionView>;
  /** 明确障碍对象 */
  barriers: ReadonlyArray<EpisodeSummaryView>;
  /** 存在冲突对象 */
  conflicts: ReadonlyArray<EpisodeSummaryView>;
  /** 正在处理/可恢复/失败可重试的任务 */
  activeJobs: ReadonlyArray<JobView>;
  /** 近期变化（方案版本差异、资料变化标记） */
  recentChanges: ReadonlyArray<TodayChangeView>;
}

export interface WorkspaceView {
  workspaceId: string;
  schemaVersion: string;
  board: BoardView;
  today: TodayWorkView;
  protocolDiff: ProtocolDiffView;
  jobs: ReadonlyArray<JobView>;
  reviewDiffs: ReadonlyArray<ReviewDiffView>;
}

/** UAT 场景引用的 fixture 实体，供场景页/验收测试校验存在性。 */
export interface ScenarioFixtureRefs {
  episodeIds: ReadonlyArray<ReviewEpisodeId>;
  actionIds: ReadonlyArray<ActionId>;
  spanIds: ReadonlyArray<EvidenceSpanId>;
  documentIds: ReadonlyArray<SourceDocumentVersionId>;
  usesProtocolDiff: boolean;
}

export interface KeyEvidenceTarget {
  spanId: EvidenceSpanId;
  pageNumber: number;
  precision: LocatorPrecision;
  /** 从场景起始页到实际定位精度可见的最大操作数（合同 ≤ 3） */
  maxClicksFromEntry: number;
}

export interface UiScenario {
  id: string;
  uatId: string;
  title: string;
  /** 用户任务（UAT 脚本原文语义，中文） */
  task: string;
  /** 场景入口表面 */
  entrySurface: string;
  fixtureRefs: ScenarioFixtureRefs;
  keyEvidence: KeyEvidenceTarget | null;
  /** 成功证据要点 */
  acceptance: ReadonlyArray<string>;
  /** 模拟行为必须明确为原型场景 */
  prototypeOnly: boolean;
}
