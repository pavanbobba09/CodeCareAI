# CLAUDE.md

Instructions for Claude Code in the CodeCare AI repo. Read this file, `DESIGN.md`, and `tasks/lessons.md` at the start of every session.

## What we are building

CodeCare AI reads an outpatient clinical note and suggests ICD-10-CM and CPT codes. Each code comes with the sentence that supports it, the results of the rule checks, and any documentation gaps. A human coder accepts, edits, or rejects every suggestion.

`DESIGN.md` is the single source of truth for components, types, endpoints, tables, rules R1 to R14, and build order. If the code and `DESIGN.md` disagree, stop and ask. Never quietly change the design. Update `DESIGN.md` in the same change as any change to a type, endpoint, table, rule, or component.

## Project rules (never break these)

1. **The LLM reads, plain code checks.** The LLM only extracts facts and picks from a candidate list. It never makes up codes, never decides a rule, and never computes the E/M level.
2. **No code without evidence.** Every suggestion cites sentence numbers that exist in the note.
3. **Every code comes from the `codes` table** for the code set valid on the visit date. Invented code rate must stay at 0.
4. **Synthetic data only.** Never add real patient data, real names, or anything that looks like PHI to the repo, fixtures, logs, or prompts.
5. **No AMA CPT text.** CPT descriptions are our own short wording in `data/cpt_subset.csv`.
6. **Coding rules live in `backend/app/rules/`**, one file per rule, each citing its guideline section, each with its own test file. Never put coding rules in prompts.
7. **Gap queries are neutral.** They never nudge the doctor toward a higher-paying answer.
8. **Reviews are append-only.** No UPDATE or DELETE on the `reviews` table.
9. **Tests never call the real LLM.** Use the recorded responses in `backend/tests/fixtures/llm/`.
10. **The LLM is set only by env vars** (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`). Never hardcode a provider or model name in code.
11. **Keep the LangGraph graph linear.** One failure branch, no loops, no checkpointer, no agents, unless `DESIGN.md` changes first.
12. **Stay inside scope.** No auth, claim submission, real-time analysis, inpatient coding, or payer rules. If a task seems to need one, ask first.

## Commands

Backend commands run inside `backend/` with the venv active (`source backend/.venv/bin/activate`).
Config comes from env vars or `backend/.env` (copy `backend/.env.example`).

```bash
# local Postgres (pgvector + pg_trgm) on :5432
docker compose up -d --wait db

# backend
uv venv --python 3.12 backend/.venv && cd backend && uv pip install -e ".[dev]"
cd backend && pytest tests/unit              # fast, no db, no LLM
cd backend && pytest tests/integration       # needs Postgres; uses <db>_test (or TEST_DATABASE_URL), never the dev db
cd backend && alembic check                  # ORM models match migrations
cd backend && ruff check . && ruff format --check .
cd backend && mypy app
cd backend && alembic upgrade head
cd backend && uvicorn app.main:app --reload

# frontend
cd frontend && npm install && npm run dev
cd frontend && npm run gen:types             # regenerate lib/types.ts from OpenAPI; never hand-edit it
cd frontend && npm run lint && npm run test:e2e

# data (backend venv active, from repo root; raw CMS files cached in data/raw/)
python scripts/seed_abbreviations.py
python scripts/load_icd10cm.py --fy 2027            # ~1.5 min; upsert keeps unchanged embeddings
python scripts/embed_codes.py --code-set ICD10CM-FY2027   # resumable; first run ~20-30 min on CPU
python scripts/check_search.py                      # M1 search smoke check on the real tables
python scripts/record_llm.py                        # worked example via the real LLM; re-records fixtures only on PASS (free tier: wait ~1 min between runs)
ruff check scripts && ruff format --check scripts

# eval (local, live LLM; paced; reruns with the same --run-id resume)
python scripts/validate_gold.py                     # gold notes: structure + codes billable for the visit date
python eval/run_eval.py --setup pipeline --limit 10 [--model M] [--run-id ID] [--extract-prompt extract_v1]
python eval/run_eval.py --replay-of RUN_ID [--run-id ID]   # rule changes: rerun rules on saved LLM outputs, no tokens
python eval/baseline_llm_only.py --limit 10 [--model M]
python eval/compare.py RUN_ID RUN_ID [--limit N]    # side-by-side vs DESIGN §9 thresholds
python eval/rescore.py                              # CI gate: no invented codes in committed pipeline runs
```

## Workflow

### 1. Plan first

- Use plan mode for any task with 3 or more steps or an architecture decision.
- Write the plan to `tasks/todo.md` as a checklist. Include how you will verify it.
- Check in with me before implementing. Name the `DESIGN.md` sections and milestone the task touches.
- If something goes wrong, stop and re-plan. Don't keep pushing a broken approach.

### 2. Subagents

- Use subagents for research, codebase searches, and independent parallel checks, so the main context stays clean.
- Give each subagent one focused job and ask it for a short conclusion, not file dumps.
- Don't use subagents for small, obvious edits.

### 3. Verify before calling it done

- Never mark a task complete without proof: tests pass, the endpoint returns the expected JSON, the page renders, or the eval runs.
- For pipeline, prompt, or retrieval changes, run the smoke eval (`--limit 10`) and compare with the last result in `eval/results/`. Measure rule and assemble changes by replaying a saved run (`--replay-of`). Report any metric that dropped. Live runs print a token budget check first; don't pass `--ignore-budget` without asking.
- While developing, use only the 10-note smoke set. Run the full gold set (20 notes today) only once, at the end of a milestone. The Groq free tier caps gpt-oss-120b at 200k tokens per rolling day; a pipeline note costs roughly 4k tokens and a baseline note under 1k (M4 estimate), so budget full runs.
- Ask yourself: would a staff engineer approve this change?

### 4. Simple and elegant, in balance

- For non-trivial changes, pause and ask whether there is a simpler design.
- If a fix feels hacky, rewrite it the clean way using what you now know.
- Don't over-engineer simple fixes. No new dependency, service, or abstraction without a clear reason noted in `tasks/todo.md`.

### 5. Fix bugs on your own

- Given a bug report, a failing test, or a CI failure: find the root cause and fix it. Don't ask me to walk you through it.
- No temporary patches, no skipped tests, no loosened assertions, no `# type: ignore` to get green.
- If the fix requires a design change, stop and explain why.

### 6. Learn from corrections

- After any correction from me, add an entry to `tasks/lessons.md`: what went wrong, and the rule that prevents it.
- Review `tasks/lessons.md` at the start of each session and follow it.

## Task management

1. Write the plan to `tasks/todo.md` with checkable items.
2. Check in before starting implementation.
3. Tick items off as you finish them.
4. Give a short summary of what changed at each step.
5. Add a Review section to `tasks/todo.md` at the end: what was done, how it was verified, anything left open.
6. Update `tasks/lessons.md` after any correction.

Create `tasks/todo.md` and `tasks/lessons.md` if they don't exist.

## Code conventions

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, full type hints. Ruff for lint and format, mypy for types.
- All Pydantic types live in `backend/app/models/`, named exactly as in `DESIGN.md` Section 5.
- Rules are pure functions: `apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput`. No LLM calls, no db calls inside a rule.
- Each pipeline node is its own file in `backend/app/pipeline/nodes/`. Nodes read and write `PipelineState` only.
- Prompts are versioned files in `backend/app/llm/prompts/` (`extract_v1.md`). To change a prompt, add a new version. Don't edit an old one.
- Errors use the `ErrorCode` values in `DESIGN.md`. Don't invent new codes without updating `DESIGN.md`.
- Every schema change goes through an Alembic migration.
- Frontend: TypeScript strict mode. API types come only from the generated `lib/types.ts`.
- Commit messages are short and in the imperative ("Add R9 CKD stage gap rule").

## Core principles

- **Simplicity first.** Make every change as small and simple as possible.
- **No laziness.** Find root causes. Senior developer standards.
- **Minimal impact.** Only touch what the task needs. Don't refactor unrelated code in the same change.
