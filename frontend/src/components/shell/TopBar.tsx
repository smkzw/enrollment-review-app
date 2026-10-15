/**
 * 顶栏：当前位置、当前项目/方案版本（中文展示名）、帮助入口（合同 §3.1）。
 * 不显示登录、模型、开发信息或原始项目代号（如 SYNTHETIC-001-III）。
 * 仅显式演示模式展示示例项目，正式界面面向宽屏桌面。
 */

import { RouteLink } from "../../app/router";
import { getDefaultRepository } from "../../api";
import { useLoad } from "../../app/useLoad";
import { isInterfaceTrialMode } from "../../app/runtimeMode";
import { HelpIcon, ProtocolFileIcon } from "./icons";
import { projectDisplayLabel } from "./projectDisplay";

interface TopBarProps {
  /** 当前一级入口中文名（当前位置） */
  positionLabel: string;
  /** 项目看板上下文提供从方案新建项目入口 */
  showProjectCreation?: boolean;
  /** 新建项目页面不展示当前示例项目上下文，避免误解为资料已带入 */
  showProjectContext?: boolean;
}

export function TopBar({
  positionLabel,
  showProjectCreation = false,
  showProjectContext = true,
}: TopBarProps) {
  const trial = isInterfaceTrialMode();
  const { state } = useLoad(
    () => trial ? getDefaultRepository().getProjectSummary() : Promise.resolve(null),
    [trial],
  );
  const project = state.status === "success" ? state.data : null;
  return (
    <header className="topbar">
      <div className="topbar__position">
        <span className="topbar__label">当前位置</span>
        <strong>{positionLabel}</strong>
      </div>
      {showProjectContext && (
        <div className="topbar__context" aria-live="polite">
          {trial && project !== null && (
            <>
              <span className="topbar__context-item">{projectDisplayLabel(project)}</span>
              <span className="topbar__context-item">方案 {project.protocolVersion}</span>
            </>
          )}
        </div>
      )}
      <div className="topbar__actions">
        {showProjectCreation && (
          <RouteLink
            to="/projects/new"
            className="topbar__create"
            ariaLabel="从方案新建项目"
            title="从方案新建项目"
          >
            <ProtocolFileIcon size={15} />
            <span>从方案新建项目</span>
          </RouteLink>
        )}
        <RouteLink
          to="/help"
          className="topbar__help"
          ariaLabel="打开系统帮助"
          title="系统帮助"
        >
          <HelpIcon size={15} />
          <span>帮助</span>
        </RouteLink>
      </div>
    </header>
  );
}
