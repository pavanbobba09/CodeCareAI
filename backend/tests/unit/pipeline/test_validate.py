from app.models import CandidateSet, ClinicalFact, CodeCandidate, CodeSelection, FactLink
from app.pipeline.validate import validate_facts, validate_selections


def _fact(fid: str, evidence: list[int], links: list[FactLink] | None = None) -> ClinicalFact:
    return ClinicalFact(
        fact_id=fid,
        kind="condition",
        concept="c",
        status="active",
        details={},
        links=links or [],
        evidence=evidence,
    )


def _sel(fid: str, code: str | None, evidence: list[int]) -> CodeSelection:
    return CodeSelection(fact_id=fid, code=code, evidence=evidence, rationale="r")


def _cands(fid: str, *codes: str) -> CandidateSet:
    return CandidateSet(
        fact_id=fid,
        candidates=[
            CodeCandidate(code=c, system="ICD-10-CM", description=c, score=1.0, sources=["text"])
            for c in codes
        ],
    )


def test_facts_with_unknown_or_missing_evidence_are_dropped_and_counted() -> None:
    facts = [_fact("f1", [1]), _fact("f2", [9]), _fact("f3", []), _fact("f4", [2, 1, 2])]

    kept, errors = validate_facts(facts, {1, 2, 3})

    assert [f.fact_id for f in kept] == ["f1", "f4"]
    assert kept[1].evidence == [1, 2]
    assert errors == 2


def test_duplicate_fact_ids_keep_the_first() -> None:
    kept, errors = validate_facts([_fact("f1", [1]), _fact("f1", [2])], {1, 2})
    assert [f.evidence for f in kept] == [[1]]
    assert errors == 1


def test_links_to_dropped_facts_are_removed_and_counted() -> None:
    link = FactLink(type="associated_with", target_fact_id="f2")
    kept, errors = validate_facts([_fact("f1", [1], [link]), _fact("f2", [7])], {1})
    assert kept[0].links == []
    assert errors == 2  # f2 bad evidence + dangling link


def test_selection_outside_candidates_is_dropped_and_counted() -> None:
    sets = [_cands("f1", "E11.22"), _cands("f2", "N18.30")]
    sels = [
        _sel("f1", "E11.22", [1]),
        _sel("f1", "N18.30", [1]),  # candidate of another fact
        _sel("f9", "E11.22", [1]),  # unknown fact
        _sel("f2", "Z99.99", [1]),  # invented code
    ]
    kept, errors = validate_selections(sels, sets, {1})
    assert [(s.fact_id, s.code) for s in kept] == [("f1", "E11.22")]
    assert errors == 3


def test_selection_with_bad_evidence_is_dropped() -> None:
    kept, errors = validate_selections([_sel("f1", "E11.22", [4])], [_cands("f1", "E11.22")], {1})
    assert (kept, errors) == ([], 1)


def test_null_code_and_duplicates_are_not_errors() -> None:
    sels = [_sel("f1", None, []), _sel("f1", "E11.22", [1]), _sel("f1", "E11.22", [1])]
    kept, errors = validate_selections(sels, [_cands("f1", "E11.22")], {1})
    assert len(kept) == 1
    assert errors == 0
