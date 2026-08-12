// @vitest-environment jsdom
/**
 * 今日工作页组件测试：区块内容来自真实 fixture，直达审核节点入口。
 * 覆盖工作项验收“direct review entry”行为（UAT-P1-01 语义）。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { TodayPage } from "./TodayPage";

describe("今日工作页", () => {
  beforeEach(() => {
    window.location.hash = "";
  });

  it("加载后显示待处理事项计数与明确障碍、存在冲突、任务、近期变化区块", async () => {
    render(<TodayPage />);
    expect(
      await screen.findByRole("heading", { name: "今日工作" }),
    ).toBeInTheDocument();
    const due = await screen.findByRole("heading", {
      name: /待处理事项/,
    });
    expect(due.parentElement).toHaveTextContent("40");
    expect(
      screen.getByRole("heading", { name: /明确障碍/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /存在冲突/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /资料整理任务/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /近期变化/ }),
    ).toBeInTheDocument();
  });

  it("待处理事项展示对象、缺口、责任方与直达入口", async () => {
    render(<TodayPage />);
    const dueSection = (await screen.findByRole("heading", {
      name: /待处理事项/,
    })).closest("section");
    expect(dueSection).not.toBeNull();
    const list = within(dueSection as HTMLElement).getByRole("list");
    const row = within(list)
      .getAllByRole("listitem")
      .find((item) =>
        within(item).queryByRole("link", {
          name: /打开 UAT-03 筛选期审核/,
        }),
      );
    expect(row).not.toBeUndefined();
    expect(row).toHaveTextContent("UAT-03");
    expect(row).toHaveTextContent("补充当前审核节点未记录的关键信息");
    expect(row).toHaveTextContent("关联规则：IN-01");
    expect(row).toHaveTextContent("责任方：研究者方");
    expect(
      within(row as HTMLElement).getByRole("link", {
        name: /打开 UAT-03 筛选期审核/,
      }),
    ).toBeInTheDocument();
  });

  it("待处理事项预览最多六行并提供行动中心入口", async () => {
    render(<TodayPage />);
    const dueSection = (await screen.findByRole("heading", {
      name: /待处理事项/,
    })).closest("section");
    expect(dueSection).not.toBeNull();
    const list = within(dueSection as HTMLElement).getByRole("list");
    const rows = within(list).getAllByRole("listitem");
    expect(rows.length).toBeLessThanOrEqual(6);
    expect(dueSection).toHaveTextContent("共 40 项，其余请在");
    const moreLink = within(dueSection as HTMLElement).getByRole("link", {
      name: "打开行动中心",
    });
    expect(moreLink).toHaveAttribute("href", "#/actions");
  });

  it("点击直达入口进入对应审核节点（URL 契约 #/workbench?episode=）", async () => {
    const user = userEvent.setup();
    render(<TodayPage />);
    const dueSection = (await screen.findByRole("heading", {
      name: /待处理事项/,
    })).closest("section");
    const link = within(dueSection as HTMLElement).getAllByRole("link", {
      name: /打开 UAT-03 筛选期审核/,
    })[0];
    await user.click(link);
    expect(window.location.hash).toBe(
      "#/workbench?episode=episode-uat-03-screening-gap_conflict&component=component-in-01",
    );
  });

  it("明确障碍区块列出 UAT-02 与 UAT-06 并提供直达入口", async () => {
    render(<TodayPage />);
    const barrierSection = (await screen.findByRole("heading", {
      name: /明确障碍/,
    })).closest("section");
    const list = within(barrierSection as HTMLElement).getByRole("list");
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(4);
    expect(list).toHaveTextContent("UAT-02");
    expect(list).toHaveTextContent("UAT-06");
    expect(
      within(rows[0]).getByRole("link", { name: /打开 UAT-02 筛选期审核/ }),
    ).toHaveAttribute(
      "href",
      "#/workbench?episode=episode-uat-02-screening-barrier&component=component-ex-03",
    );
  });

  it("近期变化显示方案差异条目（新增 EX-05）", async () => {
    render(<TodayPage />);
    const changeSection = (await screen.findByRole("heading", {
      name: /近期变化/,
    })).closest("section");
    expect(changeSection).toHaveTextContent("方案新增条件 EX-05");
    const protocolLinks = within(changeSection as HTMLElement).getAllByRole(
      "link",
      { name: "打开方案工作台查看差异" },
    );
    expect(protocolLinks.length).toBeGreaterThan(0);
    expect(protocolLinks[0]).toHaveAttribute("href", "#/protocols");
  });
});
