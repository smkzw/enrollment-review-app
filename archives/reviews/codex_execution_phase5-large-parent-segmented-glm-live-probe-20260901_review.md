# Codex Execution Review: phase5-large-parent-segmented-glm-live-probe-20260901

## Verdict

**Rerun required.** The packet is accepted as evidence for a failed live probe, not as acceptance of segmented GLM deconstruction. The production path did not meet the objective: one of four segments timed out, no deterministic merge or full publication gate ran, and the GLM transport does not advertise the capability currently required to enter the segmentation path.

## Worker Outputs

- `worker_01`: read-only preflight confirmed the frozen EX-06 package is unchanged and plans to four segments `[3,3,3,2]`; it also found that the existing probe omits `transport_factory` and that the parent application `.env` must be injected into the isolated process.
- `worker_02`: ran the pinned `zhipu-coding-plan/glm-5.3-flash:high` probe with concurrency two. An accidental whole-parent control proved that `uses_compact_wire_contract=False` bypasses segmentation. The authoritative segmented run completed three segments, timed out segment 01 at about 600 seconds, hard-stopped, and used no whole-parent or cross-provider fallback.
- `worker_03`: independently compared the frozen input, whole-parent baseline, partial segment outputs, gates, timing, and production code. It confirmed that a complete quality comparison is impossible without a merged segmented draft and found no D001/SAR-specific literals in the production planner or runner.

## Manager Assessment

No separate manager was declared for this finite-code packet. Codex disposition: retain both the failed segmented run and the accidental whole-parent run as diagnostic evidence, but label only `run-segmented` as the authoritative segmented attempt. Do not treat `summary.json`'s process-level `completed` value as business success; `segmentation-failure.json` and `runner-result.json` are authoritative.

## Codex Independent Verification

- Frozen package SHA remained `c7c038e38cdf3ce887bab8f8dc2ed8cc57b1cc100d7c8853be1dd118178e3b67`; prior baseline hashes remained unchanged.
- Planner preflight recorded four segments and `[3,3,3,2]` body-unit packing before network access.
- Every authoritative live call recorded `glm-5.3-flash`; concurrency was bounded at two; no MTPLX or DeepSeek fallback ran.
- Authoritative run: 7 calls, 1213.19 seconds, three successful segments, one 600.154-second timeout, no merged candidate, no hydrated draft, and no full gate.
- Whole-parent baseline: 803.21 seconds and a complete draft; the same unchanged draft later passed the repaired generic gate. Therefore the segmented approach has not yet shown either a speed or quality advantage.
- Shared production files reviewed contain no project, disease, drug, score, clause-code, or time-point branching for this segmentation behavior. The EX-06 literal exists only in the isolated probe pin.

Required remediation is generic: decouple segmentability from compact-wire support, persist successful segment results by deterministic identity, resume only missing/failed segments, classify timeout distinctly from schema failure, and rerun merge plus full gate. A blind full four-segment replay is not accepted because it would discard three valid completed segments and repeat expensive calls.

## Boundary Verification

- The frozen clinical package, prior whole-parent probe, failed SAR job, and paused D001 task remained read-only.
- No secret value was written to reports or artifacts; the existing parent `.env` was injected only into the isolated live process.
- Hermes was not used as a transport. The governed workers ran on the declared Pi/Cursor route, while the product-under-test called the explicitly pinned Coding Plan GLM endpoint.

## Cleanup Decision

Archive the governed process files after audit, but retain the isolated probe artifact and checkpoint as failed-run evidence. No clinical source, old probe, failed SAR job, or paused D001 task may be cleaned or resumed.
