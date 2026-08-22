MODE=TEST

Delegated mode. 这是 Cursor CLI `cursor-grok-4.6-medium` 的真实浏览器连通性检查，不是正式试用、实现或会商。

仅使用浏览器打开 `http://127.0.0.1:4277/#/subjects`，视口设为 1920×1080。不要读取源码、数据库、日志、接口或终端，不要修改任何数据。请确认：

1. 页面能正常打开；
2. 页面为中文“受试者资料库”；
3. 可看到 D001-02、Ⅱ期、方案 1.0 的项目选择信息；
4. 浏览器工具真实可用，并保存一张截图到 `runs/test/phase4-d001-real-uat-20260822/r8/cursor/screenshots/connectivity.png`。

最后只报告实际观察和 `CONNECTIVITY_PASS` 或 `CONNECTIVITY_BLOCKED`。不得把工具调用文字当作浏览器执行结果。
