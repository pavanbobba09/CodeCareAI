from app.rules import r9_ckd_stage
from tests.unit.rules.helpers import by_code, codes_of, fact, outcomes, run, sug


def test_unstaged_ckd_keeps_n18_9_and_raises_gap() -> None:
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.9", ["f1"])], [fact("f1", "CKD", [1])])

    [gap] = out.gaps
    assert (gap.gap_id, gap.rule_id, gap.kind, gap.affects_codes) == (
        "R9-N18.9",
        "R9",
        "missing",
        ["N18.9"],
    )
    assert by_code(out, "N18.9").gap_ids == ["R9-N18.9"]
    assert outcomes(by_code(out, "N18.9"), "R9") == ["needs_review"]


def test_stage_3_without_subtype_raises_gap() -> None:
    ckd = fact("f1", "chronic kidney disease", [1], details={"stage": "3"})
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.30", ["f1"])], [ckd])

    assert [g.gap_id for g in out.gaps] == ["R9-N18.30"]


def test_documented_stage_passes_without_gap() -> None:
    ckd = fact("f1", "CKD stage 3b", [1])
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.32", ["f1"])], [ckd])

    assert out.gaps == []
    assert outcomes(by_code(out, "N18.32"), "R9") == ["pass"]


def test_stage_plus_esrd_keeps_n18_6_only() -> None:
    facts = [fact("f1", "CKD stage 4", [1]), fact("f2", "end-stage renal disease", [2])]
    out = run(r9_ckd_stage.apply, [sug("s1", "N18.4", ["f1"]), sug("s2", "N18.6", ["f2"])], facts)

    assert codes_of(out) == ["N18.6"]
    assert [(d.code, d.rule_id) for d in out.dropped] == [("N18.4", "R9")]
