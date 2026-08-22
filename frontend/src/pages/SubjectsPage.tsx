/**
 * 受试者与资料（合同 §3.1/§4.2）：受试者选择 + Patient Profile。
 * - 首屏默认只突出入排相关、异常、临界、趋势、冲突与资料缺口事件；完整明细按需展开。
 * - 未解决冲突在风险视图内并列展示来源（复用 ConflictSources，不跳工作台；UAT-P1-06）。
 * - 应备证据覆盖与“资料中未提到 ≠ 明确否认”显式区分。
 * - URL 契约：/subjects?subject=<SubjectId>&stage=<ReviewStage>；证据直达 /workbench。
 */

import { useMemo } from "react";
import { getDefaultRepository } from "../api";
import { updateParams, RouteLink, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { ExpectationCoverage } from "../components/profile/ExpectationCoverage";
import { ConflictSources } from "../components/evidence/ConflictSources";
import {
  PROFILE_FILTERS,
  eventFilterKeys,
  isRiskEvent,
  type ProfileFilterKey,
} from "../components/profile/ProfileFilters";
import { ProfileEventRow } from "../components/profile/ProfileEventRow";
import { MainStatusBadge, TaskStateBadge } from "../components/shell/StatusBadge";
import { projectDisplayLabel } from "../components/shell/projectDisplay";
import { stageLabel, laneLabel, stageOrder, UI_PHRASES } from "../domain/labels";
import { PROFILE_LANE_ORDER } from "../components/profile/ProfileFilters";
import type { ReviewStage } from "../domain/enums";
import type { RuleComponentId, SubjectId } from "../domain/ids";
import type {
  EpisodeSummaryView,
  PatientProfileView,
  SubjectSummaryView,
} from "../domain/viewModels";

function isStage(value: string | null): value is ReviewStage {
  return (
    value !== null &&
    ["pre_screening", "screening", "run_in", "baseline"].includes(value)
  );
}

function isSubjectId(
  value: string | null,
  subjects: ReadonlyArray<SubjectSummaryView>,
): value is SubjectId {
  return value !== null && subjects.some((subject) => subject.subjectId === value);
}

/** 选中阶段：URL 优先且有效；否则取该受试者最早审核节点。 */
function deriveSelectedStage(
  subjectId: string | null,
  stageParam: string | null,
  episodeList: ReadonlyArray<EpisodeSummaryView>,
): ReviewStage | null {
  if (subjectId === null) return null;
  const subjectEpisodes = episodeList.filter(
    (episode) => episode.subjectId === subjectId,
  );
  if (subjectEpisodes.length === 0) return null;
  if (isStage(stageParam)) {
    const found = subjectEpisodes.some((episode) => episode.stage === stageParam);
    if (found) return stageParam;
  }
  return [...subjectEpisodes].sort(
    (a, b) => stageOrder.indexOf(a.stage) - stageOrder.indexOf(b.stage),
  )[0].stage;
}

/** 过滤开关：点击切换；再次点击同项视为取消（多选） */
function toggleFilter(
  current: ReadonlyArray<ProfileFilterKey>,
  key: ProfileFilterKey,
): ProfileFilterKey[] {
  return current.includes(key)
    ? current.filter((item) => item !== key)
    : [...current, key];
}

export function SubjectsPage() {
  const { params } = useHashRoute();
  const subjectParam = params.get("subject");
  const stageParam = params.get("stage");

  const subjects = useLoad(() => getDefaultRepository().getSubjects(), []);
  const board = useLoad(() => getDefaultRepository().getBoard(), []);

  // 派生值（非 hook）：数据未就绪时为空，不提前返回
  const subjectList =
    subjects.state.status === "success" ? subjects.state.data : [];
  const episodeList =
    board.state.status === "success" ? board.state.data.episodes : [];
  const project =
    board.state.status === "success" ? board.state.data.project : null;
  const selectedSubjectId: SubjectId | null = isSubjectId(subjectParam, subjectList)
    ? subjectParam
    : (subjectList[0]?.subjectId ?? null);
  const selectedStage = deriveSelectedStage(
    selectedSubjectId,
    stageParam,
    episodeList,
  );

  const profile = useLoad(
    () =>
      selectedSubjectId === null || selectedStage === null
        ? Promise.reject(new Error("no selection"))
        : getDefaultRepository().getPatientProfile(selectedSubjectId, selectedStage),
    [selectedSubjectId, selectedStage],
  );

  const detail = useLoad(
    () =>
      selectedSubjectId === null || selectedStage === null
        ? Promise.reject(new Error("no selection"))
        : getDefaultRepository().getEpisodeDetail(selectedSubjectId, selectedStage),
    [selectedSubjectId, selectedStage],
  );

  // 风险过滤（URL focus 参数）与完整明细（URL all 参数）
  const [activeFilters, setActiveFilters] = useUrlFilters(params.get("focus"));
  const showAll = params.get("all") === "1";

  if (subjects.state.status === "loading" || board.state.status === "loading") {
    return <LoadingState />;
  }
  if (subjects.state.status === "error") {
    return <ErrorState message={subjects.state.message} onRetry={subjects.retry} />;
  }
  if (board.state.status === "error") {
    return <ErrorState message={board.state.message} onRetry={board.retry} />;
  }

  const episodesOf = (subjectId: string): ReadonlyArray<EpisodeSummaryView> =>
    episodeList.filter((episode) => episode.subjectId === subjectId);

  if (
    episodesOf(selectedSubjectId ?? "").length > 0 &&
    (profile.state.status === "loading" || detail.state.status === "loading")
  ) {
    return <LoadingState />;
  }
  if (profile.state.status === "error") {
    return <ErrorState message={profile.state.message} onRetry={profile.retry} />;
  }
  if (detail.state.status === "error") {
    return <ErrorState message={detail.state.message} onRetry={detail.retry} />;
  }
  if (selectedSubjectId === null || selectedStage === null || profile.state.status !== "success" || detail.state.status !== "success") {
    return (
      <EmptyState
        message="当前没有可查看的受试者资料。"
        hint="可在项目看板中先选择一个受试者与审核节点。"
      />
    );
  }

  const profileData: PatientProfileView = profile.state.data;
  const episode = episodesOf(selectedSubjectId).find(
    (candidate) => candidate.stage === selectedStage,
  );

  /** 组件 ID → 显示编号 */
  const rulesOfEpisode = detail.state.data.rules;
  const componentCodeOf = (componentId: RuleComponentId): string => {
    for (const rule of rulesOfEpisode) {
      const found = rule.components.find(
        (component) => component.componentId === componentId,
      );
      if (found !== undefined) return found.displayCode;
    }
    return componentId;
  };

  const allEvents = profileData.lanes.flatMap((lane) => lane.events);
  const riskEvents = allEvents.filter(isRiskEvent);
  const filteredEvents = riskEvents.filter((event) => {
    if (activeFilters.length === 0) return true;
    const keys = eventFilterKeys(event);
    return activeFilters.some((key) => keys.includes(key));
  });

  const subjectCode = subjectList.find(
    (subject) => subject.subjectId === selectedSubjectId,
  )?.subjectCode;
  const subjectCenter = subjectList.find(
    (subject) => subject.subjectId === selectedSubjectId,
  );

  return (
    <div className="subjects">
      <header className="page-head">
        <h1 className="page-head__title">受试者与资料</h1>
        <p className="page-head__note">
          {UI_PHRASES.prototypeOnly}：展示合成示例数据。选择受试者后查看其当前节点的风险资料与证据覆盖。
        </p>
      </header>

      <div className="subjects-picker">
        <label className="subjects-picker__label" htmlFor="subjects-picker-select">
          受试者
        </label>
        <select
          id="subjects-picker-select"
          className="subjects-picker__select"
          value={selectedSubjectId}
          onChange={(event) =>
            updateParams({
              subject: event.target.value,
              stage: null,
              focus: null,
              all: null,
            })
          }
        >
          {subjectList.map((subject: SubjectSummaryView) => (
            <option key={subject.subjectId} value={subject.subjectId}>
              {subject.subjectCode} · {subject.centerCode} {subject.centerName}
            </option>
          ))}
        </select>
      </div>

      <div className="subjects-layout">
        <aside className="subjects-list" aria-label="受试者列表">
          <h2 className="subjects-list__title">受试者</h2>
          <ul>
            {subjectList.map((subject: SubjectSummaryView) => {
              const isActive = subject.subjectId === selectedSubjectId;
              const subjectEpisodes = episodesOf(subject.subjectId);
              return (
                <li key={subject.subjectId}>
                  <button
                    type="button"
                    className={`subjects-list__item${isActive ? " subjects-list__item--active" : ""}`}
                    aria-pressed={isActive}
                    onClick={() =>
                      updateParams({
                        subject: subject.subjectId,
                        stage: null,
                        focus: null,
                        all: null,
                      })
                    }
                  >
                    <span className="subjects-list__code">{subject.subjectCode}</span>
                    <span className="subjects-list__center">
                      {subject.centerCode} {subject.centerName}
                    </span>
                    {subjectEpisodes.map((item) => (
                      <span key={item.stage} className="count-chip">
                        {stageLabel[item.stage]} · {item.mainStatusLabel}
                      </span>
                    ))}
                  </button>
                </li>
              );
            })}
          </ul>
        </aside>

        <section className="profile" aria-label="个例全景">
          {profileData.stale && (
            <div className="profile-stale" role="status">
              <TaskStateBadge state="stale" />
              <span>
                当前审核结果需要重新核对。建议先查看最近一次资料变化。
              </span>
            </div>
          )}

          <header className="profile-head">
            <div className="profile-head__identity">
              <h2 className="profile-head__subject">{subjectCode}</h2>
              <p className="profile-head__meta">
                {project !== null
                  ? `${projectDisplayLabel(project)} · 方案 ${project.protocolVersion}`
                  : ""}
                {subjectCenter !== undefined
                  ? ` · ${subjectCenter.centerCode} ${subjectCenter.centerName}`
                  : ""}
              </p>
            </div>
            <div className="profile-head__node">
              {episode !== undefined && (
                <>
                  <span className="profile-head__stage">{episode.stageLabel}</span>
                  <MainStatusBadge status={episode.mainStatus} />
                  <span className="count-chip">
                    资料快照第 {episode.revision} 版
                  </span>
                  <RouteLink
                    to={`/subjects/${selectedSubjectId}/evidence`}
                    params={{ episode: episode.episodeId }}
                    className="button button--primary profile-head__evidence"
                    title="查看或补充该审核节点的资料"
                  >
                    查看/补充资料
                  </RouteLink>
                </>
              )}
            </div>
          </header>

          <div className="profile-toolbar">
            <div className="profile-toolbar__filters" role="group" aria-label="风险过滤">
              {PROFILE_FILTERS.map((option) => {
                const pressed = activeFilters.includes(option.key);
                return (
                  <button
                    key={option.key}
                    type="button"
                    className="chip"
                    aria-pressed={pressed}
                    title={option.describe}
                    onClick={() =>
                      setActiveFilters(toggleFilter(activeFilters, option.key))
                    }
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
            <div className="profile-toolbar__switch">
              <button
                type="button"
                className="chip"
                aria-pressed={showAll}
                onClick={() => updateParams({ all: showAll ? null : "1" })}
                title={showAll ? "返回风险视图" : "展开完整明细"}
              >
                {showAll ? "返回风险视图" : "完整明细"}
              </button>
            </div>
          </div>

          {!showAll && (
            <section className="profile-section" aria-labelledby="profile-risk-title">
              <h3 id="profile-risk-title" className="profile-section__title">
                关键事件与风险
                <span className="section-count">{filteredEvents.length}</span>
              </h3>
              {filteredEvents.length === 0 ? (
                <EmptyState
                  message="当前筛选下没有突出的事件。"
                  hint="可调整风险过滤条件，或打开完整明细查看全部资料。"
                />
              ) : (
                <ul className="profile-event-list">
                  {filteredEvents.map((event) => (
                    <li key={event.eventId}>
                      <ProfileEventRow
                        event={event}
                        episodeId={profileData.reviewEpisodeId}
                        componentCodeOf={componentCodeOf}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {!showAll && (
            <ConflictSources
              conflicts={detail.state.data.conflicts}
              sourceDocuments={detail.state.data.sourceDocuments}
            />
          )}

          {showAll && (
            <section className="profile-section" aria-labelledby="profile-all-title">
              <h3 id="profile-all-title" className="profile-section__title">
                完整明细
                <span className="section-count">{allEvents.length}</span>
              </h3>
              {PROFILE_LANE_ORDER.map((laneId) => {
                const lane = profileData.lanes.find(
                  (candidate) => candidate.lane === laneId,
                );
                const laneLabelOf =
                  lane?.laneLabel ??
                  laneLabel[laneId];
                return (
                  <div key={laneId} className="profile-lane">
                    <h4 className="profile-lane__title">{laneLabelOf}</h4>
                    {lane === undefined || lane.events.length === 0 ? (
                      <p className="profile-lane__muted">
                        {UI_PHRASES.profileLaneEmpty}
                      </p>
                    ) : (
                      <ul className="profile-event-list">
                        {lane.events.map((event) => (
                          <li key={event.eventId}>
                            <ProfileEventRow
                              event={event}
                              episodeId={profileData.reviewEpisodeId}
                              componentCodeOf={componentCodeOf}
                            />
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </section>
          )}

          <section className="profile-section" aria-labelledby="profile-cover-title">
            <h3 id="profile-cover-title" className="profile-section__title">
              应备证据覆盖
            </h3>
            <ExpectationCoverage expectations={profileData.expectations} />
          </section>
        </section>
      </div>
    </div>
  );
}

/** URL 保存的风险过滤（focus 参数逗号分隔；改动写回 URL，不产生历史记录） */
function useUrlFilters(param: string | null): [
  ReadonlyArray<ProfileFilterKey>,
  (next: ReadonlyArray<ProfileFilterKey>) => void,
] {
  const active = useMemo(() => {
    if (param === null) return [] as ReadonlyArray<ProfileFilterKey>;
    const keys = param.split(",").filter(
      (key): key is ProfileFilterKey =>
        PROFILE_FILTERS.some((option) => option.key === key),
    );
    return keys;
  }, [param]);

  const setActive = (next: ReadonlyArray<ProfileFilterKey>) => {
    updateParams({ focus: next.length === 0 ? null : next.join(",") });
  };

  return [active, setActive];
}

export default SubjectsPage;
