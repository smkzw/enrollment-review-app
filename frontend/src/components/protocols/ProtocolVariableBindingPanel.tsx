import { useEffect, useRef, useState } from "react";
import { decodeBindingView, variableRequest, type BindingView, type VariableBinding, type VariableDef } from "../../api/protocolVariables";

interface Props { jobId: string; revisionId: string; onSaved: () => void }
export function ProtocolVariableBindingPanel({ jobId, revisionId, onSaved }: Props) {
  const [view, setView] = useState<BindingView | null>(null);
  const [bindings, setBindings] = useState<VariableBinding[]>([]);
  const [definitions, setDefinitions] = useState<VariableDef[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [label, setLabel] = useState(""); const [unit, setUnit] = useState("");
  const [type, setType] = useState<VariableDef["value_type"]>("boolean");
  const [low, setLow] = useState(""); const [high, setHigh] = useState("");
  const scope = `${jobId}:${revisionId}`; const current = useRef(scope); current.current = scope;
  useEffect(() => {
    const controller = new AbortController(); setView(null); setBindings([]); setDefinitions([]); setError(null);
    variableRequest(jobId, "", undefined, controller.signal).then(value => {
      if (!controller.signal.aborted) setView(decodeBindingView(value, jobId, revisionId));
    }).catch(error => { if (!controller.signal.aborted) setError(error.message); });
    return () => controller.abort();
  }, [jobId, revisionId]);
  const allVariables = [...new Map([...(view?.variables ?? []), ...definitions].map(v => [v.variable_id, v])).values()];
  function choose(predicate: BindingView["predicates"][number], variableId: string) {
    setBindings(values => [...values.filter(b => b.component_id !== predicate.component_id || b.predicate_id !== predicate.predicate_id),
      ...(variableId ? predicate.requirements.map(requirement => ({ component_id: predicate.component_id,
        predicate_id: predicate.predicate_id, requirement_id: requirement.requirement_id, variable_id: variableId })) : [])]);
  }
  async function act(suggest: boolean) {
    setBusy(true); setError(null);
    try {
      const result = await variableRequest(jobId, suggest ? "/suggest" : "", {
        expected_revision_id: revisionId, ...(suggest ? {} : { proposal: { variables: definitions, bindings } }),
      });
      if (current.current !== scope) return;
      if (suggest) {
        const value = result as { proposal: { variables: VariableDef[]; bindings: VariableBinding[] } | null; system_issue?: string };
        if (!value.proposal) throw new Error(value.system_issue ?? "本次建议未能完成，请直接选择。");
        setDefinitions(value.proposal.variables); setBindings(value.proposal.bindings);
        setError(value.system_issue ?? null);
      } else onSaved();
    } catch (error) { if (current.current === scope) setError(error instanceof Error ? error.message : "数据项目未能保存。"); }
    finally { if (current.current === scope) setBusy(false); }
  }
  function addVariable() {
    if (!label.trim() || (type === "number" && (!unit.trim() || low.trim() === "" || high.trim() === "" || Number(low) >= Number(high)))) return;
    setDefinitions(values => [...values, { variable_id: `project_${crypto.randomUUID().replaceAll("-", "")}`,
      label_zh: label.trim(), value_type: type, canonical_unit: type === "number" ? unit.trim() : null,
      unit_conversions: {}, plausible_range: type === "number" ? [Number(low), Number(high)] : null,
      aliases_zh: [], domain: type === "exposure" ? "medication" : "history" }]);
    setLabel(""); setUnit(""); setLow(""); setHigh("");
  }
  return <section className="protocol-variable-bindings" aria-label="判断所需数据项目">
    <h2>判断所需数据项目</h2>
    {error && <p role="alert">{error}</p>}
    <div className="protocol-rule-reviews__actions"><button className="button" disabled={!view || busy} onClick={() => void act(true)}>建议对应项目</button>
      <button className="button button--primary" disabled={!view || busy || (!bindings.length && !definitions.length)} onClick={() => void act(false)}>{busy ? "正在处理…" : "保存项目选择"}</button></div>
    {view && <details><summary>{view.predicates.length} 个判断条件</summary><table><thead><tr><th>条款与判断项目</th><th>对应病例数据</th></tr></thead><tbody>
      {view.predicates.map(p => <tr key={`${p.component_id}:${p.predicate_id}`}><td>{p.official_code} · {p.label}</td><td><select aria-label={`${p.official_code} ${p.label}对应数据`} disabled={busy || !p.requirements.length}
        value={bindings.find(b => b.component_id === p.component_id && b.predicate_id === p.predicate_id)?.variable_id ?? p.variable_id ?? ""} onChange={event => choose(p, event.target.value)}>
        <option value="">尚未选择</option>{allVariables.map(v => <option key={v.variable_id} value={v.variable_id}>{v.label_zh}{v.canonical_unit ? `（${v.canonical_unit}）` : ""}</option>)}</select></td></tr>)}
    </tbody></table></details>}
    <details><summary>新增本项目数据</summary><fieldset disabled={busy}>
      <label>项目名称<input value={label} onChange={e => setLabel(e.target.value)} /></label>
      <label>内容类型<select value={type} onChange={e => setType(e.target.value as VariableDef["value_type"])}>
        <option value="boolean">是否存在或完成</option><option value="category">分类结果</option><option value="number">数值</option><option value="date">日期</option><option value="exposure">用药或治疗</option></select></label>
      {type === "number" && <><label>单位<input value={unit} onChange={e => setUnit(e.target.value)} /></label><label>合理范围下限<input type="number" value={low} onChange={e => setLow(e.target.value)} /></label><label>合理范围上限<input type="number" value={high} onChange={e => setHigh(e.target.value)} /></label></>}
      <button className="button" disabled={!label.trim()} onClick={addVariable}>加入项目清单</button>
    </fieldset></details>
  </section>;
}
