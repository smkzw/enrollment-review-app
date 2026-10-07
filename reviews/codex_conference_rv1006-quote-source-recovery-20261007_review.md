# Source recovery boundary review

Date: 2026-10-07

## Evidence and Scope

Frozen source: 9d4f94c4. Approved C03 CodeBuddy/codebuddy-cli/deepseek-v4.1-flash/max; fresh session 01a1160f-39c6-7882-bd4c-2cf8f5f2ec45, 200.521s, exit0, no fallback. Fourteen source read/search calls; no clinical originals, private answers, environment, databases, edits or test execution. Parent waited for completion under the 120-minute policy. This is engineering advice, not medical approval.

## Findings and Owner Decision

The existing quote-correction producer omitted its typed trigger; the replay accepted scope corrections only. Identity equality alone cannot establish that a saved interpretation came from the actual model answer. Owner implemented explicit quote triggers and replay of at most two witnessed corrections under unchanged source/base prompt/Schema/route. Raw hashes, actual target, correction contract, final snapshot and current source validation must agree. More than two corrections remain refresh-only; historical missing trigger details are never reconstructed.

The same-component invalid semantic-wire branch now uses that same proof before dropping the wire, target review, coverage, alignment and session. The malformed-wire structural check and source/identity checks remain outside this fallback. Without proof, it preserves the prior hard failure. Preflight and actual execution independently recompute the proof. A fresh author result must pass the ordinary gates and consumers; source replay does not adopt rules.

The briefing used an incorrect hypothetical field shape. Actual SourceQuoteCorrection fields are version, structure_unit_id, corrected_quote and unresolved; implementation uses these, not quoted_text/source_span_ids. The adviser inferred uncertainty about change authorization; the owner's latest user instruction already authorizes in-scope implementation, so that inference was not adopted. Advice recommending identity-only reuse was not adopted.

## Verification Boundary

The quote-replay five-module window passed 1204 tests in60.34s/exit0 before the same-component addition. An earlier focused window had51 passed/1 failed due to the owner's incorrect expected diagnostic field values; those expectations were aligned to the actual typed issue without changing validation. One invalid test-module path exited4 before any test execution. The subsequent same-component diagnostic had13 passed/1 failed because the owner removed its injected gate between preflight and execution; this correctly produced a proof mismatch. The fault injection was kept consistent across both boundaries and separated from the new author's valid output.

Final connected checks and real-product outcomes are recorded in implement.md and review_index.json. Counts here are version-specific, not cumulative and not proof of complete clinical acceptance. The reviewer did not inspect the final patch; owner integration and consumer checks provide the final software evidence.

## Unresolved

The old real2a24a4c source has missing quote-trigger receipts and remains non-reusable. No old failed job becomes completed. Full joint requirements adoption and the current-node eligibility report remain unproved; claims_complete=false.
