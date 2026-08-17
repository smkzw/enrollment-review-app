/**
 * 方案解构工作台首页：首次解构与重新解构分流。
 */

import logoUrl from "../../assets/logo_bot.svg";
import { RouteLink } from "../../app/router";
import {
  getProtocolWorkbenchRepository,
  PROTOCOL_DEMO_JOB_ID,
  PROTOCOL_RECOVERY_JOB_ID,
} from "../../api/protocolWorkbenchRepository";
import { ResumeIcon, HistoryIcon, ProtocolFileIcon } from "../shell/icons";

export function ProtocolWorkbenchHome() {
  const showDemoRecovery = getProtocolWorkbenchRepository().kind === "stub";

  return (
    <div className="protocol-home">
      <header className="protocol-home__hero">
        <img src={logoUrl} alt="康哲药业" className="protocol-home__logo" width={158} height={33} />
        <h1 className="protocol-home__title">方案工作台</h1>
        <p className="protocol-home__lead">
          从方案原文解构入排规则与流程节点。首次解构建立新项目；重新解构在已有项目上比较新版方案。
        </p>
      </header>

      <div className="protocol-home__cards">
        <section className="protocol-home-card protocol-home-card--primary" aria-labelledby="protocol-first-title">
          <h2 id="protocol-first-title" className="protocol-home-card__title">
            <ResumeIcon size={18} />
            首次解构新方案
          </h2>
          <p className="protocol-home-card__desc">
            上传 DOCX 方案，核对方案信息与研究期别后生成<strong>草稿第 1 稿</strong>，核对规则树、来源定位与完整性检查后再发布。
          </p>
          <ul className="protocol-home-card__steps">
            <li>登记文件并提取结构</li>
            <li>确认方案编号、版本与研究期别</li>
            <li>审阅草稿并保存，不覆盖正式规则版本</li>
          </ul>
          <RouteLink to="/protocols" params={{ mode: "first" }} className="button button--primary">
            开始首次解构
          </RouteLink>
        </section>

        <section className="protocol-home-card" aria-labelledby="protocol-redo-title">
          <h2 id="protocol-redo-title" className="protocol-home-card__title">
            <HistoryIcon size={18} />
            重新解构已有项目
          </h2>
          <p className="protocol-home-card__desc">
            在已发布项目上上传新版方案，并列比较当前正式版本与新草稿的规则变化；确认后可保存、取消或发布新的规则版本。
          </p>
          <ul className="protocol-home-card__steps">
            <li>选择目标正式项目并上传新版方案</li>
            <li>按官方编号逐条核对规则变化与来源定位</li>
            <li>保存草稿或基于反馈修订，发布前可取消</li>
          </ul>
          <RouteLink to="/protocols" params={{ mode: "redo" }} className="button">
            开始重新解构
          </RouteLink>
        </section>
      </div>

      {showDemoRecovery && (
        <section className="protocol-home-recovery" aria-labelledby="protocol-recovery-title">
          <h2 id="protocol-recovery-title" className="protocol-home-recovery__title">
            <ProtocolFileIcon size={16} />
            恢复未完成任务（界面试用）
          </h2>
          <p className="protocol-home-recovery__desc">
            若浏览器关闭或服务中断，可从上次检查点继续，不会丢失已登记的文件与确认进度。
          </p>
          <div className="protocol-home-recovery__links">
            <RouteLink
              to="/protocols"
              params={{ job: PROTOCOL_DEMO_JOB_ID }}
              className="button button--quiet"
            >
              继续审阅示例草稿
            </RouteLink>
            <RouteLink
              to="/protocols"
              params={{ job: PROTOCOL_RECOVERY_JOB_ID }}
              className="button button--quiet"
            >
              恢复中断示例任务
            </RouteLink>
          </div>
        </section>
      )}

      {showDemoRecovery && (
        <p className="protocol-home__disclaimer" role="note">
          界面试用数据用于熟悉操作流程；发布前需医学经理终审。
        </p>
      )}
    </div>
  );
}
