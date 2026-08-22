MODE=TEST

Delegated mode. Continue the same bounded Qwen connectivity TEST session. The previous output ended inside an unexecuted screenshot-copy tool call and is incomplete.

Hard boundaries:
- Continue only the existing Qwen test session and use its browser/visual tools.
- Do not edit code, configuration, project data, or clinical source files.
- Do not create another subject or start another Agent.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-qwen-r3-recovery.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r3/connectivity/qwen-recovery.md`.

The disposable subject `CONN-R3-QWEN-DISPOSABLE` already exists. Continue from it: enter its evidence workbench, open `建立完整资料快照`, use the real file chooser to select this recovery prompt file, do not confirm the upload, and cancel the unconfirmed preview if the UI offers that action. Save the missing evidence-workspace screenshot plus a final-state screenshot under `runs/test/phase4-d001-real-uat-20260822/r3/qwen/connectivity/`; verify both files actually exist. The controller will rebuild the isolated database before full UAT, so do not attempt to delete a subject carrying immutable preview history.

Return a concise Chinese table covering page load, visual rendering, interaction, actual file chooser, preview cancellation, screenshots on disk, and exact runtime model. End exactly with `CONNECTIVITY_OK` only if browser, screenshot, and file-chooser checks pass; otherwise end exactly with `CONNECTIVITY_BLOCKED`.
