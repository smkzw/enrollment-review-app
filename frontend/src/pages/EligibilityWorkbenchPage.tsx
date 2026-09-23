import { useEffect, useMemo, useState, type ReactNode } from "react";
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
import { OriginalEvidenceViewer } from "../components/evidence-workspace/OriginalEvidenceViewer";
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

type EligibilityWorkItem = EligibilityClauseView & { controlId?: string; continuingNote?: string | null };

function controlWorkItems(controls: ReadonlyArray<EligibilityControlView>): EligibilityWorkItem[] {
  return controls.flatMap((control) => control.obligations.map((obligation) => ({
    controlId: control.protocolControlId,
    ruleComponentId: `control:${control.protocolControlId}:${obligation.obligationId}`,
    ruleCode: control.displayLabel,
    ruleKind: "required_procedure" as const,
    textSummary: control.title,
    sourceText: obligation.statement,
    parentRuleCode: null,
    decision: ({
      fulfilled: "requirement_met",
      unfulfilled: "requirement_not_met",
      unverified: "indeterminate",
      not_applicable: "not_applicable",
    } as const)[obligation.status],
    decisionLabel: obligation.statusLabel,
    reason: obligation.reason,
    continuingNote: obligation.continuingNote,
    factRefs: obligation.factRefs,
    gapType: null,
    determinationMode: "semantic" as const,
    actionOwner: null,
    actionDetail: null,
    actionEvidence: null,
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
  }
}

function workItemKindLabel(item: EligibilityWorkItem): string {
  return item.controlId ? "方案补充要求" : clauseKindLabel(item.ruleKind);
}

export function isUndeterminedDecision(decision: EligibilityDecision): boolean {
  return decision === "professional_judgment" || decision === "indeterminate" || decision === "conflict";
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
  return `${project.projectName} · ${project.studyPhaseLabel} · 方案 ${project.officialVersion}`;
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
  unclassified: "原因待明确",
};

/** 队列成员：风险（已触发/未满足）、冲突、未决；已满足/未触发/未到期不算问题。 */
function clauseIsIssue(clause: EligibilityClauseView): boolean {
  const tone = decisionTone(clause.decision);
  return tone === "danger" || tone === "info";
}

/** 根因键：优先投影缺口类型；未归类时按判定回退，绝不静默丢失。 */
function clauseIssueKey(clause: EligibilityClauseView): {
  key: string;
  severity: IssueSeverity;
} {
  switch (clause.decision) {
    case "conflict":
    case "exclusion_triggered":
    case "inclusion_not_met":
    case "requirement_not_met":
      return { key: clause.gapType ?? "clause_not_satisfied", severity: "danger" };
    case "professional_judgment":
      return { key: clause.gapType ?? "professional_judgment", severity: "attention" };
    default:
      return { key: clause.gapType ?? "unclassified", severity: "info" };
  }
}

function issueGroupLabel(key: string): string {
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
      ISSUE_SEVERITY_ORDER[a.severity] - ISSUE_SEVERITY_ORDER[b.severity] ||
      b.clauses.length - a.clauses.length ||
      a.key.localeCompare(b.key),
  );
}

function compareEligibilityClauses(
  left: EligibilityClauseView,
  right: EligibilityClauseView,
): number {
  const leftSeverity = clauseIsIssue(left)
    ? ISSUE_SEVERITY_ORDER[clauseIssueKey(left).severity]
    : 3;
  const rightSeverity = clauseIsIssue(right)
    ? ISSUE_SEVERITY_ORDER[clauseIssueKey(right).severity]
    : 3;
  return leftSeverity - rightSeverity
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
  return (
    <section className="eligibility-issue-queue" aria-label="问题队列">
      <p className="eligibility-issue-queue__summary">
        {totalIssues} 条条款需要处理，按问题类型归为 {groups.length} 类。
      </p>
      {groups.map((group, index) => {
        const meta = ISSUE_SEVERITY_META[group.severity];
        return (
          <details
            key={group.key}
            className="eligibility-issue-queue__group"
            open={index === 0}
          >
            <summary>
              <StatusBadge tone={meta.tone} text={meta.text} />
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
  selectedFactIndex: number;
  onSelectFact: (index: number) => void;
}

function EligibilityClauseDetail({
  clause,
  selectedFactIndex,
  onSelectFact,
}: EligibilityClauseDetailProps) {
  return (
    <div className="eligibility-clause-detail">
      <div className="eligibility-clause-detail__decision">
        <StatusBadge
          tone={decisionTone(clause.decision)}
          text={clause.decisionLabel}
          hint={clause.reason}
          icon={decisionIcon(clause.decision)}
        />
      </div>
      <ul className="eligibility-clause-detail__bullets" aria-label="条款详情">
        <li className="eligibility-detail-bullet">
          <strong>判定依据</strong>
          <span>{clause.reason}</span>
        </li>
        {clause.continuingNote && <li className="eligibility-detail-bullet">
          <strong>后续持续要求</strong>
          <span>{clause.continuingNote}</span>
        </li>}
        {clause.actionOwner !== null && clause.actionDetail !== null && (
          <li className="eligibility-detail-bullet">
            <strong>建议动作 · {actionTargetLabel[clause.actionOwner]}</strong>
            <span>{clause.actionDetail}</span>
            {clause.actionEvidence !== null && (
              <span className="eligibility-muted">可接受证据：{clause.actionEvidence}</span>
            )}
          </li>
        )}
        {(!clause.sourceText || clause.controlId) && (
          <li className="eligibility-detail-bullet">
            <strong>审核要点</strong>
            <span>{clause.textSummary}</span>
          </li>
        )}
      </ul>
      {clause.sourceText && (
        <details className="eligibility-clause-detail__source">
          <summary>查看方案原文</summary>
          <p>{clause.sourceText}</p>
        </details>
      )}
      <section className="eligibility-detail-section" aria-labelledby="eligibility-facts-title">
        <h3 id="eligibility-facts-title">关联事实</h3>
        {clause.factRefs.length === 0 ? (
          <p className="eligibility-muted">当前条款没有关联事实。</p>
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
      </section>
      {!clause.controlId && <p className="eligibility-clause-detail__mode">
        {determinationModeLabel(clause.determinationMode)}
      </p>}
    </div>
  );
}

function determinationModeLabel(mode: EligibilityClauseView["determinationMode"]): string {
  switch (mode) {
    case "deterministic":
      return "系统按结构化资料完成判断";
    case "semantic":
      return "系统按资料内容完成判断";
    case "investigator_judgment":
      return "需要研究者结合资料确认";
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
  const [browsedPage, setBrowsedPage] = useState<{ context: string; entryId: string } | null>(null);
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
  const referencePage = selectedFact === null
    ? null
    : selectedFact.pageNumber === null
      ? null
      : pages.find((page) => page.pageNumber === selectedFact.pageNumber
          && page.sourceDocumentVersionId === selectedFact.sourceDocumentVersionId
          && page.pageArtifactId === selectedFact.pageArtifactId) ?? null;
  const sourceContext = JSON.stringify([
    review.completeProcessingRevisionId, clause.ruleComponentId,
    selectedFact?.factId, selectedFact?.locatorId, selectedFact?.sourceDocumentVersionId,
    selectedFact?.pageArtifactId, selectedFact?.pageNumber,
  ]);
  const selectedPage = browsedPage?.context === sourceContext
    ? pages.find((page) => page.entryId === browsedPage.entryId) ?? referencePage
    : referencePage ?? pages[0] ?? null;
  const isReferencePage = referencePage !== null && selectedPage?.entryId === referencePage.entryId;
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

  return (
    <aside className="eligibility-evidence" aria-label="原件面板">
      <header className="workbench-pane__head">
        <div>
          <h2 className="workbench-pane__title">原件</h2>
          <p className="workbench-pane__subtitle">{clause.ruleCode} · {workItemKindLabel(clause)}</p>
        </div>
      </header>
      {selectedPage !== null && (
        <div className="eligibility-evidence__state" role="status">
          <strong>{isReferencePage ? "引用原文" : "浏览原件"}</strong>
          <span>
            {documentNames.get(selectedPage.sourceDocumentVersionId) ?? "原始资料"}
            {` · 第 ${selectedPage.pageNumber} 页`}
          </span>
        </div>
      )}
      {clause.factRefs.length === 0 && (
        <p className="eligibility-muted">当前条款没有已采用事实，可浏览全部原件页核实。</p>
      )}
      {(
        <>
          <ul className="eligibility-evidence__refs" aria-label="关联事实原件定位">
            {clause.factRefs.map((fact, index) => (
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
                    onClick={() => { returnToReference(); onSelectFact(index); }}
                  >
                    <strong>{fact.excerpt?.trim() || `原文依据 ${index + 1}`}</strong>
                    <span>{documentNames.get(fact.sourceDocumentVersionId ?? "") ?? "原始资料"} · 第 {fact.pageNumber} 页</span>
                  </button>
                )}
              </li>
            ))}
          </ul>
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
                返回引用原文
              </button>
            ) : null}
            {isReferencePage && locatorPage.state.status === "error" ? (
              <ErrorState message="原文标注暂时无法读取，可先查看原件。" onRetry={locatorPage.retry} />
            ) : isReferencePage && locatorPage.state.status === "success" && !hasVerifiedBox ? (
              <p className="eligibility-muted">已定位到原件页面，具体文字位置尚未核实，暂不显示红框。</p>
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
  }, [selectedEpisode?.reviewEpisodeId, componentParam]);

  const setProject = (projectId: string) =>
    updateParams({ project: projectId, subject: null, episode: null, component: null });
  const setSubject = (subjectId: string) =>
    updateParams({ subject: subjectId, episode: null, component: null });
  const setEpisode = (episodeId: string) =>
    updateParams({ episode: episodeId, component: null });

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
    return <ErrorState message={review.state.message} onRetry={review.retry} />;
  }

  const reviewData = review.state.data;
  const allClauses: EligibilityWorkItem[] = [
    ...reviewData.clauses, ...controlWorkItems(reviewData.controls),
  ];
  const requestedClause = componentParam === null
    ? null : allClauses.find((clause) => clause.ruleComponentId === componentParam);
  if (componentParam !== null && requestedClause === undefined) {
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
    <div className="eligibility-workbench workbench">
      <header className="page-head">
        <h1 className="page-head__title">入排审核工作台</h1>
        <p className="page-head__note">
          {subjectLabel} · {selectedProject.projectName} · {episodeLabel(selectedEpisode)} · 方案 {selectedProject.officialVersion}
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
        <aside className="workbench-col eligibility-workbench__clauses" aria-label="审核要点列表">
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
        </aside>
        <section className="workbench-col eligibility-workbench__detail" aria-label="审核要点详情">
          <div className="workbench-pane">
            <header className="workbench-pane__head">
              <div>
                <h2 className="workbench-pane__title">
                  <span className="workbench-pane__code">{selectedClause?.ruleCode ?? "审核要点"}</span>
                  <span>{selectedClause ? workItemKindLabel(selectedClause) : ""}</span>
                </h2>
                <p className="workbench-pane__subtitle">审核要点详情</p>
              </div>
            </header>
            {selectedClause ? <EligibilityClauseDetail
              clause={selectedClause}
              selectedFactIndex={selectedFactIndex}
              onSelectFact={setSelectedFactIndex}
            /> : <p className="eligibility-muted">当前筛选没有符合条件的审核要点。</p>}
          </div>
        </section>
        <section className="workbench-col eligibility-workbench__evidence">
          {selectedClause && <EligibilityEvidencePanel
            review={reviewData}
            clause={selectedClause}
            selectedFactIndex={selectedFactIndex}
            onSelectFact={setSelectedFactIndex}
          />}
        </section>
      </div>
      <footer className="eligibility-workbench__footnote">
        规则修订：{formatSnapshotVersion(reviewData.ruleSetRevision, null)} · 节点修订：{formatSnapshotVersion(selectedEpisode.revision, null)}
        {` · 资料快照：${reviewData.evidenceSnapshotV2Id.slice(0, 8)}`}
      </footer>
    </div>
  );
}

export default EligibilityWorkbenchPage;
