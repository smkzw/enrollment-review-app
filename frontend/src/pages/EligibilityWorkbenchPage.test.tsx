// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import {
  setEligibilityReviewRepository,
  type EligibilityReviewView,
} from "../api/eligibility-review";
import { EligibilityWorkbenchPage } from "./EligibilityWorkbenchPage";

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
      ruleKind: "inclusion",
      textSummary: "目标人群符合方案要求",
      parentRuleCode: null,
      decision: "professional_judgment",
      decisionLabel: "无法判定",
      reason: "需要研究者结合资料确认。",
      factRefs: [
        { factId: "fact-1", locatorId: null, pageNumber: null },
      ],
      gapType: "professional_judgment",
      determinationMode: "investigator_judgment",
    },
    {
      ruleCode: "IN-02",
      ruleKind: "inclusion",
      textSummary: "年龄处于方案范围",
      parentRuleCode: "IN-01",
      decision: "inclusion_met",
      decisionLabel: "符合入选标准",
      reason: "资料中的年龄满足方案要求。",
      factRefs: [],
      gapType: null,
      determinationMode: "deterministic",
    },
    {
      ruleCode: "EX-01",
      ruleKind: "exclusion",
      textSummary: "排除既往治疗",
      parentRuleCode: null,
      decision: "exclusion_not_triggered",
      decisionLabel: "未触发排除标准",
      reason: "当前资料未见该排除条件。",
      factRefs: [],
      gapType: null,
      determinationMode: "semantic",
    },
    {
      ruleCode: "REQ-01",
      ruleKind: "required_procedure",
      textSummary: "完成必要检查",
      parentRuleCode: null,
      decision: "not_due",
      decisionLabel: "尚未到期",
      reason: "该流程要求对应的审核节点尚未到期。",
      factRefs: [],
      gapType: "future_stage_not_due",
      determinationMode: "deterministic",
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

describe("入排审核工作台", () => {
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
});
