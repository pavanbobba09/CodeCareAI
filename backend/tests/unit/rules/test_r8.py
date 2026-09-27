import csv

from app.models import ClinicalFact
from app.rules import r8_diabetes_drugs
from app.rules.r8_diabetes_drugs import DRUGS_CSV, drug_class
from tests.unit.rules.helpers import by_code, codes_of, fact, run, sug

DM = fact("f1", "type 2 diabetes mellitus", [1])


def med(fid: str, drug: str, n: int, status: str = "active") -> ClinicalFact:
    return fact(fid, drug, [n], kind="medication", status=status, details={"drug": drug})


def test_insulin_and_oral_get_both_codes() -> None:
    facts = [DM, med("f2", "metformin", 2), med("f3", "insulin glargine", 3)]
    out = run(r8_diabetes_drugs.apply, [sug("s1", "E11.9", ["f1"])], facts)

    assert codes_of(out) == ["E11.9", "Z79.4", "Z79.84"]
    z = by_code(out, "Z79.4")
    # Evidence: the diabetes fact and the medication fact together (Codex finding 11).
    assert (z.added_by_rule, z.fact_ids, z.evidence) == ("R8", ["f1", "f3"], [1, 3])


def test_injectable_non_insulin_gets_z79_85() -> None:
    out = run(
        r8_diabetes_drugs.apply, [sug("s1", "E11.9", ["f1"])], [DM, med("f2", "Trulicity", 2)]
    )

    assert "Z79.85" in codes_of(out)


def test_no_diabetes_code_means_no_drug_code() -> None:
    out = run(r8_diabetes_drugs.apply, [sug("s1", "I10", ["f1"])], [med("f2", "metformin", 2)])

    assert codes_of(out) == ["I10"]


def test_stopped_or_planned_drug_is_not_current_use() -> None:
    out = run(
        r8_diabetes_drugs.apply,
        [sug("s1", "E11.9", ["f1"])],
        [DM, med("f2", "metformin", 2, "planned")],
    )

    assert codes_of(out) == ["E11.9"]


def test_unknown_drug_has_no_class() -> None:
    assert drug_class("lisinopril") is None
    assert drug_class("Insulin Lispro") == "insulin"


def test_every_drug_row_cites_a_label_and_a_known_class() -> None:
    with DRUGS_CSV.open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows
    for row in rows:
        assert row["class"] in r8_diabetes_drugs.CLASS_CODES, row
        assert "DailyMed setid" in row["source"], row
