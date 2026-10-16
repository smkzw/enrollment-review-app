// @vitest-environment jsdom
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { decodeRuleReviews } from "../../api/protocolRuleReviews";
import { ProtocolRuleReviewPanel } from "./ProtocolRuleReviewPanel";
import { ProtocolJobFlow } from "./ProtocolJobFlow";
import { createProtocolWorkbenchStub, setProtocolWorkbenchRepository, PROTOCOL_DEMO_JOB_ID } from "../../api/protocolWorkbenchRepository";
import { protocolSessionFixtures } from "../../fixtures/protocol-deconstruction-workbench";

const hash = "a".repeat(64);
const entry = { official_code: "IN-01", kind: "rule", label: "年龄要求", rule_content_hash: hash,
  source_refs: ["source-1"], issue_refs: ["component-1"], review: null };
const initial = { job_id: "job", draft_revision_id: "revision", operator_name: "王医学经理",
  all_reviewed: false, entries: [entry], history: [] };
const integrity = { jobId: "job", publishable: true, blockingCount: 0, reviewCount: 0, reminderCount: 1,
  summary: "可审定", checks: [], issues: [{ issueCode: "hint", checkName: "numeric", level: "提醒",
    problem: "请核对年龄依据", impact: "年龄判断", nextAction: "查看原文", affectedRefs: ["component-1"], repairScope: [] }] };
const sources = { jobId: "job", snapshotId: "snapshot", selectedPhase: "phase_iii" as const,
  selectedPhaseLabel: "III期", sourceSpans: {}, sourceMaterials: {} };

afterEach(() => { vi.unstubAllGlobals(); setProtocolWorkbenchRepository(createProtocolWorkbenchStub()); });
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
});
describe("逐条审定", () => {
  it.each(["all_members", "qualified", null])("用药审定及集中确认可查看同版节点、类别、例外与时间：%s", async classScope => {
    const medicationEntry = { ...entry, official_code: "med:fixture", kind: "medication", label: "药物甲限制" };
    const full = { ...initial, entries: [medicationEntry] };
    const supplement = { selection_sha256: hash, input_sha256: hash, structure_sha256: hash,
      drug_classes: { fixture: ["药物甲", "药物乙"] }, sources: [], source_dispositions: [], medications: [{
        item_id: medicationEntry.official_code, drug_text: "药物甲限制", drug_class_id: "fixture", class_scope: classScope,
        period: "study_period", window: null, applicable_stages: ["screening", "baseline"],
        exception_excerpt: "本条明确例外", unresolved_reason: null, source_quotes: [], applies_to_rule: null,
      }] };
    const fetcher = vi.fn(async (url: RequestInfo | URL) => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : full)));
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources}
      content={{ scope_supplement: supplement }} onReady={vi.fn()} />);
    const checkbox = await screen.findByRole("checkbox", { name: "选择药物甲限制（筛选、基线）" });
    expect(within(screen.getByRole("list", { name: "审定条目" })).getByText("筛选、基线")).toBeInTheDocument();
    const logic = screen.getByRole("region", { name: "逻辑解析" });
    expect(within(logic).getByText("整个研究期间")).toBeInTheDocument();
    expect(within(logic).getByText(classScope === "all_members" ? "本条适用于该类全部药物"
      : classScope === "qualified" ? "另有给药途径、制剂等限定" : "尚未核清")).toBeInTheDocument();
    const names = within(logic).getByText("2 个药名").closest("details")!;
    expect(names).not.toHaveAttribute("open");
    await userEvent.click(within(names).getByText("2 个药名"));
    expect(within(names).getByText("药物乙")).toBeVisible();
    await userEvent.click(checkbox);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "builder_verification");
    await userEvent.click(screen.getByRole("button", { name: "批准所选 1 项" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("筛选、基线");
    await userEvent.click(within(dialog).getByText("查看限制范围与例外"));
    expect(within(dialog).getByText("本条明确例外")).toBeVisible();
    expect(within(dialog).getByText("整个研究期间")).toBeVisible();
    expect(fetcher.mock.calls.every(([url]) => !String(url).endsWith("/publish"))).toBe(true);
  });
  it("旧版缺类别表显示未保存，不编造零成员；无节点条目不显示空括号", async () => {
    const medicationEntry = { ...entry, official_code: "med:old", kind: "medication", label: "旧药物限制" };
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL) => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] }
      : { ...initial, entries: [medicationEntry] }))));
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={vi.fn()}
      content={{ scope_supplement: { selection_sha256: hash, input_sha256: hash, structure_sha256: hash,
        sources: [], source_dispositions: [], medications: [{ item_id: "med:old", drug_text: "旧药物限制",
          drug_class_id: "old-class", class_scope: null, window: null, period: null, applicable_stages: [],
          exception_excerpt: null, unresolved_reason: null, source_quotes: [], applies_to_rule: null }] } }} />);
    await screen.findByRole("checkbox", { name: "选择旧药物限制" });
    expect(screen.getByText("本版未保存类别成员")).toBeInTheDocument();
    expect(screen.queryByText("0 个药名")).not.toBeInTheDocument();
  });
  it("未改条目保持审定，默认只列剩余项，不发起重复批准", async () => {
    const retained = { record_id: "retained", official_code: "IN-01", rule_content_hash: hash,
      reviewer_kind: "medical_manager", reviewed_by: "王医学经理", reviewed_at: "2026-10-12T00:00:00Z",
      action: "approved", note: null, result_variables: [] };
    const fetcher = vi.fn(async (url: RequestInfo | URL, _options?: RequestInit) => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] }
      : { ...initial, entries: [{ ...entry, review: retained }, { ...entry, official_code: "IN-02", label: "病史要求" }],
          history: [retained] })));
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={vi.fn()} />);
    await screen.findByText("待审定 1 项 · 已审定 1 项");
    expect(screen.queryByText("已审定且内容未变的条目无需重复批准。")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("选择IN-01")).not.toBeInTheDocument();
    expect(screen.getByLabelText("选择IN-02")).toBeInTheDocument();
    expect(fetcher.mock.calls.every(([, options]) => options?.method === "GET")).toBe(true);
  });
  it("拒绝错任务、过期内容、重复条目与虚假的全部已审定状态", () => {
    expect(decodeRuleReviews(initial, "job").all_reviewed).toBe(false);
    expect(() => decodeRuleReviews(initial, "other")).toThrow();
    expect(() => decodeRuleReviews({ ...initial, all_reviewed: true }, "job")).toThrow();
    expect(() => decodeRuleReviews({ ...initial, entries: [entry, entry] }, "job")).toThrow();
    const review = { record_id: "record", official_code: "IN-01", rule_content_hash: "b".repeat(64),
      reviewer_kind: "builder_verification", reviewed_by: "构建者（验证）", reviewed_at: "2026-10-12T00:00:00Z",
      action: "approved", note: null, result_variables: [] };
    expect(() => decodeRuleReviews({ ...initial, entries: [{ ...entry, review }] }, "job")).toThrow();
    const copied = { ...initial, all_reviewed: true, entries: [{ ...entry, review, reviewed_content_hash: hash }], history: [review] };
    expect(decodeRuleReviews(copied, "job").entries[0].review?.rule_content_hash).toBe("b".repeat(64));
    expect(() => decodeRuleReviews({ ...copied, entries: [{ ...entry, review, reviewed_content_hash: "c".repeat(64) }] }, "job")).toThrow();
    expect(() => decodeRuleReviews({ ...copied, entries: [{ ...entry, review: { ...review, action: "revoked" }, reviewed_content_hash: hash }] }, "job")).toThrow();
  });

  it("显示对应提示，明确验证身份，并用内容与修订核对保存", async () => {
    const onReady = vi.fn();
    const fetcher = vi.fn(async (url, options) => {
      if (options.method === "GET") return new Response(JSON.stringify(String(url).endsWith("/variables")
        ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : initial));
      const payload = JSON.parse(options.body);
      expect(payload.reviewer_kind).toBe("builder_verification");
      expect(payload.expected_revision_id).toBe("revision");
      expect(payload.rule_content_hash).toBe(hash);
      const review = { record_id: "record", official_code: "IN-01", rule_content_hash: hash,
        reviewer_kind: "builder_verification", reviewed_by: "构建者（验证）", reviewed_at: "2026-10-12T00:00:00Z",
        action: "approved", note: null, result_variables: [] };
      return new Response(JSON.stringify({ ...initial, all_reviewed: true,
        entries: [{ ...entry, review }], history: [review] }));
    });
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={onReady} />);
    const hint = await screen.findByText("请核对年龄依据", { exact: true });
    expect(hint.closest("details")).not.toHaveAttribute("open");
    await userEvent.click(hint.closest("details")!.querySelector("summary")!);
    expect(hint.closest("details")).toHaveAttribute("open");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "builder_verification");
    expect(screen.getByText("构建者验证：发布为验证用规则包。")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "审定通过" }));
    await waitFor(() => expect(onReady).toHaveBeenLastCalledWith(true));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定范围" }), "approved");
    // The next-action selector is not the author of the saved approval.
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "medical_manager");
    expect(screen.getByText(/^构建者验证：已由/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "撤销审定" })).toBeEnabled();
  });

  it("分类、筛选、多选确认不会自动批准，批量保存明确绑定内容和身份", async () => {
    const second = { ...entry, official_code: "EX-01", label: "已知过敏", rule_content_hash: "b".repeat(64) };
    const full = { ...initial, entries: [entry, second] };
    const fetcher = vi.fn(async (_url, options) => {
      if (options.method === "GET") return new Response(JSON.stringify(String(_url).endsWith("/variables")
        ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : full));
      const payload = JSON.parse(options.body);
      expect(payload.entries.map((item: { official_code: string }) => item.official_code)).toEqual(["IN-01", "EX-01"]);
      expect(payload.expected_revision_id).toBe("revision");
      expect(payload.reviewer_kind).toBe("builder_verification");
      return new Response(JSON.stringify(full));
    });
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={vi.fn()} />);
    await screen.findByRole("checkbox", { name: "选择IN-01" });
    await userEvent.click(screen.getByRole("checkbox", { name: "选择IN-01" }));
    await userEvent.click(screen.getByRole("button", { name: "排除标准 1" }));
    expect(screen.getByRole("button", { name: "批准所选 0 项" })).toBeDisabled();
    expect(screen.queryByRole("checkbox", { name: "选择IN-01" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "全部 2" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "选择当前列表" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "builder_verification");
    await userEvent.click(screen.getByRole("button", { name: "批准所选 2 项" }));
    expect(screen.getByRole("dialog")).toHaveTextContent("构建者验证（仅供验证）");
    expect(fetcher.mock.calls.every(([, options]) => options.method === "GET")).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "确认批准所选" }));
    await screen.findByText("已保存2项审定。没有发布规则包。");
  });

  it("真实主入口只读取审定记录，不自动新建跨章作业", async () => {
    const base = createProtocolWorkbenchStub();
    setProtocolWorkbenchRepository({ ...base, kind: "http", getSession: async () => ({
      ...protocolSessionFixtures[PROTOCOL_DEMO_JOB_ID]!, draftRevisionId: "revision",
    }) });
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...initial, job_id: PROTOCOL_DEMO_JOB_ID })));
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolJobFlow jobId={PROTOCOL_DEMO_JOB_ID} componentParam={null} />);
    await screen.findByRole("heading", { name: "规则审定" });
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(fetcher.mock.calls.every(([url, options]) => /\/draft\/(reviews|variables)$/.test(String(url)) && options.method === "GET")).toBe(true);
    expect(screen.getByRole("button", { name: "发布" })).toBeDisabled();
  });
  it("实际条件树与原文分开展示，保留组合方向和中文项目名", async () => {
    const atom = (id: string, value: number) => ({ kind: "predicate", predicate: { predicate_id: id,
      subject: "受试者", attribute: "年龄", comparator: "gte", value, unit: "岁" } });
    const content = { proposed_rules: [{ rule_id: "r", official_code: "IN-01", kind: "inclusion", source_text: entry.label,
      components: [{ rule_component_id: "c", parent_rule_id: "r", display_code: "IN-01", title: "年龄范围", expression: {
        kind: "logical", operator: "all", children: [atom("p1", 18), { kind: "logical", operator: "any", children: [atom("p2", 30), atom("p3", 40)] }],
      }, exception_expression: null }] }] };
    vi.stubGlobal("fetch", vi.fn(async url => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : initial))));
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} content={content} onReady={vi.fn()} />);
    await screen.findByRole("region", { name: "逻辑解析" });
    expect([...screen.getByLabelText("逻辑解析").querySelectorAll(".expr-node__operator")]
      .map(node => node.textContent)).toEqual(["全部满足", "任一满足"]);
    expect(screen.getByText("年龄 大于等于 18 岁")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: "查找条目" }), "没有的条目");
    expect(screen.queryByRole("region", { name: "逻辑解析" })).not.toBeInTheDocument();
    expect(screen.getByText("当前范围没有条目。")).toBeInTheDocument();
  });
  it.each([
    ["本节点已有治疗及其相对应疗效", "本节点已有治疗及其相对应疗效"],
    ["对相对应治疗的疗效已明确否认", "对相对应治疗的疗效已明确否认"],
    ["treatment_response", "疗效记录"],
  ])("数据项目名不能覆盖完整条件或否定：%s", async (attribute, visible) => {
    const content = { proposed_rules: [{ rule_id: "r", official_code: "IN-01", kind: "inclusion", source_text: entry.label,
      components: [{ rule_component_id: "c", parent_rule_id: "r", display_code: "IN-01", title: "治疗及疗效核对",
        expression: { kind: "predicate", predicate: { predicate_id: "response", subject: "受试者", attribute,
          comparator: "exists", value: null, unit: null, requires_professional_judgment: true } }, exception_expression: null }] }] };
    vi.stubGlobal("fetch", vi.fn(async url => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [{ variable_id: "response", label_zh: "疗效记录",
            value_type: "boolean", domain: "history", canonical_unit: null, unit_conversions: {}, plausible_range: null, aliases_zh: [] }],
          predicates: [{ component_id: "c", predicate_id: "response", label: "疗效记录", official_code: "IN-01",
            variable_id: "response", requirements: [] }] } : initial))));
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources}
      content={content} onReady={vi.fn()} />);
    const region = await screen.findByRole("region", { name: "逻辑解析" });
    await waitFor(() => expect(region).toHaveTextContent(`${visible}：需有相应记录`));
    expect(region).toHaveTextContent("需要研究者判断");
    expect(region).not.toHaveTextContent("treatment_response");
  });
  it("多子项备选默认只展开第一组，其他组可独立打开且预览不保存审定", async () => {
    const atom = (id: string) => ({ kind: "predicate", predicate: { predicate_id: id,
      subject: "受试者", attribute: "年龄", comparator: "gte", value: 18, unit: "岁" } });
    const content = { proposed_rules: [{ rule_id: "r", official_code: "IN-01", kind: "inclusion", source_text: entry.label,
      components: ["a", "b"].map(id => ({ rule_component_id: id, parent_rule_id: "r", display_code: `IN-01${id}`,
        title: `条件${id}`, expression: { kind: "logical", operator: "any", children: [atom(`${id}1`), atom(`${id}2`)] },
        exception_expression: null })) }] };
    const fetcher = vi.fn(async (url: RequestInfo | URL, _options?: RequestInit) => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : initial)));
    const onEdit = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity}
      sources={sources} content={content} onReady={vi.fn()} onEdit={onEdit} />);
    await screen.findByLabelText("备选解释与处理");
    const advice = screen.getByLabelText("备选解释与处理");
    await userEvent.click(advice.querySelector("summary")!);
    const groups = [...container.querySelectorAll<HTMLDetailsElement>(".protocol-review-advice__group")];
    expect(groups).toHaveLength(2);
    expect(groups.map(group => group.open)).toEqual([true, false]);
    await userEvent.click(groups[1].querySelector("summary")!);
    expect(groups[1].open).toBe(true);
    expect(groups[1].querySelector("button")).toBeDisabled();
    await userEvent.click(groups[1].querySelector('input[type="radio"][value="0"]')!);
    expect(screen.getByRole("button", { name: "审定通过" })).toBeDisabled();
    await userEvent.click(groups[1].querySelector("button")!);
    expect(onEdit).toHaveBeenCalledWith("b", "all");
    expect(fetcher.mock.calls.every(([, options]) => !options || options.method === "GET")).toBe(true);
    await userEvent.click(groups[1].querySelector('input[type="radio"][value="1"]')!);
    expect(screen.getByRole("button", { name: "审定通过" })).toBeEnabled();
  });

  it("保留现有解释需要选择和明确确认；暂不审定不偷偷写批准", async () => {
    const review = { record_id: "confirmed", official_code: "IN-01", rule_content_hash: hash,
      reviewer_kind: "builder_verification", reviewed_by: "构建者验证", reviewed_at: "2026-10-14T00:00:00Z",
      action: "approved", note: null, result_variables: [] };
    const fetcher = vi.fn(async (url: RequestInfo | URL, options?: RequestInit) => {
      if (options?.method === "POST") {
        expect(String(url)).toMatch(/\/draft\/rules\/IN-01\/review$/);
        expect(JSON.parse(String(options.body))).toMatchObject({ reviewer_kind: "builder_verification",
          expected_revision_id: "revision", rule_content_hash: hash });
        return new Response(JSON.stringify({ ...initial, all_reviewed: true, entries: [{ ...entry, review }], history: [review] }));
      }
      return new Response(JSON.stringify(String(url).endsWith("/variables")
        ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] } : initial));
    });
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={vi.fn()} />);
    await userEvent.click(await screen.findByText("比较备选解释与手动调整"));
    await userEvent.click(screen.getByRole("radio", { name: "暂不审定，补充依据" }));
    await userEvent.click(screen.getByRole("button", { name: "确认暂不审定" }));
    expect(screen.getByText("本条保留待审，未改变现有解释。")).toBeInTheDocument();
    expect(fetcher.mock.calls.every(([, options]) => options?.method !== "POST")).toBe(true);
    await userEvent.click(screen.getByRole("radio", { name: "核对原文后保留现有解释" }));
    expect(fetcher.mock.calls.every(([, options]) => options?.method !== "POST")).toBe(true);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "审定身份" }), "builder_verification");
    await userEvent.click(screen.getByRole("button", { name: "确认现有解释并审定本条" }));
    await screen.findByText("该条审定已保存。没有发布规则包。");
    expect(fetcher.mock.calls.filter(([, options]) => options?.method === "POST")).toHaveLength(1);
  });

  it("切换条目不会让未保存的选择被集中批准", async () => {
    const second = { ...entry, official_code: "IN-02", label: "病史要求" };
    const fetcher = vi.fn(async (url: RequestInfo | URL, _options?: RequestInit) => new Response(JSON.stringify(String(url).endsWith("/variables")
      ? { job_id: "job", draft_revision_id: "revision", variables: [], predicates: [] }
      : { ...initial, entries: [entry, second] })));
    vi.stubGlobal("fetch", fetcher);
    render(<ProtocolRuleReviewPanel jobId="job" revisionId="revision" integrity={integrity} sources={sources} onReady={vi.fn()} />);
    await userEvent.click(await screen.findByText("比较备选解释与手动调整"));
    await userEvent.click(screen.getByRole("radio", { name: "暂不审定，补充依据" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "选择当前列表" }));
    await userEvent.click(screen.getByRole("button", { name: /IN-02.*病史要求/ }));
    expect(screen.getByRole("button", { name: "审定通过" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "批准所选 2 项" })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "选择IN-01" }));
    expect(screen.getByRole("button", { name: "批准所选 1 项" })).toBeEnabled();
    expect(fetcher.mock.calls.every(([, options]) => options?.method !== "POST")).toBe(true);
  });
});
