/**
 * 前端唯一数据访问出口：组件与页面只从此处获取数据。
 * Phase 1 为 stub 实现；真实 API 就绪后在同一接口下替换实现。
 */

export {
  createStubRepository,
  getDefaultRepository,
  StubApiError,
  type EnrollmentRepository,
} from "./stubRepository";
export { FIXTURE_SCHEMA_VERSION } from "./fixtureAssets";
