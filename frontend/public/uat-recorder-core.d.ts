export interface TaskRecord {
  completed: boolean | null;
  assisted: boolean | null;
  layoutIssue: boolean | null;
  criticalEvidenceOperations: number | null;
  isInvalid: boolean;
  invalidReason: string;
  errorCategories: string[];
  notes: string;
  [key: string]: unknown;
}

export interface ParticipantRecord {
  taskRecords: Record<string, TaskRecord>;
  [key: string]: unknown;
}

export interface BatchRecord {
  participants: ParticipantRecord[];
  [key: string]: unknown;
}

export interface TaskDefinition {
  id: string;
  title: string;
  criticalEvidenceRequired: boolean;
}

export interface GateResult {
  label: string;
  passed: boolean | null;
  statusText: string;
  tasksWithoutRuns?: string[];
}

export interface RecorderSummary {
  validRunCount: number;
  invalidRunCount: number;
  e4Count: number;
  hasErrorConclusion: boolean;
  stopWarnings: string[];
  layout: { checkedRuns: number };
  gates: Record<string, GateResult> & {
    errorConclusion: GateResult;
    perTaskUnassistedRate: GateResult & { tasksWithoutRuns: string[] };
    criticalEvidenceOps: GateResult;
    layoutKeyboard: GateResult;
  };
}

export const TASKS: readonly TaskDefinition[];
export function createEmptyBatch(overrides?: Partial<BatchRecord>): BatchRecord;
export function createEmptyParticipant(overrides?: Record<string, unknown>): ParticipantRecord;
export function summarizeBatch(batch: BatchRecord):
  | { ok: true; errors: []; value: RecorderSummary }
  | { ok: false; errors: string[]; value?: undefined };
export function generateBackupText(batch: BatchRecord, exportedAt?: string): string;
export function parseBackupText(text: string):
  | {
      ok: true;
      errors: [];
      value: BatchRecord;
      meta: {
        batchCode: string;
        pageVersion: string;
        participantCount: number;
        taskRecordCount: number;
        fixtureVersion: string;
      };
    }
  | { ok: false; errors: string[]; value?: undefined; meta?: undefined };
