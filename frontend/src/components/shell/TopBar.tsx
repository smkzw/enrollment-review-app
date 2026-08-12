/**
 * 顶栏：当前位置、当前项目/方案版本（中文展示名）、帮助入口（合同 §3.1）。
 * 不显示登录、模型、开发信息或原始项目代号（如 SYNTHETIC-001-III）。
 * 窄屏只保留当前位置标题与紧凑帮助图标；项目/方案上下文移出窄屏顶栏。
 */

import { getDefaultRepository } from "../../api";
import { useLoad } from "../../app/useLoad";
import { RouteLink } from "../../app/router";
import { HelpIcon } from "./icons";
import { projectDisplayLabel } from "./projectDisplay";

interface TopBarProps {
  /** 当前一级入口中文名（当前位置） */
  positionLabel: string;
}

export function TopBar({ positionLabel }: TopBarProps) {
  const { state } = useLoad(
    () => getDefaultRepository().getProjectSummary(),
    [],
  );
  const project =
    state.status === "success" ? state.data : null;

  return (
    <header className="topbar">
      <div className="topbar__position">
        <span className="topbar__label">当前位置</span>
        <strong>{positionLabel}</strong>
      </div>
      <div className="topbar__context" aria-live="polite">
        {project === null ? (
          <span className="topbar__context-item">项目信息整理中</span>
        ) : (
          <>
            <span className="topbar__context-item" title={project.projectName}>
              {projectDisplayLabel(project)}
            </span>
            <span className="topbar__context-item">
              方案 {project.protocolVersion}
            </span>
          </>
        )}
      </div>
      <RouteLink
        to="/help"
        className="topbar__help"
        ariaLabel="打开系统帮助"
        title="系统帮助"
      >
        <HelpIcon size={15} />
        <span>帮助</span>
      </RouteLink>
    </header>
  );
}
