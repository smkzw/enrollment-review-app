import { useEffect, useState } from "react";
import { requestReviewScope, scopeLabels, type ReviewScopeView, type ScopeKind } from "../../api/protocolReviewScope";

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

export function ProtocolReviewScope({ jobId, revisionId }: { jobId: string; revisionId: string }) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<ReviewScopeView | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setView(null);
    setError(null);
    if (!open) return;
    const controller = new AbortController();
    requestReviewScope(jobId, revisionId, controller.signal).then(result => {
      if (!controller.signal.aborted) setView(result);
    }).catch(reason => {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "审核范围暂不可读取。");
    });
    return () => controller.abort();
  }, [open, jobId, revisionId]);
  const current = view?.job_id === jobId && view.draft_revision_id === revisionId ? view : null;
  const records = new Map(current?.source_records.map(record => [record.source_span_id, record]));
  return <details className="protocol-review-scope" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>查看审核范围</summary>
    {open && <div className="protocol-review-scope__body">
      {error && <p role="alert">{error}</p>}
      {!current && !error && <p role="status">正在读取已保存的方案范围…</p>}
      {current && <>
        <p className="protocol-review-scope__note">以下是原文范围定位，不代表这些内容已经审定或用于本次判断。</p>
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
              return <details key={item.candidate_key} className="protocol-review-scope__item">
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
            </details>; })}
          </details>;
        })}
        {current.diagnostics.length > 0 && <details className="protocol-review-scope__group">
          <summary>范围定位待核对 <span>{current.diagnostics.length}项</span></summary>
          <ul>{current.diagnostics.map((item, index) => <li key={index}>
            {item.related_official_codes.join("、")} {item.identifiers.join("、")}：
            {diagnosticLabels[item.kind] ?? "来源定位尚需核对"}
          </li>)}</ul>
        </details>}
      </>}
    </div>}
  </details>;
}
