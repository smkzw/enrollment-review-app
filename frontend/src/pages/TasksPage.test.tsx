// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { TasksPage } from "./TasksPage";

describe("任务与系统", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("显示当前可用的资料整理记录和数据来源", async () => {
    render(<TasksPage />);
    expect(await screen.findByRole("heading", { name: "任务与系统" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "资料处理记录" })).toBeInTheDocument();
    expect(screen.getByText("数据来源：当前已接入的资料处理记录。")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /UAT-01/ }).length).toBeGreaterThan(0);
    expect(screen.queryByText("继续未完成事项")).not.toBeInTheDocument();
    expect(screen.queryByText(/不会实际/)).not.toBeInTheDocument();
  });

  it("点击任务行显示任务状态、进度和处理记录", async () => {
    const user = userEvent.setup();
    render(<TasksPage />);
    await screen.findByRole("heading", { name: "资料处理记录" });
    await user.click(screen.getAllByRole("button", { name: /UAT-01/ })[0]);
    expect(await screen.findByRole("heading", { name: /任务详情：UAT-01/ })).toBeInTheDocument();
    expect(screen.getByText(/进度：已整理/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "处理记录" })).toBeInTheDocument();
  });
});
