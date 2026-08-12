/**
 * 证据详情弹窗：原始文件信息 + 识别文字 + 定位说明。
 * 打开后焦点进入标题区；Escape/关闭按钮退出并返回触发控件（§7.1）。
 * 界面试用阶段不附带原始页图，不绘制任何坐标框或虚假高亮（§6.1）。
 */

import { useEffect, useId, useRef } from "react";
import type { EvidenceLocatorView } from "../../domain/viewModels";
import { UI_PHRASES } from "../../domain/labels";
import { PRECISION_DESCRIPTIONS, PrecisionBadge } from "./PrecisionBadge";
import { documentTypeLabel, sourcePartyLabel } from "./sourceLabels";

/** 页面可附加的来源信息（来自审核节点详情） */
export interface SourceDocumentView {
  documentVersionId: string;
  fileName: string;
  documentType: string;
  sourceParty: string;
}

export interface EvidenceDialogProps {
  locator: EvidenceLocatorView;
  source?: SourceDocumentView | undefined;
  onClose: () => void;
}

export function EvidenceDialog({
  locator,
  source,
  onClose,
}: EvidenceDialogProps) {
  const titleId = useId();
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="evidence-dialog-scrim" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="evidence-dialog"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="evidence-dialog__head">
          <h2 id={titleId} className="evidence-dialog__title">
            原始资料证据
          </h2>
          <button
            ref={closeRef}
            type="button"
            className="icon-button"
            aria-label="关闭证据"
            title="关闭证据"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <dl className="evidence-detail">
          <div className="evidence-detail__row">
            <dt>资料文件</dt>
            <dd>{locator.fileName}</dd>
          </div>
          {source !== undefined && (
            <div className="evidence-detail__row">
              <dt>资料类型</dt>
              <dd>
                {documentTypeLabel(source.documentType)} · 来源方：
                {sourcePartyLabel(source.sourceParty)}
              </dd>
            </div>
          )}
          <div className="evidence-detail__row">
            <dt>页码</dt>
            <dd>第 {locator.pageNumber} 页</dd>
          </div>
          <div className="evidence-detail__row">
            <dt>定位精度</dt>
            <dd>
              <PrecisionBadge precision={locator.precision} />
            </dd>
          </div>
          {locator.degradationReason !== null && (
            <div className="evidence-detail__row">
              <dt>{UI_PHRASES.degradationPrefix}</dt>
              <dd>{locator.degradationReason}</dd>
            </div>
          )}
          <div className="evidence-detail__row evidence-detail__row--full">
            <dt>识别文字摘录</dt>
            <dd>
              {locator.excerpt !== null && locator.excerpt !== "" ? (
                <blockquote className="evidence-detail__excerpt">
                  {locator.excerpt}
                </blockquote>
              ) : (
                <span className="evidence-detail__muted">
                  该页仅有定位信息，未提供文字摘录。
                </span>
              )}
            </dd>
          </div>
          <div className="evidence-detail__row evidence-detail__row--full">
            <dt>定位说明</dt>
            <dd>
              <p className="evidence-detail__note">
                {PRECISION_DESCRIPTIONS[locator.precision]}
              </p>
              <p className="evidence-detail__note evidence-detail__note--muted">
                当前界面不附带原始页图预览；资料文件与定位信息以中文说明为准。
              </p>
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
