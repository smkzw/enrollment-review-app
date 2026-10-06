import { RefreshCw } from "lucide-react";
import type { ControlGroupView } from "../../api/protocolControlView";
import type { useProtocolControls } from "./useProtocolControls";
import "./protocolControlPanel.css";

interface Props { controls: ReturnType<typeof useProtocolControls> }

function officialRuleLabel(code: string | null): string {
  if (code === null) return "对应条款待核";
  const match = /^(IN|EX)-(\d{2})$/.exec(code);
  return match ? `${match[1] === "IN" ? "入选" : "排除"}标准第${Number(match[2])}条` : "对应条款待核";
}

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
          {atom.continuing && <p className="kz-control-qualifiers">后续持续要求（本次不判定）：{atom.continuing.period}，{atom.continuing.statement}</p>}
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
      <p role="status">{state.job.statusLabel}。</p>
      <p role="status">补充审核要求尚未整理完成，当前方案暂不能发布。已保存的结果仍保留。</p>
      {state.job.state === "failed_final" && <button type="button" className="button" disabled={controls.retrying} onClick={() => { void controls.retryFailed(); }}>
        {controls.retrying ? "正在继续整理…" : "继续整理未完成部分"}
      </button>}
    </>}
    {state.status === "error" && <p role="alert">{state.message}</p>}
    {state.status === "ready" && <>
      <p>{state.data.calculationGaps.length > 0
        ? `已整理${state.data.requirements.length}项补充要求，另有${state.data.calculationGaps.length}处计算相关原文尚未纳入可靠审核，当前不能发布。`
        : state.data.restrictedStatements.length > 0
          ? `已整理${state.data.requirements.length}项补充要求，另有${state.data.restrictedStatements.length}段方案原文尚不能自动核对，以下一并保留。`
        : state.data.requirements.length === 0
          ? "本次整理未列出额外审核要求。"
          : `已整理${state.data.requirements.length}项补充要求，待随方案发布。`}</p>
      {state.data.restrictedStatements.length > 0 && <section className="kz-control-layer" aria-label="尚不能自动核对的方案原文">
        <h4>尚不能自动核对的方案原文</h4>
        <p>这些内容随本次方案保存，不视为已符合，也不代表受试者缺少资料。其他已核清要求仍单独保留。</p>
        <ol>{state.data.restrictedStatements.map((item, index) => <li key={item.id}>
          <strong>待核原文{index + 1}：{item.limitationKind === "consumer_unavailable" ? "核对方法尚未接通" : "适用含义尚待核清"}</strong>
          <blockquote>{item.sourceQuote}</blockquote>
          {item.scopeQuote && <p><strong>原文限定范围：</strong>{item.scopeQuote}</p>}
          {item.timeWords.length > 0 && <p><strong>原文时间要求：</strong>{item.timeWords.join("、")}</p>}
          {item.exceptionWords && <p><strong>原文例外：</strong>{item.exceptionWords}</p>}
          {item.affectedStage && <p><strong>涉及时期：</strong>{item.affectedStage}</p>}
          <ul>{item.unresolvedDimensions.map((dimension, dimensionIndex) => <li key={dimensionIndex}>{dimension}</li>)}</ul>
          {item.dependencyLabels.length > 0 && <p>还需结合{item.dependencyLabels.join("、")}核对。</p>}
        </li>)}</ol>
      </section>}
      {state.data.calculationGaps.length > 0 && <section className="kz-control-layer" aria-label="尚未纳入审核的计算相关原文">
        <h4>尚未纳入审核的计算相关原文</h4>
        <p>这里保留了方案原文。仍需核对它对哪些审核要求起作用，并接通可靠的取值或计算方式；这不是请研究者补写医学判断。</p>
        <ol>{state.data.calculationGaps.map((gap) => <li key={gap.id}>
          <strong>{gap.linkedOfficialCode === null
            ? "关联的审核条款尚待核对"
            : `原文核对时提及${officialRuleLabel(gap.linkedOfficialCode)}，尚未证明它影响哪项具体判断`}</strong>
          <blockquote>{gap.sourceQuote}</blockquote>
          <p>{gap.unresolvedAspects.length > 0 || gap.reviewDecision === "unresolved"
            ? "这段原文的适用含义仍需核清，不能先当作已确定要求。"
            : gap.reviewDecision === "covered_by_official" || gap.reviewDecision === "covered_by_procedure" || gap.reviewDecision === "additional_requirement"
              ? "已记录原文与审核要求的对应；可靠计算方式尚未接通，由系统建设继续处理。"
              : "这段原文是否属于本次审核、对应哪些要求仍需核对。"}</p>
        </li>)}</ol>
      </section>}
      <div className="kz-control-list">
        {state.data.requirements.map((item, index) => <details key={item.id} className="kz-control-item">
          <summary><span>补充要求 {index + 1}</span><strong>{item.title}</strong></summary>
          <div className="kz-control-body">
            <p><strong>适用人群：</strong>{item.population}</p>
            <ul className="kz-control-nodes">{item.nodes.map((node, nodeIndex) => <li key={nodeIndex}>
              <strong>{node.label}</strong> · {node.role}{node.guidance ? `：${node.guidance}` : ""}
              {node.scopeSource && <details className="kz-control-source">
                <summary>审核时期原文</summary>
                <blockquote>{node.scopeSource.excerpt}</blockquote>
              </details>}
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
