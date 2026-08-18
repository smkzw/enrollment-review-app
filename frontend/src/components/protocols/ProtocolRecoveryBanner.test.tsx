// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ProtocolSessionView } from "../../api/protocolWorkbenchTypes";
import { ProtocolRecoveryBanner } from "./ProtocolRecoveryBanner";

function failedSession(): ProtocolSessionView {
  return {
    jobId: "job-failed",
    jobType: "protocol_deconstruction",
    state: "failed_final",
    stateLabel: "失败",
    progressCompleted: 5,
    progressTotal: 9,
    sessionKind: "first_deconstruction",
    awaitingUser: null,
    awaitingUserLabel: null,
    sourceArtifactId: "artifact-1",
    fileName: "测试方案.docx",
    snapshotId: "snapshot-1",
    draftId: null,
    draftRevisionId: null,
    draftRevisionNumber: null,
    draftStatus: null,
    draftStatusLabel: null,
    selectedPhase: "phase_iii",
    selectedPhaseLabel: "III 期",
    protocolCode: "TEST-001",
    officialVersion: "V1.0",
    recoveryCheckpointId: "checkpoint-1",
    recoveryStepId: "await_identity_confirm",
    nextAction:
      "草稿生成未能完成。可以重新生成草稿；已核对的方案信息和研究期别会保留。",
    publishable: null,
    targetProjectId: null,
    targetProjectName: null,
    targetProjectCode: null,
    targetProtocolCode: null,
    targetStudyPhase: null,
    targetStudyPhaseLabel: null,
    targetOfficialVersion: null,
    targetRuleSetRevision: null,
  };
}

describe("方案解构失败恢复提示", () => {
  it("终止失败时显示真正的重新生成动作", async () => {
    const user = userEvent.setup();
    const onContinue = vi.fn();
    render(
      <ProtocolRecoveryBanner session={failedSession()} onContinue={onContinue} />,
    );

    expect(screen.getByRole("heading", { name: "草稿生成未完成" })).toBeInTheDocument();
    expect(screen.queryByText("当前状态：失败。")).not.toBeInTheDocument();
    expect(screen.getByText(/已核对的方案信息/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "重新生成草稿" }));
    expect(onContinue).toHaveBeenCalledTimes(1);
  });
});
