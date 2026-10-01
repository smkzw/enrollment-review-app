import { describe, expect, it } from "vitest";
import { reviewConditionNotes } from "./reviewConditionNotes";

describe("方案采用要求与病例资料分开说明", () => {
  it("持续期计算未支持不伪装成缺少记录或研究者判断", () => {
    const text = reviewConditionNotes(["interval_calculation_unsupported"]).join(" ");
    expect(text).toContain("系统尚不能");
    expect(text).toContain("不表示受试者缺少记录");
    expect(text).toContain("不需要因此补研究者判断");
    expect(text).not.toContain("interval_calculation");
  });
  it("不把规则对应未完成写成病例缺失或让用户反复上传", () => {
    const text = reviewConditionNotes(["source_policy_unattributed", "source_policy_missing"]);
    expect(text.join(" ")).toContain("方案");
    expect(text.join(" ")).toContain("不是受试者资料缺失");
    expect(text.join(" ")).toContain("不需要因此重复上传原件");
    expect(text.join(" ")).not.toMatch(/source_policy|unattributed/);
  });

  it("普通原件未核与方案要求不清不混为一条说明", () => {
    const text = reviewConditionNotes(["source_policy_ambiguous", "observation_unverified"]);
    expect(text).toHaveLength(2);
    expect(text[0]).toContain("资料采用要求");
    expect(text[1]).toContain("原始资料");
  });
});
