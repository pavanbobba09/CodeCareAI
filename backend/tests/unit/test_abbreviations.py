import csv
from pathlib import Path

from app.terminology.abbreviations import expand

ABBR = {"CKD": "chronic kidney disease", "DM2": "type 2 diabetes mellitus", "HF": "heart failure"}


def test_expands_whole_tokens_case_insensitive() -> None:
    assert expand("dm2 with CKD 3b", ABBR) == (
        "type 2 diabetes mellitus with chronic kidney disease 3b",
        True,
    )


def test_leaves_partial_tokens_alone() -> None:
    assert expand("HFrEF and CKDs", ABBR) == ("HFrEF and CKDs", False)


def test_no_abbreviation_means_not_expanded() -> None:
    assert expand("essential hypertension", ABBR) == ("essential hypertension", False)


def test_project_heart_failure_mapping_follows_coding_guidance() -> None:
    # FY2027 Index: Failure, heart, reduced ejection fraction -> see Failure, heart, systolic;
    # preserved ejection fraction -> see Failure, heart, diastolic.
    csv_path = Path(__file__).parents[3] / "data" / "abbreviations.csv"
    with csv_path.open(newline="") as f:
        mapping = {r["abbr"].upper(): r["expansion"] for r in csv.DictReader(f)}

    assert mapping["HFREF"] == "systolic heart failure"
    assert mapping["HFPEF"] == "diastolic heart failure"
