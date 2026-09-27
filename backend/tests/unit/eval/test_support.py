"""Hand-labeled (code, cited sentences) pairs for the evidence support checker (finding 8).

Contexts are real FY2027 descriptions and Index paths (tests/fixtures/support_contexts_fy2027
.json); abbreviations are the project's data/abbreviations.csv. Labels were written by hand:
True = a coder would accept these sentences as support for the code.
"""

import csv
import json
from pathlib import Path

import pytest

from eval.support import SupportContext, check_support

ROOT = Path(__file__).parents[3]
CONTEXTS = json.loads((ROOT / "tests/fixtures/support_contexts_fy2027.json").read_text())
with (ROOT.parent / "data/abbreviations.csv").open(newline="") as f:
    ABBREVIATIONS = {r["abbr"].upper(): r["expansion"] for r in csv.DictReader(f)}


def _ctx(code: str) -> SupportContext:
    c = CONTEXTS[code]
    return SupportContext(c["description"], c["index_paths"], ABBREVIATIONS)


ACTIVE = ["active"]
# (code, cited sentences, fact statuses (None = baseline, no facts), supported, reason part)
PAIRS = [
    # names the condition, plain and through abbreviations
    ("I10", ["Essential hypertension, well controlled."], ACTIVE, True, ""),
    ("I10", ["HTN, stable on lisinopril."], ACTIVE, True, ""),
    ("I10", ["No chest pain; hypertension is controlled."], None, True, ""),
    ("E11.9", ["Type 2 diabetes mellitus without complications."], ACTIVE, True, ""),
    ("E11.9", ["DM2 on metformin."], None, True, ""),
    ("R06.02", ["Reports shortness of breath when climbing stairs."], ACTIVE, True, ""),
    ("E11.22", ["Type 2 diabetes mellitus with chronic kidney disease stage 3."], ACTIVE, True, ""),
    ("I12.9", ["Hypertension.", "Chronic kidney disease stage 4."], ACTIVE, True, ""),
    (
        "I13.0",
        ["Hypertension.", "Chronic diastolic heart failure.", "CKD stage 3a."],
        ACTIVE,
        True,
        "",
    ),
    ("I11.0", ["Hypertension.", "Chronic systolic heart failure."], ACTIVE, True, ""),
    ("Z79.84", ["Takes metformin 1000 mg twice daily."], ACTIVE, True, ""),
    ("Z79.4", ["Increase insulin glargine to 30 units nightly."], ACTIVE, True, ""),
    # details present
    ("N18.32", ["A/P: DM2, HTN, CKD 3b."], ACTIVE, True, ""),
    ("N18.31", ["Chronic kidney disease stage 3a."], ACTIVE, True, ""),
    ("N18.4", ["Chronic kidney disease stage 4."], None, True, ""),
    ("N18.6", ["End-stage renal disease on hemodialysis."], ACTIVE, True, ""),
    ("I50.22", ["Chronic systolic heart failure."], ACTIVE, True, ""),
    ("I50.20", ["HFrEF."], ACTIVE, True, ""),
    ("E11.65", ["Type 2 diabetes mellitus, poorly controlled."], ACTIVE, True, ""),
    # condition not named
    ("I10", ["Continue current regimen."], ACTIVE, False, "not named"),
    ("E11.22", ["Type 2 diabetes mellitus without complications."], ACTIVE, False, "not named"),
    ("Z79.84", ["Continue lisinopril."], ACTIVE, False, "not named"),
    # negated
    ("R06.02", ["Denies chest pain or shortness of breath."], ACTIVE, False, "negated"),
    ("I50.9", ["No heart failure symptoms."], ACTIVE, False, "negated"),
    (
        "N18.9",
        ["Chronic kidney disease was ruled out on repeat testing."],
        ACTIVE,
        False,
        "negated",
    ),
    ("I50.9", ["History of heart failure."], None, False, "negated"),
    ("I50.9", ["Possible heart failure."], None, False, "negated"),
    # missing details
    ("N18.32", ["Chronic kidney disease stage 3."], ACTIVE, False, "missing detail"),
    ("I50.23", ["Chronic systolic heart failure."], ACTIVE, False, "missing detail"),
    ("E10.9", ["Diabetes mellitus, controlled on metformin."], ACTIVE, False, "missing detail"),
    ("E10.9", ["Type 2 diabetes mellitus."], None, False, "missing detail"),
    ("E11.9", ["Type 1 diabetes mellitus."], None, False, "missing detail"),
    (
        "N18.4",
        ["Chronic kidney disease. Follow up in 4 weeks."],
        None,
        False,
        "missing detail",
    ),
    (
        "E11.65",
        ["Type 2 diabetes mellitus without complications."],
        ACTIVE,
        False,
        "missing detail",
    ),
    # not from an active fact
    ("I50.9", ["Possible heart failure."], ["suspected"], False, "no active fact"),
]


@pytest.mark.parametrize(("code", "cited", "statuses", "supported", "reason"), PAIRS)
def test_labeled_pair(
    code: str, cited: list[str], statuses: list[str] | None, supported: bool, reason: str
) -> None:
    ok, why = check_support(code, cited, _ctx(code), statuses)

    assert ok is supported, why
    assert reason in why


def test_the_labeled_set_is_balanced_enough() -> None:
    assert 30 <= len(PAIRS) <= 40
    assert 8 <= sum(1 for p in PAIRS if not p[3]) <= len(PAIRS) - 8
