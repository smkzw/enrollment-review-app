import { Printer, FileSearch, Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { FrozenReviewEvidence } from "./FrozenReviewEvidence";
import { ReviewActionResponseDialog } from "./ReviewActionResponseDialog";
import type { ReviewHistoryRunDetailView } from "../../api/review-history/reviewHistoryTypes";
import { actionStateLabel, actionTargetLabel, decisionLabel, gapTypeLabel, stageLabel } from "../../domain/labels";
import { useApplicationMode } from "../../app/applicationMode";
import { reviewConditionNotes } from "../../domain/reviewConditionNotes";
import { frozenReviewExport, reviewEvidenceScopeNote } from "../../domain/frozenReviewExport";

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
      link.download = `入排审核报告-${report.context.subjectCode.replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_")}-${report.run.reviewRunId}.${format}`;
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
          <p className="reports-print__eyebrow">{complete ? "入排审核报告" : "审核尚未完成"}</p>
          <h2>{context.subjectCode} · {context.workflowStageLabel}</h2>
          <p>{context.projectName} · 方案 {context.officialProtocolVersion}</p>
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
      <section className="reports-print__section" aria-label="本次审核资料">
        <p className="reports-print__reason">{reviewEvidenceScopeNote}</p>
        <table className="reports-print__table reports-print__subject-table"><tbody>
          <tr><th scope="row">中心</th><td>{center}</td><th scope="row">审核节点</th><td>{context.workflowStageLabel}</td></tr>
          <tr><th scope="row">审核时间</th><td>{reviewTime(run.completedAt ?? run.startedAt)}</td>
            <th scope="row">审核情况</th><td>{complete ? "已完成，逐项结果见下表" : "尚未完成，不作为正式报告"}</td></tr>
        </tbody></table>
      </section>
      <section className="reports-print__section" aria-labelledby="reports-decisions-title">
        <h3 id="reports-decisions-title">逐项审核结果</h3>
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
      <section className="reports-print__section" aria-labelledby="reports-actions-title">
        <h3 id="reports-actions-title">补充资料与核实事项</h3>
        {focusActionId !== null && !actions.some((item) => item.actionId === focusActionId)
          && <p role="status">未在本次审核中找到所选办理事项，请返回待办清单重新选择。</p>}
        <p className="reports-print__reason">以下为当前办理情况。事项关闭不改变上述审核结论；补充资料后的结论另行审核。</p>
        {actions.length === 0 ? <p>{report.controls.some((item) => item.status === "unverified")
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
      </section>
      <footer className="reports-print__footnote">
        审核时间为本次记录保存的时间（北京时间）。本报告辅助医学监查，不代替研究者的最终入组决定。
      </footer>
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
