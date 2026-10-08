# Owner Decision: saved source-question recovery

Actual C03: Grok/grok-build/grok-4.7/high, session 17ee3ff0-3b08-4b97-9418-e6f14ec49e9d; one round 958.163s, exit0/no fallback. Frozen f205bf54 and proposal only, not final patch or clinical acceptance.

Accepted: removing the saved-wire guard alone is insufficient. Persist and charge actual prior question attempts; do not reread a witnessed unchanged uncertainty; preserve the saved wire on failure; bind every reused target decision, including old covered/background decisions, to the original source identity. Changed source triggers fresh review for that item.

Implemented in existing Runner and execution checkpoints, not a new queue/proof store. Private raw proposal history is excluded from public RunResult and explicitly restored. Damaged history rejects before a request. Full source validation and downstream adoption unchanged.

Rejected: another user approval for ordinary test calls (already authorized), blanket prohibition of partial recovery, and an inference that last_checkpoint overwrites all history without reading JobStore. No global prompt/compiler upgrade or clinical gate relaxation.

Evidence: first connected window1024pass/5fail; four fixture excerpts and an empty-history no-op issue corrected. Final affected recovery-family53pass/339deselected/25.05s, exit0. Final whole three-module rerun not performed. Real read-only preflight18reusable/1partial/71refresh; four prior question calls retained, zero calls/writes and database hash unchanged. Next legally created isolated Job uses committed source snapshot; no publication/signature claimed.
