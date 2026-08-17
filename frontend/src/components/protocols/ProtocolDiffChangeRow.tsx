/**
 * 差异分类变化单条展示：稳定引用 + 正式版本快照 / 新草稿快照并列。
 */

import type { ProtocolCategoryChangeView } from "../../domain/protocolDiffViewModels";

export function ProtocolCategoryChangeRow({
  change,
}: {
  change: ProtocolCategoryChangeView;
}) {
  return (
    <li className="protocol-redo-change">
      <span className="protocol-redo-change__ref">
        {change.kind === "rule" ? "父规则" : change.kind === "requirement" ? "资料要求" : "子项"}
        {change.stableRef}
      </span>
      <div className="protocol-redo-change__compare">
        <div className="protocol-redo-change__side">
          <span className="protocol-redo-change__side-label">正式版本</span>
          <ProtocolPayload payload={change.previous} />
        </div>
        <div className="protocol-redo-change__side">
          <span className="protocol-redo-change__side-label">新草稿</span>
          <ProtocolPayload payload={change.current} />
        </div>
      </div>
    </li>
  );
}

export function ProtocolPayload({ payload }: { payload: unknown }) {
  return (
    <pre className="protocol-redo-change__payload">
      {typeof payload === "string" ? payload : JSON.stringify(payload, null, 2)}
    </pre>
  );
}
