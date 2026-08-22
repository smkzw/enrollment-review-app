MODE=TEST

Delegated mode. Continue the same bounded connectivity TEST session. Do not implement or edit application code.

Hard boundaries:
- Continue only the existing MiniMax test session and use its browser/visual tools.
- Do not edit code, configuration, project data, or clinical source files.
- Do not create another subject or start another Agent.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-minimax-r3-recovery.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r3/connectivity/minimax-recovery.md`.

The previous pass selected a file and left a persisted, unconfirmed upload preview on subject `CONNECTIVITY_TEST_DELETE_ME`. The evidence workbench screenshot visibly contains the button `取消预览`. Return to that subject's evidence workbench, cancel the unconfirmed preview through the UI, then return to the subject list and delete the disposable subject through the UI. Confirm the D001-02 II subject list is empty. Save one final screenshot under `runs/test/phase4-d001-real-uat-20260822/r3/minimax/connectivity/` and verify it exists on disk. Do not create another subject and do not modify source files.

Return a concise Chinese table and end exactly with `CONNECTIVITY_OK` only if the preview is canceled, the subject is deleted, the list is empty, and the final screenshot exists; otherwise end exactly with `CONNECTIVITY_BLOCKED`.
