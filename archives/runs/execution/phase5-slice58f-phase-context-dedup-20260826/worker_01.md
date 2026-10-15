# Execution Output: phase5-slice58f-phase-context-dedup-20260826 - worker_01

## Boundary And Context Check

- Read only the declared execution context and plan first.
- Audited the phase-applicability adapter, contracts, hydration logic, focused tests, and existing D001 package-32 probe.
- Audit-only; no source, test, production, or generated files were modified.
- No external calls, package installation, or clinical/regulatory acceptance performed.

## Work Performed

Current duplication is in `build_phase_applicability_agent_prompt()`:

- `target_units` and `context_units` render every unit once.
- Every `context_packet` additionally renders full `source_members`.
- `heading_chain` covers all units, while the other five packet kinds overlap those indexes.

Evidence:

- `app/agents/phase_applicability.py:1042-1059` renders duplicated `source_members`.
- `app/agents/phase_applicability.py:1070-1088` already renders the complete target/context unit projection.
- `PhaseApplicabilityContextPacket` itself contains only `kind`, `source_unit_indexes`, and `source_span_indexes` at `app/agents/phase_applicability.py:257-268`.

Minimal safe compression:

```json
"context_packets": [
  {
    "packet_index": 0,
    "kind": "heading_chain",
    "source_unit_indexes": [0, 1, 2],
    "source_span_indexes": [0, 1, 2]
  }
]
```

Remove only `source_members`. Keep all full unit data in `target_units` and `context_units`, and retain every packet kind and both index arrays.

This preserves:

- source closure: `PhaseApplicabilityAgentInput.validate_context_closure()` still validates packet unit/span indexes at `app/agents/phase_applicability.py:475-508`;
- package identity and ownership: unchanged `PhaseApplicabilityFrozenPackage`;
- hydration identity: hydration resolves indexes against `package.all_units` and generates system IDs at `app/protocols/phase_applicability.py:178-230`;
- Chinese clinical semantic contract: retain all six packet roles and phase-disposition rules;
- target/context separation: packet indexes remain read-only references.

The prompt contract should replace `source_member` wording with explicit global-index wording: packet `source_unit_indexes` reference the `unit_index` values in `target_units + context_units`, and packet span indexes must be drawn from the cited units’ displayed span indexes.

## Artifacts And Evidence

No artifacts were changed.

Baseline focused tests:

- `42 passed in 0.05s`
- Command covered:
  - `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py`
  - `tests/v2/protocols/test_phase_applicability_contract.py`

Synthetic fixture measurement:

- 3 total units, 6 packets, 10 packet-member renderings.
- Each unit appeared 4–5 times in the full projection.
- Current prompt: 11,325 characters.
- Packet-index-only projection: 7,570 characters.
- Reduction: 3,755 characters / 33.16%.

Existing D001 package-32 probe measurement:

- Input: `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/probe-package32-slice58e/agent-input.json`
- SHA-256: `78d5cbee76937bf0fdb7cb7af4eaa2b164459bf9f19d2d0cfc45fabb68e961a0`
- 12 owned units, 192 context units, 204 total units, 6 packets.
- Current packet rendering: 585 full packet-member occurrences.
- Current prompt: 420,401 characters.
- Simulated packet-index-only prompt: 117,450 characters.
- Reduction: 302,951 characters / 72.06%.
- The current rendering exceeds the runner’s 240,000-character input ceiling; the simulated compact form is below it.

## Commands And Observations

- `rg` over `app`, `tests`, `contracts`, and `docs` located the renderer, packet contract, validator, and hydration paths.
- Read relevant source with `sed`/`nl`.
- Ran focused pytest with cache disabled:
  - `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider ...`
  - Result: `42 passed`.
- Ran read-only Python measurements against the synthetic fixture and D001 package-32 probe.
- Verified global unit-index and packet source-span closure on the D001 projection.

## Blockers Or Missing Environment

- No blocker for the assigned audit.
- Package-32 evidence is from the prior `slice58e` probe; it is quantitative baseline evidence, not post-change acceptance.
- The worktree already contained extensive unrelated modifications and untracked artifacts; none were changed.

## Rerun Requests Or Next Step

1. Implement only packet-index-only prompt rendering in `app/agents/phase_applicability.py`.
2. Update the source-reference contract text from `source_member` to global `unit_index`/span-index semantics.
3. Consider bumping `PHASE_APPLICABILITY_AGENT_PROMPT_VERSION` to `v3`; the prompt hash includes the version and contract, while input/wire/domain versions should remain unchanged.
4. Update the projection test to assert:
   - every unit is rendered once;
   - packets contain no `source_members`;
   - packet unit/span indexes remain closed and ordered.
5. Rebuild and measure real D001 package 32, then rerun hydration/gate and semantic regressions.
