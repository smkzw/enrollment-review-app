/**
 * 入排审核界面试用记录工作台——核心数据模块（worker_01 交付）。
 *
 * 边界：
 * - 原生 ES module，无第三方依赖，不操作 DOM，不读写桌面文件，不访问浏览器存储。
 * - 只负责：14 项中文任务定义、8 类错误定义（E1–E8，另含 E0 无错误）、单一原始记录模型、
 *   备份结构校验与规范化、批次汇总，以及 Markdown / CSV / 本机备份文本三种导出与恢复解析。
 * - 记录数据使用独立的本地存储键命名空间（RECORDER_STORAGE_KEY），
 *   与参与者界面试用状态（`eligibility-review:uat:` 登记键）互不干扰。
 * - 记录工具版本（RECORDER_TOOL_VERSION）独立于参与者页面版本，不参与混算。
 * - 所有统计全部派生自逐项原始记录，本模块不提供任何手工覆盖统计结果的入口。
 *
 * 口径（与 contracts/v1/interaction/UAT_PHASE1.md 保持一致）：
 * - 已记录运行：该任务行有任一填写内容（含无效运行标记、备注、计时、错误类别等）。
 * - 有效运行：已记录且未标记为无效运行（环境或脚本故障）。无效运行必须保存剔除原因。
 * - 无辅助完成：有效运行中「是否完成 = 是」，且未获得辅助（「是否获得提示」≠ 是，错误类别不含 E8）。
 * - 未填写：完成/提示/评分等字段为 null（导出显示为空），与「否」严格区分，绝不参与通过判定。
 * - 关键证据操作数：null 表示不适用或未填写；UAT-P1-07 至 UAT-P1-10、UAT-P1-14 需逐次记录，
 *   超过 3 次的运行单独计数并触发停止提示。
 * - 分母为 0 时，相关比例与门槛显示「无法计算」，绝不显示通过。
 */

/** 记录工作台名称（界面只显示该中文名称，不显示内部状态名）。 */
export const RECORDER_TOOL_NAME = "入排审核界面试用记录工作台";

/** 记录工具版本，独立于参与者页面版本。 */
export const RECORDER_TOOL_VERSION = "1.0.0";

/** 记录数据本地存储键：与参与者的界面试用状态命名空间分离，复位操作不得清除。 */
export const RECORDER_STORAGE_KEY = "eligibility-review:uat-recorder:batch";

/** 本机备份文件标识与版本。 */
export const BACKUP_SCHEMA = "enrollment-review/uat-recorder-backup";
export const BACKUP_VERSION = 1;

/** 正式 UAT 冻结的临时量化门槛（只读常量，界面与汇总统一引用）。 */
export const FREEZE_THRESHOLDS = Object.freeze({
  validParticipants: 10,
  validRuns: 140,
  overallUnassistedRate: 0.9,
  perTaskUnassistedRate: 0.8,
  errorConclusion: 0,
  criticalEvidenceMaxOps: 3,
});

/** 完成后两项主观评分问题（1 至 5 分）。 */
export const RATING_QUESTIONS = Object.freeze([
  { key: "nextStep", question: "我能看懂下一步要做什么" },
  { key: "evidenceTrust", question: "我信任系统展示的证据定位" },
]);

/** 「本次记录是否有效」四项确认（来自原始记录表模板）。 */
export const VALIDITY_CHECKLIST_ITEMS = Object.freeze([
  "全程使用约定的合成示例数据和同一页面版本。",
  "记录人员未提示路径、按钮、状态答案或代替操作。",
  "所有失败、放弃和错误均保留，没有删除不利记录。",
  "如发生错误结论，本轮试用已暂停并转入问题复现。",
]);

/** 14 项中文任务定义：任务卡名称、合同名称、固定起始页、目标与关键证据要求。 */
const TASK_DEFS = [
  {
    id: "UAT-P1-01",
    title: "今日工作",
    contractTitle: "首次进入与今日工作",
    startPage: "今日工作（系统首页，无需登录）",
    goal: "从首页找到今天需要优先处理的事项，说明当前项目、对象、审核节点、主要风险和下一步。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-02",
    title: "新建项目",
    contractTitle: "创建项目并选择独立阶段",
    startPage: "项目看板（顶部「从方案新建项目」）",
    goal: "从方案创建一个项目，确认研究期别，进入筛选期审核节点，并说明筛选与基线是否是同一个审核节点。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-03",
    title: "方案比较",
    contractTitle: "方案工作台比较当前与新版本",
    startPage: "方案工作台",
    goal: "比较当前使用版本与新版本草稿，把 EX-05、必做-02、EX-01 归入新增/删除/逻辑或时间范围变化，打开一处方案原文，保存草稿并说明哪一版仍是当前使用版本。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-04",
    title: "看板筛选排序",
    contractTitle: "项目看板筛选、排序与阶段计数",
    startPage: "项目看板",
    goal: "只看筛选期，筛出存在当前节点缺口的受试者并按阻断程度排序，指出明确障碍与资料缺口各是哪一位，说明溯源待办是否等于阻断。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-05",
    title: "看板直达节点",
    contractTitle: "从看板进入指定受试者阶段",
    startPage: "项目看板",
    goal: "从看板直接打开 UAT-03 的筛选期审核，不先打开基线期；说明受试者、审核节点、方案版本和资料快照后返回看板。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-06",
    title: "个例全景",
    contractTitle: "Patient Profile 首屏风险过滤与完整资料",
    startPage: "受试者与资料",
    goal: "先只看 UAT-03 筛选期当前入排相关、异常、临界、趋势和资料缺口，再打开完整明细并返回；说明「资料中未提到」与「明确否认」是否相同。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-07",
    title: "规则树证据跳转",
    contractTitle: "规则树、父子层级与证据跳转",
    startPage: "入排工作台（UAT-03 筛选期）",
    goal: "展开父规则 EX-01，找到子项 EX-01a，说明父子关系与「全部满足/任一满足」，再打开支持该子项的原始资料证据；关键证据操作数不超过 3 次。",
    criticalEvidenceRequired: true,
  },
  {
    id: "UAT-P1-08",
    title: "证据定位精度",
    contractTitle: "EvidenceSpan 降级与定位诚实性",
    startPage: "入排工作台（证据区）",
    goal: "依次打开「页内摘录」和「仅页码」两种定位的证据，说明系统能确定到什么程度、哪些位置不能当作精确文字高亮，以及定位降级原因；关键证据操作数不超过 3 次。",
    criticalEvidenceRequired: true,
  },
  {
    id: "UAT-P1-09",
    title: "三类待办",
    contractTitle: "缺口、责任方、可接受证据与到期节点",
    startPage: "行动中心",
    goal: "分别找到一项当前节点资料缺口、一项需研究者专业判断和一项溯源待办，逐项说明谁负责、要做什么、什么资料可以关闭、最晚在哪个节点完成，指出哪项不阻断当前节点；关键证据操作数不超过 3 次。",
    criticalEvidenceRequired: true,
  },
  {
    id: "UAT-P1-10",
    title: "人工确认",
    contractTitle: "Action override（人工确认）与重新核对",
    startPage: "行动中心",
    goal: "查看 UAT-03 的需研究者专业判断行动为什么存在和什么资料可以关闭，填写真实可读的理由并确认；说明行动关闭是否等于关联规则通过，重新打开核对确认记录仍保留；关键证据操作数不超过 3 次。",
    criticalEvidenceRequired: true,
  },
  {
    id: "UAT-P1-11",
    title: "批量范围",
    contractTitle: "批量选择与范围确认",
    startPage: "项目看板",
    goal: "只勾选 UAT-03 和 UAT-04 执行批量回看审核摘要，确认前和完成后都核对对象清单，改变排序后再次确认勾选范围没有悄悄扩大。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-12",
    title: "任务恢复",
    contractTitle: "任务中断与恢复",
    startPage: "任务与系统（「继续未完成事项」）",
    goal: "区分已经完成、尚未处理和处理失败可重试的资料，继续完成一项后离开页面再返回，确认已完成进度保留、未重复处理已完成资料。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-13",
    title: "窄屏工作台",
    contractTitle: "窄屏工作台与页面级横向滚动",
    startPage: "入排工作台（窄窗口）",
    goal: "缩窄浏览器窗口，在 UAT-03 筛选期依次切换「规则、判断、证据」三个工作区，打开并关闭一次原始资料证据再返回规则；确认受试者、审核节点和当前规则没有丢失，观察是否出现整页左右拖动。",
    criticalEvidenceRequired: false,
  },
  {
    id: "UAT-P1-14",
    title: "三档缩放",
    contractTitle: "100/150/200% 缩放下的关键路径",
    startPage: "入排工作台 / 受试者与资料",
    goal: "分别在 100%、150%、200% 缩放下完成一次「个例风险 → 规则子项 → 原始证据 → 返回」，观察文字、按钮和弹窗是否重叠、裁切或需要整页左右拖动；关键证据操作数不超过 3 次。",
    criticalEvidenceRequired: true,
  },
];

export const TASKS = Object.freeze(TASK_DEFS.map((task) => Object.freeze(task)));
export const TASK_IDS = Object.freeze(TASKS.map((task) => task.id));
export const TASK_BY_ID = Object.freeze(new Map(TASKS.map((task) => [task.id, task])));

/** 任务编号到 14 项顺序下标的映射（供逐任务汇总使用）。 */
const TASK_INDEX_BY_ID = new Map(TASKS.map((task, index) => [task.id, index]));

function taskDisplay(taskId) {
  const index = TASK_INDEX_BY_ID.get(taskId);
  return index == null ? "未识别任务" : `第 ${String(index + 1).padStart(2, "0")} 项`;
}

/** 错误类别定义：E0 无错误，E1–E8 为 8 类错误（与 UAT 合同 §1.4 一致）。 */
const ERROR_DEFS = [
  {
    id: "E0",
    name: "无错误",
    definition: "无提示完成，成功证据全部满足。",
    isError: false,
    isErrorConclusion: false,
    isAssistance: false,
  },
  {
    id: "E1",
    name: "操作错误",
    definition: "点击了错误控件、重复操作、误取消或误提交，但未形成错误结论。",
    isError: true,
    isErrorConclusion: false,
    isAssistance: false,
  },
  {
    id: "E2",
    name: "导航错误",
    definition: "进入错误项目、受试者、阶段、规则或页面，或无法返回正确位置。",
    isError: true,
    isErrorConclusion: false,
    isAssistance: false,
  },
  {
    id: "E3",
    name: "术语/信息理解错误",
    definition: "把中文状态、缺口、责任方或阶段含义理解错，但未正式提交错误结论。",
    isError: true,
    isErrorConclusion: false,
    isAssistance: false,
  },
  {
    id: "E4",
    name: "错误结论",
    definition: "因界面、状态或证据表现而把合成示例资料的状态、规则或冲突判断成相反结果；立即按停止条件处理，计数必须为 0。",
    isError: true,
    isErrorConclusion: true,
    isAssistance: false,
  },
  {
    id: "E5",
    name: "证据/溯源错误",
    definition: "无法回到正确文件/页、把页码定位说成坐标定位、遗漏冲突来源或把转述当原始证据。",
    isError: true,
    isErrorConclusion: false,
    isAssistance: false,
  },
  {
    id: "E6",
    name: "任务状态/恢复错误",
    definition: "丢失已完成进度、重复应用动作、误把部分完成当全部完成或无法继续。",
    isError: true,
    isErrorConclusion: false,
    isAssistance: false,
  },
  {
    id: "E7",
    name: "布局/键盘错误",
    definition: "裁切、重叠、页面横向滚动、焦点丢失、勾选跳顶或键盘无法完成。",
    isError: true,
    isErrorConclusion: false,
    isAssistance: false,
  },
  {
    id: "E8",
    name: "获得辅助",
    definition: "主持人以路径、按钮、状态或证据答案形式提示，或替参与者操作；该任务不计入无辅助完成。",
    isError: true,
    isErrorConclusion: false,
    isAssistance: true,
  },
];

export const ERROR_CATEGORIES = Object.freeze(ERROR_DEFS.map((entry) => Object.freeze(entry)));
export const ERROR_TYPES = Object.freeze(ERROR_CATEGORIES.filter((entry) => entry.isError));
export const ERROR_BY_ID = Object.freeze(new Map(ERROR_CATEGORIES.map((entry) => [entry.id, entry])));
const ERROR_ORDER = ERROR_CATEGORIES.map((entry) => entry.id);

/* ------------------------------------------------------------------ */
/* 空记录构造函数                                                       */
/* ------------------------------------------------------------------ */

/**
 * 创建一条空白任务记录。taskId 必须是 14 项任务之一。
 * 关键点：completed / assisted 等判定字段初始为 null（未填写），与「否」(false) 严格区分。
 */
export function createEmptyTaskRecord(taskId, overrides = {}) {
  const task = TASK_BY_ID.get(taskId);
  if (!task) {
    throw new RangeError(`未定义的任务编号：${String(taskId)}`);
  }
  return {
    taskId: task.id,
    startTime: null,
    endTime: null,
    durationSeconds: null,
    totalOperations: null,
    criticalEvidenceOperations: null,
    completed: null,
    assisted: null,
    errorCategories: [],
    notes: "",
    facilitatorNotes: "",
    isInvalid: false,
    invalidReason: "",
    layoutIssue: null,
    updatedAt: "",
    ...overrides,
  };
}

/** 创建一名空白参与者，自带 14 项空白任务记录与两项未填写的评分。 */
export function createEmptyParticipant(overrides = {}) {
  return {
    code: "",
    pageVersion: "",
    browser: "",
    windowWidth: null,
    zoom: "100%",
    recorderCode: "",
    testDate: "",
    startedAt: "",
    finishedAt: "",
    taskRecords: Object.fromEntries(
      TASKS.map((task) => [task.id, createEmptyTaskRecord(task.id)])
    ),
    ratings: {
      nextStep: null,
      evidenceTrust: null,
      nextStepNote: "",
      evidenceTrustNote: "",
    },
    validityChecklist: [false, false, false, false],
    signature: "",
    signDate: "",
    ...overrides,
  };
}

/** 创建空白批次（不含参与者）。页面版本与资料版本由界面从当前页照录/预填。 */
export function createEmptyBatch(overrides = {}) {
  return {
    batchCode: "",
    startDate: "",
    endDate: "",
    pageVersion: "",
    fixtureVersion: "示例资料第1版",
    recorderCode: "",
    facilitatorCode: "",
    notes: "",
    participants: [],
    createdAt: "",
    updatedAt: "",
    ...overrides,
  };
}

/* ------------------------------------------------------------------ */
/* 校验与规范化                                                         */
/* ------------------------------------------------------------------ */

function failure(errors) {
  return { ok: false, errors, value: null };
}

function trimText(value, path, errors) {
  if (value == null) return "";
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  errors.push(`${path}必须是文字`);
  return "";
}

function nullableText(value) {
  if (value == null) return null;
  const text = String(value).trim();
  return text === "" ? null : text;
}

function toFiniteNumber(value, path, errors) {
  if (value == null || value === "") return null;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      errors.push(`${path}不是有限数值`);
      return null;
    }
    return value;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (trimmed === "") return null;
    const parsed = Number(trimmed);
    if (!Number.isFinite(parsed)) {
      errors.push(`${path}不是有限数值：${trimmed}`);
      return null;
    }
    return parsed;
  }
  errors.push(`${path}不是有限数值`);
  return null;
}

function numberField(value, path, errors, { integer = false, min = null } = {}) {
  const number = toFiniteNumber(value, path, errors);
  if (number === null) return null;
  if (integer && !Number.isInteger(number)) {
    errors.push(`${path}必须是整数：${number}`);
    return null;
  }
  if (min !== null && number < min) {
    errors.push(`${path}不能小于 ${min}：${number}`);
    return null;
  }
  return number;
}

function booleanField(value, path, errors) {
  if (value == null || value === "") return null;
  if (value === true || value === false) return value;
  errors.push(`${path}必须是「是/否/未填写」`);
  return null;
}

function ratingField(value, path, errors) {
  const number = numberField(value, path, errors, { integer: true, min: 1 });
  if (number === null) return null;
  if (number > 5) {
    errors.push(`${path}必须是 1 至 5 的整数：${number}`);
    return null;
  }
  return number;
}

function normalizeTaskRecord(taskId, raw, loc, errors) {
  const durationSeconds = numberField(raw.durationSeconds, `${loc}的「用时（秒）」`, errors, { min: 0 });
  const totalOperations = numberField(raw.totalOperations, `${loc}的「总操作数」`, errors, { integer: true, min: 0 });
  const criticalEvidenceOperations = numberField(
    raw.criticalEvidenceOperations,
    `${loc}的「关键证据操作数」`,
    errors,
    { integer: true, min: 0 }
  );
  const completed = booleanField(raw.completed, `${loc}的「是否完成」`, errors);
  const assisted = booleanField(raw.assisted, `${loc}的「是否获得提示」`, errors);
  const isInvalid =
    raw.isInvalid == null || raw.isInvalid === ""
      ? false
      : booleanField(raw.isInvalid, `${loc}的「是否无效运行」`, errors);
  const layoutIssue = booleanField(raw.layoutIssue, `${loc}的「是否出现页面级横向滚动或布局问题」`, errors);

  const errorCategories = [];
  if (raw.errorCategories != null) {
    if (!Array.isArray(raw.errorCategories)) {
      errors.push(`${loc}的「错误类别」必须是列表`);
    } else {
      for (const category of raw.errorCategories) {
        if (typeof category !== "string" || !ERROR_BY_ID.has(category)) {
          errors.push(`${loc}包含未定义的错误类别：${category == null ? "（空）" : String(category)}`);
        } else if (!errorCategories.includes(category)) {
          errorCategories.push(category);
        }
      }
      errorCategories.sort((a, b) => ERROR_ORDER.indexOf(a) - ERROR_ORDER.indexOf(b));
    }
  }

  return {
    taskId,
    startTime: nullableText(raw.startTime),
    endTime: nullableText(raw.endTime),
    durationSeconds,
    totalOperations,
    criticalEvidenceOperations,
    completed,
    assisted,
    errorCategories,
    notes: trimText(raw.notes, `${loc}的「参与者原话、错误位置与自行恢复过程」`, errors),
    facilitatorNotes: trimText(raw.facilitatorNotes, `${loc}的「主持人提示或代操作」`, errors),
    isInvalid,
    invalidReason: trimText(raw.invalidReason, `${loc}的「剔除原因」`, errors),
    layoutIssue,
    updatedAt: nullableText(raw.updatedAt),
  };
}

function normalizeParticipant(raw, index, errors) {
  const loc = `第 ${index + 1} 位参与者`;
  const code = trimText(raw.code, `${loc}的参与者代号`, errors);

  const taskRecords = {};
  const rawRecords = raw.taskRecords;
  if (rawRecords == null || typeof rawRecords !== "object" || Array.isArray(rawRecords)) {
    errors.push(`${loc}缺少 14 项任务记录`);
  } else {
    const missing = TASK_IDS.filter((id) => !(id in rawRecords));
    const unknown = Object.keys(rawRecords).filter((key) => !TASK_BY_ID.has(key));
    if (missing.length > 0) {
      errors.push(`${loc}缺少任务记录：${missing.join("、")}`);
    }
    if (unknown.length > 0) {
      errors.push(`${loc}包含未定义的任务编号：${unknown.join("、")}`);
    }
  }
  for (const task of TASKS) {
    const record =
      rawRecords != null && typeof rawRecords === "object" && !Array.isArray(rawRecords)
        ? rawRecords[task.id]
        : undefined;
    taskRecords[task.id] = normalizeTaskRecord(
      task.id,
      record != null && typeof record === "object" && !Array.isArray(record) ? record : {},
      `${loc}任务 ${task.id}`,
      errors
    );
  }

  const ratings = { nextStep: null, evidenceTrust: null, nextStepNote: "", evidenceTrustNote: "" };
  if (raw.ratings != null) {
    if (typeof raw.ratings !== "object" || Array.isArray(raw.ratings)) {
      errors.push(`${loc}的评分记录不是对象`);
    } else {
      ratings.nextStep = ratingField(raw.ratings.nextStep, `${loc}的「${RATING_QUESTIONS[0].question}」评分`, errors);
      ratings.evidenceTrust = ratingField(
        raw.ratings.evidenceTrust,
        `${loc}的「${RATING_QUESTIONS[1].question}」评分`,
        errors
      );
      ratings.nextStepNote = trimText(raw.ratings.nextStepNote, `${loc}的评分原因①`, errors);
      ratings.evidenceTrustNote = trimText(raw.ratings.evidenceTrustNote, `${loc}的评分原因②`, errors);
    }
  }

  let validityChecklist = [false, false, false, false];
  if (raw.validityChecklist != null) {
    if (!Array.isArray(raw.validityChecklist)) {
      errors.push(`${loc}的「本次记录是否有效」确认项必须是列表`);
    } else {
      validityChecklist = VALIDITY_CHECKLIST_ITEMS.map((_, i) => raw.validityChecklist[i] === true);
    }
  }

  return {
    code,
    pageVersion: trimText(raw.pageVersion, `${loc}的页面版本`, errors),
    browser: trimText(raw.browser, `${loc}的浏览器`, errors),
    windowWidth: numberField(raw.windowWidth, `${loc}的窗口宽度`, errors, { integer: true, min: 1 }),
    zoom: trimText(raw.zoom, `${loc}的浏览器缩放`, errors),
    recorderCode: trimText(raw.recorderCode, `${loc}的记录人员代号`, errors),
    testDate: trimText(raw.testDate, `${loc}的测试日期`, errors),
    startedAt: nullableText(raw.startedAt),
    finishedAt: nullableText(raw.finishedAt),
    taskRecords,
    ratings,
    validityChecklist,
    signature: trimText(raw.signature, `${loc}的记录人员签名`, errors),
    signDate: trimText(raw.signDate, `${loc}的签名日期`, errors),
  };
}

/**
 * 校验并规范化一个批次对象。任何错误都会导致 ok=false 并列出中文原因。
 * 严格拒绝：重复参与者代号、缺失 14 项任务记录、未定义的任务编号或错误类别、
 * 非有限数值（含 Infinity/NaN）、负操作数、非 1–5 的评分。
 * 规范化：修剪文字、空值统一为 null/""、错误类别去重并按 E0–E8 排序、只保留登记字段。
 */
export function normalizeBatch(input) {
  if (input == null || typeof input !== "object" || Array.isArray(input)) {
    return failure(["批次数据必须是对象"]);
  }
  const errors = [];
  if (!Array.isArray(input.participants)) {
    return failure(["批次缺少参与者列表"]);
  }

  const seenCodes = new Map();
  const duplicateCodes = new Set();
  const participants = [];

  for (let i = 0; i < input.participants.length; i++) {
    const raw = input.participants[i];
    if (raw == null || typeof raw !== "object" || Array.isArray(raw)) {
      errors.push(`第 ${i + 1} 位参与者的记录不是对象`);
      continue;
    }
    const participant = normalizeParticipant(raw, i, errors);
    if (participant.code !== "") {
      const count = (seenCodes.get(participant.code) ?? 0) + 1;
      seenCodes.set(participant.code, count);
      if (count > 1) duplicateCodes.add(participant.code);
    }
    participants.push(participant);
  }
  for (const code of duplicateCodes) {
    errors.push(`参与者代号重复：${code}`);
  }

  if (errors.length > 0) {
    return failure(errors);
  }

  const value = {
    batchCode: trimText(input.batchCode, "批次编号", errors),
    startDate: trimText(input.startDate, "开始日期", errors),
    endDate: trimText(input.endDate, "结束日期", errors),
    pageVersion: trimText(input.pageVersion, "页面版本", errors),
    fixtureVersion: trimText(input.fixtureVersion, "合成示例资料版本", errors),
    recorderCode: trimText(input.recorderCode, "记录人员代号", errors),
    facilitatorCode: trimText(input.facilitatorCode, "主持人代号", errors),
    notes: trimText(input.notes, "批次备注", errors),
    participants,
    createdAt: nullableText(input.createdAt),
    updatedAt: nullableText(input.updatedAt),
  };
  if (errors.length > 0) {
    return failure(errors);
  }
  return { ok: true, errors: [], value };
}

function buildBackupMeta(batch) {
  return {
    batchCode: batch.batchCode,
    pageVersion: batch.pageVersion,
    participantCount: batch.participants.length,
    taskRecordCount: batch.participants.reduce(
      (count, participant) =>
        count + Object.values(participant.taskRecords).filter(isRecordedRun).length,
      0
    ),
    fixtureVersion: batch.fixtureVersion,
  };
}

/**
 * 解析并校验本机备份文本（由 generateBackupText 生成）。
 * 严格拒绝：非法 JSON、错误备份标识、错误版本、缺失 14 项任务、重复参与者代号、非有限数值。
 * 成功时返回 { ok: true, errors: [], value: 规范化批次, meta: 导入预览信息 }。
 */
export function parseBackupText(text) {
  if (typeof text !== "string") {
    return failure(["备份文本必须是字符串"]);
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch (error) {
    return failure([`备份文本不是有效的 JSON：${error instanceof Error ? error.message : String(error)}`]);
  }
  if (data == null || typeof data !== "object" || Array.isArray(data)) {
    return failure(["备份内容不是对象"]);
  }
  if (data.schema !== BACKUP_SCHEMA) {
    return failure(["该文件不是本记录工作台的备份文件"]);
  }
  if (typeof data.version !== "number" || data.version !== BACKUP_VERSION) {
    return failure([
      `备份版本不受支持：${data.version == null ? "（缺失）" : String(data.version)}（当前仅支持版本 ${BACKUP_VERSION}）`,
    ]);
  }
  if (data.batch == null || typeof data.batch !== "object" || Array.isArray(data.batch)) {
    return failure(["备份缺少批次数据"]);
  }
  const result = normalizeBatch(data.batch);
  if (!result.ok) {
    return result;
  }
  return { ok: true, errors: [], value: result.value, meta: buildBackupMeta(result.value) };
}

/**
 * 校验备份：接受备份文本（等价于 parseBackupText）或对象。
 * 对象若带 batch/version/schema 字段按备份封套处理，否则按批次对象直接校验。
 */
export function validateBackup(input) {
  if (typeof input === "string") {
    return parseBackupText(input);
  }
  if (input == null || typeof input !== "object" || Array.isArray(input)) {
    return failure(["备份内容不是对象"]);
  }
  let candidate = input;
  if ("batch" in input || "version" in input || "schema" in input) {
    if (typeof input.version !== "number" || input.version !== BACKUP_VERSION) {
      return failure([
        `备份版本不受支持：${input.version == null ? "（缺失）" : String(input.version)}（当前仅支持版本 ${BACKUP_VERSION}）`,
      ]);
    }
    if ("schema" in input && input.schema !== BACKUP_SCHEMA) {
      return failure(["该文件不是本记录工作台的备份文件"]);
    }
    if (input.batch == null) {
      return failure(["备份缺少批次数据"]);
    }
    candidate = input.batch;
  }
  const result = normalizeBatch(candidate);
  if (!result.ok) {
    return result;
  }
  return { ok: true, errors: [], value: result.value, meta: buildBackupMeta(result.value) };
}

/* ------------------------------------------------------------------ */
/* 批次汇总                                                             */
/* ------------------------------------------------------------------ */

function zeroErrorCounts() {
  return { E1: 0, E2: 0, E3: 0, E4: 0, E5: 0, E6: 0, E7: 0, E8: 0 };
}

function isRecordedRun(record) {
  return (
    record.completed !== null ||
    record.assisted !== null ||
    record.isInvalid === true ||
    record.errorCategories.length > 0 ||
    record.durationSeconds != null ||
    record.totalOperations != null ||
    record.criticalEvidenceOperations != null ||
    record.layoutIssue != null ||
    record.notes !== "" ||
    record.facilitatorNotes !== ""
  );
}

function medianOf(values) {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function round2(number) {
  return Math.round(number * 100) / 100;
}

/** 汇总批次。全部统计派生自逐项原始记录；分母为 0 时比例与门槛为「无法计算」，绝不显示通过。 */
export function summarizeBatch(batch) {
  const normalized = normalizeBatch(batch);
  if (!normalized.ok) {
    return { ok: false, errors: normalized.errors, value: null };
  }
  const value = normalized.value;

  const perParticipant = [];
  const perTask = TASKS.map((task) => ({
    taskId: task.id,
    title: task.title,
    validRuns: 0,
    completions: 0,
    unassistedCompletions: 0,
    assistedRuns: 0,
    incompleteRuns: 0,
    invalidRuns: 0,
    unfilled: 0,
    errorCounts: zeroErrorCounts(),
    criticalValues: [],
    criticalOver3Count: 0,
    missingCriticalCount: 0,
  }));

  const errorCounts = zeroErrorCounts();
  const invalidRunDetails = [];
  const e4Runs = [];
  const criticalOver3Runs = [];
  const layoutIssueRuns = [];
  const criticalValues = [];

  let validRunCount = 0;
  let recordedRunCount = 0;
  let invalidRunCount = 0;
  let unfilledTaskCount = 0;
  let completedRunCount = 0;
  let incompleteRecordedRunCount = 0;
  let assistedRunCount = 0;
  let unassistedCompletionCount = 0;
  let layoutCheckedRuns = 0;
  let layoutIssueCount = 0;
  let confirmedParticipantCount = 0;

  for (const participant of value.participants) {
    let participantValidRuns = 0;
    let participantCompleted = 0;
    let participantUnassisted = 0;
    let participantAssisted = 0;
    let participantIncomplete = 0;
    let participantInvalid = 0;
    let participantUnfilled = 0;
    let participantCriticalOver3 = 0;
    const participantErrors = zeroErrorCounts();
    for (const task of TASKS) {
      const record = participant.taskRecords[task.id];
      const taskStats = perTask[TASK_INDEX_BY_ID.get(task.id)];
      if (!isRecordedRun(record)) {
        participantUnfilled += 1;
        unfilledTaskCount += 1;
        taskStats.unfilled += 1;
        continue;
      }
      recordedRunCount += 1;

      // 错误结论属于正式试用历史，即使该次运行随后因环境原因被标记无效，
      // 也不得从 E4 计数和停止提示中消失。
      if (record.errorCategories.includes("E4")) {
        errorCounts.E4 += 1;
        participantErrors.E4 += 1;
        taskStats.errorCounts.E4 += 1;
        e4Runs.push({
          participantCode: participant.code || "（未填写代号）",
          taskId: task.id,
          notes: record.notes,
          invalidRun: record.isInvalid,
        });
      }
      if (record.isInvalid) {
        participantInvalid += 1;
        invalidRunCount += 1;
        taskStats.invalidRuns += 1;
        invalidRunDetails.push({
          participantCode: participant.code || "（未填写代号）",
          taskId: task.id,
          reason: record.invalidReason || "未填写剔除原因",
        });
        continue;
      }
      participantValidRuns += 1;
      validRunCount += 1;
      taskStats.validRuns += 1;

      for (const category of record.errorCategories) {
        if (category !== "E0" && category !== "E4") {
          errorCounts[category] += 1;
          participantErrors[category] += 1;
          taskStats.errorCounts[category] += 1;
        }
      }
      if (record.completed === true) {
        participantCompleted += 1;
        completedRunCount += 1;
        taskStats.completions += 1;
      } else if (record.completed === false) {
        participantIncomplete += 1;
        incompleteRecordedRunCount += 1;
        taskStats.incompleteRuns += 1;
      }

      const assistedEffective = record.assisted === true || record.errorCategories.includes("E8");
      if (assistedEffective) {
        participantAssisted += 1;
        assistedRunCount += 1;
        taskStats.assistedRuns += 1;
      }
      if (record.completed === true && !assistedEffective) {
        participantUnassisted += 1;
        unassistedCompletionCount += 1;
        taskStats.unassistedCompletions += 1;
      }

      if (task.criticalEvidenceRequired) {
        if (record.criticalEvidenceOperations == null) {
          taskStats.missingCriticalCount += 1;
        } else {
          criticalValues.push(record.criticalEvidenceOperations);
          taskStats.criticalValues.push(record.criticalEvidenceOperations);
          if (record.criticalEvidenceOperations > FREEZE_THRESHOLDS.criticalEvidenceMaxOps) {
            participantCriticalOver3 += 1;
            taskStats.criticalOver3Count += 1;
            criticalOver3Runs.push({
              participantCode: participant.code || "（未填写代号）",
              taskId: task.id,
              value: record.criticalEvidenceOperations,
            });
          }
        }
      }

      if (record.layoutIssue != null) {
        layoutCheckedRuns += 1;
        if (record.layoutIssue === true) {
          layoutIssueCount += 1;
          layoutIssueRuns.push({
            participantCode: participant.code || "（未填写代号）",
            taskId: task.id,
          });
        }
      }
    }

    const confirmed =
      participant.validityChecklist.every(Boolean) &&
      participant.signature !== "" &&
      participant.signDate !== "";
    if (confirmed) confirmedParticipantCount += 1;

    perParticipant.push({
      code: participant.code,
      pageVersion: participant.pageVersion,
      browser: participant.browser,
      windowWidth: participant.windowWidth,
      zoom: participant.zoom,
      testDate: participant.testDate,
      validRuns: participantValidRuns,
      completedRuns: participantCompleted,
      unassistedCompletions: participantUnassisted,
      assistedRuns: participantAssisted,
      incompleteRuns: participantIncomplete,
      invalidRuns: participantInvalid,
      unfilled: participantUnfilled,
      unassistedRate: participantValidRuns > 0 ? participantUnassisted / participantValidRuns : null,
      errorCounts: participantErrors,
      criticalOver3Count: participantCriticalOver3,
      ratings: { nextStep: participant.ratings.nextStep, evidenceTrust: participant.ratings.evidenceTrust },
      confirmed,
      signedOff: participant.signature !== "" && participant.signDate !== "",
    });
  }

  for (const taskStats of perTask) {
    taskStats.unassistedRate = taskStats.validRuns > 0 ? taskStats.unassistedCompletions / taskStats.validRuns : null;
  }

  const validParticipants = perParticipant.filter(
    (entry) => entry.code !== "" && entry.validRuns > 0
  );
  const validParticipantCount = validParticipants.length;
  const overallUnassistedRate = validRunCount > 0 ? unassistedCompletionCount / validRunCount : null;

  const ratings = {};
  for (const question of RATING_QUESTIONS) {
    const recorded = validParticipants
      .map((entry) => entry.ratings[question.key])
      .filter((rating) => rating != null);
    ratings[question.key] = {
      recorded: recorded.length,
      average: recorded.length > 0 ? round2(recorded.reduce((sum, r) => sum + r, 0) / recorded.length) : null,
    };
  }

  const criticalOver3Count = criticalOver3Runs.length;

  const tasksWithRuns = perTask.filter((taskStats) => taskStats.validRuns > 0);
  const tasksWithoutRuns = perTask
    .filter((taskStats) => taskStats.validRuns === 0)
    .map((taskStats) => `${taskStats.taskId} ${taskStats.title}`);
  const failingTasks = perTask
    .filter(
      (taskStats) =>
        taskStats.validRuns === 0 ||
        taskStats.unassistedRate < FREEZE_THRESHOLDS.perTaskUnassistedRate
    )
    .map((taskStats) => `${taskStats.taskId} ${taskStats.title}`);
  const worstPerTaskRate =
    tasksWithRuns.length > 0
      ? Math.min(...tasksWithRuns.map((taskStats) => taskStats.unassistedRate))
      : null;

  const gates = {
    validParticipants: {
      label: "有效参与者人数",
      requirement: `≥ ${FREEZE_THRESHOLDS.validParticipants}`,
      actual: validParticipantCount,
      display: String(validParticipantCount),
      passed: validParticipantCount >= FREEZE_THRESHOLDS.validParticipants,
    },
    validRuns: {
      label: "有效任务运行总数",
      requirement: `≥ ${FREEZE_THRESHOLDS.validRuns}（10 人 × 14 项）`,
      actual: validRunCount,
      display: String(validRunCount),
      passed: validRunCount >= FREEZE_THRESHOLDS.validRuns,
    },
    overallUnassistedRate: {
      label: "总体无辅助完成率",
      requirement: `≥ ${Math.round(FREEZE_THRESHOLDS.overallUnassistedRate * 100)}%`,
      actual: overallUnassistedRate,
      display:
        overallUnassistedRate == null
          ? "无法计算"
          : `${formatPercent(overallUnassistedRate)}（${unassistedCompletionCount}/${validRunCount}）`,
      passed: overallUnassistedRate == null ? null : overallUnassistedRate >= FREEZE_THRESHOLDS.overallUnassistedRate,
    },
    perTaskUnassistedRate: {
      label: "单项无辅助完成率",
      requirement: `每项 ≥ ${Math.round(FREEZE_THRESHOLDS.perTaskUnassistedRate * 100)}%`,
      actual: worstPerTaskRate,
      display:
        worstPerTaskRate == null
          ? "无法计算"
          : `最差 ${formatPercent(worstPerTaskRate)}${failingTasks.length > 0 ? `（未达或未测试：${failingTasks.join("、")}）` : ""}`,
      passed:
        validRunCount === 0
          ? null
          : tasksWithoutRuns.length > 0
            ? false
            : worstPerTaskRate >= FREEZE_THRESHOLDS.perTaskUnassistedRate,
      failingTasks,
      tasksWithoutRuns,
    },
    errorConclusion: {
      label: "错误结论计数",
      requirement: "= 0",
      actual: errorCounts.E4,
      display: String(errorCounts.E4),
      passed:
        validRunCount === 0
          ? null
          : errorCounts.E4 === FREEZE_THRESHOLDS.errorConclusion,
    },
    criticalEvidenceOps: {
      label: "关键证据操作数",
      requirement: `每次 ≤ ${FREEZE_THRESHOLDS.criticalEvidenceMaxOps}`,
      actual: criticalOver3Count,
      display: `超过 ${FREEZE_THRESHOLDS.criticalEvidenceMaxOps} 次：${criticalOver3Count} 次（共记录 ${criticalValues.length} 条）`,
      passed:
        validRunCount === 0
          ? null
          : perTask
              .filter((taskStats) => TASK_BY_ID.get(taskStats.taskId).criticalEvidenceRequired)
              .some(
                (taskStats) =>
                  taskStats.validRuns === 0 ||
                  taskStats.missingCriticalCount > 0
              )
            ? false
            : criticalOver3Count === 0,
    },
    layoutKeyboard: {
      label: "布局与键盘",
      requirement: "无横向滚动/重叠/裁切/焦点陷阱/勾选跳顶",
      actual: layoutIssueCount,
      display: `问题 ${layoutIssueCount} 条（已记录 ${layoutCheckedRuns} 条）`,
      passed:
        validRunCount === 0
          ? null
          : layoutCheckedRuns < validRunCount
            ? false
            : layoutIssueCount === 0,
    },
    subjectiveRatings: {
      label: "主观评价",
      requirement: "记录①②平均分，仅用于修订判断",
      actual: null,
      display:
        validParticipantCount === 0
          ? "无法计算"
          : `① ${ratings.nextStep.average == null ? "未记录" : ratings.nextStep.average}（${ratings.nextStep.recorded} 人）　② ${
              ratings.evidenceTrust.average == null ? "未记录" : ratings.evidenceTrust.average
            }（${ratings.evidenceTrust.recorded} 人）`,
      passed:
        validParticipantCount === 0
          ? null
          : ratings.nextStep.recorded === validParticipantCount &&
            ratings.evidenceTrust.recorded === validParticipantCount,
    },
  };
  for (const gate of Object.values(gates)) {
    gate.statusText = gate.passed === true ? "通过" : gate.passed === false ? "未通过" : "无法计算";
  }

  const stopWarnings = [];
  for (const run of e4Runs) {
    stopWarnings.push(
      `错误结论：参与者 ${run.participantCode} 在${taskDisplay(run.taskId)}中出现错误结论——按试用要求立即暂停本轮试用，保留页面现场并转入问题复现。`
    );
  }
  for (const run of criticalOver3Runs) {
    stopWarnings.push(
      `关键证据超过 ${FREEZE_THRESHOLDS.criticalEvidenceMaxOps} 次操作：参与者 ${run.participantCode} ${taskDisplay(run.taskId)}用了 ${run.value} 次操作——该项失败，需修订后复测。`
    );
  }
  for (const run of layoutIssueRuns) {
    stopWarnings.push(
      `布局问题：参与者 ${run.participantCode} ${taskDisplay(run.taskId)}记录出现页面级横向滚动或布局问题——需记录窗口宽度和缩放比例并修订。`
    );
  }

  return {
    ok: true,
    errors: [],
    value: {
      batchCode: value.batchCode,
      pageVersion: value.pageVersion,
      fixtureVersion: value.fixtureVersion,
      startDate: value.startDate,
      endDate: value.endDate,
      recorderCode: value.recorderCode,
      facilitatorCode: value.facilitatorCode,
      participantCount: value.participants.length,
      validParticipantCount,
      recordedRunCount,
      validRunCount,
      invalidRunCount,
      invalidRunDetails,
      unfilledTaskCount,
      completedRunCount,
      incompleteRecordedRunCount,
      assistedRunCount,
      unassistedCompletionCount,
      overallUnassistedRate,
      errorCounts,
      e4Count: errorCounts.E4,
      hasErrorConclusion: e4Runs.length > 0,
      e4Runs,
      criticalEvidence: {
        requiredTaskIds: TASKS.filter((task) => task.criticalEvidenceRequired).map((task) => task.id),
        recordedCount: criticalValues.length,
        over3Count: criticalOver3Count,
        max: criticalValues.length > 0 ? Math.max(...criticalValues) : null,
        median: medianOf(criticalValues),
        over3Runs: criticalOver3Runs,
      },
      layout: {
        checkedRuns: layoutCheckedRuns,
        issueRuns: layoutIssueCount,
        issueRunDetails: layoutIssueRuns,
      },
      ratings,
      perTask,
      perParticipant,
      confirmedParticipantCount,
      gates,
      stopWarnings,
    },
  };
}

/* ------------------------------------------------------------------ */
/* 展示辅助（无 DOM，供界面与导出共用）                                   */
/* ------------------------------------------------------------------ */

/** 比例格式化：null → 「无法计算」，否则保留一位小数百分比。 */
export function formatPercent(rate) {
  if (rate == null) return "无法计算";
  return `${(rate * 100).toFixed(1)}%`;
}

/** CSV 单元格转义：含逗号、引号或换行时加引号并把内部引号翻倍（RFC 4180）。 */
export function escapeCsvCell(value) {
  const text = value == null ? "" : String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function yesNoText(value) {
  if (value === true) return "是";
  if (value === false) return "否";
  return "";
}

function errorText(categories) {
  if (categories.length === 0) return "";
  return categories.map((category) => `${category} ${ERROR_BY_ID.get(category).name}`).join("；");
}

function rateCell(rate, numerator, denominator) {
  return rate == null ? "无法计算" : `${formatPercent(rate)}（${numerator}/${denominator}）`;
}

function criticalCell(record, task) {
  if (record.criticalEvidenceOperations != null) return String(record.criticalEvidenceOperations);
  return task.criticalEvidenceRequired ? "" : "不适用";
}

function mdCell(value) {
  return String(value ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, "<br>");
}

function mdRow(cells) {
  return `| ${cells.map(mdCell).join(" | ")} |`;
}

function csvLine(cells) {
  return cells.map(escapeCsvCell).join(",");
}

function summarizeOrThrow(batch) {
  const result = summarizeBatch(batch);
  if (!result.ok) {
    throw new Error(`批次数据校验未通过，无法导出：${result.errors.join("；")}`);
  }
  return result.value;
}

/* ------------------------------------------------------------------ */
/* 导出生成                                                             */
/* ------------------------------------------------------------------ */

/** 生成完整审阅用 Markdown（逐人原始记录 + 汇总 + 门槛结论）。 */
export function generateMarkdown(batch, options = {}) {
  const summary = options.summary ?? summarizeOrThrow(batch);
  const normalized = normalizeBatch(batch);
  if (!normalized.ok) {
    throw new Error(`批次数据校验未通过，无法导出：${normalized.errors.join("；")}`);
  }
  const exportedAt = options.exportedAt ?? new Date().toISOString();
  const lines = [];

  lines.push("# 入排审核工作台界面试用原始记录与汇总");
  lines.push("");
  lines.push(
    `> 由${RECORDER_TOOL_NAME}（工具版本 ${RECORDER_TOOL_VERSION}）自动生成，导出时间 ${exportedAt}。`
  );
  lines.push("> 本表全部数字派生自逐项原始记录，未填写与「否」分开显示；无有效运行时相关比例显示「无法计算」。");
  lines.push("> 达到临时门槛不等于冻结：必须由用户明确批准默认首屏、中文状态词、个例全景首屏过滤、规则与证据工作台分区、窄屏呈现方式、关键操作路径和临时阈值后，方可宣布通过；未经批准不得进入下一阶段构建。");
  lines.push("");

  const batchData = normalized.value;
  lines.push("## 0. 批次基本信息");
  lines.push("");
  lines.push("| 项目 | 记录 |");
  lines.push("|---|---|");
  lines.push(mdRow(["批次编号", batchData.batchCode]));
  lines.push(mdRow(["开始日期 / 结束日期", `${batchData.startDate} / ${batchData.endDate}`]));
  lines.push(mdRow(["页面版本（须与记录表一致）", batchData.pageVersion]));
  lines.push(mdRow(["合成示例资料版本", batchData.fixtureVersion]));
  lines.push(mdRow(["记录人员代号 / 主持人代号", `${batchData.recorderCode} / ${batchData.facilitatorCode}`]));
  lines.push(mdRow(["参与者数 / 任务记录数", `${summary.participantCount} 人 / ${summary.participantCount * TASKS.length} 条`]));

  const versionMismatch = batchData.participants.filter(
    (participant) => participant.pageVersion !== "" && participant.pageVersion !== batchData.pageVersion
  );
  if (versionMismatch.length > 0) {
    lines.push("");
    lines.push(
      `> 警告：以下参与者的页面版本与本批次不一致，版本变化后不得与本批混算——${versionMismatch
        .map((participant) => `${participant.code || "（未填写代号）"}（${participant.pageVersion || "未填写"}）`)
        .join("、")}。`
    );
  }

  if (summary.stopWarnings.length > 0) {
    lines.push("");
    lines.push("## 停止提示（持续显示，直至记录被明确修正）");
    lines.push("");
    for (const warning of summary.stopWarnings) {
      lines.push(`- **${warning}**`);
    }
  }

  lines.push("");
  lines.push("## 1. 逐人原始记录");
  for (const participant of batchData.participants) {
    lines.push("");
    lines.push(
      `### 参与者 ${participant.code || "（未填写代号）"}（页面版本：${participant.pageVersion || "未填写"}；浏览器：${participant.browser || "未填写"}；窗口宽度：${participant.windowWidth == null ? "未填写" : participant.windowWidth}；缩放：${participant.zoom || "未填写"}；记录人员：${participant.recorderCode || "未填写"}；测试日期：${participant.testDate || "未填写"}）`
    );
    lines.push("");
    lines.push("| 任务 | 用时（秒） | 总操作数 | 关键证据操作数 | 是否完成 | 是否获得提示 | 错误类别 | 参与者原话、错误位置与自行恢复过程 |");
    for (const task of TASKS) {
      const record = participant.taskRecords[task.id];
      lines.push(
        mdRow([
          `${task.id} ${task.title}`,
          record.durationSeconds == null ? "" : record.durationSeconds,
          record.totalOperations == null ? "" : record.totalOperations,
          criticalCell(record, task),
          yesNoText(record.completed),
          yesNoText(record.assisted),
          errorText(record.errorCategories),
          record.notes,
        ])
      );
    }
    const invalidRuns = Object.entries(participant.taskRecords).filter(([, record]) => record.isInvalid);
    for (const [taskId, record] of invalidRuns) {
      lines.push("");
      lines.push(`> 无效运行：${taskId}——${record.invalidReason || "未填写剔除原因"}`);
    }
    const rating = participant.ratings;
    lines.push("");
    lines.push(
      `> 完成评价①「${RATING_QUESTIONS[0].question}」：${rating.nextStep == null ? "未填写" : rating.nextStep}　②「${RATING_QUESTIONS[1].question}」：${rating.evidenceTrust == null ? "未填写" : rating.evidenceTrust}`
    );
    const recordConfirmed =
      participant.validityChecklist.every(Boolean) && participant.signature !== "" && participant.signDate !== "";
    lines.push(
      `> 本次记录是否有效：${recordConfirmed ? "已确认" : "未完成确认"}（签名：${participant.signature || "未填写"}；日期：${participant.signDate || "未填写"}）`
    );
  }

  lines.push("");
  lines.push("## 2. 停止与异常记录");
  lines.push("");
  lines.push("| 发生时间 | 参与者 | 任务 | 说明 |");
  lines.push("|---|---|---|---|");
  const stopRows = [];
  for (const run of summary.invalidRunDetails) {
    stopRows.push([
      batchTimeOf(batchData, run.participantCode, run.taskId),
      run.participantCode,
      run.taskId,
      `无效运行（已剔除，不计入统计）：${run.reason}`,
    ]);
  }
  for (const run of summary.e4Runs) {
    stopRows.push([
      batchTimeOf(batchData, run.participantCode, run.taskId),
      run.participantCode,
      run.taskId,
      `错误结论（E4）：${run.notes || "无补充说明"}`,
    ]);
  }
  for (const run of summary.criticalEvidence.over3Runs) {
    stopRows.push([
      batchTimeOf(batchData, run.participantCode, run.taskId),
      run.participantCode,
      run.taskId,
      `关键证据操作数 ${run.value} 次，超过 ${FREEZE_THRESHOLDS.criticalEvidenceMaxOps} 次`,
    ]);
  }
  for (const run of summary.layout.issueRunDetails) {
    stopRows.push([
      batchTimeOf(batchData, run.participantCode, run.taskId),
      run.participantCode,
      run.taskId,
      "出现页面级横向滚动或布局问题",
    ]);
  }
  if (stopRows.length === 0) {
    lines.push("| — | — | — | 无 |");
  } else {
    for (const row of stopRows) {
      lines.push(mdRow(row));
    }
  }

  lines.push("");
  lines.push("## 3. 参与者汇总（逐人）");
  lines.push("");
  lines.push("| 参与者代号 | 页面版本 | 窗口宽度 | 缩放 | 完成项数 | 有效运行数 | 无辅助完成项数 | 无辅助完成率 | 获得辅助(E8)项数 | E1 | E2 | E3 | E4 | 完成评价① | 信任评价② | 备注 |");
  lines.push("|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|");
  for (const entry of summary.perParticipant) {
    const remarks = [];
    remarks.push(entry.confirmed ? "已确认并签名" : "未完成有效性确认");
    if (entry.invalidRuns > 0) remarks.push(`无效运行 ${entry.invalidRuns}`);
    if (entry.criticalOver3Count > 0) remarks.push(`关键证据超 3 次 ${entry.criticalOver3Count}`);
    lines.push(
      mdRow([
        entry.code || "（未填写代号）",
        entry.pageVersion,
        entry.windowWidth == null ? "" : entry.windowWidth,
        entry.zoom,
        entry.completedRuns,
        entry.validRuns,
        entry.unassistedCompletions,
        rateCell(entry.unassistedRate, entry.unassistedCompletions, entry.validRuns),
        entry.assistedRuns,
        entry.errorCounts.E1,
        entry.errorCounts.E2,
        entry.errorCounts.E3,
        entry.errorCounts.E4,
        entry.ratings.nextStep == null ? "" : entry.ratings.nextStep,
        entry.ratings.evidenceTrust == null ? "" : entry.ratings.evidenceTrust,
        remarks.join("；"),
      ])
    );
  }
  lines.push(
    mdRow([
      "合计",
      "",
      "",
      "",
      summary.completedRunCount,
      summary.validRunCount,
      summary.unassistedCompletionCount,
      rateCell(summary.overallUnassistedRate, summary.unassistedCompletionCount, summary.validRunCount),
      summary.assistedRunCount,
      summary.errorCounts.E1,
      summary.errorCounts.E2,
      summary.errorCounts.E3,
      summary.errorCounts.E4,
      summary.ratings.nextStep.average == null ? "" : summary.ratings.nextStep.average,
      summary.ratings.evidenceTrust.average == null ? "" : summary.ratings.evidenceTrust.average,
      "",
    ])
  );

  lines.push("");
  lines.push("## 4. 逐任务汇总（14 项）");
  lines.push("");
  lines.push("| 任务 | 有效运行数 | 无辅助完成项数 | 无辅助完成率 | E1 | E2 | E3 | E4 | E5 | E6 | E7 | 关键证据操作数（逐条列出） | 备注/修订记录 |");
  lines.push("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|");
  for (const taskStats of summary.perTask) {
    const remarks = [];
    if (taskStats.invalidRuns > 0) remarks.push(`无效运行 ${taskStats.invalidRuns}`);
    if (taskStats.unfilled > 0) remarks.push(`未填写 ${taskStats.unfilled}`);
    if (taskStats.missingCriticalCount > 0) remarks.push(`关键证据未记录 ${taskStats.missingCriticalCount}`);
    lines.push(
      mdRow([
        `${taskStats.taskId} ${taskStats.title}`,
        taskStats.validRuns,
        taskStats.unassistedCompletions,
        rateCell(taskStats.unassistedRate, taskStats.unassistedCompletions, taskStats.validRuns),
        taskStats.errorCounts.E1,
        taskStats.errorCounts.E2,
        taskStats.errorCounts.E3,
        taskStats.errorCounts.E4,
        taskStats.errorCounts.E5,
        taskStats.errorCounts.E6,
        taskStats.errorCounts.E7,
        taskStats.criticalValues.length > 0 ? taskStats.criticalValues.join("、") : "",
        remarks.join("；"),
      ])
    );
  }
  lines.push(
    mdRow([
      "合计",
      summary.validRunCount,
      summary.unassistedCompletionCount,
      rateCell(summary.overallUnassistedRate, summary.unassistedCompletionCount, summary.validRunCount),
      summary.errorCounts.E1,
      summary.errorCounts.E2,
      summary.errorCounts.E3,
      summary.errorCounts.E4,
      summary.errorCounts.E5,
      summary.errorCounts.E6,
      summary.errorCounts.E7,
      "",
      "",
    ])
  );

  lines.push("");
  lines.push("## 5. 意见归类（逐人逐条）");
  lines.push("");
  lines.push("| 编号 | 参与者 | 任务 | 原话或行为 | 记录人员备注 |");
  lines.push("|---|---|---|---|---|");
  let remarkIndex = 0;
  let remarkFound = false;
  for (const participant of batchData.participants) {
    for (const task of TASKS) {
      const record = participant.taskRecords[task.id];
      if (record.notes === "" && record.facilitatorNotes === "") continue;
      remarkFound = true;
      remarkIndex += 1;
      lines.push(
        mdRow([
          remarkIndex,
          participant.code || "（未填写代号）",
          `${task.id} ${task.title}`,
          record.notes,
          record.facilitatorNotes,
        ])
      );
    }
  }
  if (!remarkFound) {
    lines.push("| — | — | — | 无 | 无 |");
  }

  lines.push("");
  lines.push("## 6. 正式门槛结论");
  lines.push("");
  lines.push("| 门槛 | 要求 | 实测 | 通过 |");
  lines.push("|---|---|---|---|");
  for (const gate of Object.values(summary.gates)) {
    lines.push(mdRow([gate.label, gate.requirement, gate.display, gate.statusText]));
  }
  lines.push("");
  lines.push("> 达到临时门槛不等于方案冻结。只有用户在下方明确批准后才可冻结；未经批准不得进入下一阶段构建。");

  lines.push("");
  lines.push("## 7. 主观评价汇总");
  lines.push("");
  lines.push(
    `- ①「${RATING_QUESTIONS[0].question}」平均分：${summary.ratings.nextStep.average == null ? "未记录" : summary.ratings.nextStep.average}（已记录 ${summary.ratings.nextStep.recorded} 人）。`
  );
  lines.push(
    `- ②「${RATING_QUESTIONS[1].question}」平均分：${summary.ratings.evidenceTrust.average == null ? "未记录" : summary.ratings.evidenceTrust.average}（已记录 ${summary.ratings.evidenceTrust.recorded} 人）。`
  );
  lines.push("> 主观评价平均分不替代客观门槛，只用于决定文案和信息密度是否修订。");
  lines.push("");
  lines.push("## 8. 用户明确批准（冻结门）");
  lines.push("");
  lines.push("- [ ] 默认首屏（今日工作或项目看板）已获用户明确批准。");
  lines.push("- [ ] 中文状态词、个例全景首屏过滤、规则与证据工作台分区、窄屏呈现方式已获用户明确批准。");
  lines.push("- [ ] 用户已批准关键操作路径与临时阈值（无辅助完成率 ≥90%、错误结论为 0、关键证据 ≤3 次操作）。");
  lines.push("- [ ] 已提交：任务逐项记录、样本量、无辅助完成率、错误结论计数、关键证据操作数、视口与缩放检查、错误修订记录、未解决风险、默认首屏建议。");
  lines.push("");
  lines.push("用户批准结论（由用户本人填写）：");
  lines.push("");
  lines.push("____________________________________________");
  lines.push("");
  lines.push("用户签名或代号：____________　日期：____________");
  lines.push("");
  lines.push(
    `> 本表由${RECORDER_TOOL_NAME}自动生成；正式界面试用未获用户批准前不得宣布通过，也不得开始下一阶段构建。`
  );

  return lines.join("\n");
}

/** 生成逐行原始记录 CSV（每名参与者 × 14 项任务各一行；正确转义逗号、引号与换行）。 */
export function generateCsv(batch) {
  const normalized = normalizeBatch(batch);
  if (!normalized.ok) {
    throw new Error(`批次数据校验未通过，无法导出：${normalized.errors.join("；")}`);
  }
  const batchData = normalized.value;
  const rows = [];
  rows.push(
    csvLine([
      "批次编号",
      "参与者代号",
      "任务编号",
      "任务名称",
      "用时（秒）",
      "总操作数",
      "关键证据操作数",
      "是否完成",
      "是否获得提示",
      "错误类别",
      "参与者原话、错误位置与自行恢复过程",
      "主持人提示或代操作",
      "是否无效运行",
      "剔除原因",
      "是否出现页面级横向滚动或布局问题",
      "最近修改时间",
    ])
  );
  for (const participant of batchData.participants) {
    for (const task of TASKS) {
      const record = participant.taskRecords[task.id];
      rows.push(
        csvLine([
          batchData.batchCode,
          participant.code,
          task.id,
          task.title,
          record.durationSeconds == null ? "" : record.durationSeconds,
          record.totalOperations == null ? "" : record.totalOperations,
          criticalCell(record, task),
          yesNoText(record.completed),
          yesNoText(record.assisted),
          errorText(record.errorCategories),
          record.notes,
          record.facilitatorNotes,
          record.isInvalid ? "是" : "",
          record.invalidReason,
          yesNoText(record.layoutIssue),
          record.updatedAt ?? "",
        ])
      );
    }
  }
  return `${rows.join("\r\n")}\r\n`;
}

/** 生成逐任务统计 CSV（用于表格统计；与 Markdown、本机备份同源派生）。 */
export function generateSummaryCsv(batch, summary = null) {
  const computed = summary ?? summarizeOrThrow(batch);
  const rows = [];
  rows.push(
    csvLine([
      "任务编号",
      "任务名称",
      "有效运行数",
      "无辅助完成项数",
      "无辅助完成率",
      "完成项数",
      "未完成项数",
      "获得辅助(E8)项数",
      "无效运行数",
      "未填写项数",
      "E1",
      "E2",
      "E3",
      "E4",
      "E5",
      "E6",
      "E7",
      "E8",
      "关键证据操作数（逐条列出）",
      "关键证据超过3次",
    ])
  );
  for (const taskStats of computed.perTask) {
    rows.push(
      csvLine([
        taskStats.taskId,
        taskStats.title,
        taskStats.validRuns,
        taskStats.unassistedCompletions,
        taskStats.unassistedRate == null ? "无法计算" : formatPercent(taskStats.unassistedRate),
        taskStats.completions,
        taskStats.incompleteRuns,
        taskStats.assistedRuns,
        taskStats.invalidRuns,
        taskStats.unfilled,
        taskStats.errorCounts.E1,
        taskStats.errorCounts.E2,
        taskStats.errorCounts.E3,
        taskStats.errorCounts.E4,
        taskStats.errorCounts.E5,
        taskStats.errorCounts.E6,
        taskStats.errorCounts.E7,
        taskStats.errorCounts.E8,
        taskStats.criticalValues.join("、"),
        taskStats.criticalOver3Count,
      ])
    );
  }
  rows.push(
    csvLine([
      "合计",
      "",
      computed.validRunCount,
      computed.unassistedCompletionCount,
      computed.overallUnassistedRate == null ? "无法计算" : formatPercent(computed.overallUnassistedRate),
      computed.completedRunCount,
      computed.incompleteRecordedRunCount,
      computed.assistedRunCount,
      computed.invalidRunCount,
      computed.unfilledTaskCount,
      computed.errorCounts.E1,
      computed.errorCounts.E2,
      computed.errorCounts.E3,
      computed.errorCounts.E4,
      computed.errorCounts.E5,
      computed.errorCounts.E6,
      computed.errorCounts.E7,
      computed.errorCounts.E8,
      computed.criticalEvidence.recordedCount > 0
        ? `${computed.criticalEvidence.recordedCount} 条（最多 ${computed.criticalEvidence.max}）`
        : "",
      computed.criticalEvidence.over3Count,
    ])
  );
  return `${rows.join("\r\n")}\r\n`;
}

/** 生成本机备份文本（JSON，含备份标识、版本与导出时间；内容即规范化后的批次）。 */
export function generateBackupText(batch, exportedAt = new Date().toISOString()) {
  const normalized = normalizeBatch(batch);
  if (!normalized.ok) {
    throw new Error(`批次数据校验未通过，无法导出备份：${normalized.errors.join("；")}`);
  }
  const envelope = {
    schema: BACKUP_SCHEMA,
    version: BACKUP_VERSION,
    toolVersion: RECORDER_TOOL_VERSION,
    exportedAt,
    batch: normalized.value,
  };
  return JSON.stringify(envelope, null, 2);
}

function batchTimeOf(batchData, participantCode, taskId) {
  const participant = batchData.participants.find((entry) => entry.code === participantCode);
  if (!participant) return "";
  const record = participant.taskRecords[taskId];
  return record == null ? "" : record.updatedAt ?? participant.testDate;
}
