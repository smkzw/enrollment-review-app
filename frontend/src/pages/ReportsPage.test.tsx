// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReviewHistoryRunDetailView } from "../api/review-history/reviewHistoryTypes";
import { ReportsPage } from "./ReportsPage";
import { frozenReviewExport } from "../domain/frozenReviewExport";

const mocks = vi.hoisted(() => ({ listRuns: vi.fn(), getRun: vi.fn(), canModify: true }));
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
  mocks.listRuns.mockReset().mockImplementation(async (subjectId: string, reviewEpisodeId: string) => ({
    subjectId, reviewEpisodeId, items: [frozenReport(subjectId, reviewEpisodeId).run],
  }));
  mocks.getRun.mockReset().mockImplementation(async (subjectId: string, reviewEpisodeId: string) => frozenReport(subjectId, reviewEpisodeId));
});

describe("报告", () => {
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
      expect(content).toContain("例外原文：特殊情况不适用");
      expect(content).toContain("涉及阶段：筛选期至治疗结束");
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
    expect(screen.getByText("冻结项目名称 · 方案 1.0")).toBeInTheDocument();
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
    await screen.findByText("该节点尚无正式审核记录。");
    expect(mocks.getRun).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "打印报告" })).not.toBeInTheDocument();
  });
});
