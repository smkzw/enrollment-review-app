import { useEffect, useMemo, useRef, useState } from "react";
import { AlertCircle, Check, SlidersHorizontal, GitBranch } from "lucide-react";
import { requestRuleReviews, type RuleReviews, type ReviewerKind } from "../../api/protocolRuleReviews";
import type { IntegrityView, SourcesView } from "../../api/protocolWorkbenchTypes";
import { displayProtocolSourceLocators } from "../../domain/protocolMappers";
import { ProtocolDraftSourcePane } from "./ProtocolDraftSourcePane";
import { decodeBindingView, variableRequest, type BindingView } from "../../api/protocolVariables";
import { reviewCategories, ruleReviewAdvice, ruleReviewIssueText, ruleReviewPresentations, type ReviewCategory } from "../../domain/protocolRuleReview";
import { ProtocolReviewLogic } from "./ProtocolReviewLogic";

interface Props {
  jobId: string;
  revisionId: string;
  integrity: IntegrityView;
  sources: SourcesView;
  content?: Record<string, unknown>;
  onReady: (ready: boolean) => void;
  onEdit?: (componentId?: string, mainOperator?: "all" | "any") => void;
}
const emptyContent = {};
export function ProtocolRuleReviewPanel({ jobId, revisionId, integrity, sources, content = emptyContent, onReady, onEdit }: Props) {
  const [data, setData] = useState<RuleReviews | null>(null);
  const [selection, setSelection] = useState<string | null>(null);
  const [choices, setChoices] = useState<Record<string, number>>({});
  const [kind, setKind] = useState<ReviewerKind>("medical_manager");
  const [excluded, setExcluded] = useState(false);
  const [variables, setVariables] = useState("");
  const [bindings, setBindings] = useState<BindingView | null>(null);
  const dictionary = bindings?.variables ?? [];
  const [category, setCategory] = useState<ReviewCategory | "all">("all");
  const [filter, setFilter] = useState("pending");
  const [search, setSearch] = useState("");
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set());
  const [batchOpen, setBatchOpen] = useState(false);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const scope = `${jobId}:${revisionId}`;
  const currentScope = useRef(scope);
  currentScope.current = scope;
  const items = useMemo(() => ruleReviewPresentations(data?.entries ?? [], content, bindings, integrity, sources),
    [data, content, bindings, integrity, sources]);
  const visible = useMemo(() => items.filter(item => (category === "all" || item.category === category || category === "medication" && item.medicationRelated)
    && (filter === "all" || filter === "pending" && !item.entry.review || filter === "focus" && item.reasons.length > 0 || filter === "approved" && item.entry.review)
    && `${item.entry.official_code} ${item.entry.label}`.includes(search.trim()))
    .sort((a, b) => Number(!!b.reasons.length) - Number(!!a.reasons.length)), [items, category, filter, search]);
  const selectedItem = visible.find(item => item.entry.official_code === selection) ?? visible[0] ?? null;
  const entry = selectedItem?.entry ?? null;
  const adviceGroups = selectedItem ? ruleReviewAdvice(selectedItem, content) : [];
  const unsavedChoiceCodes = new Set(items.filter(item => ruleReviewAdvice(item, content).some(advice => {
    const option = advice.options[choices[`${item.entry.official_code}:${advice.componentId ?? advice.title}`] ?? -1];
    return option && !option.keep && !option.current;
  })).map(item => item.entry.official_code));
  const hasUnsavedChoice = entry ? unsavedChoiceCodes.has(entry.official_code) : false;
  const selectedBatch = visible.filter(item => checked.has(item.entry.official_code));
  const batchHasUnsavedChoice = selectedBatch.some(item => unsavedChoiceCodes.has(item.entry.official_code));
  const reviewedCount = data?.entries.filter(entry => entry.review).length ?? 0;

  useEffect(() => {
    const controller = new AbortController();
    setData(null); setSelection(null); setChoices({}); setChecked(new Set()); setBatchOpen(false); setError(null); setBusy(false); onReady(false);
    requestRuleReviews(jobId, { signal: controller.signal }).then(value => {
      if (controller.signal.aborted) return;
      if (value.draft_revision_id !== revisionId) throw new Error("草稿已更新，请刷新工作区。");
      setData(value); onReady(value.all_reviewed);
    }).catch(error => { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "审定记录暂不能读取。"); });
    return () => controller.abort();
  }, [jobId, revisionId, reload, onReady]);

  useEffect(() => {
    const controller = new AbortController(); setBindings(null);
    variableRequest(jobId, "", undefined, controller.signal).then(value => {
      if (!controller.signal.aborted) setBindings(decodeBindingView(value, jobId, revisionId));
    }).catch(() => { /* The binding panel reports its own unavailable dictionary. */ });
    return () => controller.abort();
  }, [jobId, revisionId]);

  useEffect(() => {
    setExcluded(entry?.review?.note === "excluded");
    setVariables(entry?.review?.result_variables.join("、") ?? "");
  }, [entry]);

  useEffect(() => { setChecked(new Set()); setBatchOpen(false); }, [category, filter, search]);
  useEffect(() => {
    if (batchOpen) dialog.current?.showModal();
    else dialog.current?.close();
  }, [batchOpen]);

  async function submit(revoke: boolean) {
    if (!entry || !data) return;
    setBusy(true); setError(null);
    try {
      const value = await requestRuleReviews(jobId, { entry, draftRevisionId: revisionId,
        reviewerKind: kind, revoke, excluded, resultVariables: variables.split(/[、,，\s]+/).filter(Boolean) });
      if (currentScope.current !== scope) return;
      if (value.draft_revision_id !== revisionId) throw new Error("草稿已更新，请刷新工作区。");
      setData(value); onReady(value.all_reviewed);
      setSavedNotice(revoke ? "已撤销该条审定。" : "该条审定已保存。没有发布规则包。");
    } catch (error) { if (currentScope.current === scope) setError(error instanceof Error ? error.message : "审定未能保存，请重试。"); }
    finally { if (currentScope.current === scope) setBusy(false); }
  }
  function batchSettings(item: typeof items[number]) {
    const current = item.entry.official_code === entry?.official_code;
    return { official_code: item.entry.official_code, rule_content_hash: item.entry.rule_content_hash,
      note: current ? excluded ? "excluded" : null : item.entry.review?.note ?? null,
      result_variables: current ? variables.split(/[、,，\s]+/).filter(Boolean) : item.entry.review?.result_variables ?? [] };
  }
  async function submitBatch() {
    if (!selectedBatch.length || batchHasUnsavedChoice) return;
    setBusy(true); setError(null);
    try {
      const value = await requestRuleReviews(jobId, { draftRevisionId: revisionId, reviewerKind: kind,
        entries: selectedBatch.map(batchSettings) });
      if (currentScope.current !== scope) return;
      if (value.draft_revision_id !== revisionId) throw new Error("草稿已更新，请刷新工作区。");
      setData(value); onReady(value.all_reviewed); setChecked(new Set()); setBatchOpen(false);
      setSavedNotice(`已保存${selectedBatch.length}项审定。没有发布规则包。`);
    } catch (error) { if (currentScope.current === scope) setError(error instanceof Error ? error.message : "集中审定未能保存。"); }
    finally { if (currentScope.current === scope) setBusy(false); }
  }
  return <section className="protocol-rule-reviews" aria-label="逐条审定">
    <header><h2>规则审定</h2><span>{data ? `待审定 ${data.entries.length - reviewedCount} 项 · 已审定 ${reviewedCount} 项` : "正在读取审定记录…"}</span>
      <label>审定身份 <select value={kind} disabled={busy} onChange={event => setKind(event.target.value as ReviewerKind)}>
        <option value="medical_manager">医学经理本人</option><option value="builder_verification">构建者验证</option>
      </select></label>
    </header>
    {kind === "builder_verification" && <p role="status">构建者验证：发布为验证用规则包。</p>}
    {savedNotice && <p role="status">{savedNotice}</p>}
    {error && <p role="alert">{error} <button className="button" onClick={() => setReload(value => value + 1)}>重新读取</button></p>}
    {data && <>
      <div className="protocol-review-categories" aria-label="要求分类">
        <button type="button" aria-pressed={category === "all"} onClick={() => setCategory("all")} disabled={busy}>全部 {items.length}</button>
        {Object.entries(reviewCategories).map(([key, label]) => <button key={key} type="button" aria-pressed={category === key}
          onClick={() => setCategory(key as ReviewCategory)} disabled={busy}>{label} {items.filter(item => item.category === key || key === "medication" && item.medicationRelated).length}</button>)}
      </div>
      {category === "medication" && <p>官方入排标准中的用药条件仍按原编号审定；此视图不新增条目，不代表其他用药章节已完整纳入。</p>}
      <div className="protocol-review-filters">
        <label>审定范围 <select value={filter} disabled={busy} onChange={event => setFilter(event.target.value)}>
          <option value="pending">待审定</option><option value="focus">重点核对</option><option value="all">全部条目</option><option value="approved">已审定</option>
        </select></label>
        <label>查找条目 <input type="search" value={search} disabled={busy} onChange={event => setSearch(event.target.value)} placeholder="编号或内容" /></label>
        <span>重点核对 {items.filter(item => item.reasons.length).length} 项 · 当前 {visible.length} 项</span>
      </div>
      <div className="protocol-rule-reviews__layout">
      <div className="protocol-review-queue">
        <div className="protocol-review-batch-actions">
          <label><input type="checkbox" checked={visible.length > 0 && visible.every(item => checked.has(item.entry.official_code))}
            disabled={busy || !visible.length} onChange={event => setChecked(event.target.checked ? new Set(visible.map(item => item.entry.official_code)) : new Set())} /> 选择当前列表</label>
          <button className="button button--primary" disabled={busy || !selectedBatch.length || !integrity.publishable || batchHasUnsavedChoice}
            onClick={() => setBatchOpen(true)}>批准所选 {selectedBatch.length} 项</button>
        </div>
        <ul aria-label="审定条目">{visible.map(item => <li key={item.entry.official_code}>
        <input type="checkbox" aria-label={`选择${item.entry.kind === "rule" ? item.entry.official_code : `${item.entry.label}（${[...new Set(item.requirements.map(value => value.stage))].join("、")}）`}`} checked={checked.has(item.entry.official_code)} disabled={busy}
          onChange={event => setChecked(previous => { const next = new Set(previous); if (event.target.checked) next.add(item.entry.official_code); else next.delete(item.entry.official_code); return next; })} />
        <button aria-pressed={entry?.official_code === item.entry.official_code} disabled={busy} onClick={() => setSelection(item.entry.official_code)}>
          <span className="protocol-review-queue__title">{item.entry.kind === "rule" ? item.entry.official_code : reviewCategories[item.category]} · {item.title}</span>
          <span className="protocol-review-queue__meta"><strong>{item.entry.review ? "已审定" : "待审定"}</strong>
            {item.rule && <span>{item.rule.components.length + item.rule.restrictedComponents.length} 个子项</span>}
            <span>{[...new Set(item.requirements.map(value => value.stage))].join("、")}</span>
            <span className={item.reasons.length ? "protocol-review-confidence--low" : "protocol-review-confidence--high"}>
              {item.reasons.length ? "重点核对" : "结构清楚"}</span></span>
        </button>
      </li>)}</ul>
        {!visible.length && <p role="status">{category === "medication" ? "此类尚无独立审定条目；官方入排标准内已有的用药条件仍在原编号下查看，不能据此认为方案没有用药限制。" : "当前范围没有条目。"}</p>}
      </div>
      {entry && selectedItem && <div className="protocol-rule-reviews__detail">
        <header className="protocol-review-detail-head"><h3>{entry.kind === "rule" ? entry.official_code : entry.label}</h3>
          <span className={selectedItem.reasons.length ? "protocol-review-confidence--low" : "protocol-review-confidence--high"}>
            {selectedItem.reasons.length ? <AlertCircle size={15} aria-hidden="true" /> : <Check size={15} aria-hidden="true" />}
            {selectedItem.reasons.length ? "重点核对" : "结构清楚"}</span>
        </header>
        <details className="protocol-review-original"><summary>条款原文</summary><p>{entry.label}</p></details>
        {selectedItem.reasons.length > 0 && <details className="protocol-review-focus" aria-label="解析把握度">
          <summary><AlertCircle size={15} aria-hidden="true" /> {selectedItem.reasons.length} 项核对提示</summary>
          <ul>{selectedItem.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
        </details>}
        <ProtocolReviewLogic item={selectedItem} content={content} bindings={bindings} />
        {selectedItem.reasons.length > 0 && <details className="protocol-review-advice" aria-label="备选解释与处理" key={entry.official_code}>
          <summary><SlidersHorizontal size={16} aria-hidden="true" /> 比较备选解释与手动调整</summary>
          {adviceGroups.map((advice, groupIndex) => {
            const choiceKey = `${entry.official_code}:${advice.componentId ?? advice.title}`;
            const selected = advice.options[choices[choiceKey] ?? -1];
            return <details className="protocol-review-advice__group" key={choiceKey} open={groupIndex === 0}>
            <summary><GitBranch size={16} aria-hidden="true" />{advice.title}</summary>
            <details><summary>为什么需要核对</summary><p className="protocol-review-advice__analysis">{advice.analysis}</p></details>
            <fieldset><legend>选择解释方向</legend><ol>{advice.options.map((option, index) => <li key={option.label} className={option.recommended ? "is-recommended" : ""}>
              <div className="protocol-review-option__head"><span className="protocol-review-option__letter">{String.fromCharCode(65 + index)}</span>
                <label><input type="radio" name={`choice:${choiceKey}`} value={index} checked={choices[choiceKey] === index} disabled={busy}
                  onChange={() => setChoices(previous => ({ ...previous, [choiceKey]: index }))} /><strong>{option.label}</strong></label></div>
              <div className="protocol-review-option__tags">
                {option.current && <span>当前解释</span>}{option.recommended && <span><Check size={13} aria-hidden="true" />推荐核对方向</span>}
              </div>
              <p><b>判断变化</b>{option.explanation}</p>
            </li>)}</ol></fieldset>
            {selected && (selected.keep || selected.current) ? <button className="button button--primary"
              disabled={busy || !integrity.publishable || hasUnsavedChoice} onClick={() => void submit(false)}>确认现有解释并审定本条</button>
              : selected?.defer ? <button className="button" disabled={busy}
                onClick={() => { if (entry.review) void submit(true); else setSavedNotice("本条保留待审，未改变现有解释。"); }}>
                {entry.review ? "撤销本条审定，保留待审" : "确认暂不审定"}</button>
              : <button className="button" disabled={busy || !selected || !onEdit || !advice.componentId}
                onClick={() => { if (selected && advice.componentId) onEdit?.(advice.componentId, selected.operator); }}>
                {selected?.operator ? "按此方向预览修订" : "打开手动调整"}</button>}
          </details>;
          })}
        </details>}
        {onEdit && entry.kind === "rule" && selectedItem.rule?.components[0] && <button className="button" disabled={busy}
          onClick={() => onEdit(selectedItem.rule?.components[0]?.componentId)}>手动修改本条解析</button>}
        {integrity.issues.filter(issue => issue.level === "阻止发布" && issue.affectedRefs.some(ref => entry.issue_refs.includes(ref))).map(issue => <p key={issue.issueCode + issue.affectedRefs.join(",")} role="status">{issue.level}：{ruleReviewIssueText(issue)}</p>)}
        {entry.kind === "procedure" && <fieldset><legend>入组前检查要求</legend>
          <label><input type="checkbox" checked={excluded} disabled={busy} onChange={event => setExcluded(event.target.checked)} /> 不作为入组前必需</label>
          <label>必需检查结果 <select multiple value={variables.split("、").filter(Boolean)} disabled={busy || excluded}
            onChange={event => setVariables(Array.from(event.target.selectedOptions, option => option.value).join("、"))}>
            {dictionary.filter(value => value.value_type !== "procedure").map(value => <option key={value.variable_id} value={value.variable_id}>{value.label_zh}</option>)}
          </select></label>
        </fieldset>}
        {entry.review && <p>已由{entry.review.reviewed_by}于{new Date(entry.review.reviewed_at).toLocaleString("zh-CN")}审定{entry.review.note === "excluded" ? "，不参与入组前判定" : ""}。</p>}
        <div className="protocol-rule-reviews__actions">
          <button className="button button--primary" disabled={busy || !integrity.publishable || hasUnsavedChoice} onClick={() => void submit(false)}>{busy ? "正在保存…" : "审定通过"}</button>
          <button className="button" disabled={busy || !entry.review} onClick={() => void submit(true)}>撤销审定</button>
        </div>
        {hasUnsavedChoice && <p role="status">所选调整尚未保存，请先预览修订；或改选保留现有解释。</p>}
        <details><summary>原文依据与位置</summary><ProtocolDraftSourcePane component={null} fileName={null}
          selectionLabel={entry.kind === "rule" ? entry.official_code : entry.label}
          locators={displayProtocolSourceLocators(sources.sourceSpans, entry.source_refs)} /></details>
        <details><summary>审定历史</summary><ul>{data.history.filter(record => record.official_code === entry.official_code).map(record => <li key={record.record_id}>{new Date(record.reviewed_at).toLocaleString("zh-CN")} · {record.reviewed_by} · {record.action === "approved" ? "审定通过" : "撤销审定"}</li>)}</ul></details>
      </div>}
    </div></>}
    <dialog ref={dialog} className="protocol-review-batch-dialog" onCancel={event => { if (busy) event.preventDefault(); else setBatchOpen(false); }} onClose={() => setBatchOpen(false)} aria-labelledby="review-batch-title">
      <h3 id="review-batch-title">确认批准所选 {selectedBatch.length} 项</h3>
      <p>审定身份：{kind === "medical_manager" ? "医学经理本人" : "构建者验证（仅供验证）"}。本次只保存所选条目的审定，不发布规则包。</p>
      {!!selectedBatch.filter(item => item.reasons.length).length && <p>其中 {selectedBatch.filter(item => item.reasons.length).length} 项标为重点核对；请确认已对照原文与解析。</p>}
      <ul>{selectedBatch.map(item => {
        const settings = batchSettings(item);
        return <li key={item.entry.official_code}>{item.entry.kind === "rule" ? item.entry.official_code : "检查项目"} · {item.entry.label} · {[...new Set(item.requirements.map(value => value.stage))].join("、")}
          {item.rule && <p>本次审定包含此条的 {item.rule.components.length + item.rule.restrictedComponents.length} 个子项。</p>}
          {item.entry.kind === "procedure" && <p>{settings.note === "excluded" ? "不作为入组前必需" : settings.result_variables.length
            ? `必需结果：${settings.result_variables.map(id => dictionary.find(value => value.variable_id === id)?.label_zh ?? "项目名称待核对").join("、")}`
            : "只核查操作完成，不额外指定必需结果字段"}</p>}</li>;
      })}</ul>
      {error && <p role="alert">{error}</p>}
      <div className="protocol-rule-reviews__actions"><button className="button" disabled={busy} onClick={() => setBatchOpen(false)}>返回核对</button>
        <button className="button button--primary" disabled={busy || !selectedBatch.length || !integrity.publishable} onClick={() => void submitBatch()}>{busy ? "正在保存…" : "确认批准所选"}</button></div>
    </dialog>
  </section>;
}
