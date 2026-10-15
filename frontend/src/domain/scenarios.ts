/**
 * 命名 UI 场景：覆盖 `contracts/v1/interaction/UAT_PHASE1.md` 全部 14 项脚本化任务。
 * 每个场景引用真实 fixture 实体（episode/action/span/document），
 * 由 scenarios.test.ts 校验引用存在性，防止场景与数据漂移。
 * prototypeOnly=true 的场景其交互为本地演示，明确标记为原型场景，
 * 不虚构 OCR/审核/后台已经完成。
 */

import type { LocatorPrecision } from "./enums";
import {
  toId,
  type ActionId,
  type EvidenceSpanId,
  type ReviewEpisodeId,
  type SourceDocumentVersionId,
} from "./ids";
import type { UiScenario } from "./viewModels";

const episode = (id: string): ReviewEpisodeId => toId<ReviewEpisodeId>(id);
const action = (id: string): ActionId => toId<ActionId>(id);
const span = (id: string): EvidenceSpanId => toId<EvidenceSpanId>(id);
const document = (id: string): SourceDocumentVersionId =>
  toId<SourceDocumentVersionId>(id);

const GAP_SCREENING = episode("episode-uat-03-screening-gap_conflict");
const BARRIER_SCREENING = episode("episode-uat-02-screening-barrier");
const CLEAR_SCREENING = episode("episode-uat-01-screening-clear");
const GAP_SPAN = span("span-uat-03-screening-gap-page");
const GAP_DOC = document("document-uat-03-screening-gap_conflict");
const BARRIER_SPAN = span("span-uat-02-screening-barrier-risk");
const BARRIER_DOC = document("document-uat-02-screening-barrier");

const keyTarget = (
  spanId: string,
  pageNumber: number,
  precision: LocatorPrecision,
): UiScenario["keyEvidence"] => ({
  spanId: span(spanId),
  pageNumber,
  precision,
  maxClicksFromEntry: 3,
});

export const UAT_SCENARIOS: ReadonlyArray<UiScenario> = [
  {
    id: "uat-p1-01",
    uatId: "UAT-P1-01",
    title: "首次进入与今日工作",
    task: "直接进入系统，找到今天需要优先处理的事项，并说明当前项目、受试者/对象、审核节点、主要风险和下一步。",
    entrySurface: "今日工作",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING, BARRIER_SCREENING],
      actionIds: [action("action-uat-03-screening-gap-age")],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "无登录直达今日工作或项目看板",
      "能指出对象、当前节点、至少一个风险/缺口和下一步",
      "提供进入相关受试者阶段的入口",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-02",
    uatId: "UAT-P1-02",
    title: "创建项目并选择独立阶段",
    task: "从方案创建一个项目，确认研究期别，然后进入筛选阶段，并说明筛选和基线是否为同一个审核节点。",
    entrySurface: "项目看板/新建项目",
    fixtureRefs: {
      episodeIds: [
        CLEAR_SCREENING,
        episode("episode-uat-01-baseline-clear"),
        episode("episode-uat-07-pre_screening-clear"),
        episode("episode-uat-08-run_in-gap_conflict"),
      ],
      actionIds: [],
      spanIds: [],
      documentIds: [],
      usesProtocolDiff: false,
    },
    keyEvidence: null,
    acceptance: [
      "保存方案版本和研究期别",
      "筛选阶段被单独选中并显示在当前位置",
      "筛选与基线是两个独立审核节点，不合并为总状态",
      "不静默带入旧项目或其他阶段资料",
    ],
    prototypeOnly: true,
  },
  {
    id: "uat-p1-03",
    uatId: "UAT-P1-03",
    title: "方案工作台比较当前与新版本",
    task: "在方案工作台比较当前版本和新版本，找到一处新增、一处删除和一处逻辑或时间窗变化，并说明哪一版仍是当前使用版本。",
    entrySurface: "方案工作台",
    fixtureRefs: {
      episodeIds: [CLEAR_SCREENING],
      actionIds: [],
      spanIds: [],
      documentIds: [],
      usesProtocolDiff: true,
    },
    keyEvidence: null,
    acceptance: [
      "当前结果与新结果并列，变化类型清楚（新增 EX-05、删除 REQ-02、变化 EX-01）",
      "能回到变化对应的方案原文定位",
      "新内容仍是草稿，当前规则版本未被覆盖",
      "不要求用户理解内部运行方式即可完成比较",
    ],
    prototypeOnly: true,
  },
  {
    id: "uat-p1-04",
    uatId: "UAT-P1-04",
    title: "项目看板筛选、排序与阶段计数",
    task: "只看筛选阶段，筛出有当前节点缺口的受试者，再按阻断程度排序，指出明确障碍和资料缺口各是哪一位，并说明溯源待办是否等于阻断。",
    entrySurface: "项目看板",
    fixtureRefs: {
      episodeIds: [
        CLEAR_SCREENING,
        episode("episode-uat-01-baseline-clear"),
        BARRIER_SCREENING,
        episode("episode-uat-02-baseline-barrier"),
        GAP_SCREENING,
        episode("episode-uat-03-baseline-gap_conflict"),
        episode("episode-uat-04-screening-gap_conflict"),
        episode("episode-uat-04-baseline-gap_conflict"),
        episode("episode-uat-05-screening-clear"),
        episode("episode-uat-05-baseline-clear"),
        episode("episode-uat-06-screening-barrier"),
        episode("episode-uat-06-baseline-barrier"),
      ],
      actionIds: [],
      spanIds: [],
      documentIds: [],
      usesProtocolDiff: false,
    },
    keyEvidence: null,
    acceptance: [
      "筛选条件明确标出当前阶段",
      "结果顺序和计数与 fixture 预期一致（筛选期：明确障碍 2、当前节点缺口 2、后续关注 2）",
      "明确障碍、资料缺口和溯源待办不混为一个状态",
      "切换排序后回到列表，筛选、勾选和滚动位置保持",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-05",
    uatId: "UAT-P1-05",
    title: "从看板进入指定受试者阶段",
    task: "从看板直接打开指定受试者的筛选审核（不先打开基线），说出当前受试者、审核节点和资料版本，再返回看板。",
    entrySurface: "项目看板",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING],
      actionIds: [],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "直接进入正确受试者的筛选 ReviewEpisode",
      "页面明确显示阶段、方案版本和资料版本",
      "不把基线资料混成筛选结论",
      "返回后保留看板筛选、排序和滚动位置",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-06",
    uatId: "UAT-P1-06",
    title: "Patient Profile 首屏风险过滤与完整资料",
    task: "先只看这位受试者当前入排相关、异常、临界、趋势和资料缺口，再找到一项完整资料，并说明“资料中未提到”与“明确否认”是否相同。",
    entrySurface: "受试者与 Patient Profile",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING],
      actionIds: [],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "首屏先显示风险过滤和关键事件，不无差别铺开全部正常结果",
      "能打开完整资料并返回风险视图",
      "“资料中未提到”显示为资料缺口，不被说成明确否认",
      "冲突来源并列可见，后续阶段资料有阶段标记",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-07",
    uatId: "UAT-P1-07",
    title: "规则树、父子层级与证据跳转",
    task: "展开指定父规则（EX-01），找到任务卡中的子项，说明父项和子项的关系，然后打开支持该子项的原文件证据。",
    entrySurface: "入排工作台",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING],
      actionIds: [],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "父级编号、子项编号和逻辑关系正确（EX-01a：全部满足，含任一满足/不满足以下条件子项与例外条件）",
      "证据区域显示文件、版本、页码、摘录和实际定位精度",
      "从规则起始页到正确文件/页和定位精度可见不超过 3 次操作",
      "不把任一子项误说成独立父级，不把任一满足说成全部满足",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-08",
    uatId: "UAT-P1-08",
    title: "原文定位范围与诚实说明",
    task: "依次打开页内摘录和仅页码定位，说明系统能确定到什么程度、哪些位置不能作为重点标注，并解释定位范围有限的原因。",
    entrySurface: "入排工作台/证据区",
    fixtureRefs: {
      episodeIds: [CLEAR_SCREENING, BARRIER_SCREENING, GAP_SCREENING],
      actionIds: [],
      spanIds: [
        span("span-uat-01-screening-clear-age"),
        span("span-uat-01-screening-clear-history"),
        BARRIER_SPAN,
        GAP_SPAN,
      ],
      documentIds: [
        document("document-uat-01-screening-clear"),
        BARRIER_DOC,
        GAP_DOC,
      ],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "页面显示坐标区域/文本范围/页内摘录/仅页码等实际中文精度",
      "仅页码项没有坐标框或虚假高亮",
      "能指出文件、版本和页码，并能打开整页查看",
      "定位范围说明自然可读，不被误解为已精确到具体文字",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-09",
    uatId: "UAT-P1-09",
    title: "缺口、责任方、可接受证据与到期节点",
    task: "找到一项当前节点缺口、一项需专业判断和一项溯源待办，说明谁负责、要做什么、什么证据可以关闭、最晚在哪个阶段完成，并指出哪项不阻断当前节点。",
    entrySurface: "行动中心",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING, CLEAR_SCREENING],
      actionIds: [
        action("action-uat-03-screening-gap-age"),
        action("action-uat-03-screening-gap-professional"),
        action("action-uat-01-screening-clear-provenance"),
        action("action-uat-03-screening-gap-future"),
      ],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: null,
    acceptance: [
      "判断状态和缺口原因分开显示",
      "责任方使用研究者方/CRC/CRA/申办方医学或项目组等自然中文",
      "每项有具体动作、可接受证据、到期节点、关联规则和来源",
      "溯源待办可计数但不被说成明确障碍；后续节点尚未到期不被说成当前缺口",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-10",
    uatId: "UAT-P1-10",
    title: "Action 人工确认与重新核对",
    task: "查看行动为什么存在和什么资料可以关闭；对指定行动进行人工确认，填写真实可读的理由，然后查看关闭后的规则状态、前后差异和新的审核运行。",
    entrySurface: "行动中心",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING],
      actionIds: [action("action-uat-03-screening-gap-professional")],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "确认前显示具体对象、影响、来源和理由要求",
      "无关文件不会关闭该行动",
      "人工确认有理由、时间、操作者和不可变转移记录",
      "页面明确区分行动关闭与规则状态；若状态改变则显示新的审核运行和差异（原型）",
    ],
    prototypeOnly: true,
  },
  {
    id: "uat-p1-11",
    uatId: "UAT-P1-11",
    title: "批量选择与范围确认",
    task: "只勾选任务卡指定的两位受试者，执行批量动作并核对完成摘要；排序一次，确认没有其他受试者被包含、原勾选范围没有悄悄扩大。",
    entrySurface: "项目看板",
    fixtureRefs: {
      episodeIds: [
        GAP_SCREENING,
        episode("episode-uat-04-screening-gap_conflict"),
      ],
      actionIds: [],
      spanIds: [],
      documentIds: [],
      usesProtocolDiff: false,
    },
    keyEvidence: null,
    acceptance: [
      "页面显示已选择数量和明确范围",
      "批量确认前显示对象和动作",
      "完成摘要只有指定的两位受试者",
      "排序/刷新后选择、滚动和当前范围可解释，未勾选对象不被默认加入",
    ],
    prototypeOnly: true,
  },
  {
    id: "uat-p1-12",
    uatId: "UAT-P1-12",
    title: "任务中断与恢复",
    task: "打开任务，确认已经完成的部分，关闭页面重新进入，继续未完成事项，指出失败资料、影响范围和下一步，不重复已完成部分。",
    entrySurface: "任务与系统帮助",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING],
      actionIds: [],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "重新进入后显示已保存进度",
      "已完成内容不重复生成，未完成和失败范围清楚",
      "失败资料显示“资料发生变化，当前结果需要重新核对”或等价自然中文",
      "能继续、稍后再试或取消未完成部分，历史已完成部分仍保留",
    ],
    prototypeOnly: true,
  },
  {
    id: "uat-p1-13",
    uatId: "UAT-P1-13",
    title: "窄屏工作台与页面级横向滚动",
    task: "在窄窗口中打开这位受试者的规则、判断和证据，依次切换三个工作区，打开一个证据，再回到当前规则，说明是否需要拖动整个页面。",
    entrySurface: "入排工作台（窄屏）",
    fixtureRefs: {
      episodeIds: [GAP_SCREENING],
      actionIds: [],
      spanIds: [GAP_SPAN],
      documentIds: [GAP_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-03-screening-gap-page", 4, "page_only"),
    acceptance: [
      "规则、判断、证据通过标签页或抽屉堆叠，当前选择持续可见",
      "可以打开关键证据并回到同一规则/阶段",
      "页面没有整体横向滚动，只有必要的密集组件内部滚动",
      "状态词、按钮、工具提示不裁切，键盘焦点清楚",
    ],
    prototypeOnly: false,
  },
  {
    id: "uat-p1-14",
    uatId: "UAT-P1-14",
    title: "100/150/200% 缩放下的关键路径",
    task: "在三个缩放级别分别打开 Patient Profile 风险项、规则子项和 EvidenceSpan，完成一次证据返回，指出是否有文字覆盖、按钮裁切、焦点丢失或页面横向滚动。",
    entrySurface: "入排工作台/Patient Profile",
    fixtureRefs: {
      episodeIds: [BARRIER_SCREENING],
      actionIds: [],
      spanIds: [BARRIER_SPAN],
      documentIds: [BARRIER_DOC],
      usesProtocolDiff: false,
    },
    keyEvidence: keyTarget("span-uat-02-screening-barrier-risk", 3, "page_excerpt"),
    acceptance: [
      "100%、150%、200% 均能完成关键路径",
      "中文状态、缺口、证据精度和主要动作不被裁切或覆盖",
      "150%/200% 可收起侧栏、切换标签页或组件内滚动，不以缩小字号掩盖问题",
      "不因布局得出错误状态或错误证据结论",
    ],
    prototypeOnly: false,
  },
];
