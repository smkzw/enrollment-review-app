// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  setEligibilityReviewRepository,
  type EligibilityReviewView,
} from "../api/eligibility-review";
import { ReportsPage } from "./ReportsPage";

const longReason = "资料中的研究者记录需要结合审核节点要求进一步确认，完整原因应在打印报告中保留。";

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
      textSummary: "符合目标人群要求",
      parentRuleCode: null,
      decision: "professional_judgment",
      decisionLabel: "无法判定",
      reason: longReason,
      factRefs: [],
      gapType: "professional_judgment",
      determinationMode: "investigator_judgment",
    },
    {
      ruleCode: "EX-01",
      ruleKind: "exclusion",
      textSummary: "排除既往治疗",
      parentRuleCode: null,
      decision: "not_due",
      decisionLabel: "尚未到期",
      reason: "该条款对应的审核节点尚未到期。",
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

describe("报告", () => {
  it("按受试者信息、无法判定清单、逐条判定和脚注顺序渲染", async () => {
    render(<ReportsPage />);
    expect(await screen.findByRole("heading", { name: "报告" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "逐条判定" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "受试者信息" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /无法判定清单/ })).toBeInTheDocument();
    expect(screen.getByText(/资料版本：第/)).toBeInTheDocument();
    const sections = [...document.querySelectorAll(".reports-print__section h3")].map(
      (heading) => heading.textContent?.replace(/\s+/g, " ").trim(),
    );
    expect(sections).toEqual(["受试者信息", "无法判定清单 1", "逐条判定"]);
  });

  it("保留完整原因并把尚未到期条款列入逐条判定表", async () => {
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "逐条判定" });
    expect(screen.getAllByText(longReason)).toHaveLength(2);
    expect(screen.getByText("尚未到期")).toBeInTheDocument();
    expect(document.querySelector(".reports-print")).toBeInTheDocument();
  });

  it("生成打印版直接调用浏览器打印", async () => {
    const user = userEvent.setup();
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    render(<ReportsPage />);
    await screen.findByRole("heading", { name: "逐条判定" });
    await user.click(screen.getByRole("button", { name: "生成打印版" }));
    expect(print).toHaveBeenCalledTimes(1);
    print.mockRestore();
  });
});
