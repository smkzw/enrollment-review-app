Delegated mode. Continue the same bounded worker session for task `phase5-slice58r-affected-package-semantic-validation-20260826`, role `worker_01`.

Parent review accepts the need for a generic package-limited execution entry but rejects the current audit durability. Modify only `scripts/run_phase_applicability_acceptance.py` and `tests/v2/protocols/test_phase_applicability_package_selection.py`. Do not modify app contracts, artifacts, task records, source protocols, subjects, browser files, other tests, or runner-owned reports.

Observed root cause:

- package-limited execution renumbers source packages and derives new package/plan identities;
- the old-to-new mapping currently exists only in optional stdout/`--summary` output;
- the durable execution checkpoint stores only the derived plan, so a run without `--summary` cannot independently reconstruct that derived packages 1..5 came from source packages 67/78/79/80/111.

Required correction:

1. Every package-limited run must automatically persist a compact, deterministic provenance JSON inside `--state-dir`, bound to the run id. Do not require `--summary`.
2. Provenance must include a schema version; run id; source and derived plan IDs; selected source ordinals in order; source and derived plan payload hashes; and one mapping per package with source ordinal/package ID, derived ordinal/package ID, and exact owned structure-unit IDs.
3. Persist atomically with standard-library facilities. If the same run-id provenance file already exists with a different payload, fail before any semantic Provider call; identical reruns are allowed. Do not overwrite a conflicting file.
4. Prepare the durable execution checkpoint before any model call, then persist/verify provenance, then execute. Keep ordinary full-plan behavior unchanged.
5. Extend focused tests to prove: CLI build-only without `--summary` writes reloadable provenance; mapping exactly matches the execution checkpoint; identical rerun is stable; a conflicting selection using the same run id fails and leaves the first provenance/checkpoint unchanged; invalid selection writes neither checkpoint nor provenance.
6. Keep the source full plan byte-untouched. Do not run a semantic model. Return a compact updated report with exact tests and any remaining limitation.
