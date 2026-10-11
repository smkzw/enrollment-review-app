MODE=TEST

Delegated mode. This is a bounded connectivity TEST pass, not implementation or acceptance.

Hard boundaries:
- Use only the exact current model and its available visual/browser tools.
- Do not modify code, configuration, projects, or clinical source files. You may create and then delete one disposable empty subject only as described below.
- Do not start another Agent and do not substitute a model.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-minimax-r3.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r3/connectivity/minimax.md`.

Open `http://127.0.0.1:4262/#/subjects` in a real browser at 2560x1440. Verify actual local page load, visual rendering, interaction, screenshot creation under `runs/test/phase4-d001-real-uat-20260822/r3/minimax/connectivity/`, and file-chooser capability by selecting this prompt file without submitting it. Confirm project D001-02 II is visible and the subject list is initially empty. Because the file chooser exists only inside a subject evidence workspace, you may create one clearly named disposable empty subject solely for this connectivity check; delete it through the UI before finishing and confirm the subject list is empty again. Screenshot files must actually exist on disk before you report success. Do not edit application code or clinical source files. Return a concise Chinese table and end exactly with `CONNECTIVITY_OK` or `CONNECTIVITY_BLOCKED`.
