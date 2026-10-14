import { useEffect, useRef, useState } from "react";
import { requestReviewScope, saveReviewScope, scopeLabels, type ReviewScopeView, type ScopeKind, type ScopeProposal } from "../../api/protocolReviewScope";
import { ProtocolScopeSourcePicker } from "./ProtocolScopeSourcePicker";

const diagnosticLabels: Record<string, string> = {
  reference_unresolved: "尚未找到对应章节",
  reference_ambiguous: "有多处同编号内容，需指定对应章节",
  reference_external_attribution: "引用外部文件，未按方案章节处理",
  reference_identifier_unsupported: "引用编号暂不能自动定位",
  source_span_unknown: "缺少来源位置",
  source_span_cross_snapshot: "来源不属于本版方案",
  source_text_unavailable: "来源文字暂不可读",
  excerpt_not_in_source_text: "摘录与来源文字不一致",
  table_geometry_inconsistent: "表格位置关系尚待核对",
  source_geometry_inconsistent: "来源位置与原文结构不一致",
};

export function ProtocolReviewScope({ jobId, revisionId, onSaved, expanded, onExpandedChange }: {
  jobId: string; revisionId: string; onSaved?: () => void;
  expanded?: boolean; onExpandedChange?: (value: boolean) => void;
}) {
  const [localOpen, setLocalOpen] = useState(false);
  const open = expanded ?? localOpen;
  const [view, setView] = useState<ReviewScopeView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<ScopeProposal | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const active = useRef("");
  active.current = `${jobId}/${revisionId}`;
  useEffect(() => { setSaving(false); }, [jobId, revisionId]);
  useEffect(() => {
    if (!open || (view?.job_id === jobId && view.draft_revision_id === revisionId && !error)) return;
    setView(null);
    setProposal(null);
    setError(null);
    const controller = new AbortController();
    requestReviewScope(jobId, revisionId, controller.signal).then(result => {
      if (!controller.signal.aborted) {
        setView(result);
        setProposal(result.selection ? { ...result.selection, scope_content_hash: result.scope_content_hash } : {
          scope_content_hash: result.scope_content_hash, exclusions: [], additions: [],
          included_candidate_keys: result.candidates.filter(item => item.scope_kind === "referenced_source" || item.scope_kind === "medication_section").map(item => item.candidate_key),
        });
        setDirty(!result.selection || result.selection.scope_content_hash !== result.scope_content_hash);
      }
    }).catch(reason => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "审核范围暂不可读取。");
    });
    return () => controller.abort();
  }, [open, jobId, revisionId]);
  const current = view?.job_id === jobId && view.draft_revision_id === revisionId ? view : null;
  const records = new Map([...(current?.source_records ?? []), ...(current?.additional_source_records ?? [])].map(record => [record.source_span_id, record]));
  const editable = Boolean(current?.editable && onSaved && proposal);
  const optional = current?.candidates.filter(item => item.scope_kind === "referenced_source" || item.scope_kind === "medication_section") ?? [];
  const missingReason = optional.some(item => !proposal?.included_candidate_keys.includes(item.candidate_key) &&
    !proposal?.exclusions.find(row => row.candidate_key === item.candidate_key)?.reason.trim());
  async function save() {
    if (!proposal || !current || !editable) return;
    const identity = active.current;
    setSaving(true); setError(null);
    try {
      const result = await saveReviewScope(jobId, revisionId, proposal);
      if (active.current !== identity) return;
      setView(result); setProposal(result.selection); setDirty(false); onSaved?.();
    } catch (reason) {
      if (active.current === identity) setError(reason instanceof Error ? reason.message : "保存结果尚未确认，请刷新核对。");
    } finally { if (active.current === identity) setSaving(false); }
  }
  return <details className="protocol-review-scope" open={open} onToggle={event => {
    setLocalOpen(event.currentTarget.open); onExpandedChange?.(event.currentTarget.open);
  }}>
    <summary>查看审核范围</summary>
    {open && <div className="protocol-review-scope__body">
      {error && <p role="alert">{error}</p>}
      {!current && !error && <p role="status">正在读取已保存的方案范围…</p>}
      {current && <>
        <p className="protocol-review-scope__note">以下是原文范围定位，不代表这些内容已经审定或用于本次判断。</p>
        {current.selection && <p role="status">范围选择已保存；补充要求尚未纳入规则。</p>}
        {editable && <p>勾选需要补充核对的原文范围；入排标准和必做项目保留。</p>}
        {(Object.keys(scopeLabels) as ScopeKind[]).map(kind => {
          const items = current.candidates.filter(item => item.scope_kind === kind);
          return <details key={kind} className="protocol-review-scope__group">
            <summary>{scopeLabels[kind]} <span>{items.length}项</span></summary>
            {items.length === 0 && <p>未自动定位到相关内容，不能据此认定没有要求。</p>}
            {items.map(item => {
              const located = item.source_span_ids.map(id => ({ id, source: records.get(id) }))
                .filter(({ source }) => source?.raw_text !== "");
              const sourceRows = located.length > 1
                ? located.filter(({ source }, index) => index !== 0 || source?.raw_text !== item.label) : located;
              const optionalItem = item.scope_kind === "referenced_source" || item.scope_kind === "medication_section";
              return <div key={item.candidate_key} className="protocol-review-scope__choice">
              {editable && optionalItem && <label><input type="checkbox" aria-label={`保留 ${item.label}`} checked={proposal!.included_candidate_keys.includes(item.candidate_key)}
                disabled={saving} onChange={event => { const included = proposal!.included_candidate_keys.filter(key => key !== item.candidate_key);
                  setProposal({ ...proposal!, included_candidate_keys: event.target.checked ? [...included, item.candidate_key] : included,
                    exclusions: event.target.checked ? proposal!.exclusions.filter(row => row.candidate_key !== item.candidate_key)
                      : [...proposal!.exclusions.filter(row => row.candidate_key !== item.candidate_key), { candidate_key: item.candidate_key, reason: "" }] }); setDirty(true); }} />
                保留</label>}
              {editable && optionalItem && !proposal!.included_candidate_keys.includes(item.candidate_key) && <label>移除理由
                <input value={proposal!.exclusions.find(row => row.candidate_key === item.candidate_key)?.reason ?? ""} disabled={saving}
                  onChange={event => { setProposal({ ...proposal!, exclusions: [...proposal!.exclusions.filter(row => row.candidate_key !== item.candidate_key),
                    { candidate_key: item.candidate_key, reason: event.target.value }] }); setDirty(true); }} /></label>}
              <details className="protocol-review-scope__item">
              <summary>{item.official_codes.length > 0 && <strong>{item.official_codes.join("、")} </strong>}
                {item.label}{item.visit_instance && <span> · {item.visit_instance}</span>}</summary>
              <div className="protocol-review-scope__source">
                {sourceRows.map(({ id, source }, index) => {
                  const previous = sourceRows[index - 1]?.source;
                  const changedLocation = index === 0 || previous?.render_page !== source?.render_page ||
                    previous?.identity_status !== source?.identity_status;
                  return <div key={id}>
                    {changedLocation && <small>{source?.render_page ? `第${source.render_page}页` : "原文段落（页码未定位）"}
                      {source?.identity_status !== "ok" && " · 来源尚待核对"}</small>}
                    <p>{source?.raw_text ?? "原文暂不可读取，不能按无要求处理。"}</p>
                  </div>;
                })}
              </div>
            </details></div>; })}
          </details>;
        })}
        {current.diagnostics.length > 0 && <details className="protocol-review-scope__group">
          <summary>{current.diagnostics.some(item => !item.resolved_by_manual_selection) ? "范围定位待核对" : "引用原文已指定"}
            <span>{current.diagnostics.filter(item => !item.resolved_by_manual_selection).length || current.diagnostics.length}项</span></summary>
          <ul>{current.diagnostics.map((item, index) => <li key={index}>
            {item.related_official_codes.join("、")} {item.identifiers.join("、")}：
            {item.resolved_by_manual_selection ? "已手工指定原文" : diagnosticLabels[item.kind] ?? "来源定位尚需核对"}
          </li>)}</ul>
        </details>}
        {(proposal?.additions ?? current.selection?.additions ?? []).map((addition, index) => <details key={index} className="protocol-review-scope__group">
          <summary>手工指定的{scopeLabels[addition.scope_kind]} · {addition.official_codes.join("、") || "用药范围"}</summary>
          <p>{addition.reason}</p>
          <div className="protocol-review-scope__source">{addition.source_span_ids.map(id => records.get(id)).filter(source => source?.raw_text)
            .map(source => <p key={source!.source_span_id}>{source!.raw_text}</p>)}</div>
          {editable && <button type="button" className="button" disabled={saving} onClick={() => {
            setProposal({ ...proposal!, additions: proposal!.additions.filter((_, position) => position !== index) }); setDirty(true);
          }}>移除此段</button>}
        </details>)}
        {editable && <>
          <ProtocolScopeSourcePicker key={`${jobId}/${revisionId}`} view={current} onAdd={addition => {
            if (saving) return;
            const same = (value: typeof addition) => value.scope_kind === addition.scope_kind &&
              value.source_span_ids.join("|") === addition.source_span_ids.join("|") && value.official_codes.join("|") === addition.official_codes.join("|");
            const previous = proposal!.additions.find(same);
            const merged = previous ? { ...addition, resolves_references: [...new Set([
              ...(previous.resolves_references ?? []), ...(addition.resolves_references ?? [])])] } : addition;
            setProposal({ ...proposal!, additions: [...proposal!.additions.filter(value => !same(value)), merged] }); setDirty(true);
          }} />
          <button type="button" className="button button--primary" disabled={saving || !dirty || missingReason}
            title={missingReason ? "请说明移除范围的理由" : undefined} onClick={() => void save()}>{saving ? "正在保存…" : "保存范围选择"}</button>
        </>}
      </>}
    </div>}
  </details>;
}
