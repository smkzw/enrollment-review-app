# Codex Execution Review: phase5-slice58c1-docx-heading-recovery-20260824

## Verdict

ACCEPTED for Slice 5.8c-1 only. The DOCX structure layer now preserves custom
Chinese style metadata and effective outline levels, the coverage manifest
reconstructs source-grounded heading/table-title paths, and the phase graph no
longer leaks a phase across an unrelated sibling heading. This is not acceptance
of semantic phase-applicability resolution or D001 II control publication.

## Worker Outputs

- `worker_01` added `style_name` and inherited/direct `outline_level` extraction
  while retaining the raw style ID and old constructor compatibility.
- `worker_02` rebuilt coverage heading paths from structural outline metadata,
  kept numbered rules out of the heading stack, and attached generic adjacent
  table titles to table rows.
- `worker_03` changed phase-context propagation to structural headings, closed
  stale context at sibling/ancestor headings, and retained unresolved content as
  `UNKNOWN` instead of converting it to shared applicability.

## Manager Assessment

The selected live execution route was `codex-subagent/codex/gpt-5.6-luna:max`.
All three serial workers completed without fallback. There was no execution
manager on this route; Codex reviewed every report and the combined diff.

The worker-reported increase from 802 to 1,433 `UNKNOWN/MIXED` units is an
intentional correction of false certainty. Before this change, non-structural
text heuristics leaked a nearby III-phase context into unrelated sections.
Publication must continue to reject these unresolved units.

## Boundary

This acceptance is limited to DOCX structure extraction, coverage heading paths,
phase-context propagation, and their tests. It does not accept semantic phase
resolution, clinical control completeness, real subject review, browser UAT, or
independent tester work. The real D001 protocol was read only.

## Hermes

Hermes was not used for transport or review. The live guard selected the native
Codex subAgent route declared above; audit evidence confirms the same provider,
model, and role for all three workers with no fallback.

## Codex Independent Verification

- Focused combined regression: `53 passed`.
- Full protocol regression: `566 passed, 58 warnings` in 180.88 seconds,
  including the rendering tests that had intermittently aborted in worker runs.
- Read-only D001 II reconstruction: 3,581 structure blocks, 1,689 coverage
  units, 144 selected-phase projection blocks, and 1,433 `UNKNOWN/MIXED` units.
- D001 table 5 retains one header and 12 control rows. Every row carries the
  path `研究治疗 → 合并用药/治疗 → 禁止的合并用药/治疗 → 表 5 禁止的合并用药/治疗`
  and remains `UNKNOWN`, rather than being falsely assigned to Phase III.
- The D001 source SHA-256, size, and mtime were unchanged.
- Of 224 ambiguous units still showing `（无标题）`, 209 are body
  paragraphs and 15 are front-matter tables/list items before the first valid
  outline chapter; no table 5 control is in this set.
- `git diff --check` passed.

## Cleanup Decision

Archive runner-owned prompts, logs, reports, and manifest after execution audit
and review gate pass. Keep the Codex review, metrics, D001 research note, and
accepted checkpoint as durable evidence. Do not start the independent tester
routes in this implementation slice.
