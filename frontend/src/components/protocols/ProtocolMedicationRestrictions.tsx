import { useEffect, useRef, useState } from "react";
import { CalendarDays, Pill } from "lucide-react";
import { decodeScopeSupplement, medicationRequest, medicationStages, type MedicationRestriction, type ScopeSupplement } from "../../api/protocolMedications";
import { formatTimeConstraint } from "../../domain/mappers";

const anchors = { icf_date: "签署知情同意", screening_date: "筛选", baseline_date: "基线", randomization_date: "随机",
  first_dose_date: "首次给药", study_drug_administration_date: "研究药物给药", last_dose_date: "末次给药",
  study_completion_date: "研究完成", event_date: "事件发生", review_node_date: "当前审核节点" } as const;
const units = { day: "天", week: "周", month: "个月", year: "年" } as const;
const dispositions = { heading: "标题", permission: "允许用药或治疗", other_phase: "其他研究期别", background: "背景说明", unresolved: "尚待核清" } as const;

export function ProtocolMedicationRestrictions({ jobId, revisionId, content, drugClasses, onSaved }: {
  jobId: string; revisionId: string; content: Record<string, unknown>; onSaved: () => void;
  drugClasses: Record<string, string[]>;
}) {
  const [draft, setDraft] = useState<ScopeSupplement | null>(null);
  const [proposalRef, setProposalRef] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [changed, setChanged] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reused, setReused] = useState(false);
  const active = useRef(""); active.current = `${jobId}/${revisionId}`;
  useEffect(() => {
    setError(null); setChanged(false); setBusy(false); setProposalRef(null); setReused(false);
    try { setDraft(content.scope_supplement ? decodeScopeSupplement(content.scope_supplement) : null); }
    catch (reason) { setDraft(null); setError(reason instanceof Error ? reason.message : "补充要求尚不能读取。"); }
  }, [jobId, revisionId, content]);
  async function run(save: boolean) {
    const identity = active.current;
    setBusy(true); setError(null);
    try {
      const result = await medicationRequest(jobId, revisionId, save ? draft! : undefined, proposalRef);
      if (active.current !== identity) return;
      if (save) { setChanged(false); onSaved(); return; }
      if (!result.supplement) {
        if (result.manual_supplement) {
          setDraft(decodeScopeSupplement(result.manual_supplement)); setProposalRef(null); setChanged(true);
        }
        throw new Error(typeof result.system_issue === "string" ? result.system_issue : "本次用药读取尚未完成。");
      }
      setDraft(decodeScopeSupplement(result.supplement));
      setProposalRef(typeof result.proposal_ref === "string" ? result.proposal_ref : null);
      setReused(result.reused === true);
      setChanged(true);
    } catch (reason) { if (active.current === identity) setError(reason instanceof Error ? reason.message : "本次操作未完成，原规则保留。"); }
    finally { if (active.current === identity) setBusy(false); }
  }
  function change(index: number, patch: Partial<MedicationRestriction>) {
    setDraft(previous => previous ? { ...previous, medications: previous.medications.map((item, position) => position === index ? { ...item, ...patch } : item) } : null);
    setChanged(true);
  }
  function addFromSource(quotes: MedicationRestriction["source_quotes"]) {
    if (!draft) return;
    const ids = new Set(quotes.map(quote => quote.source_span_id));
    setDraft({ ...draft, medications: [...draft.medications, { drug_text: "", drug_class_id: null,
      window: null, period: null, applicable_stages: [], exception_excerpt: null, applies_to_rule: null,
      unresolved_reason: "适用时间与例外尚待核清", source_quotes: quotes }],
      source_dispositions: draft.source_dispositions.filter(row => !ids.has(row.source_span_id)) });
    setChanged(true);
  }
  function remove(index: number) {
    if (!draft) return;
    const remaining = draft.medications.filter((_, position) => position !== index);
    const used = new Set(remaining.flatMap(item => item.source_quotes.map(quote => quote.source_span_id)));
    const source_dispositions = [...draft.source_dispositions];
    for (const quote of draft.medications[index].source_quotes) if (!used.has(quote.source_span_id) && !source_dispositions.some(row => row.source_span_id === quote.source_span_id))
      source_dispositions.push({ source_span_id: quote.source_span_id, disposition: "unresolved", reason: "提案已移除，此段是否包含限制仍待核对。" });
    setDraft({ ...draft, medications: remaining, source_dispositions }); setChanged(true);
  }
  return <details className="protocol-review-scope">
    <summary><Pill size={16} aria-hidden="true" /> 用药与伴随治疗限制{draft ? ` · ${draft.medications.length}项` : ""}</summary>
    <div className="protocol-review-scope__body">
      <button type="button" className="button" disabled={busy || changed} onClick={() => void run(false)}>{busy ? "正在处理…" : "整理选定章节"}</button>
      {error && <p role="alert">{error}</p>}
      {!draft && <p>整理已选原文中的用药限制、适用期间及例外。</p>}
      {draft && <>
        <p>{changed ? reused ? "已核对保存的原答，未重新读取；本次建议尚未保存。" : "本次建议尚未保存。" : "已保存为草稿，审定后才可用于规则包。"}</p>
        {draft.medications.map((item, index) => <details className="protocol-review-scope__group" key={index}>
          <summary>{item.drug_text || "新增用药限制"} · <CalendarDays size={14} aria-hidden="true" /> {item.window ? Object.hasOwn(anchors, item.window.anchor_type) ? formatTimeConstraint(item.window) : "时间起点尚未核清" : item.period === "study_period" ? "整个研究期间" : item.period === "treatment_period" ? "治疗期间" : "时间尚待核清"}
            {item.exception_excerpt && " · 含例外"}</summary>
          <div className="protocol-review-scope__form">
            <label>药物或治疗原文<input disabled={busy} value={item.drug_text} onChange={event => change(index, { drug_text: event.target.value })} /></label>
            <label>药物类别<select disabled={busy} value={item.drug_class_id ?? ""} onChange={event => change(index, { drug_class_id: event.target.value || null })}>
              <option value="">尚未归类</option>{Object.entries(draft.drug_classes ?? drugClasses).map(([id, members]) => <option key={id} value={id}>{members.slice(0, 3).join("、")}等</option>)}</select></label>
            <label>关联入排标准<input disabled={busy} value={item.applies_to_rule ?? ""} placeholder="没有明确关联则留空" onChange={event => change(index, { applies_to_rule: event.target.value || null })} /></label>
            <label>尚未核清的内容<input disabled={busy} value={item.unresolved_reason ?? ""} onChange={event => change(index, { unresolved_reason: event.target.value || null })} /></label>
          </div>
          <fieldset disabled={busy}><legend>适用审核阶段</legend>{Object.entries(medicationStages).map(([stage, label]) => <label key={stage}>
            <input type="checkbox" checked={item.applicable_stages.includes(stage as keyof typeof medicationStages)} onChange={event => change(index, {
              applicable_stages: event.target.checked ? [...item.applicable_stages, stage as keyof typeof medicationStages] : item.applicable_stages.filter(value => value !== stage) })} />{label}</label>)}</fieldset>
          <div className="protocol-review-scope__form">
            <label>适用期间<select disabled={busy} value={item.period ?? (item.window ? "window" : "unknown")} onChange={event => {
              const value = event.target.value;
              change(index, value === "window" ? { period: null, window: item.window ?? {
                anchor_type: "" as keyof typeof anchors, direction: "before", lower_bound_days: null, upper_bound_days: null,
                lower_bound: null, upper_bound: null, lower_bound_inclusive: true, upper_bound_inclusive: true, half_life_multiplier: null, allow_partial_date: false } }
                : { period: value === "study_period" || value === "treatment_period" ? value : null, window: null });
            }}><option value="unknown">尚未核清</option><option value="window">相对日期窗口</option><option value="study_period">整个研究期间</option><option value="treatment_period">治疗期间</option></select></label>
            {item.window && <>
              <label>时间起点<select disabled={busy} value={item.window.anchor_type} onChange={event => change(index, { window: { ...item.window!, anchor_type: event.target.value as keyof typeof anchors } })}>
                <option value="">请选择原文命名起点</option>{Object.entries(anchors).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
              <label>相对方向<select disabled={busy} value={item.window.direction} onChange={event => change(index, { window: { ...item.window!, direction: event.target.value as "before" | "after" | "on" } })}>
                <option value="before">起点前</option><option value="after">起点后</option><option value="on">起点当天</option></select></label>
              {(["lower", "upper"] as const).map(bound => {
                const key = `${bound}_bound` as const, dayKey = `${bound}_bound_days` as const;
                const quantity = item.window![key] ?? (item.window![dayKey] == null ? null : { value: item.window![dayKey]!, unit: "day" as const });
                return <div key={bound}><label>{bound === "lower" ? "最短间隔" : "最长间隔"}<input type="number" min="1" step="1" disabled={busy} value={quantity?.value ?? ""}
                  onChange={event => change(index, { window: { ...item.window!, [dayKey]: null, [key]: event.target.value ? { value: Number(event.target.value), unit: quantity?.unit ?? "day" } : null } })} /></label>
                  <select aria-label={`${bound === "lower" ? "最短" : "最长"}间隔单位`} disabled={busy || !quantity} value={quantity?.unit ?? "day"} onChange={event => change(index, { window: { ...item.window!, [dayKey]: null, [key]: { ...quantity!, unit: event.target.value } } })}>
                    {Object.entries(units).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></div>;
              })}
              <label>半衰期倍数<input type="number" min="0.1" step="0.1" disabled={busy} value={item.window.half_life_multiplier ?? ""} onChange={event => change(index, { window: { ...item.window!, half_life_multiplier: event.target.value ? Number(event.target.value) : null } })} /></label>
            </>}
            <label>例外原文<input disabled={busy} value={item.exception_excerpt ?? ""} onChange={event => change(index, { exception_excerpt: event.target.value || null })} /></label>
          </div>
          <details><summary>原文依据</summary>{item.source_quotes.map((quote, position) => <p key={position}>{quote.excerpt}</p>)}</details>
          <div className="protocol-rule-reviews__actions"><button type="button" className="button" disabled={busy} onClick={() => addFromSource(item.source_quotes)}>从同段补充一条限制</button>
            <button type="button" className="button" disabled={busy} onClick={() => remove(index)}>移除此项，保留原文</button></div>
        </details>)}
        <details><summary>其余所选原文的处置 · {draft.source_dispositions.length}处</summary>
          {draft.source_dispositions.map(item => <div key={item.source_span_id}><strong>{dispositions[item.disposition]}</strong><p>{item.reason}</p>
            <details><summary>查看原文</summary><p>{draft.sources.find(source => source.source_span_id === item.source_span_id)?.excerpt}</p></details>
            <details><summary>调整这段的处理方式</summary><div className="protocol-review-scope__form">
              <label>原文性质<select disabled={busy} value={item.disposition} onChange={event => {
                const disposition = event.target.value as typeof item.disposition;
                setDraft({ ...draft, source_dispositions: draft.source_dispositions.map(row => row.source_span_id === item.source_span_id ? { ...row, disposition } : row) }); setChanged(true);
              }}>{Object.entries(dispositions).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
              <label>处理说明<input disabled={busy} value={item.reason} onChange={event => {
                setDraft({ ...draft, source_dispositions: draft.source_dispositions.map(row => row.source_span_id === item.source_span_id ? { ...row, reason: event.target.value } : row) }); setChanged(true);
              }} /></label>
            </div></details>
            <button type="button" className="button" disabled={busy} onClick={() => {
              const source = draft.sources.find(source => source.source_span_id === item.source_span_id);
              if (source) addFromSource([source]);
            }}>从此段新增限制</button></div>)}
        </details>
        <button type="button" className="button button--primary" disabled={busy || !changed} onClick={() => void run(true)}>保存补充要求</button>
      </>}
    </div>
  </details>;
}
