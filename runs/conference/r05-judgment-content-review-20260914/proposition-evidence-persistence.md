I’ll inspect the new proposition-evidence job, receipts, and registration against the existing content-job path, then report only source-proven holes and a minimal next integration step.# C03: proposition-evidence job (implemented)

Job/receipt path is a distinct `proposition_evidence` / `proposition-evidence-job/v1` / `pair_local_proposition_evidence` (`proposition_evidence_receipts.py:23-27`). Content defaults unchanged: `coverage_fields=("excerpt_coverage",)`, same contract/purpose/prompt (`judgment_content_job.py:150-165`; `judgment_content_receipts.py:32-36,138-149`). Empty pairs: summary-only, reconstruct returns empty lanes (`judgment_content_job.py:111-118`; `judgment_content_receipts.py:248-249`). Not in workflow (`prepared_review_workflow.py` has no proposition child). Intake is control-candidate only (`prepared_review_intake.py:35-36,69-74`). No clinical acceptance. Runtime/tests deferred.

---

**P1 — `verify_completed` cannot feed a method-adoption gate**

Content returns logical + artifact hashes (`judgment_content_receipts.py:413-414`). Proposition verify omits `summary_artifact_sha256` (`proposition_evidence_receipts.py:124-127`). Next consumer cannot bind `JudgmentContentAdoption`-style evidence.

Minimal: return both hashes like content.

**P1 — Input is frozen candidate pairs, not source-qualified pairs**

`load_proposition_evidence_input` keeps every non-deterministic identity pair with a bound assertion locator (`proposition_evidence_input.py:33-43`). Dual-rejected / unusable qualification pairs still call the model. A later consumer that keys only `relation_agreed` would treat un-qualified excerpts as proposition evidence.

Minimal: skip (and record) pairs that are not structurally dual-agreed; do not treat skip as “proposition false”.

**P1 — Comparison collapses `entails` and `contradicts`**

Agreed decisive relations share `status="relation_agreed"` (`proposition_evidence_comparison.py:27-33`). Easy to consume as support.

Minimal: status `entails_agreed` | `contradicts_agreed` | `unresolved` | `disagreement`; keep `scope: pair_local`.

**P1 — Prompt still ships calculator material**

Condition is stripped (`proposition_evidence.py:43-47`) but `binding_qualification_prompt_payload` still sends facts/values, `source_policies`, parent context (`binding_qualification.py:99-107`). Semantic decisive basis is not pinned to `explicit_statement` (only investigator is, `proposition_evidence.py:86-89`). `undetermined` may still use `explicit_statement` (`proposition_evidence.py:29-33`).

Minimal: drop value/time/kind from the user JSON; semantic decisive ⇒ `explicit_statement`; `undetermined` ⇒ `basis=insufficient`.

**P2 — Shared cancel copy / enqueue errors still say 判断内容** (`judgment_content_job.py:69-72,356`). Reconstruction and 429/length replay are the content sequence (`judgment_content_receipts.py:39-77,255-306`). Lanes: first-batch A/B have no `depends_on`; later steps are per-lane (`judgment_content_job.py:122-135`). Extra owned proposition jobs are not workflow children (expected set unchanged).

---

**Next integration (no new queue):** method-eval kind `pair_local_proposition_relation` + consumer vN. Authorization optional on the control qualification job, like content. Consumer may record agreed **pair-local** `entails`/`contradicts` only for source-usable pair_ids. It must **not** clear `determination_mode_*`, **not** set `observation_scope_verified`, **not** map one excerpt onto `any`/`all`/`single` completeness, **not** emit IE/eligibility. Combiner stays UNKNOWN with an explicit pair-local reason until a later, separately approved observation-policy consumer. Do not auto-enqueue from the parent workflow yet.
