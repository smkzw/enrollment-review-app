// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReviewHistoryRunDetailView } from "../api/review-history/reviewHistoryTypes";
import { ReportsPage } from "./ReportsPage";
import { FrozenReviewReport } from "../components/review/FrozenReviewReport";
import { frozenReviewCollectionExport, frozenReviewExport } from "../domain/frozenReviewExport";
import { getCatalogRepository } from "../api";

const mocks = vi.hoisted(() => ({ listRuns: vi.fn(), getRun: vi.fn(), source: vi.fn(), canModify: true }));
vi.mock("../components/review/FrozenReviewEvidence", () => ({
  FrozenReviewEvidence: (props: import("react").ComponentProps<typeof import("../components/review/FrozenReviewEvidence").FrozenReviewEvidence>) => {
    mocks.source(props);
    return <section aria-label={props.title}><button onClick={props.onClose}>关闭待核原件</button></section>;
  },
}));
vi.mock("../api/review-history/reviewHistoryHttp", () => ({
  createReviewHistoryHttp: () => ({ listRuns: mocks.listRuns, getRun: mocks.getRun }),
}));
vi.mock("../app/applicationMode", () => ({
  useApplicationMode: () => ({ mode: mocks.canModify ? "standard" : "browse_only", canModify: mocks.canModify }),
}));
vi.mock("../components/review/PreparedReviewPanel", () => ({
  PreparedReviewPanel: () => <section aria-label="本次审核"><button>开始审核</button></section>,
}));

const longReason = "资料中的研究者记录需要结合审核节点要求进一步确认，完整原因应在打印报告中保留。";
const timestamp = "2026-09-16T00:00:00Z";
function frozenReport(subjectId: string, reviewEpisodeId: string): ReviewHistoryRunDetailView {
  const shared = {
    reviewRunId: "saved-run", contextId: "frozen-context", stage: "screening" as const,
    workflowStageId: null, episodeRevision: 1, protocolVersionId: "protocol-1",
    ruleSetId: "rules-1", ruleSetRevision: 1, evidenceSnapshotV2Id: "snapshot-1",
    completeProcessingRevisionId: "processing-1",
  };
  return {
    run: { ...shared, status: "completed", startedAt: timestamp, completedAt: timestamp, supersedesReviewRunId: null },
    context: { ...shared, subjectId, reviewEpisodeId, projectId: "project-1",
      createdAt: timestamp, evaluatorVersion: "frozen-version", ruleSetSha256: "a".repeat(64),
      clausePackSha256: "b".repeat(64), protocolIntegrityGateResultId: "gate-1",
      factCount: 0, expectationCount: 0, conflictGroupCount: 0, judgmentSearchCount: 0,
      subjectCode: "冻结受试者", projectName: "冻结项目名称", centerCode: "01", centerName: "冻结中心",
      officialProtocolVersion: "1.0", workflowStageLabel: "筛选期审核" },
    assessments: [{
      assessmentId: "assessment-1", clause: { ruleComponentId: "component-1", ruleCode: "IN-01",
        ruleDisplayCode: "入选标准1", ruleTitle: "原文要求", ruleKind: "inclusion",
        determinationMode: "investigator_judgment" },
      decision: "professional_judgment", gapTypes: ["professional_judgment"], blockingLevel: "blocking",
      usedFactIds: [], locatorIds: [], gateResultId: "gate-1", publicationFingerprint: "c".repeat(64),
      conditions: [{ predicateId: "predicate-1", conditionText: "原文条件", truth: "unknown",
        observedValue: null, observedUnit: null, factIds: [], locatorIds: [], reasonCodes: [],
        selectionNote: longReason, calculationBasis: [], notSelected: [], unverifiedEvidence: [] }],
    }, {
      assessmentId: "assessment-2", clause: { ruleComponentId: "component-2", ruleCode: "EX-01",
        ruleDisplayCode: "排除标准1", ruleTitle: "后续节点要求", ruleKind: "exclusion", determinationMode: "deterministic" },
      decision: "not_due", gapTypes: ["future_stage_not_due"], blockingLevel: "none",
      usedFactIds: [], locatorIds: [], gateResultId: "gate-2", publicationFingerprint: "d".repeat(64), conditions: [],
    }],
    actions: [], controls: [], controlSelectionRecords: [], restrictedRequirements: [], evidenceLocators: [],
    missingRuleComponentIds: [], missingProtocolControlIds: [],
  };
}

beforeEach(() => {
  window.location.hash = "";
  mocks.canModify = true;
  mocks.source.mockReset();
  mocks.listRuns.mockReset().mockImplementation(async (subjectId: string, reviewEpisodeId: string) => ({
    subjectId, reviewEpisodeId, items: [frozenReport(subjectId, reviewEpisodeId).run],
  }));
  mocks.getRun.mockReset().mockImplementation(async (subjectId: string, reviewEpisodeId: string) => frozenReport(subjectId, reviewEpisodeId));
});

describe("报告", () => {
  function workingReport(): ReviewHistoryRunDetailView {
    const report = frozenReport("subject-uat-01-clear", "episode-uat-01-screening-clear");
    report.run.runKind = "work_draft";
    report.assessments = [];
    report.workDraft = { subjectId: report.context.subjectId, reviewEpisodeId: report.context.reviewEpisodeId,
      ruleSetId: report.context.ruleSetId, ruleSetRevision: report.context.ruleSetRevision,
      evidenceSnapshotV2Id: report.context.evidenceSnapshotV2Id, completeProcessingRevisionId: report.context.completeProcessingRevisionId,
      reviewRunId: report.run.reviewRunId, clauses: [], controls: [], systemIssues: [] };
    return report;
  }

  it("历史待核记录可直接查看当时页面，不改成已采用证据；切换报告不带旧原件", async () => {
    const report = workingReport();
    report.workDraft!.systemIssues = [
      { kind: "extraction_failed", affectedCodes: [], detail: "检查页尚未读清", alternative: "查看检查原件",
        sourceDocumentVersionId: "old-exam", pageArtifactId: "old-exam-page", pageNumber: 2 },
      { kind: "excerpt_unverified", affectedCodes: [], detail: "用药记录尚未核清", alternative: "查看病历原件",
        sourceDocumentVersionId: "old-chart", pageArtifactId: "old-chart-page", pageNumber: 7 },
    ];
    const before = JSON.stringify(report);
    const user = userEvent.setup();
    const view = render(<FrozenReviewReport report={report} onActionChanged={vi.fn()} />);
    const pending = screen.getByText("尚未用于判断的原件记录（1）");
    await user.click(pending);
    await user.click(within(pending.closest("details")!).getByRole("button", { name: "查看待核原件" }));
    expect(mocks.source).toHaveBeenLastCalledWith(expect.objectContaining({ title: "当时的待核原件",
      context: report.context, locators: [], pageRefs: [{ sourceDocumentVersionId: "old-chart",
        pageArtifactId: "old-chart-page", pageNumber: 7, excerpt: null, disposition: "unresolved" }] }));
    await user.click(screen.getByRole("button", { name: "关闭待核原件" }));
    const failed = screen.getByText("系统尚未完成的核对（1）");
    await user.click(failed);
    await user.click(within(failed.closest("details")!).getByRole("button", { name: "查看待核原件" }));
    expect(mocks.source).toHaveBeenLastCalledWith(expect.objectContaining({
      pageRefs: [{ sourceDocumentVersionId: "old-exam", pageArtifactId: "old-exam-page",
        pageNumber: 2, excerpt: null, disposition: "unresolved" }] }));
    expect(JSON.stringify(report)).toBe(before);
    const newer = structuredClone(report);
    newer.run.reviewRunId = "new-run";
    newer.context = { ...newer.context, reviewRunId: "new-run", subjectId: "other-subject",
      evidenceSnapshotV2Id: "new-snapshot", completeProcessingRevisionId: "new-processing" };
    view.rerender(<FrozenReviewReport report={newer} onActionChanged={vi.fn()} />);
    expect(screen.queryByRole("region", { name: "当时的待核原件" })).not.toBeInTheDocument();
    expect(JSON.stringify(report)).toBe(before);
  });

  it.each(["sourceDocumentVersionId", "pageArtifactId", "pageNumber"] as const)("待核记录缺少%s时只显示问题，不猜原件", async field => {
    const report = workingReport();
    const issue = { kind: "excerpt_unverified", affectedCodes: [], detail: "原件尚待核实", alternative: "不猜来源",
      sourceDocumentVersionId: "document", pageArtifactId: "page", pageNumber: 1 };
    report.workDraft!.systemIssues = [{ ...issue, [field]: null }];
    const user = userEvent.setup();
    render(<FrozenReviewReport report={report} onActionChanged={vi.fn()} />);
    await user.click(screen.getByText("尚未用于判断的原件记录（1）"));
    expect(screen.getByText(/原件尚待核实/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "查看待核原件" })).not.toBeInTheDocument();
    expect(mocks.source).not.toHaveBeenCalled();
  });

  it("项目选择用代号、期别及版本，全名保留且项目绑定不变", async () => {
    const projects = await getCatalogRepository().listProjects(new AbortController().signal);
    render(<ReportsPage />);
    const select = await screen.findByRole("combobox", { name: "选择项目" }) as HTMLSelectElement;
    expect(select).toHaveValue(projects[0].projectId);
    expect(select).toHaveAttribute("title", projects[0].projectName);
    expect([...select.options].map(option => ({ value: option.value, label: option.text, title: option.title })))
      .toEqual(projects.map(project => ({ value: project.projectId,
        label: `${project.projectCode} · ${project.studyPhaseLabel} · 方案 ${project.officialVersion}`,
        title: project.projectName })));
  });
  it("报告与导出保留方案未决和计算限制，不改成病例缺失或合格", async () => {
    const report = frozenReport("subject-uat-01-clear", "episode-uat-01-screening-clear");
    report.restrictedRequirements = [{
      origin: "official", requirementId: "limited-official", displayLabel: "IN-02-b",
      title: "适用范围要求", sourceText: "适用范围需按相关定义核清。",
      sourceSpanIds: ["source-official"], sourceExcerpts: ["适用范围需按相关定义核清。"],
      scopeQuote: null, timeWords: [], exceptionWords: null, affectedStage: null,
      decisionFunctions: [], sourceForce: null, limitationKind: "interpretation_unresolved",
      unresolvedDimensions: ["该定义适用对象尚待澄清"], dependencyRefs: [],
    }, {
      origin: "control", requirementId: "limited-control", displayLabel: "方案补充要求",
      title: "连续期间计算", sourceText: "需核实连续期间。",
      sourceSpanIds: ["source-control"], sourceExcerpts: ["需核实连续期间。"],
      scopeQuote: "符合相应定义时", timeWords: ["筛选时"], exceptionWords: "特殊情况不适用",
      affectedStage: "筛选期至治疗结束", decisionFunctions: ["time_validity"],
      sourceForce: "prohibited", limitationKind: "consumer_unavailable",
      unresolvedDimensions: ["连续期间计算尚未支持"], dependencyRefs: [],
    }];
    const before = JSON.stringify(report);
    mocks.getRun.mockResolvedValue(report);
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "尚不能判定的方案要求（2）" });
    expect(screen.getByText("方案含义尚待澄清，不能判为符合或不符合")).toBeInTheDocument();
    expect(screen.getByText("系统暂不能完成本项计算，不能判为符合或不符合")).toBeInTheDocument();
    expect(screen.getByText("以下是方案含义或系统计算能力的限制，不等于病例缺少资料，也不能据此认为受试者符合全部要求。")).toBeInTheDocument();
    expect(screen.getByText("方案仍有待澄清或暂不能计算的要求，详见上表；不能据此认为受试者符合全部要求。")).toBeInTheDocument();
    for (const format of ["html", "md"] as const) {
      const content = frozenReviewExport(report, format, new Date(timestamp));
      expect(content).toContain("该定义适用对象尚待澄清");
      expect(content).toContain("连续期间计算尚未支持");
      expect(content).toContain("特殊情况不适用");
      const visible = format === "html" ? new DOMParser().parseFromString(content, "text/html").body.textContent : content;
      expect(visible).toContain("例外原文：特殊情况不适用");
      expect(visible).toContain("涉及阶段：筛选期至治疗结束");
      expect(content).not.toContain("time_validity");
      expect(content).not.toContain("prohibited");
      expect(content).not.toContain("本次审核未记录补充事项");
    }
    expect(JSON.stringify(report)).toBe(before);
    const reportWithAction: ReviewHistoryRunDetailView = {
      ...report,
      actions: [{
        actionId: "action-1", assessmentId: "assessment-1", clause: report.assessments[0].clause,
        control: null, gapType: "professional_judgment", targetParty: "investigator",
        requestedAction: "补充本节点的书面判断", acceptableEvidence: "对应节点病历分析",
        dueStage: "screening", blockingLevel: "blocking", state: "open",
        recomputeScope: ["component-1"], triggerLocatorId: null, recordRevision: 1,
        gateResultId: "gate-1", publicationFingerprint: "c".repeat(64), transitions: [],
      }],
    };
    const withActionBefore = JSON.stringify(reportWithAction);
    for (const format of ["html", "md"] as const) {
      const content = frozenReviewExport(reportWithAction, format, new Date(timestamp));
      expect(content).toContain("补充本节点的书面判断");
      expect(content).toContain("方案仍有尚不能判定的要求，不能据此认为受试者符合全部要求。");
      expect(content).toContain("连续期间计算尚未支持");
      expect(content).not.toContain("time_validity");
      expect(content).not.toContain("prohibited");
      expect(content).not.toContain("source-control");
      expect(content).not.toContain("source-official");
    }
    expect(JSON.stringify(reportWithAction)).toBe(withActionBefore);
  });

  it("读取保存的审核记录，显示冻结登记信息而非当前目录内容", async () => {
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "逐项审核结果" });
    expect(screen.getByRole("heading", { name: "冻结受试者 · 筛选期审核" })).toBeInTheDocument();
    expect(screen.getByText("方案 1.0 · 规则第 1 版")).toBeInTheDocument();
    expect(mocks.getRun).toHaveBeenCalledWith(expect.any(String), expect.any(String), "saved-run", expect.any(Object));
  });

  it("保留完整原因及后续节点条款，不重算保存的结论", async () => {
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "逐项审核结果" });
    expect(screen.getByText(longReason)).toBeInTheDocument();
    expect(screen.getByText("不在本节点到期")).toBeInTheDocument();
    expect(screen.getByText("待研究者判断")).toBeInTheDocument();
  });

  it("打印保存的报告，打印时展开核对详情后恢复", async () => {
    const user = userEvent.setup();
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "逐项审核结果" });
    await user.click(screen.getByRole("button", { name: "打印报告" }));
    expect(print).toHaveBeenCalledTimes(1);
    const details = document.querySelector(".reports-print details") as HTMLDetailsElement;
    expect(details.open).toBe(false);
    window.dispatchEvent(new Event("beforeprint"));
    expect(details.open).toBe(true);
    window.dispatchEvent(new Event("afterprint"));
    expect(details.open).toBe(false);
    print.mockRestore();
  });

  it("仅查看仍可读保存的报告，但不挂载审核操作区", async () => {
    mocks.canModify = false;
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "逐项审核结果" });
    expect(screen.queryByRole("button", { name: "开始审核" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "打印报告" })).toBeEnabled();
  });

  it("尚无保存记录时不以临时计算结果冒充正式报告", async () => {
    mocks.listRuns.mockImplementation(async (subjectId: string, reviewEpisodeId: string) => ({ subjectId, reviewEpisodeId, items: [] }));
    render(<ReportsPage />);
    await screen.findByText("该节点尚无审核记录。");
    expect(mocks.getRun).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "打印报告" })).not.toBeInTheDocument();
  });

  it.each([null, "builder_verification", "medical_manager"] as const)("历史工作稿只读保存结论和分项，保留核实身份（%s）", async confirmationKind => {
    const report = frozenReport("subject-uat-01-clear", "episode-uat-01-screening-clear");
    report.run.runKind = "work_draft";
    report.assessments = [];
    const clause = { ruleCode: "IN-01", ruleComponentId: "parent", ruleKind: "inclusion" as const,
      textSummary: "冻结要求标题", sourceText: "必须符合原文限定", parentRuleCode: null,
      decision: "inclusion_met" as const, confidence: confirmationKind ? "high" as const : "low" as const, confirmationKind,
      decisionLabel: "满足", reason: "已有支持。相关检查已核对。后续节点仍须另行审核。",
      factRefs: [], sourceReadRefs: [], gapType: null, determinationMode: "semantic" as const,
      actionOwner: null, actionDetail: null, actionEvidence: null };
    report.workDraft = { subjectId: report.context.subjectId, reviewEpisodeId: report.context.reviewEpisodeId,
      ruleSetId: report.context.ruleSetId, ruleSetRevision: report.context.ruleSetRevision,
      evidenceSnapshotV2Id: report.context.evidenceSnapshotV2Id, completeProcessingRevisionId: report.context.completeProcessingRevisionId,
      reviewRunId: report.run.reviewRunId, clauses: [clause], controls: [],
      componentClauses: [{ ...clause, ruleComponentId: "child", parentRuleCode: "IN-01", confidence: null, confirmationKind: null,
        decision: "not_due", decisionLabel: "未到期", reason: "基线期还未到，届时核对。" }],
      systemIssues: [{ kind: "model_output_invalid", affectedCodes: ["IN-01"], detail: "读取意见尚未一致", alternative: "原件保留，可继续核查" },
        { kind: "excerpt_unverified", affectedCodes: [], detail: "原件记录尚待核实", alternative: "不作阴性解释", pageNumber: 4 },
        { kind: "excerpt_unverified", affectedCodes: [], detail: "来源范围尚待核清", alternative: "不猜来源" }] };
    const quote = { sourceDocumentVersionId: "internal-document-id", pageArtifactId: "page-3", pageNumber: 3,
      excerpt: "同一检验读数。", disposition: "mentioned" as const };
    report.sourceFileNames = { "internal-document-id": "检验：报告.pdf" };
    report.workDraft.clauses[0].sourceReadRefs = [quote, quote];
    report.workDraft.componentClauses![0].sourceReadRefs = [quote, { ...quote, pageArtifactId: "page-4", pageNumber: 4 }];
    mocks.getRun.mockResolvedValue(report);
    mocks.listRuns.mockImplementation(async (subjectId: string, reviewEpisodeId: string) => ({ subjectId, reviewEpisodeId, items: [report.run] }));
    const before = JSON.stringify(report);
    const user = userEvent.setup();
    render(<ReportsPage />);
    await screen.findByText("入排审核工作稿 · 未签发");
    expect(screen.getByText("工作稿已保存，未签发")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "更新工作稿" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "保存日期" })).not.toBeInTheDocument();
    expect(screen.getByText(confirmationKind ? "高置信" : "低置信")).toBeInTheDocument();
    const marker = confirmationKind === "medical_manager" ? "医学经理已核实" : "构建者试用核实，非正式医学核实";
    if (confirmationKind) expect(screen.getByText(marker)).toBeInTheDocument();
    const protocolSource = screen.getByText("必须符合原文限定").closest("details")!;
    expect(protocolSource).not.toHaveAttribute("open");
    expect(protocolSource).toHaveClass("reports-print__protocol-source");
    await user.click(screen.getByText("分项核对（1）"));
    expect(screen.getByText("基线期还未到，届时核对。")).toBeVisible();
    window.dispatchEvent(new Event("beforeprint"));
    expect(screen.getByText("后续节点仍须另行审核。")).toBeVisible();
    expect(screen.getByText("基线期还未到，届时核对。")).toBeVisible();
    window.dispatchEvent(new Event("afterprint"));
    expect(protocolSource).not.toHaveAttribute("open");
    expect(screen.getByText("基线期还未到，届时核对。")).toBeVisible();
    expect(screen.getByText(/读取意见尚未一致/)).toBeInTheDocument();
    expect(screen.getByText("原件第 4 页")).toBeInTheDocument();
    expect(screen.getByText("尚未关联条款的记录")).toBeInTheDocument();
    expect(screen.queryByText("本次审核未记录补充事项。")).not.toBeInTheDocument();
    for (const format of ["html", "md"] as const) {
      const content = frozenReviewExport(report, format, new Date(timestamp));
      expect(content).toContain("未签发");
      if (confirmationKind) expect(content).toContain(marker);
      expect(content).toContain("基线期还未到");
      expect(content).toContain("读取意见尚未一致");
      expect(content).toContain("原件第 4 页");
      expect(content).toContain("尚未关联条款的记录");
      expect(content).toContain("后续节点仍须另行审核");
      expect(content).not.toContain("本次审核未记录补充事项");
      expect(content).not.toContain("saved-run");
      expect(content).not.toContain("snapshot-1");
      expect(content).not.toContain("processing-1");
      expect(content).not.toContain("internal-document-id");
      expect(content.match(/同一检验读数/g)).toHaveLength(2); // Same page folds; different pages remain distinct.
      if (format === "html") {
        const document = new DOMParser().parseFromString(content, "text/html");
        expect([...document.querySelectorAll("h2")].filter(h => h.textContent?.includes("IN-01"))).toHaveLength(1);
        expect(document.querySelectorAll("h3")).toHaveLength(1);
        const details = [...document.querySelectorAll("details")].find(node => node.querySelector("summary")?.textContent === "分项核对（1）");
        expect(details?.hasAttribute("open")).toBe(false);
        expect(details?.textContent).toContain("基线期还未到");
        expect(document.querySelector(".source-index")?.textContent).toContain("检验：报告.pdf · 第 3 页");
        expect(content).toContain("details:not([open]):not(.report-sources)");
        expect(content).toContain('addEventListener("beforeprint"');
        expect(content).toContain('addEventListener("afterprint"');
      } else {
        expect(content.split("\n").filter(line => line.startsWith("### "))).toHaveLength(1);
      }
    }
    expect(frozenReviewCollectionExport([report], "html", new Date(timestamp))).not.toContain("saved-run");
    expect(JSON.stringify(report)).toBe(before);
    const broken = structuredClone(report);
    broken.workDraft!.componentClauses![0].factRefs = [{ factId: "missing-fact", locatorId: "missing-locator",
      sourceDocumentVersionId: "internal-document-id", pageArtifactId: "page-4", pageNumber: 4, excerpt: "未知出处" }];
    expect(() => frozenReviewExport(broken, "html", new Date(timestamp))).toThrow("工作稿引用的原件位置不完整");
  });
});
