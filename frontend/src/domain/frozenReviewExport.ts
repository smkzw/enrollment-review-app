import type { ReviewHistoryRunDetailView } from "../api/review-history/reviewHistoryTypes";
import { actionStateLabel, actionTargetLabel, decisionLabel, gapTypeLabel, stageLabel } from "./labels";
import { reviewConditionNotes } from "./reviewConditionNotes";
import type { LocatorView } from "../api/evidence";

interface ReportSection { title: string; paragraphs: string[] }
export const reviewEvidenceScopeNote = "本次审核仅依据本次已提供的资料及其核对结果。已知缺失和待核实事项另列；未提供的情况不作推断。";
const controlLabels = { fulfilled: "已满足", unfulfilled: "未满足", unverified: "尚无法判定", not_applicable: "本次不适用" };
const locatorText = (locator: LocatorView) => `资料版本 ${locator.sourceDocumentVersionId}，第 ${locator.pageNumber} 页，${locator.precisionLabel}：${locator.excerpt ?? "未保存文字摘录，请在系统中查看原件。"}`;
const time = (value: string) => new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium", timeStyle: "medium", timeZone: "Asia/Shanghai", hour12: false,
}).format(new Date(value));

function sections(report: ReviewHistoryRunDetailView, exportedAt: Date): ReportSection[] {
  const { run, context } = report;
  if (run.status !== "completed" || !run.completedAt || report.missingRuleComponentIds.length || report.missingProtocolControlIds.length) {
    throw new Error("本次审核尚未完整形成，暂不能导出正式报告。");
  }
  const evidence = (ids: string[]) => ids.map((id) => {
    const locator = report.evidenceLocators.find((item) => item.locatorId === id);
    if (!locator) throw new Error("报告引用的原件位置不完整，请刷新后重试。");
    return locatorText(locator);
  });
  const result: ReportSection[] = [{ title: "本次审核资料", paragraphs: [
    `研究项目：${context.projectName}`, `受试者：${context.subjectCode}`,
    `中心：${[context.centerCode, context.centerName].filter(Boolean).join(" · ") || "未登记"}`,
    `审核节点：${context.workflowStageLabel}`, `方案版本：${context.officialProtocolVersion}`,
    `审核完成时间：${time(run.completedAt)}`, `导出时间：${time(exportedAt.toISOString())}`,
    reviewEvidenceScopeNote,
    "本报告保留该次审核的结论，不代替研究者最终入组决定。办理情况截至本次读取报告时；事项关闭不改变原审核结论。",
  ] }];
  for (const item of report.assessments) {
    result.push({ title: `${item.clause.ruleDisplayCode} · ${item.clause.ruleTitle}`, paragraphs: [
      `审核结果：${decisionLabel[item.decision]}`,
      `尚待补充或核实：${item.gapTypes.length ? item.gapTypes.map((gap) => gapTypeLabel[gap]).join("；") : "本项未记录待补充内容"}`,
      ...item.conditions.flatMap((condition, index) => [
        `条件 ${index + 1}：${condition.conditionText ?? "未单列原文摘录"}`,
        condition.truth === "unknown" ? "尚不能核实该条件" : condition.truth === "true" ? "条件成立" : "条件不成立",
        ...(condition.observedValue === null ? [] : [`记录值：${typeof condition.observedValue === "boolean" ? condition.observedValue ? "是" : "否" : condition.observedValue}${condition.observedUnit ? ` ${condition.observedUnit}` : ""}`]),
        ...reviewConditionNotes(condition.reasonCodes),
        ...(condition.selectionNote ? [condition.selectionNote] : []),
        ...condition.calculationBasis,
        ...condition.unverifiedEvidence.flatMap((gap) => [
          ...reviewConditionNotes(gap.reasonCodes).map((note) => `待核实原文：${note}`),
          ...evidence([gap.locatorId]),
        ]),
        ...condition.notSelected.flatMap((record, recordIndex) => [
          `其他记录 ${recordIndex + 1}：${record.reason}`,
          ...evidence(record.locatorIds),
        ]),
      ]), ...evidence(item.locatorIds),
    ] });
  }
  for (const item of report.controls) {
    result.push({ title: `${item.displayLabel} · ${item.title}`, paragraphs: [
      item.statement, { mandatory: "方案要求", recommended: "方案建议", best_effort: "方案要求尽可能完成" }[item.modality],
      `核对情况：${controlLabels[item.status]}`,
      ...reviewConditionNotes(item.reasonCodes),
      ...item.calculationBasis,
      ...item.protocolExcerpts.filter((text): text is string => text !== null).map((text) => `方案原文：${text}`),
      ...evidence(item.locatorIds),
      ...item.unverifiedEvidence.flatMap((gap) => [
        ...reviewConditionNotes(gap.reasonCodes).map((note) => `待核实原文：${note}`),
        ...evidence([gap.locatorId]),
      ]),
    ] });
  }
  for (const item of report.controlSelectionRecords) {
    result.push({ title: `${item.displayLabel} · ${item.conditionRole}的记录采用依据`, paragraphs: [
      item.conditionText, item.selectionNote,
      ...item.notSelected.flatMap((record, index) => [
        `其他记录 ${index + 1}：${record.reason}`, ...evidence(record.locatorIds),
      ]),
    ] });
  }
  result.push({ title: "补充资料与核实事项", paragraphs: report.actions.length ? report.actions.flatMap((action) => [
    `${action.clause?.ruleDisplayCode ?? action.control?.displayLabel ?? "对应要求未列明"}：${action.requestedAction}`,
    `应提供资料：${action.acceptableEvidence}`,
    `负责方及节点：${actionTargetLabel[action.targetParty]} · ${stageLabel[action.dueStage]}`,
    `办理情况：${actionStateLabel[action.state]}`,
    ...action.transitions.flatMap((transition) => [
      `${time(transition.occurredAt)} · ${actionStateLabel[transition.toState]}：${transition.reason}`,
      ...(transition.responseEvidence?.locators.map((locator) => `回应资料：${locatorText(locator)}`) ?? []),
    ]),
  ]) : [report.controls.some((item) => item.status === "unverified")
    ? "其他章节仍有尚无法判定的要求，详见对应核对情况；本次尚未保存对应办理事项。" : "本次审核未记录补充事项。"] });
  result.push({ title: "报告追溯信息", paragraphs: [
    `审核记录编号：${run.reviewRunId}`, `资料版本编号：${run.evidenceSnapshotV2Id}`,
    `资料整理版本编号：${run.completeProcessingRevisionId}`, `规则版本：${run.ruleSetRevision}`,
    "本文件包含已保存的文字摘录和原件页码，不包含原件附件。原始资料及精确标注请在系统中查看。",
  ] });
  return result;
}

const htmlText = (text: string) => text.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
const markdownText = (text: string) => htmlText(text).replace(/([\\`*_{}\[\]()#+.!|~-])/g, "\\$1").replace(/\r?\n/g, "  \n");

export function frozenReviewExport(report: ReviewHistoryRunDetailView, format: "md" | "html", exportedAt = new Date()): string {
  const content = sections(report, exportedAt);
  const title = `入排审核报告 · ${report.context.subjectCode} · ${report.context.workflowStageLabel}`;
  return renderDocument(title, content, format);
}

export function frozenReviewCollectionExport(reports: ReviewHistoryRunDetailView[], format: "md" | "html", exportedAt = new Date()): string {
  if (!reports.length || reports.length > 50 || new Set(reports.map((report) => report.run.reviewRunId)).size !== reports.length ||
    new Set(reports.map((report) => report.context.projectId)).size !== 1) {
    throw new Error("请选择同一项目内的报告，每次最多五十份。");
  }
  const reportSections = reports.map((report) => sections(report, exportedAt));
  const content: ReportSection[] = [{ title: "本次选取的报告", paragraphs: [
    `共 ${reports.length} 份已保存报告。以下保留各次审核的资料、日期和结论，不代表项目全部受试者的审核情况。`,
    ...reports.map((report, index) => `${index + 1}. ${report.context.subjectCode} · ${report.context.workflowStageLabel} · ${time(report.run.completedAt!)} · 报告编号 ${report.run.reviewRunId}`),
  ] }];
  reports.forEach((report, index) => {
    const label = `${index + 1}. ${report.context.subjectCode} · ${report.context.workflowStageLabel}`;
    content.push(...reportSections[index].map((section) => ({ ...section, title: `${label} / ${section.title}` })));
  });
  return renderDocument("入排审核报告汇集", content, format);
}

function renderDocument(title: string, content: ReportSection[], format: "md" | "html"): string {
  if (format === "md") return `# ${markdownText(title)}\n\n${content.map((section) => `## ${markdownText(section.title)}\n\n${section.paragraphs.map(markdownText).join("\n\n")}`).join("\n\n")}\n`;
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>${htmlText(title)}</title><style>body{font-family:system-ui,"PingFang SC",sans-serif;color:#24312c;margin:3rem auto;padding:0 2rem;max-width:72rem;line-height:1.8}h1{font-size:1.75rem}h2{font-size:1.15rem;border-bottom:1px solid #d5ded9;padding-bottom:.5rem}section{margin-block:2rem}p{white-space:pre-wrap;overflow-wrap:anywhere;margin:.5rem 0}@media print{body{margin:0;max-width:none}h2{break-after:avoid}p{orphans:3;widows:3}}</style><body><h1>${htmlText(title)}</h1>${content.map((section) => `<section><h2>${htmlText(section.title)}</h2>${section.paragraphs.map((text) => `<p>${htmlText(text)}</p>`).join("")}</section>`).join("")}</body></html>`;
}
