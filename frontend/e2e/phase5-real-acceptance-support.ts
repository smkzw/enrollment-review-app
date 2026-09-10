/**
 * Phase 5.8 真实隔离项目浏览器验收编排支持（worker_03 骨架）。
 *
 * 边界：
 * - 仅在显式提供隔离数据集根目录时启用；缺省跳过，不以 fixture 路由冒充真实运行。
 * - 执行者（executor）不得替代独立测试者（independent_tester）产出 browser_tester 证据。
 * - 真实 OCR/模型步骤必须显式启用；未启用时配置失败，不能生成可误读为验收通过的观察。
 * - 观察记录对齐 ledger EvidenceItem（evidence_class=browser_tester），不给出入排结论。
 */

import { createHash } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
  writeFileSync,
  appendFileSync,
} from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { expect, type Page, type TestInfo } from "@playwright/test";

/** 显式隔离数据集环境变量；未设置或为空时整套真实验收必须 skip。 */
export const PHASE5_ISOLATED_DATASET_ENV = "PHASE5_ISOLATED_DATASET_ROOT";

export const PHASE5_BASE_URL_ENV = "PHASE5_REAL_ACCEPTANCE_BASE_URL";
export const PHASE5_DATA_DIR_ENV = "PHASE5_REAL_ACCEPTANCE_DATA_DIR";
export const PHASE5_ROLE_ENV = "PHASE5_REAL_ACCEPTANCE_ROLE";
export const PHASE5_CASES_FILE_ENV = "PHASE5_REAL_ACCEPTANCE_CASES_FILE";
export const PHASE5_OBSERVATIONS_DIR_ENV = "PHASE5_BROWSER_OBSERVATIONS_DIR";
export const PHASE5_ALLOW_LIVE_MODEL_ENV = "PHASE5_REAL_ACCEPTANCE_ALLOW_LIVE_MODEL";
export const PHASE5_FRESH_MARKER_ENV = "PHASE5_REAL_ACCEPTANCE_FRESH_MARKER";

export const OBSERVATION_SCHEMA_VERSION = "phase5.browser_observation.v1" as const;

export type AcceptanceRole = "executor" | "independent_tester";

export type ProjectLabel = "D001-II" | "MG-K10-SAR-III";

export type StudyPhase = "phase_ii" | "phase_iii";

export type ObservationDisposition =
  | "pass"
  | "fail"
  | "blocked"
  | "not_run"
  | "observed_only"
  | "advisory";

/** 与 tools/phase5_acceptance/ledger.schema.json EvidenceItem 对齐的浏览器观察。 */
export type BrowserObservation = {
  schema_version: typeof OBSERVATION_SCHEMA_VERSION;
  evidence_class: "browser_tester";
  role: AcceptanceRole;
  case_id: string;
  project_label: ProjectLabel;
  step_id: AcceptanceStepId;
  criterion_ids: readonly string[];
  source_locator: string;
  artifact: string;
  observed_result: string;
  verifier: string;
  timestamp: string;
  disposition: ObservationDisposition;
  notes?: string;
  project_id?: string | null;
  subject_id?: string | null;
  review_episode_id?: string | null;
  database_fingerprint?: string | null;
};

export type AcceptanceStepId =
  | "gate.fixture_routes"
  | "gate.fresh_identity"
  | "flow.project_create"
  | "flow.study_phase_select"
  | "flow.subject_upload"
  | "flow.ocr_processing"
  | "flow.metadata_risk_review"
  | "flow.build_activate"
  | "flow.real_normalizer"
  | "flow.patient_profile"
  | "flow.source_locator"
  | "flow.history_replay";

export type CaseDescriptor = {
  case_id: string;
  project_label: ProjectLabel;
  study_phase: StudyPhase;
  protocol_file: string;
  subject_code: string;
  subject_files: string[];
  expected_protocol_code: string;
  expected_official_version: string;
  expected_version_date: string;
  expected_project_name_contains: string;
  /** 可选：预置审核节点进入路径；真实创建后由观察回填。 */
  preferred_stage_label?: string;
};

export type RealAcceptanceConfig = {
  isolatedDatasetRoot: string;
  baseUrl: string;
  dataDir: string;
  role: AcceptanceRole;
  allowLiveModel: boolean;
  casesFile: string;
  observationsDir: string;
  freshMarker: string;
  cases: CaseDescriptor[];
  databaseFingerprint: string;
};

export type ConfigResolution =
  | { status: "disabled"; reason: string }
  | { status: "misconfigured"; reason: string }
  | { status: "ready"; config: RealAcceptanceConfig };

function objectValue(value: unknown, label: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} 不是可读取的对象。`);
  }
  return value as Record<string, unknown>;
}

function arrayValue(value: unknown, label: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${label} 不是可读取的清单。`);
  return value;
}

function stringValue(value: unknown, label: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${label} 缺少可读取的文字。`);
  }
  return value;
}

function normalizedEvidenceText(value: string): string {
  return value.normalize("NFKC").replace(/\s+/gu, "");
}

/** 已知合成/试用身份：出现即判定为 fixture 冒充，必须失败。 */
export const FORBIDDEN_PROJECT_ID_FRAGMENTS = [
  "project-synthetic",
  "synthetic-phase",
  "interface-trial",
  "uat-phase",
] as const;

export const FORBIDDEN_UI_MARKERS = [
  "界面试用项目",
  "UAT-PHASE-III",
  "UAT-01",
  "project-synthetic-phase-iii",
  "subject-uat-01-clear",
] as const;

/** 个例档案整理任务可见中文状态（不得出现 Agent/pipeline 词）。 */
export const PROFILE_ORGANIZE_STATUS = {
  queued: /个例档案整理排队中/,
  running: /正在整理个例档案/,
  succeeded: /个例档案已整理完成/,
  failed: /个例档案整理未完成/,
  stale: /资料已更新，需重新整理个例档案/,
} as const;

const STUDY_PHASE_RADIO: Record<StudyPhase, RegExp> = {
  phase_ii: /^II 期 /,
  phase_iii: /^III 期 /,
};

const STEP_CRITERIA: Record<AcceptanceStepId, readonly string[]> = {
  "gate.fixture_routes": [],
  "gate.fresh_identity": [],
  "flow.project_create": ["P5-AC12", "P5-AC13"],
  "flow.study_phase_select": ["P5-AC12", "P5-AC13"],
  "flow.subject_upload": ["P5-AC01", "P5-AC10", "P5-AC12"],
  "flow.ocr_processing": ["P5-AC01", "P5-AC10", "P5-AC12"],
  "flow.metadata_risk_review": ["P5-AC01", "P5-AC10", "P5-AC12"],
  "flow.build_activate": ["P5-AC01", "P5-AC10", "P5-AC11"],
  "flow.real_normalizer": ["P5-AC10", "P5-AC11", "P5-AC12"],
  "flow.patient_profile": ["P5-AC02", "P5-AC09", "P5-AC12"],
  "flow.source_locator": ["P5-AC02", "P5-AC12"],
  "flow.history_replay": ["P5-AC08", "P5-AC11", "P5-AC12"],
};

function envTrim(name: string): string | undefined {
  const value = process.env[name];
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function utcNowIso(): string {
  return new Date().toISOString();
}

function resolveUnderRoot(root: string, relativeOrAbsolute: string): string {
  if (isAbsolute(relativeOrAbsolute)) {
    throw new Error(`病例编排文件只能使用隔离目录内的相对路径: ${relativeOrAbsolute}`);
  }
  const resolvedRoot = resolve(root);
  const candidate = resolve(resolvedRoot, relativeOrAbsolute);
  if (candidate !== resolvedRoot && !candidate.startsWith(`${resolvedRoot}/`)) {
    throw new Error(`病例编排路径越出隔离目录: ${relativeOrAbsolute}`);
  }
  return candidate;
}

function fingerprintDataDir(dataDir: string): string {
  const resolved = resolve(dataDir);
  let marker = "missing";
  if (existsSync(resolved)) {
    const st = statSync(resolved);
    marker = `${st.isDirectory() ? "dir" : "file"}:${st.mtimeMs}:${st.size}`;
  }
  return createHash("sha256")
    .update(`${resolved}\n${marker}\n`)
    .digest("hex")
    .slice(0, 16);
}

function parseCasesFile(path: string): CaseDescriptor[] {
  const raw = JSON.parse(readFileSync(path, "utf8")) as unknown;
  if (!Array.isArray(raw) || raw.length === 0) {
    throw new Error(`cases file must be a non-empty array: ${path}`);
  }
  const cases: CaseDescriptor[] = [];
  for (const row of raw) {
    if (row === null || typeof row !== "object") {
      throw new Error(`invalid case row in ${path}`);
    }
    const item = row as Record<string, unknown>;
    const projectLabel = item.project_label;
    if (projectLabel !== "D001-II" && projectLabel !== "MG-K10-SAR-III") {
      throw new Error(`unsupported project_label in ${path}: ${String(projectLabel)}`);
    }
    const studyPhase = item.study_phase;
    if (studyPhase !== "phase_ii" && studyPhase !== "phase_iii") {
      throw new Error(`unsupported study_phase in ${path}: ${String(studyPhase)}`);
    }
    if (typeof item.case_id !== "string" || item.case_id.trim() === "") {
      throw new Error(`case_id required in ${path}`);
    }
    if (typeof item.protocol_file !== "string" || item.protocol_file.trim() === "") {
      throw new Error(`protocol_file required for ${item.case_id}`);
    }
    if (typeof item.subject_code !== "string" || item.subject_code.trim() === "") {
      throw new Error(`subject_code required for ${item.case_id}`);
    }
    if (!Array.isArray(item.subject_files) || item.subject_files.length === 0) {
      throw new Error(`subject_files required for ${item.case_id}`);
    }
    for (const field of [
      "expected_protocol_code",
      "expected_official_version",
      "expected_version_date",
      "expected_project_name_contains",
    ] as const) {
      if (typeof item[field] !== "string" || item[field].trim() === "") {
        throw new Error(`${field} required for ${item.case_id}`);
      }
    }
    const subjectFiles = item.subject_files.map((entry) => {
      if (typeof entry !== "string" || entry.trim() === "") {
        throw new Error(`invalid subject_files entry for ${item.case_id}`);
      }
      return entry;
    });
    cases.push({
      case_id: item.case_id.trim(),
      project_label: projectLabel,
      study_phase: studyPhase,
      protocol_file: item.protocol_file,
      subject_code: item.subject_code.trim(),
      subject_files: subjectFiles,
      expected_protocol_code: item.expected_protocol_code.trim(),
      expected_official_version: item.expected_official_version.trim(),
      expected_version_date: item.expected_version_date.trim(),
      expected_project_name_contains: item.expected_project_name_contains.trim(),
      preferred_stage_label:
        typeof item.preferred_stage_label === "string"
          ? item.preferred_stage_label
          : "筛选期",
    });
  }
  const labels = new Set(cases.map((entry) => entry.project_label));
  if (!labels.has("D001-II") || !labels.has("MG-K10-SAR-III")) {
    throw new Error(
      "browser-cases must include both D001-II and MG-K10-SAR-III project_label entries",
    );
  }
  return cases;
}

/**
 * 解析真实验收配置。
 * - 未设置 PHASE5_ISOLATED_DATASET_ROOT → disabled（调用方 skip）
 * - 已设置但缺必要项或角色不是独立测试者 → misconfigured（调用方必须失败，不得降级 fixture）
 */
export function resolveRealAcceptanceConfig(): ConfigResolution {
  const isolatedRoot = envTrim(PHASE5_ISOLATED_DATASET_ENV);
  if (isolatedRoot === undefined) {
    return {
      status: "disabled",
      reason: `未设置 ${PHASE5_ISOLATED_DATASET_ENV}；真实隔离验收套件保持 skip。`,
    };
  }

  const rootResolved = resolve(isolatedRoot);
  if (!existsSync(rootResolved) || !statSync(rootResolved).isDirectory()) {
    return {
      status: "misconfigured",
      reason: `${PHASE5_ISOLATED_DATASET_ENV} 不是可用目录: ${rootResolved}`,
    };
  }

  const roleRaw = envTrim(PHASE5_ROLE_ENV);
  if (roleRaw !== "independent_tester" && roleRaw !== "executor") {
    return {
      status: "misconfigured",
      reason: `${PHASE5_ROLE_ENV} 必须为 independent_tester 或 executor（当前缺失或非法）。`,
    };
  }

  if (roleRaw === "executor") {
    return {
      status: "misconfigured",
      reason:
        "执行者不得运行独立浏览器验收套件；请由独立测试者设置 PHASE5_REAL_ACCEPTANCE_ROLE=independent_tester。",
    };
  }

  const baseUrl = envTrim(PHASE5_BASE_URL_ENV);
  const dataDir = envTrim(PHASE5_DATA_DIR_ENV);
  if (baseUrl === undefined || dataDir === undefined) {
    return {
      status: "misconfigured",
      reason: `已启用隔离数据集，但缺少 ${PHASE5_BASE_URL_ENV} 或 ${PHASE5_DATA_DIR_ENV}。`,
    };
  }

  const dataDirResolved = resolve(dataDir);
  if (!existsSync(dataDirResolved) || !statSync(dataDirResolved).isDirectory()) {
    return {
      status: "misconfigured",
      reason: `${PHASE5_DATA_DIR_ENV} 不是可用目录: ${dataDirResolved}`,
    };
  }

  // 拒绝指向默认仓库 data_v2，强制新鲜隔离库身份。
  const normalizedData = dataDirResolved.replace(/\\/g, "/");
  if (
    normalizedData.endsWith("/data_v2") ||
    normalizedData.includes("/enrollment-review-app/data_v2")
  ) {
    return {
      status: "misconfigured",
      reason: `${PHASE5_DATA_DIR_ENV} 不得指向默认/生产 data_v2；请使用隔离新鲜目录。`,
    };
  }

  const freshMarker =
    envTrim(PHASE5_FRESH_MARKER_ENV) ?? join(dataDirResolved, ".phase5_fresh_acceptance");
  if (!existsSync(freshMarker)) {
    return {
      status: "misconfigured",
      reason: `缺少新鲜库标记文件（${PHASE5_FRESH_MARKER_ENV} 或 ${freshMarker}）。执行者须在空隔离库启动前写入该标记。`,
    };
  }

  const casesFileSetting = envTrim(PHASE5_CASES_FILE_ENV) ?? "browser-cases.json";
  let casesFile: string;
  try {
    casesFile = resolveUnderRoot(rootResolved, casesFileSetting);
  } catch (error) {
    return {
      status: "misconfigured",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
  if (!existsSync(casesFile)) {
    return {
      status: "misconfigured",
      reason: `缺少病例编排文件: ${casesFile}`,
    };
  }

  let cases: CaseDescriptor[];
  try {
    cases = parseCasesFile(casesFile);
  } catch (error) {
    return {
      status: "misconfigured",
      reason: error instanceof Error ? error.message : String(error),
    };
  }

  for (const caseRow of cases) {
    const protocolPath = resolveUnderRoot(rootResolved, caseRow.protocol_file);
    if (!existsSync(protocolPath)) {
      return {
        status: "misconfigured",
        reason: `病例 ${caseRow.case_id} 方案文件不存在: ${protocolPath}`,
      };
    }
    for (const relative of caseRow.subject_files) {
      const subjectPath = resolveUnderRoot(rootResolved, relative);
      if (!existsSync(subjectPath)) {
        return {
          status: "misconfigured",
          reason: `病例 ${caseRow.case_id} 受试者资料不存在: ${subjectPath}`,
        };
      }
    }
  }

  const observationsDir =
    envTrim(PHASE5_OBSERVATIONS_DIR_ENV) ?? join(rootResolved, "browser-observations");

  const allowLiveModel = envTrim(PHASE5_ALLOW_LIVE_MODEL_ENV) === "1";
  if (!allowLiveModel) {
    return {
      status: "misconfigured",
      reason: `真实验收必须显式设置 ${PHASE5_ALLOW_LIVE_MODEL_ENV}=1；未调用真实识别和模型时不得生成验收结果。`,
    };
  }

  return {
    status: "ready",
    config: {
      isolatedDatasetRoot: rootResolved,
      baseUrl: baseUrl.replace(/\/$/, ""),
      dataDir: dataDirResolved,
      role: roleRaw,
      allowLiveModel,
      casesFile,
      observationsDir,
      freshMarker,
      cases,
      databaseFingerprint: fingerprintDataDir(dataDirResolved),
    },
  };
}

export function studyPhaseRadio(phase: StudyPhase): RegExp {
  return STUDY_PHASE_RADIO[phase];
}

export function criteriaForStep(stepId: AcceptanceStepId): readonly string[] {
  return STEP_CRITERIA[stepId];
}

export class BrowserObservationSink {
  readonly path: string;
  private readonly observations: BrowserObservation[] = [];

  constructor(
    private readonly config: RealAcceptanceConfig,
    private readonly caseRow: CaseDescriptor,
    private readonly verifier: string,
  ) {
    mkdirSync(config.observationsDir, { recursive: true });
    this.path = join(config.observationsDir, `${caseRow.case_id}.jsonl`);
    writeFileSync(this.path, "", "utf8");
  }

  record(
    partial: Omit<
      BrowserObservation,
      | "schema_version"
      | "evidence_class"
      | "role"
      | "case_id"
      | "project_label"
      | "verifier"
      | "timestamp"
      | "criterion_ids"
    > & { criterion_ids?: readonly string[] },
  ): BrowserObservation {
    const observation: BrowserObservation = {
      schema_version: OBSERVATION_SCHEMA_VERSION,
      evidence_class: "browser_tester",
      role: this.config.role,
      case_id: this.caseRow.case_id,
      project_label: this.caseRow.project_label,
      criterion_ids: partial.criterion_ids ?? criteriaForStep(partial.step_id),
      verifier: this.verifier,
      timestamp: utcNowIso(),
      database_fingerprint: this.config.databaseFingerprint,
      ...partial,
    };
    this.observations.push(observation);
    appendFileSync(this.path, `${JSON.stringify(observation)}\n`, "utf8");
    return observation;
  }

  all(): readonly BrowserObservation[] {
    return this.observations;
  }
}

async function verifyLocatorAgainstFrozenPageText(
  page: Page,
  ids: { subjectId: string; episodeId: string },
  locatorLabel: string,
): Promise<{ excerpt: string; pageNumber: number; sourceDocumentVersionId: string }> {
  const excerpt = locatorLabel.replace(/^重点标注：?/, "").trim();
  if (excerpt.length === 0) {
    throw new Error("真实定位框没有携带可回查的原文摘录。");
  }
  const profileResponse = await page.request.get(
    `/api/v2/subjects/${encodeURIComponent(ids.subjectId)}/review-episodes/${encodeURIComponent(ids.episodeId)}/patient-profile`,
  );
  expect(profileResponse.ok(), "应能读取当前个例档案用于定位闭环核对").toBe(true);
  const profile = objectValue(await profileResponse.json(), "个例档案");
  const navigation = objectValue(profile.evidence_navigation, "个例档案证据导航");
  const revisionId = stringValue(
    navigation.complete_processing_revision_id,
    "完整资料处理版本",
  );
  const locators = arrayValue(profile.evidence_locators, "个例档案原文定位").map(
    (value, index) => objectValue(value, `个例档案原文定位 ${index + 1}`),
  );
  const locator = locators.find((candidate) => candidate.excerpt === excerpt);
  if (locator === undefined) {
    throw new Error("当前红框摘录无法在同一档案修订的定位清单中找到。");
  }
  const pageArtifactId = stringValue(locator.page_artifact_id, "定位页身份");
  const sourceDocumentVersionId = stringValue(
    locator.source_document_version_id,
    "定位文件身份",
  );
  const pageNumber = Number(locator.page_number);
  if (!Number.isInteger(pageNumber) || pageNumber < 1) {
    throw new Error("定位页码无效。");
  }

  const revisionResponse = await page.request.get(
    `/api/v2/evidence-processing-revisions/${encodeURIComponent(revisionId)}`,
  );
  expect(revisionResponse.ok(), "应能读取定位所属的完整资料处理版本").toBe(true);
  const revision = objectValue(await revisionResponse.json(), "完整资料处理版本");
  const revisionPages = arrayValue(revision.pages, "完整资料页清单").map(
    (value, index) => objectValue(value, `完整资料页 ${index + 1}`),
  );
  const revisionPage = revisionPages.find(
    (candidate) =>
      candidate.page_artifact_id === pageArtifactId &&
      candidate.source_document_version_id === sourceDocumentVersionId &&
      candidate.page_number === pageNumber,
  );
  if (revisionPage === undefined) {
    throw new Error("定位引用的文件、页码与当前完整资料处理版本不一致。");
  }
  const ocrPageId = stringValue(revisionPage.ocr_page_id, "定位页识别结果");
  const ocrResponse = await page.request.get(
    `/api/v2/ocr-pages/${encodeURIComponent(ocrPageId)}?processing_revision_id=${encodeURIComponent(revisionId)}`,
  );
  expect(ocrResponse.ok(), "应能读取定位页冻结的识别文本").toBe(true);
  const ocrPage = objectValue(await ocrResponse.json(), "定位页识别结果");
  const frozenText =
    typeof ocrPage.effective_text === "string"
      ? ocrPage.effective_text
      : stringValue(ocrPage.raw_text, "定位页原始识别文本");
  expect(
    normalizedEvidenceText(frozenText),
    "红框摘录必须真实存在于同一文件同一页的冻结识别文本中",
  ).toContain(normalizedEvidenceText(excerpt));
  return { excerpt, pageNumber, sourceDocumentVersionId };
}

/**
 * 安装真实请求观察：拒绝引用已知 fixture 模块路径。
 * 是否接入真实后端还会由空数据库身份、真实上传和持久化结果共同验证；本函数本身
 * 不声称能够观察 Playwright 内部所有 route 注册。
 */
export async function installFixtureRouteTrap(page: Page): Promise<void> {
  page.on("request", (request) => assertAbsoluteApiUrl(request.url()));
  await page.addInitScript(() => {
    const marker = "__phase5RealAcceptanceNoFixture__";
    (window as unknown as Record<string, boolean>)[marker] = true;
  });
}

export function assertAbsoluteApiUrl(url: string): void {
  if (url.includes("profile-evidence-fixtures") || url.includes("evidence-fixtures")) {
    throw new Error(`禁止依赖 fixture 模块路径的请求: ${url}`);
  }
}

export async function assertNoForbiddenUiMarkers(page: Page): Promise<void> {
  const bodyText = await page.locator("body").innerText();
  for (const marker of FORBIDDEN_UI_MARKERS) {
    expect(bodyText, `检测到 fixture/试用 UI 标记「${marker}」`).not.toContain(marker);
  }
}

export function assertProjectIdentityNotFixture(projectId: string, projectName: string): void {
  const haystack = `${projectId} ${projectName}`.toLowerCase();
  for (const fragment of FORBIDDEN_PROJECT_ID_FRAGMENTS) {
    if (haystack.includes(fragment)) {
      throw new Error(`项目身份疑似 fixture：${projectId} / ${projectName}`);
    }
  }
  for (const marker of FORBIDDEN_UI_MARKERS) {
    if (`${projectId} ${projectName}`.includes(marker)) {
      throw new Error(`项目身份包含试用标记：${projectId} / ${projectName}`);
    }
  }
}

type ProtocolProjectRow = {
  project_id: string;
  project_name: string;
  study_phase?: string;
  study_phase_label?: string;
};

export async function fetchProtocolProjects(
  page: Page,
  baseUrl: string,
): Promise<ProtocolProjectRow[]> {
  const response = await page.request.get(`${baseUrl}/api/v2/protocol/projects`);
  if (!response.ok()) {
    throw new Error(`读取项目目录失败: HTTP ${response.status()}`);
  }
  const payload = (await response.json()) as unknown;
  if (payload === null || typeof payload !== "object") {
    throw new Error("项目目录响应必须是对象");
  }
  const projects = (payload as Record<string, unknown>).projects;
  if (!Array.isArray(projects)) {
    throw new Error("项目目录响应缺少 projects 数组");
  }
  return projects.map((row) => {
    if (row === null || typeof row !== "object") {
      throw new Error("项目目录行非法");
    }
    const item = row as Record<string, unknown>;
    if (typeof item.project_id !== "string" || typeof item.project_name !== "string") {
      throw new Error("项目目录缺少 project_id/project_name");
    }
    assertProjectIdentityNotFixture(item.project_id, item.project_name);
    return {
      project_id: item.project_id,
      project_name: item.project_name,
      study_phase: typeof item.study_phase === "string" ? item.study_phase : undefined,
      study_phase_label:
        typeof item.study_phase_label === "string" ? item.study_phase_label : undefined,
    };
  });
}

export async function assertFreshDatabaseIdentity(
  page: Page,
  config: RealAcceptanceConfig,
  sink: BrowserObservationSink,
): Promise<void> {
  const projects = await fetchProtocolProjects(page, config.baseUrl);
  expect(projects, "真实验收必须从空项目目录开始，不能复用旧项目").toHaveLength(0);
  const observation = sink.record({
    step_id: "gate.fresh_identity",
    source_locator: config.dataDir,
    artifact: sink.path,
    observed_result: `database_fingerprint=${config.databaseFingerprint}; project_count=0; fresh_marker=${config.freshMarker}`,
    disposition: "pass",
    notes: "结构性新鲜度观察；不代表临床正确。",
  });
  expect(observation.database_fingerprint).toBe(config.databaseFingerprint);
  expect(existsSync(config.freshMarker)).toBe(true);
}

/**
 * 若调用方试图复用 profile/evidence fixture 的 route 注册，立即失败。
 * 通过禁止导入路径在运行时无法拦截，故在此提供显式守卫供 spec 调用。
 */
export function rejectFixtureRouteRegistration(label: string): never {
  throw new Error(
    `Phase 5.8 真实验收禁止注册 fixture 路由（${label}）。请使用真实后端，不要调用 registerProfileRoutes/registerEvidenceRoutes。`,
  );
}

export function resolveCasePaths(
  config: RealAcceptanceConfig,
  caseRow: CaseDescriptor,
): { protocolFile: string; subjectFiles: string[] } {
  return {
    protocolFile: resolveUnderRoot(config.isolatedDatasetRoot, caseRow.protocol_file),
    subjectFiles: caseRow.subject_files.map((relative) =>
      resolveUnderRoot(config.isolatedDatasetRoot, relative),
    ),
  };
}

export async function openHash(page: Page, baseUrl: string, hash: string): Promise<void> {
  const url = hash.startsWith("#") ? `${baseUrl}/${hash}` : `${baseUrl}/#${hash}`;
  await page.goto(url);
  await page.waitForLoadState("networkidle");
}

/** 编排步骤：创建项目（方案上传 → 期别选择 → 发布）。需 allowLiveModel 或显式骨架 dry 标记时由调用方分支。 */
export async function stepCreateProjectAndSelectPhase(
  page: Page,
  config: RealAcceptanceConfig,
  caseRow: CaseDescriptor,
  sink: BrowserObservationSink,
): Promise<{ projectId: string; projectName: string }> {
  if (!config.allowLiveModel) {
    sink.record({
      step_id: "flow.project_create",
      source_locator: caseRow.protocol_file,
      artifact: sink.path,
      observed_result: "live model/OCR not allowed in this pass; project create not_run",
      disposition: "not_run",
      notes: `设置 ${PHASE5_ALLOW_LIVE_MODEL_ENV}=1 后由独立测试者执行。`,
    });
    sink.record({
      step_id: "flow.study_phase_select",
      source_locator: caseRow.study_phase,
      artifact: sink.path,
      observed_result: "study phase selection deferred until live model allowed",
      disposition: "not_run",
    });
    return { projectId: "", projectName: `${caseRow.project_label}-pending` };
  }

  const { protocolFile } = resolveCasePaths(config, caseRow);

  await openHash(page, config.baseUrl, "/protocols?mode=first");
  await page.locator('input[type="file"]').setInputFiles(protocolFile);
  await expect(page.getByRole("heading", { name: "核对方案信息与研究期别" })).toBeVisible({
    timeout: 120_000,
  });

  sink.record({
    step_id: "flow.project_create",
    source_locator: protocolFile,
    artifact: sink.path,
    observed_result: "protocol upload reached identity confirmation",
    disposition: "observed_only",
  });

  await expect(page.getByLabel("方案编号")).toHaveValue(caseRow.expected_protocol_code);
  await expect(page.getByLabel("正式版本")).toHaveValue(caseRow.expected_official_version);
  await expect(page.getByLabel("版本日期")).toHaveValue(caseRow.expected_version_date);
  const projectNameInput = page.getByLabel("项目名称");
  await expect(projectNameInput).toHaveValue(
    new RegExp(caseRow.expected_project_name_contains),
  );
  const projectName = (await projectNameInput.inputValue()).trim();
  expect(projectName, "项目名称必须由方案原文自动提取，验收脚本不得人工覆盖").not.toBe("");
  await page.getByRole("radio", { name: studyPhaseRadio(caseRow.study_phase) }).check();

  sink.record({
    step_id: "flow.study_phase_select",
    source_locator: caseRow.study_phase,
    artifact: sink.path,
    observed_result: `selected study phase ${caseRow.study_phase} for ${caseRow.project_label}`,
    disposition: "observed_only",
  });

  await page.getByRole("button", { name: "确认并继续解构" }).click();
  const draftHeading = page.getByRole("heading", { name: "审阅解构草稿" });
  const failedHeading = page.getByRole("heading", { name: "草稿生成未完成" });
  const jobMatch = page.url().match(/[?&]job=([^&#]+)/);
  const jobId = jobMatch?.[1] ? decodeURIComponent(jobMatch[1]) : "";
  expect(jobId, "确认方案信息后地址中应保留持久任务身份").not.toBe("");
  let terminalFailureDetail = "";
  const draftOutcome = await expect
    .poll(
      async () => {
        if ((await draftHeading.count()) > 0) return "ready";
        if ((await failedHeading.count()) > 0) return "failed";
        const response = await page.request.get(
          `${config.baseUrl}/api/v2/protocol/deconstructions/${encodeURIComponent(jobId)}`,
        );
        if (!response.ok()) return "waiting";
        const payload = objectValue(await response.json(), "方案解构任务");
        if (payload.awaiting_user === "review") return "ready";
        if (payload.state === "failed_final" || payload.state === "cancelled") {
          terminalFailureDetail = [payload.state_label, payload.next_action]
            .filter((value): value is string => typeof value === "string" && value.length > 0)
            .join("；");
          return "failed";
        }
        return "waiting";
      },
      { timeout: 2_700_000, intervals: [2_000] },
    )
    .not.toBe("waiting")
    .then(async () =>
      terminalFailureDetail.length > 0 || (await failedHeading.count()) > 0
        ? "failed"
        : "ready",
    );
  if (draftOutcome === "failed") {
    const failureText = await page.locator("main").innerText();
    throw new Error(
      `方案草稿生成未完成：${terminalFailureDetail || failureText}`,
    );
  }
  await expect(draftHeading).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("button", { name: "发布" })).toBeEnabled();
  await page.getByRole("button", { name: "发布" }).click();
  await page.getByRole("button", { name: "确认发布" }).click();
  await expect(page.getByRole("heading", { name: "发布完成" })).toBeVisible({
    timeout: 120_000,
  });

  await assertNoForbiddenUiMarkers(page);
  const projects = await fetchProtocolProjects(page, config.baseUrl);
  const created = projects.find((project) => project.project_name === projectName);
  expect(created, `发布后项目目录中应存在 ${projectName}`).toBeDefined();
  expect(created?.study_phase).toBe(caseRow.study_phase);
  return { projectId: created!.project_id, projectName };
}

export async function stepUploadSubjectMaterials(
  page: Page,
  config: RealAcceptanceConfig,
  caseRow: CaseDescriptor,
  sink: BrowserObservationSink,
  project: { projectId: string; projectName: string },
): Promise<{ subjectId: string; episodeId: string }> {
  if (!config.allowLiveModel) {
    sink.record({
      step_id: "flow.subject_upload",
      source_locator: caseRow.subject_files.join(","),
      artifact: sink.path,
      observed_result: "subject upload not_run without live model allowance",
      disposition: "not_run",
    });
    return { subjectId: "", episodeId: "" };
  }

  const { subjectFiles } = resolveCasePaths(config, caseRow);
  await openHash(page, config.baseUrl, `/subjects?project=${project.projectId}`);
  await expect(page.getByRole("heading", { name: "受试者与资料", level: 1 })).toBeVisible();

  const projectSelect = page.getByLabel("选择项目");
  if (await projectSelect.count()) {
    const options = await projectSelect.locator("option").allTextContents();
    const match = options.find((label) => label.includes(project.projectName));
    if (match) {
      const value = await projectSelect.locator("option", { hasText: match }).first().getAttribute("value");
      if (value) await projectSelect.selectOption(value);
    }
  }

  await page.getByRole("button", { name: "新增受试者" }).click();
  const createDialog = page.getByRole("dialog", { name: "新增受试者" });
  await createDialog.getByLabel(/受试者代号/).fill(caseRow.subject_code);
  await createDialog.getByRole("button", { name: "确认新增" }).click();
  await expect(page.getByRole("heading", { name: caseRow.subject_code, level: 2 })).toBeVisible({
    timeout: 60_000,
  });

  const screening = page.locator("article.catalog-episode", {
    hasText: caseRow.preferred_stage_label ?? "筛选期",
  });
  await screening.getByRole("link", { name: /打开.*证据工作台|打开筛选证据工作台/ }).click();
  await expect(page.getByRole("heading", { name: "证据工作台", level: 1 })).toBeVisible();

  await page.getByRole("radio", { name: "建立完整资料快照" }).click();
  await page.setInputFiles("#evidence-file-input", subjectFiles);
  const preview = page.getByLabel("确认前复核");
  await expect(preview).toBeVisible();
  await preview.getByRole("button", { name: "确认上传" }).click();

  const url = page.url();
  const subjectMatch = url.match(/subjects\/([^/?#]+)/);
  const episodeMatch = url.match(/[?&]episode=([^&]+)/);
  const subjectId = subjectMatch?.[1] ?? "";
  const episodeId = episodeMatch?.[1] ?? "";

  sink.record({
    step_id: "flow.subject_upload",
    source_locator: subjectFiles.join(","),
    artifact: sink.path,
    observed_result: `uploaded ${subjectFiles.length} file(s); subjectId=${subjectId || "unknown"}; episodeId=${episodeId || "unknown"}`,
    disposition: "observed_only",
    subject_id: subjectId || null,
    review_episode_id: episodeId || null,
  });

  await assertNoForbiddenUiMarkers(page);
  return { subjectId, episodeId };
}

export async function stepRealNormalizer(
  page: Page,
  config: RealAcceptanceConfig,
  sink: BrowserObservationSink,
): Promise<void> {
  if (!config.allowLiveModel) {
    for (const stepId of [
      "flow.ocr_processing",
      "flow.metadata_risk_review",
      "flow.build_activate",
      "flow.real_normalizer",
    ] as const) {
      sink.record({
        step_id: stepId,
        source_locator: "fact-normalization-job",
        artifact: sink.path,
        observed_result: `${stepId} not_run; ALLOW_LIVE_MODEL unset`,
        disposition: "not_run",
        notes: "禁止在本 worker 通行调用真实 OCR/模型；独立测试者显式开通后再跑。",
      });
    }
    return;
  }

  // 1) 等待真实 OCR/资料整理完成，出现可生成版本入口（不伪造 API 状态）。
  const buildButton = page.getByRole("button", {
    name: "检查核对结果并生成资料版本",
  });
  await expect(buildButton).toBeVisible({ timeout: 300_000 });
  sink.record({
    step_id: "flow.ocr_processing",
    source_locator: "evidence-workspace",
    artifact: sink.path,
    observed_result: "OCR/资料整理完成后出现生成资料版本入口",
    disposition: "observed_only",
  });

  // 2) 元数据与识别风险核对：有待保存项则逐项填写后保存。
  const fileList = page.getByLabel("文件清单");
  if (await fileList.count()) {
    const fileButtons = fileList.getByRole("button");
    const fileCount = await fileButtons.count();
    for (let index = 0; index < fileCount; index += 1) {
      await fileButtons.nth(index).click();
      const metadata = page.getByLabel("核对资料信息");
      if (await metadata.count()) {
        const saveMeta = metadata.getByRole("button", { name: "保存核对结果" });
        if (await saveMeta.isVisible().catch(() => false)) {
          const note = metadata.getByRole("textbox", { name: "核对说明" });
          if (await note.count()) {
            await note.fill("已对照原始资料核对文件类型与提供方");
          }
          await saveMeta.click();
        }
      }
    }
  }

  for (let pass = 0; pass < 40; pass += 1) {
    const activate = page.getByRole("button", { name: "启用这个资料版本" });
    if (await activate.isVisible().catch(() => false)) break;

    const saveRisk = page.getByRole("button", { name: "保存核对" }).first();
    if (!(await saveRisk.isVisible().catch(() => false))) {
      if (await buildButton.isVisible().catch(() => false)) {
        await buildButton.click();
      }
      await page.waitForTimeout(1_000);
      continue;
    }
    const item = saveRisk.locator(
      "xpath=ancestor::*[contains(@class,'evidence-risk-item')]",
    );
    const reviewedBefore = await page.getByText(/^已核对：/).count();
    await item.getByRole("textbox").fill("已逐字对照原始资料，确认识别内容无误");
    await saveRisk.click();
    await expect(page.getByText(/^已核对：/)).toHaveCount(reviewedBefore + 1, {
      timeout: 30_000,
    });
  }

  sink.record({
    step_id: "flow.metadata_risk_review",
    source_locator: "evidence-workspace",
    artifact: sink.path,
    observed_result: "completed metadata/risk review loop against live workspace",
    disposition: "observed_only",
  });

  // 3) 生成完整处理修订并启用；不得假设启用即已有 Profile。
  const activate = page.getByRole("button", { name: "启用这个资料版本" });
  await expect(activate).toBeVisible({ timeout: 300_000 });
  await activate.click();
  await expect(page.getByLabel("当前资料上下文")).toContainText("当前有效", {
    timeout: 120_000,
  });
  sink.record({
    step_id: "flow.build_activate",
    source_locator: "evidence-active-revision",
    artifact: sink.path,
    observed_result: "complete processing revision activated; profile not assumed yet",
    disposition: "observed_only",
  });

  // 4) 等待真实个例档案整理任务状态（UI 自动发起；禁止直接 API 伪造）。
  const organize = page.getByLabel("个例档案整理状态");
  await expect(organize).toBeVisible({ timeout: 120_000 });
  await expect(organize).not.toContainText(/Agent|pipeline|schema|provider|PromptVersion/i);
  await expect
    .poll(async () => organize.innerText(), { timeout: 600_000 })
    .toMatch(PROFILE_ORGANIZE_STATUS.succeeded);

  sink.record({
    step_id: "flow.real_normalizer",
    source_locator: "fact-normalization-job",
    artifact: sink.path,
    observed_result: "real normalization job reached succeeded Chinese status",
    disposition: "observed_only",
  });
}

export async function stepPatientProfileAndLocator(
  page: Page,
  config: RealAcceptanceConfig,
  caseRow: CaseDescriptor,
  sink: BrowserObservationSink,
  ids: { subjectId: string; episodeId: string },
): Promise<void> {
  if (!config.allowLiveModel || !ids.subjectId || !ids.episodeId) {
    sink.record({
      step_id: "flow.patient_profile",
      source_locator: "patient-profile",
      artifact: sink.path,
      observed_result: "patient profile step not_run",
      disposition: "not_run",
    });
    sink.record({
      step_id: "flow.source_locator",
      source_locator: "evidence-locator",
      artifact: sink.path,
      observed_result: "source locator step not_run",
      disposition: "not_run",
    });
    sink.record({
      step_id: "flow.history_replay",
      source_locator: "profile-revision-history",
      artifact: sink.path,
      observed_result: "history replay step not_run",
      disposition: "not_run",
    });
    return;
  }

  await openHash(
    page,
    config.baseUrl,
    `/subjects?subject=${ids.subjectId}&episode=${ids.episodeId}`,
  );
  await expect(page.getByRole("heading", { name: "受试者与资料", level: 1 })).toBeVisible();

  // 刷新恢复：持久任务状态不得只存在于组件内存。
  await page.reload();
  await expect(page.getByRole("heading", { name: "受试者与资料", level: 1 })).toBeVisible();

  const profile = page.getByLabel("个例全景");
  await expect(profile).toBeVisible({ timeout: 300_000 });
  await expect(profile).not.toContainText(PROFILE_ORGANIZE_STATUS.failed);
  await assertNoForbiddenUiMarkers(page);

  const profileText = await profile.innerText();
  expect(profileText).not.toMatch(/通过\/不通过|入排主结论|负责方|Agent|pipeline|schema/);

  sink.record({
    step_id: "flow.patient_profile",
    source_locator: ids.episodeId,
    artifact: sink.path,
    observed_result: `succeeded profile visible for ${caseRow.subject_code}; no enrollment conclusion language`,
    disposition: "observed_only",
    subject_id: ids.subjectId,
    review_episode_id: ids.episodeId,
  });

  const evidenceButtons = page.getByRole("button", { name: /查看.*原文证据/ });
  await expect
    .poll(async () => evidenceButtons.count(), { timeout: 180_000 })
    .toBeGreaterThan(0);
  const evidenceButtonCount = await evidenceButtons.count();
  let verifiedLocator = false;
  let verifiedLocatorEvidence:
    | { excerpt: string; pageNumber: number; sourceDocumentVersionId: string }
    | null = null;
  for (let index = 0; index < evidenceButtonCount; index += 1) {
    await evidenceButtons.nth(index).click();
    const panel = page.getByLabel("该条目的原文证据与定位");
    await expect(panel).toBeVisible();
    const pageImage = panel.getByAltText(/第 .+ 页原始资料/).first();
    const selectedBox = panel.getByLabel(/^重点标注/).first();
    if ((await pageImage.count()) > 0 && (await selectedBox.count()) > 0) {
      await expect
        .poll(() =>
          pageImage.evaluate(
            (element) =>
              element instanceof HTMLImageElement &&
              element.complete &&
              element.naturalWidth > 0,
          ),
        )
        .toBe(true);
      const placement = await selectedBox.evaluate((box) => {
        const image = box.parentElement?.querySelector("img");
        if (!(image instanceof HTMLImageElement)) return null;
        const boxRect = box.getBoundingClientRect();
        const imageRect = image.getBoundingClientRect();
        return {
          boxLeft: boxRect.left,
          boxTop: boxRect.top,
          boxRight: boxRect.right,
          boxBottom: boxRect.bottom,
          imageLeft: imageRect.left,
          imageTop: imageRect.top,
          imageRight: imageRect.right,
          imageBottom: imageRect.bottom,
        };
      });
      expect(placement, "真实定位框必须与已解码原件页处于同一可见区域").not.toBeNull();
      expect(placement!.boxRight).toBeGreaterThan(placement!.imageLeft);
      expect(placement!.boxBottom).toBeGreaterThan(placement!.imageTop);
      expect(placement!.boxLeft).toBeLessThan(placement!.imageRight);
      expect(placement!.boxTop).toBeLessThan(placement!.imageBottom);
      const locatorLabel = await selectedBox.getAttribute("aria-label");
      verifiedLocatorEvidence = await verifyLocatorAgainstFrozenPageText(
        page,
        { subjectId: ids.subjectId, episodeId: ids.episodeId },
        stringValue(locatorLabel, "当前红框原文摘录"),
      );
      verifiedLocator = true;
      break;
    }
    await page.getByRole("button", { name: "关闭原文证据" }).click();
  }
  expect(
    verifiedLocator,
    "代表病例至少一条关键事实必须具备可解码原件页和真实定位框；全部降级为不可定位不能通过验收",
  ).toBe(true);

  sink.record({
    step_id: "flow.source_locator",
    source_locator: ids.episodeId,
    artifact: sink.path,
    observed_result: verifiedLocatorEvidence === null
      ? "未完成原文定位闭环核对"
      : `已核对真实原件第 ${verifiedLocatorEvidence.pageNumber} 页、冻结识别文本与红框摘录一致`,
    disposition: "observed_only",
    subject_id: ids.subjectId,
    review_episode_id: ids.episodeId,
  });

  const historyToggle = page.getByRole("button", { name: /修订记录|事实修订历史|修订历史/ });
  if (await historyToggle.count()) {
    await historyToggle.first().click();
    const history = page.getByLabel(/修订记录|事实修订历史/).or(
      page.locator(".profile-correction-history-section"),
    );
    await expect(history.first()).toBeVisible();
    sink.record({
      step_id: "flow.history_replay",
      source_locator: ids.episodeId,
      artifact: sink.path,
      observed_result: "opened immutable correction/history surface for replay inspection",
      disposition: "observed_only",
      subject_id: ids.subjectId,
      review_episode_id: ids.episodeId,
    });
  } else {
    sink.record({
      step_id: "flow.history_replay",
      source_locator: ids.episodeId,
      artifact: sink.path,
      observed_result: "history surface not present yet; no fabricated pass",
      disposition: "observed_only",
      notes: "无修订历史时不伪造回放通过；首次整理成功后允许空历史。",
      subject_id: ids.subjectId,
      review_episode_id: ids.episodeId,
    });
  }
}

export function writeRunSummary(
  config: RealAcceptanceConfig,
  testInfo: TestInfo,
  sinks: BrowserObservationSink[],
): string {
  const summaryPath = join(
    config.observationsDir,
    `run-summary-${testInfo.project.name}-${Date.now()}.json`,
  );
  mkdirSync(dirname(summaryPath), { recursive: true });
  const payload = {
    schema_version: "phase5.browser_run_summary.v1",
    evidence_class: "browser_tester",
    role: config.role,
    database_fingerprint: config.databaseFingerprint,
    isolated_dataset_root: config.isolatedDatasetRoot,
    data_dir: config.dataDir,
    allow_live_model: config.allowLiveModel,
    project: testInfo.project.name,
    observations: sinks.flatMap((sink) => sink.all()),
    note: "Observations only; Codex remains final acceptance authority. Automated green ≠ clinical correctness.",
  };
  writeFileSync(summaryPath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return summaryPath;
}
