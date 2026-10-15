# Codex Conference Review: enrollment_phase1_visual_acceptance

Date: 2026-08-13

## Verdict

接受进入 Phase 1.5。Phase 1 已完成；Phase 2 仍被用户验收门阻断。

## Boundary Compliance

- 独立角色使用 `kimi-code/k3-256k` 高强度、同一会话完成首轮与复核，没有使用用户明确排除的 Qwen 3.8。
- 审查只读当前工作区、截图和本地试用站点；未读取工作区外临床资料、未做安全测试、未修改工程。
- 首次目录探测超时后按规则执行真实路由；真实会话可恢复，因此没有随意 fallback 或重派。

## Participant Outputs Reviewed

- 首轮：`runs/conference/enrollment_phase1_visual_acceptance/visual_pi_k3_256k.md`，结论“阻断并修订”。
- 同会话复核：`runs/conference/enrollment_phase1_visual_acceptance/visual_pi_k3_256k_round2.md`，结论“接受进入 Phase 1.5”。

## Conference Panel Review

首轮最有价值的发现不是表面文案，而是时间约束模型的契约错配：界面读取不存在的旧字段，导致关键洗脱时间显示为 `undefined`。审查者同时指出父子规则缺少风险汇总、事项缺少规则编号和证据深链、默认落点不风险优先、合成文件名泄露实现标签、单位未中文化及缩放覆盖不足。

复核确认上述核心问题关闭，但发现方案差异区仍有 `REQ-02`，且原缩放用例在 hash 路由页面加载完成前测量，属于假阳性。该挑战有效，Codex 在会后继续修订而未直接归档。

## Main-Venue Codex Review

- 接受独立审查对数据契约、信息层级和证据可达的判断。
- 关闭 `REQ-` 残余的共享原因：方案差异和近期变化统一经过显示编号映射。
- 修复测试证据失真：路由切换后等待新页面标题、关键内容和加载状态退出。
- 拒绝继续用 `body.style.zoom` 作为浏览器缩放代理；真实浏览器缩放改变 CSS 布局视口，而该写法不会触发同样的媒体查询。改为按 1440 物理宽度换算 960/720 CSS 布局视口。

## Codex Independent Verification

- `npm test -- --run`：19 个文件、137 项通过。
- `npm run build`：通过；主包约 1.50MB 的警告由 Phase 1 冻结 fixture 打包造成，后续真实 API 接入时消失或拆分，不阻断本阶段。
- `npm run e2e`：153 项通过、27 项按视口设计跳过、0 项失败；九个一级页面跨 1280/1440/1920/390，严重/致命可访问性问题为 0。
- 1440 物理宽度下九个一级页面在 150%/200% 等效布局缩放均无页面级横向滚动，并跨页断言无 `REQ-`、`undefined`、`null`、`year`、`xULN`。
- Codex 逐张复看桌面今日工作、方案工作台、受试者个例、200% 工作台，以及 390 窄屏今日工作、工作台、受试者个例；未见遮挡、无意义断行或新阻断。

## Final Decision

Phase 1 归档为完成。保留本地站点给用户执行 Phase 1.5；在用户确认默认首屏和核心操作体验前，不开始数据库、真实 OCR/模型审核或 Graph 持久化实现。
