/**
 * 系统帮助（合同 §3.1）：面向不熟悉电脑与 AI 的医学监查员的分步操作说明。
 * - 所有说明使用临床工作语言，不出现任何内部实现词。
 * - 覆盖：认识界面、今日工作、看板、受试者资料、入排工作台、行动、任务、报告与方案、
 *   键盘操作和遇到问题怎么办。
 */

import { RouteLink } from "../app/router";
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
      "窄窗口时左侧菜单会收起，点击左上角菜单按钮即可打开。",
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
    title: "项目看板：查看全部受试者",
    steps: [
      "看板按受试者分行、按审核阶段分列；每个阶段是独立的审核节点。",
      "可用「阶段」「状态」「代号」筛选，点击列头可排序。",
      "勾选复选框可批量选择；执行批量操作前会显示已选择数量。",
      "点击阶段格子中的打开按钮，进入该受试者该阶段的审核。",
    ],
  },
  {
    title: "查看受试者资料与风险",
    steps: [
      "左侧选择受试者，右侧显示其当前节点的个例全景。",
      "首屏只突出与入排相关、异常、临界、趋势、冲突和资料缺口的事件；需要时可打开「完整明细」。",
      "「应备证据覆盖」显示每项应备资料的查找状态；「尚未见到」表示资料中未见这项记录，不等于明确否认。",
      "点击事件上的「打开证据」直接进入对应的原始资料定位。",
    ],
  },
  {
    title: "入排工作台：规则、判断与证据",
    steps: [
      "左侧是规则树：父级为入选/排除/必做检查的官方编号，展开后是子项；子项缩进显示，不与其他父级混排。",
      "选中一个子项后，中间显示它的判断、缺口、行动与差异，右侧显示它的证据与应备证据覆盖。",
      "每条证据显示资料文件、页码、定位精度与降级原因；「仅页码」表示只能确定到整页，没有文字坐标高亮。",
      "窄窗口时通过「规则 / 判断 / 证据」标签切换三个工作区，切换后当前选择保持不变。",
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
      "任务列表显示每项资料整理的进度；点击查看处理记录。",
      "任务状态有固定中文说明：准备中、正在整理资料、部分资料尚未处理、处理失败可重试、已保存进度可继续、已取消、资料发生变化需重新核对、已完成。",
      "失败或暂停的任务可以继续或稍后再试；已完成部分始终保留。",
    ],
  },
  {
    title: "报告与方案",
    steps: [
      "「方案工作台」比较当前方案与新版草稿的差异；新内容为草稿，不改变当前审核。",
      "「报告」提供个例、中心与项目报告的入口；界面试用期间不会生成真实文件。",
    ],
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
    </div>
  );
}

export default HelpPage;
