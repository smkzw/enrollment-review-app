import { describe, expect, it } from "vitest";
import { administrativeLineRanges, clinicalReadingText, isAdministrativeRange } from "./ocrDisplayScope";

describe("临床阅读范围", () => {
  it("只收起纯行政行，数值单位、临床日期、病史与未知字段保持原文", () => {
    const clinical = "肌酐 79 μmol/L\n采样时间：2025-08-08\n处方：药物每日一次\n未知字段：51";
    const source = `报告医师：王医生\n第 1 页 共 2 页\n地址：示例街道389号\n联系电话：0311-12345678\n${clinical}`;
    expect(clinicalReadingText(source)).toBe(clinical);
    expect(source).toContain("报告医师：王医生");
    const offset = source.indexOf("0311");
    expect(isAdministrativeRange({ textStart: offset, textEnd: offset + 4 }, administrativeLineRanges(source))).toBe(true);
    expect(isAdministrativeRange({ textStart: source.indexOf("79"), textEnd: source.indexOf("79") + 2 }, administrativeLineRanges(source))).toBe(false);
  });

  it("行政标签旁的判断、混合结果、手写批注及跨行范围不收起", () => {
    const source = "审核医生：李某 NCS\n报告医师：王某，结果异常\n打印日期：研究者判断记录\n申请医生：原文用药已完成\n医师姓名：未知标签\n报告医生：普通姓名";
    expect(clinicalReadingText(source)).toBe(source.slice(0, source.lastIndexOf("\n")));
    const ranges = administrativeLineRanges(source);
    expect(ranges).toHaveLength(1);
    expect(isAdministrativeRange({ textStart: ranges[0].textStart - 1, textEnd: source.length }, ranges)).toBe(false);
    expect(isAdministrativeRange({ textStart: ranges[0].textStart, textEnd: ranges[0].textStart }, ranges)).toBe(false);
  });
});
