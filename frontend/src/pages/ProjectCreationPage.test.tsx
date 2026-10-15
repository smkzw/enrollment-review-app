// @vitest-environment jsdom
/**
 * 新建项目页组件测试：研究期别确认与独立审核节点进入（UAT-P1-02）。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { ProjectCreationPage } from "./ProjectCreationPage";

describe("新建项目", () => {
  beforeEach(() => {
    window.location.hash = "#/projects/new";
    window.sessionStorage.clear();
  });

  it("离开后重新进入仍显示本次试用中建立的项目", async () => {
    const user = userEvent.setup();
    const first = render(<ProjectCreationPage />);
    const dialog = await screen.findByRole("dialog", { name: "确认方案信息" });
    await user.click(within(dialog).getByRole("button", { name: "确认方案并继续" }));
    await user.click(screen.getByRole("button", { name: "确认研究期别并继续" }));
    await user.click(screen.getByRole("radio", { name: /筛选期/ }));
    await user.click(screen.getByRole("button", { name: "创建项目并进入筛选期" }));
    first.unmount();

    render(<ProjectCreationPage />);
    expect(await screen.findByRole("heading", { name: "项目已建立" })).toBeInTheDocument();
    expect(screen.getByText("当前位置：筛选期")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "返回原项目看板" })).toBeInTheDocument();
  });

  it("必须确认研究期别，并单独进入筛选期而不带入旧资料", async () => {
    const user = userEvent.setup();
    render(<ProjectCreationPage />);

    const dialog = await screen.findByRole("dialog", { name: "确认方案信息" });
    expect(dialog).toHaveTextContent("本次试用数据仅用于体验操作，不会写入正式项目资料");
    await user.click(within(dialog).getByRole("button", { name: "确认方案并继续" }));

    expect(screen.getByRole("heading", { name: "确认研究期别" })).toBeInTheDocument();
    const phase = screen.getByRole("radio", { name: /Ⅲ期/ });
    expect(phase).toBeChecked();
    await user.click(screen.getByRole("button", { name: "确认研究期别并继续" }));

    expect(
      screen.getByRole("heading", { name: "选择进入的审核节点" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /筛选期/ }));
    await user.click(
      screen.getByRole("button", { name: "创建项目并进入筛选期" }),
    );

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "项目已建立" })).toBeInTheDocument();
    expect(screen.getByText("方案版本").parentElement).toHaveTextContent("V1.0");
    expect(screen.getByText("研究期别").parentElement).toHaveTextContent("Ⅲ期");
    expect(screen.getByText("当前位置：筛选期")).toBeInTheDocument();
    expect(screen.getByText("基线/随机前：另一个独立审核节点")).toBeInTheDocument();
    expect(screen.getByText(/未带入旧项目或其他阶段资料/)).toBeInTheDocument();
    expect(screen.queryByText("UAT-01")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "恢复试用初始状态" }));
    expect(await screen.findByRole("dialog", { name: "确认方案信息" })).toBeInTheDocument();
  });
});
