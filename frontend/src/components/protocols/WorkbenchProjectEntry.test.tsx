// @vitest-environment jsdom

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { WorkbenchProjectEntryView } from "../../api/protocolWorkbenchTypes";
import {
  WorkbenchProjectEntry,
  isReturnRouteRejected,
  sanitizeReturnRoute,
} from "./WorkbenchProjectEntry";

const ORIGIN = "workbench:proj_user_9";

function entryView(
  patch: Partial<WorkbenchProjectEntryView> = {},
): WorkbenchProjectEntryView {
  return {
    origin: ORIGIN,
    entryState: "unbound",
    job: null,
    project: null,
    ...patch,
  };
}

describe("共享工作台来源入口", () => {
  it("返回上下文只接受本产品相对路由", () => {
    expect(sanitizeReturnRoute("/today")).toBe("/today");
    expect(sanitizeReturnRoute("/protocols?job=abc")).toBe("/protocols?job=abc");
    expect(sanitizeReturnRoute(null)).toBeNull();
    expect(sanitizeReturnRoute("")).toBeNull();
    expect(sanitizeReturnRoute("https://evil.example")).toBeNull();
    expect(sanitizeReturnRoute("//evil.example")).toBeNull();
    expect(sanitizeReturnRoute("/a/../b")).toBeNull();
    expect(isReturnRouteRejected("https://evil.example")).toBe(true);
    expect(isReturnRouteRejected(null)).toBe(false);
  });

  it("未绑定来源展示真实上传入口并如实说明，不展示历史项目", async () => {
    render(
      <WorkbenchProjectEntry
        origin={ORIGIN}
        returnRoute={null}
        busy={false}
        error={null}
        onUpload={() => {}}
        resolveEntry={async () => entryView()}
      />,
    );
    await waitFor(() => {
      expect(screen.getByText(/尚未上传研究方案/)).toBeInTheDocument();
    });
    expect(screen.queryByText(new RegExp(ORIGIN))).not.toBeInTheDocument();
  });

  it("已发布项目从持久身份跳转既有项目流程，不新建入口", async () => {
    render(
      <WorkbenchProjectEntry
        origin={ORIGIN}
        returnRoute="/today"
        busy={false}
        error={null}
        onUpload={() => {}}
        resolveEntry={async () =>
          entryView({
            entryState: "project_published",
            project: {
              projectId: "proj-1",
              projectCode: "P001",
              projectName: "测试项目",
              studyPhase: "phase_iii",
              studyPhaseLabel: "III 期",
              protocolCode: "TEST-001",
              officialVersion: "V1.0",
              ruleSetId: "ruleset-1",
              ruleSetRevision: 3,
            },
          })
        }
      />,
    );
    await waitFor(() => {
      const link = screen.getByRole("link", { name: "上传新版方案" });
      expect(link.getAttribute("href")).toBe(
        "#/protocols?mode=redo&project=proj-1&workbench_origin=workbench%3Aproj_user_9&return=%2Ftoday",
      );
    });
    expect(screen.getByRole("link", { name: "返回上一级" }).getAttribute("href")).toBe(
      "#/today",
    );
  });

  it("返回另一项目的关联时不显示上传或历史入口", async () => {
    render(<WorkbenchProjectEntry origin={ORIGIN} returnRoute={null} busy={false}
      error={null} onUpload={() => {}} resolveEntry={async () => entryView({ origin: "workbench:other" })} />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.queryByText(/尚未上传研究方案/)).not.toBeInTheDocument();
  });

  it("失败首次上传保留原因入口，并允许重新上传", async () => {
    render(<WorkbenchProjectEntry origin={ORIGIN} returnRoute="/today" busy={false}
      error={null} onUpload={() => {}} resolveEntry={async () => entryView({ entryState: "job_in_progress",
        job: { jobId: "failed-job", state: "failed_final", stateLabel: "处理失败", sessionKind: "first_deconstruction",
          awaitingUser: null, awaitingUserLabel: null, publishable: false, fileName: "失败方案.docx" } })} />);
    await waitFor(() => expect(screen.getByRole("link", { name: "查看处理进度" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "查看处理进度" }).getAttribute("href"))
      .toBe("#/protocols?job=failed-job&workbench_origin=workbench%3Aproj_user_9&return=%2Ftoday");
    expect(screen.getByText(/上次处理已结束/)).toBeInTheDocument();
  });
});
