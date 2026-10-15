import type { ReviewHistoryRunDetailView, ReviewHistoryRestrictedRequirementView } from "../api/review-history/reviewHistoryTypes";
import { actionStateLabel, actionTargetLabel, decisionLabel, gapTypeLabel, stageLabel } from "./labels";
import { reviewConditionNotes } from "./reviewConditionNotes";
import type { LocatorView } from "../api/evidence";

interface ReportSection { title: string; paragraphs: string[]; sources?: string[]; children?: ReportSection[] }
export function reviewSystemIssueLabel(issue: { affectedCodes: string[]; pageNumber?: number | null }): string {
  return issue.affectedCodes.join("、") || (issue.pageNumber ? `原件第 ${issue.pageNumber} 页` : "尚未关联条款的记录");
}
export const reviewEvidenceScopeNote = "本次审核仅依据本次已提供的资料及其核对结果。已知缺失和待核实事项另列；未提供的情况不作推断。";
export const reviewLimitationLabel = {
  interpretation_unresolved: "方案含义尚待澄清，不能判为符合或不符合",
  consumer_unavailable: "系统暂不能完成本项计算，不能判为符合或不符合",
};
export function reviewLimitationContext(item: ReviewHistoryRestrictedRequirementView): string[] {
  return [
    ...(item.scopeQuote ? [`适用范围原文：${item.scopeQuote}`] : []),
    ...item.timeWords.map((text) => `时间限定原文：${text}`),
    ...(item.exceptionWords ? [`例外原文：${item.exceptionWords}`] : []),
    ...(item.affectedStage ? [`涉及阶段：${item.affectedStage}`] : []),
  ];
}
const controlLabels = { fulfilled: "已满足", unfulfilled: "未满足", unverified: "尚无法判定", not_applicable: "本次不适用" };
const locatorText = (locator: LocatorView, fileName = "原始资料") => `${fileName} · 第 ${locator.pageNumber} 页 · ${locator.precisionLabel}：${locator.excerpt ?? "未保存文字摘录，请在系统中查看原件。"}`;
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
    return locatorText(locator, report.sourceFileNames?.[locator.sourceDocumentVersionId]);
  });
  const result: ReportSection[] = [{ title: "本次审核资料", paragraphs: [
    `研究项目：${context.projectName}`, `受试者：${context.subjectCode}`,
    `中心：${[context.centerCode, context.centerName].filter(Boolean).join(" · ") || "未登记"}`,
    `审核节点：${context.workflowStageLabel}`, `方案版本：${context.officialProtocolVersion}`,
    ...(context.nodeStartDate ? [`节点开始日：${context.nodeStartDate}`] : []),
    ...(context.evidenceCutoffDate || context.nodeStartDate
      ? [`本次资料截至：${context.evidenceCutoffDate ?? context.nodeStartDate}`] : []),
    `审核完成时间：${time(run.completedAt)}`, `导出时间：${time(exportedAt.toISOString())}`,
    reviewEvidenceScopeNote,
    report.workDraft ? "本工作稿保留当时的结果，尚未签发，不代替研究者最终入组决定。"
      : "本报告保留该次审核的结论，不代替研究者最终入组决定。办理情况截至本次读取报告时；事项关闭不改变原审核结论。",
    ...(report.workDraft?.verificationOnly ? ["本工作稿使用构建者审定的验证规则，不用于正式审核。"] : []),
    ...(report.restrictedRequirements.length ? ["方案仍有尚不能判定的要求，不能据此认为受试者符合全部要求。"] : []),
  ] }];
  if (report.workDraft) {
    const parents = [...report.workDraft.clauses].sort((a, b) =>
      ({ inclusion: 0, exclusion: 1, required_procedure: 2, medication: 3 })[a.ruleKind] - ({ inclusion: 0, exclusion: 1, required_procedure: 2, medication: 3 })[b.ruleKind]
        || a.ruleCode.localeCompare(b.ruleCode));
    for (const parent of parents) {
      const group: ReportSection[] = [];
      for (const item of [parent, ...(report.workDraft.componentClauses?.filter(child => child.parentRuleCode === parent.ruleCode) ?? [])]) {
        const sources = [
          ...((item === parent || item.sourceText !== parent.sourceText) ? [`方案要求：${item.sourceText ?? item.textSummary}`] : []),
          ...item.factRefs.map(ref => {
            const locator = report.evidenceLocators.find(position => position.locatorId === ref.locatorId);
            if (!locator) throw new Error("工作稿引用的原件位置不完整，请刷新后重试。");
            return `${report.sourceFileNames?.[locator.sourceDocumentVersionId] ?? "原始资料"} · 第 ${locator.pageNumber} 页：${ref.excerpt ?? "本处未保存文字摘录"}`;
          }),
          ...(item.sourceReadRefs ?? []).map(ref =>
            `${report.sourceFileNames?.[ref.sourceDocumentVersionId] ?? "原始资料"} · 第 ${ref.pageNumber} 页 · ${ref.disposition === "not_seen" ? "本页未见相关记录，不代表明确否认" : ref.disposition === "unresolved" ? "原文尚待核清" : "原文摘录"}：${ref.excerpt ?? "本处未保存文字摘录，请核对原件"}`),
        ];
        group.push({ title: `${item.ruleCode} · ${item.textSummary}`, paragraphs: [
          `审核结果：${item.decisionLabel}${item.confidence ? ` · ${item.confidence === "high" ? "高置信" : "低置信"}` : ""}${item.confirmationKind ? ` · ${item.confirmationKind === "medical_manager" ? "医学经理已核实" : "构建者试用核实，非正式医学核实"}` : ""}`,
          ...item.reason.split(/(?<=；)|(?<=。)|\n+/u).filter(part => part.trim() && part.trim() !== "；")
            .map((part, index) => `${index === 0 ? "判定依据：" : ""}${part}`),
        ], sources: [...new Set(sources)].filter(source => item === parent || !group[0].sources?.includes(source)) });
      }
      result.push({ ...group[0], children: group.slice(1) });
    }
    for (const group of [
      { title: "系统尚未完成的核对", issues: report.workDraft.systemIssues?.filter(issue => issue.kind !== "excerpt_unverified") ?? [] },
      { title: "尚未用于判断的原件记录", issues: report.workDraft.systemIssues?.filter(issue => issue.kind === "excerpt_unverified") ?? [] },
    ]) if (group.issues.length) result.push({ title: group.title, paragraphs: group.issues.flatMap(issue => [
      `${reviewSystemIssueLabel(issue)}：${issue.detail}`, issue.alternative]) });
  }
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
  for (const item of report.restrictedRequirements) {
    result.push({ title: `${item.displayLabel} · ${item.title}`, paragraphs: [
      reviewLimitationLabel[item.limitationKind],
      ...item.unresolvedDimensions,
      `方案原文：${item.sourceText}`,
      ...item.sourceExcerpts.map((text) => `依据摘录：${text}`),
      ...reviewLimitationContext(item),
      ...item.dependencyRefs.map((id) => {
        const dependency = report.restrictedRequirements.find((entry) => entry.requirementId === id);
        if (!dependency) throw new Error("报告中的相关方案要求未列明，请刷新后重试。");
        return `还需核清相关要求：${dependency.displayLabel} · ${dependency.title}`;
      }),
    ] });
  }
  if (!report.workDraft) result.push({ title: "补充资料与核实事项", paragraphs: report.actions.length ? report.actions.flatMap((action) => [
    `${action.clause?.ruleDisplayCode ?? action.control?.displayLabel ?? "对应要求未列明"}：${action.requestedAction}`,
    `应提供资料：${action.acceptableEvidence}`,
    `负责方及节点：${actionTargetLabel[action.targetParty]} · ${stageLabel[action.dueStage]}`,
    `办理情况：${actionStateLabel[action.state]}`,
    ...action.transitions.flatMap((transition) => [
      `${time(transition.occurredAt)} · ${actionStateLabel[transition.toState]}：${transition.reason}`,
      ...(transition.responseEvidence?.locators.map((locator) => `回应资料：${locatorText(locator)}`) ?? []),
    ]),
  ]) : [report.restrictedRequirements.length ? "方案仍有待澄清或暂不能计算的要求，详见上述内容；不能据此认为受试者符合全部要求。" : report.controls.some((item) => item.status === "unverified")
    ? "其他章节仍有尚无法判定的要求，详见对应核对情况；本次尚未保存对应办理事项。" : "本次审核未记录补充事项。"] });
  result.push({ title: "资料与版本", paragraphs: [
    `方案版本：${context.officialProtocolVersion} · 规则第 ${run.ruleSetRevision} 版`,
    "本文件包含已保存的文字摘录和原件页码，不包含原件附件。原始资料及精确标注请在系统中查看。",
  ] });
  return result;
}

const htmlText = (text: string) => text.replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]!);
const markdownText = (text: string) => htmlText(text).replace(/([\\`*_{}\[\]()#+.!|~-])/g, "\\$1").replace(/\r?\n/g, "  \n");

export function frozenReviewExport(report: ReviewHistoryRunDetailView, format: "md" | "html", exportedAt = new Date()): string {
  const content = sections(report, exportedAt);
  const title = `${report.workDraft ? "入排审核工作稿 · 未签发" : "入排审核报告"} · ${report.context.subjectCode} · ${report.context.workflowStageLabel}`;
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
    ...reports.map((report, index) => `${index + 1}. ${report.context.subjectCode} · ${report.context.workflowStageLabel} · ${time(report.run.completedAt!)}`),
  ] }];
  reports.forEach((report, index) => {
    const label = `${index + 1}. ${report.context.subjectCode} · ${report.context.workflowStageLabel}`;
    content.push(...reportSections[index].map((section) => ({ ...section, title: `${label} / ${section.title}` })));
  });
  return renderDocument("入排审核报告汇集", content, format);
}

function renderDocument(title: string, content: ReportSection[], format: "md" | "html"): string {
  const markdownSection = (section: ReportSection, level: number): string =>
    `${"#".repeat(level)} ${markdownText(section.title)}\n\n${[...section.paragraphs, ...(section.sources ?? [])].map(markdownText).join("\n\n")}${section.children?.length ? "\n\n" + section.children.map(child => markdownSection(child, level + 1)).join("\n\n") : ""}`;
  if (format === "md") return `# ${markdownText(title)}\n\n${content.map(section => markdownSection(section, 2)).join("\n\n")}\n`;
  const paragraph = (text: string) => {
    const colon = text.indexOf("：");
    return `<p>${colon > 0 && colon < 64 ? `<strong>${htmlText(text.slice(0, colon + 1))}</strong>${htmlText(text.slice(colon + 1))}` : htmlText(text)}</p>`;
  };
  const htmlSection = (section: ReportSection, level: number): string => `<section><h${level}>${htmlText(section.title)}</h${level}>${section.paragraphs.map(paragraph).join("")}${section.sources?.length ? `<details><summary>方案及原件依据</summary>${section.sources.map(paragraph).join("")}</details>` : ""}${section.children?.length ? `<details><summary>分项核对（${section.children.length}）</summary>${section.children.map(child => htmlSection(child, level + 1)).join("")}</details>` : ""}</section>`;
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>${htmlText(title)}</title><style>body{font-family:system-ui,"PingFang SC",sans-serif;color:#24312c;margin:3rem auto;padding:0 2rem;max-width:72rem;line-height:1.8}h1{font-size:1.75rem}h2{font-size:1.15rem;border-bottom:1px solid #d5ded9;padding-bottom:.5rem}h3{font-size:1rem}section{margin-block:2rem}details section{margin:1rem 0;padding-left:1rem}summary{cursor:pointer;font-weight:600}p{white-space:pre-wrap;overflow-wrap:anywhere;margin:.5rem 0}@media print{body{margin:0;max-width:none}h2,h3{break-after:avoid}p{orphans:3;widows:3}}</style><body><h1>${htmlText(title)}</h1>${content.map(section => htmlSection(section, 2)).join("")}<script>let folded=[];addEventListener("beforeprint",()=>{folded=[...document.querySelectorAll("details:not([open])")];folded.forEach(item=>{item.open=true})});addEventListener("afterprint",()=>{folded.forEach(item=>{item.open=false});folded=[]});</script></body></html>`;
}
