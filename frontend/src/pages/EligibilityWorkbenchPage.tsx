import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Check, FileSearch, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import type { WorkDraftJobView } from "../api/eligibility-review/eligibilityReviewRepository";
import { EvidenceReader } from "../components/evidence/EvidenceReader";
import { SourceExcerpt } from "../components/evidence/SourceExcerpt";
import {
  getCatalogRepository,
  getEvidenceRepository,
  type CatalogEpisodeView,
  type CatalogProjectView,
  type CatalogSubjectView,
} from "../api";
import {
  getEligibilityReviewRepository,
  type EligibilityClauseView,
  type EligibilityControlView,
  type EligibilityDecision,
  type EligibilityReviewView,
} from "../api/eligibility-review";
import { updateParams, useHashRoute, RouteLink } from "../app/router";
import { useLoad } from "../app/useLoad";
import { useApplicationMode } from "../app/applicationMode";
import { OriginalEvidenceViewer } from "../components/evidence-workspace/OriginalEvidenceViewer";
import { WorkDraftPanel } from "../components/review/WorkDraftPanel";
import { ReasonText } from "../components/review/ReasonText";
import { ErrorState, EmptyState, LoadingState } from "../components/shell/Feedback";
import { BarrierIcon, AttentionIcon, CheckIcon, ConflictIcon, JudgmentIcon } from "../components/shell/icons";
import { StatusBadge, type Tone } from "../components/shell/StatusBadge";
import { actionTargetLabel, formatSnapshotVersion, gapTypeLabel } from "../domain/labels";

export type EligibilityDecisionFilter =
  | "all"
  | "undetermined"
  | "triggered"
  | "met"
  | "not_due"
  | "not_applicable";

type EligibilityListMode = "pending" | "all";

const CLAUSE_PAGE_SIZES = [25, 50, 100] as const;

type EligibilityWorkItem = EligibilityClauseView & { controlId?: string; controlStatement?: string; continuingNote?: string | null };

function ConfirmationDialog({ clause, verificationOnly, busy, onConfirm, onClose }: {
  clause: EligibilityWorkItem; verificationOnly: boolean; busy: boolean;
  onConfirm: (actor: "medical_manager" | "builder_verification") => void; onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.showModal();
    return () => previous?.focus();
  }, []);
  return <dialog ref={dialog} className="work-draft-confirmation-dialog" aria-labelledby="work-draft-confirmation-title"
    onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <h2 id="work-draft-confirmation-title">核实 {clause.ruleCode} 的当前依据</h2>
    <p><strong>{clause.decisionLabel}</strong> · {clause.textSummary}</p>
    <p>确认已对照原件？只更新置信标记，原值、结论及旧版保持。</p>
    <div className="work-draft-confirmation-actions">
      <button type="button" className="button button--quiet" disabled={busy} onClick={onClose}>取消</button>
      <button type="button" className="button button--primary" disabled={busy}
        onClick={() => onConfirm(verificationOnly ? "builder_verification" : "medical_manager")}>
        {busy ? "正在提交" : verificationOnly ? "保存试用核实" : "保存核实结果"}</button>
    </div>
    {!verificationOnly && <details><summary>构建验证</summary>
      <button type="button" className="button button--quiet" disabled={busy} onClick={() => onConfirm("builder_verification")}>仅作试用核实</button>
      <small>保留试用标记，不代替正式医学核实。</small>
    </details>}
  </dialog>;
}

function controlWorkItems(controls: ReadonlyArray<EligibilityControlView>): EligibilityWorkItem[] {
  return controls.flatMap((control) => control.obligations.map((obligation) => ({
    controlId: control.protocolControlId,
    ruleComponentId: `control:${control.protocolControlId}:${obligation.obligationId}`,
    ruleCode: control.displayLabel,
    ruleKind: "required_procedure" as const,
    textSummary: control.title,
    sourceText: obligation.sourceExcerpts.join("\n") || null,
    controlStatement: obligation.statement,
    parentRuleCode: null,
    decision: ({
      fulfilled: "requirement_met",
      unfulfilled: "requirement_not_met",
      unverified: "indeterminate",
      restricted: "indeterminate",
      not_applicable: "not_applicable",
    } as const)[obligation.status],
    decisionLabel: obligation.statusLabel,
    reason: obligation.reason,
    continuingNote: obligation.continuingNote,
    factRefs: obligation.factRefs,
    sourceReadRefs: obligation.sourceReadRefs,
    gapType: null,
    determinationMode: obligation.status === "restricted" ? "restricted" as const : "semantic" as const,
    limitationKind: obligation.limitationKind ?? null,
    actionOwner: obligation.actionOwner ?? null,
    actionDetail: obligation.actionDetail ?? null,
    actionEvidence: obligation.actionEvidence ?? null,
  })));
}

const DECISION_FILTERS: ReadonlyArray<{
  id: EligibilityDecisionFilter;
  label: string;
}> = [
  { id: "all", label: "全部" },
  { id: "undetermined", label: "无法判定" },
  { id: "triggered", label: "已触发（排除）或未满足（入选）" },
  { id: "met", label: "未触发（排除）或已满足（入选）" },
  { id: "not_due", label: "尚未到期" },
  { id: "not_applicable", label: "不适用" },
];

function clauseKindLabel(kind: EligibilityClauseView["ruleKind"]): string {
  switch (kind) {
    case "inclusion":
      return "入选标准";
    case "exclusion":
      return "排除标准";
    case "required_procedure":
      return "流程要求";
    case "medication":
      return "合并用药与治疗要求";
  }
}

function workItemKindLabel(item: EligibilityWorkItem): string {
  return item.controlId ? "方案补充要求" : clauseKindLabel(item.ruleKind);
}

function hasJudgedSource(clause: EligibilityClauseView): boolean {
  return (Boolean(clause.confidence) || clause.decision === "not_applicable")
    && (clause.sourceReadRefs ?? []).some((ref) => ref.disposition === "mentioned" && ref.excerpt);
}

export function isUndeterminedDecision(decision: EligibilityDecision): boolean {
  return decision === "professional_judgment" || decision === "indeterminate" || decision === "conflict" || decision === "system_issue";
}

function decisionMatchesFilter(
  decision: EligibilityDecision,
  filter: EligibilityDecisionFilter,
): boolean {
  switch (filter) {
    case "all":
      return true;
    case "undetermined":
      return isUndeterminedDecision(decision);
    case "triggered":
      return (
        decision === "exclusion_triggered" ||
        decision === "inclusion_not_met" ||
        decision === "requirement_not_met"
      );
    case "met":
      return (
        decision === "exclusion_not_triggered" ||
        decision === "inclusion_met" ||
        decision === "requirement_met"
      );
    case "not_due":
      return decision === "not_due";
    case "not_applicable":
      return decision === "not_applicable";
  }
}

function decisionTone(decision: EligibilityDecision): Tone {
  switch (decision) {
    case "inclusion_met":
    case "requirement_met":
    case "exclusion_not_triggered":
      return "ok";
    case "inclusion_not_met":
    case "requirement_not_met":
    case "exclusion_triggered":
    case "conflict":
      return "danger";
    case "professional_judgment":
    case "indeterminate":
    case "system_issue":
      return "info";
    case "not_due":
    case "not_applicable":
      return "neutral";
  }
}

function decisionIcon(decision: EligibilityDecision): ReactNode {
  switch (decision) {
    case "inclusion_met":
    case "requirement_met":
    case "exclusion_not_triggered":
      return <CheckIcon size={13} />;
    case "inclusion_not_met":
    case "requirement_not_met":
    case "exclusion_triggered":
      return <BarrierIcon size={13} />;
    case "professional_judgment":
    case "indeterminate":
    case "system_issue":
      return <JudgmentIcon size={13} />;
    case "conflict":
      return <ConflictIcon size={13} />;
    case "not_due":
    case "not_applicable":
      return <AttentionIcon size={13} />;
  }
}

function centerLabel(subject: CatalogSubjectView): string {
  if (subject.centerCode !== null && subject.centerName !== null) {
    return `${subject.centerCode}｜${subject.centerName}`;
  }
  return subject.centerCode ?? subject.centerName ?? "中心信息尚未填写";
}

function episodeLabel(episode: CatalogEpisodeView): string {
  return episode.workflowStageLabel ?? episode.stageLabel;
}

function projectOption(project: CatalogProjectView): string {
  return `${project.projectCode} · ${project.studyPhaseLabel} · 方案 ${project.officialVersion}`;
}

interface EligibilitySelectionProps {
  projects: ReadonlyArray<CatalogProjectView>;
  selectedProject: CatalogProjectView;
  subjects: ReadonlyArray<CatalogSubjectView>;
  selectedSubject: CatalogSubjectView;
  episodes: ReadonlyArray<CatalogEpisodeView>;
  selectedEpisode: CatalogEpisodeView;
  onProjectChange: (projectId: string) => void;
  onSubjectChange: (subjectId: string) => void;
  onEpisodeChange: (episodeId: string) => void;
}

function EligibilitySelection({
  projects,
  selectedProject,
  subjects,
  selectedSubject,
  episodes,
  selectedEpisode,
  onProjectChange,
  onSubjectChange,
  onEpisodeChange,
}: EligibilitySelectionProps) {
  return (
    <section className="eligibility-selection" aria-label="选择审核对象">
      <label>
        <span>项目</span>
        <select
          aria-label="选择项目"
          value={selectedProject.projectId}
          onChange={(event) => onProjectChange(event.target.value)}
        >
          {projects.map((project) => (
            <option key={project.projectId} value={project.projectId}>
              {projectOption(project)}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>受试者</span>
        <select
          aria-label="选择受试者"
          value={selectedSubject.subjectId}
          onChange={(event) => onSubjectChange(event.target.value)}
        >
          {subjects.map((subject) => (
            <option key={subject.subjectId} value={subject.subjectId}>
              {subject.subjectCode} · {centerLabel(subject)}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span>审核节点</span>
        <select
          aria-label="选择审核节点"
          value={selectedEpisode.reviewEpisodeId}
          onChange={(event) => onEpisodeChange(event.target.value)}
        >
          {episodes.map((episode) => (
            <option key={episode.reviewEpisodeId} value={episode.reviewEpisodeId}>
              {episodeLabel(episode)}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}

interface EligibilityClauseListProps {
  clauses: ReadonlyArray<EligibilityWorkItem>;
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
}

function EligibilityClauseList({
  clauses,
  selectedComponentId,
  onSelect,
}: EligibilityClauseListProps) {
  const groups: ReadonlyArray<{
    kind: string;
    title: string;
  }> = [
    { kind: "inclusion", title: "入选标准" },
    { kind: "exclusion", title: "排除标准" },
    { kind: "required_procedure", title: "流程要求" },
    { kind: "medication", title: "合并用药与治疗要求" },
    { kind: "control", title: "方案补充要求" },
  ];
  return (
    <div className="eligibility-clause-list">
      {groups.map((group) => {
        const groupClauses = clauses.filter((clause) =>
          (clause.controlId ? "control" : clause.ruleKind) === group.kind);
        if (groupClauses.length === 0) return null;
        return (
          <section key={group.kind} className="eligibility-clause-group" aria-labelledby={`eligibility-group-${group.kind}`}>
            <h3 id={`eligibility-group-${group.kind}`}>{group.title}</h3>
            <ul>
              {groupClauses.map((clause) => {
                const selected = clause.ruleComponentId === selectedComponentId;
                // The parent is an official rule, never another component.
                const depth = clause.parentRuleCode === null ? 0 : 1;
                return (
                  <li key={clause.ruleComponentId}>
                    <button
                      type="button"
                      className={`eligibility-clause${selected ? " eligibility-clause--selected" : ""}`}
                      style={{ paddingInlineStart: `calc(var(--space-2) + ${depth} * var(--space-3))` }}
                      aria-pressed={selected}
                      onClick={() => onSelect(clause.ruleComponentId)}
                    >
                      <span className="eligibility-clause__identity">
                        <strong>{clause.ruleCode}</strong>
                        <span
                          className="eligibility-clause__summary"
                          title={clause.textSummary}
                        >
                          {clause.textSummary}
                        </span>
                      </span>
                      <StatusBadge
                        tone={decisionTone(clause.decision)}
                        text={clause.decisionLabel}
                        hint={clause.reason}
                        icon={decisionIcon(clause.decision)}
                      />
                      {clause.confidence === "low" && <span title={clause.confidenceReason ?? undefined}>低置信</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        );
      })}
      {clauses.length === 0 && (
        <p className="eligibility-clause-list__empty">没有符合当前筛选条件的条款。</p>
      )}
    </div>
  );
}

type IssueSeverity = "danger" | "attention" | "info";

interface EligibilityIssueGroup {
  key: string;
  label: string;
  severity: IssueSeverity;
  clauses: EligibilityClauseView[];
}

const ISSUE_SEVERITY_ORDER: Record<IssueSeverity, number> = {
  danger: 0,
  attention: 1,
  info: 2,
};

const FALLBACK_ISSUE_LABELS: Record<string, string> = {
  clause_not_satisfied: "条款未满足或已触发",
  protocol_meaning_unresolved: "方案要求尚待核清",
  review_method_unavailable: "审核方法待完善",
  protocol_requirement_unresolved: "本项暂不能判定",
  evidence_incomplete: "证据需补充或核对",
  unclassified: "原因待明确",
};

/** 队列成员：风险（已触发/未满足）、冲突、未决；已满足/未触发/未到期不算问题。 */
function clauseIsIssue(clause: EligibilityClauseView): boolean {
  const tone = decisionTone(clause.decision);
  return tone === "danger" || tone === "info" || clause.confidence === "low";
}

/** 根因键：优先投影缺口类型；未归类时按判定回退，绝不静默丢失。 */
function clauseIssueKey(clause: EligibilityClauseView): {
  key: string;
  severity: IssueSeverity;
} {
  if (clause.confidence === "low" && decisionTone(clause.decision) === "ok") {
    return { key: "low_confidence", severity: "attention" };
  }
  if (clause.determinationMode === "restricted") {
    return {
      key: clause.limitationKind === "consumer_unavailable" ? "review_method_unavailable"
        : clause.limitationKind === "interpretation_unresolved" ? "protocol_meaning_unresolved"
        : "protocol_requirement_unresolved",
      severity: "attention",
    };
  }
  switch (clause.decision) {
    case "conflict":
      return { key: clause.gapType ?? "source_conflict", severity: "danger" };
    case "exclusion_triggered":
    case "inclusion_not_met":
    case "requirement_not_met":
      return { key: clause.gapType ?? "clause_not_satisfied", severity: "danger" };
    case "professional_judgment":
      return { key: clause.gapType ?? "professional_judgment", severity: "attention" };
    case "indeterminate":
      return { key: clause.gapType ?? "evidence_incomplete", severity: "info" };
    default:
      return { key: clause.gapType ?? "unclassified", severity: "info" };
  }
}

function issueGroupLabel(key: string): string {
  if (key === "low_confidence") return "已判定 · 低置信";
  const labels = gapTypeLabel as Record<string, string>;
  return labels[key] ?? FALLBACK_ISSUE_LABELS[key] ?? key;
}

/** 根因聚合：同一根因的条款归入一组并计数；渲染全量，不用 top-N 截断。
 *  组严重性取成员最高档且与输入顺序无关（F08纠偏）。 */
export function buildEligibilityIssueGroups(
  clauses: ReadonlyArray<EligibilityClauseView>,
): EligibilityIssueGroup[] {
  const severities: IssueSeverity[] = ["danger", "attention", "info"];
  const byKey = new Map<string, EligibilityIssueGroup>();
  for (const clause of clauses) {
    if (!clauseIsIssue(clause)) continue;
    const { key, severity } = clauseIssueKey(clause);
    let group = byKey.get(key);
    if (!group) {
      group = { key, label: issueGroupLabel(key), severity, clauses: [] };
      byKey.set(key, group);
    } else if (
      severities.indexOf(severity) < severities.indexOf(group.severity)
    ) {
      group.severity = severity;
    }
    group.clauses.push(clause);
  }
  for (const group of byKey.values()) {
    group.clauses.sort(compareEligibilityClauses);
  }
  return [...byKey.values()].sort(
    (a, b) =>
      Number(a.key === "low_confidence") - Number(b.key === "low_confidence") ||
      ISSUE_SEVERITY_ORDER[a.severity] - ISSUE_SEVERITY_ORDER[b.severity] ||
      b.clauses.length - a.clauses.length ||
      a.key.localeCompare(b.key),
  );
}

function compareEligibilityClauses(
  left: EligibilityClauseView,
  right: EligibilityClauseView,
): number {
  const leftIssue = clauseIsIssue(left) ? clauseIssueKey(left) : null;
  const rightIssue = clauseIsIssue(right) ? clauseIssueKey(right) : null;
  const leftSeverity = leftIssue ? ISSUE_SEVERITY_ORDER[leftIssue.severity] : 3;
  const rightSeverity = rightIssue ? ISSUE_SEVERITY_ORDER[rightIssue.severity] : 3;
  return Number(leftIssue?.key === "low_confidence") - Number(rightIssue?.key === "low_confidence")
    || leftSeverity - rightSeverity
    || left.ruleCode.localeCompare(right.ruleCode, "zh-CN", { numeric: true })
    || left.ruleComponentId.localeCompare(right.ruleComponentId);
}

const ISSUE_SEVERITY_META: Record<IssueSeverity, { tone: Tone; text: string }> = {
  danger: { tone: "danger", text: "风险" },
  attention: { tone: "neutral", text: "需判断" },
  info: { tone: "info", text: "未决" },
};

interface EligibilityIssueQueueProps {
  clauses: ReadonlyArray<EligibilityClauseView>;
  selectedComponentId: string | null;
  onSelect: (componentId: string) => void;
}

function EligibilityIssueQueue({
  clauses,
  selectedComponentId,
  onSelect,
}: EligibilityIssueQueueProps) {
  const groups = useMemo(() => buildEligibilityIssueGroups(clauses), [clauses]);
  if (groups.length === 0) {
    return (
      <section className="eligibility-issue-queue" aria-label="问题队列">
        <p className="eligibility-muted">当前没有风险、冲突或未决条款。</p>
      </section>
    );
  }
  const totalIssues = groups.reduce((sum, group) => sum + group.clauses.length, 0);
  const lowConfidence = groups.find(group => group.key === "low_confidence")?.clauses.length ?? 0;
  return (
    <section className="eligibility-issue-queue" aria-label="问题队列">
      <p className="eligibility-issue-queue__summary">
        {totalIssues - lowConfidence} 条存在风险或未决。
        {lowConfidence > 0 && `另有 ${lowConfidence} 条已判定，保留低置信标记。`}
      </p>
      {groups.map((group) => {
        const meta = ISSUE_SEVERITY_META[group.severity];
        return (
          <details
            key={group.key}
            className="eligibility-issue-queue__group"
            open={group.key !== "low_confidence"}
          >
            <summary>
              <StatusBadge tone={meta.tone} text={group.key === "low_confidence" ? "低置信" : meta.text} />
              <strong>{group.label}</strong>
              <span className="eligibility-issue-queue__count">
                影响 {group.clauses.length} 条
              </span>
            </summary>
            <ul>
              {group.clauses.map((clause) => {
                const selected = clause.ruleComponentId === selectedComponentId;
                return (
                  <li key={clause.ruleComponentId}>
                    <button
                      type="button"
                      className={`eligibility-clause${selected ? " eligibility-clause--selected" : ""}`}
                      aria-pressed={selected}
                      onClick={() => onSelect(clause.ruleComponentId)}
                    >
                      <span className="eligibility-clause__identity">
                        <strong>{clause.ruleCode}</strong>{" "}
                        <span
                          className="eligibility-clause__summary"
                          title={clause.textSummary}
                        >
                          {clause.textSummary}
                        </span>
                      </span>
                      <StatusBadge
                        tone={decisionTone(clause.decision)}
                        text={clause.decisionLabel}
                        hint={clause.reason}
                        icon={decisionIcon(clause.decision)}
                      />
                      {clause.confidence === "low" && <span title={clause.confidenceReason ?? undefined}>低置信</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </details>
        );
      })}
    </section>
  );
}

interface EligibilityClauseDetailProps {
  clause: EligibilityWorkItem;
  conditions?: ReadonlyArray<EligibilityClauseView>;
  unresolvedConditions?: ReadonlyArray<EligibilityClauseView>;
  selectedFactIndex: number;
  onSelectFact: (index: number) => void;
}

function EligibilityClauseDetail({
  clause,
  conditions = [],
  unresolvedConditions = [],
  selectedFactIndex,
  onSelectFact,
}: EligibilityClauseDetailProps) {
  const parts = clause.reasonParts ?? [];
  const pendingParts = isUndeterminedDecision(clause.decision)
    ? parts.filter(part => part.requiresAttention) : [];
  const judgedConditions = clause.parentRuleCode === null && !isUndeterminedDecision(clause.decision)
    ? conditions.filter(item => !isUndeterminedDecision(item.decision)
      && item.decision !== "not_due" && item.decision !== "not_applicable").slice(0, 3) : [];
  const futureConditions = conditions.filter(item => item.decision === "not_due");
  return (
    <div className="eligibility-clause-detail">
      {clause.parentRuleCode !== null && <h3 className="eligibility-clause-detail__condition">{clause.textSummary}</h3>}
      <div className="eligibility-clause-detail__decision">
        <StatusBadge
          tone={decisionTone(clause.decision)}
          text={clause.decisionLabel}
          hint={clause.reason}
          icon={decisionIcon(clause.decision)}
        />
        {clause.confidence && <span className="eligibility-confidence" title={clause.confidenceReason ?? undefined}>
          {clause.confidence === "low" ? "低置信" : "高置信"}</span>}
        {clause.confirmationKind && <span title={clause.confirmationKind === "medical_manager" ? "医学经理已核实本条依据" : "构建者试用验证，非正式医学核实"}>
          {clause.confirmationKind === "medical_manager" ? "已核实" : "试用已核实"}</span>}
      </div>
      <ul className="eligibility-clause-detail__bullets" aria-label="条款详情">
        <li className="eligibility-detail-bullet">
          <strong>{pendingParts.length ? "尚需核对的条件" : unresolvedConditions.length ? "尚缺的依据" : "判定依据"}</strong>
          {pendingParts.length > 0 ? <dl className="eligibility-reason-parts">{pendingParts.map(part => <div key={part.conditionId}>
            <dt><strong>{part.conditionText}</strong></dt><dd><ReasonText text={part.reasonText} compact /></dd>
          </div>)}</dl> : judgedConditions.length > 0 ? <>
            <dl className="eligibility-reason-parts">{judgedConditions.map(item => <div key={item.ruleComponentId}>
              <dt><strong>{item.textSummary}</strong> · {item.decisionLabel}</dt>
              <dd><ReasonText text={item.reason} compact /></dd>
            </div>)}</dl>
            {futureConditions.length > 0 && <p className="eligibility-muted">另有 {futureConditions.length} 项后续要求未到期。</p>}
          </> : <ReasonText compact text={unresolvedConditions.length
            ? unresolvedConditions.map(item => item.reason).join("\n") : clause.reason} />}
          {pendingParts.length > 0 && parts.some(part => !part.requiresAttention) && <details>
            <summary>其他条件及依据（{parts.filter(part => !part.requiresAttention).length}）</summary>
            <dl className="eligibility-reason-parts">{parts.filter(part => !part.requiresAttention).map(part => <div key={part.conditionId}>
              <dt><strong>{part.conditionText}</strong></dt><dd><ReasonText text={part.reasonText} /></dd>
            </div>)}</dl>
          </details>}
          {(pendingParts.length > 0 || unresolvedConditions.length > 0 || judgedConditions.length > 0) && <details>
            <summary>完整汇总说明</summary>
            <ReasonText text={clause.reason} />
          </details>}
        </li>
        {clause.continuingNote && <li className="eligibility-detail-bullet">
          <strong>后续持续要求</strong>
          <span>{clause.continuingNote}</span>
        </li>}
        {clause.actionDetail !== null && (
          <li className="eligibility-detail-bullet">
            <strong>{clause.actionOwner === null ? "处理方向" : `建议动作 · ${actionTargetLabel[clause.actionOwner]}`}</strong>
            <span>{clause.actionDetail}</span>
            {clause.actionEvidence !== null && (
              <span className="eligibility-muted">可接受证据：{clause.actionEvidence}</span>
            )}
          </li>
        )}
        {(!clause.sourceText || clause.controlId) && (
          <li className="eligibility-detail-bullet">
          <strong>{clause.controlId ? "系统解构的审核要求" : "审核要点"}</strong>
          <span>{clause.controlStatement ?? clause.textSummary}</span>
          </li>
        )}
      </ul>
      {clause.sourceText && (
        <details className="eligibility-clause-detail__source">
          <summary>{clause.controlId ? "查看方案原文摘录" : "查看方案原文"}</summary>
          <p>{clause.sourceText}</p>
        </details>
      )}
      {!clause.sourceText && (
        <p className="eligibility-muted" role="note">
          方案原文定位待补齐，请核对方案版本及条款来源。
        </p>
      )}
      <details className="eligibility-detail-section">
        <summary>关联事实的原件位置（{clause.factRefs.length}）</summary>
        {clause.factRefs.length === 0 ? (
          <p className="eligibility-muted">{hasJudgedSource(clause)
            ? "本次判断依据病历原文，可打开原件查看。"
            : clause.determinationMode === "restricted"
            ? "方案要求尚待核清，暂不据此判定病历事实。"
            : "当前条款没有关联事实。"}</p>
        ) : (
          <ul className="eligibility-fact-list">
            {clause.factRefs.map((fact, index) => (
              <li key={`${fact.factId}-${fact.locatorId ?? "no-locator"}-${index}`}>
                <button
                  type="button"
                  className={`eligibility-fact-list__item${selectedFactIndex === index ? " is-active" : ""}`}
                  aria-pressed={selectedFactIndex === index}
                  onClick={() => onSelectFact(index)}
                >
                  <strong>{fact.excerpt?.trim() || `原文依据 ${index + 1}`}</strong>
                  <span>
                    {fact.pageNumber === null
                      ? "该事实未附页码定位"
                      : `第 ${fact.pageNumber} 页`}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </details>
      {!clause.controlId && <details className="eligibility-clause-detail__mode"><summary>核对方式</summary>
        <p>{determinationModeLabel(clause)}</p>
      </details>}
    </div>
  );
}

function determinationModeLabel(clause: EligibilityClauseView): string {
  switch (clause.determinationMode) {
    case "deterministic":
      return "系统按结构化资料完成判断";
    case "semantic":
      return "系统按资料内容完成判断";
    case "investigator_judgment":
      return "需要研究者结合资料确认";
    case "restricted":
      return clause.limitationKind === "consumer_unavailable" ? "审核方法待完善"
        : clause.limitationKind === "interpretation_unresolved" ? "方案要求尚待核清"
        : "本项暂不能判定";
  }
}

interface EligibilityEvidencePanelProps {
  review: EligibilityReviewView;
  clause: EligibilityWorkItem;
  selectedFactIndex: number;
  onSelectFact: (index: number) => void;
}

function EligibilityEvidencePanel({
  review,
  clause,
  selectedFactIndex,
  onSelectFact,
}: EligibilityEvidencePanelProps) {
  const [browsedPage, setBrowsedPage] = useState<{ context: string; entryId: string; sourceKey?: string } | null>(null);
  const [navigationAttempt, setNavigationAttempt] = useState(0);
  const returnToReference = () => {
    setBrowsedPage(null);
    setNavigationAttempt((attempt) => attempt + 1);
  };
  const processing = useLoad(
    (signal) =>
      getEvidenceRepository().getProcessingRevision(
        review.completeProcessingRevisionId,
        { signal },
      ),
    [review.completeProcessingRevisionId],
  );
  const snapshot = useLoad(
    (signal) =>
      getEvidenceRepository().getEvidenceSnapshot(review.evidenceSnapshotV2Id, {
        signal,
      }),
    [review.evidenceSnapshotV2Id],
  );
  const pages = processing.state.status === "success" ? processing.state.data.pages : [];
  const documentNames = useMemo(() => {
    if (snapshot.state.status !== "success") return new Map<string, string>();
    return new Map(
      snapshot.state.data.members.map((member) => [
        member.sourceDocumentVersionId,
        member.fileName,
      ]),
    );
  }, [snapshot.state]);
  const selectedFact = clause.factRefs[selectedFactIndex] ?? clause.factRefs[0] ?? null;
  // Display duplicates only; all source records remain in the saved review.
  const sourceRefs = useMemo(() => [...new Map((clause.sourceReadRefs ?? []).map(ref =>
    [JSON.stringify(ref), ref])).values()], [clause.sourceReadRefs]);
  const quotedRefs = sourceRefs.filter(ref => ref.excerpt);
  const scopeRefs = sourceRefs.filter(ref => !ref.excerpt);
  const sourcePageCount = new Set(sourceRefs.map(ref => JSON.stringify([
    ref.sourceDocumentVersionId, ref.pageArtifactId, ref.pageNumber]))).size;
  const selectedSource = quotedRefs[0] ?? null;
  const referencePage = selectedFact === null
    ? selectedSource === null ? null : pages.find((page) => page.pageNumber === selectedSource.pageNumber
        && page.sourceDocumentVersionId === selectedSource.sourceDocumentVersionId
        && page.pageArtifactId === selectedSource.pageArtifactId) ?? null
    : selectedFact.pageNumber === null
      ? null
      : pages.find((page) => page.pageNumber === selectedFact.pageNumber
          && page.sourceDocumentVersionId === selectedFact.sourceDocumentVersionId
          && page.pageArtifactId === selectedFact.pageArtifactId) ?? null;
  const sourceContext = JSON.stringify([
    review.completeProcessingRevisionId, clause.ruleComponentId,
    selectedFact?.factId, selectedFact?.locatorId, selectedFact?.sourceDocumentVersionId,
    selectedFact?.pageArtifactId, selectedFact?.pageNumber,
    selectedSource?.pageArtifactId, selectedSource?.excerpt,
  ]);
  const selectedPage = browsedPage?.context === sourceContext
    ? pages.find((page) => page.entryId === browsedPage.entryId) ?? referencePage
    : referencePage ?? pages[0] ?? null;
  const browsedSource = browsedPage?.context === sourceContext && browsedPage.sourceKey
    ? sourceRefs.find(ref => JSON.stringify(ref) === browsedPage.sourceKey) ?? null : null;
  const isReferencePage = browsedSource === null && referencePage !== null && selectedPage?.entryId === referencePage.entryId;
  const locatorPage = useLoad(
    (signal) => selectedPage?.ocrPageId
      ? getEvidenceRepository().getOcrPage(selectedPage.ocrPageId, review.completeProcessingRevisionId, { signal })
      : Promise.resolve(null),
    [selectedPage?.ocrPageId, review.completeProcessingRevisionId],
  );
  const selectedLocators = isReferencePage && locatorPage.state.status === "success"
    && locatorPage.state.data?.processingRevisionId === review.completeProcessingRevisionId
    ? (locatorPage.state.data?.locators ?? []).filter((locator) =>
        locator.locatorId === selectedFact?.locatorId
        && locator.sourceDocumentVersionId === selectedFact?.sourceDocumentVersionId
        && locator.pageArtifactId === selectedFact?.pageArtifactId
        && locator.pageNumber === selectedFact?.pageNumber)
    : [];
  const hasVerifiedBox = selectedLocators.some((locator) =>
    locator.precision === "bbox" && locator.authenticity === "authenticated"
    && locator.bbox !== null && locator.coordinateFrame !== null);

  const closeSourceChoices = (button: HTMLButtonElement) => {
    const choices = button.closest(".eligibility-evidence__sources");
    choices?.removeAttribute("open");
    choices?.querySelector("summary")?.focus({ preventScroll: true });
  };
  const sourceButtons = (refs: typeof sourceRefs) => refs.map(ref => {
    const key = JSON.stringify(ref);
    const page = pages.find(item => item.sourceDocumentVersionId === ref.sourceDocumentVersionId
      && item.pageArtifactId === ref.pageArtifactId && item.pageNumber === ref.pageNumber);
    return <li key={key}>
      <button type="button" className="eligibility-evidence__ref" disabled={!page}
        aria-pressed={browsedSource !== null && JSON.stringify(browsedSource) === key}
        onClick={event => {
          if (!page) return;
          setBrowsedPage({ context: sourceContext, entryId: page.entryId, sourceKey: key });
          closeSourceChoices(event.currentTarget);
        }}>
        <strong>{ref.disposition === "mentioned" ? hasJudgedSource(clause) ? "本次判断的病历依据" : "已找到相关原文，待核清" : ref.disposition === "not_seen" ? "本页未见相关记录" : "本页尚未核清"}</strong>
        {ref.excerpt && <span>{ref.excerpt}</span>}
        <span>{documentNames.get(ref.sourceDocumentVersionId) ?? "原始资料"} · 第 {ref.pageNumber} 页</span>
      </button>
    </li>;
  });

  return (
    <aside className="eligibility-evidence" aria-label="原件面板">
      {selectedPage !== null && (
        <div className="eligibility-evidence__state" role="status">
          <strong>{browsedSource ? browsedSource.disposition === "unresolved" || !hasJudgedSource(clause)
            ? "待核原文页" : "病历依据页" : isReferencePage ? selectedFact === null ? "病历依据页" : "事实来源页" : "浏览原件"}</strong>
          <span>
            {documentNames.get(selectedPage.sourceDocumentVersionId) ?? "原始资料"}
            {` · 第 ${selectedPage.pageNumber} 页`}
          </span>
        </div>
      )}
      {clause.factRefs.length === 0 && !hasJudgedSource(clause) && (
        <p className="eligibility-muted">当前条款没有已采用事实，可浏览全部原件页核实。</p>
      )}
      {browsedSource?.excerpt && <blockquote className="eligibility-evidence__excerpt"><SourceExcerpt text={browsedSource.excerpt} context={clause.textSummary} /></blockquote>}
      {isReferencePage && selectedFact === null && selectedSource?.excerpt
        && <blockquote className="eligibility-evidence__excerpt"><SourceExcerpt text={selectedSource.excerpt} context={clause.textSummary} /></blockquote>}
      {sourceRefs.length > 0 && (
        <details className="eligibility-evidence__sources" key={`sources:${clause.ruleComponentId}`} open={clause.decision === "conflict"}>
          <summary>{quotedRefs.length
            ? `病历依据与核对范围（${sourceRefs.length}）`
            : scopeRefs.some(ref => ref.disposition === "unresolved")
              ? `已检索 ${sourcePageCount} 页，部分尚未核清 · 查看范围`
              : `已核对 ${sourcePageCount} 页，未见相关记录 · 查看范围`}</summary>
        <ul className="eligibility-evidence__refs" aria-label="检索范围与待核原文">
          {sourceButtons(quotedRefs.length ? quotedRefs : scopeRefs)}
        </ul>
        {quotedRefs.length > 0 && scopeRefs.length > 0 && <details>
          <summary>查看其余检索范围</summary>
          <ul className="eligibility-evidence__refs">{sourceButtons(scopeRefs)}</ul>
        </details>}
        </details>
      )}
      {(
        <>
          {isReferencePage && selectedFact?.excerpt && <blockquote className="eligibility-evidence__excerpt"><SourceExcerpt text={selectedFact.excerpt} context={clause.textSummary} /></blockquote>}
          {clause.factRefs.length > 1 && <details className="eligibility-evidence__sources" key={`facts:${clause.ruleComponentId}`}>
          <summary>选择其他依据（{clause.factRefs.length - 1}）</summary>
          <ul className="eligibility-evidence__refs" aria-label="关联事实的原件位置">
            {clause.factRefs.map((fact, index) => index === selectedFactIndex ? null : (
              <li key={`${fact.factId}-${fact.locatorId ?? "no-locator"}-${index}`}>
                {fact.pageNumber === null ? (
                  <span className="eligibility-evidence__ref eligibility-evidence__ref--unavailable">
                    <strong>{fact.excerpt?.trim() || `原文依据 ${index + 1}`}</strong>
                    <span>该事实未附页码定位</span>
                  </span>
                ) : (
                  <button
                    type="button"
                    className={`eligibility-evidence__ref${selectedFactIndex === index ? " is-active" : ""}`}
                    aria-pressed={selectedFactIndex === index}
                    onClick={event => {
                      closeSourceChoices(event.currentTarget);
                      returnToReference();
                      onSelectFact(index);
                    }}
                  >
                    <strong>{fact.excerpt?.trim() || `原文依据 ${index + 1}`}</strong>
                    <span>{documentNames.get(fact.sourceDocumentVersionId ?? "") ?? "原始资料"} · 第 {fact.pageNumber} 页</span>
                  </button>
                )}
              </li>
            ))}
          </ul>
          </details>}
          {selectedFact?.pageNumber === null && (
            <p className="eligibility-evidence__empty" role="status">
              该事实未附页码定位，暂时无法打开对应原件页。
            </p>
          )}
          {selectedFact !== null && selectedFact.pageNumber !== null && referencePage === null && processing.state.status === "success" && (
            <p className="eligibility-evidence__empty" role="status">
              当前处理资料中没有找到第 {selectedFact.pageNumber} 页。
            </p>
          )}
          {processing.state.status === "loading" || snapshot.state.status === "loading" ? (
            <LoadingState />
          ) : processing.state.status === "error" ? (
            <ErrorState message={processing.state.message} onRetry={processing.retry} />
          ) : snapshot.state.status === "error" ? (
            <ErrorState message={snapshot.state.message} onRetry={snapshot.retry} />
          ) : pages.length === 0 ? (
            <EmptyState message="当前没有可查看的原件页。" hint="请先完成资料处理并确认可查看的原件。" />
          ) : selectedPage === null ? null : (
            <>
            {!isReferencePage && referencePage !== null ? (
              <button type="button" className="button button--quiet" onClick={returnToReference}>
                返回本条依据页
              </button>
            ) : null}
            {isReferencePage && locatorPage.state.status === "error" ? (
              <ErrorState message="原文标注暂时无法读取，可先查看原件。" onRetry={locatorPage.retry} />
            ) : isReferencePage && locatorPage.state.status === "success" && !hasVerifiedBox ? (
              <p className="eligibility-muted"><span title="已定位到原件页面，具体文字位置尚未核实，暂不显示红框。">页级定位</span></p>
            ) : null}
            <OriginalEvidenceViewer
              revisionId={review.completeProcessingRevisionId}
              pages={pages}
              documentNames={documentNames}
              selectedEntryId={selectedPage?.entryId ?? null}
              selectedLocatorId={isReferencePage ? selectedFact?.locatorId ?? null : null}
              selectedPageLocators={selectedLocators}
              navigationKey={JSON.stringify([sourceContext, navigationAttempt])}
              onSelectPage={(entryId) => setBrowsedPage({ context: sourceContext, entryId })}
              unavailableRecoveryHint="当前页面无法显示时，请回到受试者资料页检查资料处理状态。"
            />
            </>
          )}
        </>
      )}
    </aside>
  );
}

export function EligibilityWorkbenchPage() {
  const { params } = useHashRoute();
  const projectParam = params.get("project");
  const subjectParam = params.get("subject");
  const episodeParam = params.get("episode");
  const componentParam = params.get("component");
  const viewParam = params.get("view");
  const listMode: EligibilityListMode = viewParam === "pending" || viewParam === "all"
    ? viewParam
    : componentParam !== null ? "all" : "pending";
  const filterParam = params.get("filter");
  const filter: EligibilityDecisionFilter = DECISION_FILTERS.some((item) => item.id === filterParam)
    ? filterParam as EligibilityDecisionFilter
    : "all";
  const pageSizeParam = Number(params.get("limit"));
  const clausePageSize = CLAUSE_PAGE_SIZES.includes(pageSizeParam as typeof CLAUSE_PAGE_SIZES[number])
    ? pageSizeParam
    : 50;
  const requestedPageValue = Number(params.get("page"));
  const requestedPage = Number.isSafeInteger(requestedPageValue) && requestedPageValue >= 0
    ? requestedPageValue : 0;
  const [selectedFactIndex, setSelectedFactIndex] = useState(0);
  const detailPaneRef = useRef<HTMLDivElement>(null);
  const [queueVisible, setQueueVisible] = useState(true);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidenceVisited, setEvidenceVisited] = useState(false);
  const [confirmationJob, setConfirmationJob] = useState<{ episodeId: string; job: WorkDraftJobView } | null>(null);
  const [confirmationBusy, setConfirmationBusy] = useState(false);
  const [confirmationError, setConfirmationError] = useState<string | null>(null);
  const [confirmedRule, setConfirmedRule] = useState<{ episodeId: string; ruleCode: string; previousRun: string } | null>(null);
  const [confirmingClause, setConfirmingClause] = useState<EligibilityWorkItem | null>(null);
  const { canModify } = useApplicationMode();

  const projects = useLoad((signal) => getCatalogRepository().listProjects(signal), []);
  const projectList = projects.state.status === "success" ? projects.state.data : [];
  const selectedProject =
    projectParam !== null
      ? projectList.find((project) => project.projectId === projectParam) ?? null
      : projectList[0] ?? null;

  const subjects = useLoad(
    (signal) =>
      getCatalogRepository().listSubjects(selectedProject?.projectId ?? "", signal),
    [selectedProject?.projectId],
    { enabled: selectedProject !== null },
  );
  const subjectList =
    subjects.state.status === "success"
      ? subjects.state.data.filter((subject) => subject.projectId === selectedProject?.projectId)
      : [];
  const selectedSubject =
    subjectParam !== null
      ? subjectList.find((subject) => subject.subjectId === subjectParam) ?? null
      : subjectList[0] ?? null;

  const episodes = useLoad(
    (signal) =>
      getCatalogRepository().listEpisodes(selectedSubject?.subjectId ?? "", signal),
    [selectedSubject?.subjectId],
    { enabled: selectedSubject !== null },
  );
  const episodeList =
    episodes.state.status === "success"
      ? episodes.state.data.filter((episode) => episode.subjectId === selectedSubject?.subjectId)
      : [];
  const selectedEpisode =
    episodeParam !== null
      ? episodeList.find((episode) => episode.reviewEpisodeId === episodeParam) ?? null
      : episodeList[0] ?? null;

  const review = useLoad(
    (signal) =>
      getEligibilityReviewRepository().getEligibilityReview(
        selectedSubject?.subjectId ?? "",
        selectedEpisode?.reviewEpisodeId ?? "",
        { signal },
      ),
    [selectedSubject?.subjectId, selectedEpisode?.reviewEpisodeId],
    { enabled: selectedSubject !== null && selectedEpisode !== null },
  );

  useEffect(() => {
    setSelectedFactIndex(0);
    setEvidenceOpen(false);
    setEvidenceVisited(false);
    if (detailPaneRef.current) detailPaneRef.current.scrollTop = 0;
  }, [selectedEpisode?.reviewEpisodeId, componentParam]);

  useEffect(() => {
    setConfirmationError(null); setConfirmingClause(null);
  }, [selectedEpisode?.reviewEpisodeId]);

  useEffect(() => {
    if (review.state.status !== "success" || !confirmedRule || selectedEpisode?.reviewEpisodeId !== confirmedRule.episodeId
        || review.state.data.reviewRunId === confirmedRule.previousRun) return;
    const target = review.state.data.clauses.find(item => item.ruleCode === confirmedRule.ruleCode);
    if (target) updateParams({ component: target.ruleComponentId, view: "all", filter: null, page: null });
    setConfirmedRule(null);
  }, [review.state, confirmedRule, selectedEpisode?.reviewEpisodeId]);

  const setProject = (projectId: string) =>
    updateParams({ project: projectId, subject: null, episode: null, component: null });
  const setSubject = (subjectId: string) =>
    updateParams({ subject: subjectId, episode: null, component: null });
  const setEpisode = (episodeId: string) =>
    updateParams({ episode: episodeId, component: null });
  const refreshWorkDraft = () => {
    if (!confirmedRule) updateParams({ component: null, page: null });
    setConfirmationJob(null);
    episodes.retry();
    review.retry();
  };

  async function confirmClause(clause: EligibilityWorkItem, actor: "medical_manager" | "builder_verification") {
    const repo = getEligibilityReviewRepository();
    if (!canModify || review.state.status !== "success" || !review.state.data.reviewRunId || !selectedSubject || !selectedEpisode || !repo.confirmWorkDraft) return;
    setConfirmationBusy(true); setConfirmationError(null);
    try {
      const job = await repo.confirmWorkDraft(selectedSubject.subjectId, selectedEpisode.reviewEpisodeId, {
        review_run_id: review.state.data.reviewRunId, item_id: clause.ruleComponentId, confirmed: true,
        actor_kind: actor });
      setConfirmingClause(null);
      setConfirmedRule({ episodeId: selectedEpisode.reviewEpisodeId, ruleCode: clause.ruleCode, previousRun: review.state.data.reviewRunId });
      localStorage.setItem(`work-draft-job:${selectedEpisode.reviewEpisodeId}`, job.job_id);
      if (job.state === "completed") { episodes.retry(); review.retry(); }
      else setConfirmationJob({ episodeId: selectedEpisode.reviewEpisodeId, job });
    } catch (error) { setConfirmationError(error instanceof Error ? error.message : "本条尚未核实，请稍后重试。"); }
    finally { setConfirmationBusy(false); }
  }

  if (projects.state.status === "loading") return <LoadingState />;
  if (projects.state.status === "error") {
    return <ErrorState message={projects.state.message} onRetry={projects.retry} />;
  }
  if (projectList.length === 0) {
    return <EmptyState message="当前还没有已保存的项目。" hint="请先在方案工作台确认研究方案。" />;
  }
  if (selectedProject === null) {
    return <ErrorState message="链接中的项目不存在，请重新选择。" onRetry={() => updateParams({ project: null, subject: null, episode: null, component: null })} />;
  }
  if (subjects.state.status === "loading") return <LoadingState />;
  if (subjects.state.status === "error") {
    return <ErrorState message={subjects.state.message} onRetry={subjects.retry} />;
  }
  if (subjectList.length === 0) {
    return <EmptyState message="这个项目还没有受试者。" hint="请先在受试者资料目录中登记受试者。" />;
  }
  if (selectedSubject === null) {
    return <ErrorState message="链接中的受试者不属于当前项目，请重新选择。" onRetry={() => updateParams({ subject: null, episode: null, component: null })} />;
  }
  if (episodes.state.status === "loading") return <LoadingState />;
  if (episodes.state.status === "error") {
    return <ErrorState message={episodes.state.message} onRetry={episodes.retry} />;
  }
  if (episodeList.length === 0) {
    return <EmptyState message="该受试者还没有审核节点。" hint="请先在方案工作台确认审核节点。" />;
  }
  if (selectedEpisode === null) {
    return <ErrorState message="链接中的审核节点不存在，请重新选择。" onRetry={() => updateParams({ episode: null, component: null })} />;
  }
  if (review.state.status === "loading") return <LoadingState />;
  if (review.state.status === "error") {
    const newerRules = selectedEpisode.ruleSetId === selectedProject.ruleSetId
      && selectedEpisode.ruleSetRevision < selectedProject.ruleSetRevision;
    return <div className="eligibility-workbench workbench">
      <ErrorState message={review.state.message} onRetry={review.retry} />
      {newerRules && <section aria-label="采用已发布的新规则">
        <h2>{selectedSubject.subjectCode} · {episodeLabel(selectedEpisode)}</h2>
        <p>本节点尚未使用最新规则包，旧版工作稿保留。</p>
        <WorkDraftPanel key={selectedEpisode.reviewEpisodeId} episode={selectedEpisode} onCompleted={refreshWorkDraft} />
      </section>}
    </div>;
  }

  const reviewData = review.state.data;
  const issueGroups = [
    { label: "系统问题", issues: (reviewData.systemIssues ?? []).filter(issue => issue.kind !== "excerpt_unverified") },
    { label: "尚未用于判断的原件记录", issues: (reviewData.systemIssues ?? []).filter(issue => issue.kind === "excerpt_unverified") },
  ];
  const allClauses: EligibilityWorkItem[] = [
    ...reviewData.clauses, ...controlWorkItems(reviewData.controls),
  ];
  const requestedClause = componentParam === null
    ? null : [...allClauses, ...(reviewData.componentClauses ?? [])].find((clause) => clause.ruleComponentId === componentParam);
  if (componentParam !== null && requestedClause === undefined
      && reviewData.workDraftState !== "method_changed" && reviewData.workDraftState !== "source_changed") {
    return <ErrorState message="链接中的审核要点不存在，请重新选择。" onRetry={() => updateParams({ component: null })} />;
  }
  const matches = (clause: EligibilityWorkItem, mode: EligibilityListMode, decisionFilter: EligibilityDecisionFilter) =>
    mode === "pending" ? clauseIsIssue(clause) : decisionMatchesFilter(clause.decision, decisionFilter);
  const showAllForDeepLink = requestedClause !== null && requestedClause !== undefined
    && !matches(requestedClause, listMode, filter);
  const activeMode = showAllForDeepLink ? "all" : listMode;
  const activeFilter = showAllForDeepLink ? "all" : filter;
  const filteredClauses = [...allClauses]
    .filter((clause) => activeMode === "pending"
      ? clauseIsIssue(clause)
      : decisionMatchesFilter(clause.decision, activeFilter))
    .sort(compareEligibilityClauses);
  const pageCount = Math.max(1, Math.ceil(filteredClauses.length / clausePageSize));
  const deepLinkIndex = requestedClause === null || requestedClause === undefined
    ? -1 : filteredClauses.findIndex((item) => item.ruleComponentId === requestedClause.ruleComponentId);
  const currentPage = deepLinkIndex >= 0
    ? Math.floor(deepLinkIndex / clausePageSize)
    : Math.min(requestedPage, pageCount - 1);
  const visibleClauses = filteredClauses.slice(
    currentPage * clausePageSize, (currentPage + 1) * clausePageSize,
  );
  const selectedClause = requestedClause ?? visibleClauses[0];
  const undeterminedCount = allClauses.filter((clause) => isUndeterminedDecision(clause.decision)).length;
  const subjectLabel = `${selectedSubject.subjectCode} · ${centerLabel(selectedSubject)}`;
  const unassignedConflictCount = reviewData.unassignedConflicts?.length ?? 0;
  const selectClause = (componentId: string) => updateParams({ component: componentId });
  const setListMode = (mode: EligibilityListMode) => {
    const candidates = [...allClauses]
      .filter((clause) => matches(clause, mode, filter))
      .sort(compareEligibilityClauses);
    updateParams({ view: mode, filter: mode === "pending" ? null : filter, page: null,
      component: candidates[0]?.ruleComponentId ?? null });
  };
  const setDecisionFilter = (nextFilter: EligibilityDecisionFilter) => {
    const candidates = [...allClauses]
      .filter((clause) => decisionMatchesFilter(clause.decision, nextFilter))
      .sort(compareEligibilityClauses);
    updateParams({ view: "all", filter: nextFilter === "all" ? null : nextFilter, page: null,
      component: candidates[0]?.ruleComponentId ?? null });
  };

  const selectPage = (page: number) => updateParams({
    page: page === 0 ? null : String(page),
    component: filteredClauses[page * clausePageSize]?.ruleComponentId ?? null,
  });

  return (
    <div className={`eligibility-workbench workbench${queueVisible ? "" : " eligibility-workbench--reading"}`}>
      <header className="page-head">
        <h1 className="page-head__title">入排审核工作台</h1>
        <p className="page-head__note">
          {subjectLabel} · {selectedProject.projectCode} · {episodeLabel(selectedEpisode)} · 方案 {selectedProject.officialVersion}
        </p>
      </header>
      <EligibilitySelection
        projects={projectList}
        selectedProject={selectedProject}
        subjects={subjectList}
        selectedSubject={selectedSubject}
        episodes={episodeList}
        selectedEpisode={selectedEpisode}
        onProjectChange={setProject}
        onSubjectChange={setSubject}
        onEpisodeChange={setEpisode}
      />
      <div className="eligibility-context-bar">
        <button type="button" className="icon-button" aria-label={queueVisible ? "收起条款列表" : "显示条款列表"}
          title={queueVisible ? "收起条款列表，扩大依据与原件" : "显示条款列表"} aria-expanded={queueVisible}
          onClick={() => setQueueVisible(value => !value)}>
          {queueVisible ? <PanelLeftClose size={17} aria-hidden="true" /> : <PanelLeftOpen size={17} aria-hidden="true" />}
        </button>
        {reviewData.verificationOnly && <span>验证用规则包</span>}
        <span
          className="eligibility-undetermined"
          role="status"
          aria-label={`无法判定 ${undeterminedCount} 项`}
        >
          无法判定 {undeterminedCount} 项
        </span>
        <RouteLink
          to="/subjects"
          params={{ project: selectedProject.projectId, subject: selectedSubject.subjectId, episode: selectedEpisode.reviewEpisodeId }}
          className="button button--quiet"
          ariaLabel={`查看 ${selectedSubject.subjectCode} 的资料页`}
        >
          查看受试者资料
        </RouteLink>
        <RouteLink
          to="/reports"
          params={{ project: selectedProject.projectId, subject: selectedSubject.subjectId, episode: selectedEpisode.reviewEpisodeId }}
          className="button button--quiet"
          ariaLabel="打开报告页"
        >
          打开报告
        </RouteLink>
      </div>
      <details className="eligibility-work-draft-tools"><summary>工作稿操作与节点日期</summary>
        <WorkDraftPanel key={selectedEpisode.reviewEpisodeId} episode={selectedEpisode} onCompleted={refreshWorkDraft}
          initialJob={confirmationJob?.episodeId === selectedEpisode.reviewEpisodeId ? confirmationJob.job : null}
          onSettled={job => {
            if (job.state !== "completed" && confirmationJob?.episodeId === selectedEpisode.reviewEpisodeId) {
              setConfirmationJob(null); setConfirmedRule(null);
              setConfirmationError("新版尚未保存，旧版未改变。请在任务详情查看原因，处理后再试。");
            }
          }} />
      </details>
      {issueGroups.filter(group => group.issues.length).map(group => <details key={group.label}
        aria-label={group.label} className="eligibility-context-bar">
        <summary>{group.label}（{group.issues.length}）</summary>
        <ul>{group.issues.map((issue, index) => <li key={index}>
          {issue.affectedCodes.join("、")} {issue.detail} {issue.alternative}
          {issue.pageArtifactId && <RouteLink to={`/subjects/${encodeURIComponent(selectedSubject.subjectId)}/evidence`}
            params={{ episode: selectedEpisode.reviewEpisodeId, sourcePage: issue.pageArtifactId }}
            className="button button--quiet" ariaLabel={`查看相关原件第${issue.pageNumber ?? "对应"}页`}>
            查看相关原件{issue.pageNumber ? `第${issue.pageNumber}页` : ""}
          </RouteLink>}
        </li>)}</ul>
      </details>)}
      {(reviewData.workDraftState === "source_changed" || reviewData.workDraftState === "method_changed") && (
        <section className="eligibility-context-bar" role="status"
          aria-label={reviewData.workDraftState === "method_changed" ? "审核方式已更新" : "审核资料已变化"}>
          <p>{reviewData.workDraftState === "method_changed"
            ? "审核方式已更新，先前的工作稿仍保留，但未按当前方式核对。请重新准备审核后再查看本次结果。"
            : "资料已更正，先前的审核工作稿不再适用于本次资料。请重新核对后再查看结果。"}</p>
          <RouteLink to="/reports"
            params={{ project: selectedProject.projectId, subject: selectedSubject.subjectId, episode: selectedEpisode.reviewEpisodeId }}
            className="button button--quiet" ariaLabel="前往重新审核">
            前往重新审核
          </RouteLink>
        </section>
      )}
      {unassignedConflictCount > 0 && (
        <section className="eligibility-context-bar" aria-label="病史记录待核对">
          <p>有 {unassignedConflictCount} 项病史或用药记录不一致，尚未确定影响哪些条款。</p>
          <RouteLink to="/profiles"
            params={{ project: selectedProject.projectId, subject: selectedSubject.subjectId, episode: selectedEpisode.reviewEpisodeId }}
            className="button button--quiet" ariaLabel="查看病史中的不一致记录">
            查看病史记录
          </RouteLink>
        </section>
      )}
      <div className="workbench-panes">
        {queueVisible && <aside className="workbench-col eligibility-workbench__clauses" aria-label="审核要点列表">
          <div className="workbench-pane">
            <header className="workbench-pane__head">
              <div>
                <h2 className="workbench-pane__title">
                  {activeMode === "pending" ? "待处理要点" : "全部审核要点"}
                </h2>
                <p className="workbench-pane__subtitle">
                  {activeMode === "pending" ? "按问题类型汇总，逐项核对" : `共 ${filteredClauses.length} 项`}
                </p>
              </div>
            </header>
            <div className="eligibility-list-mode" role="group" aria-label="选择条款范围">
              <button type="button" aria-pressed={activeMode === "pending"}
                onClick={() => setListMode("pending")}>待处理</button>
              <button type="button" aria-pressed={activeMode === "all"}
                onClick={() => setListMode("all")}>全部条款</button>
            </div>
            <div className="eligibility-clause-list__toolbar">
              {activeMode === "all" && (
                <label>
                  <span>按判定筛选</span>
                  <select aria-label="按判定筛选" value={activeFilter}
                    onChange={(event) => setDecisionFilter(event.target.value as EligibilityDecisionFilter)}>
                    {DECISION_FILTERS.map((item) => (
                      <option key={item.id} value={item.id}>{item.label}</option>
                    ))}
                  </select>
                </label>
              )}
              <label>
                <span>单次显示</span>
                <select aria-label="单次显示条款数" value={clausePageSize}
                  onChange={(event) => updateParams({ limit: event.target.value === "50" ? null : event.target.value, page: null, component: null })}>
                  {CLAUSE_PAGE_SIZES.map((size) => <option key={size} value={size}>{size} 条</option>)}
                </select>
              </label>
            </div>
            {activeMode === "pending" ? (
              <EligibilityIssueQueue clauses={visibleClauses}
                selectedComponentId={selectedClause?.ruleComponentId ?? null} onSelect={selectClause} />
            ) : (
              <EligibilityClauseList clauses={visibleClauses}
                selectedComponentId={selectedClause?.ruleComponentId ?? null} onSelect={selectClause} />
            )}
            {pageCount > 1 && (
              <nav className="eligibility-clause-list__pagination" aria-label="审核要点分页">
                <button type="button" disabled={currentPage === 0} onClick={() => selectPage(currentPage - 1)}>上一页</button>
                <span>第 {currentPage + 1} / {pageCount} 页</span>
                <button type="button" disabled={currentPage >= pageCount - 1} onClick={() => selectPage(currentPage + 1)}>下一页</button>
              </nav>
            )}
          </div>
        </aside>}
        <section className="workbench-col eligibility-workbench__detail" aria-label="审核要点详情">
          <div className="workbench-pane" ref={detailPaneRef}>
            <header className="workbench-pane__head">
              <div>
                <h2 className="workbench-pane__title">
                  <span className="workbench-pane__code">{selectedClause?.ruleCode ?? "审核要点"}</span>
                  <span>{selectedClause ? workItemKindLabel(selectedClause) : ""}</span>
                </h2>
              </div>
            </header>
            {selectedClause ? <EligibilityClauseDetail
              clause={selectedClause}
              conditions={selectedClause.parentRuleCode === null
                ? reviewData.componentClauses?.filter(item => item.ruleCode === selectedClause.ruleCode
                  && item.ruleComponentId !== selectedClause.ruleComponentId) : []}
              unresolvedConditions={selectedClause.parentRuleCode === null && isUndeterminedDecision(selectedClause.decision)
                && reviewData.componentClauses?.some(item => item.ruleCode === selectedClause.ruleCode
                  && item.ruleComponentId !== selectedClause.ruleComponentId && !isUndeterminedDecision(item.decision))
                ? reviewData.componentClauses?.filter(item => item.ruleCode === selectedClause.ruleCode
                  && item.ruleComponentId !== selectedClause.ruleComponentId && isUndeterminedDecision(item.decision)) : []}
              selectedFactIndex={selectedFactIndex}
              onSelectFact={index => { setSelectedFactIndex(index); setEvidenceVisited(true); setEvidenceOpen(true); }}
            /> : <p className="eligibility-muted">当前筛选没有符合条件的审核要点。</p>}
            {canModify && selectedClause?.canConfirm && getEligibilityReviewRepository().confirmWorkDraft && <button type="button" className="button button--quiet"
              disabled={confirmationBusy || confirmationJob?.episodeId === selectedEpisode.reviewEpisodeId}
              onClick={() => setConfirmingClause(selectedClause)}><Check size={16} aria-hidden="true" />我已核实本条依据</button>}
            {confirmationJob?.episodeId === selectedEpisode.reviewEpisodeId && <p role="status">已收到核实，正在保存新版工作稿。</p>}
            {confirmationError && <p role="alert">{confirmationError}</p>}
            {confirmingClause && <ConfirmationDialog clause={confirmingClause} verificationOnly={reviewData.verificationOnly ?? false}
              busy={confirmationBusy} onClose={() => setConfirmingClause(null)}
              onConfirm={actor => void confirmClause(confirmingClause, actor)} />}
            {selectedClause && <button type="button" className="button button--primary eligibility-open-source"
              onClick={() => { setEvidenceVisited(true); setEvidenceOpen(true); }}>
              <FileSearch size={17} aria-hidden="true" /> 查看原件
            </button>}
            {selectedClause && !!reviewData.componentClauses?.some(item => item.ruleCode === selectedClause.ruleCode) &&
              <details className="eligibility-clause-detail">
                <summary>逐项条件与依据</summary>
                <ul>{reviewData.componentClauses.filter(item => item.ruleCode === selectedClause.ruleCode).map(item =>
                  <li key={item.ruleComponentId}>
                    <button type="button" className="button button--quiet" onClick={() => selectClause(item.ruleComponentId)}>
                      {item.textSummary} · {item.decisionLabel}{item.confidence === "low" ? " · 低置信" : ""}
                    </button>
                    <ReasonText text={item.reason} />
                  </li>)}</ul>
              </details>}
          </div>
        </section>
        {selectedClause && evidenceVisited && <EvidenceReader title={`${selectedClause.ruleCode} · 原始资料`}
          open={evidenceOpen} onClose={() => setEvidenceOpen(false)}>
          <EligibilityEvidencePanel
            review={reviewData}
            clause={selectedClause}
            selectedFactIndex={selectedFactIndex}
            onSelectFact={setSelectedFactIndex}
          />
        </EvidenceReader>}
      </div>
      <footer className="eligibility-workbench__footnote">
        规则修订：{formatSnapshotVersion(reviewData.ruleSetRevision, null)} · 节点修订：{formatSnapshotVersion(selectedEpisode.revision, null)}
      </footer>
    </div>
  );
}

export default EligibilityWorkbenchPage;
