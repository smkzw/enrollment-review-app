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
