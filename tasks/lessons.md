# Lessons

Corrections from the owner and the rule that prevents each one. Review at the start of every session.

## 2026-09-26: Report exact codes, never families

**What went wrong:** The M1 search check reported HFrEF as passing with "I50.2x". The actual code was I50.23 (acute on chronic), and the correct I50.20 was not in the top 20. The family label hid a wrong answer.

**Rule:** Checks, tests, and reports always name the exact billable code expected and returned (I50.20, not I50.2x or "any I50.2"). Assertions use equality on the code, never `startswith`.

## 2026-09-26: Keep rule numbers in sync with DESIGN.md

**What went wrong:** `tasks/todo.md` numbered R12 to R14 differently from DESIGN.md §3.4 (todo: R12 = CPT support, R13 = MDM gap, R14 = NCCI; DESIGN: R12 = Excludes1, R13 = CPT support + NCCI, R14 = E/M). An instruction to "skip R12 to R14 without CPT" would have switched off the Excludes1 check.

**Rule:** DESIGN.md §3.4 owns rule numbers. Any file that names a rule (todo, tests, code, prompts, commit messages) uses DESIGN's number. Changing a rule's number or scope updates DESIGN.md and every reference in the same change. When an instruction names a rule by number, check the number against DESIGN.md before acting.

## 2026-09-27: Check guideline citations against the official PDF

**What went wrong:** R1 shipped in M2 citing "ICD-10-CM Guidelines §I.B.3" for level of detail. The FY2027 PDF puts Level of Detail in Coding at **I.B.2**; I.B.3 is the valid code range. The number came from memory. The owner asked for every gold-note citation to be checked against the PDF, and that check caught it.

**Rule:** Every guideline section cited in code (`source_ref`, docstrings), gold notes, prompts, or docs is checked against the Official Guidelines PDF for that fiscal year (`data/raw/fy-20XX-icd-10-cm-coding-guidelines.pdf`) before it is committed. Say "from memory, unverified" when a source cannot be checked, and name sources that are not the Official Guidelines (for example the Alphabetic Index or AHA Coding Clinic) as what they are.

## 2026-09-27: Every abbreviation mapping needs a source

**What went wrong:** `data/abbreviations.csv` mapped HFmrEF to "combined systolic and diastolic heart failure", and a unit test, two integration cases and `scripts/check_search.py` locked it in as I50.40. Neither the FY2027 Alphabetic Index nor the Guidelines support it; it came from memory of coding practice. The Index has "reduced ejection fraction: see Failure, heart, systolic" and "preserved ejection fraction: see Failure, heart, diastolic", and no entry for mildly reduced.

**Rule:** Every abbreviation mapping must cite the Index entry or guideline section that supports it, checked in that fiscal year's files in `data/raw/`. When there is no source, the abbreviation expands only to its literal words (HFmrEF -> "heart failure with mildly reduced ejection fraction") and search handles the rest. Tests may assert only mappings that have a cited source.

## 2026-09-27: Validate code support from that suggestion's own facts

**What went wrong:** Family guards accepted diabetes, hypertension, CKD or heart failure documented anywhere in the note. A code attached to an unrelated active fact could therefore borrow another suggestion's condition and pass.

**Rule:** Every condition code must own an active matching fact in its own `fact_ids`; combination codes must own every family they assert. A rule-added or normalized code carries only the facts and evidence that produced that code. Tests include a correctly documented condition elsewhere in the note so a global-presence check cannot pass.

## 2026-09-28: Ownership checks must fit the selection contract

**What went wrong:** R2 required a model-picked E11.22 to own both a diabetes and a CKD fact, but a selection can name only one fact. Every correctly picked E11.22 (the worked example and 4 gold notes) became `not_suggested`, and the worked-example test and `record_llm.py` still passed because they checked codes and evidence, not confidence.

**Rule:** A rule that checks a suggestion's facts must be satisfiable by what the LLM contract can produce; add a test that feeds a real-shaped selection. Tests and checks on suggested codes also assert that the code is reported (confidence is not `not_suggested`), not only that it is present.
