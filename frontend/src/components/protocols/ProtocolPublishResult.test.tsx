// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PublishResultView, ProtocolSessionView } from "../../api/protocolWorkbenchTypes";
import { ProtocolPublishResult } from "./ProtocolPublishResult";
import { ProtocolPublishedSummary } from "./ProtocolPublishedSummary";
import userEvent from "@testing-library/user-event";

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
  it("历史发布摘要只声明本任务内容，入排条目数不冒充完整范围数", () => {
    render(<ProtocolPublishedSummary session={session} draft={{ protocolCode: "PROTOCOL-1",
      officialVersion: "V1.0", studyPhaseLabel: "Ⅲ期", ruleCount: 23,
      content: { project_id: "project-published-1" } } as never} />);
    expect(screen.getByRole("heading", { name: "本次发布内容" })).toBeVisible();
    expect(screen.getByText("入排标准")).toBeVisible();
    expect(screen.getByText("23 条")).toBeVisible();
    expect(screen.queryByText("当前正式版本")).not.toBeInTheDocument();
    expect(screen.queryByText("规则条目")).not.toBeInTheDocument();
  });
  it("重新发布默认显示真实代号，完整名称可展开，不复制长名称", async () => {
    const user = userEvent.setup();
    const name = "一项用于核对发布后项目显示和版本绑定的多中心临床研究完整名称";
    render(<ProtocolPublishResult session={{ ...session, sessionKind: "re_deconstruction",
      targetProjectCode: "P002", targetProjectName: name, targetProtocolCode: "PROTOCOL-2" }} result={result} />);
    expect(screen.getByText("P002")).toBeVisible();
    expect(screen.getByText("PROTOCOL-2")).toBeVisible();
    expect(screen.getAllByText(name)).toHaveLength(1);
    expect(screen.getByText(name)).not.toBeVisible();
    expect(document.querySelector("details")).not.toHaveAttribute("open");
    await user.click(screen.getByText("研究完整名称"));
    expect(screen.getByText(name)).toBeVisible();
    expect(screen.getByRole("link", { name: "前往受试者与资料" }))
      .toHaveAttribute("href", "#/subjects?project=project-published-1");
    expect(screen.getByRole("link", { name: "再次重新解构" }))
      .toHaveAttribute("href", "#/protocols?mode=redo&project=project-published-1");
  });

  it("缺少项目代号时不拿内部ID冒充名称，验证身份仍保留", () => {
    render(<ProtocolPublishResult session={{ ...session, sessionKind: "re_deconstruction" }}
      result={{ ...result, verificationOnly: true }} />);
    expect(screen.getByText("项目代号未填写")).toBeVisible();
    expect(screen.queryByText(result.projectId)).not.toBeInTheDocument();
    expect(screen.getByText(/不能用于正式审核/)).toBeVisible();
  });
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
