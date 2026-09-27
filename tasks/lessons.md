# Lessons

Corrections from the owner and the rule that prevents each one. Review at the start of every session.

## 2026-09-26: Report exact codes, never families

**What went wrong:** The M1 search check reported HFrEF as passing with "I50.2x". The actual code was I50.23 (acute on chronic), and the correct I50.20 was not in the top 20. The family label hid a wrong answer.

**Rule:** Checks, tests, and reports always name the exact billable code expected and returned (I50.20, not I50.2x or "any I50.2"). Assertions use equality on the code, never `startswith`.

## 2026-09-26: Keep rule numbers in sync with DESIGN.md

**What went wrong:** `tasks/todo.md` numbered R12 to R14 differently from DESIGN.md §3.4 (todo: R12 = CPT support, R13 = MDM gap, R14 = NCCI; DESIGN: R12 = Excludes1, R13 = CPT support + NCCI, R14 = E/M). An instruction to "skip R12 to R14 without CPT" would have switched off the Excludes1 check.

**Rule:** DESIGN.md §3.4 owns rule numbers. Any file that names a rule (todo, tests, code, prompts, commit messages) uses DESIGN's number. Changing a rule's number or scope updates DESIGN.md and every reference in the same change. When an instruction names a rule by number, check the number against DESIGN.md before acting.
