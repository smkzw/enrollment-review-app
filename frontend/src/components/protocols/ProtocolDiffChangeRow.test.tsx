// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProtocolCategoryChangeRow } from "./ProtocolDiffChangeRow";

describe("ProtocolCategoryChangeRow", () => {
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
