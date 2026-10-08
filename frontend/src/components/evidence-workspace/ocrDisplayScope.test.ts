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
    const source = "审核医生：李某 NCS\n报告医师：王某，结果异常\n打印日期：研究者判断记录\n申请医生：原文用药已完成\n未知标签：未知含义\n报告医生：普通姓名";
    expect(clinicalReadingText(source)).toBe(source.slice(0, source.lastIndexOf("\n")));
    const ranges = administrativeLineRanges(source);
    expect(ranges).toHaveLength(1);
    expect(isAdministrativeRange({ textStart: ranges[0].textStart - 1, textEnd: source.length }, ranges)).toBe(false);
    expect(isAdministrativeRange({ textStart: ranges[0].textStart, textEnd: ranges[0].textStart }, ranges)).toBe(false);
  });

  it("收起普通人员与网址页脚，保留原文偏移及旁边的临床记录", () => {
    const source = "主检：甲 审核:乙 主检实验室:某实验室\n网址: example.test 电话:12345\n医师姓名：丙\n检验人员：丁\n第(1)页 共9页\n核心项目 3.2 mmol/L\n报告日期：2026-01-03";
    expect(clinicalReadingText(source)).toBe("核心项目 3.2 mmol/L\n报告日期：2026-01-03");
    const start = source.indexOf("example.test");
    expect(isAdministrativeRange({ textStart: start, textEnd: start + 12 }, administrativeLineRanges(source))).toBe(true);
    expect(source).toContain("主检：甲");
  });

  it("普通标签同一行有临床时点、患者信息、单位或判断时不省略", () => {
    const source = "审核：甲 报告日期：2026-01-03\n主检：乙 NCS\n医师姓名：丙 访视：筛选期\n网址：example.test，参考值：4\n主检：丁 标本：血清\n审核：戊 年龄：51\n检验员：己，读数 79 μmol/L";
    expect(clinicalReadingText(source)).toBe(source);
    expect(administrativeLineRanges(source)).toEqual([]);
  });
});
