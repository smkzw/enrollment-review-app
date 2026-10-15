/**
 * 来源定位区：展示选中子项绑定的方案原文位置与定位精度。
 */

import { PrecisionBadge } from "../evidence/PrecisionBadge";
import type { ProtocolDraftItemView } from "../../domain/protocolViewModels";
import type { ProtocolSourceLocatorView } from "../../domain/protocolViewModels";
import { EmptyState } from "../shell/Feedback";
import { UI_PHRASES } from "../../domain/labels";

interface ProtocolDraftSourcePaneProps {
  component: ProtocolDraftItemView | null;
  locators: ReadonlyArray<ProtocolSourceLocatorView>;
  fileName: string | null;
  selectionLabel?: string;
}

export function ProtocolDraftSourcePane({
  component,
  locators,
  fileName,
  selectionLabel,
}: ProtocolDraftSourcePaneProps) {
  const groups = new Map<string, ProtocolSourceLocatorView[]>();
  for (const locator of locators) {
    const key = JSON.stringify([locator.sourceRef, locator.pageLabel, locator.precision]);
    groups.set(key, [...(groups.get(key) ?? []), locator]);
  }
  if (component === null && !selectionLabel) {
    return (
      <EmptyState
        message="请选择规则子项以查看来源定位"
        hint="来源定位与规则树、编辑区共享同一选中状态。"
      />
    );
  }

  return (
    <div className="protocol-source-pane">
      <header className="protocol-source-pane__head">
        <h3 className="protocol-source-pane__title">来源定位</h3>
        <p className="protocol-source-pane__meta">
          {fileName ?? "方案文件"} · {selectionLabel ?? component?.displayCode}
        </p>
      </header>

      {locators.length === 0 ? (
        <EmptyState message="当前子项暂无来源定位" hint="请核对草稿映射或等待结构提取完成。" />
      ) : (
        <ul className="protocol-source-pane__list">
          {[...groups.entries()].map(([key, entries]) => (
            <li key={key} className="protocol-source-card">
              <div className="protocol-source-card__head">
                <span className="protocol-source-card__ref">{entries[0]?.sourceRef}</span>
                {entries[0]?.pageLabel !== null && (
                  <span className="protocol-source-card__page">{entries[0]?.pageLabel}</span>
                )}
                {entries[0] && <PrecisionBadge precision={entries[0].precision} />}
              </div>
              {entries.map(locator => <div key={locator.sourceSpanId}>
              {locator.excerpt ? <blockquote className="protocol-source-card__excerpt">{locator.excerpt}</blockquote>
                : <p>此位置为整体页或表格定位，没有单独的文字摘录。</p>}
              {locator.degradationReason !== null && (
                <p className="protocol-source-card__degraded">
                  {UI_PHRASES.degradationPrefix}：{locator.degradationReason}
                </p>
              )}
              </div>)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
