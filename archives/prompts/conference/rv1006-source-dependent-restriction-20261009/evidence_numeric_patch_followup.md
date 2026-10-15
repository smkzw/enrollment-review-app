# Same-session bounded engineering review: numeric field splice

Read-only; no source edits, tests, shell, network, credentials, clinical artifacts or delegation. Return your report to the runner; do not write its output path. Same session/approved route as the previous two reviews. Same model family means procedural separation only, not clinical or model-independent approval.

Frozen baseline is b6fb9016 plus exactly these owner patches (owner verified SHA256):
- app/agents/protocol_control_deconstructor.py 2e955d8a643689465cba0cb0483cd48b29685261eb7a55bdb1109df2a2ec201d
- app/agents/protocol_control_agent_transport.py f160a07528b2a1c4829dfa6fa850fa9e24fd58d8c98d0249a353d5c68b8162a1
- app/services/protocol_control_execution.py 176c70b7597579717e36cc71af741ebe62518d66a4c869039bb78b6fc682a2a0
- tests/v2/protocols/test_slice58c_control_deconstructor.py e29154dc03ddf6f08c55a45d5a008d4666f7a75efcb1e81890cd6004ba27f0e5
- tests/v2/protocols/test_protocol_control_agent_transport.py 440016f3b39e4ce2da04fcc29c1ebc06c9c607b305251cfff43d0cedc1c49c2a
- tests/v2/services/test_protocol_control_execution.py c4f039781a13b2b30619f8f18f11f1bdc41fd4c2963c4d53c504266981068979

Actual run stopped: old 43 successes reused without models; seven new calls. Negative increment decisions now actually rechecked. The final failure was a known numeric atom repair: predicate.source_clause contained the full parent sentence while frozen evaluation.source_excerpts contained only the local numeric sentence. Existing containment validation rejected this correctly. No truncation/transport failure. No new clinical adoption.

Check this minimal response-contract change, not the whole platform:
1. Existing transport now has continue_numeric_predicate using the same local one-request recovery boundary, logical session and budget. It sends an evaluation_patch schema with exactly determination_mode/operation/predicate/operand_attribute. Existing continue_atom stays unchanged. Prompt freezes the entire original atom for context but asks only for four fields, explicitly limits numeric predicate quotations to existing evaluation excerpts. No machine shortening/replacement of model citations.
2. Merge accepts that patch only in numeric_predicate_only mode, rejects extra/missing keys, deep-copies the original atom and changes only those four fields. Runs existing atom and whole-wire validation. Current legacy full-atom recovery replies remain supported; do not call them approved. Downstream source-candidate alignment still checks numeric meaning; a wrong value that passes structure must fail there. Source policy/statement/time/proposition/siblings remain frozen.
3. Caller prefers the new method only when available, otherwise uses original complete-atom contract (for legacy transports). Same one-path attempt/budget accounting; failure returns unchanged original wire. New patch identity is in validator version, not author/compiler identity; actual request schema/prompt and response hashes remain in existing receipts. Historical source hashes/approvals not rewritten. Is this separation correct or must some other production identity change for safe recovery? Give exact caller evidence, not a blanket version bump that forces healthy successful source reads.
4. Newly extended runner tests cover valid patch, altered threshold, parent-length quote and unauthorized proposition. Transport checks text/json_object/json_schema all deliver matching schema and preserve session history. Owner ran 18 affected tests, exit0; you may read but may not claim you ran them.

Read complete affected definitions plus immediate callers and ControlAtomEvaluationSpec.validate source logic (app/domain/contracts/control_evaluation_spec.py). Challenge source/scope/identity and consumer behavior; distinguish code defects, test gaps and unsupported speculation. Return concise findings by severity with exact functions, a concrete counterexample, smallest remedy, and evidence limitations. Do not approve clinical semantics or suggest more full protocol retries. No final acceptance.
