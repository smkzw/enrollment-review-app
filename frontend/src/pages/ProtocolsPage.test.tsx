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

describe("方案工作台", () => {
  beforeEach(() => {
    navigate("/protocols");
    window.sessionStorage.clear();
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

  it("首次解构上传页使用中文说明", async () => {
    navigate("/protocols", { mode: "first" });
    render(<ProtocolsPage />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "首次解构新方案" })).toBeInTheDocument();
    });
    expect(screen.getByText(/核对方案信息与研究期别/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择方案文件" })).toBeInTheDocument();
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
  });

  it("选择规则子项后编辑区与来源区同步显示", async () => {
    const user = userEvent.setup();
    navigate("/protocols", { job: PROTOCOL_DEMO_JOB_ID });
    render(<ProtocolsPage />);
    await screen.findByRole("tree", { name: "方案规则树" });
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

  it("重新解构占位展示空态说明", async () => {
    navigate("/protocols", { mode: "redo" });
    render(<ProtocolsPage />);
    expect(await screen.findByText("重新解构流程尚未在本切片开放")).toBeInTheDocument();
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
});
