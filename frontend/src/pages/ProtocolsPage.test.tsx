// @vitest-environment jsdom
/**
 * 方案工作台组件测试（Phase 3 Slice 5）：分流首页、身份确认、草稿审阅三区。
 */

import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { navigate } from "../app/router";
import { ProtocolsPage } from "./ProtocolsPage";
import { PROTOCOL_DEMO_JOB_ID, PROTOCOL_IDENTITY_JOB_ID, PROTOCOL_RECOVERY_JOB_ID } from "../api/protocolWorkbenchRepository";
import {
  createProtocolWorkbenchStub,
  createProtocolWorkbenchHttp,
  setProtocolWorkbenchRepository,
} from "../api/protocolWorkbenchRepository";
import {
  draftRevisionFixture,
  officialProjectsFixture,
  protocolSessionFixtures,
} from "../fixtures/protocol-deconstruction-workbench";

describe("方案工作台", () => {
  beforeEach(() => {
    setProtocolWorkbenchRepository(createProtocolWorkbenchStub());
    navigate("/protocols");
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it("首页展示首次解构与重新解构分流", async () => {
    render(<ProtocolsPage />);
    expect(await screen.findByRole("heading", { name: "方案工作台" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /首次解构新方案/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /重新解构已有项目/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "开始首次解构" })).toHaveAttribute(
      "href",
      "#/protocols?mode=first",
    );
  });

  it("真实模式可从首页继续上次方案任务", async () => {
    setProtocolWorkbenchRepository(createProtocolWorkbenchHttp());
    window.localStorage.setItem("enrollment-review:last-protocol-job", "saved-job-1");
    render(<ProtocolsPage />);
    expect(await screen.findByRole("heading", { name: "继续上次方案任务" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "继续处理" })).toHaveAttribute(
      "href",
      "#/protocols?job=saved-job-1",
    );
    expect(screen.queryByText(/界面试用/)).not.toBeInTheDocument();
  });

  it("首次解构上传页使用中文说明", async () => {
    navigate("/protocols", { mode: "first" });
    render(<ProtocolsPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "首次解构新方案" })).toBeInTheDocument();
    });
    expect(screen.getByText(/核对方案信息与研究期别/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择方案文件" })).toBeInTheDocument();
    expect(document.querySelector("input[type=file]")).toHaveAttribute(
      "accept",
      expect.stringContaining(".docx"),
    );
    expect(document.querySelector("input[type=file]")).toHaveAttribute(
      "accept",
      expect.not.stringContaining("application/pdf"),
    );
  });

  it("示例草稿任务展示规则树、编辑区与来源定位", async () => {
    navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
    render(<ProtocolsPage />);
    expect(await screen.findByRole("heading", { name: "审阅解构草稿" })).toBeInTheDocument();
    expect(screen.getAllByText(/草稿第 1 稿/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/完整性检查/).length).toBeGreaterThan(0);
    expect(screen.getByRole("tree", { name: "方案规则树" })).toHaveTextContent("IN-01");
    expect(screen.getByRole("tree", { name: "方案规则树" })).toHaveTextContent("EX-01");
    expect(screen.getAllByText(/方案原文摘要/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/来源定位/).length).toBeGreaterThan(0);
    expect(screen.getByText(/请逐项核对原文、逻辑和资料要求/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消本次草稿" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "发布" })).toBeEnabled();
  });

  it("选择规则子项后编辑区与来源区同步显示", async () => {
    const user = userEvent.setup();
    navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
    render(<ProtocolsPage />);
    await screen.findByRole("tree", { name: "方案规则树" });
    await user.click(screen.getByRole("button", { name: /EX-01排除条件/ }));
    await user.click(screen.getByRole("button", { name: /EX-01a/ }));
    const editPane = screen.getByRole("tabpanel", { name: /编辑/ });
    expect(within(editPane).getByText("ALT或AST≥1.5×ULN")).toBeInTheDocument();
    expect(screen.getAllByText(/第 18 页/).length).toBeGreaterThan(0);
  });

  it("身份确认阶段展示期别候选", async () => {
    navigate("/protocols", { job: PROTOCOL_IDENTITY_JOB_ID });
    render(<ProtocolsPage />);
    expect(
      await screen.findByRole("heading", { name: "核对方案信息与研究期别" }),
    ).toBeInTheDocument();
    expect(screen.getByText("II 期")).toBeInTheDocument();
    expect(screen.getByText("III 期")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "确认并继续解构" })).toBeInTheDocument();
  });

  it("工作区标签切换时保留规则选择", async () => {
    const user = userEvent.setup();
    navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
    render(<ProtocolsPage />);
    await screen.findByRole("tree", { name: "方案规则树" });
    await user.click(screen.getByRole("button", { name: /IN-01a/ }));

    const editTab = screen.getByRole("tab", { name: "编辑" });
    await user.click(editTab);
    const editPanel = screen.getByRole("tabpanel", { name: /编辑/ });
    expect(within(editPanel).getByText("年龄要求")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "来源定位" }));
    const sourcePanel = screen.getByRole("tabpanel", { name: /来源定位/ });
    expect(within(sourcePanel).getByText(/第 12 页/)).toBeInTheDocument();
  });

  it("未知任务显示错误态", async () => {
    navigate("/protocols", { job: "missing-job" });
    render(<ProtocolsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("未找到该解构任务");
  });

  it("恢复示例展示中断横幅", async () => {
    navigate("/protocols", { job: PROTOCOL_RECOVERY_JOB_ID });
    render(<ProtocolsPage />);
    expect(await screen.findByRole("heading", { name: "可从中断处继续" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "继续任务" })).toBeInTheDocument();
  });

  it("正常运行中的任务即使已有检查点也继续展示处理进度", async () => {
    const base = createProtocolWorkbenchStub();
    setProtocolWorkbenchRepository({
      ...base,
      getSession: async () => ({
        ...protocolSessionFixtures[PROTOCOL_RECOVERY_JOB_ID]!,
        state: "running",
        stateLabel: "正在处理",
        progressCompleted: 6,
        progressTotal: 10,
        nextAction: "等待生成方案解构草稿。",
      }),
    });
    navigate("/protocols", { job: PROTOCOL_RECOVERY_JOB_ID });
    render(<ProtocolsPage />);

    expect(
      await screen.findByRole("heading", { name: "方案解构进行中" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "可从中断处继续" })).not.toBeInTheDocument();
  });

  it("重新解构入口展示正式项目选择列表", async () => {
    navigate("/protocols", { mode: "redo" });
    render(<ProtocolsPage />);
    expect(
      await screen.findByRole("heading", { name: /重新解构已有项目/ }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("测试研究", { exact: true }).length).toBeGreaterThan(0);
    expect(screen.getByText(/TEST-001/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /测试研究二/ })).toBeInTheDocument();
  });

  it("从已发布任务进入时展示正式版本摘要而不是中断恢复", async () => {
    const base = createProtocolWorkbenchStub();
    const completedSession = {
      ...protocolSessionFixtures[PROTOCOL_DEMO_JOB_ID]!,
      jobId: "job-published",
      state: "completed",
      stateLabel: "已完成",
      awaitingUser: null,
      awaitingUserLabel: null,
      draftStatus: "published",
      draftStatusLabel: "已发布",
      recoveryCheckpointId: "checkpoint-published",
      nextAction: "请刷新查看最新进展。",
    };
    setProtocolWorkbenchRepository({
      ...base,
      getSession: async () => completedSession,
      getDraft: async () => ({
        ...draftRevisionFixture,
        jobId: "job-published",
        status: "published",
        statusLabel: "已发布",
        content: {
          ...draftRevisionFixture.content,
          project_id: officialProjectsFixture[0]!.projectId,
        },
      }),
    });
    window.localStorage.setItem("enrollment-review:last-protocol-job", "job-published");
    navigate("/protocols", { job: "job-published" });
    render(<ProtocolsPage />);

    expect(await screen.findByRole("heading", { name: "方案已发布" })).toBeInTheDocument();
    expect(screen.queryByText("可从中断处继续")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "重新解构此项目" })).toHaveAttribute(
      "href",
      "#/protocols?mode=redo&project=project-demo-1",
    );
    await waitFor(() => {
      expect(window.localStorage.getItem("enrollment-review:last-protocol-job")).toBeNull();
    });
  });

  it("从已发布摘要进入重新解构时自动选中目标项目", async () => {
    navigate("/protocols", { mode: "redo", project: "project-demo-2" });
    render(<ProtocolsPage />);

    const selected = await screen.findByRole("button", { name: /测试研究二/ });
    expect(selected).toHaveAttribute("aria-pressed", "true");
    expect(await screen.findByText("目标项目与正式版本")).toBeInTheDocument();
  });

  it("重新解构：选择项目后上传新版方案可进入任务", async () => {
    const user = userEvent.setup();
    navigate("/protocols", { mode: "redo" });
    render(<ProtocolsPage />);
    await screen.findByRole("heading", { name: /重新解构已有项目/ });
    await user.click(screen.getByRole("button", { name: /测试研究二/ }));
    const file = new File([btoa("dummy-docx")], "新版方案.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    expect(screen.getByRole("button", { name: "选择新版方案文件" })).toBeInTheDocument();
    const uploadInput = document.querySelector("input[type=file]") as HTMLInputElement;
    expect(uploadInput).not.toBeNull();
    await user.upload(uploadInput, file);
    expect(
      await screen.findByRole("heading", { name: "核对方案信息与研究期别" }),
    ).toBeInTheDocument();
  });

  it("示例草稿保存后显示界面试用状态", async () => {
    const user = userEvent.setup();
    navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
    render(<ProtocolsPage />);
    await screen.findByRole("button", { name: "保存草稿" });
    await user.click(screen.getByRole("button", { name: "保存草稿" }));
    expect(await screen.findByRole("status")).toHaveTextContent("已保存草稿");
    expect(await screen.findByRole("button", { name: "已保存草稿" })).toBeDisabled();
  });

  it("首次解构发布前显示适用于新项目的确认说明", async () => {
    const user = userEvent.setup();
    navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
    render(<ProtocolsPage />);
    await user.click(await screen.findByRole("button", { name: "发布" }));
    const dialog = screen.getByRole("dialog", { name: "确认发布新规则版本" });
    expect(dialog).toHaveTextContent("建立正式项目");
    expect(dialog).toHaveTextContent("同一方案、同一期别已有正式项目时");
    expect(dialog).not.toHaveTextContent("目标项目下");
  });
});
