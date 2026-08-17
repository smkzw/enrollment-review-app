/**
 * 来源定位区：展示选中子项绑定的方案原文位置与定位精度。
 */

import { PrecisionBadge } from "../evidence/PrecisionBadge";
import type { ProtocolDraftComponentView } from "../../domain/protocolViewModels";
import type { ProtocolSourceLocatorView } from "../../domain/protocolViewModels";
import { EmptyState } from "../shell/Feedback";
import { UI_PHRASES } from "../../domain/labels";

interface ProtocolDraftSourcePaneProps {
  component: ProtocolDraftComponentView | null;
  locators: ReadonlyArray<ProtocolSourceLocatorView>;
  fileName: string | null;
}

export function ProtocolDraftSourcePane({
  component,
  locators,
  fileName,
}: ProtocolDraftSourcePaneProps) {
  if (component === null) {
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
          {fileName ?? "方案文件"} · {component.displayCode}
        </p>
      </header>

      {locators.length === 0 ? (
        <EmptyState message="当前子项暂无来源定位" hint="请核对草稿映射或等待结构提取完成。" />
      ) : (
        <ul className="protocol-source-pane__list">
          {locators.map((locator) => (
            <li key={locator.sourceSpanId} className="protocol-source-card">
              <div className="protocol-source-card__head">
                <span className="protocol-source-card__ref">{locator.sourceRef}</span>
                {locator.pageLabel !== null && (
                  <span className="protocol-source-card__page">{locator.pageLabel}</span>
                )}
                <PrecisionBadge precision={locator.precision} />
              </div>
              <blockquote className="protocol-source-card__excerpt">{locator.excerpt}</blockquote>
              {locator.degradationReason !== null && (
                <p className="protocol-source-card__degraded">
                  {UI_PHRASES.degradationPrefix}：{locator.degradationReason}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
