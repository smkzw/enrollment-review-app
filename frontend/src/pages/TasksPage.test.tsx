// @vitest-environment jsdom
/**
 * 任务与系统组件测试：真实任务列表与事件时间线、处理状态试用覆盖
 * 排队/运行/部分失败/可恢复/取消/stale/完成边界（UAT-P1-12 语义）。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { TasksPage } from "./TasksPage";

async function openTasks(user: ReturnType<typeof userEvent.setup>) {
  render(<TasksPage />);
  await screen.findByRole("heading", { name: "任务与系统" });
  await screen.findByRole("heading", { name: /资料整理记录/ });
  return user;
}

describe("任务与系统", () => {
  beforeEach(() => {
    window.location.hash = "";
    window.sessionStorage.clear();
  });

  it("真实任务列表显示对象、阶段、状态与进度", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    const listSection = screen
      .getByRole("heading", { name: /资料整理记录/ })
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

  it("处理状态试用从部分完成开始，继续时不重复已完成资料", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    expect(screen.getByText("部分资料尚未处理")).toBeInTheDocument();
    expect(screen.getByText("已完成，继续时不会重复")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "继续" }));
    expect(screen.getByText("正在整理资料")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "暂停" }));
    expect(screen.getByText("已保存进度，可继续")).toBeInTheDocument();
  });

  it("处理状态试用：部分完成→继续→暂停→取消，已完成部分仍保留", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    await user.click(screen.getByRole("button", { name: "继续" }));
    await user.click(screen.getByRole("button", { name: "暂停" }));
    await user.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.getByText("已取消")).toBeInTheDocument();
    expect(
      screen.getAllByText(/已完成部分仍保留/).length,
    ).toBeGreaterThan(0);
  });

  it("从零进度发生部分失败时不误称已有资料完成", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    await user.click(screen.getByRole("button", { name: "取消本次操作" }));
    await user.click(screen.getByRole("button", { name: "重新开始" }));
    await user.click(screen.getByRole("button", { name: "开始整理" }));
    await user.click(screen.getByRole("button", { name: "部分资料失败" }));

    expect(screen.getByText("已整理 0 / 3 项资料")).toBeInTheDocument();
    expect(screen.getByText("有资料处理失败或尚未处理；可继续未完成部分。")).toBeInTheDocument();
    expect(screen.queryByText(/部分资料已整理完成/)).not.toBeInTheDocument();
  });

  it("处理状态试用：失败→稍后再试→资料发生变化→需重新核对", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    await user.click(screen.getByRole("button", { name: "继续" }));
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

  it("离开页面后重新进入，保存的进度仍可继续", async () => {
    const user = userEvent.setup();
    const first = render(<TasksPage />);
    await screen.findByRole("heading", { name: "任务与系统" });
    await user.click(screen.getByRole("button", { name: "继续" }));
    await user.click(screen.getByRole("button", { name: "完成一项资料" }));
    const files = screen.getByRole("list", { name: "资料处理范围" });
    expect(within(files).getByText("实验室检查.pdf").closest("li"))
      .toHaveTextContent("已完成，继续时不会重复");
    expect(within(files).getByText("既往用药记录.pdf").closest("li"))
      .toHaveTextContent("上次处理失败，可稍后再试");
    first.unmount();

    render(<TasksPage />);
    await screen.findByRole("heading", { name: "任务与系统" });
    expect(screen.getByText("已整理 2 / 3 项资料")).toBeInTheDocument();
    expect(screen.getByText("正在整理资料")).toBeInTheDocument();
    const restoredFiles = screen.getByRole("list", { name: "资料处理范围" });
    expect(within(restoredFiles).getByText("实验室检查.pdf").closest("li"))
      .toHaveTextContent("已完成，继续时不会重复");
  });

  it.each([
    ["queued", ["completed", "pending", "pending"]],
    ["running", ["completed", "completed", "completed"]],
    ["partial", ["completed", "completed", "completed"]],
    ["partial", ["pending", "pending", "pending"]],
    ["failed", ["completed", "pending", "pending"]],
    ["resumable", ["completed", "completed", "completed"]],
    ["cancelled", ["completed", "completed", "completed"]],
    ["stale", ["pending", "pending", "pending"]],
    ["completed", ["pending", "pending", "pending"]],
  ] as const)("拒绝与资料进度矛盾的 %s 状态并恢复可信初始状态", async (state, fileStates) => {
    window.sessionStorage.setItem(
      "eligibility-review:uat:task-progress",
      JSON.stringify({
        state,
        fileStates: {
          screening: fileStates[0],
          laboratory: fileStates[1],
          medication: fileStates[2],
        },
      }),
    );

    const user = userEvent.setup();
    await openTasks(user);
    expect(screen.getByText("部分资料尚未处理")).toBeInTheDocument();
    expect(screen.getByText("已整理 1 / 3 项资料")).toBeInTheDocument();
    expect(screen.queryByText("全部资料整理完成。")).not.toBeInTheDocument();
  });

  it("处理状态试用明确说明不会实际运行", async () => {
    const user = userEvent.setup();
    await openTasks(user);
    const demoSection = screen
      .getByRole("heading", { name: /继续未完成事项/ })
      .closest("section");
    expect(demoSection).toHaveTextContent("不会实际运行文字识别或审核");
  });
});
