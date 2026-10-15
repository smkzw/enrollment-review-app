# Same-session bounded correction check

Continue C03 session 0c49f351-2835-4001-9104-ebb164d6758b with the same read-only
boundaries. No clinical/env/tmp/DB reads, writes, tests, network or delegation.

Owner adopted the residual-action objection, not source equality as semantic
proof. The helper now requires exactly one temporal cue in both the quoted
source and atom statement, requires every temporal clause to be an exemption,
rejects routine actions unless their start is inside an existing exemption cue
(e.g. the need in need-not), and conservatively refuses coordinated clauses.
Shared exemption regex, schemas, author and consumers are unchanged.

Read only the current helper in app/protocols/protocol_control_gate.py and the
new test_result_validity_exemption_keeps_independent_action_or_window in the
original test module. Synthetic tests cover added mandatory/timed actions,
same-clause alternatives, a separate recording action and statement-only
additions. This shortcut is not a generic source-coverage proof or a clinical
adoption permission. Complex coordination falls through the old check; no
window is inferred. Owner connected window48pass is software evidence only.

Give one compact decision on closure of your actual counterexamples, any new
concrete release blocker, and remaining limits. No repeat whole audit. State
the checked source version as base83d8ee59 plus current two-file patch.
Return report; runner persists it. No medical approval.
