// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProtocolCategoryChangeRow } from "./ProtocolDiffChangeRow";

describe("ProtocolCategoryChangeRow", () => {
  it("既往事件和必需记录分开呈现，不把用途说明当患者已核实", () => {
    const { container } = render(<ProtocolCategoryChangeRow change={{ category: "logic", categoryLabel: "判断条件",
      stableRef: "EX-01a", kind: "component", previous: null,
      current: { kind: "predicate", predicate: { subject: "受试者", attribute: "既往事件", comparator: "exists",
        record_semantics: { target_kind: "event_history", record_obligation: "required",
          proposition_direction: "event_present", source_excerpts: ["既往事件须以规定记录核对"] } } },
    }} />);
    expect(screen.getByText("核对对象：既往事件或病史")).toBeInTheDocument();
    expect(screen.getByText("方案记录要求：需要规定的记录或书面判断")).toBeInTheDocument();
    expect(screen.getByText("用途依据：既往事件须以规定记录核对")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/record_semantics|event_history|event_present|已核实|已符合/);
  });
  it("明确显示记录选取和未核清的排序日期，不显示内部枚举", () => {
    const { container } = render(<ProtocolCategoryChangeRow change={{ category: "logic", categoryLabel: "判断条件",
      stableRef: "IN-01a", kind: "component", previous: null,
      current: { kind: "predicate", predicate: { subject: "受试者", attribute: "审核值", comparator: "gte", value: 7,
        unit: "分", source_computation: { operator: "mean", operator_ref: { statement_index: 0, quote: "均值" },
          input_refs: [{ statement_index: 0, quote: "最近三次记录" }], missing_policy: "not_specified",
          missing_ref: null, declared_input_count: { value: 3, number_text: "三", source: { statement_index: 0, quote: "最近三次记录" } },
          max_missing_count: null, input_selection: { mode: "latest_n", source: { statement_index: 0, quote: "最近三次记录" },
            ordering_basis: "unresolved", ordering_ref: null, window_refs: [] } } } },
    }} />);
    expect(screen.getByText("记录选取（待核对）：按原文规定取最近若干次")).toBeInTheDocument();
    expect(screen.getByText("排序依据（待核对）：排序日期尚未核清")).toBeInTheDocument();
    expect(screen.getByText("原文规定输入数量：3（三）")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/latest_n|ordering_basis|input_selection|unresolved/);
  });
  it("计算方法与逐字依据可见，不将方法保存说成已核实结果", () => {
    const { container } = render(<ProtocolCategoryChangeRow change={{
      category: "logic", categoryLabel: "判断条件", stableRef: "IN-01a", kind: "component", previous: null,
      current: { kind: "predicate", predicate: { subject: "受试者", attribute: "审核值", comparator: "gte",
        value: 7, unit: "分", source_computation: {
          operator: "mean", operator_ref: { statement_index: 0, quote: "均值" },
          input_refs: [{ statement_index: 0, quote: "最近三次记录" }],
          missing_policy: "not_specified", missing_ref: null, declared_input_count: null, max_missing_count: null,
        } } },
    }} />);
    expect(screen.getByText("计算方法：均值")).toBeInTheDocument();
    expect(screen.getByText("计算依据：最近三次记录")).toBeInTheDocument();
    expect(screen.getByText("原文方法已保存；所用记录与计算结果尚未核实，不能据此作出结论。")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/source_computation|statement_index|not_specified/);
  });
  it("显示已保存的完整期间限定，不把混合阶段缩成研究期间", () => {
    const excerpt = "准备阶段及干预阶段（第六次访视之前）";
    const { container } = render(<ProtocolCategoryChangeRow change={{
      category: "time_window", categoryLabel: "时间窗", stableRef: "EX-01a", kind: "component",
      previous: [{ scope: "main", time_constraint: null, occurrence_window: null,
        prospective_window: null, prospective_period: { period: "study_period" } }],
      current: [{ scope: "main", time_constraint: null, occurrence_window: null,
        prospective_window: null, prospective_period: { kind: "source_defined", source_excerpts: [excerpt] } }],
    }} />);
    expect(screen.getByText("主条件：研究期间")).toBeInTheDocument();
    expect(screen.getByText(`主条件：按原文限定期间核对：${excerpt}`)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/source_defined|source_excerpts/);
  });

  it("缺少原文依据时不伪称期间已核实", () => {
    render(<ProtocolCategoryChangeRow change={{
      category: "time_window", categoryLabel: "时间窗", stableRef: "EX-01a", kind: "component",
      previous: null,
      current: [{ scope: "main", time_constraint: null, occurrence_window: null,
        prospective_window: null, prospective_period: { kind: "source_defined", source_excerpts: [] } }],
    }} />);
    expect(screen.getByText("主条件：期间依据尚不完整")).toBeInTheDocument();
  });

  it("把复合逻辑显示为医学监查员可读的中文，不暴露内部结构", () => {
    const { container } = render(
      <ProtocolCategoryChangeRow
        change={{
          category: "logic",
          categoryLabel: "逻辑",
          stableRef: "IN-01a",
          kind: "component",
          previous: {
            kind: "predicate",
            predicate: {
              subject: "受试者",
              attribute: "age",
              comparator: "gte",
              value: 18,
              unit: "year",
            },
          },
          current: {
            kind: "logical",
            operator: "all",
            children: [
              {
                kind: "predicate",
                predicate: {
                  subject: "受试者",
                  attribute: "age",
                  comparator: "gte",
                  value: 18,
                  unit: "year",
                },
              },
              {
                kind: "predicate",
                predicate: {
                  subject: "受试者",
                  attribute: "age",
                  comparator: "lte",
                  value: 65,
                  unit: "year",
                },
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("以下条件全部满足：")).toBeInTheDocument();
    expect(screen.getAllByText("受试者：年龄 大于或等于 18 岁")).toHaveLength(2);
    expect(screen.getByText("受试者：年龄 小于或等于 65 岁")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/predicate|operator|kind|children/);
  });

  it("把时间锚点和阶段显示为中文", () => {
    const { container } = render(
      <ProtocolCategoryChangeRow
        change={{
          category: "time_window",
          categoryLabel: "时间窗",
          stableRef: "EX-06f",
          kind: "component",
          previous: [{
            scope: "main",
            time_constraint: null,
            occurrence_window: null,
            prospective_window: null,
            prospective_period: null,
          }],
          current: [
            {
              scope: "main",
              time_constraint: {
                anchor_type: "randomization_date",
                direction: "before",
                upper_bound_days: 28,
              },
              occurrence_window: null,
              prospective_window: null,
              prospective_period: null,
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("主条件：未设置时间要求")).toBeInTheDocument();
    expect(screen.getByText("主条件：随机日期前28天内")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/anchor_type|upper_bound_days/);
  });

  it("完整显示否定逻辑、例外时间窗、日历单位和同日锚点", () => {
    render(
      <ProtocolCategoryChangeRow
        change={{
          category: "time_window",
          categoryLabel: "时间窗",
          stableRef: "EX-12a",
          kind: "component",
          previous: [
            {
              scope: "exception",
              time_constraint: {
                anchor_type: "baseline_date",
                direction: "on",
              },
              occurrence_window: null,
              prospective_window: null,
              prospective_period: null,
            },
          ],
          current: [
            {
              scope: "exception",
              time_constraint: {
                anchor_type: "randomization_date",
                direction: "before",
                lower_bound: { value: 4, unit: "week" },
                upper_bound: { value: 6, unit: "month" },
                half_life_multiplier: 5,
              },
              occurrence_window: null,
              prospective_window: null,
              prospective_period: null,
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("例外条件：基线日期当日")).toBeInTheDocument();
    expect(
      screen.getByText("例外条件：随机日期前至少4周且不超过6个月；同时核对5个半衰期"),
    ).toBeInTheDocument();
  });

  it("否定逻辑不会显示成全部满足", () => {
    render(
      <ProtocolCategoryChangeRow
        change={{
          category: "logic",
          categoryLabel: "逻辑",
          stableRef: "EX-01a",
          kind: "component",
          previous: null,
          current: {
            kind: "logical",
            operator: "not",
            children: [
              {
                kind: "predicate",
                predicate: {
                  subject: "研究者判断",
                  attribute: "exception_confirmed",
                  comparator: "eq",
                  value: true,
                  unit: "unitless",
                },
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("以下条件不成立：")).toBeInTheDocument();
    expect(screen.queryByText("以下条件全部满足：")).not.toBeInTheDocument();
  });
});
