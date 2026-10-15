// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PreparedReviewPanel } from "./PreparedReviewPanel";
import type { CatalogEpisodeView } from "../../api/catalog/catalogTypes";

const episode: CatalogEpisodeView = {
  reviewEpisodeId: "screen", subjectId: "subject", projectId: "project", ruleSetId: "rules",
  studyPhase: "phase_iii", studyPhaseLabel: "III期", stage: "screening", stageLabel: "筛选期",
  protocolVersionId: "protocol", ruleSetRevision: 1, evidenceSnapshotId: "snapshot",
  workflowStageId: null, workflowStageLabel: null, visitWindow: null,
  latestEvidenceSnapshotId: "snapshot", activeEvidenceSnapshotId: "snapshot",
  activeEvidenceProcessingRevisionId: "processing", anchorDates: {}, dueAt: null, revision: 1,
};

const { state } = vi.hoisted(() => ({ state: {
  data: { state: "failed_final", stateLabel: "处理未完成", stageLabel: "复核原文依据",
    reportSaved: false, failureReason: "这不是受试者资料缺失，不需要因此重复上传原件。" as string | null,
    retryAvailable: false, items: [] },
  busy: false, canStart: true, errorMessage: null,
  start: vi.fn(), publish: vi.fn(), change: vi.fn(), refresh: vi.fn(),
} }));
vi.mock("../../features/eligibility-review/usePreparedReview", () => ({ usePreparedReview: () => state }));
afterEach(() => { cleanup(); });

function panel() {
  return render(<PreparedReviewPanel episode={episode} workflowId="workflow" requestKey={null}
    onRequestKey={vi.fn()} onStarted={vi.fn()} onNewReview={vi.fn()} onPublished={vi.fn()} />);
}

it("直接说明方案侧缺口，不提供无效重复核对", () => {
  state.data.failureReason = "这不是受试者资料缺失，不需要因此重复上传原件。";
  state.data.retryAvailable = false;
  panel();
  expect(screen.getByRole("alert")).toHaveTextContent("完善方案并采用新的规则版本后");
  expect(screen.queryByRole("button", { name: "重试未完成部分" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "重新准备审核" })).toBeEnabled();
});

it("普通可恢复失败仍可重试，不冒用方案侧原因", () => {
  state.data.failureReason = null;
  state.data.retryAvailable = true;
  panel();
  expect(screen.getByRole("button", { name: "重试未完成部分" })).toBeEnabled();
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});
