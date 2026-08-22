/**
 * 固定上下文带（design.md §8.2）：项目、受试者、审核节点、方案版本、
 * 当前资料版本与待处理数量，上传与确认全过程不消失。
 * 浅色表面 + 橙色身份线；返回入口保留受试者上下文。
 */

import { RouteLink } from "../../app/router";
import { BackIcon } from "../shell/icons";

export interface ContextBandProps {
  /** 中文项目展示名（projectDisplayLabel 派生，不暴露内部代号） */
  projectLabel: string;
  protocolVersion: string;
  subjectCode: string;
  /** 中心代号 + 名称，如 “001 中心名称” */
  centerLabel: string;
  /** 审核节点中文名（如 “筛选期”） */
  nodeLabel: string;
  /** 当前资料版本（如 “第 1 版”） */
  snapshotVersion: string;
  /** 待处理资料数量；无预览时为 0（不显示） */
  pendingCount: number;
  /** 返回受试者资料页时保留的受试者编号 */
  backSubjectId: string;
}

export function ContextBand({
  projectLabel,
  protocolVersion,
  subjectCode,
  centerLabel,
  nodeLabel,
  snapshotVersion,
  pendingCount,
  backSubjectId,
}: ContextBandProps) {
  return (
    <header className="evidence-band" aria-label="当前资料上下文">
      <dl className="evidence-band__items">
        <div className="evidence-band__item">
          <dt>项目</dt>
          <dd>{projectLabel}</dd>
        </div>
        <div className="evidence-band__item">
          <dt>受试者</dt>
          <dd>
            {subjectCode}
            <span className="evidence-band__muted"> · {centerLabel}</span>
          </dd>
        </div>
        <div className="evidence-band__item">
          <dt>审核节点</dt>
          <dd>{nodeLabel}</dd>
        </div>
        <div className="evidence-band__item">
          <dt>方案版本</dt>
          <dd>{protocolVersion}</dd>
        </div>
        <div className="evidence-band__item">
          <dt>当前资料版本</dt>
          <dd>{snapshotVersion}</dd>
        </div>
        {pendingCount > 0 && (
          <div className="evidence-band__item evidence-band__item--pending">
            <dt>待处理资料</dt>
            <dd>{pendingCount} 份</dd>
          </div>
        )}
      </dl>
      <RouteLink
        to="/subjects"
        params={{ subject: backSubjectId }}
        className="button evidence-band__back"
        aria-label="返回受试者资料页"
        title="返回受试者资料页"
      >
        <BackIcon size={15} />
        返回资料页
      </RouteLink>
    </header>
  );
}
