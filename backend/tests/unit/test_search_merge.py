from app.models import ClinicalFact
from app.terminology.search import RRF_K, build_query, rrf_merge


def _fact(concept: str, details: dict[str, str]) -> ClinicalFact:
    return ClinicalFact(
        fact_id="f1",
        kind="condition",
        concept=concept,
        status="active",
        details=details,
        links=[],
        evidence=[1],
    )


def test_build_query_appends_sorted_details() -> None:
    fact = _fact("chronic kidney disease", {"stage": "3b", "acuity": "chronic"})
    assert build_query(fact) == "chronic kidney disease acuity chronic stage 3b"


def test_rrf_rewards_codes_found_by_several_sources() -> None:
    merged = rrf_merge({"index": ["A", "B"], "text": ["B", "C"], "vector": ["B"]})

    assert [code for code, _, _ in merged] == ["B", "A", "C"]
    assert merged[0][2] == ["index", "text", "vector"]
    assert merged[0][1] == round(1 / (RRF_K + 2) + 2 / (RRF_K + 1), 6)


def test_rrf_dedupes_within_a_source_and_caps() -> None:
    merged = rrf_merge({"text": ["A", "A", "B", "C"]}, limit=2)

    assert [code for code, _, _ in merged] == ["A", "B"]
    assert merged[0][2] == ["text"]


def test_rrf_ties_break_by_code() -> None:
    merged = rrf_merge({"index": ["Z"], "text": ["A"]})
    assert [code for code, _, _ in merged] == ["A", "Z"]


def test_rrf_empty() -> None:
    assert rrf_merge({"index": [], "text": [], "vector": []}) == []
