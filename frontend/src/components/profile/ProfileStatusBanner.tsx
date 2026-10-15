/**
 * Patient Profile 状态横幅（Slice 5.6）：生成中 / 生成失败 / 陈旧三种状态提示。
 * 空档案（succeeded 且无条目）由页面以空态呈现，不在此重复；正常已生成不渲染。
 * 状态词只使用后端 statusLabel，不在此发明临床结论。
 */

import { TaskStateBadge } from "../shell/StatusBadge";
import type { PatientProfileModel } from "../../features/patient-profile/model";

export interface ProfileStatusBannerProps {
  model: PatientProfileModel;
}

export function ProfileStatusBanner({ model }: ProfileStatusBannerProps) {
  if (model.isGenerating) {
    return (
      <div className="profile-status profile-status--generating" role="status">
        <span className="feedback__spinner" aria-hidden="true" />
        <div>
          <p className="profile-status__title">{model.statusLabel}</p>
          <p className="profile-status__hint">
            正在整理已核实的病史、用药和检查记录。
          </p>
        </div>
      </div>
    );
  }
  if (model.isFailed) {
    return (
      <div className="profile-status profile-status--failed" role="alert">
        <p className="profile-status__title">{model.statusLabel}</p>
        <p className="profile-status__hint">
          本次档案整理未完成，不表示病史、用药或检查记录为空。原始资料仍保留。
        </p>
      </div>
    );
  }
  if (model.isStale) {
    return (
      <div className="profile-stale" role="status">
        <TaskStateBadge state="stale" />
        <span>
          {model.statusLabel}；下方展示的是上一版已生成档案的内容。
        </span>
      </div>
    );
  }
  return null;
}
