Read and follow CLAUDE.md, DESIGN.md, tasks/todo.md, and tasks/lessons.md before any task. CLAUDE.md is the source of the working rules; where it says Claude Code, it means you.

# Project rules

1. The LLM only extracts facts and selects from candidates; deterministic code validates codes, rules, and E/M levels.
2. Every suggested code must cite valid supporting sentence numbers from the note.
3. Every code must come from the `codes` table and the code set valid on the visit date; never allow invented codes.
4. Use synthetic data only; never add real patient data, names, or PHI-like content to the repository, fixtures, logs, or prompts.
5. Never include AMA CPT text; use only the project's short descriptions in `data/cpt_subset.csv`.
6. Put each coding rule in its own file under `backend/app/rules/`, cite its guideline section, and give it a dedicated test; never place coding rules in prompts.
7. Keep documentation-gap queries neutral and never steer clinicians toward higher-paying answers.
8. Keep reviews append-only; never update or delete rows in the `reviews` table.
9. Tests must never call a real LLM; use recorded responses from `backend/tests/fixtures/llm/`.
10. Configure the LLM only through `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL`; never hardcode a provider or model.
11. Keep the LangGraph graph linear, with one failure branch and no loops, checkpointer, or agents, unless `DESIGN.md` is changed first.
12. Stay within scope: no authentication, claim submission, real-time analysis, inpatient coding, or payer rules without asking first.
