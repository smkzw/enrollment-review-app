// @vitest-environment jsdom
/**
 * 行动中心组件测试：责任方/原因/可关闭证据/到期节点、人工确认理由必填、
 * 确认记录与本次试用差异（UAT-P1-09/10 语义）。
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, beforeEach } from "vitest";
import { ActionsPage } from "./ActionsPage";

describe("行动中心", () => {
  beforeEach(() => {
    window.location.hash = "";
    window.sessionStorage.clear();
  });

  it("列表展示对象、缺口、责任方、关联规则与阻断程度", async () => {
    render(<ActionsPage />);
    const list = (await screen.findByRole("heading", { name: /行动列表/ }))
      .closest("section");
    expect(list).not.toBeNull();
    expect(list).toHaveTextContent("补充当前审核节点未记录的关键信息");
    expect(list).toHaveTextContent("责任方：研究者方");
    expect(list).toHaveTextContent("关联规则：IN-01");
    expect(list).toHaveTextContent("阻断");
  });

  it("点击行动行打开详情：可关闭证据、到期节点与关联规则判断", async () => {
    const user = userEvent.setup();
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    const row = screen
      .getAllByRole("button")
      .find(
        (button) =>
          button.textContent?.includes("UAT-03") &&
          button.textContent?.includes("补充当前审核节点未记录的关键信息") &&
          button.textContent?.includes("筛选期"),
      );
    expect(row).not.toBeUndefined();
    await user.click(row as HTMLElement);
    const detail = await screen.findByRole("complementary", { name: "行动详情" });
    expect(detail).toHaveTextContent("什么资料可以关闭");
    expect(detail).toHaveTextContent("到期节点");
    expect(detail).toHaveTextContent("筛选期");
    // 关联规则当前判断来自该节点审核详情
    expect(
      await screen.findByText("关联规则当前判断"),
    ).toBeInTheDocument();
  });

  it("人工确认理由为空时提示必填", async () => {
    const user = userEvent.setup();
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    const row = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("补充当前审核节点未记录的关键信息"));
    await user.click(row as HTMLElement);
    await user.click(await screen.findByRole("button", { name: "核对确认内容" }));
    expect(
      await screen.findByText("请填写确认理由后再确认关闭。"),
    ).toBeInTheDocument();
  });

  it("填写理由后确认：显示不可变记录与本次差异，且不写入项目资料", async () => {
    const user = userEvent.setup();
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    const row = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("补充当前审核节点未记录的关键信息"));
    await user.click(row as HTMLElement);
    const reason = await screen.findByLabelText("确认理由（必填）");
    await user.type(reason, "已核对筛选病历与知情同意，确认年龄记录来源可靠。");
    await user.click(screen.getByRole("button", { name: "核对确认内容" }));
    const dialog = await screen.findByRole("dialog", { name: "确认本次人工处理" });
    expect(dialog).toHaveTextContent("UAT-03 · IN-01");
    expect(dialog).toHaveTextContent("关闭行动不等于规则通过");
    await user.click(screen.getByRole("button", { name: "确认关闭并重新核对" }));
    expect(await screen.findByText(/人工操作记录（本次试用）/)).toBeInTheDocument();
    expect(screen.getByText(/理由：已核对筛选病历与知情同意/)).toBeInTheDocument();
    expect(screen.getByText(/操作者：本机用户/)).toBeInTheDocument();
    // 本次确认前后差异与诚实说明
    expect(screen.getByText("本次确认前后差异")).toBeInTheDocument();
    expect(screen.getByText(/不等于规则自动通过/)).toBeInTheDocument();
    expect(screen.getByText(/未写入项目资料/)).toBeInTheDocument();
  });

  it("重新打开会追加记录而不删除此前确认", async () => {
    const user = userEvent.setup();
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    const reason = await screen.findByLabelText("确认理由（必填）");
    await user.type(reason, "研究者已补充书面判断并完成签名日期。");
    await user.click(screen.getByRole("button", { name: "核对确认内容" }));
    await user.click(screen.getByRole("button", { name: "确认关闭并重新核对" }));
    await user.click(await screen.findByRole("button", { name: "重新打开" }));
    const records = screen.getByRole("heading", { name: /人工操作记录/ }).closest("section");
    expect(records).toHaveTextContent("确认关闭");
    expect(records).toHaveTextContent("重新打开");
    expect(records).toHaveTextContent("保留此前确认记录");
  });

  it("无 URL 参数时默认选中首项并显示为什么/谁/补什么/可关闭证据", async () => {
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    const detail = await screen.findByRole("complementary", {
      name: "行动详情",
    });
    // 默认选中排序后的首项（UAT-03 的阻断行动）
    expect(detail).toHaveTextContent("UAT-03");
    expect(detail).toHaveTextContent("谁负责");
    expect(detail).toHaveTextContent("需要补什么");
    expect(detail).toHaveTextContent("什么资料可以关闭");
  });

  it("按状态筛选：全部/待处理切换不改变行动总数语义", async () => {
    const user = userEvent.setup();
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    const allCount = screen
      .getByRole("heading", { name: /行动列表/ })
      .parentElement?.querySelector(".section-count")?.textContent;
    await user.click(screen.getByRole("button", { name: "已人工确认关闭" }));
    const closedCount = screen
      .getByRole("heading", { name: /行动列表/ })
      .parentElement?.querySelector(".section-count")?.textContent;
    expect(allCount).not.toBe(closedCount);
  });

  it("溯源提醒为独立类别：可单独筛选出全部溯源行动（I1）", async () => {
    const user = userEvent.setup();
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    await user.click(screen.getByRole("button", { name: "溯源提醒" }));
    const list = screen
      .getByRole("heading", { name: /行动列表/ })
      .closest("section");
    expect(list).not.toBeNull();
    // 四例溯源行动：UAT-01 与 UAT-05 的筛选期/基线期
    expect(list).toHaveTextContent("UAT-01");
    expect(list).toHaveTextContent("UAT-05");
    expect(list).toHaveTextContent("核对当前病历转述所依据的原始来源");
    const countEl = screen
      .getByRole("heading", { name: /行动列表/ })
      .parentElement?.querySelector(".section-count");
    expect(countEl?.textContent).toBe("4");
    // 阻断行动不被混入
    expect(list).not.toHaveTextContent("补充当前审核节点未记录的关键信息");
  });

  it("溯源提醒不并入阻断或笼统关注（I1）", async () => {
    const user = userEvent.setup();
    render(<ActionsPage />);
    await screen.findByRole("heading", { name: /行动列表/ });
    // 阻断当前节点筛选不含溯源行动
    await user.click(screen.getByRole("button", { name: "阻断当前节点" }));
    const list = screen
      .getByRole("heading", { name: /行动列表/ })
      .closest("section");
    expect(list).not.toHaveTextContent("核对当前病历转述所依据的原始来源");
    // 不阻断需关注筛选也不含溯源行动（溯源是独立类别，不是笼统关注）
    await user.click(screen.getByRole("button", { name: "不阻断，需关注" }));
    expect(list).not.toHaveTextContent("核对当前病历转述所依据的原始来源");
    // 全部类别下溯源行动可见，且标记为「无」而非「阻断」
    await user.click(screen.getByRole("button", { name: "全部程度" }));
    await user.click(screen.getByRole("button", { name: "全部类别" }));
    const provenanceRow = screen
      .getAllByRole("button")
      .find((button) =>
        button.textContent?.includes("核对当前病历转述所依据的原始来源"),
      );
    expect(provenanceRow).not.toBeUndefined();
    expect(provenanceRow?.textContent).not.toContain("阻断");
  });

  it("行动中心与今日工作口径有中文说明（I5）", async () => {
    render(<ActionsPage />);
    expect(
      await screen.findByText(/行动中心统计全部行动/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/今日工作只统计当前审核节点到期且需关注或阻断的开放行动/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/「溯源提醒」是独立类别/),
    ).toBeInTheDocument();
  });
});
