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
            档案正在生成中，生成后将自动展示首屏重点与完整历时信息。
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
          本次生成未产出可展示的档案条目，请稍后重新生成后再查看。
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
