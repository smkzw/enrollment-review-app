/**
 * 单个父规则八类差异面板（重新解构中间栏）。
 * 按 official_code 展示：新增/删除整条父规则，以及子组件级六类变化快照（原文/逻辑/时间窗/例外/证据要求/应完成阶段）。
 */

import type { ProtocolRuleDiffView } from "../../domain/protocolDiffViewModels";
import { ProtocolCategoryChangeRow } from "./ProtocolDiffChangeRow";

interface ProtocolRedoDiffPaneProps {
  rule: ProtocolRuleDiffView;
  selected: boolean;
  onSelect: () => void;
}

export function ProtocolRedoDiffPane({ rule, selected, onSelect }: ProtocolRedoDiffPaneProps) {
  return (
    <li className={`protocol-redo-diff${selected ? " protocol-redo-diff--selected" : ""}`}>
      <button type="button" className="protocol-redo-diff__head" onClick={onSelect}>
        <span className="protocol-redo-diff__code">{rule.officialCode}</span>
        {rule.added && <span className="protocol-redo-diff__badge protocol-redo-diff__badge--added">新增</span>}
        {rule.removed && <span className="protocol-redo-diff__badge protocol-redo-diff__badge--removed">删除</span>}
        {!rule.added && !rule.removed && rule.hasChanges && (
          <span className="protocol-redo-diff__badge protocol-redo-diff__badge--changed">修改</span>
        )}
        {!rule.hasChanges && <span className="protocol-redo-diff__badge protocol-redo-diff__badge--unchanged">无变化</span>}
      </button>

      {(rule.added || rule.addedComponentRefs.length > 0) && (
        <p className="protocol-redo-diff__summary protocol-redo-diff__summary--added">
          新增子项：{rule.addedComponentRefs.length > 0 ? rule.addedComponentRefs.join("、") : "整条规则"}
        </p>
      )}
      {(rule.removed || rule.removedComponentRefs.length > 0) && (
        <p className="protocol-redo-diff__summary protocol-redo-diff__summary--removed">
          删除子项：{rule.removedComponentRefs.length > 0 ? rule.removedComponentRefs.join("、") : "整条规则"}
        </p>
      )}

      {rule.changes.length > 0 ? (
        <dl className="protocol-redo-diff__categories">
          {groupByCategory(rule.changes).map(([categoryLabel, changes]) => (
            <div key={categoryLabel} className="protocol-redo-category">
              <dt className="protocol-redo-category__label">{categoryLabel}</dt>
              <dd>
                <ul className="protocol-redo-category__list">
                  {changes.map((change, index) => (
                    <ProtocolCategoryChangeRow
                      key={`${change.stableRef}-${index}`}
                      change={change}
                    />
                  ))}
                </ul>
              </dd>
            </div>
          ))}
        </dl>
      ) : !rule.added && !rule.removed ? (
        <p className="protocol-redo-diff__unchanged">结构与正式版本一致，没有变化。</p>
      ) : null}
    </li>
  );
}

function groupByCategory(
  changes: ProtocolRuleDiffView["changes"],
): Array<[string, ProtocolRuleDiffView["changes"]]> {
  const groups = new Map<string, ProtocolRuleDiffView["changes"]>();
  for (const change of changes) {
    const list = groups.get(change.categoryLabel) ?? [];
    list.push(change);
    groups.set(change.categoryLabel, list);
  }
  return [...groups.entries()];
}
