// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PublishResultView, ProtocolSessionView } from "../../api/protocolWorkbenchTypes";
import { ProtocolPublishResult } from "./ProtocolPublishResult";
import { ProtocolPublishedSummary } from "./ProtocolPublishedSummary";

const session: ProtocolSessionView = {
  jobId: "job-1",
  jobType: "protocol_first_deconstruction",
  state: "completed",
  stateLabel: "已完成",
  progressCompleted: 1,
  progressTotal: 1,
  sessionKind: "first_deconstruction",
  awaitingUser: null,
  awaitingUserLabel: null,
  sourceArtifactId: null,
  fileName: null,
  snapshotId: null,
  draftId: null,
  draftRevisionId: null,
  draftRevisionNumber: null,
  draftStatus: null,
  draftStatusLabel: null,
  selectedPhase: null,
  selectedPhaseLabel: "Ⅲ期",
  protocolCode: "PROTOCOL-1",
  officialVersion: "V1.0",
  recoveryCheckpointId: null,
  recoveryStepId: null,
  nextAction: "",
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

const result: PublishResultView = {
  jobId: "job-1",
  projectId: "project-published-1",
  protocolVersionId: "protocol-v1",
  ruleSetId: "rules-1",
  ruleSetRevision: 1,
  replay: false,
};

describe("方案发布后入口", () => {
  it("验证发布与重开摘要均明确显示验证身份", () => {
    const view = render(<ProtocolPublishResult session={session} result={{ ...result, verificationOnly: true }} />);
    expect(screen.getByRole("heading", { name: "验证用规则包已发布" })).toBeInTheDocument();
    expect(screen.getByText(/不能用于正式审核/)).toBeInTheDocument();
    view.rerender(<ProtocolPublishedSummary session={{ ...session, verificationOnly: true }}
      draft={{ content: {}, ruleCount: 1, studyPhaseLabel: "III期" } as never} />);
    expect(screen.getByRole("heading", { name: "验证用规则包已发布" })).toBeInTheDocument();
  });
  it("发布完成页提供直达受试者资料目录且预选该项目", () => {
    window.location.hash = "#/protocols";
    render(<ProtocolPublishResult session={session} result={result} />);

    const link = screen.getByRole("link", { name: "前往受试者与资料" });
    expect(link).toHaveAttribute("href", "#/subjects?project=project-published-1");
  });

  it("已发布摘要页同样提供直达入口", () => {
    window.location.hash = "#/protocols";
    const draft = {
      protocolCode: "PROTOCOL-1",
      officialVersion: "V1.0",
      studyPhaseLabel: "Ⅲ期",
      ruleCount: 10,
      content: { project_id: "project-published-1" },
    } as never;
    render(
      <ProtocolPublishedSummary
        session={session}
        draft={draft as never}
      />,
    );

    const link = screen.getByRole("link", { name: "前往受试者与资料" });
    expect(link).toHaveAttribute("href", "#/subjects?project=project-published-1");
  });
});
