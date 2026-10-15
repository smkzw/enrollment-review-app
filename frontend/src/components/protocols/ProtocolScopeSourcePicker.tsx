import { useEffect, useRef, useState } from "react";
import { findScopeSources, type ReviewScopeView, type ScopeAddition, type ScopeSourceOption, type ScopeSourceOptions } from "../../api/protocolReviewScope";

export function ProtocolScopeSourcePicker({ view, onAdd }: { view: ReviewScopeView; onAdd: (value: ScopeAddition) => void }) {
  const [kind, setKind] = useState<ScopeAddition["scope_kind"]>("referenced_source");
  const [code, setCode] = useState("");
  const [reference, setReference] = useState("");
  const [reason, setReason] = useState("");
  const [query, setQuery] = useState("");
  const [chosen, setChosen] = useState<ScopeSourceOption | null>(null);
  const [options, setOptions] = useState<ScopeSourceOptions | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), [view.job_id, view.draft_revision_id]);
  const known = view.candidates.filter(item => item.scope_kind === "referenced_source" || item.scope_kind === "medication_section");
  const codes = [...new Set(view.candidates.flatMap(item => item.official_codes))].sort();
  const references = view.diagnostics.filter(item => item.diagnostic_key && ["reference_unresolved", "reference_ambiguous"].includes(item.kind));
  const selectedReference = references.find(item => item.diagnostic_key === reference);
  async function search(offset = 0) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true); setError(null); setOptions(null);
    try {
      const result = await findScopeSources(view.job_id, view.draft_revision_id, query, offset, controller.signal);
      if (!controller.signal.aborted) setOptions(result);
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "原文查找未完成。");
    } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  return <details className="protocol-review-scope__group">
    <summary>手工指定原文</summary>
    <div className="protocol-review-scope__form">
      <label>范围用途<select value={kind} onChange={event => { setKind(event.target.value as ScopeAddition["scope_kind"]); setReference(""); }}>
        <option value="referenced_source">条款引用的说明</option><option value="medication_section">用药或伴随治疗</option>
      </select></label>
      <label>关联条款<select value={selectedReference?.related_official_codes[0] ?? code} disabled={Boolean(selectedReference)} onChange={event => setCode(event.target.value)}>
        <option value="">{kind === "referenced_source" ? "请选择条款" : "不单独关联条款"}</option>
        {codes.map(value => <option key={value} value={value}>{value}</option>)}
      </select></label>
      {kind === "referenced_source" && references.length > 0 && <label>对应的待定位引用<select value={reference} onChange={event => setReference(event.target.value)}>
        <option value="">不替代现有引用定位</option>
        {references.map(item => <option key={item.diagnostic_key} value={item.diagnostic_key}>{item.related_official_codes.join("、")} · {item.identifiers.join("、")}</option>)}
      </select></label>}
      <label>选择理由<input value={reason} onChange={event => setReason(event.target.value)} /></label>
      <label>从已定位章节选择<select value={known.find(item => item.source_span_ids.join("|") === chosen?.source_span_ids.join("|"))?.candidate_key ?? ""}
        onChange={event => { const item = known.find(item => item.candidate_key === event.target.value);
          setChosen(item ? { label: item.label, text: item.label, page: null,
            source_span_ids: item.source_span_ids, missing_positions: 0 } : null); }}>
        <option value="">请选择原文章节</option>
        {known.map(item => <option key={item.candidate_key} value={item.candidate_key}>{item.label}</option>)}
      </select></label>
    </div>
    <details>
      <summary>查找其他原文</summary>
      <div className="protocol-review-scope__search">
        <label>章节标题或原文<input value={query} maxLength={200} onChange={event => {
          request.current?.abort(); setBusy(false); setOptions(null); setQuery(event.target.value);
        }} /></label>
        <button type="button" className="button" disabled={busy} onClick={() => void search()}>{busy ? "正在查找…" : "查找"}</button>
      </div>
      {error && <p role="alert">{error}</p>}
      {options && <>
        <p>找到{options.total}处，本页{options.items.length}处</p>
        <ul>{options.items.map((item, index) => <li key={item.source_span_ids.join("|") || index}>
          <label><input type="radio" name={`scope-source-${view.job_id}`} disabled={item.missing_positions > 0 || item.source_span_ids.length === 0}
            checked={chosen?.source_span_ids.join("|") === item.source_span_ids.join("|")} onChange={() => setChosen(item)} />
            {item.label} · {item.page ? `第${item.page}页` : "页码未定位"}</label>
          <details><summary>查看原文</summary><p>{item.text}</p></details>
          {item.missing_positions > 0 && <p>此范围的来源位置不完整，暂不能选择。</p>}
        </li>)}</ul>
        {options.next_offset !== null && <button type="button" className="button" disabled={busy}
          onClick={() => void search(options.next_offset!)}>下一页</button>}
      </>}
    </details>
    {chosen && <p>已选择：{chosen.label} · {chosen.source_span_ids.length}个原文位置</p>}
    <button type="button" className="button" disabled={!chosen || !reason.trim() || (kind === "referenced_source" && !code && !selectedReference)}
      onClick={() => { if (!chosen) return;
        onAdd({ scope_kind: kind, source_span_ids: chosen.source_span_ids,
          official_codes: selectedReference?.related_official_codes ?? (code ? [code] : []), reason: reason.trim(),
          resolves_references: selectedReference?.diagnostic_key ? [selectedReference.diagnostic_key] : [] });
        setChosen(null); setReason(""); }}>
      添加到范围
    </button>
  </details>;
}
