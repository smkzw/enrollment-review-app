/**
 * Patient Profile 13 条主题泳道（Slice 5.6）：全量历时信息。
 * 泳道按稳定展示顺序（model.lanes 已由领域模型排序，含空泳道）；
 * 空泳道只表示当前没有已整理的结构化条目，不判为资料缺口（由应备证据覆盖决定）。
 */

import { ProfileItemCard } from "./ProfileItemCard";
import type { PatientProfileModel } from "../../features/patient-profile/model";
import type { ProfileItemView } from "../../api/patient-profile";

export interface ProfileLaneListProps {
  model: PatientProfileModel;
  onOpenEvidence?: (item: ProfileItemView) => void;
  onRequestCorrection?: (item: ProfileItemView) => void;
}

export function ProfileLaneList({
  model,
  onOpenEvidence,
  onRequestCorrection,
}: ProfileLaneListProps) {
  return (
    <div className="profile-lane-list">
      <p className="profile-lane-list__note">
        分区暂无记录不代表正常或否认；是否存在资料缺漏，请以本审核节点的资料核对结果为准。
      </p>
      {model.lanes.map((lane) => (
        <section key={lane.lane} className="profile-lane" aria-label={lane.laneLabel}>
          <h4 className="profile-lane__title">
            {lane.laneLabel}
            <span className="section-count">{lane.items.length}</span>
          </h4>
          {lane.items.length === 0 ? (
            <p className="profile-lane__muted">
              暂无已整理记录
            </p>
          ) : (
            <ul className="profile-item-list">
              {lane.items.map((item) => (
                <li key={item.itemId}>
                  <ProfileItemCard
                    model={model}
                    item={item}
                    onOpenEvidence={onOpenEvidence}
                    onRequestCorrection={onRequestCorrection}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
