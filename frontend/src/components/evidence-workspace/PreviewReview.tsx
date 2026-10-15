/**
 * 确认前逐文件复核（P4-R02）：新增、内容重复、名称相同但内容不同、
 * 不支持、无法读取、完整资料遗漏与预计重新识别逐行展示。
 * - 每行一个清晰的下一步动作；同名异内容必须显式选择处置后才能确认。
 * - 取消只清理暂存，不建立任何资料版本；确认按钮在所有阻塞选择解决前保持禁用。
 * - 每份已选文件可“移除”（重新生成预览）；完整资料遗漏行不携带文件，无移除动作。
 */

import {
  formatByteSize,
  type EvidenceConflictResolution,
  type EvidenceItemStatus,
  type EvidenceUploadPreviewView,
} from "../../api/evidence";
import { ConflictIcon } from "../shell/icons";

export interface PreviewReviewProps {
  preview: EvidenceUploadPreviewView;
  resolutions: Record<string, EvidenceConflictResolution>;
  onResolve: (itemId: string, resolution: EvidenceConflictResolution) => void;
  onRemove: (itemId: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
  busy: boolean;
  canConfirm: boolean;
  notice: string | null;
  error: string | null;
}

/** 分组顺序与标题：用户按处理语义理解，不暴露内部分类词。 */
const GROUPS: ReadonlyArray<{
  id: string;
  title: string;
  statuses: ReadonlyArray<EvidenceItemStatus>;
}> = [
  {
    id: "process",
    title: "本次将处理",
    statuses: ["added", "expected_reprocessing", "conflict"],
  },
  {
    id: "reuse",
    title: "复用已有处理结果",
    statuses: ["duplicate"],
  },
  {
    id: "rejected",
    title: "无法纳入处理",
    statuses: ["unsupported", "unreadable"],
  },
  {
    id: "omission",
    title: "上一资料版本有、本次未选择",
    statuses: ["full_snapshot_omission"],
  },
];

/** 行音调：橙色强调（本次处理）、中性（复用）、琥珀提醒（无法纳入/遗漏）、红仅用于风险 */
function rowTone(status: EvidenceItemStatus): string {
  if (status === "conflict" || status === "expected_reprocessing") return "attention";
  if (status === "unsupported" || status === "unreadable") return "rejected";
  if (status === "full_snapshot_omission") return "omitted";
  return "added";
}

const RESOLUTION_OPTIONS: ReadonlyArray<{
  value: EvidenceConflictResolution;
  label: string;
}> = [
  { value: "new_version", label: "作为原资料的新版本" },
  { value: "keep_parallel", label: "作为另一份资料并列保留" },
];

function ConflictResolutionField({
  itemId,
  value,
  onChange,
}: {
  itemId: string;
  value: EvidenceConflictResolution | undefined;
  onChange: (resolution: EvidenceConflictResolution) => void;
}) {
  return (
    <fieldset className="evidence-conflict">
      <legend className="evidence-conflict__legend">
        请选择处置方式（必选）
      </legend>
      <div className="evidence-conflict__options">
        {RESOLUTION_OPTIONS.map((option) => (
          <label key={option.value} className="evidence-conflict__option">
            <input
              type="radio"
              name={`resolution-${itemId}`}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function PreviewReview({
  preview,
  resolutions,
  onResolve,
  onRemove,
  onCancel,
  onConfirm,
  busy,
  canConfirm,
  notice,
  error,
}: PreviewReviewProps) {
  const conflictsUnresolved = preview.items
    .filter((item) => item.status === "conflict")
    .filter((item) => resolutions[item.itemId] === undefined).length;
  const omissions = preview.items.filter(
    (item) => item.status === "full_snapshot_omission",
  ).length;
  const includableItems = preview.items.filter((item) =>
    ["added", "duplicate", "conflict", "expected_reprocessing"].includes(
      item.status,
    ),
  ).length;
  const hasNewProcessing = preview.items.some((item) =>
    ["added", "conflict", "expected_reprocessing"].includes(item.status),
  );
  const duplicateOnly = includableItems > 0 && !hasNewProcessing;
  const wholeSetAlreadyExists = preview.matchingSnapshotId !== null;

  return (
    <section className="evidence-review" aria-label="确认前复核">
      <header className="evidence-review__head">
        <h3 className="evidence-review__title">
          确认前复核
          <span className="section-count">{preview.items.length}</span>
        </h3>
        <p className="evidence-review__summary">
          {preview.uploadModeLabel}：{preview.items.length} 份文件
          {omissions > 0 ? `，其中 ${omissions} 份来自上一资料版本且本次未选择` : ""}
          {conflictsUnresolved > 0
            ? `，${conflictsUnresolved} 份同名文件等待处置`
            : ""}
        </p>
      </header>

      {notice !== null && (
        <div className="evidence-notice evidence-notice--info" role="status">
          {notice}
        </div>
      )}
      {error !== null && (
        <div className="evidence-notice evidence-notice--error" role="alert">
          {error}
        </div>
      )}
      {wholeSetAlreadyExists && (
        <div className="evidence-notice evidence-notice--info" role="status">
          这组资料已经形成{preview.matchingSnapshotStatusLabel ?? "资料版本"}，
          无需再次确认。返回后可继续查看原处理进度和核对结果。
        </div>
      )}

      {GROUPS.map((group) => {
        const items = preview.items.filter((item) =>
          group.statuses.includes(item.status),
        );
        if (items.length === 0) return null;
        return (
          <div key={group.id} className="evidence-group">
            <h4 className="evidence-group__title">
              {group.title}
              <span className="section-count">{items.length}</span>
            </h4>
            <ul className="evidence-group__list">
              {items.map((item) => {
                const isOmission = item.status === "full_snapshot_omission";
                return (
                  <li
                    key={item.itemId}
                    className={`evidence-row evidence-row--${rowTone(item.status)}`}
                  >
                    <div className="evidence-row__main">
                      <div className="evidence-row__head">
                        <span className="evidence-row__file">{item.fileName}</span>
                        <span className="chip">{item.statusLabel}</span>
                        <span className="evidence-row__size">
                          {formatByteSize(item.byteSize)}
                        </span>
                      </div>
                      {item.reason !== "" && (
                        <p className="evidence-row__reason">{item.reason}</p>
                      )}
                      <p className="evidence-row__action">
                        <strong>下一步：</strong>
                        {item.nextAction}
                      </p>
                      {item.status === "conflict" && (
                        <ConflictResolutionField
                          itemId={item.itemId}
                          value={resolutions[item.itemId]}
                          onChange={(resolution) =>
                            onResolve(item.itemId, resolution)
                          }
                        />
                      )}
                    </div>
                    {!isOmission && (
                      <button
                        type="button"
                        className="button evidence-row__remove"
                        onClick={() => onRemove(item.itemId)}
                        disabled={busy}
                        title="从本次选择中移除该文件并重新生成预览"
                      >
                        移除
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}

      <footer className="evidence-review__footer">
        <div className="evidence-review__hint" aria-live="polite">
          {wholeSetAlreadyExists ? (
            <p>整组资料已存在，不会再次建立或重复识别。</p>
          ) : conflictsUnresolved > 0 ? (
            <p className="evidence-review__blocking">
              <ConflictIcon size={14} />
              还有 {conflictsUnresolved} 份同名文件未选择处置方式，确认暂不可用。
            </p>
          ) : includableItems === 0 ? (
            <p className="evidence-review__blocking">
              当前选择中没有可纳入的资料，请移除无法读取或不支持的文件后重新选择。
            </p>
          ) : duplicateOnly ? (
            <p>所选资料已在当前版本中，无需再次上传或建立资料版本。</p>
          ) : (
            <p>逐项核对无误后即可确认；确认将建立资料版本并开始处理。</p>
          )}
        </div>
        <div className="evidence-review__actions">
          <button
            type="button"
            className="button"
            onClick={onCancel}
            disabled={busy}
          >
            {duplicateOnly || wholeSetAlreadyExists ? "返回已有资料" : "取消预览"}
          </button>
          {!duplicateOnly && !wholeSetAlreadyExists && (
            <button
              type="button"
              className="button button--primary"
              onClick={onConfirm}
              disabled={busy || !canConfirm}
            >
              {busy ? "正在提交…" : "确认上传"}
            </button>
          )}
        </div>
      </footer>
    </section>
  );
}
