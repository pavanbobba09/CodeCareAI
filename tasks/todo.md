# CodeCare AI: To-Do

Source of truth: `DESIGN.md`. Rules for working: `CLAUDE.md`.
Each milestone ends with its own passing check. Don't start a milestone until the one before it passes.

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

- [ ] `segment_note()`: sections, numbered sentences, char offsets; unit tests on offsets
- [ ] `POST /notes`, `GET /notes/{id}`
- [ ] `llm_client`: OpenAI-compatible calls, JSON mode, Pydantic validation, one retry, timeout, 429 handling; unit tests with a fake server
- [ ] Prompts `extract_v1.md` and `select_v1.md` (note is data, JSON only, schema included)
- [ ] LangGraph graph: `extract_facts -> retrieve_candidates -> select_codes -> run_rules (R1 only) -> assemble`, plus `fail` branch
- [ ] Drop facts with bad sentence numbers and selections outside the candidates; count `model_errors`
- [ ] `POST /notes/{id}/analyze` stores and returns `AnalysisResult`
- [ ] Record LLM responses into `tests/fixtures/llm/`; integration test on the worked example
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
- [ ] Conflict detection in `assemble` (two different stages for one condition)
- [ ] Confidence bands: strong, review, not suggested
- [ ] One test file per rule: positive, negative, edge case
- [ ] Rerun eval; record the change from M3
- **Done when:** all rule tests pass and gap recall is measured

## M5: Code set versions

- [ ] Load FY2026 with `load_icd10cm.py --fy 2026`
- [ ] Test the Sep 30 vs Oct 1, 2026 switch in `resolve_code_sets`
- [ ] `409 CODE_SET_MISSING` when no code set covers the visit date
- **Done when:** the same note dated 2026-09-30 and 2026-10-01 uses the matching code set

## M6: CPT and E/M

- [ ] `data/cpt_subset.csv` (our own wording) + `scripts/seed_cpt.py`
- [ ] `scripts/load_ncci.py` (pairs filtered to our subset)
- [ ] Extend extraction to return `MdmElements` (problems, data, risk)
- [ ] `em.compute_level()`: MDM 2-of-3 table for new and established patients; table-driven tests for every combination
- [ ] `compute_em` node in the graph
- [ ] R12 each CPT code has a supporting diagnosis
- [ ] R13 missing MDM elements → gap
- [ ] R14 NCCI pair conflict
- [ ] Add 10 gold notes with labs, full MDM, and incomplete MDM
- **Done when:** E/M tests pass and gold notes with labs raise R12 correctly

## M7: Review and history

- [ ] `POST /suggestions/{id}/review`: accept, edit (replacement must exist and be billable), reject (reason required)
- [ ] Append-only `reviews`; no update or delete path in code
- [ ] `GET /notes/{id}/history`
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
- `todo.md` vs `DESIGN.md` conflicts to resolve before M4/M6/M7: R12–R14 numbering, review endpoint path, undefined "worked example" note and `GoldNote` format.
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
