/**
 * 证据卡片：一条证据定位的紧凑展示（合同 §6.1）。
 * - 文件名、页码、精度徽标、降级原因、摘录同卡可见；点击“打开证据”进入详情弹窗。
 * - 打开证据按钮有中文可访问名称与工具提示，键盘 Tab 可达（§7.1）。
 */

import { useId, useRef, useState } from "react";
import type { EvidenceLocatorView } from "../../domain/viewModels";
import { UI_PHRASES } from "../../domain/labels";
import { PrecisionBadge } from "./PrecisionBadge";
import { EvidenceDialog, type SourceDocumentView } from "./EvidenceDialog";
import { PageOnlyIcon } from "../shell/icons";
import { documentTypeLabel, sourcePartyLabel } from "./sourceLabels";

export interface EvidenceCardProps {
  locator: EvidenceLocatorView;
  /** 附加来源信息（资料类型/来源方） */
  source?: SourceDocumentView | undefined;
  /** 打开证据的回调（覆盖默认弹窗；用于跨页导航） */
  onOpen?: ((locator: EvidenceLocatorView) => void) | undefined;
}

export function EvidenceCard({ locator, source, onOpen }: EvidenceCardProps) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);

  const handleOpen = () => {
    // 通知父级（用于高亮定位）并打开详情弹窗
    if (onOpen !== undefined) {
      onOpen(locator);
    }
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    // 弹窗关闭后焦点返回触发按钮（合同 §7.1）
    triggerRef.current?.focus();
  };

  return (
    <article className="evidence-card" aria-labelledby={titleId}>
      <header className="evidence-card__head">
        <h3 id={titleId} className="evidence-card__file">
          {locator.fileName}
        </h3>
        <PrecisionBadge precision={locator.precision} />
      </header>
      <p className="evidence-card__meta">
        第 {locator.pageNumber} 页
        {source !== undefined
          ? ` · ${documentTypeLabel(source.documentType)} · 来源方：${sourcePartyLabel(source.sourceParty)}`
          : ""}
      </p>
      {locator.degradationReason !== null && (
        <p className="evidence-card__degradation">
          {UI_PHRASES.degradationPrefix}：{locator.degradationReason}
        </p>
      )}
      {locator.excerpt !== null && locator.excerpt !== "" ? (
        <blockquote className="evidence-card__excerpt">
          {locator.excerpt}
        </blockquote>
      ) : (
        <p className="evidence-card__empty-excerpt">
          <PageOnlyIcon size={13} />
          该页仅有定位信息，未提供文字摘录。
        </p>
      )}
      <button
        ref={triggerRef}
        type="button"
        className="button button--quiet evidence-card__open"
        aria-label={`打开证据：${locator.fileName} 第 ${locator.pageNumber} 页`}
        title="打开证据"
        onClick={handleOpen}
      >
        打开证据
      </button>
      {open && (
        <EvidenceDialog
          locator={locator}
          source={source}
          onClose={handleClose}
        />
      )}
    </article>
  );
}
