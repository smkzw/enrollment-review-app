# 真实浏览器缩放验收

日期：2026-08-14

## 环境与路径

- 浏览器：本机 Chrome，真实缩放 100%、150%、200%。
- 页面：`http://127.0.0.1:4173/#/workbench?episode=episode-uat-02-screening-barrier&component=component-in-01&evidence=span-uat-02-screening-barrier-risk`
- 操作：从入排工作台打开“原始资料证据”弹窗，核对文件、来源方、资料快照、页码、定位精度、摘录和定位说明。

## 观察

- 三档缩放均能读取弹窗主信息和关闭入口。
- 没有页面级横向溢出、文字相互遮挡、按钮裁切或用缩小字号掩盖布局问题。
- 150%/200% 下内容自然重排；弹窗内容可继续纵向浏览。
- 页面明确说明当前界面试用未附带原始页图，不把“页内摘录”伪装成字符级或坐标级定位。

## 证据

- `frontend/e2e/screenshots/real-browser-zoom/chrome-100-system-window.png`
- `frontend/e2e/screenshots/real-browser-zoom/chrome-150-system-window.png`
- `frontend/e2e/screenshots/real-browser-zoom/chrome-200-system-window.png`

Codex 已按原始分辨率查看三张截图；本结论只覆盖当前 Phase 1 合成交互原型。
