"""The full rule chain: order, R1 on rule-added codes, gap wording, ids."""

import re

from app.rules import r9_ckd_stage, r10_heart_failure_type
from app.terminology.lookup import CodeRecord
from tests.unit.rules.helpers import by_code, codes_of, fact, lookup, run_chain, sug

HTN = fact("f1", "hypertension", [1])
HF = fact("f2", "chronic systolic heart failure", [2])
CKD = fact("f3", "chronic kidney disease", [3], details={"stage": "3a"})
TRIAD = [sug("s1", "I10", ["f1"]), sug("s2", "I50.22", ["f2"]), sug("s3", "N18.31", ["f3"])]


def test_triad_gives_i13_0_with_i50_and_n18_and_no_i10() -> None:
    out = run_chain(TRIAD, [HTN, HF, CKD])

    assert codes_of(out) == ["I13.0", "I50.22", "N18.31"]
    i13 = by_code(out, "I13.0")
    assert (i13.suggestion_id, i13.added_by_rule) == ("s4", "R5")
    assert [r.rule_id for r in i13.rule_results] == ["R5", "R1"]  # R1 checked the added code


def test_diabetes_type_normalizes_before_ckd_combination() -> None:
    dm = fact("f1", "diabetes mellitus", [1])
    ckd = fact("f2", "chronic kidney disease stage 4", [2])
    out = run_chain([sug("s1", "E13.9", ["f1"]), sug("s2", "N18.4", ["f2"])], [dm, ckd])

    assert "E11.22" in codes_of(out)
    assert "E13.9" not in codes_of(out)


def test_added_code_absent_from_code_set_is_dropped_by_r1() -> None:
    out = run_chain(TRIAD, [HTN, HF, CKD], lookup(without={"I13.0"}))

    assert "I13.0" not in codes_of(out)
    assert ("I13.0", "R1") in [(d.code, d.rule_id) for d in out.dropped]


def test_added_code_not_billable_is_dropped_by_r1() -> None:
    dm, ckd = fact("f1", "type 2 diabetes mellitus", [1]), fact("f2", "chronic kidney disease", [2])
    out = run_chain(
        [sug("s1", "E11.9", ["f1"]), sug("s2", "N18.32", ["f2"])],
        [dm, ckd],
        lookup(not_billable={"E11.22"}),
    )

    assert "E11.22" not in codes_of(out)
    assert any(
        d.code == "E11.22" and d.rule_id == "R1" and "not billable" in d.reason for d in out.dropped
    )


def test_added_code_from_another_release_is_dropped_by_r1() -> None:
    only_fy2026 = {("ICD10CM-FY2026", "I13.0"): CodeRecord("I13.0", "ICD-10-CM", "d", True, "I13")}
    out = run_chain(TRIAD, [HTN, HF, CKD], lookup(without={"I13.0"}, extra=only_fy2026))

    assert "I13.0" not in codes_of(out)
    assert any(d.code == "I13.0" and "not in ICD10CM-FY2027" in d.reason for d in out.dropped)


def test_gap_on_a_removed_code_is_dropped() -> None:
    ckd = fact("f3", "chronic kidney disease", [3])
    esrd = fact("f4", "end-stage renal disease", [4])
    out = run_chain([sug("s1", "N18.9", ["f3"]), sug("s2", "N18.6", ["f4"])], [ckd, esrd])

    assert codes_of(out) == ["N18.6"]
    assert out.gaps == []


LEADING = re.compile(
    r"higher|more specific code|reimburse|payment|pay|revenue|consider documenting|"
    r"should document|\b[A-Z]\d{2}(\.\w+)?\b",
)


def test_gap_queries_are_neutral() -> None:
    queries = [q for _, q in r9_ckd_stage.MISSING.values()] + [
        q for _, q in r10_heart_failure_type.MISSING.values()
    ]
    for q in queries:
        assert not LEADING.search(q), q
        assert q.endswith("if known."), q
