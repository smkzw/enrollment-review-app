// @vitest-environment jsdom
/**
 * 任务与系统组件测试：真实任务列表与事件时间线、处理状态试用覆盖
 * 排队/运行/部分失败/可恢复/取消/stale/完成边界（UAT-P1-12 语义）。
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { TasksPage } from "./TasksPage";

async function openTasks(user: ReturnType<typeof userEvent.setup>) {
  render(<TasksPage />);
  await screen.findByRole("heading", { name: "任务与系统" });
  await screen.findByRole("heading", { name: /资料整理任务/ });
  return user;
}

describe("任务与系统", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("真实任务列表显示对象、阶段、状态与进度", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    const listSection = screen
      .getByRole("heading", { name: /资料整理任务/ })
      .closest("section");
    expect(listSection).toHaveTextContent("UAT-03");
    expect(listSection).toHaveTextContent("筛选期");
    expect(listSection).toHaveTextContent("已完成");
    expect(listSection).toHaveTextContent("已整理 2 / 2 项资料");
  });

  it("点击任务行显示事件时间线，包含失败与重试记录", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    const row = screen
      .getAllByRole("button")
      .find(
        (button) =>
          button.textContent?.includes("UAT-03") &&
          button.textContent?.includes("筛选期") &&
          button.textContent?.includes("查看"),
      );
    expect(row).not.toBeUndefined();
    await user.click(row as HTMLElement);
    expect(
      await screen.findByRole("heading", { name: /任务详情：UAT-03 筛选期/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("一项资料整理失败")).toBeInTheDocument();
    expect(screen.getByText("已安排重试")).toBeInTheDocument();
    expect(screen.getAllByText("已完成").length).toBeGreaterThan(0);
  });

  it("处理状态试用覆盖边界：准备中→运行→部分失败→继续→暂停→可恢复", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    // 初始：准备中
    expect(screen.getByText("准备中")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始整理" }));
    expect(screen.getByText("正在整理资料")).toBeInTheDocument();
    // 部分资料失败
    await user.click(screen.getByRole("button", { name: "部分资料失败" }));
    expect(screen.getByText("部分资料尚未处理")).toBeInTheDocument();
    // 继续 → 暂停 → 已保存进度，可继续
    await user.click(screen.getByRole("button", { name: "继续" }));
    expect(screen.getByText("正在整理资料")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "暂停" }));
    expect(screen.getByText("已保存进度，可继续")).toBeInTheDocument();
  });

  it("处理状态试用：可恢复→取消→重新开始→准备中", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    await user.click(screen.getByRole("button", { name: "开始整理" }));
    await user.click(screen.getByRole("button", { name: "暂停" }));
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.getByText("已取消")).toBeInTheDocument();
    expect(
      screen.getAllByText(/已完成部分仍保留/).length,
    ).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "重新开始" }));
    expect(screen.getByText("准备中")).toBeInTheDocument();
  });

  it("处理状态试用：失败→稍后再试→资料发生变化→需重新核对", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    await user.click(screen.getByRole("button", { name: "开始整理" }));
    await user.click(screen.getByRole("button", { name: "一项资料失败" }));
    expect(screen.getByText("处理失败，可重试")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "稍后再试" }));
    expect(screen.getByText("正在整理资料")).toBeInTheDocument();
    // 再次失败 → 资料发生变化 → 需重新核对
    await user.click(screen.getByRole("button", { name: "一项资料失败" }));
    await user.click(screen.getByRole("button", { name: "资料发生变化" }));
    expect(
      screen.getByText("资料发生变化，当前结果需要重新核对"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /查看差异/ })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "开始新的整理" }));
    expect(screen.getByText("正在整理资料")).toBeInTheDocument();
  });

  it("处理状态试用明确说明不会实际运行", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    const demoSection = screen
      .getByRole("heading", { name: /处理状态试用/ })
      .closest("section");
    expect(demoSection).toHaveTextContent("不会实际运行文字识别或审核");
  });
});
