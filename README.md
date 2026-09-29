# CodeCare AI

**CodeCare AI: an explainable ICD-10-CM coding copilot for outpatient notes.**

> Proof of concept. Synthetic data only, not reviewed by a certified coder, and not for real clinical or billing use.

![CodeCare AI review page](docs/review-page.png)

*The review page: the E11.22 card is selected and its evidence sentence is highlighted in the note.*

## The problem

Medical coders turn clinical notes into billing codes by hand. They follow long official rules, such as the ICD-10-CM Official Guidelines. A code must come from what the doctor wrote, not from what the patient may have. Mistakes lead to denials, lost revenue, audits, and rework. Medicare fee-for-service improper payments were 6.55% ($28.83 billion) in FY 2025 (ACDIS, 2026), and 41% of providers say more than 10% of their claims are denied (Experian Health, 2025). Asking an LLM for codes on its own does not fix this: in one benchmark, the best model exactly matched only 33.9% of ICD-10-CM codes (Soroush et al., 2024).

## The solution

**The LLM reads, plain code checks.** The AI does only two things: it reads the note and lists the facts it finds, and it picks codes from a short list of real codes pulled from the official code tables. It cannot make up a code. The official coding guidelines are written as ordinary Python rules, each with its own tests and its guideline citation. Every suggested code points to the sentence that supports it. A human coder makes the final decision on every code.

## How it works

```mermaid
flowchart LR
    A[Clinical note] --> B[Extract facts<br/>LLM]
    B --> C[Find candidate codes<br/>official code tables]
    C --> D[Pick codes<br/>LLM, candidates only]
    D --> E[Coding rules<br/>R1 to R12]
    E --> F[Documentation gaps]
    F --> G[Coder review]
```

1. **Extract facts:** the LLM lists each condition, medication, and procedure with its status (active, denied, suspected) and the numbered sentences that support it.
2. **Find candidate codes:** each fact is searched in the ICD-10-CM tables valid on the visit date, using the Alphabetic Index, full-text, and vector search.
3. **Pick codes:** the LLM chooses from up to 20 real candidates per fact; anything else is dropped.
4. **Coding rules:** plain Python rules apply the guidelines, for example combination codes, CKD stage, and uncertain diagnoses.
5. **Documentation gaps:** when a detail is missing, the system writes a neutral question for the doctor.
6. **Coder review:** the coder accepts, edits, or rejects each code, and every decision is saved.

## Worked example

Note (synthetic, visit date 2026-10-15), split into numbered sentences:
1. Patient with type 2 diabetes and chronic kidney disease stage 3.
2. Metformin continued.
3. Recheck kidney function in 3 months.

What the system returned (one live run with gpt-oss-120b):

| Output | Evidence | Status | Why |
|---|---|---|---|
| **E11.22** Type 2 diabetes mellitus with diabetic chronic kidney disease | sentence 1 | strong | Picked by the LLM. Rule R2 confirms both diabetes and CKD are documented and links it to both facts (the guidelines presume the link for "with", I.A.15). |
| **N18.30** Chronic kidney disease, stage 3 unspecified | sentence 1 | review | The note says stage 3 but not 3a or 3b, so rule R9 marks it for review. |
| **Z79.84** Long term (current) use of oral hypoglycemic drugs | sentence 2 | strong | Picked for the metformin fact (guideline I.C.4.a.3). |
| **Gap** (R9): CKD stage 3 subtype | | | Query: "The note documents chronic kidney disease stage 3 without 3a or 3b. Please document the subtype, if known." |

## What was built

- Fact extraction with sentence-level evidence; a code without valid evidence is dropped.
- Candidate search over the official CMS code tables and Alphabetic Index (trigram, full-text, and vector search).
- The code set is chosen by visit date: the April 2026 update of FY2026 before October 1, 2026, and FY2027 from then on.
- Coding rules as pure, tested functions (one file and one test file per rule):

| Rule | What it does | Status |
|---|---|---|
| R1 | Drops codes that do not exist, are not billable, or are not valid on the visit date | built |
| R2 | Diabetes with CKD: E11.22 plus the documented stage | built |
| R3 | Hypertension with CKD: I12.x instead of I10 | built |
| R4 | Hypertension with heart failure: I11.0 plus the I50 code | built |
| R5 | Hypertension, heart failure, and CKD: I13.x | built |
| R6 | Removes I10 when a combination code covers it | built |
| R7 | Matches the diabetes code to the documented type; defaults to type 2 and marks it for review | built |
| R8 | Adds long-term insulin or oral drug codes (Z79.4, Z79.84, Z79.85) | built |
| R9 | CKD stage: matches the documented stage; raises a gap when stage or 3a/3b is missing | built |
| R10 | Heart failure: matches type and acuity; raises a gap when either is missing | built |
| R11 | Suspected or ruled-out diagnoses are not coded as confirmed | built |
| R12 | Excludes1 conflicts: both codes go to review with a question | built |

- Neutral documentation gap queries (a test checks that no query names a code or pushes toward a higher-paying answer).
- A review screen with evidence highlighting, and accept, edit, or reject with append-only history.
- An evaluation harness with 20 gold notes, an LLM-only baseline, a token budget check, and replay of saved LLM outputs.

## Results

20 synthetic gold notes, the same model (gpt-oss-120b) in every column.

| Metric | LLM-only baseline | First pipeline (M3) | Final pipeline |
|---|---|---|---|
| Precision | 0.56 | 0.78 | **0.95** |
| Recall | 0.49 | 0.82 | **0.95** |
| Invented codes (not in the code set) | 0.03 | 0.00 | **0.00** |
| Invalid codes (invented or not billable) | 0.12 | 0.00 | **0.00** |
| Documentation gaps caught (4 expected) | 0.00 | 0.00 | **1.00** |

The final pipeline is more accurate than the LLM alone and never returned a code outside the official tables. The rules added the combination codes and all four expected gaps that the first pipeline missed. The final column is run `2026-09-28-n20-replay-extract_v1-fix-openai_gpt-oss-120b`: the saved LLM outputs of a live 20-note run, replayed through the final rules. All per-note results are in [eval/results/](eval/results/).

Remaining misses: n004 (the LLM picked E11.9 instead of E11.65), n014 (an extra I50.9 next to I50.20), and n015 (the symptom code R06.02 behind a suspected diagnosis was missed).

## Data used

- Official CMS ICD-10-CM code files for [FY2027](https://www.cms.gov/files/zip/2027-code-tables-tabular-index.zip) and the [April 1, 2026 update of FY2026](https://www.cms.gov/files/zip/april-1-2026-code-tables-tabular-index.zip) (tabular, Alphabetic Index, and [code descriptions](https://www.cms.gov/files/zip/2027-code-descriptions-tabular-order.zip)). `scripts/load_icd10cm.py` downloads them from cms.gov.
- The [FY2027 ICD-10-CM Official Guidelines](https://www.cms.gov/files/document/fy-2027-icd-10-cm-coding-guidelines.pdf), used to write and cite each rule (downloaded by hand, not by the script).
- 20 synthetic gold notes in [data/gold_notes/](data/gold_notes/). `scripts/validate_gold.py` checks that every expected code exists and is billable for the note's visit date.
- No real patient data anywhere in the repository.

## Key design decisions

- **Chose picking from retrieved candidates over free LLM coding** because it makes invented codes impossible (0.00 here vs 0.03 for the LLM alone).
- **Chose rules as tested code over rules in prompts** because code gives the same answer every time, can be tested, and cites its guideline section.
- **Chose "every code must own its evidence" over note-level checks** because a code must be supported by its own facts, not by a condition mentioned elsewhere in the note.
- **Chose deterministic scoring against a gold set over an LLM judge** because exact code matching is repeatable and cannot be talked into a pass.
- **Chose saved LLM outputs with replay over re-running the LLM** because rule changes can be measured with no API calls or tokens.
- **Chose an open-weight model through an OpenAI-compatible API, set only by env vars,** over a hardcoded provider, so the model can be swapped or hosted locally.

## Tech stack

| Part | Choice |
|---|---|
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 |
| Database and search | PostgreSQL 16, pgvector, pg_trgm; embeddings with BAAI/bge-small-en-v1.5 (fastembed) |
| Pipeline | LangGraph (a straight line of five steps) |
| LLM | gpt-oss-120b on Groq (any OpenAI-compatible API works) |
| Web app | Next.js 15, TypeScript, Tailwind |
| Tests | pytest, Playwright |

## Run it locally

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20, Docker.
```bash
git clone https://github.com/pavanbobba09/CodeCareAI.git && cd CodeCareAI
docker compose up -d --wait db                     # Postgres with pgvector and pg_trgm

uv venv --python 3.12 backend/.venv && source backend/.venv/bin/activate
cd backend && uv pip install -e ".[dev]" && cp .env.example .env && alembic upgrade head && cd ..

python scripts/seed_abbreviations.py
python scripts/load_icd10cm.py --fy 2027                    # downloads the CMS files
python scripts/embed_codes.py --code-set ICD10CM-FY2027     # about 30 minutes on CPU the first time
python scripts/load_icd10cm.py --fy 2026 && python scripts/embed_codes.py --code-set ICD10CM-FY2026   # optional: visits before Oct 1, 2026
```

Set the LLM in `backend/.env` (get a free key at [console.groq.com/keys](https://console.groq.com/keys)):

```
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=your-key-here
LLM_MODEL=openai/gpt-oss-120b
```

Start the backend and the web app in two terminals, then open http://localhost:3000:

```bash
cd backend && uvicorn app.main:app --reload       # API on :8000
cd frontend && npm install && npm run dev         # web app on :3000
```

**No API key?** Run a fake LLM that replays recorded answers. Start it in a third terminal, and start the backend with these variables instead. It answers only the "Worked example" sample note (pick it from "Load sample note"); other notes show a failed analysis.

```bash
python scripts/fake_llm.py --port 8765
cd backend && LLM_BASE_URL=http://127.0.0.1:8765/v1 LLM_API_KEY=fake LLM_MODEL=fake-replay uvicorn app.main:app --reload
```

## Tests and evaluation

Run with the backend venv active, from the repo root. The tests never call a real LLM.
```bash
cd backend && pytest tests/unit                  # unit tests: rules, metrics, models (no database)
cd backend && pytest tests/integration           # API and pipeline on a separate test database
cd frontend && npx playwright install chromium && npm run test:e2e   # browser tests with the fake LLM
python eval/run_eval.py --setup pipeline --limit 10                   # live smoke eval on 10 gold notes (uses tokens)
python eval/run_eval.py --replay-of 2026-09-28-n20-pipeline-extract_v1-openai_gpt-oss-120b   # replay: rules only, no tokens
```

## Project structure

| Folder | Contents |
|---|---|
| `backend/` | FastAPI app, pipeline, rules, prompts, migrations, tests |
| `frontend/` | Next.js review app and Playwright tests |
| `data/` | Gold notes, abbreviations, drug classes, worked example (CMS downloads go to `data/raw/`, not committed) |
| `eval/` | Evaluation harness, metrics, and every saved run |
| `scripts/` | Data loading, embedding, fake LLM, fixture recording |
| `docker/` | Database init script |
| `docs/` | Screenshot |
| `deliverables/` | Report, slides, video, resume |
| `tasks/` | Plans, reviews, and lessons from the build |

Full design (types, endpoints, tables, rule details, build order): [DESIGN.md](DESIGN.md).

## Limitations and future work

- The gold set is small (20 notes) and synthetic.
- No certified coder has reviewed the gold codes or the output.
- Outpatient ICD-10-CM only, for four conditions: diabetes, hypertension, CKD, and heart failure.
- CPT codes and office visit (E/M) levels are designed but not built.
- The Groq free tier limits gpt-oss-120b to 200k tokens per day; a note used 5,369 tokens on average in the final live run.
- Next steps: validate on MIMIC-IV-Note under a PhysioNet data use agreement with a locally hosted model; add CPT and E/M; publish a static live demo; add a calibrated LLM judge for evidence quality.

## Deliverables

- Report: [CodeCare_AI_Report.docx](deliverables/CodeCare_AI_Report.docx)
- Slides: [CodeCare_AI_Presentation.pptx](deliverables/CodeCare_AI_Presentation.pptx)
- Video: [CodeCare_AI_Video.mp4](deliverables/CodeCare_AI_Video.mp4)
- Resume: [PavanBobba_Resume.pdf](deliverables/PavanBobba_Resume.pdf)

## References

ACDIS. (2026, January 29). *News: CMS publishes FY 2025 improper payment figures*. CDI Strategies. https://acdis.org/articles/news-cms-publishes-fy-2025-improper-payment-figures

Centers for Medicare & Medicaid Services. (2026). *ICD-10-CM official guidelines for coding and reporting FY 2027*. https://www.cms.gov/files/document/fy-2027-icd-10-cm-coding-guidelines.pdf

Experian Health. (2025, September 23). *State of claims 2025: The denial problem (and is AI the answer?)*. https://www.experian.com/blogs/healthcare/state-of-claims-2025/

Soroush, A., Glicksberg, B. S., Zimlichman, E., Barash, Y., Freeman, R., Charney, A. W., Nadkarni, G. N., & Klang, E. (2024). Large language models are poor medical coders: Benchmarking of medical code querying. *NEJM AI, 1*(5). https://doi.org/10.1056/AIdbp2300040
