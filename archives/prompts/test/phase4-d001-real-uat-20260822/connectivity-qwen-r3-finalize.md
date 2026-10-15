MODE=TEST

Delegated mode. This is the final same-session completion pass for the bounded Qwen connectivity TEST.

Hard boundaries:
- Continue only the existing Qwen session and current disposable subject.
- Do not edit code, configuration, project data, or clinical source files.
- Do not create another subject, start another Agent, or substitute a model.

Read these files only:
- `prompts/test/phase4-d001-real-uat-20260822/connectivity-qwen-r3-finalize.md`

Runner-managed output path: `runs/test/phase4-d001-real-uat-20260822/r3/connectivity/qwen-finalize.md`.

Your previous two outputs stopped inside literal `<tool_calls>` text instead of completing the requested browser action. Do not print tool-call markup or browser code in the final answer. Use the available browser/file-chooser tools now to select this finalize prompt file in `建立完整资料快照` for subject `CONN-R3-QWEN-DISPOSABLE`, without confirming upload; cancel the preview if available. Save and verify a final screenshot under `runs/test/phase4-d001-real-uat-20260822/r3/qwen/connectivity/`. Then stop using tools and return only a concise Chinese results table. End exactly with `CONNECTIVITY_OK` only if the actual file chooser and screenshot-on-disk checks completed; otherwise end exactly with `CONNECTIVITY_BLOCKED` and state the concrete harness failure.
