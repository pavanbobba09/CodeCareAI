from app.models import Suggestion
from app.pipeline.confidence import band, finalize
from tests.unit.rules.helpers import sug


def _with(code: str, *outcomes: str, gap: str | None = None, sid: str = "s1") -> Suggestion:
    s = sug(sid, code, ["f1"])
    results = [
        {"rule_id": "R1", "outcome": o, "message": "m", "source_ref": "x", "affects_codes": [code]}
        for o in outcomes
    ]
    return Suggestion.model_validate(
        {**s.model_dump(), "rule_results": results, "gap_ids": [gap] if gap else []}
    )


def test_bands() -> None:
    assert band(_with("I10", "pass")) == "strong"
    assert band(_with("I10", "pass", "needs_review")) == "review"
    assert band(_with("N18.30", "pass", gap="R9-N18.30")) == "review"
    assert band(_with("I50.9", "fail")) == "not_suggested"


def test_no_evidence_is_never_strong() -> None:
    s = _with("I10", "pass").model_copy(update={"evidence": []})
    assert band(s) == "review"


def test_two_ckd_stages_conflict() -> None:
    sugs, gaps = finalize([_with("N18.31", "pass", sid="s1"), _with("N18.4", "pass", sid="s2")], [])

    [gap] = gaps
    assert (gap.gap_id, gap.kind, gap.rule_id, gap.affects_codes) == (
        "conflict-N18",
        "conflicting",
        None,
        ["N18.31", "N18.4"],
    )
    assert [s.confidence for s in sugs] == ["review", "review"]


def test_one_code_per_family_has_no_conflict() -> None:
    sugs, gaps = finalize(
        [_with("N18.31", "pass", sid="s1"), _with("I50.22", "pass", sid="s2")], []
    )

    assert gaps == []
    assert [s.confidence for s in sugs] == ["strong", "strong"]
