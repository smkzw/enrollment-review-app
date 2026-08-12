/**
 * 方案工作台（合同 §3.1）：当前方案版本与新版草稿的差异比较（UAT-P1-03 语义）。
 * - 明确哪一版是当前使用版本；新内容为草稿，不覆盖当前规则版本。
 * - 变化类型分为新增 / 删除 / 逻辑或时间窗变化；来源标注可回方案原文定位。
 */

import { getDefaultRepository } from "../api";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { ProtocolFileIcon, ReportFileIcon } from "../components/shell/icons";
import { UI_PHRASES } from "../domain/labels";

interface SourceRefInfo {
  /** 中文来源标注 */
  label: string;
  /** 页码（如“第 10 页”） */
  page: string | null;
}

/** 解析来源标注：protocol-v1:p10 → 当前方案第 10 页；protocol-v2-draft:p12 → 新版本草稿第 12 页 */
function parseSourceRef(ref: string): SourceRefInfo {
  const [version, pagePart] = ref.split(":");
  const page =
    pagePart === undefined || pagePart === "" ? null : `第 ${pagePart.replace(/^p/, "")} 页`;
  const label =
    version === "protocol-v1"
      ? "当前方案"
      : version === "protocol-v2-draft"
        ? "新版本草稿"
        : "方案来源";
  return { label, page };
}

export function ProtocolsPage() {
  const { state, retry } = useLoad(
    () => getDefaultRepository().getProtocolDiff(),
    [],
  );

  if (state.status === "loading") {
    return <LoadingState />;
  }
  if (state.status === "error") {
    return <ErrorState message={state.message} onRetry={retry} />;
  }

  const diff = state.data;
  const currentRefs = diff.sourceRefs.map(parseSourceRef);
  const added = diff.addedRuleCodes;
  const deleted = diff.deletedRuleCodes;
  const changed = diff.changedRuleCodes;

  return (
    <div className="protocols">
      <header className="page-head">
        <h1 className="page-head__title">方案工作台</h1>
        <p className="page-head__note">
          {UI_PHRASES.prototypeOnly}：展示合成示例数据。比较当前方案与新版草稿的规则差异。
        </p>
      </header>

      <div className="protocol-versions">
        <section className="protocol-version protocol-version--current">
          <h2 className="protocol-version__title">
            <ProtocolFileIcon size={15} />
            当前使用版本
          </h2>
          <p className="protocol-version__name">V1.0</p>
          <p className="protocol-version__meta">
            生效日期：2026-08-01 · 当前规则版本
          </p>
          <p className="protocol-version__note">
            当前审核均以此版本为准；新版草稿尚未发布，不会覆盖现有结论。
          </p>
        </section>
        <section className="protocol-version protocol-version--draft">
          <h2 className="protocol-version__title">
            <ReportFileIcon size={15} />
            新版本草稿
          </h2>
          <p className="protocol-version__name">V2.0（草稿）</p>
          <p className="protocol-version__meta">尚未生效 · 不改变当前审核结果</p>
          <p className="protocol-version__note">
            草稿中的变化仅作比较参考；正式发布前，现有审核不受影响。
          </p>
        </section>
      </div>

      <section className="protocol-changes" aria-labelledby="protocol-change-title">
        <h2 id="protocol-change-title" className="protocol-section__title">
          规则差异
        </h2>
        {added.length === 0 && deleted.length === 0 && changed.length === 0 ? (
          <EmptyState message="当前没有可比较的方案差异。" />
        ) : (
          <ul className="protocol-change-list">
            {added.map((code) => (
              <li key={code} className="protocol-change protocol-change--added">
                <span className="protocol-change__badge">新增</span>
                <span className="protocol-change__code">{code}</span>
                <span className="protocol-change__desc">
                  新版本草稿中新增的条件，尚未发布。
                </span>
              </li>
            ))}
            {deleted.map((code) => (
              <li key={code} className="protocol-change protocol-change--deleted">
                <span className="protocol-change__badge">删除</span>
                <span className="protocol-change__code">{code}</span>
                <span className="protocol-change__desc">
                  新版本草稿中删除的条件，尚未发布。
                </span>
              </li>
            ))}
            {changed.map((code) => (
              <li key={code} className="protocol-change protocol-change--changed">
                <span className="protocol-change__badge">变化</span>
                <span className="protocol-change__code">{code}</span>
                <span className="protocol-change__desc">
                  逻辑或时间窗发生变化，尚未发布。
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="protocol-changes" aria-labelledby="protocol-source-title">
        <h2 id="protocol-source-title" className="protocol-section__title">
          方案原文位置
        </h2>
        {currentRefs.length === 0 ? (
          <EmptyState message="当前没有方案来源标注。" />
        ) : (
          <ul className="protocol-source-list">
            {currentRefs.map((ref, index) => (
              <li key={index} className="protocol-source">
                <span className="protocol-source__label">{ref.label}</span>
                {ref.page !== null && (
                  <span className="protocol-source__page">{ref.page}</span>
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="protocol-changes__note">
          新内容仍为草稿，当前规则版本未被覆盖；发布后系统会提示受影响的审核节点。
        </p>
      </section>
    </div>
  );
}

export default ProtocolsPage;
