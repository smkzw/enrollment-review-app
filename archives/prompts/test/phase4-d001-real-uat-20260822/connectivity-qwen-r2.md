MODE=TEST

Delegated mode. This is a bounded connectivity TEST pass, not implementation or acceptance.

Hard boundaries:
- Use only the exact current model and its available visual/browser tools.
- Do not modify code, configuration, databases, projects, subjects, or clinical source files.
- Do not start another Agent and do not substitute a model.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-qwen-r2.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r2/connectivity/qwen.md`.

Open `http://127.0.0.1:4263/#/subjects` in a real browser at 3840x2160. Verify all five items with actual tool evidence: local HTTP page load, rendered-page visual inspection, browser interaction, screenshot creation under `runs/test/phase4-d001-real-uat-20260822/r2/qwen/connectivity/`, and file-chooser capability by selecting this prompt file without submitting it. Confirm the D001-02 II phase project is visible and the subject list is empty. Return a concise Chinese table and end with exactly `CONNECTIVITY_OK` or `CONNECTIVITY_BLOCKED`. Do not continue into the full UAT. If a tool call cannot be executed, report the exact transport/tool failure instead of printing a tool-call request as if it ran.
