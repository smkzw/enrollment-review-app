/**
 * 应用入口：无登录直达今日工作（合同 §3.1）。
 * 全局壳负责路由与布局；正式与界面试用的数据入口分别注册。
 */

import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/shell.css";
import "./styles/components.css";
import "./styles/today.css";
import "./styles/board.css";
import "./styles/profile.css";
import "./styles/workbench.css";
import "./styles/actions.css";
import "./styles/tasks.css";
import "./styles/protocols.css";
import "./styles/project-creation.css";
import "./styles/evidence.css";
import "./styles/reports.css";
import "./styles/help.css";
import { AppShell } from "./app/AppShell";

export function App() {
  return <AppShell />;
}
