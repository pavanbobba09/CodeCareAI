# CodeCare AI

**Work in progress.** CodeCare AI reads a synthetic outpatient clinical note and suggests ICD-10-CM codes. Each suggestion cites the note sentence that supports it, shows the results of deterministic rule checks, and lists documentation gaps. A human coder accepts, edits, or rejects every suggestion.

The LLM only extracts facts and picks from real candidate codes; plain code checks the coding rules. See `DESIGN.md` for the architecture and `tasks/todo.md` for progress.

## Important limits

- **Synthetic data only.** Every note in this repo is made up. It contains no real patient data.
- **Not reviewed by a certified coder.** Expected codes in the gold set were checked by the author against the FY2027 ICD-10-CM Official Guidelines and code tables, not by a certified professional coder.
- **Not for real clinical or billing use.** Do not use this project to code real patient records or to submit claims.

## Status

Milestones M0 to M3 are done: code tables and search, the end-to-end note-to-codes slice, and an evaluation harness with 20 gold notes and an LLM-only baseline. Results are in `eval/results/`. M4 (ICD-10 combination rules and documentation gaps) is in progress.
