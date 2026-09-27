# Lessons

Corrections from the owner and the rule that prevents each one. Review at the start of every session.

## 2026-09-26: Report exact codes, never families

**What went wrong:** The M1 search check reported HFrEF as passing with "I50.2x". The actual code was I50.23 (acute on chronic), and the correct I50.20 was not in the top 20. The family label hid a wrong answer.

**Rule:** Checks, tests, and reports always name the exact billable code expected and returned (I50.20, not I50.2x or "any I50.2"). Assertions use equality on the code, never `startswith`.
