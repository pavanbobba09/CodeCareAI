# CodeCare AI: To-Do

Source of truth: `DESIGN.md`. Rules for working: `CLAUDE.md`.
Each milestone ends with its own passing check. Don't start a milestone until the one before it passes.

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

- [ ] First 20 gold notes in `data/gold_notes/` (`GoldNote` format)
- [ ] `eval/metrics.py`: precision, recall, invented rate, unsupported rate, gap recall, E/M match
- [ ] `eval/run_eval.py` (pipeline) and `eval/baseline_llm_only.py` (same model, LLM only)
- [ ] Save results to `eval/results/YYYY-MM-DD.json` + markdown summary
- [ ] Add smoke eval (10 notes) to CI; invented rate must be 0
- **Done when:** the first pipeline vs baseline table prints

## M4: ICD-10 rules and gaps

- [ ] R2 diabetes + CKD → E11.22 + N18.x
- [ ] R3 hypertension + CKD → I12.9 or I12.0 + N18.x
- [ ] R4 hypertension + heart failure → I11.0 + I50.x
- [ ] R5 all three → I13.0 or I13.2 + I50.x + N18.x
- [ ] R6 remove I10 when I11, I12, or I13 is present
- [ ] R7 diabetes type not stated → E11, needs review
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

