"""R3, R4 and R5 share the hypertension link logic, so their cases live together."""

from app.rules import r3_htn_ckd, r4_htn_hf, r5_htn_hf_ckd
from tests.unit.rules.helpers import by_code, codes_of, fact, outcomes, run, sug

HTN = fact("f1", "hypertension", [1])
HF = fact("f2", "chronic systolic heart failure", [2])
CKD = fact("f3", "chronic kidney disease", [3], details={"stage": "4"})


# R3 hypertension + CKD
def test_r3_adds_i12_9_for_stage_1_to_4() -> None:
    out = run(r3_htn_ckd.apply, [sug("s1", "I10", ["f1"]), sug("s2", "N18.4", ["f3"])], [HTN, CKD])

    added = by_code(out, "I12.9")
    assert (added.added_by_rule, added.fact_ids, added.evidence) == ("R3", ["f1", "f3"], [1, 3])


def test_r3_adds_i12_0_for_stage_5_or_esrd() -> None:
    out = run(r3_htn_ckd.apply, [sug("s1", "I10", ["f1"]), sug("s2", "N18.6", ["f3"])], [HTN, CKD])

    assert "I12.0" in codes_of(out)


def test_r3_no_ckd_adds_nothing() -> None:
    out = run(r3_htn_ckd.apply, [sug("s1", "I10", ["f1"])], [HTN])

    assert codes_of(out) == ["I10"]


def test_r3_ckd_caused_by_something_else_needs_review() -> None:
    ckd = fact("f3", "chronic kidney disease", [3], caused_by="f9")
    other = fact("f9", "glomerulonephritis", [4])
    out = run(
        r3_htn_ckd.apply, [sug("s1", "I10", ["f1"]), sug("s2", "N18.4", ["f3"])], [HTN, ckd, other]
    )

    assert codes_of(out) == ["I10", "N18.4"]
    assert outcomes(by_code(out, "I10"), "R3") == ["needs_review"]


# R4 hypertension + heart failure
def test_r4_adds_i11_0() -> None:
    out = run(r4_htn_hf.apply, [sug("s1", "I10", ["f1"]), sug("s2", "I50.22", ["f2"])], [HTN, HF])

    assert by_code(out, "I11.0").added_by_rule == "R4"


def test_r4_skips_when_i13_present() -> None:
    sugs = [sug("s1", "I13.0", ["f1"]), sug("s2", "I50.22", ["f2"]), sug("s3", "N18.4", ["f3"])]
    out = run(r4_htn_hf.apply, sugs, [HTN, HF, CKD])

    assert "I11.0" not in codes_of(out)


def test_r4_hf_caused_by_something_else_needs_review() -> None:
    hf = fact("f2", "heart failure", [2], caused_by="f9")
    other = fact("f9", "aortic stenosis", [4])
    out = run(
        r4_htn_hf.apply, [sug("s1", "I10", ["f1"]), sug("s2", "I50.22", ["f2"])], [HTN, hf, other]
    )

    assert "I11.0" not in codes_of(out)
    assert outcomes(by_code(out, "I50.22"), "R4") == ["needs_review"]


# R5 hypertension + heart failure + CKD
def test_r5_adds_i13_0_for_stage_1_to_4() -> None:
    sugs = [sug("s1", "I10", ["f1"]), sug("s2", "I50.22", ["f2"]), sug("s3", "N18.4", ["f3"])]
    out = run(r5_htn_hf_ckd.apply, sugs, [HTN, HF, CKD])

    added = by_code(out, "I13.0")
    assert (added.added_by_rule, added.fact_ids) == ("R5", ["f1", "f2", "f3"])


def test_r5_adds_i13_2_for_esrd() -> None:
    sugs = [sug("s1", "I10", ["f1"]), sug("s2", "I50.22", ["f2"]), sug("s3", "N18.6", ["f3"])]
    out = run(r5_htn_hf_ckd.apply, sugs, [HTN, HF, CKD])

    assert "I13.2" in codes_of(out)


def test_r5_blocked_ckd_link_leaves_r4() -> None:
    ckd = fact("f3", "chronic kidney disease", [3], caused_by="f9")
    other = fact("f9", "glomerulonephritis", [4])
    sugs = [sug("s1", "I10", ["f1"]), sug("s2", "I50.22", ["f2"]), sug("s3", "N18.4", ["f3"])]
    out = run(r5_htn_hf_ckd.apply, sugs, [HTN, HF, ckd, other])

    assert "I13.0" not in codes_of(out)
    out = run(r4_htn_hf.apply, out.suggestions, [HTN, HF, ckd, other])
    assert "I11.0" in codes_of(out)
