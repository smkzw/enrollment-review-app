import { RefreshCw } from "lucide-react";
import type { ControlGroupView } from "../../api/protocolControlView";
import type { useProtocolControls } from "./useProtocolControls";
import "./protocolControlPanel.css";

interface Props { controls: ReturnType<typeof useProtocolControls> }

function Groups({ title, groups }: { title: string; groups: ControlGroupView[] }) {
  if (!groups.length) return null;
  return <section className="kz-control-layer">
    <h4>{title}</h4>
    {groups.length > 1 && <p>{title === "要求组" ? "按各组的适用条件执行" : "满足其中任一组"}</p>}
    <ol>
      {groups.map((group, index) => <li key={index}>
        <strong>{title}{index + 1}{group.atoms.length > 1 ? (title === "要求组" ? "：各项一并核对" : "：以下条件同时成立") : ""}</strong>
        {group.triggerBranches.length > 0 && <p>适用于{group.triggerBranches.join("、")}</p>}
        {group.activatedBy.length > 0 && <p>仅在{group.activatedBy.join("、")}成立时采用</p>}
        {group.waivesBranches.length > 0 && <p>豁免范围：{group.waivesBranches.join("、")}</p>}
        {group.activatesGroups.length > 0 && <p>改按{group.activatesGroups.join("、")}执行</p>}
        <ul>{group.atoms.map((atom, atomIndex) => <li key={atomIndex}>
          <p>{atom.statement}</p>
          {atom.qualifiers.length > 0 && <p className="kz-control-qualifiers">{atom.qualifiers.join("；")}</p>}
          {atom.professionalJudgment && <p className="kz-control-qualifiers">涉及专业评估，按原文要求核对</p>}
          <details className="kz-control-source">
            <summary>方案原文</summary>
            {atom.excerpts.map((excerpt, excerptIndex) => <blockquote key={excerptIndex}>{excerpt}</blockquote>)}
          </details>
        </li>)}</ul>
      </li>)}
    </ol>
  </section>;
}

export function ProtocolControlPanel({ controls }: Props) {
  const { state, retry } = controls;
  return <section className="kz-protocol-controls" aria-label="跨章节补充审核要求">
    <header>
      <h2>跨章节补充审核要求</h2>
      <button type="button" className="button button--quiet" onClick={retry}>
        <RefreshCw size={16} aria-hidden="true" />刷新
      </button>
    </header>
    {state.status === "loading" && <p role="status">正在读取补充审核要求…</p>}
    {state.status === "processing" && <p role="status">{state.job.statusLabel}；完成后可与入排标准一并发布。</p>}
    {state.status === "stopped" && <>
      <p role="status">补充审核要求尚未整理完成，当前方案暂不能发布。已保存的结果仍保留。</p>
      {state.job.state === "failed_final" && <button type="button" className="button" disabled={controls.retrying} onClick={() => { void controls.retryFailed(); }}>
        {controls.retrying ? "正在继续整理…" : "继续整理未完成部分"}
      </button>}
    </>}
    {state.status === "error" && <p role="alert">{state.message}</p>}
    {state.status === "ready" && <>
      <p>{state.data.requirements.length === 0
        ? "本次整理未列出额外审核要求。"
        : `已整理${state.data.requirements.length}项补充要求，待随方案发布。`}</p>
      <div className="kz-control-list">
        {state.data.requirements.map((item, index) => <details key={item.id} className="kz-control-item">
          <summary><span>补充要求 {index + 1}</span><strong>{item.title}</strong></summary>
          <div className="kz-control-body">
            <p><strong>适用人群：</strong>{item.population}</p>
            <ul className="kz-control-nodes">{item.nodes.map((node, nodeIndex) => <li key={nodeIndex}>
              <strong>{node.label}</strong> · {node.role}{node.guidance ? `：${node.guidance}` : ""}
            </li>)}</ul>
            <div className="kz-control-layers">
              <Groups title="适用条件组" groups={item.applicability} />
              <Groups title="触发条件组" groups={item.triggers} />
              <Groups title="要求组" groups={item.obligations} />
              <Groups title="例外组" groups={item.exceptions} />
            </div>
            <h4>所需资料</h4>
            <ul>{item.evidence.map((evidence, evidenceIndex) => <li key={evidenceIndex}>
              <p>{evidence.description} · 于{evidence.dueStage}核对</p>
              {evidence.purposes.length > 0
                ? evidence.purposes.map((purpose, purposeIndex) => <p key={purposeIndex}>
                  <strong>{purpose.label}：</strong>{purpose.statement}
                </p>)
                : <p className="kz-control-qualifiers">此项资料对应的具体核实用途尚未整理。</p>}
              <p className="kz-control-qualifiers">{evidence.sourcePolicy.join("；")}</p>
              <details className="kz-control-source">
                <summary>资料要求原文</summary>
                {evidence.excerpts.map((excerpt, excerptIndex) => <blockquote key={excerptIndex}>{excerpt}</blockquote>)}
              </details>
            </li>)}</ul>
            {item.relations.length > 0 && <>
              <h4>与其他要求的关系</h4>
              <ul>{item.relations.map((relation, relationIndex) => <li key={relationIndex}>
                <strong>{relation.kind}</strong>：{relation.left} / {relation.right}
                {relation.node ? `（${relation.node}）` : ""}
                {relation.notes ? `。${relation.notes}` : ""}
              </li>)}</ul>
            </>}
          </div>
        </details>)}
      </div>
    </>}
  </section>;
}
