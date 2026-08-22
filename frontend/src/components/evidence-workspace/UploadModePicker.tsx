/**
 * 上传方式选择（design.md §8.3 / 任务）：首屏清晰的二选一切段控件。
 * - 只显示中文“补充资料 / 建立完整资料快照”与旁边的中文说明；
 *   绝不出现 incremental/full、Job、schema、payload、缓存、门禁、修订号等词。
 * - 选中态用橙色强调（品牌 #FF9900，深色文字），键盘可达（radio 语义 + aria-pressed）。
 */

import type { EvidenceUploadMode } from "../../api/evidence";

const MODE_OPTIONS: ReadonlyArray<{
  mode: EvidenceUploadMode;
  label: string;
  detail: string;
}> = [
  {
    mode: "incremental",
    label: "补充资料",
    detail:
      "在上一有效快照的全部资料基础上，合并本次新选择的文件；上一快照保持完整，可随时回看。",
  },
  {
    mode: "full",
    label: "建立完整资料快照",
    detail:
      "本次选择的文件构成新的完整资料集合，不继承上一快照；上一快照完整保留，用于差异比较。",
  },
];

export interface UploadModePickerProps {
  mode: EvidenceUploadMode | null;
  onSelect: (mode: EvidenceUploadMode) => void;
  /** 已有待确认预览时锁定上传方式：必须先用“取消预览”重来，不静默丢引用。 */
  disabled?: boolean;
  /** 首次建立资料版本时不存在可继承的当前有效资料。 */
  canSupplement?: boolean;
}

export function UploadModePicker({
  mode,
  onSelect,
  disabled = false,
  canSupplement = true,
}: UploadModePickerProps) {
  return (
    <div className="evidence-mode" role="group" aria-label="选择上传方式">
      <div className="evidence-mode__options" role="radiogroup" aria-label="上传方式">
        {MODE_OPTIONS.map((option) => {
          const selected = mode === option.mode;
          const optionDisabled =
            disabled || (option.mode === "incremental" && !canSupplement);
          return (
            <button
              key={option.mode}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={optionDisabled}
              className={`evidence-mode__option${selected ? " evidence-mode__option--selected" : ""}`}
              onClick={() => onSelect(option.mode)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <p className="evidence-mode__explain" aria-live="polite">
        {disabled
          ? "当前已有待确认的预览。如需更换上传方式，请先点击「取消预览」。"
          : !canSupplement && mode === null
            ? "当前审核节点尚无有效资料版本，请先选择「建立完整资料快照」。"
          : mode === null
            ? "请先选择本次资料的上传方式。"
            : (MODE_OPTIONS.find((option) => option.mode === mode)?.detail ?? "")}
      </p>
    </div>
  );
}
