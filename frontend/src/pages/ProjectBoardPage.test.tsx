// @vitest-environment jsdom
/**
 * 项目看板页组件测试：阶段聚焦、状态筛选、排序、勾选与直达审核节点。
 * 覆盖工作项验收“sorting/filtering 与 direct review entry”（UAT-P1-04/05 语义）。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { ProjectBoardPage } from "./ProjectBoardPage";

function rowsOfTable(table: HTMLElement): HTMLElement[] {
  return Array.from(table.querySelectorAll("tbody tr"));
}

describe("项目看板页", () => {
  beforeEach(() => {
    // 看板页在真实应用中以 #/board 打开；筛选/排序参数基于当前路由路径写入
    window.location.hash = "#/board";
  });

  it("默认显示全部受试者与四个独立审核节点列", async () => {
    render(<ProjectBoardPage />);
    await screen.findByRole("heading", { name: "项目看板" });
    const table = await screen.findByRole("table");
    const headers = within(table).getAllByRole("columnheader");
    const headerTexts = headers.map((header) => header.textContent ?? "");
    expect(headerTexts.join("|")).toContain("受试者");
    expect(headerTexts.join("|")).toContain("阻断程度");
    expect(headerTexts.join("|")).toContain("预筛期");
    expect(headerTexts.join("|")).toContain("筛选期");
    expect(headerTexts.join("|")).toContain("导入/洗脱期");
    expect(headerTexts.join("|")).toContain("基线/随机前");
    expect(rowsOfTable(table)).toHaveLength(8);
    expect(table).toHaveTextContent("UAT-01");
    expect(table).toHaveTextContent("UAT-08");
  });

  it("阶段汇总条显示筛选期计数（明确障碍 2、当前节点缺口 2、后续节点关注 2）", async () => {
    render(<ProjectBoardPage />);
    const summary = (await screen.findByLabelText("各审核阶段节点汇总"));
    const screening = Array.from(summary.querySelectorAll(".stage-summary__item"))
      .find((item) => item.textContent?.includes("筛选期"));
    expect(screening).not.toBeUndefined();
    expect(screening).toHaveTextContent("6 个节点");
    expect(screening).toHaveTextContent("明确障碍 2");
    expect(screening).toHaveTextContent("当前节点缺口 2");
    expect(screening).toHaveTextContent("后续节点关注 2");
  });

  it("阶段聚焦：点击筛选期后只显示该阶段列，其余阶段列隐藏", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    await user.click(await screen.findByRole("button", { name: "筛选期" }));
    const table = await screen.findByRole("table");
    const headerTexts = within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent ?? "")
      .join("|");
    expect(headerTexts).toContain("筛选期");
    expect(headerTexts).not.toContain("预筛期");
    expect(headerTexts).not.toContain("基线/随机前");
    expect(window.location.hash).toContain("stage=screening");
    expect(
      screen.getByText(/当前范围：筛选期/),
    ).toBeInTheDocument();
  });

  it("状态筛选：明确障碍只保留 UAT-02 与 UAT-06", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    await user.click(await screen.findByRole("button", { name: /明确障碍 4/ }));
    const table = await screen.findByRole("table");
    const rows = rowsOfTable(table);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("UAT-02");
    expect(rows[1]).toHaveTextContent("UAT-06");
  });

  it("阻断程度排序：点击列头后明确障碍对象排在最前", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    await screen.findByRole("table");
    const sortButton = await screen.findByRole("button", { name: "阻断程度" });
    await user.click(sortButton);
    const table = await screen.findByRole("table");
    const firstRow = rowsOfTable(table)[0];
    expect(firstRow).toHaveTextContent("UAT-02");
    expect(firstRow).toHaveTextContent("明确障碍");
    expect(window.location.hash).toContain("sort=blocking");
  });

  it("直达节点：点击 UAT-03 筛选期单元格进入对应审核（URL 契约）", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    const openLink = await screen.findByRole("link", {
      name: "打开 UAT-03 筛选期审核",
    });
    await user.click(openLink);
    expect(window.location.hash).toBe(
      "#/workbench?episode=episode-uat-03-screening-gap_conflict",
    );
  });

  it("受试者代号筛选：输入 UAT-01 只保留该受试者", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    const input = await screen.findByLabelText("按受试者代号筛选");
    await user.type(input, "UAT-01");
    const table = await screen.findByRole("table");
    expect(rowsOfTable(table)).toHaveLength(1);
    expect(table).toHaveTextContent("UAT-01");
    expect(table).not.toHaveTextContent("UAT-02");
  });

  it("勾选：选择一行显示已选数量，全选作用于当前筛选范围", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    const checkbox = await screen.findByRole("checkbox", {
      name: "选择 UAT-01",
    });
    await user.click(checkbox);
    expect(screen.getByText("已选择 1 位受试者（只处理明确勾选对象）")).toBeInTheDocument();
    const selectAll = screen.getByRole("checkbox", {
      name: "全选当前筛选范围",
    });
    await user.click(selectAll);
    expect(screen.getByText("已选择 8 位受试者（只处理明确勾选对象）")).toBeInTheDocument();
  });

  it("批量操作先核对明确范围，完成摘要不扩大勾选对象", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    await user.click(await screen.findByRole("checkbox", { name: "选择 UAT-03" }));
    await user.click(screen.getByRole("checkbox", { name: "选择 UAT-04" }));
    await user.click(screen.getByRole("button", { name: "批量回看审核摘要" }));
    const dialog = screen.getByRole("dialog", { name: "确认批量操作范围" });
    expect(dialog).toHaveTextContent("UAT-03");
    expect(dialog).toHaveTextContent("UAT-04");
    expect(dialog).not.toHaveTextContent("UAT-01");
    await user.click(screen.getByRole("button", { name: "确认回看" }));
    const result = screen.getByText("批量操作完成").closest("section");
    expect(result).toHaveTextContent("UAT-03、UAT-04");
    expect(result).not.toHaveTextContent("UAT-01");
    await user.click(screen.getByRole("button", { name: "阻断程度" }));
    expect(screen.getByText("已选择 2 位受试者（只处理明确勾选对象）")).toBeInTheDocument();
  });

  it("筛选无结果时显示空集合文案与清除筛选", async () => {
    const user = userEvent.setup();
    render(<ProjectBoardPage />);
    const input = await screen.findByLabelText("按受试者代号筛选");
    await user.type(input, "UAT-99");
    expect(
      await screen.findByText("当前没有符合条件的资料"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "清除筛选" }));
    expect(await screen.findByRole("table")).toBeInTheDocument();
  });
});
