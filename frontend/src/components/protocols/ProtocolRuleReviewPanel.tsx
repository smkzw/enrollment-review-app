import { useEffect, useRef, useState } from "react";
import { requestRuleReviews, type RuleReviews, type ReviewerKind } from "../../api/protocolRuleReviews";
import type { IntegrityView, SourcesView } from "../../api/protocolWorkbenchTypes";
import { mapProtocolSourceLocators } from "../../domain/protocolMappers";
import { ProtocolDraftSourcePane } from "./ProtocolDraftSourcePane";

interface Props {
  jobId: string;
  revisionId: string;
  integrity: IntegrityView;
  sources: SourcesView;
  onReady: (ready: boolean) => void;
}
export function ProtocolRuleReviewPanel({ jobId, revisionId, integrity, sources, onReady }: Props) {
  const [data, setData] = useState<RuleReviews | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const [kind, setKind] = useState<ReviewerKind>("medical_manager");
  const [excluded, setExcluded] = useState(false);
  const [variables, setVariables] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const scope = `${jobId}:${revisionId}`;
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const entry = data?.entries.find(entry => entry.official_code === selection) ?? null;

  useEffect(() => {
    const controller = new AbortController();
    setData(null); setSelection(null); setError(null); setBusy(false); onReady(false);
    requestRuleReviews(jobId, { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return;
      if (value.draft_revision_id !== revisionId) throw new Error("草稿已更新，请刷新工作区。");
      setData(value); setSelection(value.entries[0]?.official_code ?? null); onReady(value.all_reviewed);
    }).catch(error => { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "审定记录暂不能读取。"); });
    return () => controller.abort();
  }, [jobId, revisionId, reload, onReady]);

  useEffect(() => {
    setExcluded(entry?.review?.note === "excluded");
    setVariables(entry?.review?.result_variables.join("、") ?? "");
  }, [entry]);

  async function submit(revoke: boolean) {
    if (!entry || !data) return;
    setBusy(true); setError(null);
    try {
      const value = await requestRuleReviews(jobId, { entry, draftRevisionId: revisionId,
        reviewerKind: kind, revoke, excluded, resultVariables: variables.split(/[、,，\s]+/).filter(Boolean) });
      if (currentScope.current !== scope) return;
      if (value.draft_revision_id !== revisionId) throw new Error("草稿已更新，请刷新工作区。");
      setData(value); onReady(value.all_reviewed);
    } catch (error) { if (currentScope.current === scope) setError(error instanceof Error ? error.message : "审定未能保存，请重试。"); }
    finally { if (currentScope.current === scope) setBusy(false); }
  }
  return <section className="protocol-rule-reviews" aria-label="逐条审定">
    <header><h2>逐条审定</h2><span>{data ? `${data.entries.filter(entry => entry.review).length} / ${data.entries.length} 项已审定` : "正在读取审定记录…"}</span>
      <label>审定身份 <select value={kind} disabled={busy} onChange={event => setKind(event.target.value as ReviewerKind)}>
        <option value="medical_manager">医学经理本人</option><option value="builder_verification">构建者验证</option>
      </select></label>
    </header>
    {kind === "builder_verification" && <p role="status">此身份的审定仅供验证，不能代替医学经理正式审定。</p>}
    {error && <p role="alert">{error} <button className="button" onClick={() => setReload(value => value + 1)}>重新读取</button></p>}
    {data && <div className="protocol-rule-reviews__layout">
      <ul aria-label="审定条目">{data.entries.map(item => <li key={item.official_code}>
        <button aria-pressed={selection === item.official_code} disabled={busy} onClick={() => setSelection(item.official_code)}>
          <span>{item.kind === "rule" ? item.official_code : "检查项目"} · {item.label}</span>
          <strong>{item.review ? "已审定" : "待审定"}</strong>
        </button>
      </li>)}</ul>
      {entry && <div className="protocol-rule-reviews__detail">
        <h3>{entry.kind === "rule" ? entry.official_code : "检查项目"}</h3><p>{entry.label}</p>
        {integrity.issues.filter(issue => issue.affectedRefs.some(ref => entry.issue_refs.includes(ref))).map(issue => <p key={issue.issueCode + issue.affectedRefs.join(",")} role="status">{issue.level}：{issue.problem}</p>)}
        {entry.kind === "procedure" && <fieldset><legend>入组前检查要求</legend>
          <label><input type="checkbox" checked={excluded} disabled={busy} onChange={event => setExcluded(event.target.checked)} /> 不作为入组前必需</label>
          <label>必需结果变量 <input value={variables} disabled={busy || excluded} onChange={event => setVariables(event.target.value)} /></label>
        </fieldset>}
        {entry.review && <p>已由{entry.review.reviewed_by}于{new Date(entry.review.reviewed_at).toLocaleString("zh-CN")}审定{entry.review.note === "excluded" ? "，不参与入组前判定" : ""}。</p>}
        <div className="protocol-rule-reviews__actions">
          <button className="button button--primary" disabled={busy || !integrity.publishable} onClick={() => void submit(false)}>{busy ? "正在保存…" : "审定通过"}</button>
          <button className="button" disabled={busy || !entry.review} onClick={() => void submit(true)}>撤销审定</button>
        </div>
        <details><summary>原文依据</summary><ProtocolDraftSourcePane component={null} fileName={null}
          selectionLabel={entry.kind === "rule" ? entry.official_code : entry.label}
          locators={mapProtocolSourceLocators(sources.sourceSpans, entry.source_refs)} /></details>
        <details><summary>审定历史</summary><ul>{data.history.filter(record => record.official_code === entry.official_code).map(record => <li key={record.record_id}>{new Date(record.reviewed_at).toLocaleString("zh-CN")} · {record.reviewed_by} · {record.action === "approved" ? "审定通过" : "撤销审定"}</li>)}</ul></details>
      </div>}
    </div>}
  </section>;
}
