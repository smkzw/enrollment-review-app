/**
 * 系统帮助（合同 §3.1）：面向不熟悉电脑与 AI 的医学监查员的分步操作说明。
 * - 所有说明使用临床工作语言，不出现任何内部实现词。
 * - 覆盖：认识界面、今日工作、看板、受试者资料、入排工作台、行动、任务、报告与方案、
 *   键盘操作和遇到问题怎么办。
 */

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { navigate, RouteLink } from "../app/router";
import { resetUatTrialState, UAT_PAGE_VERSION } from "../app/uatTrialState";
import { HelpIcon } from "../components/shell/icons";

interface HelpStep {
  title: string;
  steps: ReadonlyArray<string>;
  tip?: string;
}

const HELP_SECTIONS: ReadonlyArray<HelpStep> = [
  {
    title: "从这里开始：认识界面",
    steps: [
      "打开系统后直接进入「今日工作」，不需要登录账号。",
      "左侧是主要功能入口：今日工作、项目看板、方案工作台、受试者与资料、入排工作台、行动中心、报告、任务与系统、系统帮助。",
      "顶部显示当前所在位置、项目代号与方案版本。",
    ],
  },
  {
    title: "今日工作：今天先做什么",
    steps: [
      "「待处理事项」列出当前节点到期、需要补充或核对的行动，按阻断程度排序。",
      "「明确障碍」与「存在冲突」列出需要优先处理的对象。",
      "「资料整理任务」显示资料整理的进度；「近期变化」提示方案或资料的变化。",
      "点击任意一行的「打开审核」，直接进入该受试者对应审核节点。",
    ],
  },
  {
    title: "从方案建立一个新项目",
    steps: [
      "在项目看板顶部点击「从方案新建项目」；系统会先显示从方案中读取的项目名称、项目标识、方案版本和方案日期。",
      "逐项核对方案信息后点击「确认方案并继续」；本次界面试用不会把演示内容写入正式项目资料。",
      "确认研究期别。若一份方案同时包含两个不能作为同一研究审核的期别，应分别建立项目，不共用受试者和审核结论。",
      "选择本次要进入的审核节点。筛选期与基线/随机前是两个独立节点，不能合并成一个总状态。",
      "完成后先核对页面上的方案版本、研究期别和当前位置，再开始添加受试者或资料。",
    ],
    tip: "如果期别、版本或审核节点与方案不一致，请先返回修改，不要带着错误信息继续。",
  },
  {
    title: "项目看板：查看全部受试者",
    steps: [
      "看板按受试者分行、按审核阶段分列；每个阶段是独立的审核节点。",
      "可用「阶段」「状态」「代号」筛选，点击列头可排序。",
      "勾选复选框可批量选择；执行前必须在确认窗口逐一核对对象，未列出的受试者不会被处理。",
      "完成后再次核对完成摘要；排序或筛选不会自动扩大已经勾选的范围。",
      "点击阶段格子中的打开按钮，进入该受试者该阶段的审核。",
    ],
  },
  {
    title: "查看受试者资料与风险",
    steps: [
      "左侧选择受试者，右侧显示其当前节点的个例全景。",
      "首屏只突出与入排相关、异常、临界、趋势、冲突和资料缺口的事件；需要时可打开「完整明细」。",
      "「应备证据覆盖」显示每项应备资料的查找状态；「尚未见到」表示资料中未见这项记录，不等于明确否认。",
      "事件有直接来源时可「打开原始依据」；审核汇总或规则关联事件会明确显示「查看判断依据」或「查看关联规则资料」。没有独立定位时，页面会如实提示，不会用无关片段代替。",
    ],
  },
  {
    title: "入排工作台：规则、判断与证据",
    steps: [
      "左侧是规则树：父级为入选/排除/必做检查的官方编号，展开后是子项；子项缩进显示，不与其他父级混排。",
      "选中一个子项后，中间显示它的判断、缺口、行动与差异，右侧显示它的证据与应备证据覆盖。",
      "每条证据显示资料文件、页码、定位精度与降级原因；「仅页码」表示只能确定到整页，没有文字坐标高亮。",
    ],
  },
  {
    title: "行动中心：谁负责、补什么、何时完成",
    steps: [
      "每项行动说明：为什么需要、谁负责、需要补什么、什么资料可以关闭、最晚在哪个节点完成。",
      "「溯源待办」与「阻断」分开显示；溯源待办不阻断当前节点。",
      "人工确认必须填写理由；确认只表示该项行动已处理，不等于规则自动通过。",
      "行动关闭后如判断发生变化，会在差异区显示前后变化。",
    ],
  },
  {
    title: "任务与系统：资料整理进度",
    steps: [
      "页面最上方的「继续未完成事项」先显示上次停下的位置；已完成、尚未处理和处理失败可重试的资料会分开列出。",
      "点击「继续」只处理尚未完成的部分，已经完成的资料不会重复处理。",
      "离开页面后再次进入，已保存的试用进度仍会显示；需要重新演示时再点击「恢复试用初始状态」。",
      "下方任务列表显示每项资料整理的总体进度；点击查看处理记录。",
      "任务状态有固定中文说明：准备中、正在整理资料、部分资料尚未处理、处理失败可重试、已保存进度可继续、已取消、资料发生变化需重新核对、已完成。",
      "失败或暂停的任务可以继续或稍后再试；不要因为一份资料失败而重新处理全部已完成资料。",
    ],
  },
  {
    title: "方案工作台：首次解构与重新解构",
    steps: [
      "「方案工作台」首页提供两条路径：首次解构新方案，或在已发布项目上重新解构新版本。",
      "首次解构：上传 DOCX 方案原文 → 核对方案编号、版本、日期与研究期别 → 审阅草稿第 1 稿、来源定位与完整性检查 → 保存后发布正式项目。",
      "保存草稿只保存待讨论内容，不发布、不覆盖当前使用版本，也不会立即改变现有审核。",
      "重新解构：先在首页选择目标正式项目，再上传同一项目的新版方案。系统会把当前正式版本与新草稿并列，按官方编号逐条显示八类差异：新增、删除、原文、逻辑、时间窗、例外、证据要求、应完成阶段。",
      "重新解构时上传的新版方案只允许更新版本、日期与文件内容；方案编号和研究期别必须与目标项目一致，否则会阻止发布并提示原因。",
      "基于反馈修订：指出系统对方案原文的理解有误，或补充解释说明；提交后生成修订稿，正式版本不受影响。",
      "手工修订：直接改写所选子项的标题或方案原文摘录后提交，同样生成修订稿且不改变正式版本。",
      "取消本次草稿不会改变正式版本，已保存的草稿可稍后从恢复入口继续。",
      "发布会在目标项目下生成一个新的不可变规则版本，并把当前正式版本切换到新草稿；历史版本保留用于追溯，不会被覆盖或删除。",
    ],
  },
  {
    title: "常见问题：重新解构与发布",
    steps: [
      "找不到要重新解构的项目：请先确认该项目已经完成首次解构并发布，再返回「重新解构已有项目」列表选择。",
      "新版方案上传后被阻止发布：核对上传的父方案编号与研究期别是否与目标项目一致；只允许同一方案、同一期别的正式新版本。",
      "复合差异含义：中心栏差异显示当前正式版本（左）与新草稿（右）在原文、逻辑、时间窗、例外、证据要求或应完成阶段上的前后变化，逐条核对后再决定是否接受。",
      "误操作后恢复：浏览器关闭或服务中断不会丢失正式版本；请从工作台首页的「恢复未完成任务」继续上次检查点。",
    ],
    tip: "发布是不可轻易撤销的动作：发布前请务必与方案编号、研究期别逐一核对。",
  },
  {
    title: "键盘操作",
    steps: [
      "按 Tab 键在可操作控件之间移动，按 Enter 执行当前按钮。",
      "规则树中：方向键上下移动，向右展开、向左收起或返回父级。",
      "打开弹窗后按 Escape 关闭，焦点会回到打开它的按钮。",
      "复选框用空格切换；勾选、排序和筛选不会让页面跳回顶部。",
    ],
  },
  {
    title: "遇到问题怎么办",
    steps: [
      "资料暂时打不开：已经保存的进度不会丢失。请稍后再试。",
      "如果仍无法打开，请记录页面上的事项编号并联系系统支持人员。",
      "看到「资料发生变化，当前结果需要重新核对」时，先查看差异，再决定是否开始新的整理。",
    ],
    tip: "当前为界面试用：展示的均为合成示例数据，不代表真实审核已经完成。",
  },
];

export function HelpPage() {
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const confirmBackRef = useRef<HTMLButtonElement>(null);
  const resetTriggerRef = useRef<HTMLButtonElement>(null);
  const titleId = useId();

  const closeResetConfirm = useCallback(() => {
    setShowResetConfirm(false);
    requestAnimationFrame(() => resetTriggerRef.current?.focus());
  }, []);

  const confirmReset = useCallback(() => {
    resetUatTrialState();
    setShowResetConfirm(false);
    navigate("/today");
  }, []);

  useEffect(() => {
    if (!showResetConfirm) return;
    confirmBackRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeResetConfirm();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeResetConfirm, showResetConfirm]);

  return (
    <div className="help">
      <header className="page-head">
        <h1 className="page-head__title">
          <HelpIcon size={20} />
          系统帮助
        </h1>
        <p className="page-head__note">
          按顺序阅读即可完成日常工作；所有说明均为当前版本的真实操作。
        </p>
        <p className="page-head__meta">
          页面版本：{UAT_PAGE_VERSION}
        </p>
      </header>

      <ol className="help-sections">
        {HELP_SECTIONS.map((section, index) => (
          <li key={section.title} className="help-section">
            <h2 className="help-section__title">
              <span className="help-section__number">{index + 1}</span>
              {section.title}
            </h2>
            <ol className="help-section__steps">
              {section.steps.map((step, stepIndex) => (
                <li key={stepIndex} className="help-section__step">
                  {step}
                </li>
              ))}
            </ol>
            {section.tip !== undefined && (
              <p className="help-section__tip">{section.tip}</p>
            )}
          </li>
        ))}
      </ol>

      <section className="help-reset" aria-labelledby="help-reset-title">
        <h2 id="help-reset-title" className="help-reset__title">
          开始新的界面试用
        </h2>
        <p className="help-reset__note">
          每位参与者开始前，记录人员可以用这里把演示内容恢复成同一起点。
          只清除本系统在本次会话中保存的演示状态，不影响其他页面和数据。
        </p>
        <button
          ref={resetTriggerRef}
          type="button"
          className="button button--quiet"
          onClick={() => setShowResetConfirm(true)}
        >
          开始新的界面试用
        </button>
      </section>

      <section className="help-links" aria-labelledby="help-links-title">
        <h2 id="help-links-title" className="help-links__title">
          快速前往
        </h2>
        <div className="help-links__grid">
          <RouteLink to="/today" className="button">
            今日工作
          </RouteLink>
          <RouteLink to="/board" className="button">
            项目看板
          </RouteLink>
          <RouteLink to="/projects/new" className="button">
            从方案新建项目
          </RouteLink>
          <RouteLink to="/protocols" className="button">
            方案工作台
          </RouteLink>
          <RouteLink to="/subjects" className="button">
            受试者与资料
          </RouteLink>
          <RouteLink to="/workbench" className="button">
            入排工作台
          </RouteLink>
          <RouteLink to="/actions" className="button">
            行动中心
          </RouteLink>
          <RouteLink to="/tasks" className="button">
            任务与系统
          </RouteLink>
        </div>
      </section>

      {showResetConfirm && (
        <div className="confirmation-scrim" onClick={closeResetConfirm}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            className="confirmation-dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id={titleId}>开始新的界面试用</h2>
            <p className="confirmation-dialog__note">
              这一步会把本次会话中已经保存的演示状态清除，回到每位参与者的同一起点。
            </p>
            <p className="confirmation-dialog__note">
              当前页面版本：{UAT_PAGE_VERSION}
            </p>
            <div className="confirmation-dialog__actions">
              <button
                ref={confirmBackRef}
                type="button"
                className="button"
                onClick={closeResetConfirm}
              >
                先不要
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={confirmReset}
              >
                确认并回到今日工作
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default HelpPage;
