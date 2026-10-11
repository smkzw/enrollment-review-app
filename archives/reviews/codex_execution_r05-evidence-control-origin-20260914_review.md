# Codex Execution Review: r05-evidence-control-origin-20260914

## Verdict

Revise and integrate. ORM third-origin shape retained. Owner corrected migration failure atomicity before any execution; runtime migration acceptance remains deferred by user.

## Worker Outputs

Worker report read in full. E03 codebuddy/codebuddy-cli/deepseek-v4.1-flash max, session 01a09c50-902a-78f4-96f5-b7285df4d297, exit0, no fallback, empty stderr; authenticated health marker passed. Actual result modelUsage names deepseek-v4.1-flash; runner records max. Allowed models.py definition and new0025 only. Worker used native Edit/Write rather than instructed apply_patch; recorded deviation, not silently claimed compliant. Source checks and py_compile only, no staged tests or database access reported.

## Codex Independent Verification

Read entire migration and changed ORM definition plus migration env. Worker inherited raw COMMIT in finally, which could commit partial rebuild on error. Owner replaced it with explicit write transaction, precommit FK check, rollback on error, restoration of prior enforcement state. Fresh metadata per invocation avoids repeated upgrade/downgrade table-definition collisions. Downgrade refusal now runs under the same write lock as reconstruction. No migration was run; these changes need final fault-injection and roundtrip validation. Single-column FK is intentional; repository must verify rule/control/evidence/node scope from immutable publication. Constraint-name alignment remains to inspect; not a reason to rewrite existing historical migrations.

## Cleanup Decision

Retain packet/report/receipt while integration and final verification are incomplete. No cleanup, no original data changes, no acceptance of full T3.
