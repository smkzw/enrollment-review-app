# C03 read-only source-bound review of candidate probe

Continue primary zcode/GLM-5.3:max same session, no fallback. Read-only independent adviser, no writes except requested report. No network/install/credentials/local services/other agents. You MAY inspect ONLY the listed frozen clinical images inside this workspace, not originals elsewhere or clinical databases. Use image-capable reading if available, explicitly report if images cannot actually be seen; do not claim visual review from filename/text alone. Engineering review is not clinical approval; same-family independence limited.

Sources:
- artifacts/phase55-takeover/20260910/judgment-source-probe-plan.md (pre-call criteria, not authority over original)
- judgment-source-probe-page7/source.png, input.json and attempt/*.response.json
- judgment-source-probe-page9/source.png, input.json and attempt/*.response.json (v2 failed relevance negative)
- judgment-source-probe-v3-page9/source.png and attempt/*.response.json
- judgment-source-probe-page8/source.png and attempt/*.response.json (v3)
- judgment-source-probe-v3-report1-sige/source.png, input.json and attempt/*.response.json
All paths share artifacts/phase55-takeover/20260910/. Do not read model reasoning/private traces. PageCompletion text is the final model artifact to compare with source. Do not edit historical responses.

Current code read app/llm/judgment_search_reader.py (v3: complete single JSON fence allowed without changing content; strict complete outer JSON and duplicate keys rejected; stop mandatory; raw preserved; conditional ambiguity requires relevant substantive content) and app/services/judgment_search_source.py (published parent/child/requirement selected-path exact consistency, actual workflow membership, template semantics; procedure-origin explicitly unsupported). Source-backed target supplies only selected context, not whole protocol. Candidate reader and probe are not clinical production acceptance or full24page coverage. Known real results: preserve your own source judgment, not the owner's claims.

Review focused questions:
1. Are v3 negatives appropriately excluded without losing relevant statement? Does report handwritten fragment require preserving leading uncertain letters and how should uncertain transcription be represented WITHOUT supplying a guessed correct answer or hardcoded patient patch? Difference in excerpt granularity is not automatic clinical agreement.
2. BoundingBox currently lacks coordinate convention. Check actual returned box against image; do not infer normalized1000/pixels as proven. Recommend minimal change that preserves raw bbox but prevents unverified location from being displayed as precise evidence. Do not mechanically rescale from a guess.
3. Does the proposed target/source preparation miss a material deterministic consistency check? Recommend only concrete verified gaps, not redesign entire project.
4. Next integration should NOT do N requirements times24pages times2models blindly. Give bounded per-page grouped-target candidate design preserving each required target's explicit status, relevance/ambiguity and failure/omission, no automatic inference of clinical absence. Explicitly reject prior suggestion that assigning excerpts to the wrong target is harmless merely because candidate-only. Do not pick an arbitrary group size as accepted threshold.

Run current reader/source/coverage tests if helpful; report exact test paths/results. End with current defects, concrete fixes, known unimplemented boundaries, and what evidence is needed before reporting confirmed lack of investigator judgment. No full clinical acceptance, no user confirmation requirement merely for truly missing judgment once independently established. No forced modeling assumptions about author/date/context.time_text.
