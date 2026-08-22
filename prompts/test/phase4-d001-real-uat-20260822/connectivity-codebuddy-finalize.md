MODE=TEST

Delegated mode. This is the final same-session completion pass for CodeBuddy connectivity.

Hard boundaries:
- Do not modify application, database, source, configuration, or clinical files.
- Do not start another Agent or substitute another model.
- Do not repeat completed HTTP/browser/screenshot checks.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-codebuddy-finalize.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/connectivity/codebuddy-final.md`.

已验证 `4261` 页面加载、浏览器交互和真实截图。现在只做两件事：使用当前页面的文件选择能力选择本提示文件本身但不要提交；随后立即输出五项连通性总结和 `CONNECTIVITY_OK` 或 `CONNECTIVITY_BLOCKED`。不要继续探索，不要写过程叙述。
