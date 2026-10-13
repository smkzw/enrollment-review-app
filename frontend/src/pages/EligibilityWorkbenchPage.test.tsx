// @vitest-environment jsdom

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getEvidenceRepository, type ProcessingRevisionPageView } from "../api/evidence";
import { getCatalogRepository } from "../api/catalog";
import {
  EligibilityReviewApiError,
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
  controls: [],
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
      mediaType: "application/pdf", versionNumber: 1, uploadedBy: "test", origin: "uploaded", originLabel: "上传资料",
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
  it("审核方式更新后旧条目链接不遮住更新入口，不把旧条目猜映到新结果", async () => {
    window.location.hash = "#/workbench?component=retired-result";
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, workDraftState: "method_changed", reviewRunId: null,
    }) });
    render(<EligibilityWorkbenchPage />);
    await screen.findByLabelText("审核方式已更新");
    expect(screen.queryByText("链接中的审核要点不存在，请重新选择。")).not.toBeInTheDocument();
    expect(window.location.hash).toContain("component=retired-result");
    expect(screen.getByText("工作稿操作与节点日期")).toBeInTheDocument();
  });
  it("整组尚未核清时不把整段综合说明误标成具体缺失依据", async () => {
    const first = review.clauses[0]!;
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      clauses: [first], componentClauses: [{ ...first, ruleComponentId: "compound", parentRuleCode: first.ruleCode }],
    }) });
    render(<EligibilityWorkbenchPage />);
    await screen.findByText("判定依据");
    expect(screen.queryByText("尚缺的依据")).not.toBeInTheDocument();
  });
  it("未决汇总先显示具体缺口，完整理由可展开，选择子项时不带兄弟理由", async () => {
    const first = review.clauses[0]!;
    const missing = { ...first, ruleComponentId: "missing", parentRuleCode: first.ruleCode,
      decision: "indeterminate" as const, decisionLabel: "证据不足", reason: "同次治疗的疗效尚无对应依据。" };
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      clauses: [{ ...first, decision: "indeterminate", reason: "已核对治疗史。还需核对应疗效。" }],
      componentClauses: [missing, { ...missing, ruleComponentId: "met", decision: "inclusion_met",
        decisionLabel: "满足", reason: "已有记录支持治疗史。" }],
    }) });
    render(<EligibilityWorkbenchPage />);
    await screen.findByText("尚缺的依据");
    const summary = screen.getByText("完整汇总说明");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(summary);
    expect(summary.closest("details")).toHaveAttribute("open");
    await userEvent.click(screen.getByText("逐项条件与依据"));
    await userEvent.click(screen.getByRole("button", { name: /目标人群符合方案要求 · 证据不足/ }));
    expect(screen.queryByText("尚缺的依据")).not.toBeInTheDocument();
    expect(screen.queryByText("完整汇总说明")).not.toBeInTheDocument();
  });
  it("规则更新导致读取拒绝时，可由用户更新工作稿，不自动调用或沿用旧结果链接", async () => {
    localStorage.clear();
    const catalog = getCatalogRepository();
    const projects = await catalog.listProjects();
    const subjects = await catalog.listSubjects(projects[0]!.projectId);
    const episodes = await catalog.listEpisodes(subjects[0]!.subjectId);
    const episode = { ...episodes[0]!, activeEvidenceProcessingRevisionId: "processing-1" };
    vi.spyOn(catalog, "listProjects").mockResolvedValue([{ ...projects[0]!, ruleSetRevision: 2 }]);
    vi.spyOn(catalog, "listEpisodes").mockResolvedValue([episode]);
    window.location.hash = `#/workbench?component=old-result&episode=${episode.reviewEpisodeId}`;
    let updated = false;
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => {
      if (!updated) throw new EligibilityReviewApiError("SCOPE_VIOLATION", "读取失败",
        "本节点的方案版本与现行已发布规则不同", "请核对方案。", 409);
      return review;
    } });
    const fetched = vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, options) => {
      if (options?.method === "POST") updated = true;
      return new Response(JSON.stringify({ job_id: "new-job", state: "completed", review_run_id: "new-result" }));
    });
    render(<EligibilityWorkbenchPage />);
    const action = await screen.findByRole("button", { name: "开始审核" });
    expect(fetched).not.toHaveBeenCalled();
    expect(screen.getByText("本节点尚未使用最新规则包，旧版工作稿保留。")).toBeInTheDocument();
    await userEvent.click(action);
    await screen.findByLabelText("审核要点列表");
    expect(window.location.hash).not.toContain("old-result");
    expect(fetched.mock.calls[0]![0]).toBe(`/api/v2/subjects/${episode.subjectId}/review-episodes/${episode.reviewEpisodeId}/work-draft-jobs`);
    expect(fetched.mock.calls[0]![1]?.method).toBe("POST");
    localStorage.clear();
  });

  it("同版规则下的来源错误不显示规则更新入口", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => {
      throw new EligibilityReviewApiError("SCOPE_VIOLATION", "读取失败", "文件哈希不符", "请核对原件。", 409);
    } });
    const fetched = vi.spyOn(globalThis, "fetch");
    render(<EligibilityWorkbenchPage />);
    await screen.findByText("文件哈希不符");
    expect(screen.queryByLabelText("采用已发布的新规则")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "开始审核" })).not.toBeInTheDocument();
    expect(fetched).not.toHaveBeenCalled();
  });

  it("未见记录的检索范围默认收起，仍可展开回到每页原件", async () => {
    installSourcePages();
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      clauses: [{ ...review.clauses[0]!, sourceReadRefs: [{
        sourceDocumentVersionId: "document-b", pageArtifactId: "page-b", pageNumber: 1,
        excerpt: null, disposition: "not_seen",
      }] }],
    }) });
    render(<EligibilityWorkbenchPage />);
    const summary = await screen.findByText("已核对 1 页，未见相关记录 · 查看范围");
    expect(summary.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(summary);
    const reference = screen.getByRole("button", { name: /本页未见相关记录/ });
    await userEvent.click(reference);
    expect(within(screen.getByLabelText("原始资料查看区"))
      .getByRole("button", { name: "检验报告.pdf 第 1 页" })).toHaveAttribute("aria-current", "page");
  });
  it("未采用原件记录与系统故障分别计数，均保留内容及回源入口", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      systemIssues: [
        { kind: "excerpt_unverified", affectedCodes: [], detail: "这处记录尚未核实。", alternative: "原件保留。",
          pageArtifactId: "original-page", pageNumber: 4 },
        { kind: "component_unstructured", affectedCodes: ["EX-01"], detail: "当前条件暂不能完整核对。", alternative: "请查看方案原文。" },
        { kind: "model_output_invalid", affectedCodes: ["IN-02"], detail: "本条病历核对未完成。", alternative: "保留其他结果。" },
      ],
    }) });
    render(<EligibilityWorkbenchPage />);
    const technical = await screen.findByLabelText("系统问题");
    const records = screen.getByLabelText("尚未用于判断的原件记录");
    expect(within(technical).getByText("系统问题（2）")).toBeInTheDocument();
    expect(within(records).getByText("尚未用于判断的原件记录（1）")).toBeInTheDocument();
    expect(technical).not.toHaveAttribute("open");
    expect(records).not.toHaveAttribute("open");
    await userEvent.click(within(records).getByText("尚未用于判断的原件记录（1）"));
    expect(within(records).getByText(/这处记录尚未核实/)).toBeVisible();
    expect(within(records).getByRole("link", { name: "查看相关原件第4页" })).toHaveAttribute("href", expect.stringContaining("sourcePage=original-page"));
    await userEvent.click(within(technical).getByText("系统问题（2）"));
    expect(within(technical).getByText(/当前条件暂不能完整核对/)).toBeVisible();
    expect(within(technical).getByText(/本条病历核对未完成/)).toBeVisible();
  });
  it("已核病历依据可回源但不伪装成已发布事实", async () => {
    installSourcePages();
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      clauses: [{ ...review.clauses[0]!, decision: "exclusion_not_triggered", decisionLabel: "未触发",
        confidence: "low", determinationMode: "semantic", factRefs: [], sourceReadRefs: [{
          sourceDocumentVersionId: "document-b", pageArtifactId: "page-b", pageNumber: 1,
          excerpt: "病历明确否认相关事件", disposition: "mentioned",
        }] }],
    }) });
    render(<EligibilityWorkbenchPage />);
    await userEvent.click(await screen.findByText("病历依据与核对范围（1）"));
    const button = await screen.findByRole("button", { name: /本次判断的病历依据/ });
    await userEvent.click(button);
    expect(screen.queryByText("当前条款没有已采用事实，可浏览全部原件页核实。")).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("原始资料查看区"))
      .getByRole("button", { name: "检验报告.pdf 第 1 页" })).toHaveAttribute("aria-current", "page");
  });
  it("不适用无需置信等级，已核人群依据仍可回源且不显示成待核", async () => {
    installSourcePages();
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      clauses: [{ ...review.clauses[0]!, decision: "not_applicable", decisionLabel: "不适用",
        confidence: null, determinationMode: "semantic", factRefs: [], sourceReadRefs: [{
          sourceDocumentVersionId: "document-b", pageArtifactId: "page-b", pageNumber: 1,
          excerpt: "本节点病历明确记录适用人群", disposition: "mentioned",
        }] }],
    }) });
    render(<EligibilityWorkbenchPage />);
    await userEvent.click(await screen.findByRole("button", { name: "全部条款" }));
    await userEvent.click(await screen.findByText("病历依据与核对范围（1）"));
    await userEvent.click(await screen.findByRole("button", { name: /本次判断的病历依据/ }));
    expect(screen.queryByText("当前条款没有已采用事实，可浏览全部原件页核实。")).not.toBeInTheDocument();
    expect(screen.queryByText("已找到相关原文，待核清")).not.toBeInTheDocument();
    expect(within(screen.getByLabelText("原始资料查看区"))
      .getByRole("button", { name: "检验报告.pdf 第 1 页" })).toHaveAttribute("aria-current", "page");
  });
  it("检索发现可打开正确原件但不会显示成已采用事实", async () => {
    installSourcePages();
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      clauses: [{ ...review.clauses[0]!, factRefs: [], sourceReadRefs: [{
        sourceDocumentVersionId: "document-b", pageArtifactId: "page-b", pageNumber: 1,
        excerpt: "既往事件日期不详", disposition: "mentioned",
      }] }],
    }) });
    render(<EligibilityWorkbenchPage />);
    await userEvent.click(await screen.findByText("病历依据与核对范围（1）"));
    const button = await screen.findByRole("button", { name: /已找到相关原文，待核清/ });
    await userEvent.click(button);
    expect(await screen.findByText("当前条款没有已采用事实，可浏览全部原件页核实。")).toBeInTheDocument();
    expect(within(screen.getByLabelText("原始资料查看区"))
      .getByRole("button", { name: "检验报告.pdf 第 1 页" })).toHaveAttribute("aria-current", "page");
  });
  it("低置信只留标记，理由分点但不改数值否定；收起列表后保留当前对象和原件", async () => {
    const reason = "检验结果：1.2 mmol/L，未超过界值；研究者判断：尚无明确记载。";
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review,
      clauses: [{ ...review.clauses[0]!, confidence: "low", confidenceReason: "重复的低置信长说明", reason }],
    }) });
    render(<EligibilityWorkbenchPage />);
    const detail = await screen.findByLabelText("审核要点详情");
    expect(within(detail).getByText("低置信")).toHaveAttribute("title", "重复的低置信长说明");
    expect(within(detail).queryByText("重复的低置信长说明")).not.toBeInTheDocument();
    const reasons = detail.querySelector(".eligibility-reason-lines");
    expect(reasons?.children).toHaveLength(2);
    expect(reasons?.textContent).toBe(reason);
    await userEvent.click(screen.getByRole("button", { name: "收起条款列表" }));
    expect(screen.queryByLabelText("审核要点列表")).not.toBeInTheDocument();
    expect(detail).toBeInTheDocument();
    expect(screen.getByLabelText("原件面板")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "显示条款列表" }));
    expect(screen.getByLabelText("审核要点列表")).toBeInTheDocument();
  });
  it("核对方法未支持时显示处理方向，不要求研究者替软件作判断", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, clauses: [{ ...review.clauses[0]!, determinationMode: "restricted",
        limitationKind: "consumer_unavailable", decision: "indeterminate", gapType: null,
        factRefs: [], actionOwner: null, actionDetail: "完善这项要求的核对方法。",
        actionEvidence: "已核实的方法与方案来源。",
      }],
    }) });
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "入排审核工作台" });
    expect(screen.getByText("处理方向")).toBeInTheDocument();
    expect(screen.getByText("完善这项要求的核对方法。")).toBeInTheDocument();
    expect(screen.queryByText("建议动作 · 研究者方")).not.toBeInTheDocument();
  });
  it("资料更正后说明旧工作稿失效并回到同一节点重新审核", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, workDraftState: "source_changed",
    }) });
    render(<EligibilityWorkbenchPage />);
    const reminder = await screen.findByRole("status", { name: "审核资料已变化" });
    expect(within(reminder).getByText(/先前的审核工作稿不再适用于本次资料/)).toBeInTheDocument();
    const href = within(reminder).getByRole("link", { name: "前往重新审核" }).getAttribute("href");
    expect(href).toContain("/reports");
    const sourceHref = screen.getByRole("link", { name: /的资料页$/ }).getAttribute("href");
    expect(href?.split("?")[1]).toBe(sourceHref?.split("?")[1]);
  });
  it("核对方法更新不假称资料更正，保留原稿并回到同一节点重新准备", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, workDraftState: "method_changed",
    }) });
    render(<EligibilityWorkbenchPage />);
    const reminder = await screen.findByRole("status", { name: "审核方式已更新" });
    expect(within(reminder).getByText(/先前的工作稿仍保留.*未按当前方式核对/)).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "审核资料已变化" })).not.toBeInTheDocument();
    const href = within(reminder).getByRole("link", { name: "前往重新审核" }).getAttribute("href");
    expect(href).toContain("/reports");
    const sourceHref = screen.getByRole("link", { name: /的资料页$/ }).getAttribute("href");
    expect(href?.split("?")[1]).toBe(sourceHref?.split("?")[1]);
  });
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
    expect(screen.getByLabelText("无法判定 1 项")).toBeInTheDocument();
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
    expect(panel.querySelector(".eligibility-evidence__excerpt")).toBeNull();
    await user.click(within(panel).getByRole("button", { name: "返回本条依据页" }));
    expect(reference).toHaveAttribute("aria-current", "page");
    expect(adjacent).not.toHaveAttribute("aria-current");
    expect(panel.querySelector(".eligibility-evidence__excerpt")).toHaveTextContent("检查结果见原件");
  });
  it("同一官方编号的两个要点可独立选择并生成各自链接", async () => {
    const first = { ...review.clauses[0]!, ruleComponentId: "component-a", parentRuleCode: "IN-01", textSummary: "第一个审核要点" };
    const second = { ...first, ruleComponentId: "component-b", textSummary: "第二个审核要点" };
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({ ...review, clauses: [first, second] }) });
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "待处理要点" });
    await user.click(screen.getByRole("button", { name: "全部条款" }));
    const clausePane = screen.getByRole("complementary", { name: "审核要点列表" });
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
    expect(screen.getByRole("status", { name: "无法判定 1 项" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "全部条款" }));
    expect(screen.getByRole("heading", { name: "入选标准" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "排除标准" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "流程要求" })).toBeInTheDocument();
    expect(screen.getAllByText("该事实未附页码定位").length).toBeGreaterThan(0);
  });

  it("按判定筛选条款并保留父子层级", async () => {
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "入排审核工作台" });
    await user.click(screen.getByRole("button", { name: "全部条款" }));
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
    await screen.findByRole("heading", { name: "待处理要点" });
    expect(screen.getByText(/1 条条款需要处理，按问题类型归为 1 类/)).toBeInTheDocument();
    expect(screen.getByText("待研究者判断")).toBeInTheDocument();
    expect(screen.getByText("影响 1 条")).toBeInTheDocument();
    // 已满足/未触发/尚未到期的条款不属于问题。
    const queue = screen.getByRole("region", { name: "问题队列" });
    const queueText = queue.textContent ?? "";
    expect(queueText).not.toContain("IN-02");
    expect(queueText).not.toContain("EX-01");
    expect(queueText).not.toContain("REQ-01");
    expect(within(queue).getByRole("button", { name: /IN-01/ })).toBeInTheDocument();
  });

  it("点击问题队列中的条款会打开同一详情", async () => {
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "待处理要点" });
    const queue = screen.getByRole("region", { name: "问题队列" });
    await user.click(within(queue).getByRole("button", { name: /IN-01/ }));
    expect(window.location.hash).toContain("component=IN-01");
  });

  it("跨章节要求单列且可打开真实关联原件，不冒充入排编号", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, clauses: [], controls: [{
        protocolControlId: "control-1", displayLabel: "合并用药限制", title: "筛选期用药核对",
        sourceSpanIds: ["span-1"], obligations: [{
          obligationId: "obligation-1", obligationGroupId: "group-1",
          statement: "核对合并用药原始记录", sourceExcerpts: ["筛选期不得调整背景治疗剂量。"], status: "unverified",
          statusLabel: "无法判定", reason: "用药记录尚未核实", factRefs: [],
          continuingNote: "治疗期间：不得调整背景治疗。本次入排审核不判定后续期间是否已遵守。",
        }],
      }],
    }) });
    render(<EligibilityWorkbenchPage />);
    expect((await screen.findAllByText("筛选期用药核对")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("方案补充要求").length).toBeGreaterThan(0);
    expect(screen.queryByText(/IN-\d/)).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "全部条款" }));
    expect(screen.getByRole("heading", { name: "方案补充要求" })).toBeInTheDocument();
    expect(screen.getByText("核对合并用药原始记录")).toBeInTheDocument();
    expect(screen.getByText("系统解构的审核要求")).toBeInTheDocument();
    expect(screen.getByText("查看方案原文摘录")).toBeInTheDocument();
    expect(screen.getByText("筛选期不得调整背景治疗剂量。")).toBeInTheDocument();
    expect(screen.getByText(/本次入排审核不判定后续期间是否已遵守/)).toBeInTheDocument();
  });

  it("方案含义待澄清的跨章要求列为未决并显示责任方", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, clauses: [], controls: [{
        protocolControlId: "restricted:unit-1", displayLabel: "方案补充要求",
        title: "基线前要求", sourceSpanIds: ["span-1"],
        obligations: [{
          obligationId: "restricted:unit-1", obligationGroupId: "restricted",
          statement: "基线前待确认事项", sourceExcerpts: ["基线前待确认事项"],
          status: "restricted", statusLabel: "方案待澄清",
          reason: "方案所指事项尚未核清。", factRefs: [],
          actionOwner: "sponsor_medical_or_project",
          actionDetail: "请澄清适用范围", actionEvidence: "方案书面澄清或正式修订",
        }],
      }],
    }) });
    render(<EligibilityWorkbenchPage />);
    expect((await screen.findAllByText("基线前要求")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("方案待澄清").length).toBeGreaterThan(0);
    expect(screen.getByText("请澄清适用范围")).toBeInTheDocument();
  });

  it("官方条款已满足但补充要求未满足时仍列入待处理", async () => {
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review,
      clauses: [review.clauses[1]!],
      controls: [{
        protocolControlId: "control-2", displayLabel: "其他章节要求", title: "基线前资料核对",
        sourceSpanIds: ["span-2"], obligations: [{
          obligationId: "obligation-2", obligationGroupId: "group-2",
          statement: "尚未完成必须的核对", sourceExcerpts: [], status: "unfulfilled",
          statusLabel: "尚未满足", reason: "缺少本节点要求的资料", factRefs: [],
        }],
      }],
    }) });
    render(<EligibilityWorkbenchPage />);
    const queue = await screen.findByRole("region", { name: "问题队列" });
    expect(within(queue).getByRole("button", { name: /基线前资料核对/ })).toBeInTheDocument();
    expect(within(queue).queryByText(/IN-02/)).not.toBeInTheDocument();
    expect(screen.getByText("尚未完成必须的核对")).toBeInTheDocument();
    expect(screen.queryByText("查看方案原文摘录")).not.toBeInTheDocument();
    expect(screen.getByText("方案原文定位待补齐，请核对方案版本及条款来源。")).toBeInTheDocument();
  });

  it("101项审核要点可翻页且空筛选不显示无关详情", async () => {
    const clauses = Array.from({ length: 101 }, (_, index) => ({
      ...review.clauses[1]!, ruleComponentId: `item-${index + 1}`,
      ruleCode: `IN-${index + 1}`, textSummary: `审核要点${index + 1}`,
    }));
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, clauses,
    }) });
    const user = userEvent.setup();
    render(<EligibilityWorkbenchPage />);
    await screen.findByRole("heading", { name: "待处理要点" });
    await user.click(screen.getByRole("button", { name: "全部条款" }));
    const pane = screen.getByRole("complementary", { name: "审核要点列表" });
    expect(within(pane).getByText("第 1 / 3 页")).toBeInTheDocument();
    await user.click(within(pane).getByRole("button", { name: "下一页" }));
    expect(within(pane).getByText("第 2 / 3 页")).toBeInTheDocument();
    await user.click(within(pane).getByRole("button", { name: "下一页" }));
    expect(within(pane).getByText("第 3 / 3 页")).toBeInTheDocument();
    expect(within(pane).getByRole("button", { name: /审核要点101/ })).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "按判定筛选" }), "triggered");
    expect(screen.getByText("当前筛选没有符合条件的审核要点。")).toBeInTheDocument();
    expect(screen.queryByText("年龄处于方案范围")).not.toBeInTheDocument();
  });

  it("250项时深链定位末尾要点，分页和详情指向同一项", async () => {
    const clauses = Array.from({ length: 250 }, (_, index) => ({
      ...review.clauses[1]!, ruleComponentId: `item-${index + 1}`,
      ruleCode: `IN-${index + 1}`, textSummary: `审核要点${index + 1}`,
    }));
    window.location.hash = "#/workbench?component=item-250";
    setEligibilityReviewRepository({ kind: "http", getEligibilityReview: async () => ({
      ...review, clauses,
    }) });
    render(<EligibilityWorkbenchPage />);
    const pane = await screen.findByRole("complementary", { name: "审核要点列表" });
    expect(within(pane).getByText("第 5 / 5 页")).toBeInTheDocument();
    expect(within(pane).getByRole("button", { name: /审核要点250/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("heading", { name: /IN-250/ })).toBeInTheDocument();
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
      actionOwner: null,
      actionDetail: null,
      actionEvidence: null,
      ...overrides,
    });

    it("低置信确定结果留在待处理，高置信正常结果不增加卡片", () => {
      const groups = buildEligibilityIssueGroups([
        clause({ ruleComponentId: "low", decision: "inclusion_met", confidence: "low", confidenceReason: "日期需核对" }),
        clause({ ruleComponentId: "high", decision: "inclusion_met", confidence: "high" }),
      ]);
      expect(groups).toHaveLength(1);
      expect(groups[0]!.label).toBe("依据仍需核对");
      expect(groups[0]!.clauses.map(item => item.ruleComponentId)).toEqual(["low"]);
    });

    it("大量低置信正常项不遮住风险与真正未决，全部项目仍保留", () => {
      const normal = Array.from({ length: 35 }, (_, index) => clause({
        ruleComponentId: `normal-${index}`, decision: "exclusion_not_triggered", confidence: "low",
      }));
      const groups = buildEligibilityIssueGroups([...normal,
        clause({ ruleComponentId: "missing", gapType: "observation_unverified" }),
        clause({ ruleComponentId: "conflict", decision: "conflict", gapType: "source_conflict" }),
        clause({ ruleComponentId: "restricted", determinationMode: "restricted", limitationKind: "interpretation_unresolved" }),
      ]);
      expect(groups.map(group => group.key)).toEqual([
        "source_conflict", "protocol_meaning_unresolved", "observation_unverified", "low_confidence",
      ]);
      expect(groups.reduce((count, group) => count + group.clauses.length, 0)).toBe(38);
      expect(groups.at(-1)?.clauses).toHaveLength(35);
      expect(normal.every(item => item.confidence === "low" && item.decision === "exclusion_not_triggered")).toBe(true);
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

    it("方案含义待核不会混入病历缺失或研究者判断", () => {
      const groups = buildEligibilityIssueGroups([
        clause({ ruleComponentId: "r", ruleCode: "IN-08",
          determinationMode: "restricted", limitationKind: "interpretation_unresolved", gapType: null }),
      ]);
      expect(groups).toHaveLength(1);
      expect(groups[0]!.key).toBe("protocol_meaning_unresolved");
      expect(groups[0]!.label).toBe("方案要求尚待核清");
    });

    it("软件核对能力不足不被转给研究者澄清方案，旧缺字段结果也不猜原因", () => {
      const groups = buildEligibilityIssueGroups([
        clause({ ruleComponentId: "unsupported", determinationMode: "restricted",
          limitationKind: "consumer_unavailable", gapType: null }),
        clause({ ruleComponentId: "legacy", determinationMode: "restricted", gapType: null }),
      ]);
      expect(Object.fromEntries(groups.map((group) => [group.key, group.label]))).toEqual({
        review_method_unavailable: "审核方法待完善",
        protocol_requirement_unresolved: "本项暂不能判定",
      });
    });
  });
});
