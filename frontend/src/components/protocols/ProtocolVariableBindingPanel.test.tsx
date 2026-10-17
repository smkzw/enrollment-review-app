// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { decodeBindingView } from "../../api/protocolVariables";
import { ProtocolVariableBindingPanel } from "./ProtocolVariableBindingPanel";

const age = { variable_id: "age", label_zh: "年龄", value_type: "number", canonical_unit: "周岁",
  unit_conversions: {}, plausible_range: [0, 130], aliases_zh: [], domain: "demographic" };
const view = { job_id: "job", draft_revision_id: "revision", variables: [age], predicates: [{
  component_id: "component", predicate_id: "predicate", official_code: "IN-01", label: "年龄",
  variable_id: null, requirements: [{ requirement_id: "requirement", description: "年龄依据" }] }] };
afterEach(() => vi.unstubAllGlobals());

it("错修订不展示；选择按实际条件与要求保存，不改变原条件", async () => {
  expect(() => decodeBindingView(view, "job", "other")).toThrow();
  const saved = vi.fn();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(view)))
    .mockImplementationOnce(async (_url, options) => {
      expect(options.method).toBe("PUT");
      expect(JSON.parse(options.body)).toEqual({ expected_revision_id: "revision", proposal: {
        variables: [], bindings: [{ component_id: "component", predicate_id: "predicate",
          requirement_id: "requirement", variable_id: "age" }] } });
      return new Response("{}");
    });
  vi.stubGlobal("fetch", fetcher);
  render(<ProtocolVariableBindingPanel jobId="job" revisionId="revision" onSaved={saved} />);
  await userEvent.click(await screen.findByText("1 个判断条件"));
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "IN-01 年龄对应数据" }), "age");
  await userEvent.click(screen.getByRole("button", { name: "保存项目选择" }));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
});

it("模型建议不自动保存，重复已有定义只展示一次", async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(view)))
    .mockResolvedValueOnce(new Response(JSON.stringify({ proposal: { variables: [age], bindings: [] } })));
  vi.stubGlobal("fetch", fetcher);
  render(<ProtocolVariableBindingPanel jobId="job" revisionId="revision" onSaved={vi.fn()} />);
  await screen.findByText("1 个判断条件");
  await userEvent.click(screen.getByRole("button", { name: "建议对应项目" }));
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  await userEvent.click(screen.getByText("1 个判断条件"));
  expect(screen.getAllByRole("option", { name: "年龄（周岁）" })).toHaveLength(1);
});

it("一次选择保留同一条件的多个节点资料要求", async () => {
  const multiple = structuredClone(view);
  multiple.predicates[0].requirements.push({ requirement_id: "baseline", description: "基线年龄依据" });
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(multiple)))
    .mockImplementationOnce(async (_url, options) => {
      expect(JSON.parse(options.body).proposal.bindings.map((b: { requirement_id: string }) => b.requirement_id))
        .toEqual(["requirement", "baseline"]);
      return new Response("{}");
    });
  vi.stubGlobal("fetch", fetcher);
  const saved = vi.fn();
  render(<ProtocolVariableBindingPanel jobId="job" revisionId="revision" onSaved={saved} />);
  await userEvent.click(await screen.findByText("1 个判断条件"));
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "IN-01 年龄对应数据" }), "age");
  await userEvent.click(screen.getByRole("button", { name: "保存项目选择" }));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
});

it("判断背景按需打开，来源不明或串到其他子项时拒绝", async () => {
  const context = { component: { parent_source_text: "采用当次评分，回顾评分不用于本项。", component_source_text: "单项评分至少2分。" } };
  const current = { ...view, source_context: context };
  expect(() => decodeBindingView({ ...view, source_context: { other: context.component } }, "job", "revision")).toThrow("判断背景");
  expect(() => decodeBindingView({ ...view, source_context: { component: null } }, "job", "revision")).toThrow("判断背景");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(current))));
  render(<ProtocolVariableBindingPanel jobId="job" revisionId="revision" onSaved={vi.fn()} />);
  await userEvent.click(await screen.findByText("1 个判断条件"));
  const details = screen.getByText("查看判断背景").closest("details")!;
  expect(details.open).toBe(false);
  await userEvent.click(screen.getByText("查看判断背景"));
  expect(details.open).toBe(true);
  expect(screen.getByText("单项评分至少2分。")).toBeInTheDocument();
  await userEvent.click(screen.getByText("完整条款"));
  expect(screen.getByText("采用当次评分，回顾评分不用于本项。")).toBeVisible();
});

it("可创建独立评分项目并只改变所选对应，不混入病史类别", async () => {
  const saved = vi.fn();
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(view)))
    .mockImplementationOnce(async (_url, options) => {
      const proposal = JSON.parse(options.body).proposal;
      expect(proposal.variables).toHaveLength(1);
      expect(proposal.variables[0]).toMatchObject({ label_zh: "当次量表单项", value_type: "number", domain: "score",
        canonical_unit: "分", plausible_range: [0, 5] });
      expect(proposal.bindings[0].variable_id).toBe(proposal.variables[0].variable_id);
      return new Response("{}");
    });
  vi.stubGlobal("fetch", fetcher);
  render(<ProtocolVariableBindingPanel jobId="job" revisionId="revision" onSaved={saved} />);
  await screen.findByText("1 个判断条件");
  await userEvent.click(screen.getByText("新增本项目数据"));
  await userEvent.type(screen.getByRole("textbox", { name: "项目名称" }), "当次量表单项");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "内容类型" }), "number");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "数据类别" }), "score");
  await userEvent.type(screen.getByRole("textbox", { name: "单位" }), "分");
  await userEvent.type(screen.getByRole("spinbutton", { name: "合理范围下限" }), "0");
  await userEvent.type(screen.getByRole("spinbutton", { name: "合理范围上限" }), "5");
  await userEvent.click(screen.getByRole("button", { name: "加入项目清单" }));
  await userEvent.click(screen.getByText("1 个判断条件"));
  const select = screen.getByRole("combobox", { name: "IN-01 年龄对应数据" });
  const option = screen.getByRole("option", { name: "当次量表单项（分）" }) as HTMLOptionElement;
  await userEvent.selectOptions(select, option.value);
  await userEvent.click(screen.getByRole("button", { name: "保存项目选择" }));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  expect(fetcher).toHaveBeenCalledTimes(2);
});

it("换方案时不沿用未保存的项目，也不被旧请求一直锁住", async () => {
  let finishOld!: (value: Response) => void;
  const nextView = { ...view, job_id: "next", draft_revision_id: "next-revision" };
  const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify(view)))
    .mockImplementationOnce(() => new Promise<Response>(resolve => { finishOld = resolve; }))
    .mockResolvedValueOnce(new Response(JSON.stringify(nextView)));
  vi.stubGlobal("fetch", fetcher);
  const saved = vi.fn();
  const rendered = render(<ProtocolVariableBindingPanel jobId="job" revisionId="revision" onSaved={saved} />);
  await screen.findByText("1 个判断条件");
  await userEvent.click(screen.getByText("新增本项目数据"));
  await userEvent.type(screen.getByRole("textbox", { name: "项目名称" }), "旧项目未存内容");
  await userEvent.selectOptions(screen.getByRole("combobox", { name: "数据类别" }), "score");
  await userEvent.click(screen.getByRole("button", { name: "建议对应项目" }));
  rendered.rerender(<ProtocolVariableBindingPanel jobId="next" revisionId="next-revision" onSaved={saved} />);
  await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(3));
  await waitFor(() => expect(screen.getByRole("button", { name: "建议对应项目" })).toBeEnabled());
  expect(screen.getByRole("textbox", { name: "项目名称" })).toHaveValue("");
  expect(screen.getByRole("combobox", { name: "数据类别" })).toHaveValue("history");
  finishOld(new Response(JSON.stringify({ proposal: { variables: [age], bindings: [] } })));
  await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  expect(saved).not.toHaveBeenCalled();
});
