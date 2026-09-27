# CodeCare AI: To-Do

Source of truth: `DESIGN.md`. Rules for working: `CLAUDE.md`.
Each milestone ends with its own passing check. Don't start a milestone until the one before it passes.

---

## Plan for 2026-09-28 (after 07:30 CDT, owner message starts it)

Order (owner, 2026-09-27). Stop and report after step 1.

1. [ ] **M4 eval** on `m4-rules`: budget check; re-record the worked-example fixtures (2 calls); run (a) `--extract-prompt extract_v1`, 20 notes, new run id, outputs saved; run (b) `extract_v2`, 20 notes, outputs saved (if both don't fit, (a) today and (b) the next day); replay both; report all results against M3. **Stop for approval.**
2. [ ] Merge M4, then M7, into `main`; fix conflicts (expected: `DESIGN.md`, `tasks/todo.md`).
3. [ ] Rebase `m8-frontend` onto `main`, `npm run gen:types`, add the "added by rule" badge (`Suggestion.added_by_rule`), rerun e2e, merge into `main`.
4. [ ] **Write README.md on `main`** once steps 1-3 are done and all tests pass on `main`, using the owner's README prompt below, with the M4 numbers.
5. [ ] Push.

Why the README waits (2026-09-27): no single branch had every feature (replay and the R9 gap on `m4-rules`; frontend, e2e, fake LLM, review API on `m8-frontend`), and the M4 eval numbers did not exist yet.

### README prompt (owner, verbatim)

> Write README.md for the repo root. The audience is engineers and hiring managers at a company reviewing this project. They should understand what it does, why it's built this way, and how well it works in under 3 minutes, and be able to run it in under 15.
>
> Rules:
> - Plain, direct language. No marketing words ("revolutionary", "seamless", "cutting-edge"), no emojis, no em dashes.
> - Every number must come from eval/results/ or tasks/todo.md reviews. Never estimate or round up. If a number isn't available yet, write TODO and tell me.
> - Every command in the README must actually work. Run each one in a clean shell before finishing.
> - Keep it under about 250 lines. Link to DESIGN.md for detail instead of repeating it.
>
> Sections, in this order:
>
> 1. Title and one line: "CodeCare AI: an explainable ICD-10-CM coding copilot for outpatient notes."
>    Right under it, the disclaimer: synthetic data only, not reviewed by a certified coder, not for real clinical or billing use.
>
> 2. Screenshot of the review page (note on the left with evidence highlighted, code cards on the right). Take it with Playwright against the fake LLM and save it to docs/review-page.png.
>
> 3. The problem (3 or 4 sentences): coding depends on reading notes by hand, codes come from what's documented, mistakes cause denials and rework.
>
> 4. How it works:
>    - The core rule in one line: the LLM reads, plain code checks.
>    - A Mermaid flowchart of the pipeline: note → extract facts (LLM) → find candidates (code tables) → pick codes (LLM, candidates only) → rules R1 to R14 → gaps → coder review.
>    - One line per step on what it does.
>
> 5. Worked example: the diabetes + CKD note, the codes returned (E11.22, N18.30), the evidence sentence, the rule that linked them, and the documentation gap it raised.
>
> 6. Results: the latest 20-note eval, pipeline vs LLM-only baseline, same model. Columns: precision, recall, invented rate, invalid rate, unsupported rate, gap recall. Add one line on how the gold notes were made and checked, and one line saying the gold set is small and synthetic.
>
> 7. Key design decisions: 5 or 6 short bullets, each "chose X over Y because Z". Cover: LLM picks only from retrieved candidates; rules as tested code, not prompts; deterministic eval instead of LLM-as-judge; saved LLM outputs with replay; code set chosen by visit date; open-weight model via an OpenAI-compatible API.
>
> 8. Tech stack: one short table.
>
> 9. Run it locally:
>    - Prerequisites (Python 3.12, Node, Docker).
>    - Start Postgres, run migrations, load the FY2027 code set (say it takes about 30 minutes because of embeddings).
>    - The .env settings (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL) with a link to get a Groq key. Never include a real key.
>    - Start the backend and frontend.
>    - Option to run with the fake LLM, no API key needed.
>
> 10. Tests and evaluation: commands for unit tests, integration tests, e2e, a smoke eval, and replay. One line each.
>
> 11. Project structure: top-level folders only, one line each.
>
> 12. Limitations and future work: honest and short. Include the free-tier rate limit, small synthetic gold set, no certified coder review, the hypertension exception limit, CPT/E/M status, and anything in DESIGN.md §12.
>
> 13. Data sources: CMS ICD-10-CM files and Official Guidelines (public), NCCI edits, and a note that CPT descriptions are our own wording because the AMA's are licensed.
>
> When done, show me the rendered README section by section, list any TODOs, and confirm every command was run. Commit to the current branch but don't push.

---

## Current task: Codex review fixes on m4-rules (owner, 2026-09-27)

Owner-directed fixes before tomorrow's M4 eval; no LLM calls. Each fix gets a regression test that feeds the wrong-but-valid code and fails without the fix. Findings 16-18 skipped (owner). Supersedes parts of steps 5, 9 and 23 of the M4 plan (combination presence and stage come from facts only).

1. [x] Combination codes need documented parts: HTN/CKD/HF/diabetes presence only from active facts, never from a selected I12/I13/E1x.22 code. A selected E1x.22, I11.x, I12.x or I13.x whose conditions are not documented is kept as `not_suggested` (rule result `fail`). n007: stage from the CKD fact, not the selected code.
2. [x] Stage reconciliation both ways: every selected N18 code is replaced by the documented stage's code (up or down; N18.9 when none); stage 5 and ESRD both documented -> N18.6.
3. [x] Exclusive variants from documented facts: I12.9 <-> I12.0, I13.0 <-> I13.2, I11.9 -> I11.0 when heart failure is documented; never both variants.
4. [x] R7: E10 or E13 without a documented type -> E11 counterpart.
5. [x] R2: add E1x.22 next to E1x.21/E1x.29 when CKD is documented; replace only the uncomplicated E1x.9.
6. [x] Selection evidence must be a subset of its fact's evidence; otherwise dropped and counted as a model error.
7. [x] R8: added Z79 codes cite the union of the diabetes and medication facts.
8. [x] Eval: rename the old check to evidence-reference validity; add a rule-based support check (cited sentences name the condition via description, Index terms or abbreviations; not negated; carry the needed details, e.g. "3b" for N18.32; code comes from an active fact); 20-30 hand-labeled pairs test it.
9. [x] Eval coverage: a run with a missing or failed gold note is "incomplete" and claims no pass/fail; runs store a hash per gold note; replay refuses if a gold note changed.
10. [x] Full-pipeline test: suspected heart failure plus a documented symptom -> no I50 code, symptom code present.
11. [ ] m8-frontend: review buttons disabled while re-analysis runs; e2e suggestions cite different sentences so the highlight test can fail.

### Review (2026-09-27)

**Done on `m4-rules`** (no LLM calls): items 1-10 above. Rules now read conditions and stage only from active facts (`rules/common.py` `Conditions`, `documented_ckd_codes`); `settle_variant` leaves one of I12.0/I12.9, I13.0/I13.10/I13.11/I13.2, I11.0/I11.9; R9 reconciles N18 both ways; R7 swaps untyped E10/E13 for E11 (counterparts preloaded); R2 replaces only E1x.9; R8 cites diabetes + medication facts; selection evidence must be within its fact's evidence. Eval: `evidence_ref_invalid_rate` (the old check) plus `unsupported_rate` from `eval/support.py`; runs store gold hashes, reports mark INCOMPLETE and judge nothing, replay refuses changed gold. Fixture code table gained R06.02.

**Verified:** 204 unit + 39 of 40 integration tests pass; ruff, ruff format, mypy clean. The only failure is still `test_worked_example_from_recorded_llm` (waits on re-recording tomorrow). Every fix's new test was run against the pre-fix rules in a throwaway worktree: all 16 finding tests for items 1-5, the R8 evidence test and the pipeline evidence-subset test fail there; the one guard test (typed E10 stays E10) passes on both, as intended. `rescore.py` gates pass; the two M3 10-note runs now show INCOMPLETE (no stored scope, so they are scored against all 20 notes).

**Open:** support checker is a deterministic proxy (word matching over descriptions and Index paths), not a coder; thresholds for the two evidence metrics kept at <= 5% pending owner review.

---

## Current task: M4 detailed plan (approved 2026-09-27)

Touches DESIGN §3.4 (R2-R12), §4.1 step 6 (retrieval), §4.4 (what counts as `model_errors`), §5.1 (confidence bands), §5.2 (`CodeLookup`, rule contract), §9 (smoke eval before/after). Milestone M4. Baseline to beat: M3 20-note pipeline run `2026-09-27-n20-pipeline-openai_gpt-oss-120b` (precision 0.78, recall 0.82, gap recall 0.00, invented 0, invalid 0).

Every citation below was checked against `data/raw/guidelines-fy2027.txt` (FY2027 PDF text) on 2026-09-27; Index entries against `icd10cm_index_2027.xml`.

### Approach

Rules work on **codes the LLM already selected, plus fact status and details**. The LLM still only extracts and picks from candidates. Rules can do three things, all deterministic:
- **add** a code (combination codes, Z79.x). It must come from `CodeLookup` for the visit's code set, carries `added_by_rule` (new `Suggestion` field), and its `fact_ids` and evidence are the union of the **facts** that triggered it. This is how E11.22, I12.x, I11.0 and I13.x appear when the LLM picked E11.9 / I10. **Every added code must pass R1**: R1 runs first (LLM picks) and again last (codes added by rules); a test proves an added code that is absent, non-billable, or from another release is dropped.
- **drop** a code (R6 duplicate I10, R2 E11.9 replaced by E11.22, I.C.14.a.1 stage + ESRD), recorded as `DroppedCode`. Only R1 drops of LLM-selected codes count as `model_errors`; the others are coding decisions.
- **annotate**: append a `RuleResult` (`pass` / `needs_review`), raise a `Gap`, or set `not_suggested`.

`run_rules` preloads the codes a note can need: the drafts plus each rule's declared `TARGET_CODES` (e.g. I12.0, I12.9, I11.0, I13.0, I13.2, E11.22, Z79.4, Z79.84) and their Excludes1 notes, so rules stay pure.

### Steps

1. [x] **Retrieval: Index `<see>` cross-references.** `load_icd10cm.py` resolves each `<see>` to its target term's code(s) and stores it as an extra `index_terms` row under the source term (no schema change). Reload FY2027 and FY2026 (upsert keeps embeddings). Checks: "poorly controlled" / "out of control" / "inadequately controlled" type 2 diabetes -> E11.65 in top 3; "heart failure with reduced ejection fraction" -> I50.20 in top 3; add both to `check_search.py`. Source: FY2027 Index entries.
2. [x] **Rule contract (DESIGN §5.2 first).** `CodeLookup` gains `excludes1_of(code, code_set_id) -> list[str]` (own notes plus inherited category notes, parsed to code or range patterns). Each rule module declares `TARGET_CODES`. `run_rules` counts only R1 drops as `model_errors`. New suggestions get ids after the drafts (`s{n+1}`).
3. [x] **R11 outpatient uncertain diagnosis** (IV.H). A suggestion whose facts are all `suspected`, `ruled_out` or `denied` is kept as `not_suggested` with a `RuleResult`, so the coder sees why. Runs first so later rules only combine confirmed codes. Today such facts get no candidates; R11 is the explicit guard.
4. [x] **R2 diabetes + CKD** (I.A.15 "With"). E11.9 + any N18.x -> E11.22 replaces E11.9, N18.x kept. If a more specific E11 complication is present (e.g. E11.65), add E11.22 alongside it. Same for E10 (E10.22).
5. [x] **R5, R4, R3 hypertension combinations**, run in that order (I.C.9.a.3, I.C.9.a.1, I.C.9.a.2).
   - R5: HTN + I50.x + N18.1-N18.4/N18.9 -> I13.0; with N18.5/N18.6 -> I13.2. I50.x and N18.x kept.
   - R4: HTN + I50.x, no CKD -> I11.0.
   - R3: HTN + N18.x, no HF -> I12.9 (N18.1-N18.4, N18.9) or I12.0 (N18.5, N18.6).
   - "HTN" = I10 or an I11/I12 code the LLM already picked. R4/R3 skip when R5 applied.
   - **Link check (owner decision J):** the HTN link is presumed unless a CKD or HF fact has a `caused_by` link to a fact that is not the hypertension. Then no combination code is added for that condition, and the HTN, N18/I50 suggestions get `needs_review`. If only one link is blocked (e.g. CKD caused by something else, HF not), the other combination still applies (R4 instead of R5). Same check in R2 for diabetes and CKD: CKD `caused_by` something other than diabetes -> no E11.22, `needs_review`.
6. [x] **R6** drops I10 when any I11/I12/I13 is present (I11, I12 and I13 include the hypertension; I.C.9.a.1 keeps I10 only when the provider documents the conditions as unrelated), and drops I11.x/I12.x when I13.x is present (I.C.9.a.3: "a code from I13 should be used, not codes from I11 or I12").
7. [x] **R7 diabetes type not documented** (I.C.4.a.2: default E11.-). A diabetes fact with no type in `concept` or `details` and an E11 code -> `needs_review` RuleResult, no gap (owner decision G).
8. [x] **R8 long-term drug use** (I.C.4.a.3). Diabetes code present + active medication fact that is insulin -> Z79.4; oral hypoglycemic -> Z79.84; injectable non-insulin -> Z79.85; each combination assigns both (n020). `data/diabetes_drug_classes.csv` (`drug,class,source`): the gold-note drugs (metformin, insulin glargine) plus a few common ones, each citing its FDA label (DailyMed) for route and class (owner decision K). Semaglutide is left out: it has both an oral and an injectable label, so the name alone does not give the class.
9. [x] **R9 CKD stage gap** (I.C.14.a.1). N18.9 -> gap "missing: CKD stage"; N18.30 -> gap "missing: stage 3a or 3b". Also I.C.14.a.1: stage + ESRD both documented -> keep N18.6 only.
10. [x] **R10 heart failure gap** (I.C.9.a.1 and I.C.9.a.3: "additional code from category I50 to identify the type of heart failure"; acuity has no guideline sentence of its own, it comes from the I50.2-/I50.3-/I50.4- Tabular subcodes). I50.9 -> gap "missing: heart failure type"; I50.20/I50.30/I50.40 -> gap "missing: acuity".
11. [x] **R12 Excludes1** (I.A.12.a). Two kept codes where one is in the other's Excludes1 -> both `needs_review` and a `conflicting` gap asking whether the conditions are related (the guideline says query the provider when unclear). Never drops a code on its own.
12. [x] **Gap wording.** Every `query_text` is neutral: it asks for the missing fact ("Please document the CKD stage, if known.") and never names a code, a payment effect, or a preferred answer. A unit test scans all gap templates for leading words (e.g. "higher", "more specific code", "consider documenting").
13. [x] **Conflict detection** (in `assemble`, pure helper): two different codes in the same N18 or I50 family for the note -> `conflicting` gap, both `review`. This also catches n014 (I50.20 + I50.9).
14. [x] **Confidence bands** (DESIGN §5.1 gets the definition): `not_suggested` = R11 applied; `review` = any `needs_review` result or any linked gap; `strong` = every rule result `pass`, no linked gap, evidence present.
15. [ ] **Tests.** One file per rule in `tests/unit/rules/`: positive, negative, edge case each, using `InMemoryCodeLookup`. Graph test with recorded fixtures for one combination note. Re-record the worked example only if its output changes (it should not: E11.22 + N18.30 already). *(2026-09-27: rule, chain and confidence tests done (133 unit); the recorded combination-note graph test still needs a recording, i.e. LLM calls.)*
16. [ ] **extract_v2** (owner decision L): same as v1, plus: when a diagnosis is suspected/possible/probable, also extract the documented symptoms or signs behind it as their own `active` facts. `PROMPT_VERSION` -> `extract_v2+select_v1`; re-record the worked-example fixtures with `record_llm.py`. *(2026-09-27: prompt added and pipeline switched; re-recording pending, 2 LLM calls, so `test_worked_example_from_recorded_llm` fails on prompt drift until then.)* DESIGN: MDM extraction becomes `extract_v3` in M6.
17. [ ] **Eval (revised 2026-09-27, owner):** when the Groq limit recovers, budget check first; (i) re-record worked-example fixtures (2 calls); (ii) run (a) from scratch with a new run id, `--extract-prompt extract_v1`, 20 notes, outputs saved (the old `2026-09-27-m4rules-*` 14 + 6 run is not patched); (iii) run (b) `extract_v2`, 20 notes; if both don't fit, (a) today and (b) the next day; (iv) replay both with the N18 stage rule and report all against M3.
18. [x] **DESIGN.md** in the same change as the code: `Suggestion.added_by_rule`, `CodeLookup.excludes1_of`, rule add/drop contract and R1-last, `model_errors` definition, confidence bands, R1-R12 behaviour with sources, extract_v2/v3, and a **Known limits** list (at least: "unrelated" statements with no alternative cause are not captured; secondary diabetes E08/E09/E13 combinations; temporary insulin use (I.C.4.a.3) is not detected; I11.9/I12 without a documented link beyond the presumption).
19. [x] **`--extract-prompt`** (default `extract_v2`), recorded in `meta.json`; resuming a run with a different setup, model or prompt version stops.
20. [x] **Usage logging:** `LlmClient(on_usage=...)` reports prompt, completion and reasoning tokens per call; run files keep `usage` (summed across retries); local gitignored ledger `eval/.usage_ledger.jsonl`; `record_llm.py` logs too.
21. [x] **Budget check** before every live run (`eval/budget.py`): estimate from saved usage (default 4k/pipeline note, 800/baseline note) vs 200k/day minus the ledger's last 24 h; stops unless `--ignore-budget`.
22. [x] **Saved LLM outputs + replay:** run files keep facts, candidate sets, selections (`SavedLlmOutputs`); `run_eval.py --replay-of RUN_ID` reruns only rules + assemble, no LLM. Rule changes are measured by replay from now on.
23. [x] **n007 fix:** R2/R3/R5 add the N18 code for the stage the CKD fact documents when none was selected (N18.9 if no stage); R9 replaces N18.9/N18.30 with a documented stage and raises its gap only when no stage is written. Tests in `tests/unit/rules/test_ckd_stage.py`.

**Verify:** all rule tests pass; `check_search.py` passes with the new `<see>` checks; `rescore.py` gates pass; 20-note table printed next to M3 with gap recall measured (M4 done-when).

**Owner decisions (2026-09-27):**

- I. Yes: R2-R5 add combination codes from the code table with `added_by_rule` and evidence from the triggering facts; every added code must pass R1, with a test.
- J. Use `caused_by` links: a CKD or HF fact caused by something other than hypertension -> no presumed link, `needs_review`. Same for R2 (diabetes-CKD). Uncovered cases go to DESIGN as known limits.
- K. FDA labels are fine. Short list, each row cites its label; cover Z79.4, Z79.84, Z79.85.
- L. Add `extract_v2` in M4 for symptoms behind suspected diagnoses; MDM becomes `extract_v3` in M6. Eval twice (rules + v1, then rules + v2), both against M3.
- (later, 2026-09-27) Groq free-tier daily cap hit (200k tokens/day for gpt-oss-120b). Approved: `--extract-prompt`, usage logging with a local ledger, saved LLM outputs + replay, the N18 stage fix, a budget check, and "10-note smoke while developing, full set at milestone end" (CLAUDE.md). n004 (E11.65 in candidates, LLM chose E11.9) waits for run (b). Deferred: `reasoning_effort=low` and 20 -> 10 candidates, both to be judged by replay/saved outputs.

---

## Previous task: M3 detailed plan (done 2026-09-27)

Touches DESIGN.md §3.3 (model choice), §5.4 (GoldNote, added), §9 (metrics, thresholds), §10 (M3).

### Gold notes (for owner spot-check before any eval runs)

All synthetic. All visit dates are in FY2027 (2026-10-01 to 2027-03-31). Every code below was checked as billable in `ICD10CM-FY2027` (read-only query, 2026-09-27). `scripts/validate_gold.py` will re-check them permanently. Expected codes are the **correct final coding**, not what the M2 pipeline can do today: M2 has only R1, so combination codes and gaps will score low until M4, and that change is what the eval measures.

| ID | Tags | Expected codes | Gap rules | Key guideline / reason (checked against FY2027 Guidelines PDF + FY2027 Index) | Changed? |
|---|---|---|---|---|---|
| n001 | dm, med-oral | E11.9, Z79.84 | - | DM2 no complications; metformin: I.C.4.a.3 + E11 Tabular "use additional code" -> Z79.84 | yes: added I.C.4.a.3 and Tabular note |
| n002 | dm+ckd | E11.22, N18.32 | - | I.A.15 "With" presumes DM-CKD link; stage 3b documented | no |
| n003 | dm+ckd, gap-ckd-subtype | E11.22, N18.30 | R9 | I.A.15; stage 3 without 3a/3b -> N18.30 | yes: added I.A.15 |
| n004 | dm, dm-hyperglycemia, med-insulin | E11.65, Z79.4 | - | Index: Diabetes, poorly controlled: see Diabetes, by type, with hyperglycemia; insulin: I.C.4.a.3 | yes: added I.C.4.a.3 |
| n005 | htn | I10 | - | essential hypertension only | no |
| n006 | htn+ckd | I12.9, N18.4 | - | I.C.9.a.2 Hypertensive CKD (I12 + N18 for stage); stage 4 | no |
| n007 | htn+ckd, ckd5 | I12.0, N18.5 | - | I.C.9.a.2; stage 5 not on dialysis -> I12.0 + N18.5 | yes: added I.C.9.a.2 |
| n008 | htn+hf | I11.0, I50.22 | - | I.C.9.a.1 Hypertension with heart disease (I11 + I50); chronic systolic | no |
| n009 | htn+hf, gap-hf-type | I11.0, I50.9 | R10 | I.C.9.a.1; HF type not documented -> I50.9 | yes: added I.C.9.a.1 |
| n010 | htn+hf+ckd | I13.0, I50.32, N18.31 | - | I.C.9.a.3 Hypertensive heart and CKD (I13 + I50 + N18); chronic diastolic; stage 3a | no |
| n011 | dm+ckd, htn+hf+ckd | E11.22, I13.0, I50.23, N18.32 | - | I.A.15 (DM-CKD) + I.C.9.a.3; acute on chronic systolic | yes: added I.A.15 |
| n012 | ckd, gap-ckd-stage | N18.9 | R9 | CKD, stage not documented, no HTN or DM -> N18.9 | no |
| n013 | abbrev, dm+ckd, htn+ckd | E11.22, I12.9, N18.32 | - | "DM2, HTN, CKD 3b": I.A.15 + I.C.9.a.2 | yes: added citations |
| n014 | hf, abbrev, gap-hf-acuity | I50.20 | R10 | Index: Failure, heart, with, reduced ejection fraction: see Failure, heart, systolic -> I50.20; acuity not documented | yes: was uncited; now the Index entry |
| n015 | suspected, htn | I10, R06.02 | - | IV.H Uncertain diagnosis: "possible" is a similar term indicating uncertainty; code the symptom | yes: wording (IV.H does not list "possible" by name) |
| n016 | negation, htn | I10 | - | note documents no heart failure and no CKD | no |
| n017 | ruled-out, dm | E11.9 | - | note documents CKD ruled out on repeat testing | no |
| n018 | dm-type-missing, med-oral | E11.9, Z79.84 | - | I.C.4.a.2 type not documented defaults to E11; R7 gives needs_review, no gap | yes: R7 behaviour per owner decision G |
| n019 | injection, htn | I10 | - | prompt injection in the note must be ignored (DESIGN §5.2) | no |
| n020 | dm, med-insulin, med-oral | E11.9, Z79.4, Z79.84 | - | I.C.4.a.3 insulin + oral: assign both Z79.4 and Z79.84 | no |

Coverage (coded conditions): 9 DM, 8 CKD, 11 HTN, 5 HF notes, plus 1 suspected HF (n015); 4 gap notes (R9 x2, R10 x2); negation, suspected, ruled-out, abbreviation, default-type, and prompt-injection cases.

### Steps

1. [x] `app/models/eval.py`: `ExpectedCode`, `GoldNote` exactly as DESIGN §5.4.
2. [x] `data/gold_notes/n001.json` ... `n020.json` per the table above. Short synthetic notes, no names, no PHI-like identifiers.
3. [x] `scripts/validate_gold.py`: schema, unique note ids, non-empty reasons, rule ids in R1-R14, and every expected code billable in the code set for its visit date (real tables). A unit test runs the schema and reason checks in CI; the code check needs the loaded tables, so it runs locally.
4. [x] `eval/metrics.py` (pure, unit-tested). Per-note sets of exact codes, micro-averaged:
   - precision and recall over expected vs suggested codes;
   - invented rate: suggested codes not in the code set for the visit date (hard gate 0);
   - unsupported rate: suggested codes with no evidence, or evidence that is not a sentence number in the note;
   - gap recall: expected gap rule ids raised by a `Gap.rule_id`;
   - E/M match: reported "n/a" while every `expected_em` is None.
5. [x] `eval/run_eval.py --setup pipeline --limit N [--model M] [--run-id ID]`: runs `run_pipeline` in-process against the real db (same code path as the API, minus HTTP).
   - **Pacing:** a fixed delay between LLM calls (default 4 s).
   - **Backoff:** a note that ends in `LLM_UNAVAILABLE` or `TIMEOUT` is retried up to 3 times at 30, 60 and 120 s.
   - **Resumable:** each note's result is saved to `eval/results/runs/<run_id>/<note_id>.json` as it finishes. Rerunning with the same `--run-id` skips notes already saved as completed and reruns failed ones.
   - The model is set by overriding `LLM_MODEL` for the run, never in code.
6. [x] `eval/baseline_llm_only.py`: same model, same pacing and resume. One prompt, `baseline_v1.md`, reads the numbered sentences and returns codes with evidence, with no candidates and no rules. Scored by the same metrics, so its invented rate is measured, not assumed.
7. [x] Reports: `eval/results/YYYY-MM-DD-<setup>-<model>.json` plus a markdown summary. `eval/compare.py` prints the pipeline vs baseline table and marks any metric below the DESIGN §9 threshold.
8. [x] Model comparison: `openai/gpt-oss-20b` vs `openai/gpt-oss-120b` (Groq). Pipeline and baseline for each, on n001-n010 (about 60 LLM calls, paced). Selection order: invented rate must be 0; then recall, then precision; then latency. Write the choice and numbers into DESIGN §3.3 and close Open Question 1.
9. [x] Smoke eval in CI (see decision F).
10. [x] Review: first pipeline vs baseline table on 20 notes with the chosen model, compared against thresholds (expected to miss several until M4).

**Verify:** unit tests for metrics, gold schema and pacing/resume logic (fake LLM, fake sleep); `validate_gold.py` passes on the real tables; the comparison table prints; a resumed run skips finished notes.

**Owner decisions (2026-09-27):** F agreed (CI re-scores committed results; live eval local, live-with-secrets in M9). G confirmed (n018: E11.9, R7 needs_review, no gap). H agreed (measure in M3, fix in M4; task added to M4).

**Decisions as proposed:**
**Guideline check (2026-09-27):** every section number above was checked against `data/raw/fy-2027-icd-10-cm-coding-guidelines.pdf` (FY2027, effective 2026-10-01). All cited sections exist with the cited meaning. One wrong citation was found outside the table: R1 cited "§I.B.3" for level of detail, but Level of Detail in Coding is **I.B.2** (I.B.3 is the code range A00.0-T88.9, Z00-Z99.8). Fixed in `r1_code_validity.py`. HFmrEF -> combined (I50.4-) has no Index or Guidelines source; it comes from coding practice and is not used by any gold note. Removed 2026-09-27 (owner): HFmrEF now expands only to "heart failure with mildly reduced ejection fraction"; its I50.40 test cases are gone.

- F. **CI smoke eval.** CI has no Groq key (tests never call a real LLM) and no loaded ICD tables (loading and embedding takes about 20 minutes). Proposal: CI re-scores the committed per-note results of the latest local run and fails if the invented rate is above 0 or the metrics code breaks. The live 10-note smoke run stays a local command before any pipeline, prompt, retrieval or rule change (CLAUDE.md workflow step 3), and a live eval with secrets moves to `eval-full.yml` in M9.
- G. **R7 (diabetes type not documented).** DESIGN says R7 "defaults and marks for review", not that it raises a gap. So n018 expects E11.9 and no gap rule. Confirm, or say if R7 should raise a gap.
- H. **Retrieval gap found while writing n004.** The loader skips Alphabetic Index `<see>` cross-references (12,147 of them), for example "Diabetes > poorly controlled: see Diabetes, by type, with hyperglycemia". n004 will show the effect. Proposal: record it now and fix it in M4 as a retrieval change, measured by the eval, instead of changing retrieval inside M3.

### M3 Review (2026-09-27)

**Done:** `ExpectedCode`/`GoldNote` (DESIGN §5.4); 20 synthetic gold notes, every citation checked against the FY2027 Guidelines PDF and Index; `scripts/validate_gold.py` (20 notes, 39 expected codes, 0 problems on the real tables); `eval/metrics.py` (precision, recall, invented, invalid, unsupported, gap recall, E/M match); `eval/run_eval.py` + `eval/baseline_llm_only.py` with pacing, backoff and resume by `--run-id`; reports in `eval/results/`; `eval/compare.py`; CI re-scores committed runs (`eval/rescore.py`). R1 citation fixed to I.B.2. Unsourced HFmrEF -> combined mapping removed.

**Owner decisions after the runs:** added the invalid-code metric (predicted code not in the visit date's code set, or not billable) next to the unchanged invented rate; `invalid rate = 0` is a pipeline threshold in DESIGN §9 and a CI gate in `rescore.py`. Model: `openai/gpt-oss-120b` (DESIGN §3.3; Open Question 1 closed). `context/` (a stale draft of this file) deleted.

**Model comparison (n001-n010, same prompts):**

| Metric | pipeline 20b | pipeline 120b | baseline 20b | baseline 120b |
|---|---|---|---|---|
| invented rate | 0.00 | 0.00 | 0.00 | 0.00 |
| invalid rate | 0.00 | 0.00 | 0.17 | 0.11 |
| recall | 0.70 | 0.70 | 0.35 | 0.50 |
| precision | 0.67 | 0.70 | 0.39 | 0.53 |
| mean latency | 9.6 s | 7.8 s | 4.1 s | 3.8 s |

Selection order (invented 0, then recall, then precision): tie on recall, 120b wins on precision.

**20-note result, gpt-oss-120b** (runs `2026-09-27-n20-*`):

| Metric | Threshold | Pipeline | Baseline |
|---|---|---|---|
| precision | >= 0.85 | 0.78 ✗ | 0.56 ✗ |
| recall | >= 0.80 | 0.82 ✓ | 0.49 ✗ |
| invented rate | 0 | 0.00 ✓ | 0.03 ✗ (E11.23) |
| invalid rate | 0 | 0.00 ✓ | 0.12 ✗ (N18.3 x3, E11.23) |
| unsupported rate | <= 0.05 | 0.00 ✓ | 0.00 ✓ |
| gap recall | >= 0.80 | 0.00 ✗ | 0.00 ✗ |
| E/M match | >= 0.75 | n/a | n/a |

20 notes, 0 failed in both. Mean latency 10.7 s pipeline, 4.0 s baseline.

**Verified:** 77 unit + 34 integration tests pass; ruff, ruff format and mypy clean on `app`, `scripts`, `eval`; `check_search.py` and `validate_gold.py` pass; a resumed run skipped n001-n006; `rescore.py` passes both gates on all six committed runs.

**Open, for M4:** pipeline misses are the M4 targets: combination codes (I12.9 on n006/n013, I11.0 on n008/n009, I13.0 on n010/n011; the pipeline gives I10, and adds I10 next to I12.0 on n007), R06.02 missed on n015, and all 4 expected gaps (R9 on n003/n012, R10 on n009/n014). Precision is below threshold mainly from those extra I10s, plus I50.9 next to I50.20 on n014 and R60.9 on n009. Index `<see>` cross-references are still not loaded (n004 passed on 120b anyway).

---

## Previous task: M2 detailed plan (done 2026-09-27)

Touches DESIGN.md §3.4 (R1), §4.1, §4.4, §5.1, §5.2, §6 (`/notes`, `/analyze`), §10 (M2). Adds dependency `langgraph` (DESIGN §3.3 pipeline choice).

**Worked example** (synthetic; proposed for DESIGN.md and `data/examples/worked_example.json`), visit 2026-10-15, established patient:

```
Assessment: Type 2 diabetes mellitus with chronic kidney disease stage 3.
HPI: 62-year-old presents for diabetes and kidney follow-up. Denies chest pain or shortness of breath.
Plan: Continue current regimen. Recheck renal function in 3 months.
```
Sentence 1 = "Type 2 diabetes mellitus with chronic kidney disease stage 3." Expected: E11.22 and N18.30, both with evidence [1].

1. [x] `segment/`: `segment_note(text) -> list[Sentence]`. Known headers map to normalized sections (hpi, assessment, plan, exam, ...); unknown `Word:` lines stay in the current section. Split on sentence punctuation and newlines, protecting decimals and common abbreviations. Invariant: `text[start:end] == sentence.text`. Unit tests for sections, numbering and offsets.
2. [x] Models: `Sentence`, `NoteCreate`, `Note`, `ExtractionOutput`, `MdmElements`, `CodeSelection`, `RuleResult`, `Gap`, `EmResult`, `Suggestion`, `PipelineError`, `AnalysisResult`, as in §5.1. Add `RuleInput`/`RuleOutput` to DESIGN §5.2; CLAUDE.md names them, DESIGN does not define them yet.
3. [x] `POST /notes` (segment, store, `404 PARENT_NOTE_NOT_FOUND`, `422 VALIDATION_ERROR` as `ErrorResponse`) and `GET /notes/{id}` (`404 NOTE_NOT_FOUND`).
4. [x] `llm/client.py`: httpx against `{LLM_BASE_URL}/chat/completions`, temperature 0, JSON mode, Pydantic validation. At most one retry per call: bad JSON or schema is retried once with the validation error, then `LLM_BAD_OUTPUT`; timeout, 429 or 5xx waits `Retry-After` capped at 20 s, retries once, then `LLM_UNAVAILABLE`. Sleep and transport are injectable. Unit tests use `httpx.MockTransport` and make no network calls.
5. [x] Prompts `llm/prompts/extract_v1.md` and `select_v1.md`: the note is untrusted data, output JSON only, the schema is embedded, and only supplied sentence numbers and candidate codes may be used. `extract_v1` returns `mdm` with all nulls; MDM extraction is `extract_v2` in M6.
6. [x] `pipeline/`: `PipelineState`, and nodes `extract_facts -> retrieve_candidates -> select_codes -> run_rules -> assemble`, one file each. A conditional edge after each node goes to `fail` when `state.error` is set. The 150 s deadline is carried in state; each LLM call gets the remaining time, and a node past the deadline sets `TIMEOUT`.
   - Validation: facts with evidence outside the note's sentence numbers are dropped (`model_errors += 1`). Selections for unknown facts, with codes outside that fact's `CandidateSet`, or with bad evidence are dropped (`model_errors += 1`). Candidates are retrieved for `active` and `performed` facts only.
7. [x] `rules/r1_code_validity.py`: pure `apply(inp, codes)`. It fails a code that is absent from the visit's code set or not billable. `run_rules` preloads the needed codes into an `InMemoryCodeLookup`, so rules never touch the db. `tests/unit/rules/test_r1.py` covers positive, negative and edge cases.
8. [x] `assemble`: build `Suggestion`s (ids `s1..sn`); `confidence = "review"` for every suggestion until M4's confidence bands. `em = None` until M6.
9. [x] `POST /notes/{id}/analyze`: `resolve_code_sets` (`409 CODE_SET_MISSING`), run graph, store analysis (completed or failed), return `AnalysisResult`. LLM failures return `503` + `ErrorResponse(analysis_id=...)`; a db write failure returns `500 DB_ERROR`.
10. [x] LLM recordings: `scripts/record_llm.py` runs the real provider on the worked example and saves `tests/fixtures/llm/worked_example/{extract,select}.json` with the prompt hash. A replay client serves them in tests and warns on hash drift. Integration test: worked example on the fixture db gives E11.22 and N18.30 with evidence `[1]`. Plus graph tests for each failure path with a fake LLM.

**Verify:** ruff, mypy strict, `pytest tests` green; the recorded worked example passes; a live `curl` of POST /notes then /analyze against the real db returns E11.22 and N18.30 with `[1]`.

**Owner decisions (2026-09-26):** all approved as proposed. A: Groq, model set only in `LLM_MODEL`. C: also log the dropped code and fact ID.
- A. LLM provider and model for recording (Groq first per DESIGN §3.3). The key goes in `backend/.env` (gitignored) and is never committed.
- B. DESIGN §10 says M2 compares Groq vs Hugging Face models on 10 gold notes, but gold notes are M3. Proposal: record with one model now and run the comparison in M3.
- C. R1 failure (a code not in the set or not billable): drop the suggestion and add 1 to `model_errors`. Candidates are already real and billable, so R1 is a guard that should never fire.
- D. Approve the worked example text above.
- E. `GET /analyses/{id}` is in §6 but in no milestone. Proposal: add it in M7 with history.

---

## Previous task: M1 detailed plan (done 2026-09-26)

Touches DESIGN.md §3.3 (search), §4.1 step 6, §5.2 (`search_candidates`, `get_code`), §5.3 (`codes`, `index_terms`, `abbreviations`), §10 (M1).

1. [x] Confirm CMS FY2027 ICD-10-CM download URL + file format
2. [x] `scripts/load_icd10cm.py --fy 2027`: download to `data/raw/`, parse tabular XML (codes, billable, parent, excludes1 / use additional / code first) + index XML (terms, paths); upsert `code_sets`, `codes`, `index_terms`
3. [x] `data/abbreviations.csv` + `scripts/seed_abbreviations.py`
4. [x] Embedder wrapper (`bge-small-en-v1.5`, 384-dim) via `fastembed`; `scripts/embed_codes.py` fills `codes.embedding` (resumable)
   - New dependency reason: `fastembed` runs the same bge model on ONNX without torch, so installs and CI stay small and fast.
5. [x] `terminology.resolve_code_sets(visit_date)`
6. [x] `terminology.search_candidates(fact, code_sets)`: abbreviation, index, text, vector; merge by code, record sources, billable only, cap 20
7. [x] `CodeLookup`: `get_code`, `children_of`, `is_billable`
8. [x] Tests: unit (merge/rank, abbreviation expansion, XML parser on a small fixture); integration (seeded test db: resolve, search, lookup)

**Verify:** unit + integration green; real FY2027 load, then "type 2 diabetes with CKD" → E11.22 and "CKD 3b" → N18.32 in candidates.

---

## Previous task: M0 detailed plan (done)

Touches DESIGN.md §3.3 (tech, env vars), §5.3 (tables), §6 (`/health`), §7 (folders), §10 (M0).

1. [x] Repo setup: `git init` in `CodeCareAI/` (today the only git repo is `$HOME`), `.gitignore` (`data/raw/`, `.env`, venvs, `node_modules`), move `DESIGN.md` + `CLAUDE.md` from `context/` to repo root per §7
2. [x] `backend/pyproject.toml`: fastapi, uvicorn, pydantic v2, pydantic-settings, sqlalchemy 2, psycopg 3, alembic, pgvector; dev: pytest, ruff, mypy, httpx
3. [x] `backend/app/config.py`: `Settings` via pydantic-settings — `DATABASE_URL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `FRONTEND_ORIGIN`; `.env.example`
4. [x] `docker-compose.yml`: `pgvector/pgvector:pg16`; init SQL enabling `vector` + `pg_trgm` (backend + web services added in M8/M9)
5. [x] `backend/app/db/`: engine/session, SQLAlchemy models for all 8 tables in §5.3 (`codes.embedding` = `vector(384)`, `tsv` generated tsvector, GIN/HNSW/trigram indexes)
6. [x] Alembic init + migration `0001_initial` (extensions + all tables); `reviews` append-only enforced by a trigger that raises on UPDATE/DELETE
7. [x] `GET /api/v1/health` → `{service, db: bool, code_sets: [ids]}`; `500 DB_ERROR` as `ErrorResponse` when db unreachable
8. [x] Tests: `tests/unit/test_config.py`, `tests/unit/test_health.py` (db dependency overridden, no real db); `tests/integration/test_schema.py` (real Postgres: health, tables, append-only)
9. [x] Ruff + mypy (strict) config in pyproject; `.github/workflows/ci.yml`: ruff, mypy, unit, migrate, integration on Python 3.12
10. [x] Update CLAUDE.md Commands section with real commands

**Verify:** `docker compose up -d db` → `alembic upgrade head` → `curl localhost:8000/api/v1/health` shows `"db": true`; `pytest tests/unit`, `ruff check`, `mypy app` all clean locally. CI green needs a GitHub remote (see open question).

---

## M0: Skeleton

- [x] Backend: `pyproject.toml`, FastAPI app, `config.py` with env vars from `DESIGN.md` Section 3.3
- [x] `docker-compose.yml` for local Postgres with pgvector and pg_trgm
- [x] SQLAlchemy setup + Alembic, first migration with all tables from `DESIGN.md` Section 5.3
- [x] `GET /api/v1/health` returns `db` status and loaded code sets
- [x] Ruff, mypy, pytest configured
- [x] GitHub Actions `ci.yml`: lint, type check, unit tests
- [x] Update the Commands section in `CLAUDE.md` with the real commands
- **Done when:** `/health` returns `db: true` locally and CI is green
- **Status:** local part done. CI green pending: no GitHub remote yet.

## M1: Code tables and search

- [x] `scripts/load_icd10cm.py --fy 2027`: download the CMS zip, parse codes, billable flag, parent code, tabular notes (excludes1, use additional, code first), index terms
- [x] `data/abbreviations.csv` + `scripts/seed_abbreviations.py`
- [x] Embedder wrapper (`bge-small-en-v1.5`); store 384-dim embeddings for every code
- [x] `terminology.resolve_code_sets(visit_date)`
- [x] `terminology.search_candidates(fact, code_sets)`: merge abbreviation, index, full-text, and vector results; cap at 20; billable only
- [x] `CodeLookup` interface: `get_code`, `children_of`, `is_billable`
- [x] Unit tests on a small seeded test db
- **Done when:** "type 2 diabetes with CKD" returns E11.22 and "CKD 3b" returns N18.32 in the candidates

## M2: Thinnest end-to-end slice

- [x] `segment_note()`: sections, numbered sentences, char offsets; unit tests on offsets
- [x] `POST /notes`, `GET /notes/{id}`
- [x] `llm_client`: OpenAI-compatible calls, JSON mode, Pydantic validation, one retry, timeout, 429 handling; unit tests with a fake server
- [x] Prompts `extract_v1.md` and `select_v1.md` (note is data, JSON only, schema included)
- [x] LangGraph graph: `extract_facts -> retrieve_candidates -> select_codes -> run_rules (R1 only) -> assemble`, plus `fail` branch
- [x] Drop facts with bad sentence numbers and selections outside the candidates; count `model_errors`
- [x] `POST /notes/{id}/analyze` stores and returns `AnalysisResult`
- [x] Record LLM responses into `tests/fixtures/llm/`; integration test on the worked example
- **Done when:** the worked example note returns E11.22 and N18.30 with evidence `[1]`

## M3: Evaluation harness

- [x] First 20 gold notes in `data/gold_notes/` (`GoldNote` format)
- [x] `eval/metrics.py`: precision, recall, invented rate, unsupported rate, gap recall, E/M match
- [x] `eval/run_eval.py` (pipeline) and `eval/baseline_llm_only.py` (same model, LLM only)
- [x] Save results to `eval/results/YYYY-MM-DD.json` + markdown summary
- [x] Add smoke eval (10 notes) to CI; invented rate must be 0
- **Done when:** the first pipeline vs baseline table prints

## M4: ICD-10 rules and gaps

- [ ] Retrieval: load Alphabetic Index `<see>` cross-references (12,147 in FY2027), resolving each to its target term's code(s). Must cover "poorly controlled", "out of control" and "inadequately controlled" diabetes -> "with hyperglycemia" (E11.65 for type 2), and "heart failure with reduced/preserved ejection fraction" -> systolic/diastolic. Measure with gold note n004 and the eval before/after.
- [ ] R2 diabetes + CKD → E11.22 + N18.x
- [ ] R3 hypertension + CKD → I12.9 or I12.0 + N18.x
- [ ] R4 hypertension + heart failure → I11.0 + I50.x
- [ ] R5 all three → I13.0 or I13.2 + I50.x + N18.x
- [ ] R6 remove I10 when I11, I12, or I13 is present
- [ ] R7 diabetes type not stated → E11, `needs_review` RuleResult, no gap (owner decision G)
- [ ] R8 diabetes medication → Z79.84 or Z79.4
- [ ] R9 CKD stage or 3a/3b missing → gap
- [ ] R10 heart failure type or acuity missing → gap
- [ ] R11 suspected diagnosis in outpatient → not suggested
- [ ] R12 Excludes1/tabular conflicts; review only where the official exception can apply (always runs, even without a CPT set)
- [ ] Conflict detection in `assemble` (two different stages for one condition)
- [ ] Confidence bands: strong, review, not suggested
- [ ] One test file per rule: positive, negative, edge case
- [ ] Rerun eval; record the change from M3
- **Done when:** all rule tests pass and gap recall is measured

## M5: Code set versions

- [x] Load FY2026 with `load_icd10cm.py --fy 2026` (April 1, 2026 update only, valid 2026-04-01 to 2026-09-30; loaded 2026-09-26)
- [ ] Test the Sep 30 vs Oct 1, 2026 switch in `resolve_code_sets`
- [ ] `409 CODE_SET_MISSING` when no code set covers the visit date
- **Done when:** the same note dated 2026-09-30 and 2026-10-01 uses the matching code set

## M6: CPT and E/M

- [ ] `data/cpt_subset.csv` (our own wording) + `scripts/seed_cpt.py`
- [ ] `scripts/load_ncci.py` (pairs filtered to our subset)
- [ ] Extend extraction to return `MdmElements` (problems, data, risk)
- [ ] `em.compute_level()`: MDM 2-of-3 table for new and established patients; table-driven tests for every combination
- [ ] `compute_em` node in the graph
- [ ] R13 each CPT code has a supporting diagnosis; NCCI PTP pair conflicts with the modifier indicator
- [ ] R14 E/M from extracted MDM via `em.compute_level()`; missing MDM elements → no E/M code + gap
- [ ] R13 and R14 skipped when `CodeSetSelection.cpt` is None
- [ ] Add 10 gold notes with labs, full MDM, and incomplete MDM
- **Done when:** E/M tests pass and gold notes with labs raise R13 correctly

## M7: Review and history

- [ ] `POST /analyses/{analysis_id}/suggestions/{suggestion_id}/reviews`: accept, edit (replacement must exist and be billable), reject (reason required)
- [ ] Append-only `reviews`; no update or delete path in code
- [ ] `GET /notes/{id}/history`
- [ ] `GET /analyses/{id}` (`404 ANALYSIS_NOT_FOUND`)
- [ ] New note version via `parent_note_id`
- [ ] Integration tests for every endpoint and every error code in `DESIGN.md` Section 6
- **Done when:** all API integration tests pass

## M8: Frontend

- [ ] Next.js app, `npm run gen:types` from OpenAPI
- [ ] `/`: note form (text, visit date, new or established patient)
- [ ] `/notes/[id]`: note panel with evidence highlights, suggestion cards, rule results, gap list, E/M card
- [ ] Accept, edit, reject buttons; hide not-suggested codes but show their gaps
- [ ] Clear failed-analysis state and loading state
- [ ] Playwright smoke test
- **Done when:** the smoke test passes: create note, analyze, see highlights, review a code

## M9: Deploy config and full eval

- [ ] Backend Dockerfile for the Hugging Face Space + `deploy-backend.yml`
- [ ] CORS set from `FRONTEND_ORIGIN`
- [ ] Complete gold set to 50 notes
- [ ] `eval-full.yml`: full eval + baseline; compare with thresholds in `DESIGN.md` Section 9.2
- [ ] README: setup, architecture, results table, limitations
- [ ] Public API accepts real notes (Codex finding 14): before any public deploy, add a guard (for example a synthetic-data notice plus request limits, or no public write access) so the demo cannot be used to process real patient notes
- **Done when:** full eval runs and results are in the README

---

## Review

(Fill in after each milestone: what was done, how it was verified, what's still open.)

### M0 (2026-09-26)

**Done:** own git repo; `DESIGN.md` + `CLAUDE.md` moved to root; backend skeleton (FastAPI, pydantic-settings config, SQLAlchemy 2 models for all 8 §5.3 tables, Alembic `0001_initial`); `reviews` append-only via db trigger (UPDATE/DELETE/TRUNCATE); `GET /api/v1/health` with `DB_ERROR`; docker-compose Postgres 16 + pgvector + pg_trgm; ruff, strict mypy, pytest; `ci.yml` (lint, types, unit, migrate, integration against a pgvector service).

**Verified locally:** `ruff check`, `ruff format --check`, `mypy app` (strict) clean; `pytest tests/unit` 4 passed; `alembic upgrade head` ok; `pytest tests/integration` 3 passed (health on real db, all tables exist, append-only trigger); `alembic check` no drift; live `curl /api/v1/health` → `{"service":"codecare-api","db":true,"code_sets":[]}`.

**Design change:** added `HealthResponse` to DESIGN §5.1 / §6; noted the append-only trigger in §5.3.

**Open:**
- CI never run: needs GitHub repo + push.
- ~~`todo.md` vs `DESIGN.md` conflicts~~ Resolved 2026-09-26: rule numbers and review endpoint path now follow DESIGN.md; worked example defined in the M2 plan. Still open: `GoldNote` format (define in M3).
- Starlette warns `httpx` with TestClient is deprecated (`httpx2`); harmless now, revisit on upgrade.

### M1 (2026-09-26)

**Done:** CMS FY2027 loader (order file + tabular XML + index XML; per-FY URL map since CMS names differ by year); `data/abbreviations.csv` (22; IDDM/NIDDM deliberately excluded; HFrEF/HFpEF/HFmrEF map to systolic/diastolic/combined heart failure) + seeder; fastembed bge-small embeddings (resumable `scripts/embed_codes.py`); `resolve_code_sets`; `search_candidates` (abbreviation expansion, index trigram, FTS, vector, RRF merge, billable only, cap 20); `CodeLookup` protocol + `DbCodeLookup`; DESIGN §3.3, §4.1, §5.2, §5.3, §7, §11 updated.

**Verified:** ruff, strict mypy clean; `pytest tests` 45 passed (unit: parser, abbreviations, RRF; integration on `codecare_test`: code-set dates, search, lookup, reload keeps embeddings, heart failure, no "Note:" text). Real FY2027: 98,403 codes (74,879 billable), 63,259 index terms, all 98,403 embedded. `scripts/check_search.py` with vector search fully on, exact codes:

| Query | Expected | Rank |
|---|---|---|
| type 2 diabetes with CKD | E11.22 | 1 |
| CKD 3b | N18.32 | 1 |
| chronic kidney disease, stage 3b | N18.32 | 1 |
| DM2 | E11.9 | 3 |
| HTN | I10 | 2 |
| HFrEF | I50.20 | 1 |
| systolic heart failure | I50.20 | 1 |
| HFpEF | I50.30 | 1 |
| HFmrEF | I50.40 | 1 |

Plus 0 index rows containing "Note:" text.

**Correction:** the first version of this review reported HFrEF as "I50.2x at rank 2". The exact code was I50.23 (acute on chronic), and I50.20 was not in the top 20. Two causes, both fixed: (1) CMS encodes a "Note: heart failure stages..." guidance line as an index heading wrapping the systolic subterms, which buried I50.20-I50.22 under long note text; the parser now skips "Note:" headings. (2) HFrEF expanded to "heart failure with reduced ejection fraction", which exactly matches the index path "with decompensation > with reduced ejection fraction" -> I50.23; it now expands to "systolic heart failure". Lesson added to `tasks/lessons.md`.

**Tests that can fail:** the small fixture could not tell fixed from broken end to end (text-search ties sort alphabetically, so I50.20 wins anyway). Added a check that the index source alone ranks I50.20/I50.30/I50.40 first, and a check that the CSV holds the systolic, diastolic and combined mappings. Mutation-checked: reverting the parser fix fails 4 tests; reverting the mapping fails 4 tests.

**Fixed on the way:** integration tests were wiping the dev db (now separate test db); nonessential modifiers diluted trigram scores (HTN missed I10); reload wiped embeddings (now upsert); 98k `NOT IN` hit the 65,535-param limit (array param); SQLAlchemy 2.1 `.tuples()` change.

**Open:**
- Ranking noise: HTN top-1 is K76.6 (portal hypertension); I10 is #2. The LLM picks from the 20, but measure in M3 eval before tuning.
- Embedding the full set takes ~20-30 min on CPU; not in CI (CI uses a fake embedder).

### M2 (2026-09-27)

**Done:** segmenter (sections, numbering, exact offsets); `POST /notes`, `GET /notes/{id}`, `POST /notes/{id}/analyze`; OpenAI-compatible LLM client (JSON mode, temperature 0, one retry, Retry-After capped at 20 s, 150 s deadline); prompts `extract_v1`/`select_v1`; linear LangGraph pipeline with one `fail` branch; output validation (bad evidence, non-candidate codes, dangling links counted in `model_errors`); R1 as a pure rule over a preloaded `InMemoryCodeLookup` (drops are counted and logged with code and fact IDs); worked example in `data/examples/`; record/replay of real LLM responses. DESIGN: `SelectionOutput`, `RuleInput`/`RuleOutput`/`DroppedCode`, `PIPELINE_ERROR`, pipeline state, sentence rules, worked example, model comparison moved to M3.

**Verified:**
- ruff, strict mypy clean; `pytest tests` 96 passed (no test calls a real LLM).
- **Done-when:** worked example through Groq `openai/gpt-oss-20b` against the real FY2027 tables returns E11.22 and N18.30, both evidence `[1]`, `model_errors` 0. Replayed in CI by `test_worked_example_from_recorded_llm`. Live `curl` through the API: HTTP 200, same codes, R1 pass, 6.5 s.
- Stability: 6 of 6 runs that completed gave the identical answer; 3 other runs failed with Groq free-tier 429s after the one allowed retry (`LLM_UNAVAILABLE`, as designed).
- Live error paths: 503 `LLM_UNAVAILABLE` with no key (failed analysis stored), 409 `CODE_SET_MISSING` for 2026-03-31, 404 `NOTE_NOT_FOUND`.
- Secrets: `backend/.env` is gitignored and untracked; the key appears in no committed file, history, or fixture.

**Fixed on the way:** missing LLM config raised during dependency resolution (bare 500, and it hid the 409); the recorder wrote each step as it went, so a failed run left extract and select files from different runs (now writes only after a passing run); `.env` was read relative to the working directory (now pinned to `backend/.env`); `langgraph` and `httpx` were missing from runtime dependencies.

**Open:**
- Groq free-tier rate limits: back-to-back runs hit 429s. The M3 eval (20+ notes x 2 calls, plus the baseline) needs pacing between notes.
- The extractor put `{'type': 'renal function test'}` in a planned test's details. Harmless now (planned facts are not coded); watch in M3.
- `AnalysisResult.created_at` is the pipeline start time; the db row uses the same value.

