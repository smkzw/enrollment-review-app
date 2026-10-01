# 本包检查，不是产品验收

已执行：轻量handoff索引检查器18个合成正反例，Python语法检查，未填模板的显式结构检查，以及本包相对链接／JSON／文件完整性检查。

命令：`python -m unittest -v test_check_handoff`；`python check_handoff.py ../templates/review_index.template.json --allow-template`。执行目录为本包tools。

原日志：`handoff_checker_tests.txt`。模板检查：`template_structure_check.json`。这些结果不涉及实际产品仓库、真实模型、临床材料、HTTP服务或浏览器。18项检查不能并入产品测试总数。

索引检查器不验证证据内容、实际访问权限、数据脱敏或临床正确性，也不自动读取引用文件。
