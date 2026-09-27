"""R8: long-term diabetes drug use -> Z79.4 (insulin), Z79.84 (oral), Z79.85 (injectable
non-insulin); each class documented gets its own code.

Source: ICD-10-CM Official Guidelines for Coding and Reporting FY2027, Section I.C.4.a.3
(Diabetes mellitus and the use of insulin, oral hypoglycemics, and injectable non-insulin
drugs: assign the Z79 code for each class the patient uses). Drug classes come from
`data/diabetes_drug_classes.csv`, each row citing its FDA label (DailyMed) for route.

Not covered (DESIGN.md known limits): temporary insulin use, which I.C.4.a.3 says does not
get Z79.4, is not detected.
"""

import csv
import re
from pathlib import Path

from app.models import RuleInput, RuleOutput, Suggestion
from app.rules.common import active, added, is_diabetes, present, result
from app.terminology.lookup import CodeLookup

RULE_ID = "R8"
SOURCE_REF = "ICD-10-CM Guidelines FY2027 §I.C.4.a.3"
CLASS_CODES = {"insulin": "Z79.4", "oral": "Z79.84", "injectable_non_insulin": "Z79.85"}
TARGET_CODES = frozenset(CLASS_CODES.values())
DRUGS_CSV = Path(__file__).resolve().parents[3] / "data" / "diabetes_drug_classes.csv"


def load_drug_classes(path: Path = DRUGS_CSV) -> dict[str, str]:
    with path.open(newline="") as f:
        return {row["drug"].lower(): row["class"] for row in csv.DictReader(f)}


DRUG_CLASSES = load_drug_classes()


def drug_class(text: str, classes: dict[str, str] = DRUG_CLASSES) -> str | None:
    lowered = text.lower()
    for drug in sorted(classes, key=len, reverse=True):
        if re.search(rf"\b{re.escape(drug)}\b", lowered):
            return classes[drug]
    return None


def apply(inp: RuleInput, codes: CodeLookup) -> RuleOutput:
    out: list[Suggestion] = list(inp.suggestions)
    diabetes = [s for s in active(out) if is_diabetes(s.code)]
    if not diabetes:
        return RuleOutput(suggestions=out, dropped=[], gaps=[])
    by_class: dict[str, list[str]] = {}
    for fact in inp.facts:
        if fact.kind != "medication" or fact.status != "active":
            continue
        cls = drug_class(f"{fact.details.get('drug', '')} {fact.concept}")
        if cls is not None:
            by_class.setdefault(cls, []).append(fact.fact_id)
    for cls, med_ids in by_class.items():
        target = CLASS_CODES[cls]
        if present(out, target):
            continue
        r = result(
            RULE_ID,
            "pass",
            f"Diabetes with current {cls.replace('_', ' ')} therapy: {target}.",
            SOURCE_REF,
            [target],
        )
        out.append(added(inp, codes, target, RULE_ID, diabetes, r, sorted(med_ids)))
    return RuleOutput(suggestions=out, dropped=[], gaps=[])
