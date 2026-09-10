/**
 * Wire → ViewModel 映射：唯一转换层，纯函数、确定性、可单测。
 * 组件不解析 fixture 原始结构；映射不推导任何审核结论，
 * 只搬运 fixture 已确定的 rollup/assessment 结果并附中文显示词。
 */

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
  formatSnapshotVersion,
} from "./labels";
import { isTodayWorkDueAction } from "./counts";
import {
  toId,
  type ActionId,
  type AssessmentId,
  type ConflictGroupId,
  type EvidenceSnapshotId,
  type EvidenceSpanId,
  type ExpectationId,
  type FactId,
  type JobId,
  type ProfileEventId,
  type ProjectId,
  type RequirementId,
  type ReviewEpisodeId,
  type ReviewRunId,
  type RuleComponentId,
  type RuleId,
  type RuleSetId,
  type SourceDocumentVersionId,
  type SubjectId,
  type WorkflowStageId,
} from "./ids";
import type { GapType, ProfileLane, ReviewStage, TaskState } from "./enums";
import type {
  ActionView,
  BoardView,
  ComponentDecisionView,
  ConflictGroupView,
  DateValueView,
  EpisodeDetailView,
  EpisodeSummaryView,
  EvidenceExpectationView,
  EvidenceLocatorView,
  ExpressionNodeView,
  FactView,
  GapCountItemView,
  JobEventView,
  JobView,
  PatientProfileView,
  ProfileEventView,
  ProfileLaneView,
  ProjectSummaryView,
  ProtocolDiffView,
  ReviewDiffView,
  RuleComponentView,
  RuleNodeView,
  StageInfoView,
  SubjectSummaryView,
  TodayChangeView,
  TodayWorkView,
  WorkspaceView,
} from "./viewModels";
import type {
  ActionWire,
  ConflictGroupWire,
  DateValueWire,
  EpisodeFixtureWire,
  EvidenceSpanWire,
  ExpressionWire,
  FactWire,
  FinalAssessmentWire,
  GapCountsWire,
  JobEventWire,
  PatientProfileWire,
  ProjectWire,
  ProtocolDiffWire,
  ReviewRunDiffWire,
  RuleComponentWire,
  RuleWire,
  SourceDocumentWire,
  SubjectWire,
  WorkflowStageWire,
  WorkspaceFixtureWire,
  TimeConstraintWire,
} from "../api/wire";

export function mapDateValue(
  value: DateValueWire | null | undefined,
): DateValueView | null {
  if (value === null || value === undefined) return null;
  return {
    value: value.value,
    precision: value.precision,
    precisionLabel: datePrecisionLabel[value.precision],
    sourceText: value.source_text,
  };
}

export function mapProjectSummary(
  project: ProjectWire,
  primarySubjectCount: number,
  episodeCount: number,
): ProjectSummaryView {
  return {
    projectId: toId<ProjectId>(project.project_id),
    projectCode: project.project_code,
    projectName: project.project_name,
    studyPhase: project.study_phase,
    protocolVersion: project.protocol_version.official_version,
    protocolOfficialDate:
      project.protocol_version.official_date?.value ?? "",
    ruleSetId: toId<RuleSetId>(project.rule_set_id),
    primarySubjectCount,
    episodeCount,
  };
}

export function mapSubjectSummary(subject: SubjectWire): SubjectSummaryView {
  return {
    subjectId: toId<SubjectId>(subject.subject_id),
    subjectCode: subject.subject_code,
    centerCode: subject.center_code,
    centerName: subject.center_name,
    ageYears: subject.age_years,
    sex: subject.sex,
  };
}

export function mapStageInfo(stage: WorkflowStageWire): StageInfoView {
  return {
    stage: stage.stage,
    stageLabel: stage.display_name,
    visitWindow: stage.visit_window,
    reviewRequired: stage.review_required,
    workflowStageId: toId<WorkflowStageId>(stage.workflow_stage_id),
  };
}

export function mapGapCounts(
  gapCounts: GapCountsWire,
): ReadonlyArray<GapCountItemView> {
  return (Object.keys(gapTypeLabel) as GapType[])
    .map((gapType) => ({
      gapType,
      label: gapTypeLabel[gapType],
      count: gapCounts[gapType] ?? 0,
    }))
    .filter((item) => item.count > 0)
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh"));
}

export function mapEpisodeSummary(
  episode: EpisodeFixtureWire,
): EpisodeSummaryView {
  const rollup = episode.episode_rollup;
  const stage = episode.review_episode.stage;
  const unresolvedConflictComponent = episode.conflict_groups
    .find((group) => !group.resolved)
    ?.affected_rule_component_ids[0];
  const blockingComponent = episode.final_assessments.find(
    (assessment) => assessment.blocking_level === "blocking",
  )?.rule_component_id;
  const attentionComponent = episode.final_assessments.find(
    (assessment) =>
      assessment.gap_types.length > 0 ||
      assessment.decision === "professional_judgment" ||
      assessment.decision === "not_due",
  )?.rule_component_id;
  const focusComponentId =
    unresolvedConflictComponent ?? blockingComponent ?? attentionComponent ?? null;
  return {
    episodeId: toId<ReviewEpisodeId>(episode.review_episode.review_episode_id),
    subjectId: toId<SubjectId>(episode.subject.subject_id),
    subjectCode: episode.subject.subject_code,
    stage,
    stageLabel: stageLabel[stage],
    mainStatus: rollup.main_status,
    mainStatusLabel: mainStatusLabel[rollup.main_status],
    sortRank: rollup.sort_rank,
    counts: {
      barrier: rollup.barrier_count,
      conflict: rollup.conflict_count,
      currentGap: rollup.current_gap_count,
      professionalJudgment: rollup.professional_judgment_count,
      provenanceFollowup: rollup.provenance_followup_count,
      futureAttention: rollup.future_attention_count,
      gapCounts: mapGapCounts(rollup.gap_counts),
    },
    evidenceSnapshotId: toId<EvidenceSnapshotId>(
      episode.review_episode.evidence_snapshot_id,
    ),
    revision: episode.review_episode.revision,
    focusComponentId:
      focusComponentId === null
        ? null
        : toId<RuleComponentId>(focusComponentId),
  };
}

const anchorLabel: Record<TimeConstraintWire["anchor_type"], string> = {
  icf_date: "签署知情同意",
  screening_date: "筛选",
  baseline_date: "基线",
  randomization_date: "随机",
  first_dose_date: "首次给药",
  study_drug_administration_date: "研究药物给药",
  last_dose_date: "末次给药",
  study_completion_date: "研究完成",
  event_date: "事件发生",
};

function formatDayRange(
  direction: Exclude<TimeConstraintWire["direction"], "on">,
  lower: number | null,
  upper: number | null,
  lowerInclusive: boolean,
  upperInclusive: boolean,
): string | null {
  const side = direction === "before" ? "前" : "后";
  if (lower === null && upper === null) return null;
  if (lower !== null && upper !== null) {
    if (lower === upper && lowerInclusive && upperInclusive) {
      return `${side}第 ${lower} 天`;
    }
    return `${side}${lowerInclusive ? "至少" : "超过"} ${lower} 天且${upperInclusive ? "不超过" : "少于"} ${upper} 天`;
  }
  if (upper !== null) {
    return upperInclusive ? `${side} ${upper} 天内` : `${side}少于 ${upper} 天`;
  }
  return `${side}${lowerInclusive ? "至少" : "超过"} ${lower} 天`;
}

export function formatTimeConstraint(
  constraint: TimeConstraintWire,
): string {
  const anchor = anchorLabel[constraint.anchor_type];
  if (constraint.direction === "on") return `${anchor}当天`;

  const parts: string[] = [];
  const dayRange = formatDayRange(
    constraint.direction,
    constraint.lower_bound_days,
    constraint.upper_bound_days,
    constraint.lower_bound_inclusive !== false,
    constraint.upper_bound_inclusive !== false,
  );
  if (dayRange !== null) parts.push(`${anchor}${dayRange}`);
  if (constraint.half_life_multiplier !== null) {
    const side = constraint.direction === "before" ? "前" : "后";
    parts.push(
      `${anchor}${side}至少 ${constraint.half_life_multiplier} 个半衰期`,
    );
  }
  if (parts.length === 0) {
    const side = constraint.direction === "before" ? "前" : "后";
    parts.push(`${anchor}${side}`);
  }
  if (constraint.allow_partial_date) parts.push("可按不完整日期估算");
  return parts.join("；");
}

function formatSourceValidityWindow(
  quantity: RuleComponentWire["evidence_requirements"][number]["source_validity_window"],
): string | null {
  if (quantity == null) return null;
  const unitLabels = {
    day: "天",
    week: "周",
    month: "个月",
    year: "年",
  } as const;
  return `可采用${quantity.value}${unitLabels[quantity.unit]}内的检查结果`;
}

function displayFixtureFileName(fileName: string): string {
  return fileName.replace(
    /^合成筛选资料-(?:clear|barrier|gap_conflict)(\.[^.]+)$/,
    "合成筛选资料$1",
  );
}

export function mapBoard(workspace: WorkspaceFixtureWire): BoardView {
  const primarySubjectIds = workspace.primary_subject_ids.map((id) =>
    toId<SubjectId>(id),
  );
  const templateEpisodeIds = workspace.stage_template_episode_ids.map((id) =>
    toId<ReviewEpisodeId>(id),
  );
  const subjects = workspace.episodes
    .map((episode) => mapSubjectSummary(episode.subject))
    .filter(
      (subject, index, all) =>
        all.findIndex((other) => other.subjectId === subject.subjectId) ===
        index,
    );
  const episodes = workspace.episodes.map(mapEpisodeSummary);
  const stages = workspace.episodes[0].workflow_stages.map(mapStageInfo);
  const project = mapProjectSummary(
    workspace.episodes[0].project,
    primarySubjectIds.length,
    episodes.length,
  );
  return {
    project,
    subjects,
    episodes,
    stages,
    primarySubjectIds,
    templateEpisodeIds,
  };
}

export function mapEvidenceLocator(
  span: EvidenceSpanWire,
  documents: ReadonlyArray<SourceDocumentWire>,
): EvidenceLocatorView {
  const document = documents.find(
    (candidate) =>
      candidate.source_document_version_id === span.source_document_version_id,
  );
  return {
    spanId: toId<EvidenceSpanId>(span.evidence_span_id),
    documentVersionId: toId<SourceDocumentVersionId>(
      span.source_document_version_id,
    ),
    fileName: displayFixtureFileName(document?.file_name ?? ""),
    documentType: document?.document_type ?? "",
    pageNumber: span.page_number,
    precision: span.precision,
    precisionLabel: precisionLabel[span.precision],
    degradationReason: span.degradation_reason,
    excerpt: span.excerpt,
    textRange:
      span.text_start !== null && span.text_end !== null
        ? { start: span.text_start, end: span.text_end }
        : null,
    bbox: span.bbox,
  };
}

/**
 * 应备证据要求索引：requirement_id → 所属子项显示编号 + 具体要求 + 到期节点。
 * 期望条目（evidence_expectations）是节点级；具体要求定义在规则子项的
 * evidence_requirements 中，映射时投影关联信息（I4 修复）。
 */
function requirementIndex(
  episode: EpisodeFixtureWire,
): Map<RequirementId, {
  displayCode: string;
  description: string;
  dueStage: ReviewStage;
}> {
  const index = new Map<
    RequirementId,
    { displayCode: string; description: string; dueStage: ReviewStage }
  >();
  for (const rule of episode.rule_set.rules) {
    for (const component of rule.components) {
      const displayCode = displayRuleCode(component.display_code);
      for (const requirement of component.evidence_requirements) {
        index.set(toId<RequirementId>(requirement.requirement_id), {
          displayCode,
          description: requirement.description,
          dueStage: requirement.due_stage,
        });
      }
    }
  }
  return index;
}

export function mapExpectation(
  expectation: EpisodeFixtureWire["evidence_expectations"][number],
  episode: EpisodeFixtureWire,
): EvidenceExpectationView {
  const requirement = requirementIndex(episode).get(
    toId<RequirementId>(expectation.requirement_id),
  );
  return {
    expectationId: toId<ExpectationId>(expectation.expectation_id),
    requirementId: toId<RequirementId>(expectation.requirement_id),
    gapType: expectation.gap_type,
    gapLabel: gapTypeLabel[expectation.gap_type],
    status: expectation.status,
    statusLabel: expectation.gap_type === "observation_unverified"
      ? "资料尚待核实"
      : expectationStatusLabel[expectation.status],
    evidenceSpanIds: expectation.evidence_span_ids.map((id) =>
      toId<EvidenceSpanId>(id),
    ),
    displayCode: requirement?.displayCode ?? "节点级要求",
    requirementDescription: requirement?.description ?? "",
    dueStage: requirement?.dueStage ?? null,
    dueStageLabel:
      requirement === undefined ? "未指定" : stageLabel[requirement.dueStage],
  };
}

export function mapProfileEvent(
  event: PatientProfileWire["events"][number],
  episode: EpisodeFixtureWire,
): ProfileEventView {
  const evidenceRelation: ProfileEventView["evidenceRelation"] =
    event.event_type === "review_summary"
      ? "review_basis"
      : event.fact_ids.length > 0
        ? "direct"
        : event.related_rule_component_ids.length > 0
          ? "related_rule"
          : "unavailable";
  const firstSpanId = event.evidence_span_ids[0];
  const evidenceOwner = episode.final_assessments.find(
    (assessment) =>
      firstSpanId !== undefined &&
      assessment.evidence_span_ids.includes(firstSpanId) &&
      event.related_rule_component_ids.includes(assessment.rule_component_id),
  );
  const evidenceTargetComponentId =
    evidenceOwner?.rule_component_id ?? event.related_rule_component_ids[0] ?? null;
  return {
    eventId: toId<ProfileEventId>(event.event_id),
    lane: event.lane,
    laneLabel: laneLabel[event.lane],
    eventType: event.event_type,
    title: event.title,
    riskLabels: [...event.risk_labels],
    isAbnormal: event.is_abnormal,
    isCritical: event.is_critical,
    hasTrendChange: event.has_trend_change,
    startDate: mapDateValue(event.start_date),
    endDate: mapDateValue(event.end_date),
    relatedRuleComponentIds: event.related_rule_component_ids.map((id) =>
      toId<RuleComponentId>(id),
    ),
    factIds: event.fact_ids.map((id) => toId(id)),
    evidence: event.evidence_span_ids
      .map((id) =>
        episode.evidence_spans.find((span) => span.evidence_span_id === id),
      )
      .filter((span): span is EvidenceSpanWire => span !== undefined)
      .map((span) => mapEvidenceLocator(span, episode.source_documents)),
    evidenceRelation,
    evidenceTargetComponentId:
      evidenceTargetComponentId === null
        ? null
        : toId<RuleComponentId>(evidenceTargetComponentId),
  };
}

const PROFILE_LANE_ORDER: readonly ProfileLane[] = [
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
];

export function mapPatientProfile(
  profile: PatientProfileWire,
  episode: EpisodeFixtureWire,
): PatientProfileView {
  const grouped = new Map<ProfileLane, ProfileEventView[]>();
  for (const event of profile.events) {
    const view = mapProfileEvent(event, episode);
    const list = grouped.get(event.lane) ?? [];
    list.push(view);
    grouped.set(event.lane, list);
  }
  const lanes: ProfileLaneView[] = [...grouped.entries()]
    .sort(
      (a, b) =>
        PROFILE_LANE_ORDER.indexOf(a[0]) - PROFILE_LANE_ORDER.indexOf(b[0]),
    )
    .map(([lane, events]) => ({
      lane,
      laneLabel: laneLabel[lane],
      events,
    }));
  return {
    patientProfileId: profile.patient_profile_id,
    subjectId: toId<SubjectId>(profile.subject_id),
    reviewEpisodeId: toId<ReviewEpisodeId>(profile.review_episode_id),
    stale: profile.stale,
    highlightedEventIds: profile.highlighted_event_ids.map((id) =>
      toId<ProfileEventId>(id),
    ),
    missingExpectationIds: profile.missing_expectation_ids.map((id) =>
      toId<ExpectationId>(id),
    ),
    lanes,
    expectations: episode.evidence_expectations.map((expectation) =>
      mapExpectation(expectation, episode),
    ),
  };
}

export function mapFact(fact: FactWire): FactView {
  return {
    factId: toId(fact.fact_id),
    factType: fact.fact_type,
    polarity: fact.polarity,
    polarityLabel: polarityLabel[fact.polarity],
    certainty: fact.certainty,
    value: fact.value,
    evidenceSpanIds: fact.evidence_span_ids.map((id) =>
      toId<EvidenceSpanId>(id),
    ),
  };
}

export function mapConflictGroup(
  group: ConflictGroupWire,
  episode: EpisodeFixtureWire,
): ConflictGroupView {
  const componentCodes = componentDisplayCodeIndex(episode);
  return {
    conflictGroupId: toId<ConflictGroupId>(group.conflict_group_id),
    factIds: group.fact_ids.map((id) => toId<FactId>(id)),
    affectedRuleComponentIds: group.affected_rule_component_ids.map((id) =>
      toId<RuleComponentId>(id),
    ),
    affectedDisplayCodes: group.affected_rule_component_ids.map(
      (id) => componentCodes.get(toId<RuleComponentId>(id)) ?? "未关联子项",
    ),
    resolved: group.resolved,
    snapshotVersion: formatSnapshotVersion(
      episode.review_episode.revision,
      episode.evidence_snapshot.created_at,
    ),
    facts: episode.facts
      .filter((fact) => group.fact_ids.includes(fact.fact_id))
      .map((fact) => ({
        factId: toId<FactId>(fact.fact_id),
        factType: fact.fact_type,
        polarity: fact.polarity,
        polarityLabel: polarityLabel[fact.polarity],
        certainty: fact.certainty,
        value: fact.value,
        evidence: fact.evidence_span_ids
          .map((spanId) =>
            episode.evidence_spans.find(
              (span) => span.evidence_span_id === spanId,
            ),
          )
          .filter((span): span is EvidenceSpanWire => span !== undefined)
          .map((span) => mapEvidenceLocator(span, episode.source_documents)),
      })),
  };
}

const componentDisplayCodeIndex = (
  episode: EpisodeFixtureWire,
): Map<RuleComponentId, string> =>
  new Map(
    episode.rule_set.rules.flatMap((rule) =>
      rule.components.map((component) => [
        toId<RuleComponentId>(component.rule_component_id),
        displayRuleCode(component.display_code),
      ]),
    ),
  );

function displayRuleCode(code: string): string {
  return code.replace(/^REQ-/, "必做-");
}

const assessmentIndex = (
  episode: EpisodeFixtureWire,
): Map<RuleComponentId, FinalAssessmentWire> =>
  new Map(
    episode.final_assessments.map((assessment) => [
      toId<RuleComponentId>(assessment.rule_component_id),
      assessment,
    ]),
  );

export function mapAction(
  action: ActionWire,
  episode: EpisodeFixtureWire,
): ActionView {
  const displayCode =
    componentDisplayCodeIndex(episode).get(
      toId<RuleComponentId>(action.rule_component_id),
    ) ?? action.rule_component_id;
  return {
    actionId: toId<ActionId>(action.action_id),
    episodeId: toId<ReviewEpisodeId>(episode.review_episode.review_episode_id),
    subjectCode: episode.subject.subject_code,
    assessmentId: action.assessment_id
      ? toId<AssessmentId>(action.assessment_id)
      : null,
    ruleComponentId: toId<RuleComponentId>(action.rule_component_id),
    displayCode,
    gapType: action.gap_type,
    gapLabel: gapTypeLabel[action.gap_type],
    blockingLevel: action.blocking_level,
    blockingLabel: blockingLevelLabel[action.blocking_level],
    blockingBadge: blockingLevelBadge[action.blocking_level],
    targetParty: action.target_party,
    targetPartyLabel: actionTargetLabel[action.target_party],
    requestedAction: action.requested_action,
    acceptableEvidence: action.acceptable_evidence,
    dueStage: action.due_stage,
    dueStageLabel: stageLabel[action.due_stage],
    state: action.state,
    stateLabel: actionStateLabel[action.state],
    reviewRunId: toId<ReviewRunId>(action.review_run_id),
    revision: action.revision,
  };
}

export function mapExpression(expression: ExpressionWire): ExpressionNodeView {
  if (expression.kind === "predicate" && expression.predicate !== undefined) {
    const predicate = expression.predicate;
    return {
      kind: "predicate",
      predicateId: predicate.predicate_id,
      subject: predicate.subject,
      attribute: predicate.attribute,
      comparator: predicate.comparator,
      comparatorLabel: comparatorLabel[predicate.comparator],
      value: predicate.value,
      unit: predicate.unit,
      requiresProfessionalJudgment: predicate.requires_professional_judgment,
      timeConstraint:
        expression.time_constraint === null ||
        expression.time_constraint === undefined
          ? null
          : formatTimeConstraint(expression.time_constraint),
    };
  }
  const operator = expression.operator ?? "all";
  return {
    kind: "logic",
    operator,
    operatorLabel: logicalOperatorLabel[operator],
    children: (expression.children ?? []).map(mapExpression),
  };
}

function componentEvidenceSpanIds(
  componentId: RuleComponentId,
  episode: EpisodeFixtureWire,
): EvidenceSpanId[] {
  const ids = new Set<EvidenceSpanId>();
  for (const assessment of episode.final_assessments) {
    if (assessment.rule_component_id !== componentId) continue;
    for (const spanId of assessment.evidence_span_ids ?? []) {
      ids.add(toId<EvidenceSpanId>(spanId));
    }
  }
  for (const group of episode.conflict_groups) {
    if (!group.affected_rule_component_ids.includes(componentId)) continue;
    for (const factId of group.fact_ids) {
      const fact = episode.facts.find(
        (candidate) => candidate.fact_id === factId,
      );
      for (const spanId of fact?.evidence_span_ids ?? []) {
        ids.add(toId<EvidenceSpanId>(spanId));
      }
    }
  }
  return [...ids];
}

export function mapComponentDecision(
  assessment: FinalAssessmentWire | undefined,
): ComponentDecisionView | null {
  if (assessment === undefined) return null;
  return {
    componentId: toId<RuleComponentId>(assessment.rule_component_id),
    displayCode: "",
    decision: assessment.decision,
    decisionLabel: decisionLabel[assessment.decision],
    blockingLevel: assessment.blocking_level,
    gapTypes: [...assessment.gap_types],
    gapLabels: assessment.gap_types.map((gap) => gapTypeLabel[gap]),
  };
}

export function mapRuleComponent(
  component: RuleComponentWire,
  episode: EpisodeFixtureWire,
  decision: ComponentDecisionView | null,
): RuleComponentView {
  const decisionView =
    decision === null
      ? null
      : { ...decision, displayCode: displayRuleCode(component.display_code) };
  const spanIds = componentEvidenceSpanIds(
    toId<RuleComponentId>(component.rule_component_id),
    episode,
  );
  return {
    componentId: toId<RuleComponentId>(component.rule_component_id),
    parentRuleId: toId<RuleId>(component.parent_rule_id),
    displayCode: displayRuleCode(component.display_code),
    title: component.title,
    expression: mapExpression(component.expression),
    exceptionExpression:
      component.exception_expression === null
        ? null
        : mapExpression(component.exception_expression),
    evidenceRequirements: component.evidence_requirements.map(
      (requirement) => ({
        requirementId: toId<RequirementId>(requirement.requirement_id),
        factType: requirement.fact_type,
        dueStage: requirement.due_stage,
        dueStageLabel: stageLabel[requirement.due_stage],
        sourceValidityLabel: formatSourceValidityWindow(
          requirement.source_validity_window,
        ),
        description: requirement.description,
      }),
    ),
    decision: decisionView,
    actions: episode.actions
      .filter(
        (action) => action.rule_component_id === component.rule_component_id,
      )
      .map((action) => mapAction(action, episode)),
    evidence: spanIds
      .map((spanId) =>
        episode.evidence_spans.find(
          (span) => span.evidence_span_id === spanId,
        ),
      )
      .filter((span): span is EvidenceSpanWire => span !== undefined)
      .map((span) => mapEvidenceLocator(span, episode.source_documents)),
  };
}

export function mapRuleTree(episode: EpisodeFixtureWire): RuleNodeView[] {
  const assessments = assessmentIndex(episode);
  return episode.rule_set.rules.map((rule: RuleWire) => ({
    ruleId: toId<RuleId>(rule.rule_id),
    officialCode: displayRuleCode(rule.official_code),
    kind: rule.kind,
    kindLabel: ruleKindLabel[rule.kind],
    sourceText: rule.source_text,
    components: rule.components.map((component) =>
      mapRuleComponent(
        component,
        episode,
        mapComponentDecision(
          assessments.get(toId<RuleComponentId>(component.rule_component_id)),
        ),
      ),
    ),
  }));
}

export function deriveTaskState(events: ReadonlyArray<JobEventWire>): TaskState {
  const types = new Set(events.map((event) => event.event_type));
  if (types.has("cancelled") || types.has("cancel_requested")) {
    return "cancelled";
  }
  if (types.has("completed")) return "completed";
  const hasFailed = events.some((event) => event.event_type === "step_failed");
  if (hasFailed) {
    if (events.some((event) => event.checkpoint_id !== null)) return "resumable";
    if (events.some((event) => event.retryable)) return "failed";
    return "partial";
  }
  if (types.has("retry_scheduled")) return "resumable";
  if (types.has("step_started") || types.has("step_completed")) return "running";
  return "queued";
}

export function mapJobEvent(event: JobEventWire): JobEventView {
  return {
    jobEventId: event.job_event_id,
    eventType: event.event_type,
    eventTypeLabel: jobEventTypeLabel[event.event_type],
    occurredAt: event.occurred_at,
    attempt: event.attempt,
    stepId: event.step_id,
    progressCompleted: event.progress_completed,
    progressTotal: event.progress_total,
    retryable: event.retryable,
  };
}

export function mapJob(episode: EpisodeFixtureWire): JobView | null {
  if (episode.job_events.length === 0) return null;
  const events = episode.job_events;
  const last = events[events.length - 1];
  const state = deriveTaskState(events);
  return {
    jobId: toId<JobId>(last.job_id),
    reviewEpisodeId: toId<ReviewEpisodeId>(
      episode.review_episode.review_episode_id,
    ),
    subjectCode: episode.subject.subject_code,
    stage: episode.review_episode.stage,
    stageLabel: stageLabel[episode.review_episode.stage],
    state,
    stateLabel: taskStateLabel[state],
    progressCompleted: last.progress_completed,
    progressTotal: last.progress_total,
    retryable: last.retryable,
    checkpointId: last.checkpoint_id,
    lastEventAt: last.occurred_at,
    events: events.map(mapJobEvent),
  };
}

export function mapProtocolDiff(diff: ProtocolDiffWire): ProtocolDiffView {
  return {
    currentProtocolVersionId: diff.current_protocol_version_id,
    proposedProtocolVersionId: diff.proposed_protocol_version_id,
    addedRuleCodes: diff.added_rule_codes.map(displayRuleCode),
    deletedRuleCodes: diff.deleted_rule_codes.map(displayRuleCode),
    changedRuleCodes: diff.changed_logic_or_window_codes.map(displayRuleCode),
    sourceRefs: [...diff.source_refs],
    sourceRefsByRuleCode: Object.fromEntries(
      Object.entries(diff.source_refs_by_rule_code).map(([code, refs]) => [
        displayRuleCode(code),
        [...refs],
      ]),
    ),
    currentRuleSetId: toId<RuleSetId>(diff.current_rule_set.rule_set_id),
    proposedRuleSetRevision: diff.proposed_rule_set_draft.revision,
  };
}

export function mapReviewDiff(diff: ReviewRunDiffWire): ReviewDiffView {
  return {
    priorRunId: toId<ReviewRunId>(diff.prior_review_run_id),
    currentRunId: toId<ReviewRunId>(diff.current_review_run_id),
    ruleSetRevision: null,
    diffs: (diff.component_diffs ?? []).map((item) => ({
      componentId: toId<RuleComponentId>(item.rule_component_id),
      displayCode: "",
      priorDecision: item.prior_decision,
      currentDecision: item.current_decision,
      priorLabel: item.prior_decision ? decisionLabel[item.prior_decision] : "",
      currentLabel: item.current_decision
        ? decisionLabel[item.current_decision]
        : "",
    })),
  };
}

export function mapTodayWork(workspace: WorkspaceFixtureWire): TodayWorkView {
  const episodes = workspace.episodes;
  const dueActions: ActionView[] = episodes
    .flatMap((episode) =>
      episode.actions
        .map((action) => mapAction(action, episode))
        .filter((action) =>
          isTodayWorkDueAction(action, episode.review_episode.stage),
        ),
    )
    .sort(
      (a, b) =>
        (a.blockingLevel === "blocking" ? 0 : 1) -
          (b.blockingLevel === "blocking" ? 0 : 1) ||
        a.subjectCode.localeCompare(b.subjectCode, "zh") ||
        a.actionId.localeCompare(b.actionId, "zh"),
    );
  const summaries = episodes.map(mapEpisodeSummary);
  const barriers = summaries
    .filter((summary) => summary.mainStatus === "clear_barrier")
    .sort((a, b) => a.subjectCode.localeCompare(b.subjectCode, "zh"));
  const conflicts = summaries
    .filter((summary) => summary.counts.conflict > 0)
    .sort((a, b) => a.subjectCode.localeCompare(b.subjectCode, "zh"));
  const activeJobs = episodes
    .map(mapJob)
    .filter(
      (job): job is JobView =>
        job !== null &&
        (job.state === "queued" ||
          job.state === "running" ||
          job.state === "failed" ||
          job.state === "resumable" ||
          job.state === "partial"),
    );
  const recentChanges: TodayChangeView[] = [];
  const diff = workspace.protocol_diff;
  for (const code of diff.added_rule_codes) {
    recentChanges.push({
      kind: "protocol_change",
      title: `方案新增条件 ${displayRuleCode(code)}`,
      detail: "新版本草稿中新增的条件，尚未发布。",
      sourceRefs: [...diff.source_refs],
    });
  }
  for (const code of diff.deleted_rule_codes) {
    recentChanges.push({
      kind: "protocol_change",
      title: `方案删除条件 ${displayRuleCode(code)}`,
      detail: "新版本草稿中删除的条件，尚未发布。",
      sourceRefs: [...diff.source_refs],
    });
  }
  for (const code of diff.changed_logic_or_window_codes) {
    recentChanges.push({
      kind: "protocol_change",
      title: `方案条件 ${displayRuleCode(code)} 逻辑或时间窗变化`,
      detail: "新版本草稿中的变化，尚未发布。",
      sourceRefs: [...diff.source_refs],
    });
  }
  for (const episode of episodes) {
    if (episode.patient_profile.stale) {
      recentChanges.push({
        kind: "data_change",
        title: `受试者 ${episode.subject.subject_code} 资料发生变化`,
        detail: "当前审核结果需要重新核对。",
        sourceRefs: [],
      });
    }
  }
  return { dueActions, barriers, conflicts, activeJobs, recentChanges };
}

export function mapEpisodeDetail(
  episode: EpisodeFixtureWire,
): EpisodeDetailView {
  return {
    episode: mapEpisodeSummary(episode),
    subject: mapSubjectSummary(episode.subject),
    project: mapProjectSummary(episode.project, 1, 1),
    rules: mapRuleTree(episode),
    conflicts: episode.conflict_groups.map((group) =>
      mapConflictGroup(group, episode),
    ),
    facts: episode.facts.map(mapFact),
    expectations: episode.evidence_expectations.map((expectation) =>
      mapExpectation(expectation, episode),
    ),
    sourceDocuments: episode.source_documents.map((doc) => ({
      documentVersionId: toId<SourceDocumentVersionId>(
        doc.source_document_version_id,
      ),
      fileName: displayFixtureFileName(doc.file_name),
      documentType: doc.document_type,
      sourceParty: doc.source_party,
      snapshotVersion: formatSnapshotVersion(
        episode.review_episode.revision,
        episode.evidence_snapshot.created_at,
      ),
    })),
    reviewRunId:
      episode.review_runs.length > 0
        ? toId<ReviewRunId>(episode.review_runs[0].review_run_id)
        : null,
  };
}

export function mapWorkspace(workspace: WorkspaceFixtureWire): WorkspaceView {
  return {
    workspaceId: workspace.workspace_id,
    schemaVersion: workspace.schema_version,
    board: mapBoard(workspace),
    today: mapTodayWork(workspace),
    protocolDiff: mapProtocolDiff(workspace.protocol_diff),
    jobs: workspace.episodes
      .map(mapJob)
      .filter((job): job is JobView => job !== null),
    reviewDiffs: workspace.episodes.flatMap((episode) =>
      episode.review_run_diffs.map(mapReviewDiff),
    ),
  };
}
