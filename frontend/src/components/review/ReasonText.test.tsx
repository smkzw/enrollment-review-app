// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ReasonText } from "./ReasonText";

describe("判定依据分点", () => {
  it("不把连续分隔符显示成空标点条目，保留数字、单位和阴阳性符号", () => {
    render(<ReasonText text={"检验：0.05 IU/mL（阴性）；。\n；\n+\n-\n其余：未见记录。"} />);
    expect(screen.getAllByRole("listitem").map(item => item.textContent?.trim())).toEqual([
      "检验：0.05 IU/mL（阴性）；", "+", "-", "其余：未见记录。",
    ]);
    expect(screen.getByText("检验：").tagName).toBe("STRONG");
  });

  it("精简显示仍可展开完整说明，分隔符不增加说明条目", async () => {
    const user = userEvent.setup();
    render(<ReasonText compact text={"结果一致。；\n数值：1.58×10^9/L；归属：已核对。"} />);
    expect(screen.getByText("结果一致。")).toBeVisible();
    await user.click(screen.getByText("展开核对说明"));
    const details = screen.getByText("展开核对说明").closest("details")!;
    expect(within(details).getAllByRole("listitem").map(item => item.textContent?.trim())).toEqual([
      "数值：1.58×10^9/L；", "归属：已核对。",
    ]);
  });
});
