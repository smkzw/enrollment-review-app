/**
 * 入排审核界面试用记录工作台——界面控制器（worker_02 交付）。
 *
 * 边界：
 * - 只服务记录人员工作面：批次信息、参与者切换、14 项任务状态、当前任务记录、
 *   异常记录、自动汇总、导出/备份/恢复；不含任何参与者应用导航。
 * - 所有统计与门槛结论一律由 uat-recorder-core.js 从逐项原始记录派生，
 *   界面不提供手工覆盖总体完成率、错误结论计数或门槛状态的入口。
 * - 记录自动保存在本机浏览器内（界面文案只说「本机记录/本机备份」，
 *   不向记录人员展示存储键、JSON、schema 等内部名称）。
 * - 不修改参与者原型页面，不改变参与者界面版本；记录工具版本独立显示。
 */

import {
  RECORDER_TOOL_NAME,
  RECORDER_TOOL_VERSION,
  RECORDER_STORAGE_KEY,
  FREEZE_THRESHOLDS,
  RATING_QUESTIONS,
  VALIDITY_CHECKLIST_ITEMS,
  TASKS,
  ERROR_CATEGORIES,
  createEmptyBatch,
  createEmptyParticipant,
  normalizeBatch,
  summarizeBatch,
  formatPercent,
  parseBackupText,
  generateMarkdown,
  generateCsv,
  generateSummaryCsv,
  generateBackupText,
} from "./uat-recorder-core.js";

const $ = (id) => document.getElementById(id);

/* ------------------------------------------------------------------ */
/* 状态                                                                */
/* ------------------------------------------------------------------ */

const state = {
  /** 规范化后的批次（唯一数据源）。 */
  batch: null,
  /** 从当前页面服务自动读取的参与者界面版本（可能为空）。 */
  pageVersionFromPage: "",
  /** 当前参与者下标。 */
  participantIndex: 0,
  /** 当前记录任务编号。 */
  taskId: TASKS[0].id,
  /** 计时器：running + 分段起点秒数 + 分段起始时刻。 */
  timer: { running: false, base: 0, segStartMs: 0, intervalId: null },
  /** 最近一次整体校验错误（用于禁用导出并提示）。 */
  validationErrors: [],
};

/* ------------------------------------------------------------------ */
/* 小工具                                                              */
/* ------------------------------------------------------------------ */

function pad2(n) {
  return String(n).padStart(2, "0");
}

function nowIso() {
  return new Date().toISOString();
}

function nowClock() {
  const d = new Date();
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

function nowLocalMinute() {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function localDateNow() {
  const d = new Date();
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function currentParticipant() {
  return state.batch.participants[state.participantIndex] ?? null;
}

function currentRecord() {
  const participant = currentParticipant();
  return participant ? participant.taskRecords[state.taskId] : null;
}

function taskOf(taskId) {
  return TASKS.find((task) => task.id === taskId);
}

function taskDisplay(taskId) {
  const index = TASKS.findIndex((task) => task.id === taskId);
  return index < 0 ? "未识别任务" : `第 ${String(index + 1).padStart(2, "0")} 项`;
}

/* ------------------------------------------------------------------ */
/* 保存与校验                                                          */
/* ------------------------------------------------------------------ */

function setSaveStatus(text) {
  const node = $("rec-save-status");
  if (node) node.textContent = text;
}

function persist(message) {
  if (!state.batch) return;
  state.batch.updatedAt = nowIso();
  try {
    localStorage.setItem(RECORDER_STORAGE_KEY, JSON.stringify(state.batch));
    setSaveStatus(`${message ?? "已保存到本机"}（${nowClock()}）`);
  } catch {
    setSaveStatus("保存失败：本机浏览器拒绝写入，请检查浏览器设置或先导出本机备份");
  }
}

/** 重算整体校验与汇总，刷新所有派生面板（不重建当前表单，避免打断输入）。 */
function refreshDerived() {
  const normalized = normalizeBatch(state.batch);
  state.validationErrors = normalized.ok ? [] : normalized.errors;
  renderStopBanner();
  renderExceptions();
  renderSummary();
  renderTaskBadges();
  renderParticipantStats();
  renderVersionWarnings();
  renderExportGuards();
}

/** 任一字段变化后：写时间戳、自动保存、刷新派生面板。 */
function touch() {
  persist();
  refreshDerived();
}

/* ------------------------------------------------------------------ */
/* 表单构件工厂                                                        */
/* ------------------------------------------------------------------ */

function fieldLabel(text) {
  const label = el("label", null, text);
  return label;
}

/** 单行文本/数字输入。onInput 收到解析后的值（number/string，空为 null）。 */
function inputField({ label, id, type, value, step, min, placeholder, note, onInput }) {
  const wrap = el("div", "rec-field");
  const lab = fieldLabel(label);
  const input = el("input");
  input.id = id;
  input.type = type;
  if (step != null) input.step = String(step);
  if (min != null) input.min = String(min);
  if (placeholder != null) input.placeholder = placeholder;
  if (value != null && value !== "") input.value = String(value);
  input.addEventListener("input", () => {
    onInput(input);
  });
  lab.htmlFor = id;
  wrap.appendChild(lab);
  wrap.appendChild(input);
  if (note) wrap.appendChild(el("p", "rec-field-note", note));
  return wrap;
}

function textInput(opts) {
  return inputField({ type: "text", ...opts });
}

function numberInput(opts) {
  return inputField({ type: "number", ...opts });
}

function dateInput(opts) {
  return inputField({ type: "date", ...opts });
}

function textareaField({ label, id, value, rows, placeholder, note, onInput }) {
  const wrap = el("div", "rec-field");
  const lab = fieldLabel(label);
  const input = el("textarea");
  input.id = id;
  input.rows = rows ?? 3;
  if (placeholder != null) input.placeholder = placeholder;
  input.value = value ?? "";
  input.addEventListener("input", () => onInput(input.value));
  lab.htmlFor = id;
  wrap.appendChild(lab);
  wrap.appendChild(input);
  if (note) wrap.appendChild(el("p", "rec-field-note", note));
  return wrap;
}

/** 三态单选组（是/否/未填写）。value: true/false/null。 */
function radioGroup({ label, name, value, options, note, onChange }) {
  const group = el("fieldset", "rec-choice-group");
  const legend = el("legend", null, label);
  group.appendChild(legend);
  const list = el("div", "rec-radio-list");
  for (const opt of options) {
    const item = el("label", "rec-check-item");
    const radio = el("input");
    radio.type = "radio";
    radio.name = name;
    radio.value = opt.value;
    radio.checked = String(value ?? "") === String(opt.value);
    radio.addEventListener("change", () => {
      if (radio.checked) onChange(opt.parsed);
    });
    item.appendChild(radio);
    item.appendChild(el("span", null, opt.text));
    list.appendChild(item);
  }
  group.appendChild(list);
  if (note) group.appendChild(el("p", "rec-field-note", note));
  return group;
}

const YES_NO_NULL = [
  { value: "true", parsed: true, text: "是" },
  { value: "false", parsed: false, text: "否" },
  { value: "", parsed: null, text: "未填写" },
];

/** 复选框组（fieldset/legend 分组）。items: {id,text,desc,checked,onChange} */
function checkGroup({ label, items, note }) {
  const group = el("fieldset", "rec-choice-group");
  group.appendChild(el("legend", null, label));
  const list = el("div", "rec-check-list");
  for (const item of items) {
    const check = el("label", `rec-check-item${item.danger ? " rec-check-danger" : ""}`);
    const box = el("input");
    box.type = "checkbox";
    box.checked = Boolean(item.checked);
    box.addEventListener("change", () => item.onChange(box.checked));
    check.appendChild(box);
    const textWrap = el("span");
    textWrap.appendChild(el("span", null, item.text));
    if (item.desc) {
      textWrap.appendChild(document.createTextNode(" "));
      textWrap.appendChild(el("span", "rec-check-desc", item.desc));
    }
    check.appendChild(textWrap);
    list.appendChild(check);
  }
  group.appendChild(list);
  if (note) group.appendChild(el("p", "rec-field-note", note));
  return group;
}

function button({ label, className, onClick, disabled }) {
  const btn = el("button", className ? `rec-btn ${className}` : "rec-btn", label);
  if (disabled) btn.disabled = true;
  btn.addEventListener("click", onClick);
  return btn;
}

/* ------------------------------------------------------------------ */
/* 中文确认对话框（导入预览、删除、新批次共用）                          */
/* ------------------------------------------------------------------ */

function openDialog({ title, body, confirmLabel, onConfirm, confirmDisabled, danger }) {
  const dialog = $("rec-dialog");
  const form = $("rec-dialog-form");
  const titleNode = $("rec-dialog-title");
  const bodyNode = $("rec-dialog-body");
  const cancelBtn = $("rec-dialog-cancel");
  const confirmBtn = $("rec-dialog-confirm");

  titleNode.textContent = title;
  bodyNode.replaceChildren(body);
  confirmBtn.textContent = confirmLabel ?? "确认";
  confirmBtn.disabled = Boolean(confirmDisabled);
  confirmBtn.className = `rec-btn ${danger ? "rec-btn-danger" : "rec-btn-primary"}`;

  const onSubmit = (event) => {
    event.preventDefault();
    dialog.close();
    form.removeEventListener("submit", onSubmit);
    cancelBtn.removeEventListener("click", onCancel);
    if (!confirmDisabled && onConfirm) onConfirm();
  };
  const onCancel = () => {
    dialog.close();
    form.removeEventListener("submit", onSubmit);
    cancelBtn.removeEventListener("click", onCancel);
  };
  form.addEventListener("submit", onSubmit);
  cancelBtn.addEventListener("click", onCancel);
  dialog.showModal();
}

/* ------------------------------------------------------------------ */
/* 页头与停止提示                                                      */
/* ------------------------------------------------------------------ */


function renderStopBanner() {
  const banner = $("rec-stop-banner");
  const list = $("rec-stop-banner-list");
  const summary = summarizeBatch(state.batch);
  const warnings = summary.ok ? summary.value.stopWarnings : [];
  list.replaceChildren();
  for (const warning of warnings) {
    list.appendChild(el("li", null, warning));
  }
  banner.hidden = warnings.length === 0;
}

/* ------------------------------------------------------------------ */
/* 批次信息                                                            */
/* ------------------------------------------------------------------ */

function renderBatchSection() {
  const section = el("section", "rec-section");
  section.appendChild(el("h2", "rec-section-title", "批次信息"));

  const grid = el("div", "rec-form-grid");
  const batch = state.batch;

  grid.appendChild(
    textInput({
      label: "批次编号",
      id: "rec-batch-code",
      value: batch.batchCode,
      placeholder: "例如 2026-08-13-A",
      onInput: (input) => {
        batch.batchCode = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    dateInput({
      label: "开始日期",
      id: "rec-batch-start",
      value: batch.startDate,
      onInput: (input) => {
        batch.startDate = input.value;
        touch();
      },
    })
  );
  grid.appendChild(
    dateInput({
      label: "结束日期",
      id: "rec-batch-end",
      value: batch.endDate,
      onInput: (input) => {
        batch.endDate = input.value;
        touch();
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "参与者界面版本",
      id: "rec-batch-page-version",
      value: batch.pageVersion,
      note: "已自动读取当前界面版本；版本变化后请新建批次，不得与本批混算。",
      onInput: (input) => {
        batch.pageVersion = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "合成示例资料版本",
      id: "rec-batch-fixture",
      value: batch.fixtureVersion,
      placeholder: "例如 示例资料第1版",
      onInput: (input) => {
        batch.fixtureVersion = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "记录人员代号",
      id: "rec-batch-recorder",
      value: batch.recorderCode,
      onInput: (input) => {
        batch.recorderCode = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "主持人代号",
      id: "rec-batch-facilitator",
      value: batch.facilitatorCode,
      onInput: (input) => {
        batch.facilitatorCode = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    textareaField({
      label: "批次备注",
      id: "rec-batch-notes",
      value: batch.notes,
      rows: 2,
      note: "例如合成示例数据包名称、环境说明；不参与统计。",
      onInput: (value) => {
        batch.notes = value;
        touch();
      },
    })
  );

  section.appendChild(grid);

  const actions = el("div", "rec-btn-row");
  actions.appendChild(
    button({
      label: "开始新批次",
      className: "rec-btn-ghost",
      onClick: () => {
        const body = el("div");
        body.appendChild(
          el(
            "p",
            null,
            "开始新批次会替换本机上的当前批次记录，且不可恢复。修订后重测应使用新批次，不得与旧批次混算。"
          )
        );
        body.appendChild(el("p", "rec-field-warn", "请先确认已通过「导出本机备份文件」保存当前批次。"));
        openDialog({
          title: "开始新批次",
          body,
          confirmLabel: "已备份，开始新批次",
          danger: true,
          onConfirm: () => {
            pauseTimer();
            state.batch = createEmptyBatch({
              pageVersion: state.pageVersionFromPage || "",
              fixtureVersion: "示例资料第1版",
              startDate: localDateNow(),
            });
            state.participantIndex = 0;
            state.taskId = TASKS[0].id;
            renderAll();
            persist("新批次已建立并保存到本机");
          },
        });
      },
    })
  );
  section.appendChild(actions);
  return section;
}

/* ------------------------------------------------------------------ */
/* 参与者面板（列表 + 信息 + 完成评价）                                 */
/* ------------------------------------------------------------------ */

function participantRecordStats(participant) {
  let recorded = 0;
  let completed = 0;
  let unassisted = 0;
  for (const task of TASKS) {
    const record = participant.taskRecords[task.id];
    const isRecorded =
      record.completed !== null ||
      record.assisted !== null ||
      record.isInvalid === true ||
      record.errorCategories.length > 0 ||
      record.durationSeconds != null ||
      record.totalOperations != null ||
      record.criticalEvidenceOperations != null ||
      record.layoutIssue != null ||
      record.notes !== "" ||
      record.facilitatorNotes !== "";
    if (!isRecorded) continue;
    recorded += 1;
    if (!record.isInvalid) {
      const assisted =
        record.assisted === true || record.errorCategories.includes("E8");
      if (record.completed === true) completed += 1;
      if (record.completed === true && !assisted) unassisted += 1;
    }
  }
  return { recorded, completed, unassisted };
}

function renderParticipantList(container) {
  const section = el("section", "rec-section");
  section.appendChild(el("h2", "rec-section-title", "参与者"));

  const list = el("ul", "rec-participant-list");
  if (state.batch.participants.length === 0) {
    section.appendChild(el("p", "rec-participant-empty", "还没有参与者，请先「增加参与者」。"));
  }
  state.batch.participants.forEach((participant, index) => {
    const stats = participantRecordStats(participant);
    const card = el("button", "rec-participant-card");
    card.type = "button";
    card.setAttribute("aria-current", String(index === state.participantIndex));
    card.addEventListener("click", () => {
      pauseTimer();
      state.participantIndex = index;
      renderAll();
    });
    const top = el("span", "rec-participant-card-top");
    top.appendChild(
      el("span", "rec-participant-card-code", participant.code === "" ? "（未填写代号）" : participant.code)
    );
    const stat = el("span", "rec-participant-card-stat");
    stat.appendChild(el("b", null, `${stats.recorded}/14`));
    stat.appendChild(document.createTextNode(" 已记录"));
    if (participant.validityChecklist.every(Boolean) && participant.signature !== "" && participant.signDate !== "") {
      stat.appendChild(document.createTextNode(" · 已确认"));
    }
    top.appendChild(stat);
    card.appendChild(top);
    const item = el("li", "rec-participant-item");
    item.appendChild(card);
    list.appendChild(item);
  });
  section.appendChild(list);

  const actions = el("div", "rec-btn-row");
  actions.appendChild(
    button({
      label: "增加参与者",
      className: "rec-btn-primary",
      onClick: () => {
        pauseTimer();
        const next = state.batch.participants.length + 1;
        const participant = createEmptyParticipant({
          code: `P${pad2(next)}`,
          pageVersion: state.batch.pageVersion || state.pageVersionFromPage || "",
          recorderCode: state.batch.recorderCode || "",
          testDate: localDateNow(),
        });
        state.batch.participants.push(participant);
        state.participantIndex = state.batch.participants.length - 1;
        state.taskId = TASKS[0].id;
        renderAll();
        persist("新参与者已增加并保存到本机");
      },
    })
  );
  actions.appendChild(
    button({
      label: "删除当前参与者",
      className: "rec-btn-danger",
      disabled: state.batch.participants.length === 0,
      onClick: () => {
        const participant = currentParticipant();
        if (!participant) return;
        const body = el("div");
        body.appendChild(
          el(
            "p",
            null,
            `删除参与者「${participant.code === "" ? "未填写代号" : participant.code}」后，其全部任务原始记录将从本机移除且不可恢复（此前导出的本机备份中仍保留）。`
          )
        );
        openDialog({
          title: "删除参与者",
          body,
          confirmLabel: "删除",
          danger: true,
          onConfirm: () => {
            pauseTimer();
            state.batch.participants.splice(state.participantIndex, 1);
            if (state.participantIndex >= state.batch.participants.length) {
              state.participantIndex = Math.max(0, state.batch.participants.length - 1);
            }
            state.taskId = TASKS[0].id;
            renderAll();
            persist("已删除参与者并保存到本机");
          },
        });
      },
    })
  );
  section.appendChild(actions);
  container.appendChild(section);
}

function renderParticipantInfo(container) {
  const participant = currentParticipant();
  if (!participant) return;

  const section = el("section", "rec-section");
  section.appendChild(el("h2", "rec-section-title", "参与者信息"));
  const versionMismatch =
    participant.pageVersion !== "" &&
    state.batch.pageVersion !== "" &&
    participant.pageVersion !== state.batch.pageVersion;
  if (versionMismatch) {
    section.appendChild(
      el(
        "p",
        "rec-field-warn",
        "该参与者页面版本与本批次不一致；导出时会提示，版本变化后不得与本批混算。"
      )
    );
  }

  const grid = el("div", "rec-form-grid");
  grid.appendChild(
    textInput({
      label: "参与者代号",
      id: "rec-participant-code",
      value: participant.code,
      onInput: (input) => {
        participant.code = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "页面版本",
      id: "rec-participant-page-version",
      value: participant.pageVersion,
      onInput: (input) => {
        participant.pageVersion = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "浏览器",
      id: "rec-participant-browser",
      value: participant.browser,
      placeholder: "例如 Chrome 130",
      onInput: (input) => {
        participant.browser = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    numberInput({
      label: "窗口宽度（像素）",
      id: "rec-participant-width",
      value: participant.windowWidth,
      min: 1,
      step: 1,
      onInput: (input) => {
        const parsed = input.value === "" ? null : Math.trunc(Number(input.value));
        if (parsed == null || (Number.isFinite(parsed) && parsed >= 1)) {
          participant.windowWidth = parsed;
          touch();
        } else if (input.value !== "") {
          setSaveStatus("窗口宽度必须是 1 或更大的整数，未保存该项修改");
        }
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "浏览器缩放",
      id: "rec-participant-zoom",
      value: participant.zoom,
      placeholder: "例如 100%、150%、200%",
      onInput: (input) => {
        participant.zoom = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    textInput({
      label: "记录人员代号",
      id: "rec-participant-recorder",
      value: participant.recorderCode,
      onInput: (input) => {
        participant.recorderCode = input.value.trim();
        touch();
      },
    })
  );
  grid.appendChild(
    dateInput({
      label: "测试日期",
      id: "rec-participant-date",
      value: participant.testDate,
      onInput: (input) => {
        participant.testDate = input.value;
        touch();
      },
    })
  );
  section.appendChild(grid);

  /* 完成后评价（每名参与者两条） */
  const ratingTitle = el("h3", "rec-section-title", "完成后评价");
  ratingTitle.style.marginTop = "var(--space-4)";
  section.appendChild(ratingTitle);

  const ratingGrid = el("div", "rec-form-grid");
  for (const question of RATING_QUESTIONS) {
    const wrap = el("div", "rec-field");
    const label = fieldLabel(`${question.question}（1 至 5 分）`);
    const select = el("select");
    select.id = `rec-rating-${question.key}`;
    const options = ["", "1", "2", "3", "4", "5"];
    const labels = { "": "未填写", 1: "1 分", 2: "2 分", 3: "3 分", 4: "4 分", 5: "5 分" };
    for (const value of options) {
      const option = el("option", null, labels[value]);
      option.value = value;
      if (String(participant.ratings[question.key] ?? "") === value) option.selected = true;
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      participant.ratings[question.key] = select.value === "" ? null : Number(select.value);
      touch();
    });
    label.htmlFor = select.id;
    wrap.appendChild(label);
    wrap.appendChild(select);
    wrap.appendChild(
      textareaField({
        label: "原因或原话",
        id: `rec-rating-note-${question.key}`,
        value: participant.ratings[`${question.key}Note`],
        rows: 2,
        onInput: (value) => {
          participant.ratings[`${question.key}Note`] = value;
          touch();
        },
      })
    );
    ratingGrid.appendChild(wrap);
  }
  section.appendChild(ratingGrid);

  /* 本次记录是否有效 */
  section.appendChild(
    checkGroup({
      label: "本次记录是否有效（全部勾选、签名与日期齐全才算已确认）",
      items: VALIDITY_CHECKLIST_ITEMS.map((text, index) => ({
        text,
        checked: participant.validityChecklist[index] === true,
        onChange: (checked) => {
          participant.validityChecklist[index] = checked;
          if (
            participant.validityChecklist.every(Boolean) &&
            participant.signature !== "" &&
            participant.signDate !== "" &&
            participant.finishedAt === ""
          ) {
            participant.finishedAt = nowLocalMinute();
          }
          touch();
        },
      })),
    })
  );

  const confirmGrid = el("div", "rec-form-grid");
  confirmGrid.appendChild(
    textInput({
      label: "记录人员签名或代号",
      id: "rec-participant-signature",
      value: participant.signature,
      onInput: (input) => {
        participant.signature = input.value.trim();
        touch();
      },
    })
  );
  confirmGrid.appendChild(
    dateInput({
      label: "签名日期",
      id: "rec-participant-sign-date",
      value: participant.signDate,
      onInput: (input) => {
        participant.signDate = input.value;
        touch();
      },
    })
  );
  section.appendChild(confirmGrid);
  container.appendChild(section);
}

/* ------------------------------------------------------------------ */
/* 14 项任务状态与当前任务记录                                          */
/* ------------------------------------------------------------------ */

function taskBadgeInfo(record) {
  if (record.errorCategories.includes("E4")) {
    return { text: "错误结论", kind: "danger" };
  }
  if (record.isInvalid) {
    return { text: "无效运行", kind: "warn" };
  }
  const isRecorded =
    record.completed !== null ||
    record.assisted !== null ||
    record.errorCategories.length > 0 ||
    record.durationSeconds != null ||
    record.totalOperations != null ||
    record.criticalEvidenceOperations != null ||
    record.layoutIssue != null ||
    record.notes !== "" ||
    record.facilitatorNotes !== "";
  if (!isRecorded) {
    return { text: "未记录", kind: "none" };
  }
  const assisted = record.assisted === true || record.errorCategories.includes("E8");
  if (record.completed === true) {
    return assisted
      ? { text: "完成·有辅助", kind: "warn" }
      : { text: "完成", kind: "ok" };
  }
  if (record.completed === false) {
    return { text: "未完成", kind: "warn" };
  }
  return { text: "已记录", kind: "none" };
}


function renderTaskGrid(container) {
  const section = el("section", "rec-section");
  section.appendChild(el("h2", "rec-section-title", "14 项任务状态"));
  section.appendChild(
    el(
      "p",
      "rec-section-hint",
      "点击任务卡片进行逐项记录；状态由该任务原始记录自动得出。"
    )
  );
  const list = el("ul", "rec-task-grid");
  for (const task of TASKS) {
    const record = currentParticipant()
      ? currentParticipant().taskRecords[task.id]
      : null;
    const badge = record ? taskBadgeInfo(record) : { text: "未记录", kind: "none" };
    const card = el("button", "rec-task-card");
    card.type = "button";
    card.setAttribute("aria-current", String(task.id === state.taskId));
    card.dataset.taskId = task.id;
    card.addEventListener("click", () => {
      pauseTimer();
      state.taskId = task.id;
      renderRecordForm();
    });
    const top = el("span", "rec-task-card-top");
    top.appendChild(el("span", "rec-task-card-id", taskDisplay(task.id)));
    const badgeNode = el(
      "span",
      `rec-task-badge${badge.kind === "none" ? "" : ` rec-task-badge-${badge.kind}`}`,
      badge.text
    );
    top.appendChild(badgeNode);
    card.appendChild(top);
    card.appendChild(el("span", "rec-task-card-title", task.title));
    const item = el("li");
    item.appendChild(card);
    list.appendChild(item);
  }
  section.appendChild(list);
  container.appendChild(section);
}


function renderRecordForm() {
  const container = $("rec-record-form");
  container.replaceChildren();
  const participant = currentParticipant();
  const record = currentRecord();
  const task = taskOf(state.taskId);
  if (!participant || !record || !task) {
    container.appendChild(el("p", "rec-participant-empty", "请先增加参与者。"));
    return;
  }

  const header = el("div", "rec-task-header");
  header.appendChild(el("h3", "rec-task-header-name", `${task.id} ${task.title}`));
  header.appendChild(
    el("p", "rec-task-header-meta", `固定起始页：${task.startPage}`)
  );
  container.appendChild(header);
  container.appendChild(el("p", "rec-task-goal", `任务目标：${task.goal}`));


  const grid = el("div", "rec-form-grid");

  grid.appendChild(
    numberInput({
      label: "用时（秒）",
      id: "rec-f-duration",
      value: record.durationSeconds,
      min: 0,
      note: "计时自动填写，也可以手工修正；负数或非数字不会被保存。",
      onInput: (input) => {
        const value = input.value === "" ? null : Number(input.value);
        if (Number.isFinite(value) && value >= 0) {
          record.durationSeconds = value;
          if (state.timer.running) {
            state.timer.base = value;
            state.timer.segStartMs = Date.now();
          }
          touch();
          updateTimerReadout();
        } else if (input.value !== "") {
          setSaveStatus("用时必须是 0 或更大的数字，未保存该项修改");
        }
      },
    })
  );
  grid.appendChild(
    numberInput({
      label: "总操作数",
      id: "rec-f-operations",
      value: record.totalOperations,
      min: 0,
      step: 1,
      onInput: (input) => {
        const value = input.value === "" ? null : Math.trunc(Number(input.value));
        if (Number.isFinite(value) && value >= 0) {
          record.totalOperations = value;
          touch();
        } else if (input.value !== "") {
          setSaveStatus("总操作数必须是 0 或更大的整数，未保存该项修改");
        }
      },
    })
  );
  grid.appendChild(
    numberInput({
      label: "关键证据操作数",
      id: "rec-f-critical",
      value: record.criticalEvidenceOperations,
      min: 0,
      step: 1,
      note: task.criticalEvidenceRequired
        ? "本任务需逐次记录；超过 3 次将触发停止提示。"
        : "本任务不涉及关键证据时可不填；导出中显示为「不适用」。",
      onInput: (input) => {
        const value = input.value === "" ? null : Math.trunc(Number(input.value));
        if (Number.isFinite(value) && value >= 0) {
          record.criticalEvidenceOperations = value;
          touch();
        } else if (input.value !== "") {
          setSaveStatus("关键证据操作数必须是 0 或更大的整数，未保存该项修改");
        }
      },
    })
  );
  grid.appendChild(
    radioGroup({
      label: "是否完成",
      name: "rec-radio-completed",
      value: record.completed,
      options: YES_NO_NULL,
      note: "完成 = 达到该任务全部成功证据，且无错误结论。",
      onChange: (value) => {
        record.completed = value;
        if (value === true && record.endTime === "") {
          record.endTime = nowLocalMinute();
        }
        touch();
      },
    })
  );
  grid.appendChild(
    radioGroup({
      label: "是否获得提示",
      name: "rec-radio-assisted",
      value: record.assisted,
      options: YES_NO_NULL,
      note: "主持人以路径、按钮、状态或证据答案形式提示，或替参与者操作，均计入「获得辅助」，不计入无辅助完成。",
      onChange: (value) => {
        record.assisted = value;
        touch();
      },
    })
  );
  grid.appendChild(
    radioGroup({
      label: "是否出现页面级横向滚动或布局问题",
      name: "rec-radio-layout",
      value: record.layoutIssue,
      options: YES_NO_NULL,
      note: "选择「是」会触发停止提示；请同时在原话中记录视口宽度、缩放和复现步骤。",
      onChange: (value) => {
        record.layoutIssue = value;
        touch();
      },
    })
  );

  const errorGroup = checkGroup({
    label: "本项出现的情况（可多选）",
    items: ERROR_CATEGORIES.map((category) => ({
      text: `${category.name}（记录编码 ${category.id}）`,
      desc: category.definition,
      danger: category.isErrorConclusion,
      checked: record.errorCategories.includes(category.id),
      onChange: (checked) => {
        const next = new Set(record.errorCategories);
        if (category.id === "E0") {
          if (checked) {
            next.clear();
            next.add("E0");
          } else {
            next.delete("E0");
          }
        } else {
          if (checked) {
            next.delete("E0");
            next.add(category.id);
          } else {
            next.delete(category.id);
          }
        }
        record.errorCategories = ERROR_CATEGORIES.filter((entry) => next.has(entry.id)).map(
          (entry) => entry.id
        );
        touch();
        syncErrorCheckboxes();
      },
    })),
    note: "“无错误”与其他情况不能同时选择；选择“错误结论”会立即在页面顶部显示暂停试用提示。括号内编码仅用于导出后追溯。",
  });
  errorGroup.classList.add("rec-form-grid-wide");
  errorGroup.querySelectorAll("label.rec-check-item").forEach((label, index) => {
    label.classList.add("rec-error-item");
    label.dataset.errorId = ERROR_CATEGORIES[index].id;
  });
  grid.appendChild(errorGroup);
  grid.appendChild(
    textareaField({
      label: "参与者原话、错误位置与自行恢复过程",
      id: "rec-f-notes",
      value: record.notes,
      rows: 4,
      onInput: (value) => {
        record.notes = value;
        touch();
      },
    })
  );
  grid.appendChild(
    textareaField({
      label: "主持人提示或代操作",
      id: "rec-f-facilitator-notes",
      value: record.facilitatorNotes,
      rows: 4,
      note: "主持人给出提示或代替操作时必填；与「是否获得提示」保持一致。",
      onInput: (value) => {
        record.facilitatorNotes = value;
        touch();
      },
    })
  );

  /* 无效运行 */
  const invalidGroup = el("fieldset", "rec-choice-group rec-form-grid-wide");
  invalidGroup.appendChild(el("legend", null, "本次记录是否无效（页面或试用环境故障）"));
  const invalidList = el("div", "rec-check-list");
  const invalidItem = el("label", "rec-check-item");
  const invalidBox = el("input");
  invalidBox.type = "checkbox";
  invalidBox.checked = record.isInvalid === true;
  invalidBox.addEventListener("change", () => {
    record.isInvalid = invalidBox.checked;
    touch();
  });
  invalidItem.appendChild(invalidBox);
  invalidItem.appendChild(
    el(
      "span",
      null,
      "本次记录无效，剔除出统计（原始记录与剔除原因仍保留，不会删除）"
    )
  );
  invalidList.appendChild(invalidItem);
  invalidGroup.appendChild(invalidList);
  const reasonField = textareaField({
    label: "剔除原因",
    id: "rec-f-invalid-reason",
    value: record.invalidReason,
    rows: 2,
    note: "标记无效记录时必填，例如“示例资料版本错误”或“页面意外关闭”。",
    onInput: (value) => {
      record.invalidReason = value;
      touch();
    },
  });
  invalidGroup.appendChild(reasonField);
  grid.appendChild(invalidGroup);

  container.appendChild(grid);
}

/** 把错误类别复选框的勾选状态与当前记录模型同步（E0 与其余类别互斥）。 */
function syncErrorCheckboxes() {
  const record = currentRecord();
  if (!record) return;
  document.querySelectorAll("#rec-record-form .rec-error-item").forEach((label) => {
    const box = label.querySelector("input");
    if (box) box.checked = record.errorCategories.includes(label.dataset.errorId);
  });
}

function renderTimerControls() {
  const container = $("rec-timer-controls");
  if (container) container.replaceChildren();
  const wrap = el("div", "rec-timer-panel");
  const readout = el("div", "rec-timer-readout");
  readout.appendChild(el("span", "rec-timer-label", "本次任务用时（秒）"));
  const valueNode = el("span", "rec-timer-value", String(currentRecord()?.durationSeconds ?? 0));
  valueNode.dataset.running = String(state.timer.running);
  readout.appendChild(valueNode);
  wrap.appendChild(readout);
  wrap.appendChild(
    button({
      label: state.timer.running ? "暂停计时" : "开始计时",
      className: state.timer.running ? "" : "rec-btn-primary",
      onClick: () => {
        if (state.timer.running) pauseTimer();
        else startTimer();
        renderTimerControls();
      },
    })
  );
  wrap.appendChild(
    button({
      label: "用时清零",
      className: "rec-btn-ghost",
      onClick: () => {
        pauseTimer();
        const record = currentRecord();
        if (record) {
          record.durationSeconds = 0;
          touch();
        }
        renderTimerControls();
      },
    })
  );
  wrap.appendChild(
    el("p", "rec-field-note", "计时中可直接修改表单内「用时（秒）」进行手工修正，计时会从修正后的数值继续累加。")
  );
  container.appendChild(wrap);
}

/* ------------------------------------------------------------------ */
/* 计时器                                                              */
/* ------------------------------------------------------------------ */

function startTimer() {
  const record = currentRecord();
  if (!record) return;
  state.timer.base = record.durationSeconds ?? 0;
  state.timer.segStartMs = Date.now();
  state.timer.running = true;
  if (record.startTime === "") {
    record.startTime = nowLocalMinute();
  }
  state.timer.intervalId = setInterval(timerTick, 1000);
  touch();
  updateTimerReadout();
}

function timerTick() {
  const record = currentRecord();
  if (!record) return;
  const elapsed = Math.floor((Date.now() - state.timer.segStartMs) / 1000);
  const next = state.timer.base + elapsed;
  if (record.durationSeconds !== next) {
    record.durationSeconds = next;
    record.updatedAt = nowIso();
    try {
      localStorage.setItem(RECORDER_STORAGE_KEY, JSON.stringify(state.batch));
    } catch {
      /* 存储失败已在下次交互提示 */
    }
  }
  updateTimerReadout();
}

function pauseTimer() {
  if (!state.timer.running) return;
  state.timer.running = false;
  if (state.timer.intervalId != null) {
    clearInterval(state.timer.intervalId);
    state.timer.intervalId = null;
  }
  const record = currentRecord();
  if (record) {
    const elapsed = Math.floor((Date.now() - state.timer.segStartMs) / 1000);
    record.durationSeconds = state.timer.base + elapsed;
    if (record.endTime === "") {
      record.endTime = nowLocalMinute();
    }
  }
  updateTimerReadout();
  persist("计时已暂停并保存到本机");
}

function updateTimerReadout() {
  const nodes = document.querySelectorAll(".rec-timer-value");
  for (const node of nodes) {
    node.textContent = String(currentRecord()?.durationSeconds ?? 0);
    node.dataset.running = String(state.timer.running);
  }
  const durationInput = $("rec-f-duration");
  if (
    durationInput &&
    !(state.timer.running && document.activeElement === durationInput)
  ) {
    durationInput.value = String(currentRecord()?.durationSeconds ?? 0);
  }
}

/* ------------------------------------------------------------------ */
/* 异常记录（全部派生）                                                */
/* ------------------------------------------------------------------ */

function renderExceptions() {
  const container = $("rec-exceptions");
  if (!container) return;
  container.replaceChildren();
  const summary = summarizeBatch(state.batch);
  const rows = [];
  if (summary.ok) {
    const value = summary.value;
    for (const run of value.invalidRunDetails) {
      rows.push({
        text: `无效记录（已剔除，不计入统计）：参与者「${run.participantCode}」${taskDisplay(run.taskId)}——${run.reason}`,
        danger: false,
      });
    }
    for (const run of value.e4Runs) {
      rows.push({
        text: `错误结论：参与者「${run.participantCode}」${taskDisplay(run.taskId)}${run.invalidRun ? "（该记录另被标记为无效，但错误结论历史仍保留）" : ""}——${run.notes || "无补充说明"}`,
        danger: true,
      });
    }
    for (const run of value.criticalEvidence.over3Runs) {
      rows.push({
        text: `关键证据操作数 ${run.value} 次（超过 ${FREEZE_THRESHOLDS.criticalEvidenceMaxOps} 次）：参与者「${run.participantCode}」${taskDisplay(run.taskId)}`,
        danger: false,
      });
    }
    for (const run of value.layout.issueRunDetails) {
      rows.push({
        text: `布局问题：参与者「${run.participantCode}」${taskDisplay(run.taskId)}记录出现页面级横向滚动或布局问题`,
        danger: false,
      });
    }
  } else {
    rows.push({ text: `记录数据存在校验问题：${summary.errors.join("；")}`, danger: true });
  }

  const section = el("section", "rec-section");
  section.appendChild(el("h2", "rec-section-title", "异常与停止记录"));
  section.appendChild(
    el("p", "rec-section-hint", "以下内容由逐项原始记录自动汇总，不能手工修改；修正对应任务记录后会自动消失。")
  );
  if (rows.length === 0) {
    section.appendChild(el("p", "rec-participant-empty", "暂无异常记录。"));
  } else {
    const list = el("ul", "rec-exception-list");
    for (const row of rows) {
      list.appendChild(
        el("li", `rec-exception-item${row.danger ? " rec-exception-danger" : ""}`, row.text)
      );
    }
    section.appendChild(list);
  }
  container.appendChild(section);
}

/* ------------------------------------------------------------------ */
/* 自动汇总                                                            */
/* ------------------------------------------------------------------ */

function renderSummary() {
  const container = $("rec-summary");
  if (!container) return;
  container.replaceChildren();
  const section = el("section", "rec-section");
  section.appendChild(el("h2", "rec-section-title", "自动汇总"));
  section.appendChild(
    el(
      "p",
      "rec-section-hint",
      "所有数字由逐项原始记录自动计算，不能手工修改；分母为 0 时显示「无法计算」，绝不显示通过。"
    )
  );

  const summary = summarizeBatch(state.batch);
  if (!summary.ok) {
    const errorBox = el("div", "rec-error-note");
    errorBox.appendChild(el("p", null, "记录数据校验未通过，汇总暂时无法计算："));
    const list = el("ul");
    for (const message of summary.errors) {
      list.appendChild(el("li", null, message));
    }
    errorBox.appendChild(list);
    section.appendChild(errorBox);
    container.appendChild(section);
    return;
  }
  const value = summary.value;

  const errorsLine = el("p", "rec-section-hint");
  const errorParts = [];
  for (const category of ERROR_CATEGORIES) {
    if (category.id === "E0") continue;
    const count = value.errorCounts[category.id] ?? 0;
    errorParts.push(`${category.name}：${count}`);
  }
  errorsLine.textContent = `错误类别计数：${errorParts.join("；")}`;
  section.appendChild(errorsLine);

  const table = el("table", "rec-table");
  const thead = el("thead");
  const headRow = el("tr");
  for (const label of ["正式门槛", "要求", "实测", "结论"]) {
    headRow.appendChild(el("th", null, label));
  }
  thead.appendChild(headRow);
  table.appendChild(thead);
  const tbody = el("tbody");
  for (const gate of Object.values(value.gates)) {
    const row = el("tr");
    const cellLabel = el("td", null, gate.label);
    cellLabel.dataset.label = "正式门槛";
    row.appendChild(cellLabel);
    const cellReq = el("td", null, gate.requirement);
    cellReq.dataset.label = "要求";
    row.appendChild(cellReq);
    const cellActual = el("td", null, gate.display);
    cellActual.dataset.label = "实测";
    row.appendChild(cellActual);
    const cellStatus = el("td", `rec-gate-${gate.passed === true ? "pass" : gate.passed === false ? "fail" : "unknown"}`, gate.statusText);
    cellStatus.dataset.label = "结论";
    row.appendChild(cellStatus);
    tbody.appendChild(row);
  }
  table.appendChild(tbody);
  const wrap = el("div", "rec-table-wrap");
  wrap.appendChild(table);
  section.appendChild(wrap);

  const taskTitle = el("h3", "rec-section-title", "逐任务汇总");
  taskTitle.style.marginTop = "var(--space-4)";
  section.appendChild(taskTitle);
  const taskTable = el("table", "rec-table");
  const taskHead = el("thead");
  const taskHeadRow = el("tr");
  for (const label of ["任务", "有效记录", "无辅助完成", "无辅助完成率", "错误结论", "关键证据超3次", "未填写"]) {
    taskHeadRow.appendChild(el("th", null, label));
  }
  taskHead.appendChild(taskHeadRow);
  taskTable.appendChild(taskHead);
  const taskBody = el("tbody");
  for (const taskStats of value.perTask) {
    const row = el("tr");
    const cells = [
      `${taskDisplay(taskStats.taskId)} ${taskStats.title}`,
      String(taskStats.validRuns),
      String(taskStats.unassistedCompletions),
      formatPercent(taskStats.unassistedRate),
      String(taskStats.errorCounts.E4),
      String(taskStats.criticalOver3Count),
      String(taskStats.unfilled),
    ];
    const labels = ["任务", "有效记录", "无辅助完成", "无辅助完成率", "错误结论", "关键证据超3次", "未填写"];
    cells.forEach((text, index) => {
      const td = el("td", index === 0 ? "" : "rec-table-num-center", text);
      td.dataset.label = labels[index];
      row.appendChild(td);
    });
    taskBody.appendChild(row);
  }
  taskTable.appendChild(taskBody);
  section.appendChild(taskTable);

  const ratingText = `主观评价：①「${RATING_QUESTIONS[0].question}」${value.ratings.nextStep.average == null ? "未记录" : `平均 ${value.ratings.nextStep.average} 分（已记录 ${value.ratings.nextStep.recorded} 人）`}；②「${RATING_QUESTIONS[1].question}」${value.ratings.evidenceTrust.average == null ? "未记录" : `平均 ${value.ratings.evidenceTrust.average} 分（已记录 ${value.ratings.evidenceTrust.recorded} 人）`}。主观评价不替代客观门槛。`;
  section.appendChild(el("p", "rec-section-hint", ratingText));

  const freezeNote = el("p", "rec-section-hint");
  freezeNote.textContent =
    "达到临时门槛不等于冻结：必须由用户明确批准核心信息架构、术语、关键路径与临时阈值后，方可宣布通过；未经批准不得进入下一阶段构建。";
  section.appendChild(freezeNote);

  container.appendChild(section);
}

/* ------------------------------------------------------------------ */
/* 导出、备份与恢复                                                    */
/* ------------------------------------------------------------------ */

function safeFilePart(text) {
  const cleaned = String(text || "").replace(/[\\/:*?"<>|\s]+/g, "_");
  return cleaned === "" ? "未编号" : cleaned;
}

function fileStamp() {
  const d = new Date();
  return `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}-${pad2(d.getHours())}${pad2(d.getMinutes())}`;
}

function downloadText(filename, text, mime) {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setSaveStatus(`已导出「${filename}」`);
}

function tryExport(kind) {
  const result = normalizeBatch(state.batch);
  if (!result.ok) {
    const body = el("div");
    body.appendChild(el("p", null, "当前记录存在校验问题，无法导出："));
    const list = el("ul");
    for (const message of result.errors) {
      list.appendChild(el("li", null, message));
    }
    body.appendChild(list);
    openDialog({
      title: "无法导出",
      body,
      confirmLabel: "知道了",
      onConfirm: () => {},
    });
    return;
  }
  const stamp = fileStamp();
  const part = safeFilePart(state.batch.batchCode);
  try {
    if (kind === "markdown") {
      downloadText(
        `界面试用记录-${part}-${stamp}.md`,
        generateMarkdown(state.batch),
        "text/markdown;charset=utf-8"
      );
    } else if (kind === "csv") {
      downloadText(
        `界面试用原始记录-${part}-${stamp}.csv`,
        generateCsv(state.batch),
        "text/csv;charset=utf-8"
      );
    } else if (kind === "summary-csv") {
      downloadText(
        `界面试用逐任务统计-${part}-${stamp}.csv`,
        generateSummaryCsv(state.batch),
        "text/csv;charset=utf-8"
      );
    } else if (kind === "backup") {
      downloadText(
        `本机备份-${part}-${stamp}.json`,
        generateBackupText(state.batch),
        "application/json;charset=utf-8"
      );
    }
  } catch (error) {
    const body = el("div");
    body.appendChild(el("p", null, `导出失败：${error instanceof Error ? error.message : String(error)}`));
    openDialog({ title: "导出失败", body, confirmLabel: "知道了", onConfirm: () => {} });
  }
}

function renderExportSection() {
  const section = el("section", "rec-section");
  section.appendChild(el("h2", "rec-section-title", "导出、备份与恢复"));

  const guard = el("div", "rec-export-guard");
  section.appendChild(guard);

  const grid = el("div", "rec-form-grid");
  grid.appendChild(
    el(
      "p",
      "rec-section-hint",
      "Markdown 用于完整审阅，两份 CSV 用于表格统计，本机备份文件用于保存全部原始记录并在需要时恢复。三种导出内容均来自同一份逐项原始记录。"
    )
  );
  section.appendChild(grid);

  const actions = el("div", "rec-btn-row");
  actions.appendChild(
    button({
      label: "导出审阅用 Markdown 文件",
      onClick: () => tryExport("markdown"),
      disabled: state.validationErrors.length > 0,
    })
  );
  actions.appendChild(
    button({
      label: "导出逐行原始记录 CSV",
      onClick: () => tryExport("csv"),
      disabled: state.validationErrors.length > 0,
    })
  );
  actions.appendChild(
    button({
      label: "导出逐任务统计 CSV",
      onClick: () => tryExport("summary-csv"),
      disabled: state.validationErrors.length > 0,
    })
  );
  actions.appendChild(
    button({
      label: "导出本机备份文件",
      className: "rec-btn-primary",
      onClick: () => tryExport("backup"),
      disabled: state.validationErrors.length > 0,
    })
  );
  section.appendChild(actions);

  const importWrap = el("div", "rec-field");
  importWrap.appendChild(el("p", "rec-section-hint", "从本机备份文件恢复：先预览批次、页面版本、参与者数和任务记录数，确认后才替换当前批次。"));
  const importLabel = el("label", "rec-btn", "导入本机备份文件（先预览再确认）");
  const importInput = el("input");
  importInput.type = "file";
  importInput.accept = ".json,application/json";
  importInput.style.display = "none";
  importInput.addEventListener("change", async () => {
    const file = importInput.files && importInput.files[0];
    importInput.value = "";
    if (!file) return;
    let text;
    try {
      text = await file.text();
    } catch {
      openDialog({
        title: "无法读取文件",
        body: el("p", null, "无法读取所选文件，请重新选择本机备份文件。"),
        confirmLabel: "知道了",
        onConfirm: () => {},
      });
      return;
    }
    const parsed = parseBackupText(text);
    if (!parsed.ok) {
      const body = el("div");
      body.appendChild(el("p", null, "该文件不能用作本机备份，原因："));
      const list = el("ul");
      for (const message of parsed.errors) {
        list.appendChild(el("li", null, message));
      }
      body.appendChild(list);
      openDialog({
        title: "导入预览：文件校验未通过",
        body,
        confirmLabel: "知道了",
        confirmDisabled: true,
        onConfirm: () => {},
      });
      return;
    }
    const meta = parsed.meta;
    const preview = el("table", "rec-preview-table");
    const rows = [
      ["批次编号", meta.batchCode === "" ? "（未填写）" : meta.batchCode],
      ["页面版本", meta.pageVersion === "" ? "（未填写）" : meta.pageVersion],
      ["参与者数", `${meta.participantCount} 人`],
      ["任务记录数", `${meta.taskRecordCount} 条`],
      ["合成示例资料版本", meta.fixtureVersion || "（未填写）"],
    ];
    for (const [label, text] of rows) {
      const row = el("tr");
      const th = el("th", null, label);
      const td = el("td", null, text);
      row.appendChild(th);
      row.appendChild(td);
      preview.appendChild(row);
    }
    const body = el("div");
    body.appendChild(el("p", null, "将导入以下本机备份："));
    body.appendChild(preview);
    body.appendChild(
      el(
        "p",
        "rec-field-warn",
        "确认后将替换本机上的当前批次记录，且不可恢复；建议先导出当前批次的本机备份文件。"
      )
    );
    openDialog({
      title: "导入本机备份（预览）",
      body,
      confirmLabel: "确认替换当前批次",
      danger: true,
      onConfirm: () => {
        pauseTimer();
        state.batch = parsed.value;
        state.participantIndex = 0;
        state.taskId = TASKS[0].id;
        renderAll();
        persist("已导入本机备份并替换当前批次");
      },
    });
  });
  importLabel.appendChild(importInput);
  importWrap.appendChild(importLabel);
  section.appendChild(importWrap);

  return section;
}

function renderExportGuards() {
  const guard = document.querySelector(".rec-export-guard");
  if (!guard) return;
  guard.replaceChildren();
  if (state.validationErrors.length > 0) {
    const box = el("div", "rec-error-note");
    box.appendChild(el("p", null, "记录数据存在校验问题，导出与备份已暂时停用，请先修正："));
    const list = el("ul");
    for (const message of state.validationErrors) {
      list.appendChild(el("li", null, message));
    }
    box.appendChild(list);
    guard.appendChild(box);
  }
}

/* ------------------------------------------------------------------ */
/* 派生面板局部刷新                                                    */
/* ------------------------------------------------------------------ */

function renderTaskBadges() {
  const cards = document.querySelectorAll(".rec-task-card");
  for (const card of cards) {
    const taskId = card.dataset.taskId;
    const participant = currentParticipant();
    const badge = participant
      ? taskBadgeInfo(participant.taskRecords[taskId])
      : { text: "未记录", kind: "none" };
    let badgeNode = card.querySelector(".rec-task-badge");
    if (!badgeNode) continue;
    badgeNode.textContent = badge.text;
    badgeNode.className = `rec-task-badge${badge.kind === "none" ? "" : ` rec-task-badge-${badge.kind}`}`;
  }
}

function renderParticipantStats() {
  const cards = document.querySelectorAll(".rec-participant-card");
  state.batch.participants.forEach((participant, index) => {
    const card = cards[index];
    if (!card) return;
    const codeNode = card.querySelector(".rec-participant-card-code");
    if (codeNode) {
      codeNode.textContent = participant.code === "" ? "（未填写代号）" : participant.code;
    }
    const statNode = card.querySelector(".rec-participant-card-stat");
    if (statNode) {
      const stats = participantRecordStats(participant);
      statNode.replaceChildren();
      statNode.appendChild(el("b", null, `${stats.recorded}/14`));
      statNode.appendChild(document.createTextNode(" 已记录"));
      if (
        participant.validityChecklist.every(Boolean) &&
        participant.signature !== "" &&
        participant.signDate !== ""
      ) {
        statNode.appendChild(document.createTextNode(" · 已确认"));
      }
    }
  });
}

function renderVersionWarnings() {
  const participant = currentParticipant();
  if (!participant) return;
  const mismatch =
    participant.pageVersion !== "" &&
    state.batch.pageVersion !== "" &&
    participant.pageVersion !== state.batch.pageVersion;
  const existing = document.getElementById("rec-version-warn");
  if (mismatch) {
    if (!existing) {
      const node = el(
        "p",
        "rec-field-warn",
        "该参与者页面版本与本批次不一致；导出时会提示，版本变化后不得与本批混算。"
      );
      node.id = "rec-version-warn";
      const grid = $("rec-participant-info");
      if (grid) grid.insertBefore(node, grid.firstChild);
    }
  } else if (existing) {
    existing.remove();
  }
}

/* ------------------------------------------------------------------ */
/* 整体渲染                                                            */
/* ------------------------------------------------------------------ */

function renderAll() {
  const app = $("rec-app");
  app.replaceChildren();

  refreshHeaderMeta();

  /* 批次信息（全宽） */
  app.appendChild(renderBatchSection());

  /* 记录工作面：左参与者，右任务与记录 */
  const work = el("div", "rec-work-grid");
  const left = el("div", "rec-work-left");
  renderParticipantList(left);
  const participantInfo = el("div");
  participantInfo.id = "rec-participant-info";
  renderParticipantInfo(participantInfo);
  left.appendChild(participantInfo);

  const right = el("div", "rec-work-right");
  const taskGrid = el("div");
  renderTaskGrid(taskGrid);
  right.appendChild(taskGrid);

  const recordSection = el("section", "rec-section");
  recordSection.appendChild(el("h2", "rec-section-title", "当前任务记录"));
  const timerControls = el("div");
  timerControls.id = "rec-timer-controls";
  recordSection.appendChild(timerControls);
  const recordForm = el("div");
  recordForm.id = "rec-record-form";
  recordSection.appendChild(recordForm);
  right.appendChild(recordSection);

  work.appendChild(left);
  work.appendChild(right);
  app.appendChild(work);

  const exceptions = el("div");
  exceptions.id = "rec-exceptions";
  app.appendChild(exceptions);

  const summary = el("div");
  summary.id = "rec-summary";
  app.appendChild(summary);

  app.appendChild(renderExportSection());

  renderTimerControls();
  renderRecordForm();
  refreshDerived();
  setSaveStatus("记录已从本机恢复");
}

function refreshHeaderMeta() {
  $("rec-tool-version").textContent = RECORDER_TOOL_VERSION;
  $("rec-page-version").textContent =
    state.pageVersionFromPage || "未读取到（请通过界面试用入口打开本页）";
}

/* ------------------------------------------------------------------ */
/* 启动                                                                */
/* ------------------------------------------------------------------ */

function loadStoredBatch() {
  let stored = null;
  try {
    const raw = localStorage.getItem(RECORDER_STORAGE_KEY);
    if (raw != null && raw !== "") {
      stored = JSON.parse(raw);
    }
  } catch {
    stored = null;
  }
  if (stored == null) {
    state.batch = createEmptyBatch({
      pageVersion: state.pageVersionFromPage || "",
      startDate: localDateNow(),
    });
    state.participantIndex = 0;
    state.taskId = TASKS[0].id;
    setSaveStatus("未找到本机记录，已建立空白批次");
    return;
  }
  const normalized = normalizeBatch(stored);
  if (normalized.ok) {
    state.batch = normalized.value;
    state.participantIndex = Math.min(state.participantIndex, Math.max(0, state.batch.participants.length - 1));
    state.taskId = TASKS[0].id;
  } else {
    state.batch = createEmptyBatch({
      pageVersion: state.pageVersionFromPage || "",
      startDate: localDateNow(),
    });
    setSaveStatus("本机记录无法读取，已建立空白批次（请检查或联系管理员）");
  }
}

async function loadPageVersion() {
  try {
    const response = await fetch("./uat-status.json", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();
    const version = typeof data.pageVersion === "string" ? data.pageVersion.trim() : "";
    if (version !== "") {
      state.pageVersionFromPage = version;
      if (state.batch.pageVersion === "") {
        state.batch.pageVersion = version;
        persist("已自动读取当前界面版本并保存到本机");
      }
      refreshHeaderMeta();
    }
  } catch {
    /* 未通过界面试用入口打开时保持「未读取到」提示 */
  }
}

function boot() {
  loadStoredBatch();
  renderAll();
  loadPageVersion().then(() => {
    if (state.batch.pageVersion === "" && state.pageVersionFromPage !== "") {
      state.batch.pageVersion = state.pageVersionFromPage;
      persist("已自动读取当前界面版本并保存到本机");
    }
    refreshHeaderMeta();
  });
  window.addEventListener("beforeunload", () => {
    if (state.timer.running) pauseTimer();
  });
}

boot();
