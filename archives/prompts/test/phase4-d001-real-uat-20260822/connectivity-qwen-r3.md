MODE=TEST

Delegated mode. This is a bounded connectivity TEST pass, not implementation or acceptance.

Hard boundaries:
- Use only the exact current model and its available visual/browser tools.
- Do not modify code, configuration, projects, or clinical source files. You may create and then delete one disposable empty subject only as described below.
- Do not start another Agent and do not substitute a model.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-qwen-r3.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r3/connectivity/qwen.md`.

Open `http://127.0.0.1:4263/#/subjects` in a real browser at 3840x2160. Verify actual local page load, visual rendering, interaction, screenshot creation under `runs/test/phase4-d001-real-uat-20260822/r3/qwen/connectivity/`, and file-chooser capability by selecting this prompt file without confirming the upload. Confirm project D001-02 II is visible and the subject list is initially empty. Because the file chooser exists only inside a subject evidence workspace, create one clearly named disposable subject solely for this connectivity check, select this prompt file, then cancel the unconfirmed preview if the UI offers that action. Do not require deletion after a preview has created immutable audit history; the controller will rebuild the isolated database before full UAT. Screenshot files must actually exist on disk before you report success. Do not edit application code or clinical source files. Return a concise Chinese table and end exactly with `CONNECTIVITY_OK` if the browser, screenshot and file-chooser checks pass, otherwise `CONNECTIVITY_BLOCKED`. If a tool call fails, report the actual transport/tool failure.
