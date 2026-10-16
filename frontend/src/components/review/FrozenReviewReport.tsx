import { Printer, FileSearch, Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { FrozenReviewEvidence } from "./FrozenReviewEvidence";
import { ReviewActionResponseDialog } from "./ReviewActionResponseDialog";
import { ReasonText } from "./ReasonText";
import { StatusBadge } from "../shell/StatusBadge";
import type { EligibilityClauseView } from "../../api/eligibility-review/eligibilityReviewViewModels";
import type { ReviewHistoryRunDetailView } from "../../api/review-history/reviewHistoryTypes";
import { actionStateLabel, actionTargetLabel, decisionLabel, gapTypeLabel, stageLabel } from "../../domain/labels";
import { useApplicationMode } from "../../app/applicationMode";
import { reviewConditionNotes } from "../../domain/reviewConditionNotes";
import { frozenReviewExport, reviewEvidenceScopeNote, reviewLimitationLabel, reviewLimitationContext, reviewSystemIssueLabel, reviewSourceFiles } from "../../domain/frozenReviewExport";

export function reviewTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    hour12: false, timeZone: "Asia/Shanghai",
  }).format(new Date(value));
}

export function FrozenReviewReport({ report, onActionChanged, focusActionId = null }: { report: ReviewHistoryRunDetailView; onActionChanged: () => void; focusActionId?: string | null }) {
  const { canModify } = useApplicationMode();
  const article = useRef<HTMLElement>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const exportReport = (format: "md" | "html") => {
    setExportError(null);
    try {
      const content = frozenReviewExport(report, format);
      const url = URL.createObjectURL(new Blob([content], { type: format === "html" ? "text/html;charset=utf-8" : "text/markdown;charset=utf-8" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `入排审核报告-${report.context.subjectCode.replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_")}-${reviewTime(report.run.completedAt ?? report.run.startedAt).replace(/[\\/: ]/g, "-")}.${format}`;
      document.body.append(link);
      try { link.click(); } finally { link.remove(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "报告导出失败，请重试。");
    }
  };
  const [evidenceSelection, setEvidenceSelection] = useState<{ runId: string; assessmentId: string; excludedFactId?: string; doubtLocatorId?: string } | null>(null);
  const [orderingSelection, setOrderingSelection] = useState<{ runId: string; identity: string; factId: string } | null>(null);
  const [responseSelection, setResponseSelection] = useState<{ runId: string; actionId: string; transitionId: string } | null>(null);
  const [editingAction, setEditingAction] = useState<{ runId: string; actionId: string } | null>(null);
  const [controlSelection, setControlSelection] = useState<{ runId: string; controlId: string; obligationId: string; doubtLocatorId?: string } | null>(null);
  const [draftSelection, setDraftSelection] = useState<{ runId: string; itemId: string } | null>(null);
  const [issueSelection, setIssueSelection] = useState<{ runId: string; index: number } | null>(null);
  useEffect(() => {
    setDraftSelection(null); setEvidenceSelection(null); setOrderingSelection(null);
    setControlSelection(null); setResponseSelection(null); setEditingAction(null); setIssueSelection(null);
  }, [report.run.reviewRunId]);
  useEffect(() => {
    if (focusActionId === null) return;
    const row = Array.from(article.current?.querySelectorAll<HTMLElement>("[data-review-action]") ?? [])
      .find((item) => item.dataset.reviewAction === focusActionId);
    row?.scrollIntoView({ block: "center" });
    row?.focus({ preventScroll: true });
  }, [report.run.reviewRunId, focusActionId]);
  useEffect(() => {
    let opened: HTMLDetailsElement[] = [];
    const beforePrint = () => {
      opened = Array.from(article.current?.querySelectorAll<HTMLDetailsElement>("details:not([open])") ?? []);
      opened.forEach((item) => { item.open = true; });
    };
    const afterPrint = () => { opened.forEach((item) => { item.open = false; }); opened = []; };
    window.addEventListener("beforeprint", beforePrint);
    window.addEventListener("afterprint", afterPrint);
    return () => {
      window.removeEventListener("beforeprint", beforePrint);
      window.removeEventListener("afterprint", afterPrint);
      afterPrint();
    };
  }, [report.run.reviewRunId]);
  const { run, context, assessments, actions } = report;
  const sourceFiles = reviewSourceFiles(report);
  const draft = report.workDraft;
  const sourceIssue = issueSelection?.runId === run.reviewRunId
    ? draft?.systemIssues?.[issueSelection.index] : undefined;
  const draftParents = [...(draft?.clauses ?? [])].sort((a, b) =>
    ({ inclusion: 0, exclusion: 1, required_procedure: 2, medication: 3 })[a.ruleKind] - ({ inclusion: 0, exclusion: 1, required_procedure: 2, medication: 3 })[b.ruleKind]
      || a.ruleCode.localeCompare(b.ruleCode));
  const draftItem = draftSelection?.runId === run.reviewRunId
    ? [...(draft?.clauses ?? []), ...(draft?.componentClauses ?? [])].find(item => item.ruleComponentId === draftSelection.itemId) : undefined;
  const draftSource = (item: EligibilityClauseView) => (item.factRefs.length > 0 || (item.sourceReadRefs?.length ?? 0) > 0)
    ? <button type="button" className="button reports-print__action reports-print__source" onClick={() => setDraftSelection({ runId: run.reviewRunId, itemId: item.ruleComponentId })}>
      <FileSearch size={16} aria-hidden="true" />查看原件</button> : null;
  const evidenceAssessment = evidenceSelection?.runId === run.reviewRunId
    ? assessments.find((item) => item.assessmentId === evidenceSelection.assessmentId) : undefined;
  const responseAction = responseSelection?.runId === run.reviewRunId
    ? actions.find((item) => item.actionId === responseSelection.actionId) : undefined;
  const response = responseAction?.transitions.find((item) => item.transitionId === responseSelection?.transitionId);
  const actionToEdit = editingAction?.runId === run.reviewRunId ? actions.find((item) => item.actionId === editingAction.actionId) : undefined;
  const complete = run.status === "completed";
  const selectedControl = controlSelection?.runId === run.reviewRunId ? report.controls.find((item) =>
    item.protocolControlId === controlSelection.controlId && item.obligationId === controlSelection.obligationId) : undefined;
  const controlStatus = { fulfilled: "已满足", unfulfilled: "未满足", unverified: "尚无法判定", not_applicable: "本次不适用" };
  const center = [context.centerCode, context.centerName].filter(Boolean).join(" · ") || "未登记";
  return (
    <article ref={article} className="reports-print" data-testid="reports-print">
      <header className="reports-print__head">
        <div>
          <p className="reports-print__eyebrow">{draft ? "入排审核工作稿 · 未签发" : complete ? "入排审核报告" : "审核尚未完成"}</p>
          <h2>{context.subjectCode} · {context.workflowStageLabel}</h2>
          <p>方案 {context.officialProtocolVersion} · 规则第 {run.ruleSetRevision} 版</p>
        </div>
        <div className="reports-print__tools reports-print__action">
        <button type="button" className="button button--primary reports-print__action"
          disabled={!complete} onClick={() => window.print()}>
          <Printer size={18} aria-hidden="true" />打印报告
        </button>
        <button type="button" className="button reports-print__action" disabled={!complete}
          onClick={() => exportReport("html")}><Download size={18} aria-hidden="true" />导出网页报告</button>
        <button type="button" className="button reports-print__action" disabled={!complete}
          onClick={() => exportReport("md")}><Download size={18} aria-hidden="true" />导出文字报告</button>
        </div>
      </header>
      {exportError && <p role="alert">{exportError}</p>}
      {draft?.verificationOnly && <p role="status">本工作稿使用构建者审定的验证规则，不用于正式审核。</p>}
      <section className="reports-print__section" aria-label="本次审核资料">
        <p className="reports-print__reason">{reviewEvidenceScopeNote}</p>
        <table className="reports-print__table reports-print__subject-table"><tbody>
          <tr><th scope="row">中心</th><td>{center}</td><th scope="row">审核节点</th><td>{context.workflowStageLabel}</td></tr>
          {(context.nodeStartDate || context.evidenceCutoffDate) && <tr>
            <th scope="row">节点开始日</th><td>{context.nodeStartDate ?? "未填写"}</td>
            <th scope="row">本次资料截至</th><td>{context.evidenceCutoffDate ?? context.nodeStartDate ?? "未填写"}</td>
          </tr>}
          <tr><th scope="row">审核时间</th><td>{reviewTime(run.completedAt ?? run.startedAt)}</td>
            <th scope="row">审核情况</th><td>{complete ? draft ? "工作稿已保存，未签发" : "已完成，逐项结果见下表" : "尚未完成，不作为正式报告"}</td></tr>
        </tbody></table>
        {sourceFiles.length > 0 && <details className="reports-print__conditions">
          <summary>本次资料文件（{sourceFiles.length}）</summary>
          {sourceFiles.map(([id, name]) => <p className="reports-print__reason" key={id}>{name}</p>)}
        </details>}
      </section>
      {report.restrictedRequirements.length > 0 && <section className="reports-print__section" aria-label="尚不能判定的方案要求">
        <h3>尚不能判定的方案要求（{report.restrictedRequirements.length}）</h3>
        <p className="reports-print__reason">以下是方案含义或系统计算能力的限制，不等于病例缺少资料，也不能据此认为受试者符合全部要求。</p>
        <details className="reports-print__conditions" open={draft ? undefined : true}><summary>查看受影响要求与原文</summary>
        <table className="reports-print__table"><thead><tr><th scope="col">方案要求</th><th scope="col">尚未解决的问题</th><th scope="col">本次保存的方案原文</th></tr></thead>
          <tbody>{report.restrictedRequirements.map((item) => <tr key={item.requirementId}>
            <th scope="row">{item.displayLabel}<small>{item.title}</small></th>
            <td>{reviewLimitationLabel[item.limitationKind]}{item.unresolvedDimensions.map((text, index) => <small key={index}>{text}</small>)}</td>
            <td><p>{item.sourceText}</p>{item.sourceExcerpts.map((text, index) => <small key={index}>依据摘录：{text}</small>)}
              {reviewLimitationContext(item).map((text, index) => <small key={index}>{text}</small>)}
              {item.dependencyRefs.map((id) => {
                const dependency = report.restrictedRequirements.find((entry) => entry.requirementId === id);
                return <small key={id}>还需核清相关要求：{dependency?.displayLabel} · {dependency?.title}</small>;
              })}
            </td>
          </tr>)}</tbody>
        </table>
        </details>
      </section>}
      <section className="reports-print__section" aria-labelledby="reports-decisions-title">
        <h3 id="reports-decisions-title">逐项审核结果</h3>
        {draft ? <table className="reports-print__table reports-print__draft-table">
          <thead><tr><th scope="col">审核要求</th><th scope="col">结论</th><th scope="col">判定依据</th></tr></thead>
          <tbody>{draftParents.map(item => {
            const children = draft.componentClauses?.filter(child => child.parentRuleCode === item.ruleCode) ?? [];
            return <tr key={item.ruleComponentId}>
              <th scope="row">{item.ruleCode}
                <details className="reports-print__conditions reports-print__protocol-source"><summary>方案要求</summary><p>{item.sourceText ?? item.textSummary}</p></details>
              </th>
              <td><strong>{item.decisionLabel}</strong>{item.confidence && <StatusBadge tone={item.confidence === "low" ? "info" : "neutral"} text={item.confidence === "low" ? "低置信" : "高置信"} />}
                {item.confirmationKind && <small>{item.confirmationKind === "medical_manager" ? "医学经理已核实" : "构建者试用核实，非正式医学核实"}</small>}</td>
              <td><ReasonText text={item.reason} compact />{draftSource(item)}
                {children.length > 0 && <details className="reports-print__conditions"><summary>分项核对（{children.length}）</summary>
                  <ol>{children.map(child => <li key={child.ruleComponentId}>
                    <p><strong>{child.textSummary}</strong> · {child.decisionLabel}</p>
                    <ReasonText text={child.reason} compact />{draftSource(child)}
                  </li>)}</ol>
                </details>}
              </td>
            </tr>;
          })}</tbody>
        </table> : <>
        <table className="reports-print__table reports-print__decision-table">
          <thead><tr><th scope="col">审核要求</th><th scope="col">结论</th><th scope="col">尚待补充或核实</th></tr></thead>
          <tbody>{assessments.map((item) => (
            <tr key={item.assessmentId}>
              <th scope="row"><span>{item.clause.ruleDisplayCode}</span><small>{item.clause.ruleTitle}</small>
                <details className="reports-print__conditions"><summary>条件核对（{item.conditions.length}）</summary>
                  <ol>{item.conditions.map((condition, index) => <li key={condition.predicateId}>
                    <p>{condition.conditionText ?? `第 ${index + 1} 项条件（未单列原文摘录）`}</p>
                    <p>{condition.truth === "unknown" ? "尚不能核实该条件" : condition.truth === "true" ? "条件成立" : "条件不成立"}
                      {condition.observedValue !== null && <> · 记录值：{typeof condition.observedValue === "boolean"
                        ? condition.observedValue ? "是" : "否" : condition.observedValue}{condition.observedUnit ? ` ${condition.observedUnit}` : ""}</>}
                    </p>
                    {reviewConditionNotes(condition.reasonCodes)
                      .map((note) => <p key={note} className={condition.truth === "unknown" ? "reports-print__reason" : undefined}>{note}</p>)}
                    {condition.selectionNote && <p>{condition.selectionNote}</p>}
                    {condition.calculationBasis.map((note) => <p key={note}>{note}</p>)}
                    {condition.unverifiedEvidence.map((gap) => <div key={gap.locatorId}>
                      {reviewConditionNotes(gap.reasonCodes).map((note) => <p className="reports-print__reason" key={note}>{note}</p>)}
                      <button type="button" className="button reports-print__action reports-print__source"
                        onClick={() => setEvidenceSelection({ runId: run.reviewRunId,
                          assessmentId: item.assessmentId, doubtLocatorId: gap.locatorId })}>
                        <FileSearch size={16} aria-hidden="true" />查看待核实原件
                      </button>
                    </div>)}
                    {condition.notSelected.map((record, recordIndex) => <p key={record.factId}>
                      其他记录 {recordIndex + 1}：{record.reason}
                      {record.locatorIds.length > 0 && <button type="button"
                        className="button reports-print__action reports-print__source"
                        onClick={() => setEvidenceSelection({ runId: run.reviewRunId,
                          assessmentId: item.assessmentId, excludedFactId: record.factId })}>
                        <FileSearch size={16} aria-hidden="true" />查看该记录
                      </button>}
                    </p>)}
                  </li>)}</ol>
                </details>
              </th>
              <td>{item.decision === "not_due" ? "不在本节点到期" : decisionLabel[item.decision]}</td>
              <td>{item.gapTypes.length ? item.gapTypes.map((gap) => gapTypeLabel[gap]).join("；") : "本项未记录待补充内容"}
                {item.locatorIds.length > 0 && <button type="button" className="button reports-print__action reports-print__source"
                  onClick={() => setEvidenceSelection({ runId: run.reviewRunId, assessmentId: item.assessmentId })}>
                  <FileSearch size={16} aria-hidden="true" />查看原件
                </button>}
              </td>
            </tr>
          ))}</tbody>
        </table>
        {!complete && <p className="reports-print__reason">还有 {report.missingRuleComponentIds.length} 项尚未形成审核记录。</p>}
        </>}
      </section>
      {(report.controls.length > 0 || report.missingProtocolControlIds.length > 0) && <section className="reports-print__section" aria-labelledby="reports-controls-title">
        <h3 id="reports-controls-title">方案其他章节的审核要求</h3>
        <table className="reports-print__table"><thead><tr><th scope="col">方案要求</th><th scope="col">核对情况</th><th scope="col">原始资料</th></tr></thead>
          <tbody>{report.controls.map((item) => <tr key={JSON.stringify([item.protocolControlId, item.obligationId])}>
            <th scope="row">{item.displayLabel} · {item.title}<small>{item.statement}</small>
              <small>{{ mandatory: "方案要求", recommended: "方案建议", best_effort: "方案要求尽可能完成" }[item.modality]}</small>
              <details className="reports-print__conditions"><summary>方案原文</summary>
              {item.protocolExcerpts.some(Boolean) ? item.protocolExcerpts.map((text, index) => text && <p key={index}>{text}</p>) : <p>本项未单列原文摘录。</p>}
            </details></th>
            <td>{controlStatus[item.status]}
              {reviewConditionNotes(item.reasonCodes).map((note) => <small key={note}>{note}</small>)}
              {item.calculationBasis.map((note) => <small key={note}>{note}</small>)}
              {item.status === "unverified" && item.reasonCodes.length === 0 && (
                <small>{item.activation === "unknown" ? "适用、触发或例外条件尚待核实" : "本项原始资料尚未核实清楚"}</small>
              )}
              {item.unverifiedEvidence.map((gap, index) => <div key={`${gap.locatorId}:${index}`}>
                {reviewConditionNotes(gap.reasonCodes).map((note) => <small key={note}>待核实原文：{note}</small>)}
                <button type="button" className="button reports-print__action reports-print__source"
                  onClick={() => setControlSelection({ runId: run.reviewRunId, controlId: item.protocolControlId,
                    obligationId: item.obligationId, doubtLocatorId: gap.locatorId })}>
                  <FileSearch size={16} aria-hidden="true" />查看待核实原件</button>
              </div>)}
            </td>
            <td>{item.locatorIds.length > 0 ? <button type="button" className="button reports-print__action reports-print__source"
              onClick={() => setControlSelection({ runId: run.reviewRunId, controlId: item.protocolControlId, obligationId: item.obligationId })}>
              <FileSearch size={16} aria-hidden="true" />查看原件</button> : "本项尚未引用判定依据"}</td>
          </tr>)}</tbody></table>
        {report.missingProtocolControlIds.length > 0 && <p>还有 {report.missingProtocolControlIds.length} 项要求尚未形成审核记录。</p>}
      </section>}
      {report.controlSelectionRecords.length > 0 && <section className="reports-print__section">
        <details className="reports-print__conditions"><summary>其他章节要求的记录采用依据</summary>
          <ol>{report.controlSelectionRecords.map((item) => <li key={item.identity}>
            <p>{item.displayLabel} · {item.conditionRole}：{item.conditionText}</p>
            <p style={{ whiteSpace: "pre-line" }}>{item.selectionNote}</p>
            {item.notSelected.map((record, index) => <p key={record.factId}>
              其他记录 {index + 1}：{record.reason}
              {record.locatorIds.length > 0 && <button type="button" className="button reports-print__action reports-print__source"
                onClick={() => setOrderingSelection({ runId: run.reviewRunId, identity: item.identity, factId: record.factId })}>
                <FileSearch size={16} aria-hidden="true" />查看该记录</button>}
            </p>)}
          </li>)}</ol>
        </details>
      </section>}
      {draft ? (draft.systemIssues?.length ?? 0) > 0 && <section className="reports-print__section" aria-label="核对范围与未采用记录">
        {[{ label: "系统尚未完成的核对", issues: draft.systemIssues?.filter(issue => issue.kind !== "excerpt_unverified") ?? [] },
          { label: "尚未用于判断的原件记录", issues: draft.systemIssues?.filter(issue => issue.kind === "excerpt_unverified") ?? [] }].map(group => group.issues.length > 0 &&
          <details className="reports-print__conditions" key={group.label}><summary>{group.label}（{group.issues.length}）</summary>
            <ul>{group.issues.map((issue, index) => <li key={index}>
              <strong>{reviewSystemIssueLabel(issue)}</strong>：{issue.detail}
              <small>{issue.alternative}</small>
              {issue.sourceDocumentVersionId && issue.pageArtifactId && issue.pageNumber && <button type="button"
                className="button reports-print__action reports-print__source" onClick={() => setIssueSelection({
                  runId: run.reviewRunId, index: draft.systemIssues?.indexOf(issue) ?? -1 })}>
                <FileSearch size={16} aria-hidden="true" />查看待核原件
              </button>}
            </li>)}</ul>
          </details>)}
      </section> : <section className="reports-print__section" aria-labelledby="reports-actions-title">
        <h3 id="reports-actions-title">补充资料与核实事项</h3>
        {focusActionId !== null && !actions.some((item) => item.actionId === focusActionId)
          && <p role="status">未在本次审核中找到所选办理事项，请返回待办清单重新选择。</p>}
        <p className="reports-print__reason">以下为当前办理情况。事项关闭不改变上述审核结论；补充资料后的结论另行审核。</p>
        {actions.length === 0 ? <p>{report.restrictedRequirements.length
          ? "方案仍有待澄清或暂不能计算的要求，详见上表；不能据此认为受试者符合全部要求。" : report.controls.some((item) => item.status === "unverified")
          ? "其他章节仍有尚无法判定的要求，详见上表；本次尚未保存对应办理事项。" : "本次审核未记录补充事项。"}</p> : (
          <table className="reports-print__table"><thead><tr>
            <th scope="col">对应要求</th><th scope="col">需要办理</th><th scope="col">应提供资料</th><th scope="col">负责方及节点</th><th scope="col">当前情况</th>
          </tr></thead><tbody>{actions.map((action) => <tr key={action.actionId} data-review-action={action.actionId} tabIndex={-1}>
            <th scope="row">{action.clause?.ruleDisplayCode ?? action.control?.displayLabel}<small>{action.clause?.ruleTitle ?? action.control?.title}</small></th>
            <td>{action.requestedAction}</td><td>{action.acceptableEvidence}</td>
            <td>{actionTargetLabel[action.targetParty]} · {stageLabel[action.dueStage]}</td>
            <td>{actionStateLabel[action.state]}
              {canModify && complete && ["open", "reopened", "closed_manual"].includes(action.state) && <button type="button"
                className="button reports-print__action reports-print__source"
                onClick={() => setEditingAction({ runId: run.reviewRunId, actionId: action.actionId })}>
                {action.state === "closed_manual" ? "重新办理" : "登记办结依据"}
              </button>}
              {action.transitions.length > 0 && <details className="reports-print__conditions"><summary>办理记录</summary>
                <ol>{action.transitions.map((transition) => <li key={transition.transitionId}>
                  <p>{reviewTime(transition.occurredAt)} · {actionStateLabel[transition.toState]}</p><p>{transition.reason}</p>
                  {transition.responseEvidence && <button type="button" className="button reports-print__action"
                    onClick={() => setResponseSelection({ runId: run.reviewRunId, actionId: action.actionId, transitionId: transition.transitionId })}>
                    <FileSearch size={16} aria-hidden="true" />查看回应原件</button>}
                </li>)}</ol>
              </details>}
            </td>
          </tr>)}</tbody></table>
        )}
      </section>}
      <footer className="reports-print__footnote">
        审核时间为本次记录保存的时间（北京时间）。本报告辅助医学监查，不代替研究者的最终入组决定。
      </footer>
      {draftItem && <FrozenReviewEvidence key={JSON.stringify(draftSelection)} context={context}
        title={`${draftItem.ruleCode} · 当时的原始资料`}
        locators={report.evidenceLocators.filter(locator => draftItem.factRefs.some(ref => ref.locatorId === locator.locatorId))}
        pageRefs={draftItem.sourceReadRefs} onClose={() => setDraftSelection(null)} />}
      {sourceIssue?.sourceDocumentVersionId && sourceIssue.pageArtifactId && sourceIssue.pageNumber && <FrozenReviewEvidence
        key={JSON.stringify(issueSelection)} context={context} title="当时的待核原件" locators={[]}
        pageRefs={[{ sourceDocumentVersionId: sourceIssue.sourceDocumentVersionId,
          pageArtifactId: sourceIssue.pageArtifactId, pageNumber: sourceIssue.pageNumber,
          excerpt: null, disposition: "unresolved" }]} onClose={() => setIssueSelection(null)} />}
      {evidenceAssessment && <FrozenReviewEvidence key={JSON.stringify(evidenceSelection)}
        context={context} title={`${evidenceAssessment.clause.ruleDisplayCode} · ${evidenceSelection?.doubtLocatorId ? "待核实原件" : "原始资料"}`}
        locators={report.evidenceLocators.filter((item) => evidenceSelection?.doubtLocatorId
          ? item.locatorId === evidenceSelection.doubtLocatorId && evidenceAssessment.conditions.some((condition) =>
            condition.unverifiedEvidence.some((gap) => gap.locatorId === item.locatorId))
          : evidenceSelection?.excludedFactId
          ? evidenceAssessment.conditions.some((condition) => condition.notSelected.some((record) =>
            record.factId === evidenceSelection.excludedFactId && record.locatorIds.includes(item.locatorId)))
          : evidenceAssessment.locatorIds.includes(item.locatorId))}
        onClose={() => setEvidenceSelection(null)} />}
      {selectedControl && <FrozenReviewEvidence key={JSON.stringify([run.reviewRunId, selectedControl.protocolControlId, selectedControl.obligationId, controlSelection?.doubtLocatorId])}
        context={context} title={controlSelection?.doubtLocatorId ? "补充审核要求 · 待核实原件" : "补充审核要求 · 原始资料"}
        locators={report.evidenceLocators.filter((item) => controlSelection?.doubtLocatorId
          ? item.locatorId === controlSelection.doubtLocatorId : selectedControl.locatorIds.includes(item.locatorId))}
        onClose={() => setControlSelection(null)} />}
      {orderingSelection?.runId === run.reviewRunId && report.controlSelectionRecords.some((item) =>
        item.identity === orderingSelection.identity && item.notSelected.some((record) => record.factId === orderingSelection.factId))
        && <FrozenReviewEvidence key={JSON.stringify(orderingSelection)} context={context} title="相关原始记录"
          locators={report.evidenceLocators.filter((locator) => report.controlSelectionRecords.some((item) =>
            item.identity === orderingSelection.identity && item.notSelected.some((record) =>
              record.factId === orderingSelection.factId && record.locatorIds.includes(locator.locatorId))))}
          onClose={() => setOrderingSelection(null)} />}
      {response?.responseEvidence && responseAction && <FrozenReviewEvidence key={`${run.reviewRunId}:${response.transitionId}`}
        context={response.responseEvidence} title={`${responseAction.clause?.ruleDisplayCode ?? responseAction.control?.displayLabel} · 办理回应原件`}
        locators={response.responseEvidence.locators} onClose={() => setResponseSelection(null)} />}
      {canModify && actionToEdit && <ReviewActionResponseDialog key={`${run.reviewRunId}:${actionToEdit.actionId}`}
        action={actionToEdit} context={context} onClose={() => setEditingAction(null)}
        onSaved={() => { setEditingAction(null); onActionChanged(); }} />}
    </article>
  );
}
