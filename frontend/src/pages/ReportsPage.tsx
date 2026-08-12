/**
 * 报告（合同 §3.1）：个例 / 中心 / 项目报告入口。
 * - 当前为界面试用：点击“生成报告”只说明后续功能，不生成或下载真实文件（§0 交互边界）。
 */

import { useState } from "react";
import { RouteLink } from "../app/router";
import { ReportFileIcon } from "../components/shell/icons";
import { UI_PHRASES } from "../domain/labels";

interface ReportEntry {
  id: string;
  title: string;
  scope: string;
  contents: ReadonlyArray<string>;
}

const REPORT_ENTRIES: ReadonlyArray<ReportEntry> = [
  {
    id: "subject",
    title: "个例报告",
    scope: "单名受试者",
    contents: [
      "该受试者各审核节点的判断、缺口与行动汇总",
      "关键证据定位与应备证据覆盖",
      "供监查员与研究者沟通使用",
    ],
  },
  {
    id: "center",
    title: "中心报告",
    scope: "单个研究中心",
    contents: [
      "该中心全部受试者的节点状态与分类计数",
      "待办行动、冲突与障碍对象清单",
      "供中心监查与问题跟进使用",
    ],
  },
  {
    id: "project",
    title: "项目报告",
    scope: "整个项目",
    contents: [
      "项目总体进度与各阶段状态汇总",
      "明确障碍、资料缺口、冲突与溯源待办统计",
      "方案版本差异说明",
    ],
  },
];

export function ReportsPage() {
  const [notice, setNotice] = useState<string | null>(null);

  return (
    <div className="reports">
      <header className="page-head">
        <h1 className="page-head__title">报告</h1>
        <p className="page-head__note">
          {UI_PHRASES.prototypeOnly}：可先查看三类报告的内容范围；当前不会生成文件。
        </p>
      </header>

      <div className="reports-grid">
        {REPORT_ENTRIES.map((entry) => (
          <article key={entry.id} className="report-card">
            <header className="report-card__head">
              <ReportFileIcon size={16} />
              <h2 className="report-card__title">{entry.title}</h2>
              <span className="count-chip">{entry.scope}</span>
            </header>
            <ul className="report-card__contents">
              {entry.contents.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <button
              type="button"
              className="button button--primary"
              onClick={() =>
                setNotice(
                  `界面试用：“${entry.title}”将在后续阶段提供生成与导出功能，当前不会生成文件。`,
                )
              }
            >
              生成报告
            </button>
          </article>
        ))}
      </div>

      {notice !== null && (
        <div className="reports-notice" role="status">
          {notice}
        </div>
      )}

      <section className="reports-help" aria-labelledby="reports-help-title">
        <h2 id="reports-help-title" className="reports-help__title">
          其他查看方式
        </h2>
        <p className="reports-help__text">
          当前可直接查看：
          <RouteLink to="/board" ariaLabel="打开项目看板">
            项目看板
          </RouteLink>
          （各节点状态）、
          <RouteLink to="/subjects" ariaLabel="打开受试者与资料">
            受试者与资料
          </RouteLink>
          （个例风险视图）与
          <RouteLink to="/actions" ariaLabel="打开行动中心">
            行动中心
          </RouteLink>
          （待办行动）。
        </p>
      </section>
    </div>
  );
}

export default ReportsPage;
