// @vitest-environment jsdom

import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getEvidenceRepository, type ProcessingRevisionPageView } from "../api/evidence";
import {
  setEligibilityReviewRepository,
  type EligibilityClauseView,
  type EligibilityReviewView,
} from "../api/eligibility-review";
import {
  buildEligibilityIssueGroups,
  EligibilityWorkbenchPage,
} from "./EligibilityWorkbenchPage";

const review: EligibilityReviewView = {
  subjectId: "subject-1",
  reviewEpisodeId: "episode-1",
  ruleSetId: "rule-set-1",
  ruleSetRevision: 3,
  evidenceSnapshotV2Id: "snapshot-1",
  completeProcessingRevisionId: "processing-1",
  clauses: [
    {
      ruleCode: "IN-01",
      ruleComponentId: "IN-01",
      ruleKind: "inclusion",
      textSummary: "目标人群符合方案要求",
      parentRuleCode: null,
      decision: "professional_judgment",
      decisionLabel: "无法判定",
      reason: "需要研究者结合资料确认。",
      factRefs: [
        { factId: "fact-1", excerpt: null, locatorId: null, pageNumber: null, sourceDocumentVersionId: null, pageArtifactId: null },
      ],
      gapType: "professional_judgment",
      determinationMode: "investigator_judgment",
      actionOwner: "investigator",
      actionDetail: "研究者针对本条要求作出并记录明确的临床判断。",
      actionEvidence: "具名、具日期并直接关联本条要求的研究者判断。",
    },
    {
      ruleCode: "IN-02",
      ruleComponentId: "IN-02",
      ruleKind: "inclusion",
      textSummary: "年龄处于方案范围",
      parentRuleCode: "IN-01",
      decision: "inclusion_met",
      decisionLabel: "符合入选标准",
      reason: "资料中的年龄满足方案要求。",
      factRefs: [],
      gapType: null,
      determinationMode: "deterministic",
      actionOwner: null,
      actionDetail: null,
      actionEvidence: null,
    },
    {
      ruleCode: "EX-01",
      ruleComponentId: "EX-01",
      ruleKind: "exclusion",
      textSummary: "排除既往治疗",
      parentRuleCode: null,
      decision: "exclusion_not_triggered",
      decisionLabel: "未触发排除标准",
      reason: "当前资料未见该排除条件。",
      factRefs: [],
      gapType: null,
      determinationMode: "semantic",
      actionOwner: null,
      actionDetail: null,
      actionEvidence: null,
    },
    {
      ruleCode: "REQ-01",
      ruleComponentId: "REQ-01",
      ruleKind: "required_procedure",
      textSummary: "完成必要检查",
      parentRuleCode: null,
      decision: "not_due",
      decisionLabel: "尚未到期",
      reason: "该流程要求对应的审核节点尚未到期。",
      factRefs: [],
      gapType: "future_stage_not_due",
      determinationMode: "deterministic",
      actionOwner: null,
      actionDetail: null,
      actionEvidence: null,
    },
  ],
};

beforeEach(() => {
  window.location.hash = "";
  setEligibilityReviewRepository({
    kind: "http",
    getEligibilityReview: async () => review,
  });
});

afterEach(() => vi.restoreAllMocks());

function installSourcePages() {
  const pages: ProcessingRevisionPageView[] = ["a", "b"].map((id, index) => ({
    entryId: `entry-${id}`, position: index + 1, sourceDocumentVersionId: `document-${id}`,
    pageNumber: 1, originalFrame: null, pageArtifactId: `page-${id}`, ocrPageId: null,
    status: "succeeded", statusLabel: "页面已就绪", failureReason: null, canOpen: true,
    imageAvailable: true, pageWidth: 1000, pageHeight: 1400,
  }));
  const repo = getEvidenceRepository();
  vi.spyOn(repo, "getProcessingRevision").mockResolvedValue({
    revisionId: "processing-1", revisionKind: "base", revisionKindLabel: "原始处理",
    evidenceSnapshotId: "snapshot-1", baseProcessingRevisionId: null, projectId: "project-1",
    subjectId: "subject-1", reviewEpisodeId: "episode-1", status: "active", statusLabel: "已完成",
    isActivatable: false, isCurrent: true, manifestSha256: "a".repeat(64), completionManifestSha256: "b".repeat(64),
    pages, riskFlagCount: 0, pendingRiskFlagCount: 0, locatorIds: [], riskScanIds: [], riskReviewIds: [],
    correctionIds: [], metadataRevisionIds: [], referencedDocumentRevisionIds: [], resolutionRevisionIds: [],
    gates: [], createdAt: "2026-09-13T00:00:00Z", createdBy: "test",
  });
  vi.spyOn(repo, "getEvidenceSnapshot").mockResolvedValue({
    evidenceSnapshotId: "snapshot-1", projectId: "project-1", subjectId: "subject-1",
    reviewEpisodeId: "episode-1", uploadMode: "full", uploadModeLabel: "全量资料",
    priorSnapshotId: null, comparisonSnapshotId: null, status: "active", statusLabel: "当前资料",
    isCurrent: true, baseProcessingRevisionId: "processing-1", uploadJobId: null,
    latestProcessingCandidate: null, collectionSha256: "c".repeat(64), createdAt: "2026-09-13T00:00:00Z",
    members: pages.map((page, index) => ({
      memberId: `member-${index}`, snapshotId: "snapshot-1", logicalDocumentId: `logical-${index}`,
      sourceDocumentVersionId: page.sourceDocumentVersionId, fileName: index === 0 ? "病历.pdf" : "检验报告.pdf",
      mediaType: "application/pdf", versionNumber: 1, origin: "uploaded", originLabel: "上传资料",
      metadataHead: { metadataRevisionId: `metadata-${index}`, sourceDocumentVersionId: page.sourceDocumentVersionId,
        documentType: "medical_record", sourceParty: "site", reason: "原始资料", isAutoSuggestion: false,
        supersedesMetadataRevisionId: null, revision: 1, createdAt: "2026-09-13T00:00:00Z", createdBy: "test" },
    })),
  });
  setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
    ...review, clauses: [{ ...review.clauses[0]!, factRefs: [{
      factId: "private-fact-id", excerpt: "检查结果见原件", locatorId: "locator-b", pageNumber: 1,
      sourceDocumentVersionId: "document-b", pageArtifactId: "page-b",
    }] }],
  }) });
}

describe("入排审核工作台", () => {
  it("单独提示未确定影响范围的争议，不改变条款并可打开同节点病史", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, unassignedConflicts: [{ conflictGroupId: "private-conflict", memberKind: "event", memberIds: ["private-a", "private-b"] }],
    }) });
    render(<EligibilityWorkbenchPage />);
    const reminder = await screen.findByRole("region", { name: "病史记录待核对" });
    expect(within(reminder).getByText("有 1 项病史或用药记录不一致，尚未确定影响哪些条款。")).toBeInTheDocument();
    const href = within(reminder).getByRole("link", { name: "查看病史中的不一致记录" }).getAttribute("href");
    expect(href).toContain("/profiles");
    const currentScopeHref = screen.getByRole("link", { name: /的资料页$/ }).getAttribute("href");
    expect(href?.split("?")[1]).toBe(currentScopeHref?.split("?")[1]);
    expect(screen.queryByText("private-conflict")).not.toBeInTheDocument();
    expect(screen.getByLabelText("无法判定 1 条")).toBeInTheDocument();
  });
  it("有缺口的条款详情显示责任方与建议动作", async () => {
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "入排审核工作台" });
    expect(screen.getByText("建议动作 · 研究者方")).toBeInTheDocument();
    expect(screen.getByText(/作出并记录明确的临床判断/)).toBeInTheDocument();
    expect(screen.getByText(/可接受证据：具名、具日期/)).toBeInTheDocument();
  });
  it("同页码跨文件定位准确，浏览相邻原件后可以返回所引原文", async () => {
    installSourcePages();
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    const reference = await screen.findByRole("button", { name: "检验报告.pdf 第 1 页" });
    expect(screen.queryByText("private-fact-id")).not.toBeInTheDocument();
    expect(screen.getAllByText("检查结果见原件")).toHaveLength(2);
    const adjacent = screen.getByRole("button", { name: "病历.pdf 第 1 页" });
    expect(reference).toHaveAttribute("aria-current", "page");
    expect(adjacent).not.toHaveAttribute("aria-current");
    await user.click(adjacent);
    expect(adjacent).toHaveAttribute("aria-current", "page");
    expect(reference).not.toHaveAttribute("aria-current");
    expect(screen.queryByLabelText(/^重点标注/)).not.toBeInTheDocument();
    const panel = screen.getByRole("complementary", { name: "原件面板" });
    await user.click(within(panel).getByRole("button", { name: "返回引用原文" }));
    expect(reference).toHaveAttribute("aria-current", "page");
    expect(adjacent).not.toHaveAttribute("aria-current");
  });
  it("同一官方编号的两个要点可独立选择并生成各自链接", async () => {
    const first = { ...review.clauses[0]!, ruleComponentId: "component-a", parentRuleCode: "IN-01", textSummary: "第一个审核要点" };
    const second = { ...first, ruleComponentId: "component-b", textSummary: "第二个审核要点" };
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review, clauses: [first, second] }) });
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "问题队列" });
    const clausePane = within(
      screen.getByRole("complementary", { name: "条款列表" }),
    )
      .getByRole("heading", { name: "审核条款" })
      .closest(".workbench-pane") as HTMLElement;
    const secondButton = await within(clausePane).findByRole("button", { name: /第二个审核要点/ });
    await user.click(secondButton);
    expect(secondButton).toHaveAttribute("aria-pressed", "true");
    expect(within(clausePane).getByRole("button", { name: /第一个审核要点/ })).toHaveAttribute("aria-pressed", "false");
    expect(window.location.hash).toContain("component=component-b");
    expect(secondButton.style.paddingInlineStart).toBe("calc(var(--space-2) + 1 * var(--space-3))");
    expect(within(clausePane).getByRole("button", { name: /第一个审核要点/ }).style.paddingInlineStart).toBe(secondButton.style.paddingInlineStart);
  });

  it("失效要点链接不会静默选中第一项", async () => {
    window.location.hash = "#/workbench?component=missing-component";
    render(<EligibilityWorkbenchPage />);
    expect(await screen.findByText("链接中的审核要点不存在，请重新选择。")).toBeInTheDocument();
  });

  it("展示项目、受试者、节点选择，分组条款并常显无法判定计数", async () => {
    render(<EligibilityWorkbenchPage />);
    expect(await screen.findByRole("heading", { name: "入排审核工作台" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "选择项目" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "选择受试者" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "选择审核节点" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "无法判定 1 条" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "入选标准" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "排除标准" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "流程要求" })).toBeInTheDocument();
    expect(screen.getAllByText("该事实未附页码定位").length).toBeGreaterThan(0);
  });

  it("按判定筛选条款并保留父子层级", async () => {
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "入排审核工作台" });
    const filter = screen.getByRole("combobox", { name: "按判定筛选" });
    await user.selectOptions(filter, "triggered");
    expect(screen.queryByRole("button", { name: /REQ-01/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /IN-02/ })).not.toBeInTheDocument();
    expect(screen.getByText("没有符合当前筛选条件的条款。")).toBeInTheDocument();
  });

  it("支持 component 深链直接打开对应条款详情", async () => {
    window.location.hash = "#/workbench?component=IN-02";
    render(<EligibilityWorkbenchPage />);
    expect(await screen.findByRole("heading", { name: /IN-02/ })).toBeInTheDocument();
  });

  it("问题队列只聚合风险/冲突/未决条款，已满足与未到期不进入队列", async () => {
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "问题队列" });
    expect(screen.getByText(/1 条条款需要处理，按根因聚合为 1 类/)).toBeInTheDocument();
    expect(screen.getByText("待研究者判断")).toBeInTheDocument();
    expect(screen.getByText("影响 1 条")).toBeInTheDocument();
    // 已满足/未触发/尚未到期的条款不属于问题。
    const queue = screen.getByRole("region", { name: "问题队列" });
    const queueText = within(queue).parentElement?.textContent ?? "";
    expect(queueText).not.toContain("IN-02");
    expect(queueText).not.toContain("EX-01");
    expect(queueText).not.toContain("REQ-01");
    expect(within(queue).getByRole("button", { name: /IN-01/ })).toBeInTheDocument();
  });

  it("点击问题队列中的条款会打开同一详情", async () => {
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "问题队列" });
    const queue = screen.getByRole("region", { name: "问题队列" });
    await user.click(within(queue).getByRole("button", { name: /IN-01/ }));
    expect(window.location.hash).toContain("component=IN-01");
  });

  describe("buildEligibilityIssueGroups", () => {
    const clause = (overrides: Partial<EligibilityClauseView>): EligibilityClauseView => ({
      ruleCode: "X-99",
      ruleComponentId: "X-99",
      ruleKind: "inclusion",
      textSummary: "测试条款",
      parentRuleCode: null,
      decision: "indeterminate",
      decisionLabel: "无法判定",
      reason: "测试",
      factRefs: [],
      gapType: null,
      determinationMode: "semantic",
      ...overrides,
    });

    it("按根因聚合、按严重度排序且全量保留", () => {
      const groups = buildEligibilityIssueGroups([
        clause({ ruleComponentId: "a", ruleCode: "IN-10", gapType: "observation_unverified" }),
        clause({ ruleComponentId: "b", ruleCode: "EX-05", decision: "conflict", gapType: "source_conflict" }),
        clause({ ruleComponentId: "c", ruleCode: "IN-11", gapType: "observation_unverified" }),
        clause({ ruleComponentId: "d", ruleCode: "IN-12", decision: "inclusion_met", gapType: null }),
        clause({ ruleComponentId: "e", ruleCode: "IN-13", decision: "not_due", gapType: "future_stage_not_due" }),
      ]);
      expect(groups.map((group) => group.key)).toEqual([
        "source_conflict",
        "observation_unverified",
      ]);
      expect(groups[0]!.clauses).toHaveLength(1);
      expect(groups[1]!.clauses.map((item) => item.ruleCode)).toEqual(["IN-10", "IN-11"]);
    });

    it("无缺口类型的未决条款回退到显式的待明确根因", () => {
      const groups = buildEligibilityIssueGroups([
        clause({ ruleComponentId: "f", decision: "indeterminate", gapType: null }),
      ]);
      expect(groups).toHaveLength(1);
      expect(groups[0]!.key).toBe("unclassified");
      expect(groups[0]!.label).toBe("原因待明确");
    });
  });
});
