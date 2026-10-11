MODE=TEST

Delegated mode. 这是 Pi/oMLX `Qwen3.8-27B-oQ8e-fp16-mtp` medium 的真实浏览器连通性检查，不是正式试用、实现或会商。

仅使用浏览器打开 `http://127.0.0.1:4279/#/subjects`，视口设为 3840×2160。不要读取源码、数据库、日志、接口或终端，不要修改任何数据。请确认：

1. 页面能正常打开；
2. 页面为中文“受试者资料库”；
3. 可看到 D001-02、Ⅱ期、方案 1.0 的项目选择信息；
4. 浏览器工具真实可用，并保存一张截图到 `runs/test/phase4-d001-real-uat-20260822/r8/localqwen/screenshots/connectivity.png`。

最后只报告实际观察和 `CONNECTIVITY_PASS` 或 `CONNECTIVITY_BLOCKED`。若工具无法执行，必须报告真实传输或工具错误，不得把工具调用文字冒充结果。
