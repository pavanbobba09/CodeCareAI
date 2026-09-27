"""Candidate retrieval (DESIGN.md §4.1 step 6).

Four sources, merged by reciprocal rank fusion:
- abbreviation: the fact text was expanded (DM2 -> type 2 diabetes mellitus) before searching
- index: trigram match against Alphabetic Index term paths
- text: Postgres full-text search over official descriptions
- vector: bge-small cosine similarity over official descriptions

Only billable codes from the requested code set are returned, at most MAX_CANDIDATES.
"""

from collections.abc import Mapping, Sequence

from sqlalchemy import Text, cast, func, select, text
from sqlalchemy.orm import Session

from app.db.models import Code, IndexTerm
from app.models import (
    CandidateSet,
    CandidateSource,
    ClinicalFact,
    CodeCandidate,
    CodeSetSelection,
    CodeSystem,
)
from app.terminology.abbreviations import expand, load_abbreviations
from app.terminology.embedder import Embedder

MAX_CANDIDATES = 20
PER_SOURCE = 40
RRF_K = 60  # standard reciprocal-rank-fusion constant
TRIGRAM_THRESHOLD = 0.2
DESCENDANTS_PER_INDEX_HIT = 5


def build_query(fact: ClinicalFact) -> str:
    """Concept plus details, e.g. 'chronic kidney disease stage 3b'."""
    parts = [fact.concept, *(f"{k} {v}" for k, v in sorted(fact.details.items()))]
    return " ".join(p for p in parts if p.strip())


def rrf_merge(
    ranked: Mapping[CandidateSource, Sequence[str]], limit: int = MAX_CANDIDATES
) -> list[tuple[str, float, list[CandidateSource]]]:
    """Merge per-source ranked code lists. Ties break by code for stable output."""
    scores: dict[str, float] = {}
    sources: dict[str, list[CandidateSource]] = {}
    for source, codes in ranked.items():
        for rank, code in enumerate(dict.fromkeys(codes)):
            scores[code] = scores.get(code, 0.0) + 1.0 / (RRF_K + rank + 1)
            sources.setdefault(code, []).append(source)
    order = sorted(scores, key=lambda c: (-scores[c], c))[:limit]
    return [(c, round(scores[c], 6), sources[c]) for c in order]


def index_hits(session: Session, query: str, code_set_id: str) -> list[str]:
    session.execute(text(f"SET LOCAL pg_trgm.similarity_threshold = {TRIGRAM_THRESHOLD}"))
    sim = func.similarity(IndexTerm.term, query)
    hits = session.execute(
        select(IndexTerm.code, Code.billable)
        .join(Code, (Code.code_set_id == IndexTerm.code_set_id) & (Code.code == IndexTerm.code))
        .where(IndexTerm.code_set_id == code_set_id, IndexTerm.term.op("%")(query))
        .order_by(sim.desc(), IndexTerm.code)
        .limit(PER_SOURCE)
    ).all()

    codes: list[str] = []
    for code, billable in hits:
        if billable:
            codes.append(code)
            continue
        # Index points at a category ("N18.3-"): offer its billable descendants.
        codes.extend(
            session.scalars(
                select(Code.code)
                .where(
                    Code.code_set_id == code_set_id,
                    Code.billable.is_(True),
                    Code.code.like(f"{code}%"),
                )
                .order_by(Code.code)
                .limit(DESCENDANTS_PER_INDEX_HIT)
            )
        )
    return codes


def text_hits(session: Session, query: str, code_set_id: str) -> list[str]:
    # OR the query lexemes so partial matches still rank; ts_rank_cd orders them.
    tsq = func.to_tsquery(
        "english", func.replace(cast(func.plainto_tsquery("english", query), Text), "&", "|")
    )
    return list(
        session.scalars(
            select(Code.code)
            .where(Code.code_set_id == code_set_id, Code.billable.is_(True), Code.tsv.op("@@")(tsq))
            .order_by(func.ts_rank_cd(Code.tsv, tsq).desc(), Code.code)
            .limit(PER_SOURCE)
        )
    )


def vector_hits(session: Session, vector: list[float], code_set_id: str) -> list[str]:
    session.execute(text("SET LOCAL hnsw.ef_search = 200"))
    return list(
        session.scalars(
            select(Code.code)
            .where(
                Code.code_set_id == code_set_id,
                Code.billable.is_(True),
                Code.embedding.is_not(None),
            )
            .order_by(Code.embedding.cosine_distance(vector), Code.code)
            .limit(PER_SOURCE)
        )
    )


def search_candidates(
    session: Session, fact: ClinicalFact, code_sets: CodeSetSelection, embedder: Embedder
) -> CandidateSet:
    system: CodeSystem = "CPT" if fact.kind == "procedure" else "ICD-10-CM"
    code_set_id = code_sets.cpt if system == "CPT" else code_sets.icd10cm

    query, expanded = expand(build_query(fact), load_abbreviations(session))
    [vector] = embedder.embed([query])

    ranked: dict[CandidateSource, list[str]] = {
        "index": index_hits(session, query, code_set_id),
        "text": text_hits(session, query, code_set_id),
        "vector": vector_hits(session, vector, code_set_id),
    }
    merged = rrf_merge(ranked)

    rows = session.execute(
        select(Code.code, Code.description).where(
            Code.code_set_id == code_set_id, Code.code.in_([c for c, _, _ in merged])
        )
    )
    descriptions = {code: description for code, description in rows}
    candidates = [
        CodeCandidate(
            code=code,
            system=system,
            description=descriptions[code],
            score=score,
            sources=["abbreviation", *sources] if expanded else sources,
        )
        for code, score, sources in merged
    ]
    return CandidateSet(fact_id=fact.fact_id, candidates=candidates)
