/**
 * fixture 资产装载：`contracts/v1/fixtures/*.json`（schema_version=fixture/v1）
 * 的副本统一在此装载并断言版本。
 *
 * 边界说明：JSON import 的字面量类型比 wire 类型更宽（字符串推断为 string），
 * 此处做一次收窄断言；映射单元测试会校验实际数据与枚举/字段一致，
 * 防止与 schema 契约漂移。不做整包 JSON Schema 运行时校验：
 * 运行时校验库由 Phase 0.5 决策明确推迟，本轮不引入新依赖。
 */

import workspaceJson from "../fixtures/uat-phase1-workspace.json";
import subjectClearJson from "../fixtures/subject-clear.json";
import subjectBarrierJson from "../fixtures/subject-barrier.json";
import subjectGapConflictJson from "../fixtures/subject-gap_conflict.json";
import type { EpisodeFixtureWire, WorkspaceFixtureWire } from "./wire";

export const FIXTURE_SCHEMA_VERSION = "fixture/v1";

export const workspaceFixture = workspaceJson as WorkspaceFixtureWire;
export const subjectClearFixture = subjectClearJson as EpisodeFixtureWire;
export const subjectBarrierFixture = subjectBarrierJson as EpisodeFixtureWire;
export const subjectGapConflictFixture = subjectGapConflictJson as EpisodeFixtureWire;

/** 单受试者独立 fixture（与 workspace 内嵌副本同源） */
export const subjectFixtures: ReadonlyArray<EpisodeFixtureWire> = [
  subjectClearFixture,
  subjectBarrierFixture,
  subjectGapConflictFixture,
];

export function assertFixtureVersion(version: string): void {
  if (version !== FIXTURE_SCHEMA_VERSION) {
    throw new Error(
      `fixture 版本不匹配：期望 ${FIXTURE_SCHEMA_VERSION}，实际 ${version}。请重新复制 contracts/v1/fixtures 资产。`,
    );
  }
}
